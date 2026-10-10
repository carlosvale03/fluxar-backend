"""
Teste-inventário das relações graváveis (ISOL-01, AD-032).

Percorre os serializers que a API usa para gravar e falha se algum campo de
relação gravável não for `OwnedPrimaryKeyRelatedField`. Os serializers vêm de
duas fontes:

- o `serializer_class` de cada view registrada nas rotas do projeto;
- todo serializer definido nos módulos `serializers` dos apps do projeto, o
  que alcança os serializers criados dentro de actions (`TransferSerializer`,
  `CreditCardExpenseSerializer`, `InvoicePaymentSerializer`) e os que ainda
  forem criados.

As views que leem IDs direto de `request.data`, sem serializer (edição em lote
da série, aporte e resgate de meta, importação de OFX e planilha), usam
`get_owned_or_400` e não podem ser inspecionadas daqui; cada uma tem o próprio
teste (`test_escrita_lote.py`, `test_aporte_resgate.py`, `test_importacao.py`).
"""
import importlib
import importlib.util

from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase
from django.urls import get_resolver
from rest_framework import serializers
from rest_framework.relations import ManyRelatedField, RelatedField

from core.fields import (
    CARTAO_NAO_ENCONTRADO, CATEGORIA_NAO_ENCONTRADA, CLASSE_NAO_ENCONTRADA, CONTA_NAO_ENCONTRADA,
    META_NAO_ENCONTRADA, RECEBIMENTO_NAO_ENCONTRADO, TAG_NAO_ENCONTRADA, TRANSACAO_NAO_ENCONTRADA,
    OwnedPrimaryKeyRelatedField,
)

MENSAGENS = {
    CONTA_NAO_ENCONTRADA, CARTAO_NAO_ENCONTRADO, CATEGORIA_NAO_ENCONTRADA, TAG_NAO_ENCONTRADA,
    CLASSE_NAO_ENCONTRADA, META_NAO_ENCONTRADA, RECEBIMENTO_NAO_ENCONTRADO, TRANSACAO_NAO_ENCONTRADA,
}

# Serializers que nunca recebem dados da requisição, com o motivo.
SO_LEITURA = {
    'goals.serializers.GoalDepositSerializer':
        'só monta a resposta: aninhado em GoalSerializer.deposits e na action history',
}

# Relações graváveis da tabela do design; o inventário precisa encontrar todas.
ESPERADAS = {
    ('transactions.serializers.TransactionSerializer', 'account'),
    ('transactions.serializers.TransactionSerializer', 'credit_card'),
    ('transactions.serializers.TransactionSerializer', 'category'),
    ('transactions.serializers.TransactionSerializer', 'tags'),
    ('transactions.serializers.TransactionSerializer', 'target_account_id'),
    ('transactions.serializers.CategorySerializer', 'parent'),
    ('transactions.serializers.CategorySerializer', 'expense_class'),
    ('transactions.serializers.TransferSerializer', 'account_from'),
    ('transactions.serializers.TransferSerializer', 'account_to'),
    ('transactions.serializers.CreditCardExpenseSerializer', 'credit_card'),
    ('transactions.serializers.CreditCardExpenseSerializer', 'category'),
    ('transactions.serializers.CreditCardExpenseSerializer', 'tags'),
    ('transactions.serializers.VinculoSerializer', 'principal'),
    ('budgets.serializers.BudgetSerializer', 'category'),
    ('goals.serializers.GoalSerializer', 'account'),
    ('reports.serializers.FocusedMonitorItemSerializer', 'category'),
    ('reports.serializers.FocusedMonitorItemSerializer', 'tag'),
    ('accounts.serializers.CreditCardSerializer', 'account_id'),
    ('accounts.serializers.InvoicePaymentSerializer', 'account_id'),
    ('salario.serializers.PlanPartSerializer', 'account'),
    ('salario.serializers.PlanPartSerializer', 'goal'),
    ('salario.serializers.PlanSerializer', 'salary_categories'),
    ('salario.serializers.DivisionPreviewSerializer', 'receipt'),
    ('salario.serializers.DivisionCreateSerializer', 'receipt'),
}


def nome(classe):
    return f'{classe.__module__}.{classe.__qualname__}'


def serializers_das_rotas():
    def percorrer(padroes):
        for padrao in padroes:
            if hasattr(padrao, 'url_patterns'):
                yield from percorrer(padrao.url_patterns)
            else:
                view = getattr(padrao.callback, 'cls', None) or getattr(padrao.callback, 'view_class', None)
                classe = getattr(view, 'serializer_class', None)
                if classe is not None:
                    yield classe

    return set(percorrer(get_resolver().url_patterns))


def serializers_dos_apps():
    base = str(settings.BASE_DIR)
    encontrados = set()
    for app in apps.get_app_configs():
        if not app.path.startswith(base) or 'venv' in app.path:
            continue
        modulo = f'{app.name}.serializers'
        if importlib.util.find_spec(modulo) is None:
            continue
        for objeto in vars(importlib.import_module(modulo)).values():
            if (isinstance(objeto, type) and issubclass(objeto, serializers.BaseSerializer)
                    and objeto.__module__ == modulo):
                encontrados.add(objeto)
    return encontrados


def relacoes_gravaveis(classe):
    """(nome do campo, campo de relação) de cada relação gravável do serializer."""
    for nome_campo, campo in classe().fields.items():
        if campo.read_only:
            continue
        relacao = campo.child_relation if isinstance(campo, ManyRelatedField) else campo
        if isinstance(relacao, RelatedField):
            yield nome_campo, relacao


class InventarioRelacoesGravaveisTests(SimpleTestCase):

    def test_toda_relacao_gravavel_usa_o_campo_do_dono(self):
        classes = {
            classe for classe in serializers_das_rotas() | serializers_dos_apps()
            if nome(classe) not in SO_LEITURA
        }

        verificadas = set()
        for classe in sorted(classes, key=nome):
            for nome_campo, relacao in relacoes_gravaveis(classe):
                verificadas.add((nome(classe), nome_campo))
                with self.subTest(serializer=nome(classe), campo=nome_campo):
                    self.assertIsInstance(relacao, OwnedPrimaryKeyRelatedField)
                    self.assertIn(relacao.not_found_message, MENSAGENS)

        # O inventário alcançou todas as relações da tabela do design
        self.assertEqual(ESPERADAS - verificadas, set(), sorted(verificadas))

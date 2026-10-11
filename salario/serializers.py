"""
Entrada da API da gestão do salário (SALARIO-04 a SALARIO-11, SALARIO-14).

As contas, as metas, as categorias e o recebimento só aceitam objetos do
usuário da requisição; um id de outro usuário recebe a mesma mensagem de um
id inexistente (SALARIO-10, AD-010).

A parte com destino num cofrinho que é a conta de uma única meta ativa vira
uma parte com destino nessa meta, no plano salvo e na simulação, para que o
aporte some no valor da meta (SALARIO-76). Com mais de uma meta ativa no
cofrinho, não há como saber qual, e a parte fica com destino na conta.
"""
from decimal import Decimal

from rest_framework import serializers

from accounts.models import Account
from core.fields import (
    CATEGORIA_NAO_ENCONTRADA, CONTA_NAO_ENCONTRADA, META_NAO_ENCONTRADA, RECEBIMENTO_NAO_ENCONTRADO,
    OwnedPrimaryKeyRelatedField,
)
from core.valores import CENTAVO, validar_valor_positivo
from goals.models import Goal
from transactions.models import Category, Transaction

from .models import CONTA, CONTA_DO_SALARIO, DISPENSAVEL, ESSENCIAL, FIXO, META, PERCENTUAL

DESTINO_INDISPONIVEL = 'Escolha uma conta ativa ou uma meta ativa.'
SOMA_ACIMA_DE_100 = 'A soma dos percentuais passa de 100%.'
VALOR_FIXO_MINIMO = 'O valor fixo deve ser de pelo menos R$ 0,01.'
PERCENTUAL_FORA_DO_INTERVALO = 'O percentual deve ficar entre 0,01% e 100%.'
CAMPO_OBRIGATORIO = 'Este campo é obrigatório.'
CEM = Decimal('100')


def conta_disponivel(conta):
    """Conta que pode receber uma parte: qualquer conta ativa do usuário, cofrinho inclusive (SALARIO-05)."""
    return conta is not None and conta.is_active


def meta_disponivel(meta):
    """Meta que pode receber uma parte: ativa, concluída ou não (SALARIO-05)."""
    return meta is not None and meta.is_active


def meta_do_cofrinho(conta):
    """A única meta ativa que tem a conta como cofrinho, ou `None` (SALARIO-76)."""
    if conta is None or conta.type != 'PIGGY_BANK':
        return None
    metas = list(Goal.objects.filter(account=conta, user_id=conta.user_id, is_active=True)[:2])
    return metas[0] if len(metas) == 1 else None


class PlanPartSerializer(serializers.Serializer):
    """Uma parte do plano: nome, regra e destino (SALARIO-04, SALARIO-05)."""
    name = serializers.CharField(max_length=60)
    rule_type = serializers.ChoiceField(choices=[FIXO, PERCENTUAL])
    value = serializers.DecimalField(max_digits=12, decimal_places=2)
    destination_type = serializers.ChoiceField(
        choices=[CONTA, META, CONTA_DO_SALARIO], allow_null=True, required=False, default=None,
    )
    # Inativas entram no queryset para receber a mensagem do destino (SALARIO-11)
    account = OwnedPrimaryKeyRelatedField(
        queryset=Account.objects.all(), not_found_message=CONTA_NAO_ENCONTRADA,
        allow_null=True, required=False, default=None,
    )
    goal = OwnedPrimaryKeyRelatedField(
        queryset=Goal.objects.all(), not_found_message=META_NAO_ENCONTRADA,
        allow_null=True, required=False, default=None,
    )
    reference = serializers.ChoiceField(
        choices=[ESSENCIAL, DISPENSAVEL, ''], allow_blank=True, required=False, default='',
    )

    def validate(self, dados):
        erros = {}
        valor = dados['value']
        if dados['rule_type'] == FIXO and valor < CENTAVO:
            erros['value'] = [VALOR_FIXO_MINIMO]
        if dados['rule_type'] == PERCENTUAL and not (CENTAVO <= valor <= CEM):
            erros['value'] = [PERCENTUAL_FORA_DO_INTERVALO]

        destino = dados.get('destination_type')
        if destino == CONTA:
            dados['goal'] = None
            if dados.get('account') is None:
                erros['account'] = [CAMPO_OBRIGATORIO]
            elif not conta_disponivel(dados['account']):
                erros['account'] = [DESTINO_INDISPONIVEL]
            elif (meta := meta_do_cofrinho(dados['account'])) is not None:
                # O cofrinho de uma meta: a parte vai para a meta (SALARIO-76)
                dados['destination_type'], dados['account'], dados['goal'] = META, None, meta
        elif destino == META:
            dados['account'] = None
            if dados.get('goal') is None:
                erros['goal'] = [CAMPO_OBRIGATORIO]
            elif not meta_disponivel(dados['goal']):
                erros['goal'] = [DESTINO_INDISPONIVEL]
        else:
            dados['account'] = dados['goal'] = None
        if erros:
            raise serializers.ValidationError(erros)
        return dados


def soma_dos_percentuais(partes):
    return sum((p['value'] for p in partes if p['rule_type'] == PERCENTUAL), Decimal('0'))


def conferir_soma(partes):
    """Recusa com 400 `{detail}` os percentuais que passam de 100% (SALARIO-08)."""
    if soma_dos_percentuais(partes) > CEM:
        raise serializers.ValidationError({'detail': SOMA_ACIMA_DE_100})


class PlanSerializer(serializers.Serializer):
    """O plano inteiro, com as partes na ordem e as categorias de salário."""
    parts = PlanPartSerializer(many=True)
    # Só categorias de receita ativas do usuário (SALARIO-14)
    salary_categories = OwnedPrimaryKeyRelatedField(
        many=True, queryset=Category.objects.filter(type='INCOME', is_active=True),
        not_found_message=CATEGORIA_NAO_ENCONTRADA, required=False,
    )



class SalaryCategoriesSerializer(serializers.Serializer):
    """Só as categorias de salário, sem o plano (SALARIO-14)."""
    salary_categories = OwnedPrimaryKeyRelatedField(
        many=True, queryset=Category.objects.filter(type='INCOME', is_active=True),
        not_found_message=CATEGORIA_NAO_ENCONTRADA,
    )

class SimulateSerializer(serializers.Serializer):
    """Simulação: o valor e, opcionalmente, as partes ainda não salvas (SALARIO-13)."""
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, validators=[validar_valor_positivo])
    parts = PlanPartSerializer(many=True, required=False)


class AdjustmentsField(serializers.DictField):
    """`{part_id: valor}` com valores de zero para cima e duas casas (SALARIO-30)."""
    child = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0'))


class OutflowsField(serializers.DictField):
    """
    `{id da saída: id da parte | null}` (SALARIO-66). Os ids são conferidos
    contra a lista de saídas e o plano em `salario.saidas.escolhidas`, para
    que um id malformado receba a mesma mensagem de um inexistente
    (SALARIO-69).
    """
    child = serializers.CharField(allow_null=True, allow_blank=True)


class DivisionPreviewSerializer(serializers.Serializer):
    """Revisão de um recebimento (SALARIO-29, SALARIO-30, SALARIO-40, SALARIO-64)."""
    receipt = OwnedPrimaryKeyRelatedField(
        queryset=Transaction.objects.all(), not_found_message=RECEBIMENTO_NAO_ENCONTRADO,
    )
    adjustments = AdjustmentsField(required=False, default=dict)
    # Sem `outflows`, nenhuma saída é descontada
    outflows = OutflowsField(required=False, allow_null=True, default=dict)


class DivisionCreateSerializer(DivisionPreviewSerializer):
    """
    Geração: a revisão mais a chave da tentativa (SALARIO-37, AD-007) e,
    opcionalmente, o total mostrado na revisão (SALARIO-74).
    """
    idempotency_key = serializers.UUIDField(required=False, allow_null=True, default=None)
    expected_total = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True, default=None,
    )

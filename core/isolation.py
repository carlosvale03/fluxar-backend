"""
Ligações cruzadas entre dados de usuários diferentes (ISOL-16 a ISOL-18).

Uma ligação cruzada é um registro de um usuário ligado a um objeto de outro
usuário, ou a uma categoria-modelo sem dono. As funções recebem o registro de
models (`apps`): `django.apps.apps` no comando `check_isolation` e o registro
histórico na migração de dados. Por isso não importam models nem services da
aplicação.
"""
from collections import namedtuple

from django.db.models import F

CrossLink = namedtuple('CrossLink', 'tipo registro_id relacao alheio_id')

# (app, model, relação, dono do registro, dono do objeto ligado)
RELACOES = (
    ('transactions', 'Transaction', 'account', 'user_id', 'account__user_id'),
    ('transactions', 'Transaction', 'credit_card', 'user_id', 'credit_card__user_id'),
    ('transactions', 'Transaction', 'invoice', 'user_id', 'invoice__card__user_id'),
    ('transactions', 'Transaction', 'category', 'user_id', 'category__user_id'),
    # SPEC_DEVIATION: parcela de origem e série de origem não constam da tabela
    # de correção do design.
    # Reason: o servidor define as duas relações e a API não as aceita, mas uma
    # ligação cruzada nelas custa só uma consulta para achar e desfazer.
    ('transactions', 'Transaction', 'parent_transaction', 'user_id', 'parent_transaction__user_id'),
    ('transactions', 'Transaction', 'recurring_source', 'user_id', 'recurring_source__user_id'),
    ('transactions', 'RecurringTransaction', 'account', 'user_id', 'account__user_id'),
    ('transactions', 'RecurringTransaction', 'credit_card', 'user_id', 'credit_card__user_id'),
    ('transactions', 'RecurringTransaction', 'category', 'user_id', 'category__user_id'),
    ('transactions', 'Category', 'parent', 'user_id', 'parent__user_id'),
    ('accounts', 'CreditCard', 'account', 'user_id', 'account__user_id'),
    ('goals', 'Goal', 'account', 'user_id', 'account__user_id'),
    ('budgets', 'Budget', 'category', 'user_id', 'category__user_id'),
    ('reports', 'FocusedMonitorItem', 'category', 'user_id', 'category__user_id'),
    ('reports', 'FocusedMonitorItem', 'tag', 'user_id', 'tag__user_id'),
    ('goals', 'GoalDeposit', 'account', 'goal__user_id', 'account__user_id'),
)


def _consultas(apps):
    """
    Para cada relação, devolve (tipo, relação, queryset das ligações cruzadas,
    campo do ID do registro, campo do ID do objeto ligado). Registros sem dono
    (as categorias-modelo) ficam de fora.
    """
    for app, modelo, relacao, dono, dono_alheio in RELACOES:
        Model = apps.get_model(app, modelo)
        cruzadas = (
            Model.objects
            .filter(**{f'{relacao}__isnull': False, f'{dono}__isnull': False})
            .exclude(**{dono_alheio: F(dono)})
        )
        yield modelo, relacao, cruzadas, 'pk', f'{relacao}_id'

    Transaction = apps.get_model('transactions', 'Transaction')
    TransacaoTag = Transaction._meta.get_field('tags').remote_field.through
    cruzadas = TransacaoTag.objects.exclude(tag__user_id=F('transaction__user_id'))
    yield 'Transaction', 'tags', cruzadas, 'transaction_id', 'tag_id'


def find_cross_links(apps):
    """Lista cada ligação cruzada gravada, como `CrossLink` (ISOL-16)."""
    links = []
    for tipo, relacao, cruzadas, campo_registro, campo_alheio in _consultas(apps):
        pares = cruzadas.order_by(campo_registro).values_list(campo_registro, campo_alheio)
        links.extend(CrossLink(tipo, registro_id, relacao, alheio_id) for registro_id, alheio_id in pares)
    return links

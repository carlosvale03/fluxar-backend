"""
Ligações cruzadas entre dados de usuários diferentes (ISOL-16 a ISOL-18).

Uma ligação cruzada é um registro de um usuário ligado a um objeto de outro
usuário, ou a uma categoria-modelo sem dono. As funções recebem o registro de
models (`apps`): `django.apps.apps` no comando `check_isolation` e o registro
histórico na migração de dados. Por isso não importam models nem services da
aplicação.
"""
from collections import namedtuple
from decimal import Decimal

from django.db import transaction
from django.db.models import Exists, F, OuterRef, Q, Sum

CrossLink = namedtuple('CrossLink', 'tipo registro_id relacao alheio_id')

# Quantas ligações foram desfeitas e quantas contas, faturas e metas foram
# recalculadas.
FixReport = namedtuple('FixReport', 'ligacoes contas faturas metas')

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

# Registros excluídos em vez de terem a relação anulada (tabela de correção do design)
EXCLUIDOS = ('Budget', 'FocusedMonitorItem', 'GoalDeposit')

# Regra SALDO-01
ENTRADAS = ('INCOME', 'TRANSFER_IN')
SAIDAS = ('EXPENSE', 'TRANSFER_OUT', 'CREDIT_CARD', 'INVOICE_PAYMENT')


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


def _soma(queryset):
    return queryset.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')


def _recalcular_saldos(apps, conta_ids):
    """Saldo guardado pela regra SALDO-01, só com transações do dono da conta."""
    Account = apps.get_model('accounts', 'Account')
    Transaction = apps.get_model('transactions', 'Transaction')
    for conta in Account.objects.filter(pk__in=conta_ids):
        efetivadas = Transaction.objects.filter(account_id=conta.pk, user_id=conta.user_id, status='COMPLETED')
        saldo = (
            conta.initial_balance
            + _soma(efetivadas.filter(type__in=ENTRADAS))
            - _soma(efetivadas.filter(type__in=SAIDAS))
        )
        Account.objects.filter(pk=conta.pk).update(balance=saldo)


def _recalcular_faturas(apps, fatura_ids):
    """Total da fatura com as compras do dono do cartão, como `update_invoice_total`."""
    CreditCardInvoice = apps.get_model('accounts', 'CreditCardInvoice')
    Transaction = apps.get_model('transactions', 'Transaction')
    for fatura in CreditCardInvoice.objects.filter(pk__in=fatura_ids).select_related('card'):
        compras = Transaction.objects.filter(invoice_id=fatura.pk, type='CREDIT_CARD', user_id=fatura.card.user_id)
        CreditCardInvoice.objects.filter(pk=fatura.pk).update(total_amount=_soma(compras))


def _registros_que_contam(apps, meta_id):
    """
    Os registros da meta que entram no valor dela pela regra de
    `goals/valores.calcular` (META-01, AD-045): os sem transação e os com as
    transações ligadas efetivadas, só em contas do dono da meta. A regra é
    repetida aqui porque a migração `transactions/0007` roda com o registro
    histórico, antes dos campos das pernas (`goals/0008`): sem eles, todo
    registro é resolvido pelo `transaction_id`.
    """
    GoalDeposit = apps.get_model('goals', 'GoalDeposit')
    Transaction = apps.get_model('transactions', 'Transaction')
    nao_efetivadas = Transaction.objects.exclude(status='COMPLETED')
    registros = GoalDeposit.objects.filter(goal_id=meta_id, account__user_id=F('goal__user_id'))
    antigo = Q(transaction_id__isnull=False)
    campos = {campo.name for campo in GoalDeposit._meta.get_fields()}
    if {'transacao_saida', 'transacao_entrada'} <= campos:
        registros = registros.exclude(
            Exists(nao_efetivadas.filter(pk=OuterRef('transacao_saida_id')))
            | Exists(nao_efetivadas.filter(pk=OuterRef('transacao_entrada_id')))
        )
        antigo &= Q(transacao_saida__isnull=True, transacao_entrada__isnull=True)
    return registros.exclude(antigo & Exists(nao_efetivadas.filter(
        Q(transfer_id=OuterRef('transaction_id')) | Q(pk=OuterRef('transaction_id')),
    )))


def _recalcular_metas(apps, meta_ids):
    """Valor da meta como aportes menos resgates que contam (META-01, AD-045)."""
    Goal = apps.get_model('goals', 'Goal')
    for meta_id in meta_ids:
        registros = _registros_que_contam(apps, meta_id)
        valor = _soma(registros.filter(type='DEPOSIT')) - _soma(registros.filter(type='WITHDRAWAL'))
        Goal.objects.filter(pk=meta_id).update(current_amount=valor)


def fix_cross_links(apps):
    """
    Desfaz cada ligação cruzada conforme a tabela de correção do design e
    recalcula o saldo das contas, o total das faturas e o valor das metas que
    perderam registros (ISOL-17, ISOL-18). `QuerySet.update()` e `delete()`
    não disparam os signals, por isso os recálculos são feitos aqui. Rodar de
    novo não muda nada.
    """
    ligacoes = 0
    contas, faturas, metas = set(), set(), set()
    with transaction.atomic():
        for tipo, relacao, cruzadas, campo_registro, campo_alheio in _consultas(apps):
            pares = list(cruzadas.values_list(campo_registro, campo_alheio))
            if not pares:
                continue
            ligacoes += len(pares)
            alheios = {alheio_id for _, alheio_id in pares}
            if (tipo, relacao) == ('Transaction', 'account'):
                contas |= alheios
            elif (tipo, relacao) == ('Transaction', 'invoice'):
                faturas |= alheios
            elif tipo == 'GoalDeposit':
                metas |= set(cruzadas.values_list('goal_id', flat=True))

            if relacao == 'tags' or tipo in EXCLUIDOS:
                cruzadas.delete()
            else:
                cruzadas.update(**{relacao: None})

        _recalcular_saldos(apps, contas)
        _recalcular_faturas(apps, faturas)
        _recalcular_metas(apps, metas)
    return FixReport(ligacoes, len(contas), len(faturas), len(metas))

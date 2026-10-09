"""
Regras comuns dos relatórios (AD-029, AD-046, spec `relatorios`).

Todos os relatórios, o dashboard e o gasto dos orçamentos escolhem as
transações por aqui, para que os números batam de uma tela para outra:

- despesas: as efetivadas na data delas e as compras no cartão na data da
  compra (`report_date`), mesmo com a fatura aberta (REL-01, REL-02);
- "A pagar": as despesas pendentes, à parte (REL-04);
- receitas: só as efetivadas, na data delas (REL-05);
- transferências, pagamentos de fatura e ajustes de saldo ficam fora de
  receitas e despesas (REL-03, REL-05);
- as transações de contas excluídas continuam nos períodos passados, porque o
  filtro é pelo usuário, não pela conta ativa (REL-07).

Datas e meses seguem o calendário de Brasília (REL-08, AD-008), e todo valor
sai em `Decimal`, sem ponto flutuante (REL-10).
"""
from decimal import Decimal

from django.db.models import Case, F, OuterRef, Q, Subquery, Sum, When
from django.db.models.functions import ExtractHour, ExtractWeekDay

from accounts.faturas import dia_no_mes, mes_anterior
from accounts.models import Account
from accounts.saldo import ENTRADAS, SAIDAS
from core.datas import BRASILIA, hoje
from transactions.models import Transaction

ZERO = Decimal('0.00')

# Partes do patrimônio por tipo de conta (REL-14, REL-15)
DISPONIVEL = ('CHECKING', 'SAVINGS', 'WALLET')
RESERVAS = ('PIGGY_BANK',)
INVESTIMENTOS = ('INVESTMENT',)
# Contas em que o dinheiro fica guardado (REL-20)
GUARDADO = RESERVAS + INVESTIMENTOS


def total(queryset):
    """A soma de `amount` do queryset, em `Decimal`; vazio vale zero."""
    return queryset.aggregate(total=Sum('amount'))['total'] or ZERO


# --- Calendário (REL-08, REL-17) ---

def mes_atual():
    """`(ano, mes)` de hoje no calendário de Brasília."""
    dia = hoje()
    return dia.year, dia.month


def limites_do_mes(ano, mes):
    """`(primeiro dia, último dia)` do mês."""
    return dia_no_mes(ano, mes, 1), dia_no_mes(ano, mes, 31)


def meses_do_calendario(fim, quantidade):
    """
    Os `quantidade` meses do calendário que terminam no mês de `fim`, do mais
    antigo ao mais recente, como `(ano, mes)`: cada mês uma vez só, sem pular
    nem repetir (REL-17).
    """
    mes, ano = fim.month, fim.year
    meses = []
    for _ in range(quantidade):
        meses.append((ano, mes))
        mes, ano = mes_anterior(mes, ano)
    return meses[::-1]


def hora_em_brasilia(campo='created_at'):
    """A hora do dia de `campo` no fuso de Brasília (REL-09)."""
    return ExtractHour(campo, tzinfo=BRASILIA)


def dia_da_semana_em_brasilia(campo='created_at'):
    """O dia da semana de `campo` no fuso de Brasília, de 1 (domingo) a 7 (sábado) (REL-09)."""
    return ExtractWeekDay(campo, tzinfo=BRASILIA)


# --- Despesas, "A pagar" e receitas (REL-01 a REL-05, REL-07) ---

def despesas(usuario, inicio, fim):
    """
    As despesas do período pela `report_date`: as `EXPENSE` efetivadas e as
    compras no cartão em qualquer status, sem os ajustes de saldo (REL-01 a
    REL-03). Transferências e pagamentos de fatura não entram pelo tipo.
    """
    return Transaction.objects.filter(
        Q(type='EXPENSE', status='COMPLETED') | Q(type='CREDIT_CARD'),
        user=usuario, report_date__gte=inicio, report_date__lte=fim, is_balance_adjustment=False,
    )


def a_pagar(usuario, inicio, fim):
    """As `EXPENSE` pendentes com `date` no período, sem os ajustes de saldo (REL-04)."""
    return Transaction.objects.filter(
        user=usuario, type='EXPENSE', status='PENDING', date__gte=inicio, date__lte=fim,
        is_balance_adjustment=False,
    )


def receitas(usuario, inicio, fim):
    """As `INCOME` efetivadas com `date` no período, sem os ajustes de saldo (REL-05)."""
    return Transaction.objects.filter(
        user=usuario, type='INCOME', status='COMPLETED', date__gte=inicio, date__lte=fim,
        is_balance_adjustment=False,
    )


# --- Patrimônio (REL-13 a REL-16) ---

def _data_de_efetivacao():
    """A compra no cartão paga conta no `payment_date`; as demais, na `date`."""
    return Case(
        When(type='CREDIT_CARD', payment_date__isnull=False, then=F('payment_date')),
        default=F('date'),
    )


def _saldos_em(contas, em):
    """
    `{id da conta: saldo}` no fim do dia `em`: saldo inicial mais as entradas
    menos as saídas efetivadas até `em`, só do dono da conta (SALDO-01).
    """
    saldos = {conta.pk: conta.initial_balance for conta in contas}
    somas = Transaction.objects.filter(
        account_id__in=saldos, user_id=F('account__user_id'), status='COMPLETED',
    ).annotate(efetivada_em=_data_de_efetivacao()).filter(efetivada_em__lte=em).values('account_id').annotate(
        entradas=Sum('amount', filter=Q(type__in=ENTRADAS)),
        saidas=Sum('amount', filter=Q(type__in=SAIDAS)),
    )
    for soma in somas:
        saldos[soma['account_id']] += (soma['entradas'] or ZERO) - (soma['saidas'] or ZERO)
    return saldos


def patrimonio(usuario, em=None):
    """
    O patrimônio do usuário dividido em disponível, reservas (cofrinhos),
    investimentos e faturas em aberto, e o total: as contas ativas menos as
    compras não pagas dos cartões (REL-13 a REL-15).
    - Sem `em`: os saldos atuais das contas ativas e todas as compras no
      cartão pendentes.
    - Com `em`: o saldo de cada conta ativa no fim do dia `em` e as compras
      no cartão com `report_date` até `em` ainda não pagas nele (REL-16).
    """
    contas = list(Account.objects.filter(user=usuario, is_active=True))
    if em is None:
        saldos = {conta.pk: conta.balance for conta in contas}
        faturas = total(Transaction.objects.filter(user=usuario, type='CREDIT_CARD', status='PENDING'))
    else:
        saldos = _saldos_em(contas, em)
        faturas = total(
            Transaction.objects.filter(user=usuario, type='CREDIT_CARD', report_date__lte=em)
            .annotate(efetivada_em=_data_de_efetivacao())
            .filter(Q(status='PENDING') | Q(efetivada_em__gt=em))
        )

    def soma(tipos):
        return sum((saldos[c.pk] for c in contas if c.type in tipos), ZERO)

    partes = {
        'disponivel': soma(DISPONIVEL),
        'reservas': soma(RESERVAS),
        'investimentos': soma(INVESTIMENTOS),
        'faturas_em_aberto': faturas,
    }
    partes['total'] = partes['disponivel'] + partes['reservas'] + partes['investimentos'] - faturas
    return partes


# --- Dinheiro guardado (REL-20) ---

def _tipo_da_conta_parceira():
    """O tipo da conta da outra perna da transferência, do mesmo usuário."""
    return Subquery(
        Transaction.objects.filter(transfer_id=OuterRef('transfer_id'), user_id=OuterRef('user_id'))
        .exclude(pk=OuterRef('pk')).values('account__type')[:1]
    )


def transferencias_de_fora(usuario, tipos, inicio, fim):
    """
    As pernas efetivadas no período, nas contas de `tipos`, das
    transferências com contas de outros tipos: `TRANSFER_IN` é o que entrou
    nelas e `TRANSFER_OUT`, o que saiu. Movimento entre duas contas de
    `tipos` fica de fora.
    """
    return Transaction.objects.filter(
        user=usuario, status='COMPLETED', account__type__in=tipos,
        date__gte=inicio, date__lte=fim, transfer_id__isnull=False,
    ).annotate(tipo_da_parceira=_tipo_da_conta_parceira()).filter(
        Q(tipo_da_parceira__isnull=True) | ~Q(tipo_da_parceira__in=tipos),
    )


def dinheiro_guardado(usuario, inicio, fim):
    """
    O que entrou nos cofrinhos e nas contas de investimento vindo das outras
    contas, menos o que saiu deles para as outras contas, pelas transferências
    efetivadas no período (REL-20). Movimento entre dois cofrinhos ou contas de
    investimento não conta, e o aporte do saldo livre, que não tem
    transferência, também não.
    """
    transferencias = transferencias_de_fora(usuario, GUARDADO, inicio, fim)
    return total(transferencias.filter(type='TRANSFER_IN')) - total(transferencias.filter(type='TRANSFER_OUT'))


# --- Faturas do mês (REL-18) ---

def faturas_do_mes(usuario):
    """
    O valor em aberto das faturas não pagas que vencem no mês atual de
    Brasília: as compras no cartão pendentes ligadas a elas (REL-18).
    """
    inicio, fim = limites_do_mes(*mes_atual())
    return total(Transaction.objects.filter(
        user=usuario, type='CREDIT_CARD', status='PENDING',
        invoice__due_date__gte=inicio, invoice__due_date__lte=fim,
    ).exclude(invoice__status='PAID'))

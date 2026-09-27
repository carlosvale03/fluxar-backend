"""
Ligações cruzadas gravadas à força, como antes da correção, para os testes da
verificação e da correção dos dados (ISOL-16 a ISOL-18).
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from accounts.models import CreditCard
from budgets.models import Budget
from goals.models import Goal, GoalDeposit
from reports.models import FocusedMonitorItem
from transactions.models import Category, RecurringTransaction, Transaction

DIA = date(2026, 9, 5)


def _transacao(usuario, tipo='EXPENSE', valor='10.00', status='COMPLETED', **relacoes):
    return Transaction.objects.create(
        user=usuario, type=tipo, status=status, description='Lançamento',
        amount=Decimal(valor), date=DIA, **relacoes,
    )


def gravar_ligacoes_cruzadas(a, b, categoria_modelo):
    """
    Grava pelo ORM uma ligação cruzada de cada linha da tabela de correção do
    design, sempre de um registro de A para um objeto de B ou para a
    categoria-modelo. Devolve os registros criados e `esperadas`, a lista de
    ligações como tuplas (tipo, ID do registro, relação, ID do objeto alheio).
    """
    r = SimpleNamespace()
    r.t_conta = _transacao(a.usuario, 'INCOME', '500.00', account=b.conta)
    r.t_cartao = _transacao(a.usuario, 'CREDIT_CARD', '80.00', 'PENDING', credit_card=b.cartao)
    r.t_fatura = _transacao(a.usuario, 'CREDIT_CARD', '70.00', 'PENDING', credit_card=a.cartao, invoice=b.fatura)
    r.t_categoria = _transacao(a.usuario, valor='30.00', account=a.conta, category=b.categoria)
    r.t_modelo = _transacao(a.usuario, valor='20.00', account=a.conta, category=categoria_modelo)
    r.t_tag = _transacao(a.usuario, valor='10.00', account=a.conta)
    r.t_tag.tags.set([a.tag, b.tag])

    r.origem_b = _transacao(b.usuario, 'CREDIT_CARD', '60.00', 'PENDING', credit_card=b.cartao)
    r.t_parcela = _transacao(a.usuario, 'CREDIT_CARD', '30.00', 'PENDING', credit_card=a.cartao, parent_transaction=r.origem_b)
    r.serie_b = RecurringTransaction.objects.create(
        user=b.usuario, description='Série', amount=Decimal('15.00'), type='EXPENSE',
        account=b.conta, frequency='MONTHLY', start_date=DIA,
    )
    r.t_recorrente = _transacao(a.usuario, valor='15.00', status='PENDING', account=a.conta, recurring_source=r.serie_b)

    r.serie_a = RecurringTransaction.objects.create(
        user=a.usuario, description='Série', amount=Decimal('25.00'), type='EXPENSE',
        account=b.conta, credit_card=b.cartao, category=b.categoria,
        frequency='MONTHLY', start_date=DIA,
    )
    r.categoria_a = Category.objects.create(user=a.usuario, name='Pendurada A', type='EXPENSE', parent=b.categoria)
    CreditCard.objects.filter(pk=a.cartao.pk).update(account=b.conta)
    Goal.objects.filter(pk=a.meta.pk).update(account=b.cofrinho)
    r.orcamento = Budget.objects.create(
        user=a.usuario, category=b.categoria, month=9, year=2026, amount_limit=Decimal('100.00'),
    )
    r.monitor_categoria = FocusedMonitorItem.objects.create(user=a.usuario, category=b.categoria)
    r.monitor_tag = FocusedMonitorItem.objects.create(user=a.usuario, tag=b.tag)
    r.aporte = GoalDeposit.objects.create(
        goal=a.meta, account=b.cofrinho, amount=Decimal('200.00'), type='DEPOSIT', date=DIA,
    )

    r.esperadas = [
        ('Transaction', r.t_conta.pk, 'account', b.conta.pk),
        ('Transaction', r.t_cartao.pk, 'credit_card', b.cartao.pk),
        ('Transaction', r.t_fatura.pk, 'invoice', b.fatura.pk),
        ('Transaction', r.t_categoria.pk, 'category', b.categoria.pk),
        ('Transaction', r.t_modelo.pk, 'category', categoria_modelo.pk),
        ('Transaction', r.t_tag.pk, 'tags', b.tag.pk),
        ('Transaction', r.t_parcela.pk, 'parent_transaction', r.origem_b.pk),
        ('Transaction', r.t_recorrente.pk, 'recurring_source', r.serie_b.pk),
        ('RecurringTransaction', r.serie_a.pk, 'account', b.conta.pk),
        ('RecurringTransaction', r.serie_a.pk, 'credit_card', b.cartao.pk),
        ('RecurringTransaction', r.serie_a.pk, 'category', b.categoria.pk),
        ('Category', r.categoria_a.pk, 'parent', b.categoria.pk),
        ('CreditCard', a.cartao.pk, 'account', b.conta.pk),
        ('Goal', a.meta.pk, 'account', b.cofrinho.pk),
        ('Budget', r.orcamento.pk, 'category', b.categoria.pk),
        ('FocusedMonitorItem', r.monitor_categoria.pk, 'category', b.categoria.pk),
        ('FocusedMonitorItem', r.monitor_tag.pk, 'tag', b.tag.pk),
        ('GoalDeposit', r.aporte.pk, 'account', b.cofrinho.pk),
    ]
    return r

"""
Saldo das contas (SALDO-01, AD-038).

`Account.balance` é sempre o resultado deste módulo: saldo inicial + entradas
efetivadas - saídas efetivadas, só com as transações do dono da conta.
Nenhum código grava o saldo diretamente; quem muda transações por
`QuerySet.update()` chama `recalcular()` para as contas afetadas.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum

ENTRADAS = ('INCOME', 'TRANSFER_IN')
SAIDAS = ('EXPENSE', 'TRANSFER_OUT', 'CREDIT_CARD', 'INVOICE_PAYMENT')


def calcular(conta):
    """O saldo da conta pela regra SALDO-01."""
    from transactions.models import Transaction

    somas = Transaction.objects.filter(
        account_id=conta.pk, user_id=conta.user_id, status='COMPLETED',
    ).aggregate(
        entradas=Sum('amount', filter=Q(type__in=ENTRADAS)),
        saidas=Sum('amount', filter=Q(type__in=SAIDAS)),
    )
    entradas = somas['entradas'] or Decimal('0.00')
    saidas = somas['saidas'] or Decimal('0.00')
    return conta.initial_balance + entradas - saidas


def recalcular(*conta_ids):
    """
    Grava em cada conta o saldo de `calcular`. Ignora `None`. Trava as contas
    com `select_for_update` em ordem de id, para que operações simultâneas
    esperem umas às outras sem deadlock (SALDO-44, SALDO-45).
    """
    from .models import Account

    ids = {conta_id for conta_id in conta_ids if conta_id is not None}
    if not ids:
        return
    with transaction.atomic():
        contas = Account.objects.select_for_update().filter(pk__in=ids).order_by('pk')
        for conta in contas:
            saldo = calcular(conta)
            if conta.balance != saldo:
                Account.objects.filter(pk=conta.pk).update(balance=saldo)

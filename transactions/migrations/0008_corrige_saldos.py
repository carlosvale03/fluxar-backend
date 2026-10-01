"""
Corrige os dados gravados antes da feature `saldo` (SALDO-37, SALDO-38).

1. As ocorrências de série efetivadas com data depois de hoje (no fuso de
   Brasília, AD-008) voltam a pendentes, menos a primeira de cada série, a
   mais antiga por data, criação e id. Desfaz o efeito de FIN-01.
2. O saldo de todas as contas, ativas e excluídas, é recalculado pela regra
   SALDO-01 com os modelos históricos.

Roda uma vez, no `migrate` do deploy; em banco vazio não encontra nada. A
fórmula repete a de `accounts/saldo.py` porque migrações não importam o
código da aplicação; o comando `check_saldos` confere as duas.
"""
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import migrations
from django.db.models import Q, Sum
from django.utils import timezone

ENTRADAS = ('INCOME', 'TRANSFER_IN')
SAIDAS = ('EXPENSE', 'TRANSFER_OUT', 'CREDIT_CARD', 'INVOICE_PAYMENT')


def _hoje():
    return timezone.localdate(timezone=ZoneInfo('America/Sao_Paulo'))


def _voltar_futuras_a_pendentes(apps):
    RecurringTransaction = apps.get_model('transactions', 'RecurringTransaction')
    Transaction = apps.get_model('transactions', 'Transaction')
    hoje = _hoje()
    for serie_id in RecurringTransaction.objects.values_list('pk', flat=True):
        ocorrencias = Transaction.objects.filter(recurring_source_id=serie_id)
        primeira = ocorrencias.order_by('date', 'created_at', 'pk').values_list('pk', flat=True).first()
        ocorrencias.filter(status='COMPLETED', date__gt=hoje).exclude(pk=primeira).update(status='PENDING')


def _recalcular_todas_as_contas(apps):
    Account = apps.get_model('accounts', 'Account')
    Transaction = apps.get_model('transactions', 'Transaction')
    for conta in Account.objects.all():
        somas = Transaction.objects.filter(
            account_id=conta.pk, user_id=conta.user_id, status='COMPLETED',
        ).aggregate(
            entradas=Sum('amount', filter=Q(type__in=ENTRADAS)),
            saidas=Sum('amount', filter=Q(type__in=SAIDAS)),
        )
        saldo = (
            conta.initial_balance
            + (somas['entradas'] or Decimal('0.00'))
            - (somas['saidas'] or Decimal('0.00'))
        )
        if conta.balance != saldo:
            Account.objects.filter(pk=conta.pk).update(balance=saldo)


def corrigir(apps, schema_editor):
    _voltar_futuras_a_pendentes(apps)
    _recalcular_todas_as_contas(apps)


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0007_corrige_isolamento'),
        ('accounts', '0004_account_balance'),
    ]

    operations = [
        migrations.RunPython(corrigir, migrations.RunPython.noop),
    ]

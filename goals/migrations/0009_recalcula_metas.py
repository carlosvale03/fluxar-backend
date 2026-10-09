"""
Recalcula o valor de todas as metas pela regra META-01 (META-10, META-11).

O valor passa a ser aportes menos resgates registrados para a meta, contando
os registros sem transação e os que têm todas as transações ligadas
efetivadas. Os registros antigos só têm o `transaction_id`, resolvido pelas
transações com esse `transfer_id` ou esse `id`; os do rateio automático
continuam no histórico e entram na conta.

Uma meta que ficaria negativa vai a zero com um registro de correção
("Correção do valor da meta", hoje em Brasília, AD-008), e o valor de antes
fica em `valor_antes_da_correcao` para o aviso único da interface.

Roda uma vez, no `migrate` do deploy; em banco vazio não encontra nada. A
regra repete a de `goals/valores.py` porque migrações não importam o código
da aplicação.
"""
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import migrations
from django.db.models import Exists, OuterRef, Q, Sum
from django.utils import timezone

DESCRICAO_DA_CORRECAO = 'Correção do valor da meta'


def _hoje():
    return timezone.localdate(timezone=ZoneInfo('America/Sao_Paulo'))


def _registros_que_contam(GoalDeposit, Transaction, meta):
    nao_efetivadas = Transaction.objects.exclude(status='COMPLETED')
    perna_nao_efetivada = (
        Exists(nao_efetivadas.filter(pk=OuterRef('transacao_saida_id')))
        | Exists(nao_efetivadas.filter(pk=OuterRef('transacao_entrada_id')))
    )
    antigo_nao_efetivado = Q(
        transacao_saida__isnull=True, transacao_entrada__isnull=True, transaction_id__isnull=False,
    ) & Exists(nao_efetivadas.filter(
        Q(transfer_id=OuterRef('transaction_id')) | Q(pk=OuterRef('transaction_id')),
    ))
    return GoalDeposit.objects.filter(
        goal_id=meta.pk, account__user_id=meta.user_id,
    ).exclude(perna_nao_efetivada).exclude(antigo_nao_efetivado)


def _valor(GoalDeposit, Transaction, meta):
    somas = _registros_que_contam(GoalDeposit, Transaction, meta).aggregate(
        aportes=Sum('amount', filter=Q(type='DEPOSIT')),
        resgates=Sum('amount', filter=Q(type='WITHDRAWAL')),
    )
    return (somas['aportes'] or Decimal('0.00')) - (somas['resgates'] or Decimal('0.00'))


def _conta_da_correcao(GoalDeposit, meta):
    """O cofrinho da meta; sem cofrinho, a conta do registro mais recente dela."""
    if meta.account_id is not None and meta.account.user_id == meta.user_id:
        return meta.account_id
    return (
        GoalDeposit.objects.filter(goal_id=meta.pk, account__user_id=meta.user_id)
        .order_by('-date', '-created_at', '-pk').values_list('account_id', flat=True).first()
    )


def recalcular(apps, schema_editor):
    Goal = apps.get_model('goals', 'Goal')
    GoalDeposit = apps.get_model('goals', 'GoalDeposit')
    Transaction = apps.get_model('transactions', 'Transaction')
    hoje = _hoje()
    for meta in Goal.objects.select_related('account').order_by('pk'):
        valor = _valor(GoalDeposit, Transaction, meta)
        if valor < 0:
            GoalDeposit.objects.create(
                goal_id=meta.pk, account_id=_conta_da_correcao(GoalDeposit, meta),
                amount=-valor, type='DEPOSIT', eh_correcao=True,
                description=DESCRICAO_DA_CORRECAO, date=hoje,
            )
            Goal.objects.filter(pk=meta.pk).update(
                current_amount=Decimal('0.00'), valor_antes_da_correcao=valor,
            )
        elif meta.current_amount != valor:
            Goal.objects.filter(pk=meta.pk).update(current_amount=valor)


class Migration(migrations.Migration):

    dependencies = [
        ('goals', '0008_valor_derivado_das_metas'),
        ('transactions', '0010_importacao'),
    ]

    operations = [
        migrations.RunPython(recalcular, migrations.RunPython.noop),
    ]

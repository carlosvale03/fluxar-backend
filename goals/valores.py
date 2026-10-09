"""
Valor das metas e saldo livre dos cofrinhos (META-01, META-02, AD-045).

`Goal.current_amount` é sempre o resultado deste módulo: aportes menos
resgates registrados para a meta. Um registro conta quando não tem transação
ligada (saldo livre, correção, registros antigos sem transação) ou quando
todas as transações ligadas a ele estão efetivadas (AD-002). Nenhum código
grava o valor diretamente; quem muda registros chama `recalcular()`.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Exists, OuterRef, Q, Sum


def _registros_que_contam(meta):
    """Os registros da meta que entram no valor dela (META-01)."""
    from transactions.models import Transaction
    from .models import GoalDeposit

    nao_efetivadas = Transaction.objects.exclude(status='COMPLETED')
    perna_nao_efetivada = (
        Exists(nao_efetivadas.filter(pk=OuterRef('transacao_saida_id')))
        | Exists(nao_efetivadas.filter(pk=OuterRef('transacao_entrada_id')))
    )
    # Registro antigo, só com `transaction_id`: as transações com esse
    # `transfer_id` ou esse `id` (META-10)
    antigo_nao_efetivado = Q(
        transacao_saida__isnull=True, transacao_entrada__isnull=True, transaction_id__isnull=False,
    ) & Exists(nao_efetivadas.filter(
        Q(transfer_id=OuterRef('transaction_id')) | Q(pk=OuterRef('transaction_id')),
    ))
    # Só registros em contas do dono da meta (ISOL-15)
    return GoalDeposit.objects.filter(
        goal_id=meta.pk, account__user_id=meta.user_id,
    ).exclude(perna_nao_efetivada).exclude(antigo_nao_efetivado)


def calcular(meta):
    """O valor da meta pela regra META-01."""
    somas = _registros_que_contam(meta).aggregate(
        aportes=Sum('amount', filter=Q(type='DEPOSIT')),
        resgates=Sum('amount', filter=Q(type='WITHDRAWAL')),
    )
    return (somas['aportes'] or Decimal('0.00')) - (somas['resgates'] or Decimal('0.00'))


def recalcular(*meta_ids):
    """
    Grava em cada meta o valor de `calcular`. Ignora `None`. Trava as metas
    com `select_for_update` em ordem de id, para que operações simultâneas
    esperem umas às outras (META-22). Devolve as metas que ficaram com valor
    negativo, para quem chamou decidir a recusa (META-09).
    """
    from .models import Goal

    ids = {meta_id for meta_id in meta_ids if meta_id is not None}
    if not ids:
        return []
    negativas = []
    with transaction.atomic():
        for meta in Goal.objects.select_for_update().filter(pk__in=ids).order_by('pk'):
            valor = calcular(meta)
            if meta.current_amount != valor:
                Goal.objects.filter(pk=meta.pk).update(current_amount=valor)
                meta.current_amount = valor
            if valor < 0:
                negativas.append(meta)
    return negativas


def saldo_livre(cofrinho):
    """
    Saldo do cofrinho (AD-038) menos a soma dos valores de todas as metas
    dele, inclusive as arquivadas (META-02). Só as metas do dono (ISOL-14).
    """
    from .models import Goal

    soma = Goal.objects.filter(
        account_id=cofrinho.pk, user_id=cofrinho.user_id,
    ).aggregate(total=Sum('current_amount'))['total'] or Decimal('0.00')
    return cofrinho.balance - soma

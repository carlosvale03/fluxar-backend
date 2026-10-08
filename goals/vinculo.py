"""
Vínculo dos registros das metas com as transações (META-03, META-06 a META-09).

Os signals de `Transaction` chamam este módulo. Só os registros ligados a uma
transação mudam junto com ela; uma transação comum num cofrinho muda só o
saldo livre (META-03). Toda mudança recalcula as metas afetadas e, se alguma
ficaria negativa, levanta `ValidationError` com a mensagem da META-09: o
`ATOMIC_REQUESTS` (ou o `atomic` de quem chamou) desfaz tudo.
"""
from django.db import transaction
from django.db.models import Q, QuerySet
from rest_framework.exceptions import ValidationError

META_FICARIA_NEGATIVA = 'A meta {nome} ficaria negativa. Desfaça o resgate antes.'


def _ligados(transacao):
    """
    Os registros ligados à transação: pelas pernas e, nos registros antigos
    sem as pernas, pelo `transaction_id` igual ao `transfer_id` ou ao `id`.
    """
    from .models import GoalDeposit

    referencias = [transacao.pk] + ([transacao.transfer_id] if transacao.transfer_id else [])
    return GoalDeposit.objects.filter(
        Q(transacao_saida_id=transacao.pk)
        | Q(transacao_entrada_id=transacao.pk)
        | Q(transacao_saida__isnull=True, transacao_entrada__isnull=True, transaction_id__in=referencias)
    ).select_related('goal')


def _travar_contas(transacao, registros):
    """
    Trava as contas das pernas ligadas aos registros antes das metas, na
    ordem de `accounts/saldo.travar` (AD-045).
    """
    from accounts.saldo import travar
    from transactions.models import Transaction

    pernas = {transacao.pk}
    for registro in registros:
        pernas |= {registro.transacao_saida_id, registro.transacao_entrada_id}
    filtro = Q(pk__in=pernas - {None})
    for referencia in {transacao.transfer_id} | {registro.transaction_id for registro in registros}:
        if referencia is not None:
            filtro |= Q(transfer_id=referencia, user_id=transacao.user_id)
    contas = set(Transaction.objects.filter(filtro).values_list('account_id', flat=True))
    travar(transacao.account_id, *contas)


def _recalcular_ou_recusar(meta_ids, recusar=True):
    from .valores import recalcular

    negativas = recalcular(*meta_ids)
    if negativas and recusar:
        raise ValidationError({'detail': META_FICARIA_NEGATIVA.format(nome=negativas[0].name)})


def _excluida_pela_requisicao(origem):
    """
    A exclusão começou numa transação ou num queryset de transações. A
    exclusão em cascata (usuário, conta) não passa por aqui.
    """
    from transactions.models import Transaction

    if isinstance(origem, QuerySet):
        return origem.model is Transaction
    return isinstance(origem, Transaction)


def ao_excluir(transacao, origem):
    """
    Antes de excluir a transação, remove os registros ligados a ela e
    recalcula as metas (META-06). A exclusão de uma transferência apaga as
    duas pernas (`sync_transfer_delete`): o registro sai na primeira, e a
    segunda não encontra mais nada. Só a exclusão de uma transação avulsa é
    recusada quando deixaria uma meta negativa (META-09); a exclusão em lote
    (limpeza dos dados pelo administrador) só recalcula.
    """
    from transactions.models import Transaction

    if not _excluida_pela_requisicao(origem):
        return
    registros = list(_ligados(transacao))
    if not registros:
        return
    with transaction.atomic():
        _travar_contas(transacao, registros)
        meta_ids = {registro.goal_id for registro in registros}
        type(registros[0]).objects.filter(pk__in=[r.pk for r in registros]).delete()
        _recalcular_ou_recusar(meta_ids, recusar=isinstance(origem, Transaction))


def _perna_no_cofrinho(registro, transacao):
    """
    Se a perna do cofrinho continua no cofrinho da meta: a entrada do aporte
    e a saída do resgate (META-08).
    """
    perna_id = registro.transacao_entrada_id if registro.type == 'DEPOSIT' else registro.transacao_saida_id
    if perna_id is None:
        return True
    perna = transacao if perna_id == transacao.pk else type(transacao).objects.filter(pk=perna_id).first()
    return perna is not None and perna.account_id == registro.goal.account_id


def ao_salvar(transacao):
    """
    Depois de alterar uma transação ligada a registros de meta (META-07,
    META-08): o registro sai se a perna do cofrinho deixou o cofrinho da
    meta; senão, recebe o valor e a data da transferência e a conta da outra
    perna. Os registros antigos, sem as pernas, só são recalculados, porque o
    status da transação muda o valor da meta (AD-002). Recusa se alguma meta
    ficaria negativa (META-09).
    """
    registros = list(_ligados(transacao))
    if not registros:
        return
    with transaction.atomic():
        _travar_contas(transacao, registros)
        for registro in registros:
            if registro.transacao_saida_id is None and registro.transacao_entrada_id is None:
                continue
            if not _perna_no_cofrinho(registro, transacao):
                registro.delete()
                continue
            registro.amount = transacao.amount
            registro.date = transacao.date
            # A conta do registro é a outra perna: a origem do aporte ou o destino do resgate
            outra_id = registro.transacao_saida_id if registro.type == 'DEPOSIT' else registro.transacao_entrada_id
            if outra_id == transacao.pk:
                registro.account_id = transacao.account_id
            registro.save(update_fields=['amount', 'date', 'account'])
        _recalcular_ou_recusar({registro.goal_id for registro in registros})

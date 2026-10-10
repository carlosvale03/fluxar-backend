"""
Saídas desde o salário (SALARIO-64 a SALARIO-69, AD-057).

- `elegiveis`: as saídas efetivadas da conta do recebimento (despesas,
  transferências, aportes em metas, que são transferências, e pagamentos de
  fatura) com data entre a do recebimento e hoje, no calendário de Brasília,
  menos as geradas por divisões do salário, os ajustes de saldo e as já
  descontadas numa divisão ativa (SALARIO-64).
- `sugestoes`: a parte sugerida para cada saída (SALARIO-65). Despesa: a
  primeira parte cuja referência é a classe efetiva da categoria (as classes
  padrão Essencial e Dispensável, AD-052). Transferência: a primeira parte
  com destino na meta do aporte ligado a ela ou na conta da perna de
  entrada. Nos demais casos, nenhuma.
- `escolhidas`: confere o `outflows` da requisição, `{id da saída: id da
  parte | null}`, e devolve as saídas descontadas com a parte de cada uma;
  uma saída fora da lista ou uma parte fora do plano recebe 400 no campo
  `outflows` (SALARIO-69).
"""
from decimal import Decimal

from django.db.models import Exists, OuterRef, Q
from rest_framework.exceptions import ValidationError

from core.datas import hoje
from core.valores import dinheiro
from goals.models import GoalDeposit
from transactions.classes import mapa_de_classes
from transactions.models import Transaction

from .models import CONTA, META, SaidaDescontada
from .referencias import referencia_da_classe

TIPOS_DE_SAIDA = ('EXPENSE', 'TRANSFER_OUT', 'INVOICE_PAYMENT')
SAIDA_NAO_ENCONTRADA = 'Saída não encontrada.'
PARTE_NAO_ENCONTRADA = 'Parte não encontrada.'
ZERO = Decimal('0.00')


def elegiveis(usuario, recebimento):
    """As saídas que podem ser descontadas na divisão do recebimento (SALARIO-64), da mais antiga para a mais recente."""
    descontada = SaidaDescontada.objects.filter(transacao_ref=OuterRef('pk'), ativa=True)
    return (
        Transaction.objects.filter(
            user=usuario, account_id=recebimento.account_id, status='COMPLETED', type__in=TIPOS_DE_SAIDA,
            date__gte=recebimento.date, date__lte=hoje(), divisao_do_salario__isnull=True,
            is_balance_adjustment=False,
        )
        .exclude(Exists(descontada))
        .select_related('category', 'credit_card')
        .order_by('date', 'created_at', 'pk')
    )


def _destinos_das_transferencias(usuario, saidas):
    """
    `({id da saída: (id da conta, nome)}, {id da saída: (id da meta, nome)})`:
    a conta da perna de entrada de cada transferência e a meta do aporte
    ligado a ela, pelas pernas ou, nos registros antigos, pelo `transfer_id`.
    """
    transferencias = [s for s in saidas if s.type == 'TRANSFER_OUT' and s.transfer_id is not None]
    if not transferencias:
        return {}, {}
    por_transfer_id = {s.transfer_id: s.pk for s in transferencias}
    contas = {}
    entradas = Transaction.objects.filter(
        user=usuario, type='TRANSFER_IN', transfer_id__in=list(por_transfer_id),
    ).select_related('account')
    for entrada in entradas:
        if entrada.account_id is not None:
            contas[por_transfer_id[entrada.transfer_id]] = (entrada.account_id, entrada.account.name)
    metas = {}
    ids = [s.pk for s in transferencias]
    aportes = GoalDeposit.objects.filter(
        Q(transacao_saida_id__in=ids) | Q(transaction_id__in=list(por_transfer_id)),
        goal__user=usuario, type='DEPOSIT',
    ).select_related('goal')
    for aporte in aportes:
        saida = aporte.transacao_saida_id if aporte.transacao_saida_id in ids else por_transfer_id.get(aporte.transaction_id)
        if saida is not None:
            metas[saida] = (aporte.goal_id, aporte.goal.name)
    return contas, metas


def _primeira(partes, condicao):
    return next((parte for parte in partes if condicao(parte)), None)


def sugestoes(usuario, saidas, partes):
    """`{id da saída: (parte sugerida | None, nome do destino | None)}` (SALARIO-65)."""
    contas, metas = _destinos_das_transferencias(usuario, saidas)
    classes = mapa_de_classes(usuario) if any(s.type == 'EXPENSE' for s in saidas) else {}
    resultado = {}
    for saida in saidas:
        sugerida = destino = None
        if saida.type == 'EXPENSE':
            referencia = referencia_da_classe(classes.get(saida.category_id))
            if referencia:
                sugerida = _primeira(partes, lambda p: p.referencia == referencia)
        elif saida.type == 'TRANSFER_OUT':
            meta = metas.get(saida.pk)
            conta = contas.get(saida.pk)
            if meta is not None:
                destino = meta[1]
                sugerida = _primeira(partes, lambda p: p.tipo_de_destino == META and p.meta_id == meta[0])
            elif conta is not None:
                destino = conta[1]
            if sugerida is None and conta is not None:
                sugerida = _primeira(partes, lambda p: p.tipo_de_destino == CONTA and p.conta_id == conta[0])
        elif saida.credit_card_id is not None:
            destino = saida.credit_card.name
        resultado[saida.pk] = (sugerida, destino)
    return resultado


def escolhidas(saidas, partes, pedido):
    """
    Confere `pedido` (`{id da saída: id da parte | None}`) e devolve
    `[(saida, parte)]` das saídas descontadas, na ordem de `saidas`
    (SALARIO-66, SALARIO-69). As saídas fora do pedido ou com `None` não são
    descontadas.
    """
    pedido = {str(chave): (str(valor) if valor not in (None, '') else None) for chave, valor in (pedido or {}).items()}
    por_id = {str(saida.pk): saida for saida in saidas}
    if set(pedido) - set(por_id):
        raise ValidationError({'outflows': [SAIDA_NAO_ENCONTRADA]})
    partes_por_id = {str(parte.pk): parte for parte in partes}
    if {valor for valor in pedido.values() if valor is not None} - set(partes_por_id):
        raise ValidationError({'outflows': [PARTE_NAO_ENCONTRADA]})
    return [
        (saida, partes_por_id[pedido[str(saida.pk)]])
        for saida in saidas if pedido.get(str(saida.pk)) is not None
    ]


def gastos_por_parte(descontadas):
    """`{id da parte: soma das saídas descontadas nela}`."""
    gastos = {}
    for saida, parte in descontadas:
        gastos[str(parte.pk)] = gastos.get(str(parte.pk), ZERO) + saida.amount
    return gastos


def saida_em_json(saida, sugerida, destino, escolhida):
    """Uma saída na revisão (SALARIO-64, SALARIO-65, SALARIO-71)."""
    return {
        'id': str(saida.pk),
        'date': saida.date.isoformat(),
        'description': saida.description,
        'amount': dinheiro(saida.amount),
        'type': saida.type,
        'destination_name': destino,
        'category_name': saida.category.name if saida.category_id else None,
        'suggested_part_id': str(sugerida.pk) if sugerida is not None else None,
        'part_id': str(escolhida.pk) if escolhida is not None else None,
    }

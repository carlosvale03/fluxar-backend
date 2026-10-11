"""
Saídas desde o salário (SALARIO-64 a SALARIO-69, SALARIO-75, AD-057).

- `elegiveis`: as saídas efetivadas da conta do recebimento (despesas,
  transferências, aportes em metas, que são transferências, e pagamentos de
  fatura) com data entre a do recebimento e o fim da janela, no calendário
  de Brasília, e as compras no cartão pagas pela conta do recebimento com
  data de pagamento nesse intervalo, uma linha por parcela, menos as geradas por
  divisões do salário, os ajustes de saldo e as já descontadas numa divisão
  ativa (SALARIO-64). O pagamento de fatura não cria transação: as compras
  pagas ficam `COMPLETED`, na conta que pagou e com `payment_date`; o
  estorno as devolve a pendentes, na conta do cartão e sem data de
  pagamento, e elas saem da lista.
- `fim_da_janela`: a véspera do próximo salário na mesma conta ou hoje, o
  que vier antes (SALARIO-75). O próximo salário é a primeira receita
  efetivada da conta, numa categoria de salário e sem ser ajuste de saldo
  (as mesmas regras que põem um recebimento na lista dos salários a
  dividir), com data posterior à do recebimento. Um salário no mesmo dia
  não fecha a janela: os dois listam as mesmas saídas, e a descontada num
  deles sai da lista do outro. Um salário ainda pendente também não fecha.
- `sugestoes`: a parte sugerida para cada saída (SALARIO-65). Despesa e
  compra no cartão: a primeira parte cuja referência é a classe efetiva da
  categoria (as classes padrão Essencial e Dispensável, AD-052); o destino
  da compra é o nome do cartão. Transferência: a primeira parte
  com destino na meta do aporte ligado a ela ou na conta da perna de
  entrada. Nos demais casos, nenhuma.
- `escolhidas`: confere o `outflows` da requisição, `{id da saída: id da
  parte | null}`, e devolve as saídas descontadas com a parte de cada uma;
  uma saída fora da lista ou uma parte fora do plano recebe 400 no campo
  `outflows` (SALARIO-69).
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Case, DateField, Exists, F, OuterRef, Q, When
from rest_framework.exceptions import ValidationError

from core.datas import hoje
from core.valores import dinheiro
from goals.models import GoalDeposit
from transactions.classes import mapa_de_classes
from transactions.models import Transaction

from . import plano
from .models import CONTA, META, SaidaDescontada
from .referencias import referencia_da_classe

TIPOS_DE_SAIDA = ('EXPENSE', 'TRANSFER_OUT', 'INVOICE_PAYMENT')
COMPRA_NO_CARTAO = 'CREDIT_CARD'
TIPOS_COM_CLASSE = ('EXPENSE', COMPRA_NO_CARTAO)
SAIDA_NAO_ENCONTRADA = 'Saída não encontrada.'
PARTE_NAO_ENCONTRADA = 'Parte não encontrada.'
ZERO = Decimal('0.00')


def fim_da_janela(usuario, recebimento):
    """O último dia das saídas do recebimento: hoje ou a véspera do próximo salário na mesma conta (SALARIO-75)."""
    proximo = (
        Transaction.objects.filter(
            user=usuario, type='INCOME', status='COMPLETED', account_id=recebimento.account_id,
            is_balance_adjustment=False, category_id__in=plano.categorias_de_salario(usuario),
            date__gt=recebimento.date,
        )
        .order_by('date')
        .values_list('date', flat=True)
        .first()
    )
    fim = hoje()
    if proximo is not None:
        fim = min(fim, proximo - timedelta(days=1))
    return fim


def elegiveis(usuario, recebimento):
    """As saídas que podem ser descontadas na divisão do recebimento (SALARIO-64), da mais antiga para a mais recente."""
    descontada = SaidaDescontada.objects.filter(transacao_ref=OuterRef('pk'), ativa=True)
    inicio, fim = recebimento.date, fim_da_janela(usuario, recebimento)
    return (
        Transaction.objects.filter(
            Q(type__in=TIPOS_DE_SAIDA, date__gte=inicio, date__lte=fim)
            | Q(type=COMPRA_NO_CARTAO, payment_date__gte=inicio, payment_date__lte=fim),
            user=usuario, account_id=recebimento.account_id, status='COMPLETED',
            divisao_do_salario__isnull=True, is_balance_adjustment=False,
        )
        .exclude(Exists(descontada))
        .annotate(data_da_saida=Case(
            When(type=COMPRA_NO_CARTAO, then=F('payment_date')), default=F('date'), output_field=DateField(),
        ))
        .select_related('category', 'credit_card')
        .order_by('data_da_saida', 'created_at', 'pk')
    )


def data_da_saida(saida):
    """A data da saída: a do pagamento para a compra no cartão paga, a da transação nos demais casos."""
    if saida.type == COMPRA_NO_CARTAO and saida.payment_date is not None:
        return saida.payment_date
    return saida.date


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
    classes = mapa_de_classes(usuario) if any(s.type in TIPOS_COM_CLASSE for s in saidas) else {}
    resultado = {}
    for saida in saidas:
        sugerida = destino = None
        if saida.type in TIPOS_COM_CLASSE:
            referencia = referencia_da_classe(classes.get(saida.category_id))
            if referencia:
                sugerida = _primeira(partes, lambda p: p.referencia == referencia)
            if saida.credit_card_id is not None:
                destino = saida.credit_card.name
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
        'date': data_da_saida(saida).isoformat(),
        'description': saida.description,
        'amount': dinheiro(saida.amount),
        'type': saida.type,
        'destination_name': destino,
        'category_name': saida.category.name if saida.category_id else None,
        'suggested_part_id': str(sugerida.pk) if sugerida is not None else None,
        'part_id': str(escolhida.pk) if escolhida is not None else None,
    }

"""
Regras da fatura do cartão (spec `faturas`).

Primeira camada, sem banco: as datas de fechamento e de vencimento e o mês
da fatura em que cai uma compra. A migração de correção usa as mesmas
funções, por isso esta camada não importa modelos.

`mes` e `ano` de uma fatura são sempre os do vencimento, como
`CreditCardInvoice.month` e `year`.
"""
import calendar
from datetime import date
from decimal import Decimal


def dia_no_mes(ano, mes, dia):
    """
    O `dia` do mês, ou o último dia do mês quando ele não existe (FATURA-01,
    AD-006). O ajuste não se acumula: cada mês parte do dia cadastrado
    (FATURA-02).
    """
    return date(ano, mes, min(dia, calendar.monthrange(ano, mes)[1]))


def mes_seguinte(mes, ano):
    """O mês seguinte, como `(mes, ano)`."""
    return (1, ano + 1) if mes == 12 else (mes + 1, ano)


def mes_anterior(mes, ano):
    """O mês anterior, como `(mes, ano)`."""
    return (12, ano - 1) if mes == 1 else (mes - 1, ano)


def datas_da_fatura(dia_fechamento, dia_vencimento, mes, ano):
    """
    `(fechamento, vencimento)` da fatura que vence em `mes`/`ano`. O
    fechamento fica no mesmo mês do vencimento quando o dia de vencimento é
    maior que o de fechamento (FATURA-03) e no mês anterior quando é menor
    ou igual (FATURA-04).
    """
    vencimento = dia_no_mes(ano, mes, dia_vencimento)
    if dia_vencimento > dia_fechamento:
        mes_fechamento, ano_fechamento = mes, ano
    else:
        mes_fechamento, ano_fechamento = mes_anterior(mes, ano)
    fechamento = dia_no_mes(ano_fechamento, mes_fechamento, dia_fechamento)
    return fechamento, vencimento


def mes_da_fatura(dia_fechamento, dia_vencimento, data_compra):
    """
    `(mes, ano)` do vencimento da fatura em que cai uma compra. Antes do
    fechamento do mês, já ajustado por AD-006, ela fica na fatura que fecha
    nesse mês (FATURA-10); no dia do fechamento ou depois, na que fecha no
    mês seguinte (FATURA-11).
    """
    mes, ano = data_compra.month, data_compra.year
    if data_compra >= dia_no_mes(ano, mes, dia_fechamento):
        mes, ano = mes_seguinte(mes, ano)
    if dia_vencimento <= dia_fechamento:
        mes, ano = mes_seguinte(mes, ano)
    return mes, ano


# --- Faturas e compras (com banco) ---
# Os modelos são importados dentro das funções, para que a camada de datas
# continue importável pela migração sem carregar os apps.


def obter_fatura(cartao, mes, ano):
    """
    A fatura do cartão que vence em `mes`/`ano`, criada com as datas de
    `datas_da_fatura` e os dias atuais do cartão quando falta (FATURA-25).
    Fatura existente mantém as datas gravadas, mesmo que os dias do cartão
    tenham mudado (FATURA-07).
    """
    from .models import CreditCardInvoice

    fechamento, vencimento = datas_da_fatura(cartao.closing_day, cartao.due_day, mes, ano)
    fatura, _ = CreditCardInvoice.objects.get_or_create(
        card=cartao, month=mes, year=ano,
        defaults={'closing_date': fechamento, 'due_date': vencimento, 'status': 'OPEN'},
    )
    return fatura


def fatura_da_compra(cartao, data_compra):
    """
    `(mes, ano)` da fatura em que cai uma compra, sem criar fatura. Se a
    fatura desse mês já existe e fecha na data da compra ou antes (os dias
    do cartão mudaram depois que ela foi criada), a compra vai para a
    seguinte (FATURA-07, FATURA-10, FATURA-11).
    """
    from .models import CreditCardInvoice

    mes, ano = mes_da_fatura(cartao.closing_day, cartao.due_day, data_compra)
    while CreditCardInvoice.objects.filter(
        card=cartao, month=mes, year=ano, closing_date__lte=data_compra,
    ).exists():
        mes, ano = mes_seguinte(mes, ano)
    return mes, ano


def primeira_nao_paga(cartao, mes, ano):
    """
    A partir de `mes`/`ano`, a primeira fatura do cartão que não está paga,
    criada se faltar (FATURA-15, FATURA-25).
    """
    fatura = obter_fatura(cartao, mes, ano)
    while fatura.status == 'PAID':
        fatura = obter_fatura(cartao, *mes_seguinte(fatura.month, fatura.year))
    return fatura


def alocar_parcelas(cartao, data_compra, quantidade):
    """
    As faturas das `quantidade` parcelas de uma compra: a primeira na fatura
    da data da compra e cada seguinte na fatura do mês seguinte ao da
    anterior, uma parcela por fatura, pulando as faturas pagas (FATURA-12,
    FATURA-15).
    """
    faturas = [primeira_nao_paga(cartao, *fatura_da_compra(cartao, data_compra))]
    while len(faturas) < quantidade:
        anterior = faturas[-1]
        faturas.append(primeira_nao_paga(cartao, *mes_seguinte(anterior.month, anterior.year)))
    return faturas


def dividir_valor(valor, quantidade):
    """
    O valor de cada parcela: arredondado a centavos, com a diferença somada à
    primeira, para que a soma seja o valor da compra (FATURA-13).
    """
    parcela = round(valor / Decimal(quantidade), 2)
    valores = [parcela] * quantidade
    valores[0] += valor - parcela * quantidade
    return valores


def colocar(compra, fatura):
    """
    Liga a compra à fatura e grava o vencimento dela como `date`, sempre
    juntos (AD-039). Salva a compra, o que também a cria se for nova.
    """
    compra.invoice = fatura
    compra.date = fatura.due_date
    compra.save()
    return compra


def status_exibido(fatura):
    """
    O status mostrado da fatura: `PAID` se paga; senão `OPEN` enquanto hoje
    (em Brasília, AD-008) é anterior ao fechamento e `CLOSED` a partir dele
    (FATURA-08, FATURA-09). O banco grava só `OPEN` e `PAID`.
    """
    from core.datas import hoje

    if fatura.status == 'PAID':
        return 'PAID'
    return 'OPEN' if hoje() < fatura.closing_date else 'CLOSED'


def proximo_vencimento(cartao):
    """
    O primeiro vencimento igual ou posterior a hoje, pelos dias atuais do
    cartão (FATURA-06): o deste mês, se ainda não passou, ou o do seguinte.
    """
    from core.datas import hoje

    dia = hoje()
    vencimento = dia_no_mes(dia.year, dia.month, cartao.due_day)
    if vencimento < dia:
        mes, ano = mes_seguinte(dia.month, dia.year)
        vencimento = dia_no_mes(ano, mes, cartao.due_day)
    return vencimento


def limite_disponivel(cartao):
    """
    O limite do cartão menos as compras pendentes dele, de todas as faturas,
    só as do dono do cartão (FATURA-42, ISOL-14). É a única fórmula, usada
    na tela do cartão e no dashboard.
    """
    from django.db.models import Sum

    from transactions.models import Transaction

    pendente = Transaction.objects.filter(
        credit_card=cartao, user_id=cartao.user_id, type='CREDIT_CARD', status='PENDING',
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    return cartao.limit - pendente


def recalcular_totais(*fatura_ids):
    """
    Grava em cada fatura o total igual à soma das compras no cartão ligadas a
    ela, só as do dono do cartão (FATURA-18, ISOL-14). Ignora `None`. Quem
    muda compras por `QuerySet.update()` chama esta função.
    """
    from django.db.models import Sum

    from transactions.models import Transaction

    from .models import CreditCardInvoice

    ids = {fatura_id for fatura_id in fatura_ids if fatura_id is not None}
    for fatura in CreditCardInvoice.objects.filter(pk__in=ids).select_related('card'):
        total = Transaction.objects.filter(
            invoice_id=fatura.pk, type='CREDIT_CARD', user_id=fatura.card.user_id,
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        if fatura.total_amount != total:
            CreditCardInvoice.objects.filter(pk=fatura.pk).update(total_amount=total)

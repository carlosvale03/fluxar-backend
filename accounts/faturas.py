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

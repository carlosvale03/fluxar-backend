"""
Cálculo da divisão de um salário (SALARIO-26 a SALARIO-28, SALARIO-30,
SALARIO-34).

`dividir` é uma função pura, usada pela simulação, pela revisão e pela
geração. As partes chegam na ordem do plano; cada uma é um objeto com `id`,
`nome`, `tipo_de_regra`, `valor`, `tipo_de_destino` e `conta_id` (uma
`ParteDoPlano` serve).

- Os valores fixos saem primeiro do recebido, e os percentuais valem sobre o
  que sobra (SALARIO-26, AD-056): `restante = recebido - fixos - ajustados`,
  nunca abaixo de zero. Cada percentual é arredondado para baixo no centavo,
  e a diferença fica livre (SALARIO-28).
- O ajuste da revisão, por id da parte, substitui o valor da parte só nessa
  divisão (SALARIO-30). A parte ajustada conta como valor fixo, mesmo quando
  é percentual no plano, e nunca é reduzida: o valor dela é o que o usuário
  digitou. Se só os ajustes já passam do recebido, levanta
  `AjustesAcimaDoRecebido`.
- Se os valores fixos não ajustados passam do que sobra do recebido depois
  dos ajustes, a última parte fixa da ordem é reduzida até zero, depois a
  anterior, e cada parte reduzida é marcada (SALARIO-27); as partes
  percentuais ficam com zero.
- Uma parte gera transação quando tem valor, não fica na conta do salário e
  não tem como destino a própria conta do recebimento (SALARIO-34). A parte
  sem destino conta como uma saída, porque ainda precisa de um.
- `total` é a soma das partes que geram transação, e `livre`, o que fica na
  conta do salário: o recebido menos o total.
"""
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal
from typing import Any, List

from core.valores import CENTAVO

from .models import CONTA, CONTA_DO_SALARIO, PERCENTUAL

ZERO = Decimal('0.00')


class AjustesAcimaDoRecebido(Exception):
    """Os valores ajustados na revisão passam do salário recebido."""


@dataclass
class ItemCalculado:
    parte: Any
    valor: Decimal
    reduzida: bool = False
    ajustada: bool = False
    gera_transacao: bool = False


@dataclass
class Divisao:
    itens: List[ItemCalculado] = field(default_factory=list)
    total: Decimal = ZERO
    livre: Decimal = ZERO


def valor_do_percentual(parte, restante):
    """O percentual da parte sobre o que sobrou dos fixos, para baixo no centavo (SALARIO-28)."""
    return (restante * parte.valor / Decimal('100')).quantize(CENTAVO, rounding=ROUND_DOWN)


def reduzir(itens, excesso):
    """Tira `excesso` dos itens, da última para a primeira, marcando os reduzidos (SALARIO-27)."""
    for item in reversed(itens):
        if excesso <= 0:
            break
        if item.valor <= 0:
            continue
        reducao = min(item.valor, excesso)
        item.valor -= reducao
        item.reduzida = True
        excesso -= reducao


def gera_transacao(parte, valor, conta_do_recebimento=None):
    """Se a parte com esse valor gera uma transferência ou um aporte (SALARIO-34)."""
    if valor <= 0 or parte.tipo_de_destino == CONTA_DO_SALARIO:
        return False
    if parte.tipo_de_destino == CONTA and conta_do_recebimento is not None:
        return str(parte.conta_id) != str(conta_do_recebimento)
    return True


def dividir(valor_recebido, partes, ajustes=None, conta_do_recebimento=None):
    """Divide `valor_recebido` entre as `partes`; veja o módulo."""
    ajustes = {str(chave): valor for chave, valor in (ajustes or {}).items()}
    itens, fixos, percentuais = [], [], []
    for parte in partes:
        chave = str(parte.id) if getattr(parte, 'id', None) is not None else None
        if chave is not None and chave in ajustes:
            itens.append(ItemCalculado(parte, Decimal(ajustes[chave]), ajustada=True))
        elif parte.tipo_de_regra == PERCENTUAL:
            item = ItemCalculado(parte, ZERO)
            itens.append(item)
            percentuais.append(item)
        else:
            item = ItemCalculado(parte, parte.valor)
            itens.append(item)
            fixos.append(item)

    ajustados = sum((item.valor for item in itens if item.ajustada), ZERO)
    if ajustados > valor_recebido:
        raise AjustesAcimaDoRecebido()

    disponivel = valor_recebido - ajustados
    reduzir(fixos, sum((item.valor for item in fixos), ZERO) - disponivel)

    restante = max(ZERO, disponivel - sum((item.valor for item in fixos), ZERO))
    for item in percentuais:
        item.valor = valor_do_percentual(item.parte, restante)
    # Os percentuais somam no máximo 100% (SALARIO-08); a redução só protege o recebido
    reduzir(percentuais, sum((item.valor for item in percentuais), ZERO) - restante)

    for item in itens:
        item.gera_transacao = gera_transacao(item.parte, item.valor, conta_do_recebimento)
    total = sum((item.valor for item in itens if item.gera_transacao), ZERO)
    return Divisao(itens=itens, total=total, livre=valor_recebido - total)

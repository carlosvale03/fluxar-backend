"""
Cálculo da divisão de um salário (SALARIO-26 a SALARIO-28, SALARIO-30,
SALARIO-34).

`dividir` é uma função pura, usada pela simulação, pela revisão e pela
geração. As partes chegam na ordem do plano; cada uma é um objeto com `id`,
`nome`, `tipo_de_regra`, `valor`, `tipo_de_destino` e `conta_id` (uma
`ParteDoPlano` serve).

- A parte percentual vale o percentual do recebido, arredondado para baixo no
  centavo; a diferença fica livre (SALARIO-28).
- O ajuste da revisão, por id da parte, substitui o valor da parte só nessa
  divisão (SALARIO-30).
- Se as partes passam do recebido, a última da ordem é reduzida até zero,
  depois a anterior, e cada parte reduzida é marcada (SALARIO-27). As partes
  ajustadas não são reduzidas: o valor delas é o que o usuário digitou. Se
  só os ajustes já passam do recebido, levanta `AjustesAcimaDoRecebido`.
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


def valor_da_parte(parte, valor_recebido):
    """O valor da parte pela regra dela, antes de qualquer redução."""
    if parte.tipo_de_regra == PERCENTUAL:
        return (valor_recebido * parte.valor / Decimal('100')).quantize(CENTAVO, rounding=ROUND_DOWN)
    return parte.valor


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
    itens = []
    for parte in partes:
        chave = str(parte.id) if getattr(parte, 'id', None) is not None else None
        if chave is not None and chave in ajustes:
            itens.append(ItemCalculado(parte, Decimal(ajustes[chave]), ajustada=True))
        else:
            itens.append(ItemCalculado(parte, valor_da_parte(parte, valor_recebido)))

    excesso = sum((item.valor for item in itens), ZERO) - valor_recebido
    for item in reversed(itens):
        if excesso <= 0:
            break
        if item.ajustada or item.valor <= 0:
            continue
        reducao = min(item.valor, excesso)
        item.valor -= reducao
        item.reduzida = True
        excesso -= reducao
    if excesso > 0:
        raise AjustesAcimaDoRecebido()

    for item in itens:
        item.gera_transacao = gera_transacao(item.parte, item.valor, conta_do_recebimento)
    total = sum((item.valor for item in itens if item.gera_transacao), ZERO)
    return Divisao(itens=itens, total=total, livre=valor_recebido - total)

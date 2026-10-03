"""
Valor das operações que movem dinheiro (SALDO-09).

O valor precisa ser maior que zero e ter no máximo duas casas decimais na
forma enviada. O limite de casas vem do `DecimalField` com `decimal_places=2`.

Na saída, todo valor em dinheiro passa por `dinheiro()` (CONTRATO-16, AD-041).
"""
from decimal import ROUND_HALF_UP, Decimal

from rest_framework import serializers

VALOR_NAO_POSITIVO = 'O valor deve ser maior que zero.'
CENTAVO = Decimal('0.01')


def dinheiro(valor):
    """
    Valor em dinheiro como texto com duas casas e ponto ("1234.56"), com
    arredondamento meio para cima; `None` vira "0.00" (CONTRATO-16). Aceita
    `Decimal`, `int` ou `float` vindo de agregação.
    """
    if valor is None:
        valor = Decimal('0')
    elif not isinstance(valor, Decimal):
        valor = Decimal(str(valor))
    valor = valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)
    # Sem "-0.00"
    return str(abs(valor) if valor == 0 else valor)


def validar_valor_positivo(valor):
    """Validador de campo: recusa zero e negativos."""
    if valor <= 0:
        raise serializers.ValidationError(VALOR_NAO_POSITIVO)


def ler_valor(valor, campo='amount'):
    """
    Para views que leem o valor direto de `request.data`: devolve o `Decimal`
    validado ou levanta `ValidationError({campo: [...]})` (HTTP 400).
    """
    field = serializers.DecimalField(
        max_digits=15, decimal_places=2, validators=[validar_valor_positivo],
    )
    try:
        return field.run_validation(valor)
    except serializers.ValidationError as erro:
        raise serializers.ValidationError({campo: erro.detail})


def ler_saldo(valor, campo='new_balance'):
    """
    Como `ler_valor`, mas aceita zero e negativos: um saldo de destino pode
    ser qualquer valor com até duas casas (ajuste de saldo, SALDO-40).
    """
    field = serializers.DecimalField(max_digits=15, decimal_places=2)
    try:
        return field.run_validation(valor)
    except serializers.ValidationError as erro:
        raise serializers.ValidationError({campo: erro.detail})

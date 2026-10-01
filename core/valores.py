"""
Valor das operações que movem dinheiro (SALDO-09).

O valor precisa ser maior que zero e ter no máximo duas casas decimais na
forma enviada. O limite de casas vem do `DecimalField` com `decimal_places=2`.
"""
from rest_framework import serializers

VALOR_NAO_POSITIVO = 'O valor deve ser maior que zero.'


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

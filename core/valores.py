"""
Valor das operações que movem dinheiro (SALDO-09).

O valor precisa ser maior que zero e ter no máximo duas casas decimais na
forma enviada. O limite de casas vem do `DecimalField` com `decimal_places=2`.

Na saída, todo valor em dinheiro passa por `dinheiro()` (CONTRATO-16, AD-041).
"""
import re
from decimal import ROUND_HALF_UP, Decimal

from rest_framework import serializers

VALOR_NAO_POSITIVO = 'O valor deve ser maior que zero.'
VALOR_INVALIDO = 'Valor inválido'
CENTAVO = Decimal('0.01')

MILHAR_E_DECIMAL = re.compile(r'(\d{1,3}(?:\.\d{3})*|\d+),(\d{0,2})')
SO_DECIMAL = re.compile(r'(\d*)\.(\d{1,2})')
SO_DIGITOS = re.compile(r'\d+')


def ler_valor_em_texto(texto):
    """
    Valor em texto no formato brasileiro (AD-009, IMPORT-09, IMPORT-10), com
    a mesma regra de `lerValorDigitado` no frontend: com vírgula, a vírgula é
    decimal e os pontos são de milhar; sem vírgula, os pontos são de milhar
    quando todos os grupos depois deles têm três dígitos e a parte antes do
    primeiro ponto não é zero, e decimal nos demais casos. Aceita "R$" e
    sinal de menos. Ilegível, zero ou com mais de duas casas levanta
    `ValueError(VALOR_INVALIDO)` (IMPORT-12).
    """
    limpo = re.sub(r'\s', '', str(texto).replace('R$', ''))
    negativo = limpo.startswith('-')
    if negativo:
        limpo = limpo[1:]

    fracao = ''
    if ',' in limpo:
        partes = MILHAR_E_DECIMAL.fullmatch(limpo)
        if not partes:
            raise ValueError(VALOR_INVALIDO)
        inteiro, fracao = partes.group(1).replace('.', ''), partes.group(2)
    elif '.' in limpo:
        grupos = limpo.split('.')
        milhar = (
            SO_DIGITOS.fullmatch(grupos[0]) and int(grupos[0]) != 0
            and all(re.fullmatch(r'\d{3}', g) for g in grupos[1:])
        )
        if milhar:
            inteiro = ''.join(grupos)
        else:
            partes = SO_DECIMAL.fullmatch(limpo)
            if not partes:
                raise ValueError(VALOR_INVALIDO)
            inteiro, fracao = partes.group(1) or '0', partes.group(2)
    elif SO_DIGITOS.fullmatch(limpo):
        inteiro = limpo
    else:
        raise ValueError(VALOR_INVALIDO)

    valor = Decimal(f'{inteiro}.{fracao.ljust(2, "0")}')
    if valor == 0:
        raise ValueError(VALOR_INVALIDO)
    return -valor if negativo else valor


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

"""
Dados pessoais criptografados no banco (LGPD-15, AD-020, AD-047).

`CampoCriptografado` grava no banco o token Fernet do valor convertido para
texto e, na leitura, devolve o tipo original. As chaves vêm de
`settings.FIELD_ENCRYPTION_KEYS`: a primeira grava e todas leem, o que
permite trocar a chave sem perder os dados gravados com as anteriores.

As funções `criptografar_texto` e `descriptografar_texto` não dependem de
nenhum modelo e servem também às migrações de dados.
"""
import datetime
from decimal import Decimal

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.db import models

__all__ = [
    'InvalidToken',
    'criptografar_texto',
    'descriptografar_texto',
    'CampoCriptografado',
    'TextoCriptografado',
    'DataCriptografada',
    'DecimalCriptografado',
]


def _fernet(chaves=None):
    chaves = settings.FIELD_ENCRYPTION_KEYS if chaves is None else chaves
    return MultiFernet([Fernet(chave) for chave in chaves])


def criptografar_texto(texto, chaves=None):
    """Devolve o token Fernet do texto, gravado com a primeira chave."""
    return _fernet(chaves).encrypt(texto.encode('utf-8')).decode('ascii')


def descriptografar_texto(token, chaves=None):
    """
    Devolve o texto de um token gravado com qualquer uma das chaves. Um valor
    que não é um token válido levanta `InvalidToken`.
    """
    return _fernet(chaves).decrypt(token.encode('ascii')).decode('utf-8')


class CampoCriptografado(models.TextField):
    """
    Campo de texto que guarda o valor criptografado. `None` e o texto vazio
    ficam como estão, porque não carregam dado pessoal. As subclasses dizem
    como o valor vira texto (`para_texto`) e volta ao tipo original
    (`de_texto`).
    """

    def para_texto(self, valor):
        return str(valor)

    def de_texto(self, texto):
        return texto

    def get_prep_value(self, value):
        value = super(models.TextField, self).get_prep_value(value)
        if value is None or value == '':
            return value
        return criptografar_texto(self.para_texto(value))

    def from_db_value(self, value, expression, connection):
        if value is None or value == '':
            return value
        return self.de_texto(descriptografar_texto(value))

    def to_python(self, value):
        if value is None or value == '':
            return value
        return self.de_texto(self.para_texto(value))


class TextoCriptografado(CampoCriptografado):
    """Texto criptografado (CPF e telefone)."""


class DataCriptografada(CampoCriptografado):
    """Data criptografada, guardada como AAAA-MM-DD."""

    def para_texto(self, valor):
        if isinstance(valor, datetime.datetime):
            valor = valor.date()
        if isinstance(valor, datetime.date):
            return valor.isoformat()
        return datetime.date.fromisoformat(str(valor)).isoformat()

    def de_texto(self, texto):
        return datetime.date.fromisoformat(texto)


class DecimalCriptografado(CampoCriptografado):
    """Valor decimal criptografado, sem perder as casas decimais."""

    def para_texto(self, valor):
        return str(Decimal(str(valor)))

    def de_texto(self, texto):
        return Decimal(texto)

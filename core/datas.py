"""
Data de hoje no fuso de Brasília (AD-008).

O `TIME_ZONE` global continua UTC; as regras que dependem de "hoje" usam
`hoje()`.
"""
import re
from datetime import date
from zoneinfo import ZoneInfo

from django.utils import timezone
from rest_framework.exceptions import ValidationError

BRASILIA = ZoneInfo('America/Sao_Paulo')

DATA_INVALIDA = 'Data inválida. Use o formato AAAA-MM-DD.'
_AAAA_MM_DD = re.compile(r'\d{4}-\d{2}-\d{2}')


def hoje():
    """A data corrente em `America/Sao_Paulo`."""
    return timezone.localdate(timezone=BRASILIA)


def ler_data(texto, campo):
    """
    Data sem hora, como data de calendário e sem fuso (CONTRATO-22): aceita só
    `AAAA-MM-DD`; qualquer outro formato, inclusive data com hora, levanta
    `ValidationError({campo: [...]})` (HTTP 400).
    """
    if isinstance(texto, str) and _AAAA_MM_DD.fullmatch(texto):
        try:
            return date.fromisoformat(texto)
        except ValueError:
            pass
    raise ValidationError({campo: [DATA_INVALIDA]})

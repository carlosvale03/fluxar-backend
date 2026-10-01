"""
Data de hoje no fuso de Brasília (AD-008).

O `TIME_ZONE` global continua UTC; as regras que dependem de "hoje" usam
`hoje()`.
"""
from zoneinfo import ZoneInfo

from django.utils import timezone

BRASILIA = ZoneInfo('America/Sao_Paulo')


def hoje():
    """A data corrente em `America/Sao_Paulo`."""
    return timezone.localdate(timezone=BRASILIA)

"""
Textos da importação: datas no formato brasileiro (IMPORT-13, IMPORT-15) e
a normalização sem acentos usada em nomes, tipos e status (IMPORT-16,
IMPORT-23).
"""
import re
import unicodedata
from datetime import date

DATA_INVALIDA = 'Data inválida'

# dd/mm/aaaa, dd/mm/aa e aaaa-mm-dd
DATA_COM_BARRA = re.compile(r'(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})')
DATA_ISO = re.compile(r'(\d{4})-(\d{2})-(\d{2})')


def normalizar(texto):
    """Minúsculas, sem acentos e sem espaços nas pontas; `None` vira ""."""
    if texto is None:
        return ''
    return ''.join(
        c for c in unicodedata.normalize('NFKD', str(texto))
        if not unicodedata.combining(c)
    ).lower().strip()


def ler_data_em_texto(texto):
    """
    Data em texto: dd/mm/aaaa, dd/mm/aa (ano 2000 + aa) ou aaaa-mm-dd, com o
    dia antes do mês nos formatos com barra (IMPORT-13). Outro formato ou
    data que não existe levanta `ValueError(DATA_INVALIDA)` (IMPORT-15).
    """
    limpo = str(texto).strip()
    partes = DATA_COM_BARRA.fullmatch(limpo)
    if partes:
        dia, mes, ano = (int(p) for p in partes.groups())
        if len(partes.group(3)) == 2:
            ano += 2000
    else:
        partes = DATA_ISO.fullmatch(limpo)
        if not partes:
            raise ValueError(DATA_INVALIDA)
        ano, mes, dia = (int(p) for p in partes.groups())
    try:
        return date(ano, mes, dia)
    except ValueError:
        raise ValueError(DATA_INVALIDA) from None

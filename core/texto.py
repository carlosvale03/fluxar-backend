"""
Normalização de textos para comparar nomes sem diferença de maiúsculas,
acentos e espaços nas pontas: usada pela importação (IMPORT-16, IMPORT-23)
e pelo nome único das classes de despesa (CLASSE-07, CLASSE-25).
"""
import unicodedata


def normalizar(texto):
    """Minúsculas, sem acentos e sem espaços nas pontas; `None` vira ""."""
    if texto is None:
        return ''
    return ''.join(
        c for c in unicodedata.normalize('NFKD', str(texto))
        if not unicodedata.combining(c)
    ).lower().strip()

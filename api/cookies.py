"""
Cookie do token de renovação e conferência da origem (SESSAO-01, SESSAO-04).

O token de renovação fica num cookie httpOnly, que nenhum script da página lê,
restrito às rotas de sessão (AD-013). As rotas que usam o cookie só aceitam
pedidos vindos do frontend.
"""
from urllib.parse import urlsplit

from django.conf import settings
from rest_framework_simplejwt.settings import api_settings as jwt_settings

NOME_DO_COOKIE = 'fluxar_refresh'
CAMINHO_DO_COOKIE = '/api/auth/'
PORTAS_PADRAO = {'http': 80, 'https': 443}


def gravar_cookie_de_renovacao(response, refresh):
    response.set_cookie(
        NOME_DO_COOKIE,
        refresh,
        max_age=int(jwt_settings.REFRESH_TOKEN_LIFETIME.total_seconds()),
        path=CAMINHO_DO_COOKIE,
        secure=not settings.DEBUG,
        httponly=True,
        samesite='Lax',
    )


def apagar_cookie_de_renovacao(response):
    response.delete_cookie(NOME_DO_COOKIE, path=CAMINHO_DO_COOKIE, samesite='Lax')


def _origem(url):
    """(esquema, host, porta) de uma URL, ou None se ela não tiver os três."""
    try:
        partes = urlsplit(url)
        porta = partes.port
    except ValueError:
        return None
    esquema = partes.scheme.lower()
    if esquema not in PORTAS_PADRAO or not partes.hostname:
        return None
    return esquema, partes.hostname.lower(), porta or PORTAS_PADRAO[esquema]


def origem_permitida(request):
    """
    O pedido vem do frontend: o `Origin`, ou o `Referer` na falta dele, tem a
    origem do FRONTEND_URL ou de uma das CORS_ALLOWED_ORIGINS. Sem os dois
    cabeçalhos, a origem é recusada.
    """
    cabecalho = request.headers.get('Origin') or request.headers.get('Referer')
    if not cabecalho:
        return False
    origem = _origem(cabecalho)
    if origem is None:
        return False
    permitidas = {_origem(url) for url in [settings.FRONTEND_URL, *settings.CORS_ALLOWED_ORIGINS]}
    return origem in permitidas

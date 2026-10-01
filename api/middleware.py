from django.http import JsonResponse
from rest_framework.exceptions import AuthenticationFailed

from core.authentication import SessaoJWTAuthentication
from core.manutencao import manutencao_ligada

# Rotas que respondem a todos durante a manutenção (SESSAO-19), comparadas
# pelo caminho exato: /api/auth/me/avatar/, por exemplo, fica fechada.
ROTAS_LIBERADAS = frozenset({
    '/api/auth/login/',
    '/api/auth/refresh/',
    '/api/auth/me/',
    '/api/auth/logout/',
    '/api/health/',
})

# O admin do Django tem o próprio login, só para staff, e os arquivos
# estáticos e de mídia não passam pela API.
PREFIXOS_LIBERADOS = ('/admin/', '/static/', '/media/')

EM_MANUTENCAO = {
    "detail": "O sistema está em manutenção programada. Por favor, tente novamente mais tarde.",
    "code": "maintenance_mode",
}


def _liberada(path):
    return path in ROTAS_LIBERADAS or path.startswith(PREFIXOS_LIBERADOS)


def _corpo_do_erro(erro):
    """Mesmo `detail` e `code` que a autenticação do DRF daria ao token recusado."""
    detalhe = erro.detail
    if isinstance(detalhe, dict):
        return {'detail': str(detalhe.get('detail', '')), 'code': str(detalhe.get('code', ''))}
    return {'detail': str(detalhe), 'code': getattr(detalhe, 'code', erro.default_code)}


class MaintenanceModeMiddleware:
    """
    Com a manutenção ligada, só administradores usam a API (SESSAO-19, SESSAO-20).

    O administrador é reconhecido pelo token de acesso, com a sessão aberta e
    o papel `role == 'ADMIN'` lido do banco (AD-016). O estado da manutenção
    vem do cache de 30 segundos de `core.manutencao` (SESSAO-25).
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.autenticacao = SessaoJWTAuthentication()

    def __call__(self, request):
        if _liberada(request.path) or not manutencao_ligada():
            return self.get_response(request)

        try:
            resultado = self.autenticacao.authenticate(request)
        except AuthenticationFailed as erro:
            # SPEC_DEVIATION: token vencido, de sessão encerrada ou de conta
            # inativa recebe 401, e não 503.
            # Reason: o token de acesso dura 15 minutos; com 503, o administrador
            # iria para a página de manutenção em vez de renovar a sessão
            # (SESSAO-20). Depois de renovar, quem não é admin recebe 503.
            resposta = JsonResponse(_corpo_do_erro(erro), status=401)
            resposta['WWW-Authenticate'] = self.autenticacao.authenticate_header(request)
            return resposta

        if resultado is not None and resultado[0].role == 'ADMIN':
            return self.get_response(request)
        return JsonResponse(EM_MANUTENCAO, status=503)

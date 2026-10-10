from django.http import JsonResponse
from rest_framework.exceptions import AuthenticationFailed

from core.authentication import SessaoJWTAuthentication
from core import termos
from core.manutencao import manutencao_ligada

# Rotas que respondem a todos durante a manutenção (SESSAO-19), comparadas
# pelo caminho exato: /api/auth/me/avatar/, por exemplo, fica fechada.
ROTAS_LIBERADAS = frozenset({
    '/api/auth/login/',
    '/api/auth/refresh/',
    '/api/auth/me/',
    '/api/auth/logout/',
    '/api/health/',
    # A rotina diária tem o próprio token e precisa rodar na manutenção (AD-048)
    '/api/rotina-diaria/',
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


# Rotas que respondem sem o aceite da versão vigente dos termos (LGPD-29,
# AD-031): o usuário nunca perde o acesso aos direitos da LGPD. Comparadas
# pelo caminho exato, como na manutenção.
ROTAS_SEM_ACEITE = frozenset({
    '/api/auth/login/',
    '/api/auth/refresh/',
    '/api/auth/me/',
    '/api/auth/logout/',
    '/api/terms/',
    '/api/terms/accept/',
    '/api/users/me/export/',
    '/api/users/me/delete/',
    '/api/auth/cancel-deletion/',
    '/api/rotina-diaria/',
    '/api/health/',
})


def termos_pendentes():
    """O corpo do 403 de quem não aceitou a versão vigente (LGPD-29)."""
    return {
        "detail": "Os termos de uso e a política de privacidade mudaram. Aceite a nova versão para continuar.",
        "code": "terms_acceptance_required",
        "version": termos.VERSAO_VIGENTE,
    }


class TermosMiddleware:
    """
    Sem o aceite da versão vigente dos termos, o usuário autenticado recebe
    403 `terms_acceptance_required` fora das rotas liberadas (LGPD-28,
    LGPD-29), no mesmo padrão da manutenção.

    O usuário vem do token de acesso, com a sessão aberta; o aceite vem do
    cache `versao_dos_termos_aceita`, lido junto com o usuário. Token
    recusado ou ausente segue para a rota, que responde como sempre.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.autenticacao = SessaoJWTAuthentication()

    def __call__(self, request):
        if request.path in ROTAS_SEM_ACEITE or request.path.startswith(PREFIXOS_LIBERADOS):
            return self.get_response(request)
        if not request.META.get('HTTP_AUTHORIZATION'):
            return self.get_response(request)

        try:
            resultado = self.autenticacao.authenticate(request)
        except AuthenticationFailed:
            # A rota responde o 401 de sempre, e a tela renova a sessão
            return self.get_response(request)

        if resultado is not None and not termos.aceitou_a_vigente(resultado[0]):
            return JsonResponse(termos_pendentes(), status=403)
        return self.get_response(request)


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

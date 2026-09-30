from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed

from api.sessoes import sessao_aberta


class SessaoJWTAuthentication(JWTAuthentication):
    """
    JWT que só vale com a sessão do token aberta (SESSAO-17, SESSAO-18).

    O SimpleJWT confere a assinatura, a validade e a conta ativa; aqui se exige
    o claim `sid` de uma sessão aberta do mesmo usuário. Token sem `sid`, das
    versões antigas, também recebe 401.
    """

    def authenticate(self, request):
        resultado = super().authenticate(request)
        if resultado is None:
            return None
        user, token = resultado
        if not sessao_aberta(token.get('sid'), user.pk):
            raise AuthenticationFailed('Sessão expirada. Entre de novo.', code='session_expired')
        return resultado

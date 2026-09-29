"""
Limites de tentativas das rotas de autenticação (AUTH-31 a AUTH-35).

Os limites por IP e por e-mail valem juntos. Os contadores ficam no cache padrão (DatabaseCache), compartilhado entre os
workers. O IP vem do `get_ident` do DRF, que lê o X-Forwarded-For conforme
REST_FRAMEWORK['NUM_PROXIES'].
"""
import hashlib

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from rest_framework.throttling import SimpleRateThrottle


class IPThrottle(SimpleRateThrottle):
    """Conta as requisições por IP, num contador por `scope`."""

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class LoginIPThrottle(IPThrottle):
    scope = 'login_ip'
    rate = '5/min'


class CadastroIPThrottle(IPThrottle):
    scope = 'cadastro_ip'
    rate = '5/hour'


class PedidoIPThrottle(IPThrottle):
    """Pedidos que enviam e-mail; cada rota tem a sua subclasse e o seu contador."""
    rate = '10/hour'


class EsqueciSenhaIPThrottle(PedidoIPThrottle):
    scope = 'esqueci_senha_ip'


class ReenvioIPThrottle(PedidoIPThrottle):
    scope = 'reenvio_ip'


class LinkIPThrottle(IPThrottle):
    """Verificação de e-mail e redefinição por link, num contador só."""
    scope = 'link_ip'
    rate = '20/hour'


def _email_do_corpo(request):
    """
    O e-mail do corpo em minúsculas, ou None quando falta ou é inválido: sem
    ele, vale só o limite por IP, em vez de um contador comum a todos.
    """
    email = request.data.get('email') if hasattr(request.data, 'get') else None
    if not isinstance(email, str):
        return None
    email = email.strip().lower()
    try:
        validate_email(email)
    except ValidationError:
        return None
    return email


class EmailThrottle(SimpleRateThrottle):
    """Conta por e-mail; a chave guarda só o hash, sem o endereço."""

    def chave(self, email):
        ident = hashlib.sha256(email.encode()).hexdigest()
        return self.cache_format % {'scope': self.scope, 'ident': ident}

    def get_cache_key(self, request, view):
        email = _email_do_corpo(request)
        return self.chave(email) if email else None


class LoginFalhasEmailThrottle(EmailThrottle):
    """
    Bloqueia o login do e-mail com 10 falhas na última hora, inclusive com a
    senha certa (AUTH-32). Só a falha conta: o serializer de login chama
    `registrar_falha` com a senha errada ou a conta inexistente.
    """
    scope = 'login_falhas_email'
    rate = '10/hour'

    def _historico(self, chave):
        self.history = self.cache.get(chave, [])
        self.now = self.timer()
        while self.history and self.history[-1] <= self.now - self.duration:
            self.history.pop()

    def allow_request(self, request, view):
        chave = self.get_cache_key(request, view)
        if chave is None:
            return True
        self._historico(chave)
        return len(self.history) < self.num_requests

    def registrar_falha(self, email):
        email = email.strip().lower()
        chave = self.chave(email)
        self._historico(chave)
        self.history.insert(0, self.now)
        self.cache.set(chave, self.history, self.duration)


class PedidoEmailThrottle(EmailThrottle):
    """Pedidos que enviam e-mail, por e-mail; cada rota tem o seu contador."""
    rate = '3/hour'


class EsqueciSenhaEmailThrottle(PedidoEmailThrottle):
    scope = 'esqueci_senha_email'


class ReenvioEmailThrottle(PedidoEmailThrottle):
    scope = 'reenvio_email'

"""
Limites de tentativas das rotas de autenticação (AUTH-31 a AUTH-35).

Os contadores ficam no cache padrão (DatabaseCache), compartilhado entre os
workers. O IP vem do `get_ident` do DRF, que lê o X-Forwarded-For conforme
REST_FRAMEWORK['NUM_PROXIES'].
"""
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

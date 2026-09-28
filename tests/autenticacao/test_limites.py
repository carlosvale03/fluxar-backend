"""
Limites de tentativas (AUTH-31 a AUTH-35).

O relógio dos limites é simulado: cada teste fixa o instante, faz as
tentativas e avança o relógio para conferir a liberação depois do período.
O envio de e-mail é simulado nas views.
"""
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import SimpleRateThrottle

LOGIN = '/api/auth/login/'
CADASTRO = '/api/auth/register/'
ESQUECI = '/api/auth/forgot-password/'
REENVIAR = '/api/auth/resend-verification/'
VERIFICAR = '/api/auth/verify-email/'
REDEFINIR = '/api/auth/reset-password/'
INICIO = 1_800_000_000.0


@override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK, 'NUM_PROXIES': 1})
@mock.patch('api.views.send_password_reset_email', return_value=True)
@mock.patch('api.views.send_verification_email', return_value=True)
class LimitesPorIPTests(APITestCase):

    def setUp(self):
        cache.clear()
        relogio = mock.patch.object(SimpleRateThrottle, 'timer', return_value=INICIO)
        self.relogio = relogio.start()
        self.addCleanup(relogio.stop)

    def avancar(self, segundos):
        self.relogio.return_value = INICIO + segundos

    def de(self, ip):
        return {'HTTP_X_FORWARDED_FOR': ip}

    def login(self, n, ip='203.0.113.10'):
        return self.client.post(
            LOGIN, {'email': f'pessoa{n}@fluxar.teste', 'password': 'Senha-Qualquer-1'},
            format='json', **self.de(ip),
        )

    def cadastro(self, n, ip='203.0.113.10'):
        return self.client.post(CADASTRO, {
            'name': f'Pessoa {n}', 'email': f'pessoa{n}@fluxar.teste',
            'password': 'Cofre-Azul-2026', 'password_confirm': 'Cofre-Azul-2026',
            'terms_accepted': True,
        }, format='json', **self.de(ip))

    def pedido(self, rota, n, ip='203.0.113.10'):
        return self.client.post(rota, {'email': f'pessoa{n}@fluxar.teste'}, format='json', **self.de(ip))

    def verificacao(self, ip='203.0.113.10'):
        return self.client.get(VERIFICAR, {'token': 'nao-e-um-uuid'}, **self.de(ip))

    def redefinicao(self, ip='203.0.113.10'):
        return self.client.post(REDEFINIR, {'token': 'nao-e-um-uuid'}, format='json', **self.de(ip))

    def assertPassaram(self, respostas):
        self.assertNotIn(status.HTTP_429_TOO_MANY_REQUESTS, [r.status_code for r in respostas])

    def assertBloqueado(self, resposta):
        self.assertEqual(resposta.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('Retry-After', resposta.headers)

    # AUTH-31 -----------------------------------------------------------

    def test_sexta_tentativa_de_login_em_um_minuto_bloqueada_ate_o_fim_do_periodo(self, *_):
        self.assertPassaram([self.login(n) for n in range(5)])

        self.assertBloqueado(self.login(5))
        self.avancar(59)
        self.assertBloqueado(self.login(6))

        self.avancar(61)
        self.assertEqual(self.login(7).status_code, status.HTTP_400_BAD_REQUEST)

    # AUTH-33 -----------------------------------------------------------

    def test_sexto_cadastro_em_uma_hora_bloqueado_ate_completar_a_hora(self, *_):
        respostas = [self.cadastro(n) for n in range(5)]
        self.assertEqual([r.status_code for r in respostas], [status.HTTP_201_CREATED] * 5)

        self.assertBloqueado(self.cadastro(5))
        self.avancar(3599)
        self.assertBloqueado(self.cadastro(6))

        self.avancar(3601)
        self.assertEqual(self.cadastro(7).status_code, status.HTTP_201_CREATED)

    # AUTH-34 -----------------------------------------------------------

    def test_decimo_primeiro_esqueci_a_senha_por_ip_bloqueado_ate_completar_a_hora(self, *_):
        self.assertPassaram([self.pedido(ESQUECI, n) for n in range(10)])

        self.assertBloqueado(self.pedido(ESQUECI, 10))

        self.avancar(3601)
        self.assertEqual(self.pedido(ESQUECI, 11).status_code, status.HTTP_200_OK)

    def test_decimo_primeiro_reenvio_por_ip_bloqueado_e_contado_a_parte_do_esqueci(self, *_):
        self.assertPassaram([self.pedido(ESQUECI, n) for n in range(10)])
        self.assertPassaram([self.pedido(REENVIAR, n) for n in range(10)])

        self.assertBloqueado(self.pedido(REENVIAR, 10))

        self.avancar(3601)
        self.assertEqual(self.pedido(REENVIAR, 11).status_code, status.HTTP_200_OK)

    # AUTH-35 -----------------------------------------------------------

    def test_vigesima_primeira_tentativa_de_link_bloqueada_ate_completar_a_hora(self, *_):
        respostas = [self.verificacao() for _ in range(10)] + [self.redefinicao() for _ in range(10)]
        self.assertEqual([r.status_code for r in respostas], [status.HTTP_400_BAD_REQUEST] * 20)

        self.assertBloqueado(self.verificacao())
        self.assertBloqueado(self.redefinicao())

        self.avancar(3601)
        self.assertEqual(self.verificacao().status_code, status.HTTP_400_BAD_REQUEST)

    # IP do cliente -----------------------------------------------------

    def test_ips_diferentes_tem_contadores_separados(self, *_):
        self.assertPassaram([self.login(n, ip='203.0.113.10') for n in range(5)])
        self.assertBloqueado(self.login(5, ip='203.0.113.10'))

        self.assertEqual(self.login(6, ip='198.51.100.20').status_code, status.HTTP_400_BAD_REQUEST)

    def test_ip_forjado_no_inicio_do_x_forwarded_for_nao_abre_contador_novo(self, *_):
        # Com um proxy na frente, vale o último endereço, que o proxy acrescenta
        self.assertPassaram([
            self.login(n, ip=f'10.0.0.{n}, 203.0.113.10') for n in range(5)
        ])

        self.assertBloqueado(self.login(5, ip='10.0.0.99, 203.0.113.10'))

    @override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK, 'NUM_PROXIES': 0})
    def test_sem_proxy_o_x_forwarded_for_e_ignorado(self, *_):
        self.assertPassaram([self.login(n, ip=f'198.51.100.{n}') for n in range(5)])

        self.assertBloqueado(self.login(5, ip='198.51.100.99'))

"""
Cookie de renovação e origem (SESSAO-01 e SESSAO-04).

O token de renovação vai no cookie `fluxar_refresh`: httpOnly, SameSite=Lax,
restrito a `/api/auth/`, Secure fora do DEBUG e válido por 7 dias. As rotas de
sessão só aceitam pedidos do frontend: a origem vem do `Origin` ou, na falta
dele, do `Referer`, e é comparada com o `FRONTEND_URL` e as origens do CORS.
"""
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from api.cookies import (
    NOME_DO_COOKIE,
    apagar_cookie_de_renovacao,
    gravar_cookie_de_renovacao,
    origem_permitida,
)


class CookieDeRenovacaoTests(SimpleTestCase):

    def gravar(self):
        resposta = HttpResponse()
        gravar_cookie_de_renovacao(resposta, 'token-de-renovacao')
        return resposta.cookies[NOME_DO_COOKIE]

    # SESSAO-01 ---------------------------------------------------------

    @override_settings(DEBUG=False)
    def test_grava_o_cookie_httponly_lax_restrito_as_rotas_de_sessao_por_7_dias(self):
        cookie = self.gravar()

        self.assertEqual(NOME_DO_COOKIE, 'fluxar_refresh')
        self.assertEqual(cookie.value, 'token-de-renovacao')
        self.assertIs(cookie['httponly'], True)
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(cookie['path'], '/api/auth/')
        self.assertIs(cookie['secure'], True)
        self.assertEqual(cookie['max-age'], 7 * 24 * 60 * 60)

    @override_settings(DEBUG=True)
    def test_com_debug_ligado_o_cookie_dispensa_o_https(self):
        cookie = self.gravar()

        self.assertFalse(cookie['secure'])
        self.assertIs(cookie['httponly'], True)

    def test_apagar_vence_o_cookie_no_mesmo_caminho(self):
        resposta = HttpResponse()
        apagar_cookie_de_renovacao(resposta)

        cookie = resposta.cookies[NOME_DO_COOKIE]
        self.assertEqual(cookie.value, '')
        self.assertEqual(cookie['max-age'], 0)
        self.assertEqual(cookie['path'], '/api/auth/')


@override_settings(
    FRONTEND_URL='https://app.fluxar.teste/',
    CORS_ALLOWED_ORIGINS=['https://painel.fluxar.teste', 'http://localhost:3000'],
)
class OrigemPermitidaTests(SimpleTestCase):

    def pedido(self, **cabecalhos):
        return RequestFactory().post('/api/auth/refresh/', **cabecalhos)

    # SESSAO-04 ---------------------------------------------------------

    def test_aceita_a_origem_do_frontend(self):
        self.assertIs(origem_permitida(self.pedido(HTTP_ORIGIN='https://app.fluxar.teste')), True)

    def test_aceita_as_origens_do_cors(self):
        self.assertIs(origem_permitida(self.pedido(HTTP_ORIGIN='https://painel.fluxar.teste')), True)
        self.assertIs(origem_permitida(self.pedido(HTTP_ORIGIN='http://localhost:3000')), True)

    def test_sem_origin_aceita_o_referer_do_frontend(self):
        pedido = self.pedido(HTTP_REFERER='https://app.fluxar.teste/dashboard?aba=1')

        self.assertIs(origem_permitida(pedido), True)

    def test_recusa_outra_origem(self):
        for origem in (
            'https://malicioso.teste',
            'http://app.fluxar.teste',
            'https://app.fluxar.teste:8443',
            'https://app.fluxar.teste.malicioso.teste',
            'http://localhost:3001',
            'null',
        ):
            with self.subTest(origem=origem):
                self.assertIs(origem_permitida(self.pedido(HTTP_ORIGIN=origem)), False)

    def test_recusa_o_referer_de_outra_origem(self):
        pedido = self.pedido(HTTP_REFERER='https://malicioso.teste/https://app.fluxar.teste/')

        self.assertIs(origem_permitida(pedido), False)

    def test_origin_de_outra_origem_nao_e_salvo_pelo_referer_do_frontend(self):
        pedido = self.pedido(
            HTTP_ORIGIN='https://malicioso.teste', HTTP_REFERER='https://app.fluxar.teste/',
        )

        self.assertIs(origem_permitida(pedido), False)

    def test_recusa_o_pedido_sem_origin_e_sem_referer(self):
        self.assertIs(origem_permitida(self.pedido()), False)

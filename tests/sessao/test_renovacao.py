"""
Renovação rotativa pelo cookie (SESSAO-04, SESSAO-08 e SESSAO-09).

`POST /api/auth/refresh/` lê o token de renovação do cookie, devolve um token
de acesso novo no corpo e grava um token de renovação novo no cookie. Um token
já usado, vencido, ausente ou de sessão encerrada recebe 401 e o cookie é
apagado. Um pedido de outra origem recebe 403, sem renovar.
"""
from datetime import timedelta

from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from api.cookies import NOME_DO_COOKIE
from api.models import Sessao, User
from api.sessoes import criar_sessao, encerrar

RENOVAR = '/api/auth/refresh/'
FRONTEND = 'https://app.fluxar.teste'
SENHA = 'Cofre-Azul-2026'
SESSAO_EXPIRADA = {'detail': 'Sessão expirada. Entre de novo.', 'code': 'session_expired'}


@override_settings(FRONTEND_URL=FRONTEND, CORS_ALLOWED_ORIGINS=[])
class RenovacaoTests(APITestCase):

    def setUp(self):
        self.ana = User.objects.create_user(
            email='ana@fluxar.teste', password=SENHA, name='Ana', email_verified=True,
        )
        _, self.refresh = criar_sessao(self.ana)
        self.sessao = Sessao.objects.get(pk=RefreshToken(self.refresh)['sid'])

    def renovar(self, cookie=None, origem=FRONTEND):
        self.client.cookies.pop(NOME_DO_COOKIE, None)
        if cookie is not None:
            self.client.cookies[NOME_DO_COOKIE] = cookie
        cabecalhos = {'HTTP_ORIGIN': origem} if origem else {}
        return self.client.post(RENOVAR, **cabecalhos)

    def assertRecusadaComCookieApagado(self, resposta):
        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(resposta.data, SESSAO_EXPIRADA)
        cookie = resposta.cookies[NOME_DO_COOKIE]
        self.assertEqual(cookie.value, '')
        self.assertEqual(cookie['max-age'], 0)
        self.assertEqual(cookie['path'], '/api/auth/')

    # SESSAO-08 ---------------------------------------------------------

    def test_renova_com_acesso_novo_no_corpo_e_renovacao_nova_no_cookie(self):
        resposta = self.renovar(self.refresh)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(set(resposta.data), {'access'})
        acesso = AccessToken(resposta.data['access'])
        self.assertEqual(acesso['sid'], str(self.sessao.id))
        cookie = resposta.cookies[NOME_DO_COOKIE]
        self.assertIs(cookie['httponly'], True)
        self.assertNotEqual(cookie.value, self.refresh)
        novo = RefreshToken(cookie.value)
        self.assertEqual(novo['sid'], str(self.sessao.id))
        self.sessao.refresh_from_db()
        self.assertEqual(self.sessao.refresh_jti, novo['jti'])
        me = self.client.get('/api/auth/me/', HTTP_AUTHORIZATION=f"Bearer {resposta.data['access']}")
        self.assertEqual(me.status_code, status.HTTP_200_OK)

    # SESSAO-09 ---------------------------------------------------------

    def test_reapresentar_o_cookie_antigo_recebe_401(self):
        self.assertEqual(self.renovar(self.refresh).status_code, status.HTTP_200_OK)

        self.assertRecusadaComCookieApagado(self.renovar(self.refresh))

    def test_sem_cookie_recebe_401(self):
        self.assertRecusadaComCookieApagado(self.renovar())

    def test_cookie_vencido_recebe_401(self):
        vencido = RefreshToken(self.refresh)
        vencido.set_exp(from_time=timezone.now() - timedelta(days=8))

        self.assertRecusadaComCookieApagado(self.renovar(str(vencido)))

    def test_cookie_de_sessao_encerrada_recebe_401(self):
        encerrar(str(self.sessao.id))

        self.assertRecusadaComCookieApagado(self.renovar(self.refresh))

    # SESSAO-04 ---------------------------------------------------------

    def test_pedido_de_outra_origem_ou_sem_origem_recebe_403_sem_renovar(self):
        for origem in ('https://malicioso.teste', None):
            with self.subTest(origem=origem):
                resposta = self.renovar(self.refresh, origem=origem)

                self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)
                self.assertEqual(resposta.data['code'], 'origin_not_allowed')
                self.assertTrue(resposta.data['detail'])
                self.assertNotIn('access', resposta.data)
                self.assertNotIn(NOME_DO_COOKIE, resposta.cookies)
                self.sessao.refresh_from_db()
                self.assertEqual(self.sessao.refresh_jti, RefreshToken(self.refresh)['jti'])

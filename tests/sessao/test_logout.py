"""
Logout (SESSAO-04 e SESSAO-13).

`POST /api/auth/logout/` encerra a sessão do cookie de renovação, mesmo com o
token vencido, e apaga o cookie. Responde 204 também sem cookie. Um pedido de
outra origem recebe 403 e a sessão continua aberta.
"""
from datetime import timedelta

import jwt
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from api.cookies import NOME_DO_COOKIE
from api.models import Sessao, User
from api.sessoes import criar_sessao

LOGOUT = '/api/auth/logout/'
RENOVAR = '/api/auth/refresh/'
FRONTEND = 'https://app.fluxar.teste'
SENHA = 'Cofre-Azul-2026'


@override_settings(FRONTEND_URL=FRONTEND, CORS_ALLOWED_ORIGINS=[])
class LogoutTests(APITestCase):

    def setUp(self):
        self.ana = User.objects.create_user(
            email='ana@fluxar.teste', password=SENHA, name='Ana', email_verified=True,
        )
        _, self.refresh = criar_sessao(self.ana)
        self.sessao = Sessao.objects.get(pk=RefreshToken(self.refresh)['sid'])

    def com_cookie(self, cookie):
        self.client.cookies.pop(NOME_DO_COOKIE, None)
        if cookie is not None:
            self.client.cookies[NOME_DO_COOKIE] = cookie

    def sair(self, cookie=None, origem=FRONTEND):
        self.com_cookie(cookie)
        return self.client.post(LOGOUT, HTTP_ORIGIN=origem)

    def assertSaidaComCookieApagado(self, resposta):
        self.assertEqual(resposta.status_code, status.HTTP_204_NO_CONTENT)
        cookie = resposta.cookies[NOME_DO_COOKIE]
        self.assertEqual(cookie.value, '')
        self.assertEqual(cookie['max-age'], 0)
        self.assertEqual(cookie['path'], '/api/auth/')

    def encerrada(self, sessao):
        sessao.refresh_from_db()
        return sessao.encerrada_em is not None

    # SESSAO-13 ---------------------------------------------------------

    def test_logout_encerra_so_esta_sessao_e_o_token_de_renovacao_deixa_de_valer(self):
        _, refresh_outro_aparelho = criar_sessao(self.ana)
        outra = Sessao.objects.get(pk=RefreshToken(refresh_outro_aparelho)['sid'])

        self.assertSaidaComCookieApagado(self.sair(self.refresh))

        self.assertTrue(self.encerrada(self.sessao))
        self.assertFalse(self.encerrada(outra))
        self.com_cookie(self.refresh)
        resposta = self.client.post(RENOVAR, HTTP_ORIGIN=FRONTEND)
        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(resposta.data['code'], 'session_expired')

    def test_logout_sem_cookie_responde_204(self):
        self.assertSaidaComCookieApagado(self.sair())

        self.assertFalse(self.encerrada(self.sessao))

    def test_logout_com_token_vencido_encerra_a_sessao(self):
        vencido = RefreshToken(self.refresh)
        vencido.set_exp(from_time=timezone.now() - timedelta(days=8))

        self.assertSaidaComCookieApagado(self.sair(str(vencido)))

        self.assertTrue(self.encerrada(self.sessao))

    def test_logout_com_token_de_assinatura_falsa_nao_encerra_a_sessao(self):
        forjado = jwt.encode(
            {**RefreshToken(self.refresh).payload}, 'outra-chave-com-mais-de-32-bytes-0123456789',
            algorithm='HS256',
        )

        self.assertSaidaComCookieApagado(self.sair(forjado))

        self.assertFalse(self.encerrada(self.sessao))

    # SESSAO-04 ---------------------------------------------------------

    def test_logout_de_outra_origem_recebe_403_e_a_sessao_continua_aberta(self):
        resposta = self.sair(self.refresh, origem='https://malicioso.teste')

        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resposta.data['code'], 'origin_not_allowed')
        self.assertNotIn(NOME_DO_COOKIE, resposta.cookies)
        self.assertFalse(self.encerrada(self.sessao))

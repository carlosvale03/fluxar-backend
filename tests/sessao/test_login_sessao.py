"""
Login e verificação abrem a sessão (SESSAO-01).

O login e o link de verificação criam uma sessão: o token de acesso vai no
corpo da resposta e o de renovação só no cookie httpOnly `fluxar_refresh`.
As recusas da `autenticacao` não abrem sessão nem gravam cookie.
"""
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from api.cookies import NOME_DO_COOKIE
from api.models import EmailVerificationToken, Sessao, User

LOGIN = '/api/auth/login/'
VERIFICAR = '/api/auth/verify-email/'
SENHA = 'Cofre-Azul-2026'


class SessaoAbertaPelaRespostaMixin:

    def assertSessaoAberta(self, resposta, usuario):
        """Acesso no corpo, renovação só no cookie, os dois da mesma sessão aberta."""
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertNotIn('refresh', resposta.data)
        acesso = AccessToken(resposta.data['access'])
        cookie = resposta.cookies[NOME_DO_COOKIE]
        self.assertIs(cookie['httponly'], True)
        self.assertEqual(cookie['path'], '/api/auth/')
        renovacao = RefreshToken(cookie.value)
        sessao = Sessao.objects.get(pk=acesso['sid'])
        self.assertEqual(sessao.user, usuario)
        self.assertIsNone(sessao.encerrada_em)
        self.assertEqual(renovacao['sid'], str(sessao.id))
        self.assertEqual(sessao.refresh_jti, renovacao['jti'])
        return acesso

    def assertSemSessao(self, resposta):
        self.assertNotIn('access', resposta.data)
        self.assertNotIn('refresh', resposta.data)
        self.assertNotIn(NOME_DO_COOKIE, resposta.cookies)
        self.assertFalse(Sessao.objects.exists())


class LoginAbreASessaoTests(SessaoAbertaPelaRespostaMixin, APITestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user(
            email='ana@fluxar.teste', password=SENHA, name='Ana', email_verified=True,
        )

    def entrar(self, email='ana@fluxar.teste', senha=SENHA):
        return self.client.post(LOGIN, {'email': email, 'password': senha}, format='json')

    def test_login_entrega_o_acesso_no_corpo_e_a_renovacao_so_no_cookie(self):
        resposta = self.entrar()

        acesso = self.assertSessaoAberta(resposta, self.ana)
        self.assertEqual(acesso['name'], 'Ana')
        self.assertEqual(acesso['role'], 'USER')
        me = self.client.get('/api/auth/me/', HTTP_AUTHORIZATION=f"Bearer {resposta.data['access']}")
        self.assertEqual(me.status_code, status.HTTP_200_OK)

    def test_cada_login_abre_uma_sessao_nova(self):
        primeiro = AccessToken(self.entrar().data['access'])
        segundo = AccessToken(self.entrar().data['access'])

        self.assertNotEqual(primeiro['sid'], segundo['sid'])
        self.assertEqual(Sessao.objects.filter(user=self.ana, encerrada_em__isnull=True).count(), 2)

    def test_login_recusado_nao_abre_sessao_e_mantem_a_resposta(self):
        User.objects.create_user(email='pendente@fluxar.teste', password=SENHA, name='Pendente')
        User.objects.create_user(
            email='desativada@fluxar.teste', password=SENHA, name='Desativada',
            email_verified=True, is_active=False,
        )
        casos = [
            ('ana@fluxar.teste', 'Cofre-Roxo-2026',
             {'detail': 'E-mail ou senha incorretos.', 'code': 'invalid_credentials'}),
            ('pendente@fluxar.teste', SENHA,
             {'detail': 'Confirme seu e-mail para entrar.', 'code': 'email_not_verified'}),
            ('desativada@fluxar.teste', SENHA,
             {'detail': 'Esta conta está desativada.', 'code': 'account_disabled'}),
        ]
        for email, senha, corpo in casos:
            with self.subTest(email=email):
                resposta = self.entrar(email, senha)
                self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(resposta.data, corpo)
                self.assertSemSessao(resposta)


class VerificacaoAbreASessaoTests(SessaoAbertaPelaRespostaMixin, APITestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user(
            email='ana@fluxar.teste', password=SENHA, name='Ana',
        )
        self.link = EmailVerificationToken.objects.create(
            user=self.ana, expires_at=timezone.now() + timedelta(hours=24),
        )

    def test_verificacao_entrega_o_acesso_no_corpo_e_a_renovacao_so_no_cookie(self):
        resposta = self.client.get(VERIFICAR, {'token': str(self.link.token)})

        self.assertSessaoAberta(resposta, self.ana)
        self.assertEqual(resposta.data['message'], 'E-mail verificado com sucesso! Sua conta está ativa.')

    def test_verificacao_de_conta_desativada_nao_abre_sessao(self):
        User.objects.filter(pk=self.ana.pk).update(is_active=False)

        resposta = self.client.get(VERIFICAR, {'token': str(self.link.token)})

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resposta.data, {'detail': 'Esta conta está desativada.', 'code': 'account_disabled'})
        self.assertSemSessao(resposta)

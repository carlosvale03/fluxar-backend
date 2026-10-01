"""
Desativação, arquivamento e exclusão pelo administrador (SESSAO-17).

Depois que o administrador desativa, arquiva ou exclui uma conta pelo painel,
os tokens dela recebem 401 na próxima requisição e na renovação. A desativação
e o arquivamento encerram as sessões (AD-037); a exclusão as apaga em cascata.
A sessão do administrador continua aberta.
"""
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from api.cookies import NOME_DO_COOKIE
from api.models import Sessao, User
from api.sessoes import criar_sessao

ME = '/api/auth/me/'
RENOVAR = '/api/auth/refresh/'
FRONTEND = 'https://app.fluxar.teste'
SENHA = 'Cofre-Azul-2026'


@override_settings(FRONTEND_URL=FRONTEND, CORS_ALLOWED_ORIGINS=[])
class AdministradorDerrubaAsSessoesTests(APITestCase):

    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@fluxar.teste', password=SENHA, name='Admin', email_verified=True,
            is_staff=True, role='ADMIN',
        )
        self.access_admin, _ = criar_sessao(self.admin)
        self.ana = User.objects.create_user(
            email='ana@fluxar.teste', password=SENHA, name='Ana', email_verified=True,
        )
        self.access, self.refresh = criar_sessao(self.ana)
        self.sid = RefreshToken(self.refresh)['sid']

    def como_admin(self, metodo, url, dados):
        return getattr(self.client, metodo)(
            url, dados, format='json', HTTP_AUTHORIZATION=f'Bearer {self.access_admin}',
        )

    def assertTokensDaContaRecusados(self):
        me = self.client.get(ME, HTTP_AUTHORIZATION=f'Bearer {self.access}')
        self.assertEqual(me.status_code, status.HTTP_401_UNAUTHORIZED)
        self.client.cookies[NOME_DO_COOKIE] = self.refresh
        renovacao = self.client.post(RENOVAR, HTTP_ORIGIN=FRONTEND)
        self.assertEqual(renovacao.status_code, status.HTTP_401_UNAUTHORIZED)
        # A sessão do administrador continua valendo
        admin = self.client.get(ME, HTTP_AUTHORIZATION=f'Bearer {self.access_admin}')
        self.assertEqual(admin.status_code, status.HTTP_200_OK)

    def assertSessaoEncerrada(self):
        self.assertIsNotNone(Sessao.objects.get(pk=self.sid).encerrada_em)

    def test_desativar_pelo_painel_encerra_as_sessoes(self):
        resposta = self.como_admin('patch', f'/api/admin/users/{self.ana.pk}/', {
            'admin_password': SENHA, 'is_active': False,
        })

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertSessaoEncerrada()
        self.assertTokensDaContaRecusados()

    def test_arquivar_pelo_painel_encerra_as_sessoes(self):
        resposta = self.como_admin('delete', f'/api/admin/users/{self.ana.pk}/', {
            'admin_password': SENHA,
        })

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertSessaoEncerrada()
        self.assertTokensDaContaRecusados()

    def test_arquivar_em_massa_encerra_as_sessoes(self):
        resposta = self.como_admin('delete', '/api/admin/users/', {
            'admin_password': SENHA, 'user_ids': [str(self.ana.pk)],
        })

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertSessaoEncerrada()
        self.assertTokensDaContaRecusados()

    def test_excluir_pelo_painel_apaga_as_sessoes(self):
        for metodo, url, dados in (
            ('delete', '/api/admin/users/{pk}/', {'admin_password': SENHA, 'permanent': True}),
            ('delete', '/api/admin/users/{pk}/hard-delete/', {'admin_password': SENHA}),
        ):
            with self.subTest(url=url):
                resposta = self.como_admin(metodo, url.format(pk=self.ana.pk), dados)

                self.assertEqual(resposta.status_code, status.HTTP_200_OK)
                self.assertFalse(Sessao.objects.filter(pk=self.sid).exists())
                self.assertTokensDaContaRecusados()
            # Conta nova para o próximo caminho de exclusão
            self.ana = User.objects.create_user(
                email='ana@fluxar.teste', password=SENHA, name='Ana', email_verified=True,
            )
            self.access, self.refresh = criar_sessao(self.ana)
            self.sid = RefreshToken(self.refresh)['sid']

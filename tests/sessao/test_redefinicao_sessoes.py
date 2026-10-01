"""
Redefinição de senha encerra todas as sessões (SESSAO-16 e SESSAO-18).

Depois da redefinição por link ou pelo administrador, todas as sessões do
usuário recebem 401, no token de acesso e na renovação.
"""
from datetime import timedelta

from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from api.cookies import NOME_DO_COOKIE
from api.models import PasswordResetToken, User
from api.sessoes import criar_sessao

ME = '/api/auth/me/'
RENOVAR = '/api/auth/refresh/'
FRONTEND = 'https://app.fluxar.teste'
SENHA = 'Cofre-Azul-2026'
SENHA_NOVA = 'Trilha-Verde-2027'


@override_settings(FRONTEND_URL=FRONTEND, CORS_ALLOWED_ORIGINS=[])
class RedefinicaoEncerraTodasAsSessoesTests(APITestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user(
            email='ana@fluxar.teste', password=SENHA, name='Ana', email_verified=True,
        )
        self.sessoes = [criar_sessao(self.ana), criar_sessao(self.ana)]

    def me(self, access):
        return self.client.get(ME, HTTP_AUTHORIZATION=f'Bearer {access}')

    def renovar(self, refresh):
        self.client.cookies[NOME_DO_COOKIE] = refresh
        return self.client.post(RENOVAR, HTTP_ORIGIN=FRONTEND)

    def assertTodasEncerradas(self):
        for access, refresh in self.sessoes:
            self.assertEqual(self.me(access).status_code, status.HTTP_401_UNAUTHORIZED)
            self.assertEqual(self.renovar(refresh).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_redefinicao_por_link_encerra_todas_as_sessoes(self):
        link = PasswordResetToken.objects.create(
            user=self.ana, expires_at=timezone.now() + timedelta(hours=1),
        )

        resposta = self.client.post('/api/auth/reset-password/', {
            'token': str(link.token), 'new_password': SENHA_NOVA, 'new_password_confirm': SENHA_NOVA,
        }, format='json')

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertTodasEncerradas()

    def test_redefinicao_pelo_administrador_encerra_todas_as_sessoes_do_usuario(self):
        admin = User.objects.create_user(
            email='admin@fluxar.teste', password=SENHA, name='Admin', email_verified=True,
            is_staff=True, role='ADMIN',
        )
        access_admin, _ = criar_sessao(admin)

        resposta = self.client.post(
            f'/api/admin/users/{self.ana.pk}/reset-password/',
            {'admin_password': SENHA, 'new_password': SENHA_NOVA}, format='json',
            HTTP_AUTHORIZATION=f'Bearer {access_admin}',
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertTodasEncerradas()
        # A sessão do administrador não é a do usuário redefinido
        self.assertEqual(self.me(access_admin).status_code, status.HTTP_200_OK)

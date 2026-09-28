"""
Rotas públicas sem sessão (AUTH-40).

As seis rotas públicas de autenticação ignoram um token de acesso vencido ou
malformado e respondem como a um pedido anônimo. As rotas protegidas
continuam recusando o mesmo token.
"""
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from api.models import EmailVerificationToken, PasswordResetToken, User

SENHA = 'Cofre-Azul-2026'


@mock.patch('api.views.send_password_reset_email', return_value=True)
@mock.patch('api.views.send_verification_email', return_value=True)
class RotasPublicasComTokenInvalidoTests(APITestCase):

    def setUp(self):
        cache.clear()
        self.usuario = User.objects.create_user(
            email='ana@x.com', password=SENHA, name='Ana', email_verified=True,
        )
        vencido = AccessToken.for_user(self.usuario)
        vencido.set_exp(from_time=timezone.now() - timedelta(hours=2), lifetime=timedelta(hours=1))
        self.cabecalhos = {
            'vencido': f'Bearer {vencido}',
            'malformado': 'Bearer nao-e-um-jwt',
        }

    def com_cada_token(self, chamar, esperado):
        for nome, cabecalho in self.cabecalhos.items():
            with self.subTest(token=nome):
                resposta = chamar(cabecalho)
                self.assertEqual(resposta.status_code, esperado, resposta.data)

    def test_cadastro_processado_como_anonimo(self, *_):
        emails = iter(['bia@x.com', 'caio@x.com'])
        self.com_cada_token(lambda cabecalho: self.client.post('/api/auth/register/', {
            'name': 'Pessoa', 'email': next(emails), 'password': SENHA,
            'password_confirm': SENHA, 'terms_accepted': True,
        }, format='json', HTTP_AUTHORIZATION=cabecalho), status.HTTP_201_CREATED)

    def test_login_processado_como_anonimo(self, *_):
        self.com_cada_token(lambda cabecalho: self.client.post(
            '/api/auth/login/', {'email': 'ana@x.com', 'password': SENHA}, format='json',
            HTTP_AUTHORIZATION=cabecalho,
        ), status.HTTP_200_OK)

    def test_verificacao_processada_como_anonima(self, *_):
        User.objects.filter(pk=self.usuario.pk).update(email_verified=False)

        def verificar(cabecalho):
            token = EmailVerificationToken.objects.create(
                user=self.usuario, expires_at=timezone.now() + timedelta(hours=24),
            )
            return self.client.get(
                '/api/auth/verify-email/', {'token': str(token.token)}, HTTP_AUTHORIZATION=cabecalho,
            )
        self.com_cada_token(verificar, status.HTTP_200_OK)

    def test_reenvio_processado_como_anonimo(self, *_):
        self.com_cada_token(lambda cabecalho: self.client.post(
            '/api/auth/resend-verification/', {'email': 'ana@x.com'}, format='json',
            HTTP_AUTHORIZATION=cabecalho,
        ), status.HTTP_200_OK)

    def test_esqueci_a_senha_processado_como_anonimo(self, *_):
        self.com_cada_token(lambda cabecalho: self.client.post(
            '/api/auth/forgot-password/', {'email': 'ana@x.com'}, format='json',
            HTTP_AUTHORIZATION=cabecalho,
        ), status.HTTP_200_OK)

    def test_redefinicao_processada_como_anonima(self, *_):
        def redefinir(cabecalho):
            token = PasswordResetToken.objects.create(
                user=self.usuario, expires_at=timezone.now() + timedelta(hours=1),
            )
            return self.client.post('/api/auth/reset-password/', {
                'token': str(token.token), 'new_password': 'Trilha-Verde-2027',
                'new_password_confirm': 'Trilha-Verde-2027',
            }, format='json', HTTP_AUTHORIZATION=cabecalho)
        self.com_cada_token(redefinir, status.HTTP_200_OK)

    def test_rota_protegida_continua_recusando_o_mesmo_token(self, *_):
        self.com_cada_token(
            lambda cabecalho: self.client.get('/api/auth/me/', HTTP_AUTHORIZATION=cabecalho),
            status.HTTP_401_UNAUTHORIZED,
        )

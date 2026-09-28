"""
Link de verificação de e-mail (AUTH-08 e AUTH-09).

Todo link inválido recebe a mesma resposta: HTTP 400 com
"Link inválido ou expirado." e o código invalid_link.
"""
import uuid
from datetime import timedelta
from unittest import mock

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from api.models import EmailVerificationToken, SystemLog, User

VERIFICAR = '/api/auth/verify-email/'
LINK_INVALIDO = {'detail': 'Link inválido ou expirado.', 'code': 'invalid_link'}


class LinkDeVerificacaoTests(APITestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(
            email='pendente@fluxar.teste', password='senha-de-teste-123', name='Pendente',
        )

    def novo_token(self):
        return EmailVerificationToken.objects.create(
            user=self.usuario, expires_at=timezone.now() + timedelta(hours=24),
        )

    def abrir(self, token):
        return self.client.get(VERIFICAR, {'token': str(token)})

    def assertLinkInvalido(self, resposta):
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resposta.data, LINK_INVALIDO)
        self.assertNotIn('access', resposta.data)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.email_verified)

    # AUTH-08 -----------------------------------------------------------

    def test_link_valido_confirma_o_email_e_inicia_a_sessao(self):
        token = self.novo_token()

        resposta = self.abrir(token.token)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(AccessToken(resposta.data['access'])['user_id'], str(self.usuario.pk))
        self.assertEqual(RefreshToken(resposta.data['refresh'])['user_id'], str(self.usuario.pk))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.email_verified)
        self.assertTrue(self.usuario.is_active)
        token.refresh_from_db()
        self.assertTrue(token.used)
        self.assertTrue(SystemLog.objects.filter(user=self.usuario, action='EMAIL_VERIFIED').exists())

    def test_link_valido_nao_reativa_conta_desativada_pelo_administrador(self):
        User.objects.filter(pk=self.usuario.pk).update(is_active=False)
        token = self.novo_token()

        resposta = self.abrir(token.token)

        self.assertNotIn('access', resposta.data)
        self.assertNotIn('refresh', resposta.data)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_active)

    # AUTH-09 -----------------------------------------------------------

    def test_link_aberto_duas_vezes_recusado_na_segunda(self):
        token = self.novo_token()
        self.assertEqual(self.abrir(token.token).status_code, status.HTTP_200_OK)

        resposta = self.abrir(token.token)

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resposta.data, LINK_INVALIDO)
        self.assertNotIn('access', resposta.data)

    def test_link_vencido_ha_25_horas_recusado(self):
        token = self.novo_token()
        daqui_a_25_horas = timezone.now() + timedelta(hours=25)

        with mock.patch('django.utils.timezone.now', return_value=daqui_a_25_horas):
            resposta = self.abrir(token.token)

        self.assertLinkInvalido(resposta)
        token.refresh_from_db()
        self.assertFalse(token.used)

    def test_link_substituido_por_um_mais_novo_recusado(self):
        antigo = self.novo_token()
        novo = self.novo_token()

        resposta = self.abrir(antigo.token)

        self.assertLinkInvalido(resposta)
        novo.refresh_from_db()
        self.assertFalse(novo.used)

    def test_link_sem_token_recusado(self):
        resposta = self.client.get(VERIFICAR)

        self.assertLinkInvalido(resposta)

    def test_link_com_token_malformado_recusado_sem_erro_500(self):
        self.novo_token()

        resposta = self.abrir('nao-e-um-uuid')

        self.assertLinkInvalido(resposta)

    def test_link_com_token_inexistente_recusado(self):
        self.novo_token()

        resposta = self.abrir(uuid.uuid4())

        self.assertLinkInvalido(resposta)

"""
Reenvio do e-mail de verificação (AUTH-10 e AUTH-11).

A resposta é sempre a mesma, para não revelar se o e-mail está cadastrado ou
já foi verificado. O envio é simulado na view.
"""
from datetime import timedelta
from unittest import mock

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import EmailVerificationToken, User

REENVIAR = '/api/auth/resend-verification/'
VERIFICAR = '/api/auth/verify-email/'
RESPOSTA_NEUTRA = {
    'message': 'Se houver uma conta aguardando verificação com este e-mail, enviamos um novo link.',
}


@mock.patch('api.views.send_verification_email', return_value=True)
class ReenvioDaVerificacaoTests(APITestCase):

    def setUp(self):
        self.pendente = User.objects.create_user(
            email='pendente@fluxar.teste', password='senha-de-teste-123', name='Pendente',
        )
        self.link_antigo = EmailVerificationToken.objects.create(
            user=self.pendente, expires_at=timezone.now() + timedelta(hours=24),
        )

    def reenviar(self, email):
        return self.client.post(REENVIAR, {'email': email}, format='json')

    # AUTH-10 -----------------------------------------------------------

    def test_conta_pendente_recebe_link_novo_e_o_antigo_deixa_de_valer(self, envio):
        antes = timezone.now()
        resposta = self.reenviar('PENDENTE@Fluxar.teste')

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data, RESPOSTA_NEUTRA)
        novo = EmailVerificationToken.objects.exclude(pk=self.link_antigo.pk).get(user=self.pendente)
        self.assertFalse(novo.used)
        self.assertGreaterEqual(novo.expires_at, antes + timedelta(hours=24))
        self.assertLessEqual(novo.expires_at, timezone.now() + timedelta(hours=24))
        envio.assert_called_once()
        usuario_enviado, token_enviado = envio.call_args.args
        self.assertEqual(usuario_enviado.pk, self.pendente.pk)
        self.assertEqual(token_enviado.pk, novo.pk)
        self.link_antigo.refresh_from_db()
        self.assertTrue(self.link_antigo.used)

        antigo = self.client.get(VERIFICAR, {'token': str(self.link_antigo.token)})
        self.assertEqual(antigo.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(antigo.data['code'], 'invalid_link')

        valido = self.client.get(VERIFICAR, {'token': str(novo.token)})
        self.assertEqual(valido.status_code, status.HTTP_200_OK)
        self.assertIn('access', valido.data)
        self.pendente.refresh_from_db()
        self.assertTrue(self.pendente.email_verified)

    # AUTH-11 -----------------------------------------------------------

    def test_email_inexistente_recebe_a_mesma_resposta_sem_envio(self, envio):
        resposta = self.reenviar('ninguem@fluxar.teste')

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data, RESPOSTA_NEUTRA)
        envio.assert_not_called()
        self.assertEqual(EmailVerificationToken.objects.count(), 1)

    def test_conta_ja_verificada_recebe_a_mesma_resposta_sem_envio(self, envio):
        verificada = User.objects.create_user(
            email='verificada@fluxar.teste', password='senha-de-teste-123', name='Verificada',
            email_verified=True,
        )

        resposta = self.reenviar('verificada@fluxar.teste')

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data, RESPOSTA_NEUTRA)
        envio.assert_not_called()
        self.assertFalse(EmailVerificationToken.objects.filter(user=verificada).exists())
        self.link_antigo.refresh_from_db()
        self.assertFalse(self.link_antigo.used)

    def test_conta_desativada_nao_e_pendente_e_nao_recebe_link(self, envio):
        # Pela AD-035, pendente é email_verified=False com is_active=True
        User.objects.filter(pk=self.pendente.pk).update(is_active=False)

        resposta = self.reenviar('pendente@fluxar.teste')

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data, RESPOSTA_NEUTRA)
        envio.assert_not_called()
        self.assertEqual(EmailVerificationToken.objects.filter(user=self.pendente).count(), 1)

    def test_email_malformado_recusado_no_campo_email(self, envio):
        resposta = self.reenviar('nao-e-email')

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', resposta.data)
        envio.assert_not_called()

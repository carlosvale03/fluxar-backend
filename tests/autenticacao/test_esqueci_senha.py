"""
"Esqueci a senha" (AUTH-18, AUTH-19 e AUTH-27).

A resposta é sempre a mesma, exista ou não a conta, e mesmo quando o envio
falha. O envio é simulado na view.
"""
from datetime import timedelta
from unittest import mock

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import PasswordResetToken, User

ESQUECI = '/api/auth/forgot-password/'
RESPOSTA_NEUTRA = {
    'message': 'Se o e-mail estiver cadastrado, enviamos um link para redefinir a senha.',
}


@mock.patch('api.views.send_password_reset_email', return_value=True)
class EsqueciASenhaTests(APITestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(
            email='ricardo@fluxar.teste', password='senha-de-teste-123', name='Ricardo',
            email_verified=True,
        )

    def pedir(self, email):
        return self.client.post(ESQUECI, {'email': email}, format='json')

    def assertEnviadoPara(self, envio, usuario):
        envio.assert_called_once()
        usuario_enviado, token_enviado = envio.call_args.args
        self.assertEqual(usuario_enviado.pk, usuario.pk)
        token = PasswordResetToken.objects.get(user=usuario, used=False)
        self.assertEqual(token_enviado.pk, token.pk)
        return token

    # AUTH-18 -----------------------------------------------------------

    def test_email_cadastrado_recebe_a_resposta_neutra_e_o_link(self, envio):
        resposta = self.pedir('ricardo@fluxar.teste')

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data, RESPOSTA_NEUTRA)
        self.assertEnviadoPara(envio, self.usuario)

    def test_email_inexistente_recebe_a_mesma_resposta_sem_envio_nem_log(self, envio):
        with self.assertNoLogs('api.views'):
            resposta = self.pedir('ninguem@fluxar.teste')

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data, RESPOSTA_NEUTRA)
        envio.assert_not_called()
        self.assertFalse(PasswordResetToken.objects.exists())

    def test_conta_desativada_recebe_a_mesma_resposta(self, envio):
        User.objects.filter(pk=self.usuario.pk).update(is_active=False)

        resposta = self.pedir('ricardo@fluxar.teste')

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data, RESPOSTA_NEUTRA)
        self.assertEnviadoPara(envio, self.usuario)

    def test_email_com_outra_caixa_encontra_a_conta(self, envio):
        resposta = self.pedir('Ricardo@FLUXAR.teste')

        self.assertEqual(resposta.data, RESPOSTA_NEUTRA)
        self.assertEnviadoPara(envio, self.usuario)

    # AUTH-19 -----------------------------------------------------------

    def test_link_novo_vale_1_hora_e_o_anterior_deixa_de_valer(self, envio):
        anterior = PasswordResetToken.objects.create(
            user=self.usuario, expires_at=timezone.now() + timedelta(hours=1),
        )

        antes = timezone.now()
        self.pedir('ricardo@fluxar.teste')
        depois = timezone.now()

        novo = self.assertEnviadoPara(envio, self.usuario)
        self.assertNotEqual(novo.pk, anterior.pk)
        self.assertGreaterEqual(novo.expires_at, antes + timedelta(hours=1))
        self.assertLessEqual(novo.expires_at, depois + timedelta(hours=1))
        anterior.refresh_from_db()
        self.assertTrue(anterior.used)
        self.assertFalse(anterior.is_valid())

    def test_envio_na_propria_requisicao_sem_thread(self, envio):
        with mock.patch('threading.Thread') as thread:
            self.pedir('ricardo@fluxar.teste')

        thread.assert_not_called()
        envio.assert_called_once()

    # AUTH-27 -----------------------------------------------------------

    def test_falha_no_envio_mantem_a_resposta_e_registra_o_email_mascarado(self, envio):
        envio.return_value = False

        with self.assertLogs('api.views', level='WARNING') as logs:
            resposta = self.pedir('ricardo@fluxar.teste')

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data, RESPOSTA_NEUTRA)
        saida = '\n'.join(logs.output)
        self.assertIn('ri***@fluxar.teste', saida)
        self.assertNotIn('ricardo@fluxar.teste', saida)
        token = PasswordResetToken.objects.get(user=self.usuario)
        self.assertNotIn(str(token.token)[:8], saida)

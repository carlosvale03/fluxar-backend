"""
Fluxo completo de entrada, só pela API (Success Criteria da spec).

Cadastro, login recusado sem verificação, reenvio, link antigo recusado,
verificação pelo link novo, login, "esqueci a senha", redefinição pelo link e
login com a senha nova. Os e-mails são lidos da chamada ao Resend, simulada
no requests.post do serviço de e-mail, e os tokens saem do link do e-mail.
"""
import re
from unittest import mock

from django.core.cache import cache
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from api.utils import email_service

FRONTEND = 'https://app.fluxar.teste'
EMAIL = 'ana.fluxo@x.com'
SENHA_ANTIGA = 'cofre-forte-2026'
SENHA_NOVA = 'outro-cofre-2027'


@override_settings(
    FRONTEND_URL=FRONTEND,
    ENABLE_RESEND_PROVIDER=True,
    ENABLE_SMTP_FALLBACK=False,
)
@mock.patch.dict('os.environ', {'RESEND_API_KEY': 'chave-resend-de-teste'})
class FluxoCompletoDeEntradaTests(APITestCase):

    def setUp(self):
        cache.clear()
        patcher = mock.patch.object(email_service.requests, 'post')
        self.resend = patcher.start()
        self.addCleanup(patcher.stop)
        self.resend.return_value.status_code = 200

    def ultimo_email(self):
        return self.resend.call_args.kwargs['json']

    def token_do_link(self, caminho):
        """Tira o token do link do último e-mail, conferindo o endereço do link."""
        email = self.ultimo_email()
        self.assertEqual(email['to'], [EMAIL])
        links = re.findall(rf'{re.escape(FRONTEND + caminho)}\?token=([^"\s<]+)', email['html'])
        self.assertTrue(links, f'nenhum link {caminho} no e-mail')
        return links[0]

    def entrar(self, senha, email=EMAIL):
        return self.client.post('/api/auth/login/', {'email': email, 'password': senha}, format='json')

    def test_cadastro_verificacao_reenvio_login_e_redefinicao(self):
        # 1. Cadastro com o e-mail em outra caixa (AUTH-01, AUTH-02)
        resposta = self.client.post('/api/auth/register/', {
            'name': 'Ana Fluxo',
            'email': 'Ana.Fluxo@X.com',
            'password': SENHA_ANTIGA,
            'password_confirm': SENHA_ANTIGA,
            'terms_accepted': True,
        }, format='json')
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        self.assertIs(resposta.data['email_sent'], True)
        self.assertEqual(self.resend.call_count, 1)
        link_antigo = self.token_do_link('/auth/verify-email')

        # 2. Login recusado enquanto o e-mail não foi confirmado (AUTH-13)
        resposta = self.entrar(SENHA_ANTIGA)
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resposta.data['code'], 'email_not_verified')
        self.assertEqual(resposta.data['detail'], 'Confirme seu e-mail para entrar.')

        # 3. Reenvio: um link novo, e o antigo deixa de valer (AUTH-10)
        resposta = self.client.post('/api/auth/resend-verification/', {'email': EMAIL}, format='json')
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(
            resposta.data['message'],
            'Se houver uma conta aguardando verificação com este e-mail, enviamos um novo link.',
        )
        self.assertEqual(self.resend.call_count, 2)
        link_novo = self.token_do_link('/auth/verify-email')
        self.assertNotEqual(link_novo, link_antigo)

        # 4. O link antigo é recusado; o novo confirma e inicia a sessão (AUTH-09, AUTH-08)
        resposta = self.client.get('/api/auth/verify-email/', {'token': link_antigo})
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resposta.data['detail'], 'Link inválido ou expirado.')
        self.assertEqual(resposta.data['code'], 'invalid_link')

        resposta = self.client.get('/api/auth/verify-email/', {'token': link_novo})
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertTrue(resposta.data['access'])
        self.assertTrue(resposta.data['refresh'])

        # 5. Login com a conta verificada (AUTH-14)
        resposta = self.entrar(SENHA_ANTIGA)
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertTrue(resposta.data['access'])

        # 6. "Esqueci a senha" com a resposta neutra e o link por e-mail (AUTH-18, AUTH-19)
        resposta = self.client.post('/api/auth/forgot-password/', {'email': EMAIL}, format='json')
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(
            resposta.data['message'],
            'Se o e-mail estiver cadastrado, enviamos um link para redefinir a senha.',
        )
        self.assertEqual(self.resend.call_count, 3)
        link_redefinicao = self.token_do_link('/auth/reset-password')

        # 7. Redefinição pelo link do e-mail (AUTH-20, AUTH-23)
        corpo = {
            'token': link_redefinicao,
            'new_password': SENHA_NOVA,
            'new_password_confirm': SENHA_NOVA,
        }
        resposta = self.client.post('/api/auth/reset-password/', corpo, format='json')
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data['message'], 'Senha redefinida com sucesso.')

        # O mesmo link não vale uma segunda vez (AUTH-21)
        resposta = self.client.post('/api/auth/reset-password/', corpo, format='json')
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resposta.data['detail'], 'Link inválido ou expirado.')

        # 8. A senha nova entra e a antiga é recusada (AUTH-14, AUTH-15)
        resposta = self.entrar(SENHA_NOVA)
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertTrue(resposta.data['access'])

        resposta = self.entrar(SENHA_ANTIGA)
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resposta.data['detail'], 'E-mail ou senha incorretos.')
        self.assertEqual(resposta.data['code'], 'invalid_credentials')

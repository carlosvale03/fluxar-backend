"""
Login (AUTH-13 a AUTH-16).

O estado da conta (pendente ou desativada) só aparece com a senha correta.
Com a senha errada, ou com um e-mail inexistente, a resposta é sempre a mesma.
"""
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from api.models import User

LOGIN = '/api/auth/login/'
SENHA = 'Cofre-Azul-2026'
SENHA_ERRADA = 'Cofre-Roxo-2026'
CREDENCIAIS_INCORRETAS = {'detail': 'E-mail ou senha incorretos.', 'code': 'invalid_credentials'}
EMAIL_NAO_VERIFICADO = {'detail': 'Confirme seu e-mail para entrar.', 'code': 'email_not_verified'}
CONTA_DESATIVADA = {'detail': 'Esta conta está desativada.', 'code': 'account_disabled'}


class LoginTests(APITestCase):

    def setUp(self):
        self.verificada = User.objects.create_user(
            email='verificada@fluxar.teste', password=SENHA, name='Verificada',
            email_verified=True,
        )
        self.pendente = User.objects.create_user(
            email='pendente@fluxar.teste', password=SENHA, name='Pendente',
        )
        self.desativada = User.objects.create_user(
            email='desativada@fluxar.teste', password=SENHA, name='Desativada',
            email_verified=True, is_active=False,
        )

    def entrar(self, email, senha):
        return self.client.post(LOGIN, {'email': email, 'password': senha}, format='json')

    def assertRecusado(self, resposta, corpo):
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resposta.data, corpo)
        self.assertNotIn('access', resposta.data)
        self.assertNotIn('refresh', resposta.data)

    # AUTH-14 -----------------------------------------------------------

    def test_conta_verificada_e_ativa_com_senha_certa_inicia_a_sessao(self):
        resposta = self.entrar('verificada@fluxar.teste', SENHA)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        acesso = AccessToken(resposta.data['access'])
        self.assertEqual(acesso['user_id'], str(self.verificada.pk))
        self.assertEqual(acesso['email'], 'verificada@fluxar.teste')
        self.assertEqual(acesso['name'], 'Verificada')
        self.assertEqual(acesso['plan'], 'COMMON')
        self.assertEqual(acesso['role'], 'USER')
        self.assertEqual(RefreshToken(resposta.data['refresh'])['user_id'], str(self.verificada.pk))

    # AUTH-15 -----------------------------------------------------------

    def test_senha_errada_na_conta_verificada_da_a_mensagem_unica(self):
        self.assertRecusado(self.entrar('verificada@fluxar.teste', SENHA_ERRADA), CREDENCIAIS_INCORRETAS)

    def test_senha_errada_na_conta_pendente_nao_revela_o_estado(self):
        self.assertRecusado(self.entrar('pendente@fluxar.teste', SENHA_ERRADA), CREDENCIAIS_INCORRETAS)

    def test_senha_errada_na_conta_desativada_nao_revela_o_estado(self):
        self.assertRecusado(self.entrar('desativada@fluxar.teste', SENHA_ERRADA), CREDENCIAIS_INCORRETAS)

    def test_email_inexistente_da_a_mesma_mensagem_da_senha_errada(self):
        self.assertRecusado(self.entrar('ninguem@fluxar.teste', SENHA), CREDENCIAIS_INCORRETAS)

    # AUTH-13 -----------------------------------------------------------

    def test_conta_pendente_com_senha_certa_pede_a_confirmacao_do_email(self):
        self.assertRecusado(self.entrar('pendente@fluxar.teste', SENHA), EMAIL_NAO_VERIFICADO)

    # AUTH-16 -----------------------------------------------------------

    def test_conta_desativada_com_senha_certa_avisa_a_desativacao(self):
        self.assertRecusado(self.entrar('desativada@fluxar.teste', SENHA), CONTA_DESATIVADA)

    def test_conta_desativada_e_nao_verificada_avisa_a_desativacao(self):
        # Pela AD-035, is_active=False é a desativação, qualquer que seja o e-mail
        User.objects.filter(pk=self.pendente.pk).update(is_active=False)

        self.assertRecusado(self.entrar('pendente@fluxar.teste', SENHA), CONTA_DESATIVADA)

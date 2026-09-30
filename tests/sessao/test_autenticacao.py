"""
Autenticação pela sessão (SESSAO-17 e SESSAO-18).

O token de acesso só vale enquanto a sessão dele estiver aberta e a conta
ativa. Um token dentro da validade de uma sessão encerrada, de uma conta
desativada ou sem `sid` recebe 401 já na próxima requisição.
"""
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from api.models import User
from api.sessoes import criar_sessao, encerrar

ME = '/api/auth/me/'
SENHA = 'Cofre-Azul-2026'


class AutenticacaoPelaSessaoTests(APITestCase):

    def setUp(self):
        self.ana = User.objects.create_user(
            email='ana@fluxar.teste', password=SENHA, name='Ana', email_verified=True,
        )
        self.access, self.refresh = criar_sessao(self.ana)

    def me(self, access):
        return self.client.get(ME, HTTP_AUTHORIZATION=f'Bearer {access}')

    def test_sessao_aberta_e_conta_ativa_atendem_a_requisicao(self):
        resposta = self.me(self.access)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data['email'], 'ana@fluxar.teste')

    # SESSAO-18 ---------------------------------------------------------

    def test_token_de_sessao_encerrada_dentro_da_validade_recebe_401(self):
        encerrar(RefreshToken(self.refresh)['sid'])

        self.assertEqual(self.me(self.access).status_code, status.HTTP_401_UNAUTHORIZED)

    # SESSAO-17 ---------------------------------------------------------

    def test_token_de_conta_desativada_recebe_401(self):
        User.objects.filter(pk=self.ana.pk).update(is_active=False)

        self.assertEqual(self.me(self.access).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_sem_sid_recebe_401(self):
        # Token das versões antigas, emitido antes das sessões
        antigo = AccessToken.for_user(self.ana)

        self.assertEqual(self.me(str(antigo)).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_de_outro_usuario_com_o_sid_da_vitima_recebe_401(self):
        bia = User.objects.create_user(
            email='bia@fluxar.teste', password=SENHA, name='Bia', email_verified=True,
        )
        forjado = AccessToken.for_user(bia)
        forjado['sid'] = AccessToken(self.access)['sid']

        self.assertEqual(self.me(str(forjado)).status_code, status.HTTP_401_UNAUTHORIZED)

"""
Troca de senha com o usuário logado (SESSAO-15).

Trocar a senha encerra todas as outras sessões do usuário e mantém a atual.
Uma troca recusada não encerra nada.
"""
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from api.cookies import NOME_DO_COOKIE
from api.models import User
from api.sessoes import criar_sessao

TROCAR = '/api/users/me/password/'
ME = '/api/auth/me/'
RENOVAR = '/api/auth/refresh/'
FRONTEND = 'https://app.fluxar.teste'
SENHA = 'Cofre-Azul-2026'
SENHA_NOVA = 'Trilha-Verde-2027'


@override_settings(FRONTEND_URL=FRONTEND, CORS_ALLOWED_ORIGINS=[])
class TrocaDeSenhaEncerraAsOutrasSessoesTests(APITestCase):

    def setUp(self):
        self.ana = User.objects.create_user(
            email='ana@fluxar.teste', password=SENHA, name='Ana', email_verified=True,
        )
        self.access_atual, self.refresh_atual = criar_sessao(self.ana)
        self.access_outra, self.refresh_outra = criar_sessao(self.ana)

    def me(self, access):
        return self.client.get(ME, HTTP_AUTHORIZATION=f'Bearer {access}')

    def renovar(self, refresh):
        self.client.cookies[NOME_DO_COOKIE] = refresh
        return self.client.post(RENOVAR, HTTP_ORIGIN=FRONTEND)

    def trocar(self, senha_atual=SENHA, senha_nova=SENHA_NOVA):
        return self.client.put(
            TROCAR, {'current_password': senha_atual, 'new_password': senha_nova},
            format='json', HTTP_AUTHORIZATION=f'Bearer {self.access_atual}',
        )

    def test_outra_sessao_recebe_401_na_proxima_requisicao_e_na_renovacao(self):
        self.assertEqual(self.trocar().status_code, status.HTTP_200_OK)

        self.assertEqual(self.me(self.access_outra).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.renovar(self.refresh_outra).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_sessao_atual_continua_atendida_e_renovando(self):
        self.assertEqual(self.trocar().status_code, status.HTTP_200_OK)

        self.assertEqual(self.me(self.access_atual).status_code, status.HTTP_200_OK)
        self.assertEqual(self.renovar(self.refresh_atual).status_code, status.HTTP_200_OK)

    def test_troca_recusada_nao_encerra_nenhuma_sessao(self):
        for senha_atual, senha_nova in (('Cofre-Roxo-2026', SENHA_NOVA), (SENHA, '123')):
            with self.subTest(senha_atual=senha_atual, senha_nova=senha_nova):
                self.assertEqual(
                    self.trocar(senha_atual, senha_nova).status_code, status.HTTP_400_BAD_REQUEST,
                )
                self.assertEqual(self.me(self.access_outra).status_code, status.HTTP_200_OK)

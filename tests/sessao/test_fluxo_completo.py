"""
Fluxo completo de sessão pela API, com dois navegadores da mesma usuária.

Percorre, em ordem, o que as Success Criteria da spec pedem:
- login nos dois com o token de renovação só no cookie (SESSAO-01);
- renovação com rotação e recusa do token antigo (SESSAO-08, SESSAO-09);
- troca de senha no primeiro, que continua, derrubando o segundo
  (SESSAO-15, SESSAO-18);
- logout, que revoga o token de renovação (SESSAO-13);
- manutenção ligada e desligada pelo painel: o usuário comum recebe 503 nas
  rotas de dados sem perder a sessão, e o administrador trabalha normalmente
  (SESSAO-19, SESSAO-20, SESSAO-23).
"""
from django.core.cache import cache
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from api.cookies import NOME_DO_COOKIE
from api.models import User
from core import manutencao

FRONTEND = 'https://app.fluxar.teste'
LOGIN = '/api/auth/login/'
RENOVAR = '/api/auth/refresh/'
SAIR = '/api/auth/logout/'
ME = '/api/auth/me/'
TROCAR = '/api/users/me/password/'
AJUSTES = '/api/admin/settings/'
SAUDE = '/api/health/'
DADOS = '/api/accounts/'
SENHA = 'Cofre-Azul-2026'
SENHA_NOVA = 'Trilha-Verde-2027'
SESSAO_EXPIRADA = {'detail': 'Sessão expirada. Entre de novo.', 'code': 'session_expired'}
EM_MANUTENCAO = {
    'detail': 'O sistema está em manutenção programada. Por favor, tente novamente mais tarde.',
    'code': 'maintenance_mode',
}


@override_settings(FRONTEND_URL=FRONTEND, CORS_ALLOWED_ORIGINS=[])
class FluxoCompletoDeSessaoTests(APITestCase):

    def setUp(self):
        cache.clear()
        manutencao.invalidar()
        self.addCleanup(manutencao.invalidar)
        User.objects.create_user(
            email='ana@fluxar.teste', password=SENHA, name='Ana', email_verified=True,
        )
        User.objects.create_user(
            email='admin@fluxar.teste', password=SENHA, name='Admin', email_verified=True,
            role='ADMIN', is_staff=True,
        )

    # Passos ------------------------------------------------------------

    def entrar(self, navegador, email='ana@fluxar.teste', senha=SENHA):
        resposta = navegador.post(
            LOGIN, {'email': email, 'password': senha}, format='json', HTTP_ORIGIN=FRONTEND,
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertNotIn('refresh', resposta.data)
        self.assertTrue(resposta.cookies[NOME_DO_COOKIE]['httponly'])
        return resposta.data['access']

    def renovar(self, navegador):
        return navegador.post(RENOVAR, HTTP_ORIGIN=FRONTEND)

    def com_token(self, access):
        return {'HTTP_AUTHORIZATION': f'Bearer {access}'}

    def cookie(self, navegador):
        return navegador.cookies[NOME_DO_COOKIE].value

    def assertSessaoExpirada(self, resposta):
        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(resposta.json(), SESSAO_EXPIRADA)

    def assertEmManutencao(self, resposta):
        self.assertEqual(resposta.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(resposta.json(), EM_MANUTENCAO)

    # Fluxo -------------------------------------------------------------

    def test_fluxo_completo_de_sessao_em_dois_navegadores(self):
        a1, a2 = APIClient(), APIClient()

        # 1. Login nos dois navegadores
        access_a1 = self.entrar(a1)
        access_a2 = self.entrar(a2)
        self.assertEqual(a1.get(ME, **self.com_token(access_a1)).status_code, status.HTTP_200_OK)
        self.assertEqual(a2.get(ME, **self.com_token(access_a2)).status_code, status.HTTP_200_OK)

        # 2. A1 renova; o cookie antigo, reapresentado, é recusado
        cookie_antigo = self.cookie(a1)
        renovacao = self.renovar(a1)
        self.assertEqual(renovacao.status_code, status.HTTP_200_OK)
        access_a1 = renovacao.data['access']
        self.assertNotEqual(self.cookie(a1), cookie_antigo)
        copia = APIClient()
        copia.cookies[NOME_DO_COOKIE] = cookie_antigo
        self.assertSessaoExpirada(self.renovar(copia))
        self.assertEqual(a1.get(ME, **self.com_token(access_a1)).status_code, status.HTTP_200_OK)

        # 3. A1 troca a senha: A1 continua, A2 cai na requisição e na renovação
        troca = a1.put(
            TROCAR, {'current_password': SENHA, 'new_password': SENHA_NOVA},
            format='json', **self.com_token(access_a1),
        )
        self.assertEqual(troca.status_code, status.HTTP_200_OK)
        self.assertEqual(a1.get(ME, **self.com_token(access_a1)).status_code, status.HTTP_200_OK)
        self.assertEqual(a2.get(ME, **self.com_token(access_a2)).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertSessaoExpirada(self.renovar(a2))
        renovacao = self.renovar(a1)
        self.assertEqual(renovacao.status_code, status.HTTP_200_OK)
        access_a1 = renovacao.data['access']

        # 4. A1 sai: o cookie é apagado e o token de renovação deixa de valer
        cookie_antes_de_sair = self.cookie(a1)
        saida = a1.post(SAIR, HTTP_ORIGIN=FRONTEND)
        self.assertEqual(saida.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(saida.cookies[NOME_DO_COOKIE].value, '')
        a1.cookies[NOME_DO_COOKIE] = cookie_antes_de_sair
        self.assertSessaoExpirada(self.renovar(a1))

        # 5. Manutenção ligada pelo painel: o administrador continua, a usuária
        # comum entra, recebe 503 nos dados e mantém a sessão
        painel = APIClient()
        access_admin = self.entrar(painel, email='admin@fluxar.teste')
        ligar = painel.post(AJUSTES, {'maintenance_mode': True}, format='json', **self.com_token(access_admin))
        self.assertEqual(ligar.status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(SAUDE).json(), {'status': 'ok', 'maintenance': True})

        access_a2 = self.entrar(a2, senha=SENHA_NOVA)
        self.assertEmManutencao(a2.get(DADOS, **self.com_token(access_a2)))
        self.assertEqual(a2.get(ME, **self.com_token(access_a2)).status_code, status.HTTP_200_OK)
        self.assertEqual(painel.get(DADOS, **self.com_token(access_admin)).status_code, status.HTTP_200_OK)
        renovacao = self.renovar(a2)
        self.assertEqual(renovacao.status_code, status.HTTP_200_OK)
        access_a2 = renovacao.data['access']

        # Manutenção desligada pelo painel: a usuária comum volta, ainda logada
        desligar = painel.post(AJUSTES, {'maintenance_mode': False}, format='json', **self.com_token(access_admin))
        self.assertEqual(desligar.status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(SAUDE).json(), {'status': 'ok', 'maintenance': False})
        self.assertEqual(a2.get(DADOS, **self.com_token(access_a2)).status_code, status.HTTP_200_OK)

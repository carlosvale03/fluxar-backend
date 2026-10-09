"""
Bloqueio até o aceite da versão vigente dos termos (LGPD-28 a LGPD-30).

Os usuários destes testes são criados sem o aceite da versão vigente
(`versao_dos_termos_aceita=None`) e usam sessões de verdade, com o token de
acesso no cabeçalho, como o frontend.
"""
from unittest import mock

from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from api.cookies import NOME_DO_COOKIE
from api.models import AceiteDosTermos, User
from api.sessoes import criar_sessao
from core import termos

SENHA = 'senha-de-teste-123'
FRONTEND = 'https://app.fluxar.teste'
CONTAS = '/api/accounts/'
ACEITAR = '/api/terms/accept/'
BLOQUEADO = 'terms_acceptance_required'


@override_settings(FRONTEND_URL=FRONTEND, CORS_ALLOWED_ORIGINS=[])
class BloqueioDosTermosTests(APITestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user(
            email='ana@teste.fluxar', password=SENHA, name='Ana', email_verified=True,
            versao_dos_termos_aceita=None,
        )
        self.entrar(self.ana)

    def entrar(self, usuario):
        self.access, self.refresh = criar_sessao(usuario)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access}')

    def assertBloqueado(self, resposta, versao=None):
        self.assertEqual(resposta.status_code, 403, resposta.content)
        corpo = resposta.json()
        self.assertEqual(corpo['code'], BLOQUEADO)
        self.assertEqual(corpo['version'], versao or termos.VERSAO_VIGENTE)
        self.assertTrue(corpo['detail'])

    # LGPD-29 ---------------------------------------------------------------

    def test_sem_o_aceite_da_versao_vigente_as_contas_recebem_403(self):
        self.assertBloqueado(self.client.get(CONTAS))
        self.assertBloqueado(self.client.post(CONTAS, {'name': 'Nova', 'type': 'CHECKING'}, format='json'))

    def test_aceite_de_versao_antiga_tambem_bloqueia(self):
        termos.registrar_aceite(self.ana, '1.0')

        self.assertBloqueado(self.client.get(CONTAS))

    def test_rotas_liberadas_continuam_funcionando_sem_o_aceite(self):
        me = self.client.get('/api/auth/me/')
        self.assertEqual(me.status_code, 200, me.content)
        self.assertEqual(
            me.data['terms'], {'accepted_version': None, 'current_version': termos.VERSAO_VIGENTE},
        )
        self.assertIs(me.data['product_improvement_consent'], False)

        self.assertEqual(self.client.get('/api/terms/').status_code, 200)
        self.assertEqual(self.client.get('/api/health/').status_code, 200)
        exportacao = self.client.get('/api/users/me/export/')
        self.assertEqual(exportacao.status_code, 200, exportacao.content)

        self.client.credentials()
        login = self.client.post(
            '/api/auth/login/', {'email': 'ana@teste.fluxar', 'password': SENHA}, format='json',
        )
        self.assertEqual(login.status_code, 200, login.content)
        self.client.cookies[NOME_DO_COOKIE] = self.refresh
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access}')
        renovacao = self.client.post('/api/auth/refresh/', HTTP_ORIGIN=FRONTEND)
        self.assertEqual(renovacao.status_code, 200, renovacao.content)
        saida = self.client.post('/api/auth/logout/', HTTP_ORIGIN=FRONTEND)
        self.assertEqual(saida.status_code, 204)

    @mock.patch('api.views.send_account_deletion_email', return_value=True)
    def test_pedido_de_exclusao_e_cancelamento_funcionam_sem_o_aceite(self, envio):
        pedido = self.client.post('/api/users/me/delete/', {'password': SENHA}, format='json')
        self.assertEqual(pedido.status_code, 200, pedido.content)

        self.client.credentials()
        login = self.client.post(
            '/api/auth/login/', {'email': 'ana@teste.fluxar', 'password': SENHA}, format='json',
        )
        self.assertEqual(login.data['code'], 'deletion_pending')
        cancelamento = self.client.post(
            '/api/auth/cancel-deletion/', {'cancel_token': login.data['cancel_token']}, format='json',
        )
        self.assertEqual(cancelamento.status_code, 200, cancelamento.content)

        # De volta ao app, o aceite ainda é pedido
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {cancelamento.data['access']}")
        self.assertBloqueado(self.client.get(CONTAS))

    def test_sem_login_ou_com_token_invalido_a_rota_responde_401_como_sempre(self):
        self.client.credentials()
        self.assertEqual(self.client.get(CONTAS).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer token-invalido')
        self.assertEqual(self.client.get(CONTAS).status_code, 401)

    # LGPD-28, LGPD-30 ------------------------------------------------------

    def test_aceitar_a_versao_vigente_libera_e_mantem_os_aceites_anteriores(self):
        anterior = termos.registrar_aceite(self.ana, '1.0')

        resposta = self.client.post(ACEITAR, {'version': termos.VERSAO_VIGENTE}, format='json')

        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertEqual(resposta.data['accepted_version'], termos.VERSAO_VIGENTE)
        self.assertEqual(resposta.data['current_version'], termos.VERSAO_VIGENTE)
        self.assertEqual(self.client.get(CONTAS).status_code, 200)
        versoes = set(AceiteDosTermos.objects.filter(user=self.ana).values_list('versao', flat=True))
        self.assertEqual(versoes, {'1.0', termos.VERSAO_VIGENTE})
        self.assertTrue(AceiteDosTermos.objects.filter(pk=anterior.pk).exists())
        self.assertEqual(
            self.client.get('/api/auth/me/').data['terms']['accepted_version'], termos.VERSAO_VIGENTE,
        )

    def test_aceitar_outra_versao_recebe_400_no_campo_e_continua_bloqueado(self):
        for versao in ('1.0', '', None):
            with self.subTest(versao=versao):
                resposta = self.client.post(ACEITAR, {'version': versao}, format='json')

                self.assertEqual(resposta.status_code, 400)
                self.assertIn('version', resposta.data)
                self.assertFalse(AceiteDosTermos.objects.filter(user=self.ana).exists())
                self.assertBloqueado(self.client.get(CONTAS))

    def test_mudar_a_versao_vigente_bloqueia_quem_aceitou_a_anterior(self):
        self.client.post(ACEITAR, {'version': termos.VERSAO_VIGENTE}, format='json')
        self.assertEqual(self.client.get(CONTAS).status_code, 200)

        with mock.patch.object(termos, 'VERSAO_VIGENTE', '99.0'):
            self.assertBloqueado(self.client.get(CONTAS), versao='99.0')
            me = self.client.get('/api/auth/me/')
            self.assertEqual(me.data['terms']['current_version'], '99.0')
            aceite = self.client.post(ACEITAR, {'version': '99.0'}, format='json')
            self.assertEqual(aceite.status_code, 200)
            self.assertEqual(self.client.get(CONTAS).status_code, 200)

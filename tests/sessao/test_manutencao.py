"""
Modo manutenção (SESSAO-19, SESSAO-20 e SESSAO-23).

Com a manutenção ligada, quem não é administrador recebe 503 com o código
`maintenance_mode`, menos no login, na renovação, em `/auth/me/`, no logout e
em `/api/health/`. O administrador é reconhecido pelo token de acesso, pelo
papel `role == 'ADMIN'` lido do banco (AD-016), e usa o app normalmente.
Cadastro, verificação e redefinição ficam fechados. A sessão do usuário comum
continua valendo durante a manutenção.
"""
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.db import DatabaseError
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from api.cookies import NOME_DO_COOKIE
from api.models import EmailVerificationToken, GlobalSetting, PasswordResetToken, Sessao, User
from api.sessoes import criar_sessao, encerrar
from core import manutencao

FRONTEND = 'https://app.fluxar.teste'
SENHA = 'Cofre-Azul-2026'
DADOS = '/api/accounts/'
EM_MANUTENCAO = {
    'detail': 'O sistema está em manutenção programada. Por favor, tente novamente mais tarde.',
    'code': 'maintenance_mode',
}


@override_settings(FRONTEND_URL=FRONTEND, CORS_ALLOWED_ORIGINS=[])
@mock.patch('api.views.send_password_reset_email', return_value=True)
@mock.patch('api.views.send_verification_email', return_value=True)
class ModoManutencaoTests(APITestCase):

    def setUp(self):
        cache.clear()
        GlobalSetting.objects.create(key='maintenance_mode', value='true')
        manutencao.invalidar()
        self.addCleanup(manutencao.invalidar)
        self.ana = User.objects.create_user(
            email='ana@fluxar.teste', password=SENHA, name='Ana', email_verified=True,
        )
        self.access, self.refresh = criar_sessao(self.ana)

    def com_token(self, access):
        return {'HTTP_AUTHORIZATION': f'Bearer {access}'}

    def criar_admin(self, **extra):
        campos = {'is_staff': True, 'role': 'ADMIN'}
        campos.update(extra)
        return User.objects.create_user(
            email='admin@fluxar.teste', password=SENHA, name='Admin', email_verified=True, **campos,
        )

    def assertEmManutencao(self, resposta):
        self.assertEqual(resposta.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(resposta.json(), EM_MANUTENCAO)

    # SESSAO-19 ---------------------------------------------------------

    def test_usuario_comum_recebe_503_numa_rota_de_dados(self, *_):
        self.assertEmManutencao(self.client.get(DADOS, **self.com_token(self.access)))

    def test_sem_token_recebe_503_numa_rota_de_dados(self, *_):
        self.assertEmManutencao(self.client.get(DADOS))

    def test_as_cinco_rotas_liberadas_respondem_ao_usuario_comum(self, *_):
        login = self.client.post('/api/auth/login/', {'email': 'ana@fluxar.teste', 'password': SENHA}, format='json')
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertIn('access', login.data)

        me = self.client.get('/api/auth/me/', **self.com_token(self.access))
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data['email'], 'ana@fluxar.teste')

        self.client.cookies[NOME_DO_COOKIE] = self.refresh
        renovacao = self.client.post('/api/auth/refresh/', HTTP_ORIGIN=FRONTEND)
        self.assertEqual(renovacao.status_code, status.HTTP_200_OK)
        self.assertEqual(set(renovacao.data), {'access'})

        saida = self.client.post('/api/auth/logout/', HTTP_ORIGIN=FRONTEND)
        self.assertEqual(saida.status_code, status.HTTP_204_NO_CONTENT)

        saude = self.client.get('/api/health/')
        self.assertEqual(saude.status_code, status.HTTP_200_OK)
        self.assertEqual(saude.json()['status'], 'ok')

    def test_cadastro_verificacao_e_redefinicao_recebem_503(self, *_):
        pendente = User.objects.create_user(email='bia@fluxar.teste', password=SENHA, name='Bia')
        verificacao = EmailVerificationToken.objects.create(
            user=pendente, expires_at=timezone.now() + timedelta(hours=24),
        )
        redefinicao = PasswordResetToken.objects.create(
            user=self.ana, expires_at=timezone.now() + timedelta(hours=1),
        )
        nova = 'Cofre-Verde-2027'

        self.assertEmManutencao(self.client.post('/api/auth/register/', {
            'email': 'caio@fluxar.teste', 'password': SENHA, 'password_confirm': SENHA, 'name': 'Caio',
            'terms_accepted': True,
        }, format='json'))
        self.assertEmManutencao(self.client.get('/api/auth/verify-email/', {'token': str(verificacao.token)}))
        self.assertEmManutencao(self.client.post('/api/auth/reset-password/', {
            'token': str(redefinicao.token), 'new_password': nova, 'new_password_confirm': nova,
        }, format='json'))

        self.assertFalse(User.objects.filter(email='caio@fluxar.teste').exists())
        pendente.refresh_from_db()
        self.assertFalse(pendente.email_verified)
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.check_password(SENHA))

    def test_rota_que_so_comeca_como_uma_liberada_recebe_503(self, *_):
        self.assertEmManutencao(self.client.post('/api/auth/me/avatar/', **self.com_token(self.access)))
        self.assertEmManutencao(self.client.get('/api/auth/login/extra/'))

    def test_is_staff_sem_o_papel_admin_recebe_503(self, *_):
        staff = self.criar_admin(role='USER')
        access, _ = criar_sessao(staff)

        self.assertEmManutencao(self.client.get(DADOS, **self.com_token(access)))

    def test_admin_rebaixado_recebe_503_sem_perder_a_sessao(self, *_):
        admin = self.criar_admin()
        access, refresh = criar_sessao(admin)
        self.assertEqual(self.client.get(DADOS, **self.com_token(access)).status_code, status.HTTP_200_OK)

        User.objects.filter(pk=admin.pk).update(role='USER')

        self.assertEmManutencao(self.client.get(DADOS, **self.com_token(access)))
        self.assertIsNone(Sessao.objects.get(pk=RefreshToken(refresh)['sid']).encerrada_em)

    def test_renovacao_do_usuario_comum_continua_valida_durante_a_manutencao(self, *_):
        self.client.cookies[NOME_DO_COOKIE] = self.refresh

        resposta = self.client.post('/api/auth/refresh/', HTTP_ORIGIN=FRONTEND)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        sessao = Sessao.objects.get(pk=RefreshToken(self.refresh)['sid'])
        self.assertIsNone(sessao.encerrada_em)
        self.assertEqual(sessao.refresh_jti, RefreshToken(resposta.cookies[NOME_DO_COOKIE].value)['jti'])
        # Com a manutenção desligada, o token novo atende as rotas de dados
        GlobalSetting.objects.filter(key='maintenance_mode').update(value='false')
        manutencao.invalidar()
        self.assertEqual(
            self.client.get(DADOS, **self.com_token(resposta.data['access'])).status_code, status.HTTP_200_OK,
        )

    # SESSAO-20 ---------------------------------------------------------

    def test_administrador_usa_as_rotas_de_dados_e_desliga_a_manutencao(self, *_):
        admin = self.criar_admin()
        access, _ = criar_sessao(admin)

        dados = self.client.get(DADOS, **self.com_token(access))
        self.assertEqual(dados.status_code, status.HTTP_200_OK)

        painel = self.client.post(
            '/api/admin/settings/', {'maintenance_mode': False}, format='json', **self.com_token(access),
        )
        self.assertEqual(painel.status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(DADOS, **self.com_token(self.access)).status_code, status.HTTP_200_OK)

    def test_token_de_admin_de_sessao_encerrada_nao_passa_e_recebe_401(self, *_):
        # SPEC_DEVIATION (api/middleware.py): token recusado recebe 401, para a
        # interface renovar e tentar de novo, em vez de 503.
        admin = self.criar_admin()
        access, refresh = criar_sessao(admin)
        encerrar(RefreshToken(refresh)['sid'])

        resposta = self.client.get(DADOS, **self.com_token(access))

        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(resposta.json(), {'detail': 'Sessão expirada. Entre de novo.', 'code': 'session_expired'})

    def test_token_de_admin_vencido_recebe_401_para_a_interface_renovar(self, *_):
        admin = self.criar_admin()
        access, _ = criar_sessao(admin)
        vencido = AccessToken(access)
        vencido.set_exp(from_time=timezone.now() - timedelta(minutes=16))

        resposta = self.client.get(DADOS, **self.com_token(str(vencido)))

        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(resposta.json()['code'], 'token_not_valid')
        self.assertTrue(resposta.json()['detail'])

    def test_admin_do_django_continua_acessivel(self, *_):
        resposta = self.client.get('/admin/login/')

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)


class HealthCheckTests(APITestCase):
    """SESSAO-23: `/api/health/` responde 200 com ou sem manutenção."""

    def setUp(self):
        manutencao.invalidar()
        self.addCleanup(manutencao.invalidar)

    def test_responde_200_com_a_manutencao_ligada(self):
        GlobalSetting.objects.create(key='maintenance_mode', value='true')

        resposta = self.client.get('/api/health/')

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.json(), {'status': 'ok', 'maintenance': True})

    def test_responde_200_com_a_manutencao_desligada(self):
        GlobalSetting.objects.create(key='maintenance_mode', value='false')

        resposta = self.client.get('/api/health/')

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.json(), {'status': 'ok', 'maintenance': False})

    def test_falha_ao_ler_o_banco_responde_200_com_estado_desconhecido_e_registra_o_erro_sem_detalhes(self):
        erro = DatabaseError('could not connect to server at db-senha-secreta')

        with mock.patch('api.views.manutencao_ligada', side_effect=erro), \
                self.assertLogs('api.views', level='ERROR') as logs:
            resposta = self.client.get('/api/health/')

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        # Sem o banco, o estado é desconhecido: a página de manutenção não volta
        self.assertEqual(resposta.json(), {'status': 'ok', 'maintenance': None})
        self.assertEqual(len(logs.output), 1)
        self.assertIn('DatabaseError', logs.output[0])
        self.assertNotIn('db-senha-secreta', logs.output[0])

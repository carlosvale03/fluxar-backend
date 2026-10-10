"""
Log das mudanças das configurações, com o antes e o depois (ADMIN-09).
"""
from api.models import GlobalSetting, SystemLog
from api.sessoes import criar_sessao
from core import manutencao, travas

from .base import ADMIN_MASCARADO, PainelAdminTestCase

AJUSTES = '/api/admin/settings/'
PLANOS = '/api/admin/plans/'


class LogDasConfiguracoesTests(PainelAdminTestCase):

    def setUp(self):
        super().setUp()
        self.addCleanup(manutencao.invalidar)
        self.addCleanup(travas.invalidar)
        # Com a manutenção ligada, o administrador passa pelo token (SESSAO-22)
        self.client.force_authenticate(user=None)
        access, _ = criar_sessao(self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

    def assert_registro(self, log, antes, depois):
        self.assertEqual(log.admin_ref, self.admin.pk)
        self.assertEqual(log.admin_name, ADMIN_MASCARADO)
        self.assertEqual((log.antes, log.depois), (antes, depois))
        self.assertIsNotNone(log.timestamp)
        self.assert_sem_dado_pessoal(log)

    def test_ligar_e_desligar_a_manutencao_grava_o_antes_e_o_depois(self):
        self.assertEqual(self.client.post(AJUSTES, {'maintenance_mode': True}, format='json').status_code, 200)
        self.assertEqual(self.client.post(AJUSTES, {'maintenance_mode': False}, format='json').status_code, 200)

        ligar, desligar = self.logs('UPDATE_MAINTENANCE')
        self.assert_registro(ligar, False, True)
        self.assert_registro(desligar, True, False)
        self.assertEqual(GlobalSetting.objects.get(key='maintenance_mode').value, 'false')

    def test_gravar_o_mesmo_valor_da_manutencao_nao_gera_registro(self):
        GlobalSetting.objects.create(key='maintenance_mode', value='true')

        resposta = self.client.post(AJUSTES, {'key': 'maintenance_mode', 'value': True}, format='json')
        self.assertEqual(resposta.status_code, 200)
        # Sem a configuração gravada, a manutenção já está desligada
        GlobalSetting.objects.all().delete()
        resposta = self.client.post(AJUSTES, {'maintenance_mode': False}, format='json')
        self.assertEqual(resposta.status_code, 200)

        self.assertFalse(SystemLog.objects.exists())

    def test_liberacao_para_testes_grava_o_antes_e_o_depois(self):
        self.assertEqual(self.client.patch(PLANOS, {'testing_unlock': False}, format='json').status_code, 200)
        self.assertEqual(self.client.patch(PLANOS, {'testing_unlock': False}, format='json').status_code, 200)

        [log] = self.logs('UPDATE_TESTING_UNLOCK')
        self.assert_registro(log, True, False)

    def test_trava_de_recurso_grava_liberado_antes_e_bloqueado_depois(self):
        corpo = {'key': 'metas', 'plan': 'COMMON', 'enabled': False}
        self.assertEqual(self.client.patch(PLANOS, corpo, format='json').status_code, 200)
        self.assertEqual(self.client.patch(PLANOS, corpo, format='json').status_code, 200)

        [log] = self.logs('UPDATE_PLAN_LOCK')
        self.assert_registro(log, True, False)
        self.assertIn("'metas'", log.description)
        self.assertIn('COMMON', log.description)

    def test_limite_grava_o_numero_antes_e_depois_e_nulo_para_sem_limite(self):
        for limite in (2, 5, None):
            corpo = {'key': 'limite_contas', 'plan': 'PREMIUM', 'limit': limite}
            self.assertEqual(self.client.patch(PLANOS, corpo, format='json').status_code, 200)

        sem_para_dois, dois_para_cinco, cinco_para_sem = self.logs('UPDATE_PLAN_LIMIT')
        self.assert_registro(sem_para_dois, None, 2)
        self.assert_registro(dois_para_cinco, 2, 5)
        self.assert_registro(cinco_para_sem, 5, None)

    def test_registros_das_configuracoes_aparecem_no_log_com_antes_e_depois(self):
        self.client.post(AJUSTES, {'maintenance_mode': True}, format='json')

        item = self.client.get('/api/admin/logs/').data['results'][0]

        self.assertEqual(item['action'], 'UPDATE_MAINTENANCE')
        self.assertEqual((item['before'], item['after']), (False, True))
        self.assertEqual(item['admin_id'], str(self.admin.pk))
        self.assertIsNone(item['user_id'])

"""
Log de auditoria estruturado (ADMIN-10, ADMIN-11, AD-049).
"""
from unittest import mock

from api.auditoria import Acoes, registrar
from api.exclusao import excluir_definitivamente
from api.models import RegistroDeExclusao, SystemLog

from .base import ADMIN_MASCARADO, DESTRUIR, OK, USUARIO_MASCARADO, PainelAdminTestCase


class RegistrarTests(PainelAdminTestCase):

    # ADMIN-10 --------------------------------------------------------------

    def test_grava_quem_fez_sobre_quem_a_acao_e_o_antes_e_depois(self):
        registrar(self.admin, Acoes.CHANGE_PLAN, self.usuario, antes='COMMON', depois='PREMIUM')

        log = SystemLog.objects.get()
        self.assertEqual(log.action, 'CHANGE_PLAN')
        self.assertEqual(log.admin_ref, self.admin.pk)
        self.assertEqual(log.admin_name, ADMIN_MASCARADO)
        self.assertEqual(log.usuario_ref, self.usuario.pk)
        self.assertEqual(log.usuario_email, USUARIO_MASCARADO)
        self.assertEqual((log.antes, log.depois), ('COMMON', 'PREMIUM'))

    def test_nenhum_campo_tem_nome_nem_email_completo(self):
        registrar(self.admin, Acoes.RESET_PASSWORD, self.usuario, descricao='Senha redefinida pelo administrador.')
        registrar(self.admin, Acoes.UPDATE_MAINTENANCE, antes=False, depois=True)

        for log in SystemLog.objects.all():
            with self.subTest(acao=log.action):
                self.assert_sem_dado_pessoal(log)

    def test_acao_sem_usuario_afetado_fica_sem_usuario(self):
        registrar(self.admin, Acoes.UPDATE_MAINTENANCE, antes=False, depois=True)

        log = SystemLog.objects.get()
        self.assertIsNone(log.usuario_ref)
        self.assertEqual(log.usuario_email, '')
        self.assertEqual(log.admin_ref, self.admin.pk)
        self.assertEqual((log.antes, log.depois), (False, True))

    # ADMIN-11 --------------------------------------------------------------

    @mock.patch(DESTRUIR, return_value=OK)
    def test_depois_da_exclusao_o_registro_fica_so_com_o_id_interno(self, destruir):
        registrar(self.admin, Acoes.CHANGE_PLAN, self.usuario, antes='COMMON', depois='PREMIUM')
        usuario_id = self.usuario.pk

        excluir_definitivamente(self.usuario, RegistroDeExclusao.ADMIN)

        log = SystemLog.objects.get(action='CHANGE_PLAN')
        self.assertIsNone(log.user_id)
        self.assertEqual(log.usuario_ref, usuario_id)
        self.assertEqual(log.usuario_email, '')
        self.assertEqual((log.antes, log.depois), ('COMMON', 'PREMIUM'))


class ApiDoLogTests(PainelAdminTestCase):

    def test_log_global_e_do_usuario_devolvem_os_campos_novos(self):
        registrar(self.admin, Acoes.CHANGE_ROLE, self.usuario, antes='USER', depois='ADMIN', descricao='Papel alterado.')
        esperado = {
            'action': 'CHANGE_ROLE',
            'description': 'Papel alterado.',
            'admin_id': str(self.admin.pk),
            'admin_email': ADMIN_MASCARADO,
            'user_id': str(self.usuario.pk),
            'user_email': USUARIO_MASCARADO,
            'before': 'USER',
            'after': 'ADMIN',
        }

        for rota in ('/api/admin/logs/', f'/api/admin/users/{self.usuario.pk}/logs/'):
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)

                self.assertEqual(resposta.status_code, 200)
                item = resposta.data['results'][0]
                self.assertEqual({chave: item[chave] for chave in esperado}, esperado)
                self.assertEqual(set(item), set(esperado) | {'id', 'timestamp'})

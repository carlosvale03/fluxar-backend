"""
Log das ações do administrador sobre um usuário (ADMIN-08, ADMIN-11).
"""
from unittest import mock

from api.models import SystemLog, User

from .base import (
    ADMIN_MASCARADO,
    DESTRUIR,
    OK,
    SENHA,
    USUARIO_MASCARADO,
    PainelAdminTestCase,
    criar_usuario,
    textos_do_registro,
)

SENHA_NOVA = 'Nova-Senha-Forte-2026'


class LogDasAcoesTests(PainelAdminTestCase):

    def editar(self, usuario, **dados):
        return self.client.patch(
            f'/api/admin/users/{usuario.pk}/', {**dados, 'admin_password': SENHA}, format='json',
        )

    def assert_registro(self, log, usuario, antes, depois):
        self.assertEqual(log.admin_ref, self.admin.pk)
        self.assertEqual(log.admin_name, ADMIN_MASCARADO)
        self.assertEqual(log.usuario_ref, usuario.pk)
        self.assertEqual((log.antes, log.depois), (antes, depois))
        self.assertIsNotNone(log.timestamp)
        self.assert_sem_dado_pessoal(log)

    def test_mudar_o_plano_grava_o_antes_e_o_depois(self):
        resposta = self.editar(self.usuario, plan='PREMIUM')

        self.assertEqual(resposta.status_code, 200, resposta.data)
        [log] = self.logs('CHANGE_PLAN')
        self.assert_registro(log, self.usuario, 'COMMON', 'PREMIUM')
        self.assertEqual(log.usuario_email, USUARIO_MASCARADO)

    def test_mudar_plano_e_papel_juntos_grava_um_registro_por_campo(self):
        resposta = self.editar(self.usuario, plan='PREMIUM_PLUS', role='ADMIN', is_active=True)

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(
            sorted(SystemLog.objects.values_list('action', flat=True)), ['CHANGE_PLAN', 'CHANGE_ROLE'],
        )
        self.assert_registro(self.logs('CHANGE_PLAN')[0], self.usuario, 'COMMON', 'PREMIUM_PLUS')
        self.assert_registro(self.logs('CHANGE_ROLE')[0], self.usuario, 'USER', 'ADMIN')

    def test_campo_sem_mudanca_nao_gera_registro(self):
        resposta = self.editar(self.usuario, plan='COMMON', role='USER', is_active=True)

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertFalse(SystemLog.objects.exists())

    def test_desativar_e_reativar_gravam_a_mudanca_de_status(self):
        self.assertEqual(self.editar(self.usuario, is_active=False).status_code, 200)
        self.assertEqual(self.editar(self.usuario, is_active=True).status_code, 200)

        desativar, reativar = self.logs('CHANGE_STATUS')
        self.assert_registro(desativar, self.usuario, True, False)
        self.assert_registro(reativar, self.usuario, False, True)

    def test_arquivar_um_usuario_grava_a_mudanca_de_status(self):
        resposta = self.client.delete(
            f'/api/admin/users/{self.usuario.pk}/', {'admin_password': SENHA}, format='json',
        )

        self.assertEqual(resposta.status_code, 200, resposta.data)
        [log] = self.logs('CHANGE_STATUS')
        self.assert_registro(log, self.usuario, True, False)

    def test_arquivar_em_lote_grava_a_mudanca_de_status_de_cada_usuario(self):
        outro = criar_usuario('outro@teste.fluxar', 'Outro Usuario')

        resposta = self.client.delete(
            '/api/admin/users/',
            {'admin_password': SENHA, 'user_ids': [str(self.usuario.pk), str(outro.pk)]},
            format='json',
        )

        self.assertEqual(resposta.status_code, 200, resposta.data)
        logs = self.logs('CHANGE_STATUS')
        self.assertEqual({log.usuario_ref for log in logs}, {self.usuario.pk, outro.pk})
        for log in logs:
            self.assertEqual((log.antes, log.depois), (True, False))
            self.assertEqual(log.admin_ref, self.admin.pk)

    def test_redefinir_a_senha_grava_o_registro_sem_a_senha(self):
        resposta = self.client.post(
            f'/api/admin/users/{self.usuario.pk}/reset-password/',
            {'admin_password': SENHA, 'new_password': SENHA_NOVA}, format='json',
        )

        self.assertEqual(resposta.status_code, 200, resposta.data)
        [log] = self.logs('RESET_PASSWORD')
        self.assert_registro(log, self.usuario, None, None)
        texto = textos_do_registro(log)
        self.assertNotIn(SENHA_NOVA, texto)
        self.assertNotIn(SENHA, texto)

    @mock.patch(DESTRUIR, return_value=OK)
    def test_excluir_pelas_duas_rotas_deixa_o_registro_no_log_do_usuario(self, destruir):
        rotas = (
            ('/api/admin/users/{pk}/', {'admin_password': SENHA, 'permanent': True}),
            ('/api/admin/users/{pk}/hard-delete/', {'admin_password': SENHA}),
        )
        for numero, (rota, corpo) in enumerate(rotas):
            with self.subTest(rota=rota):
                vitima = criar_usuario(f'vitima{numero}@teste.fluxar', 'Vitima Excluida')
                self.editar(vitima, plan='PREMIUM')
                vitima_id = vitima.pk

                resposta = self.client.delete(rota.format(pk=vitima_id), corpo, format='json')

                self.assertEqual(resposta.status_code, 200, resposta.data)
                self.assertFalse(User.objects.filter(pk=vitima_id).exists())
                [log] = SystemLog.objects.filter(action='DELETE_ACCOUNT', usuario_ref=vitima_id)
                self.assertEqual(log.admin_ref, self.admin.pk)
                self.assertEqual(log.usuario_email, '')
                registros = self.client.get(f'/api/admin/users/{vitima_id}/logs/').data['results']
                self.assertEqual(
                    sorted(item['action'] for item in registros), ['CHANGE_PLAN', 'DELETE_ACCOUNT'],
                )
                for item in registros:
                    self.assertEqual(item['user_id'], str(vitima_id))
                    self.assertEqual(item['user_email'], '')

    @mock.patch(DESTRUIR, side_effect=ConnectionError('fora do ar'))
    def test_exclusao_que_falha_nao_deixa_registro_de_exclusao(self, destruir):
        User.objects.filter(pk=self.usuario.pk).update(avatar='avatars/avatar-do-cliente')

        resposta = self.client.delete(
            f'/api/admin/users/{self.usuario.pk}/hard-delete/', {'admin_password': SENHA}, format='json',
        )

        self.assertEqual(resposta.status_code, 503)
        self.assertFalse(SystemLog.objects.filter(action='DELETE_ACCOUNT').exists())

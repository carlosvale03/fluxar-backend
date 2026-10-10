"""
Log de auditoria sem nomes (LGPD-21, LGPD-22, LGPD-25).
"""
import importlib

import django.apps
from rest_framework.test import APITestCase

from api.models import SystemLog, User

SENHA = 'senha-de-teste-123'
NOME_DO_ADMIN = 'Admin Fulano de Tal'
ADMIN_MASCARADO = 'ad***@teste.fluxar'


def rodar_migracao():
    modulo = importlib.import_module('api.migrations.0016_log_de_auditoria_dados_antigos')
    modulo.tirar_dados_pessoais(django.apps.apps, None)


class AuditoriaTestCase(APITestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(
            email='admin.teste@teste.fluxar', password=SENHA, name=NOME_DO_ADMIN,
        )
        self.usuario = User.objects.create_user(
            email='cliente@teste.fluxar', password=SENHA, name='Cliente Beltrano', email_verified=True,
        )


class AcoesDoAdminTests(AuditoriaTestCase):

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.admin)

    def assert_registro(self, acao, descricao):
        log = SystemLog.objects.get(action=acao)
        self.assertEqual(log.description, descricao)
        self.assertEqual(log.admin_name, ADMIN_MASCARADO)
        self.assertEqual(log.usuario_ref, self.usuario.pk)
        for texto in (log.description, log.admin_name):
            self.assertNotIn('Fulano', texto)
            self.assertNotIn('Beltrano', texto)

    def test_arquivar_grava_descricao_sem_nome_e_admin_mascarado(self):
        resposta = self.client.delete(
            f'/api/admin/users/{self.usuario.pk}/', {'admin_password': SENHA}, format='json',
        )

        self.assertEqual(resposta.status_code, 200, resposta.data)
        # Arquivar é uma mudança de status, com o antes e o depois (ADMIN-08, AD-049)
        self.assert_registro('CHANGE_STATUS', 'Conta arquivada pelo administrador.')

    def test_redefinir_senha_grava_descricao_sem_nome_e_admin_mascarado(self):
        resposta = self.client.post(
            f'/api/admin/users/{self.usuario.pk}/reset-password/',
            {'admin_password': SENHA, 'new_password': 'Nova-Senha-Forte-2026'}, format='json',
        )

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assert_registro('RESET_PASSWORD', 'Senha redefinida pelo administrador.')

    def test_limpar_dados_grava_descricao_sem_nome_e_admin_mascarado(self):
        resposta = self.client.post(
            f'/api/admin/users/{self.usuario.pk}/clear-data/', {'admin_password': SENHA}, format='json',
        )

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assert_registro(
            'CLEAR_DATA', 'Todos os dados financeiros e configurações foram limpos pelo administrador.',
        )


class MigracaoDoLogTests(AuditoriaTestCase):

    def gravar_antigo(self, descricao, admin_name, user=None):
        log = SystemLog.objects.create(user=user, action='ANTIGO', description=descricao, admin_name=admin_name)
        # Como antes da correção: sem usuario_ref
        SystemLog.objects.filter(pk=log.pk).update(usuario_ref=None)
        return log

    def test_mascara_emails_das_descricoes_e_preenche_usuario_ref(self):
        log = self.gravar_antigo('Contas inativas removidas: joao@x.com, maria.silva@y.com.br', 'Sistema', self.usuario)

        rodar_migracao()

        log.refresh_from_db()
        self.assertEqual(log.description, 'Contas inativas removidas: jo***@x.com, ma***@y.com.br')
        self.assertEqual(log.usuario_ref, self.usuario.pk)
        self.assertEqual(log.admin_name, 'Sistema')

    def test_tira_o_nome_do_admin_das_descricoes_e_de_admin_name(self):
        log = self.gravar_antigo(f'Senha redefinida pelo administrador {NOME_DO_ADMIN}', NOME_DO_ADMIN, self.usuario)
        sem_dono = self.gravar_antigo('Configuração atualizada.', 'Nome Que Ninguém Tem')

        rodar_migracao()

        log.refresh_from_db()
        sem_dono.refresh_from_db()
        self.assertEqual(log.description, 'Senha redefinida pelo administrador.')
        self.assertEqual(log.admin_name, ADMIN_MASCARADO)
        self.assertEqual(sem_dono.admin_name, 'Administrador')
        self.assertIsNone(sem_dono.usuario_ref)

    def test_log_fica_com_usuario_ref_quando_a_conta_sai(self):
        log = SystemLog.objects.create(user=self.usuario, action='TESTE', description='x', admin_name='Sistema')
        id_do_usuario = self.usuario.pk

        self.usuario.delete()

        log.refresh_from_db()
        self.assertIsNone(log.user_id)
        self.assertEqual(log.usuario_ref, id_do_usuario)

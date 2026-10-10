"""
Dashboard e saúde do painel admin sem dados fixos (ADMIN-02, ADMIN-03,
ADMIN-05, ADMIN-07, AD-051).
"""
from datetime import timedelta
from unittest import mock

from django.db import DatabaseError, connection
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from api.models import User
from core.versao import ler_versao

from .base import PainelAdminTestCase, criar_usuario

URL = '/api/admin/stats/'
CHAVES_REMOVIDAS = (
    'estimated_revenue', 'conversion_rate', 'premium_users', 'status', 'db_status', 'db_latency', 'api_version',
)


class DashboardTests(PainelAdminTestCase):
    """O administrador do `setUp` é PREMIUM_PLUS e o usuário, COMMON."""

    def test_conta_cada_plano_e_a_porcentagem_de_planos_pagos_com_os_arquivados(self):
        criar_usuario('p1@teste.fluxar', 'P1', plan='PREMIUM')
        criar_usuario('p2@teste.fluxar', 'P2', plan='PREMIUM')
        criar_usuario('c1@teste.fluxar', 'C1')
        criar_usuario('c2@teste.fluxar', 'C2', is_active=False)
        criar_usuario('c3@teste.fluxar', 'C3')

        dados = self.client.get(URL).json()

        # 7 cadastros, 3 em planos pagos: 42,857...% com uma casa
        self.assertEqual(dados['total_users'], 7)
        self.assertEqual(dados['users_by_plan'], {'COMMON': 4, 'PREMIUM': 2, 'PREMIUM_PLUS': 1})
        self.assertEqual(dados['paid_users_percentage'], '42.9')

    def test_porcentagem_redonda_tambem_tem_uma_casa_decimal(self):
        dados = self.client.get(URL).json()

        self.assertEqual(dados['users_by_plan'], {'COMMON': 1, 'PREMIUM': 0, 'PREMIUM_PLUS': 1})
        self.assertEqual(dados['paid_users_percentage'], '50.0')

    def test_sem_receita_nem_valores_fixos(self):
        resposta = self.client.get(URL)

        self.assertEqual(resposta.status_code, 200)
        for chave in CHAVES_REMOVIDAS:
            self.assertNotIn(chave, resposta.json())
        texto = resposta.content.decode()
        self.assertNotIn('Operacional', texto)
        self.assertNotIn('1.2.5', texto)
        self.assertNotIn('19.90', texto)

    def test_cadastros_recentes_sao_os_cinco_ultimos_do_mais_novo_ao_mais_antigo(self):
        agora = timezone.now()
        emails = [f'r{i}@teste.fluxar' for i in range(6)]
        for i, email in enumerate(emails):
            usuario = criar_usuario(email, f'R{i}')
            User.objects.filter(pk=usuario.pk).update(created_at=agora + timedelta(minutes=i + 1))

        recentes = self.client.get(URL).json()['recent_users']

        self.assertEqual([u['email'] for u in recentes], emails[:0:-1])
        self.assertEqual(set(recentes[0]), {'id', 'name', 'email', 'created_at'})

    def test_saude_mede_o_banco_na_hora(self):
        with connection.cursor() as cursor:
            cursor.execute('SHOW server_version')
            versao_do_servidor = cursor.fetchone()[0]

        saude = self.client.get(URL).json()['health']

        self.assertEqual(saude['api'], 'ok')
        self.assertEqual(saude['database']['status'], 'ok')
        self.assertIsInstance(saude['database']['latency_ms'], int)
        self.assertGreaterEqual(saude['database']['latency_ms'], 0)
        self.assertRegex(saude['database']['version'], r'^\d+\.\d+')
        self.assertTrue(versao_do_servidor.startswith(saude['database']['version']))

    def test_banco_com_erro_vem_error_sem_latencia_nem_versao(self):
        falha = mock.MagicMock()
        falha.cursor.side_effect = DatabaseError('banco fora do ar')
        with mock.patch('api.saude.connection', falha):
            resposta = self.client.get(URL)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            resposta.json()['health'],
            {'api': 'ok', 'database': {'status': 'error', 'latency_ms': None, 'version': None}},
        )

    @override_settings(VERSAO_DO_SISTEMA='1.3.0')
    def test_versao_vem_da_configuracao_do_deploy(self):
        self.assertEqual(self.client.get(URL).json()['version'], '1.3.0')


class VersaoDoSistemaTests(SimpleTestCase):

    def test_app_version_tem_prioridade(self):
        self.assertEqual(ler_versao({'APP_VERSION': '2.0.1', 'RENDER_GIT_COMMIT': 'abcdef1234567890'}), '2.0.1')

    def test_sem_app_version_usa_os_sete_primeiros_caracteres_do_commit(self):
        self.assertEqual(ler_versao({'RENDER_GIT_COMMIT': 'abcdef1234567890'}), 'abcdef1')
        self.assertEqual(ler_versao({'APP_VERSION': '  ', 'RENDER_GIT_COMMIT': '0123456789'}), '0123456')

    def test_sem_as_duas_vale_desenvolvimento(self):
        self.assertEqual(ler_versao({}), 'desenvolvimento')
        self.assertEqual(ler_versao({'APP_VERSION': '', 'RENDER_GIT_COMMIT': ''}), 'desenvolvimento')

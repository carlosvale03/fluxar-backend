"""
Senha do administrador só nas ações sensíveis (ADMIN-17, ADMIN-18, ADMIN-19).
"""
from datetime import date
from decimal import Decimal
from unittest import mock

from api.models import SystemLog, User
from transactions.models import Transaction

from .base import DESTRUIR, OK, SENHA, SENHA_ERRADA, SENHA_INCORRETA, PainelAdminTestCase

SENHA_NOVA = 'Nova-Senha-Forte-2026'


class SenhaDoAdminTestCase(PainelAdminTestCase):

    def detalhe(self):
        return f'/api/admin/users/{self.usuario.pk}/'

    def estado(self):
        """O que as ações sensíveis mudariam no usuário."""
        usuario = User.objects.filter(pk=self.usuario.pk).first()
        if usuario is None:
            return None
        return (usuario.role, usuario.is_active, usuario.check_password(SENHA), usuario.categories.count())

    def assert_recusa_sem_senha_e_com_senha_errada(self, metodo, rota, corpo):
        antes = self.estado()
        for nome, senha in (('sem senha', None), ('senha vazia', ''), ('senha errada', SENHA_ERRADA)):
            with self.subTest(caso=nome):
                dados = dict(corpo)
                if senha is not None:
                    dados['admin_password'] = senha
                resposta = getattr(self.client, metodo)(rota, dados, format='json')

                self.assertEqual(resposta.status_code, 403)
                self.assertEqual(resposta.json(), SENHA_INCORRETA)
                self.assertEqual(self.estado(), antes)
        self.assertFalse(SystemLog.objects.exists())


class AcoesSensiveisTests(SenhaDoAdminTestCase):

    def test_mudar_o_papel_exige_a_senha(self):
        self.assert_recusa_sem_senha_e_com_senha_errada('patch', self.detalhe(), {'role': 'ADMIN'})

    def test_desativar_pela_edicao_exige_a_senha(self):
        self.assert_recusa_sem_senha_e_com_senha_errada('patch', self.detalhe(), {'is_active': False})

    def test_mudar_plano_e_papel_juntos_exige_a_senha_e_nao_muda_o_plano(self):
        self.assert_recusa_sem_senha_e_com_senha_errada('patch', self.detalhe(), {'plan': 'PREMIUM', 'role': 'ADMIN'})
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.plan, 'COMMON')

    def test_arquivar_exige_a_senha(self):
        self.assert_recusa_sem_senha_e_com_senha_errada('delete', self.detalhe(), {})

    def test_arquivar_em_lote_exige_a_senha(self):
        self.assert_recusa_sem_senha_e_com_senha_errada(
            'delete', '/api/admin/users/', {'user_ids': [str(self.usuario.pk)]},
        )

    def test_limpar_os_dados_exige_a_senha(self):
        self.assert_recusa_sem_senha_e_com_senha_errada('post', f'{self.detalhe()}clear-data/', {})

    def test_redefinir_a_senha_exige_a_senha_do_admin(self):
        self.assert_recusa_sem_senha_e_com_senha_errada(
            'post', f'{self.detalhe()}reset-password/', {'new_password': SENHA_NOVA},
        )

    @mock.patch(DESTRUIR, return_value=OK)
    def test_excluir_pelas_duas_rotas_exige_a_senha(self, destruir):
        self.assert_recusa_sem_senha_e_com_senha_errada('delete', self.detalhe(), {'permanent': True})
        self.assert_recusa_sem_senha_e_com_senha_errada('delete', f'{self.detalhe()}hard-delete/', {})
        self.assertTrue(User.objects.filter(pk=self.usuario.pk).exists())

    def test_com_a_senha_certa_as_acoes_sensiveis_seguem(self):
        resposta = self.client.patch(self.detalhe(), {'role': 'ADMIN', 'admin_password': SENHA}, format='json')
        self.assertEqual(resposta.status_code, 200, resposta.data)

        resposta = self.client.patch(self.detalhe(), {'is_active': False, 'admin_password': SENHA}, format='json')
        self.assertEqual(resposta.status_code, 200, resposta.data)

        self.usuario.refresh_from_db()
        self.assertEqual((self.usuario.role, self.usuario.is_active), ('ADMIN', False))


class AcoesSemSenhaTests(SenhaDoAdminTestCase):

    def test_mudar_so_o_plano_dispensa_a_senha(self):
        resposta = self.client.patch(self.detalhe(), {'plan': 'PREMIUM'}, format='json')

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(resposta.data['plan'], 'PREMIUM')
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.plan, 'PREMIUM')

    def test_reativar_a_conta_dispensa_a_senha(self):
        User.objects.filter(pk=self.usuario.pk).update(is_active=False)

        resposta = self.client.patch(self.detalhe(), {'is_active': True}, format='json')

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_active)

    def test_enviar_o_mesmo_papel_e_o_status_ativo_com_o_plano_dispensa_a_senha(self):
        resposta = self.client.patch(
            self.detalhe(), {'plan': 'PREMIUM_PLUS', 'role': 'USER', 'is_active': True}, format='json',
        )

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.plan, 'PREMIUM_PLUS')

    def test_nome_e_preferencias_enviados_pelo_painel_sao_ignorados(self):
        resposta = self.client.patch(self.detalhe(), {
            'plan': 'PREMIUM',
            'name': 'Nome Trocado',
            'cpf': '52998224725',
            'phone_number': '86999990000',
            'preferences': {'theme': 'dark', 'currency': 'USD', 'notifications': {'email': False}},
            'theme_preference': 'dark',
            'currency': 'USD',
            'language': 'en-US',
            'notification_settings': {'email': False},
        }, format='json')

        self.assertEqual(resposta.status_code, 200, resposta.data)
        usuario = User.objects.get(pk=self.usuario.pk)
        self.assertEqual(usuario.plan, 'PREMIUM')
        self.assertEqual(usuario.name, self.usuario.name)
        self.assertIsNone(usuario.cpf)
        self.assertIsNone(usuario.phone_number)
        self.assertEqual(
            (usuario.theme_preference, usuario.currency, usuario.language, usuario.notification_settings),
            (self.usuario.theme_preference, self.usuario.currency, self.usuario.language,
             self.usuario.notification_settings),
        )

    def test_limpar_com_a_senha_certa_segue(self):
        Transaction.objects.create(
            user=self.usuario, type='EXPENSE', status='COMPLETED', account=self.usuario.accounts.get(),
            description='Padaria', amount=Decimal('10.00'), date=date(2026, 10, 1),
        )

        resposta = self.client.post(f'{self.detalhe()}clear-data/', {'admin_password': SENHA}, format='json')

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertFalse(Transaction.objects.filter(user=self.usuario).exists())

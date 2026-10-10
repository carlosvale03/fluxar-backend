"""
Limpeza dos dados de um usuário, tudo ou nada (ADMIN-21 a ADMIN-27, AD-050).

O Cloudinary é simulado. A concorrência usa `TransactionTestCase` e duas
threads, cada uma com a própria conexão.
"""
import threading
import time
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.db import connection
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from accounts.models import Account, CreditCardInvoice
from api.exclusao import MODELOS_DO_USUARIO
from api.limpeza import MANTIDOS_NA_LIMPEZA, modelos_da_limpeza
from api.models import AceiteDosTermos, DecisaoDeConsentimento, Sessao, SystemLog, User
from goals.models import GoalDeposit
from tests.lgpd.test_exclusao_definitiva import AVATAR, IMAGEM_DA_META, criar_conta_completa, linhas_do_usuario
from transactions import padrao
from transactions.models import Category, Transaction

from .base import DESTRUIR, OK, SENHA, PainelAdminTestCase, criar_admin
from .test_padrao_do_cadastro import CATEGORIAS_PADRAO, categorias, contas

LIMPEZA_FALHOU = {
    'detail': 'Não foi possível limpar os dados agora. Nada foi apagado; tente de novo mais tarde.',
    'code': 'clear_failed',
}
TRANSACOES_EXTRAS = 300


def criar_usuario_com_dados(email='ana@teste.fluxar'):
    """Um usuário com dados em todas as partes do app e mais 300 transações."""
    usuario = criar_conta_completa(email)
    User.objects.filter(pk=usuario.pk).update(email_verified=True, plan='PREMIUM')
    usuario.refresh_from_db()
    conta = Account.objects.get(user=usuario, name='Corrente')
    inicio = date(2026, 6, 1)
    Transaction.objects.bulk_create([
        Transaction(
            user=usuario, type='EXPENSE', status='COMPLETED', account=conta,
            description=f'Compra {numero}', amount=Decimal('1.00'),
            date=inicio + timedelta(days=numero % 90), report_date=inicio + timedelta(days=numero % 90),
        )
        for numero in range(TRANSACOES_EXTRAS)
    ])
    return usuario


def rota(usuario):
    return f'/api/admin/users/{usuario.pk}/clear-data/'


@mock.patch(DESTRUIR, return_value=OK)
class LimpezaTests(PainelAdminTestCase):

    def setUp(self):
        super().setUp()
        self.ana = criar_usuario_com_dados()
        self.bia = criar_usuario_com_dados('bia@teste.fluxar')

    def limpar(self, usuario=None):
        return self.client.post(rota(usuario or self.ana), {'admin_password': SENHA}, format='json')

    def assert_cadastro_novo(self, usuario):
        restantes = {rotulo: n for rotulo, n in linhas_do_usuario(usuario.pk).items() if n}
        esperados = {rotulo: n for rotulo, n in restantes.items() if rotulo in MANTIDOS_NA_LIMPEZA}
        self.assertEqual(
            restantes,
            {
                **esperados, 'transactions.Category': len(CATEGORIAS_PADRAO), 'accounts.Account': 1,
                # Essencial e Dispensável, recriadas pelo padrão (CLASSE-01)
                'transactions.ClasseDeDespesa': 2,
            },
        )
        self.assertEqual(set(categorias(usuario)), CATEGORIAS_PADRAO)
        self.assertEqual(contas(usuario), [('Carteira', 'WALLET', 0, True)])
        self.assertFalse(GoalDeposit.objects.filter(goal__user=usuario).exists())
        self.assertFalse(CreditCardInvoice.objects.filter(card__user=usuario).exists())

    # ADMIN-21, ADMIN-22 ----------------------------------------------------

    def test_apaga_tudo_e_deixa_so_o_padrao_de_um_cadastro_novo(self, destruir):
        self.assertGreater(Transaction.objects.filter(user=self.ana).count(), TRANSACOES_EXTRAS)
        antes_da_bia = linhas_do_usuario(self.bia.pk)

        resposta = self.limpar()

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(resposta.data['message'], 'Dados do usuário limpos com sucesso.')
        self.assert_cadastro_novo(self.ana)
        # Os dados de outro usuário continuam
        self.assertEqual(linhas_do_usuario(self.bia.pk), antes_da_bia)
        [log] = SystemLog.objects.filter(action='CLEAR_DATA')
        self.assertEqual((log.usuario_ref, log.admin_ref), (self.ana.pk, self.admin.pk))

    def test_responde_com_as_estatisticas_novas_do_usuario(self, destruir):
        resposta = self.limpar()

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(resposta.data['financial_stats'], {
            'total_balance': '0.00',
            'avg_income_value': '0.00',
            'avg_expense_value': '0.00',
            'income_count_per_day': 0.0,
            'expense_count_per_day': 0.0,
            'last_transaction_date': None,
        })

    def test_limpar_duas_vezes_termina_com_um_unico_padrao(self, destruir):
        self.assertEqual(self.limpar().status_code, 200)
        self.assertEqual(self.limpar().status_code, 200)

        self.assert_cadastro_novo(self.ana)

    # ADMIN-23 --------------------------------------------------------------

    def test_mantem_login_senha_perfil_plano_e_papel(self, destruir):
        antes = User.objects.get(pk=self.ana.pk)
        sessoes = Sessao.objects.filter(user=self.ana).count()

        self.assertEqual(self.limpar().status_code, 200)

        depois = User.objects.get(pk=self.ana.pk)
        campos = ('email', 'password', 'name', 'cpf', 'plan', 'role', 'is_active', 'email_verified', 'avatar')
        self.assertEqual([str(getattr(depois, c)) for c in campos], [str(getattr(antes, c)) for c in campos])
        self.assertEqual(Sessao.objects.filter(user=self.ana).count(), sessoes)
        self.assertTrue(AceiteDosTermos.objects.filter(user=self.ana).exists())
        self.assertTrue(DecisaoDeConsentimento.objects.filter(user=self.ana).exists())

        self.client.force_authenticate(user=None)
        login = self.client.post('/api/auth/login/', {'email': 'ana@teste.fluxar', 'password': SENHA}, format='json')
        self.assertEqual(login.status_code, 200, login.data)
        self.assertIn('access', login.data)

    # ADMIN-24 --------------------------------------------------------------

    def test_remove_as_imagens_das_metas_no_cloudinary_e_mantem_o_avatar(self, destruir):
        self.assertEqual(self.limpar().status_code, 200)

        removidas = [chamada.args[0] for chamada in destruir.call_args_list]
        self.assertEqual(removidas, [IMAGEM_DA_META])
        self.assertNotIn(AVATAR, removidas)

    def test_com_o_cloudinary_falhando_responde_503_e_nada_e_apagado(self, destruir):
        antes = linhas_do_usuario(self.ana.pk)
        for falha in (ConnectionError('fora do ar'), None):
            with self.subTest(falha=falha):
                destruir.side_effect = falha
                destruir.return_value = {'result': 'error'}

                resposta = self.limpar()

                self.assertEqual(resposta.status_code, 503)
                self.assertEqual(resposta.json(), LIMPEZA_FALHOU)
                self.assertEqual(linhas_do_usuario(self.ana.pk), antes)
        self.assertFalse(SystemLog.objects.filter(action='CLEAR_DATA').exists())

    # ADMIN-25 --------------------------------------------------------------

    def test_falha_no_meio_mantem_os_dados_como_estavam(self, destruir):
        antes = linhas_do_usuario(self.ana.pk)
        self.client.raise_request_exception = False

        with mock.patch('api.limpeza.criar_padrao_do_cadastro', side_effect=RuntimeError('falha forçada')):
            resposta = self.limpar()

        self.assertEqual(resposta.status_code, 500)
        self.assertEqual(linhas_do_usuario(self.ana.pk), antes)
        self.assertGreater(Transaction.objects.filter(user=self.ana).count(), TRANSACOES_EXTRAS)
        self.assertFalse(SystemLog.objects.filter(action='CLEAR_DATA').exists())

    def test_falha_ao_gravar_o_log_mantem_os_dados_como_estavam(self, destruir):
        """O CLEAR_DATA é gravado na mesma transação: sem o registro, nada é apagado (ADMIN-08)."""
        antes = linhas_do_usuario(self.ana.pk)
        self.client.raise_request_exception = False

        with mock.patch('api.limpeza.registrar', side_effect=RuntimeError('log fora do ar')) as registrar:
            resposta = self.limpar()

        registrar.assert_called_once()
        self.assertEqual(resposta.status_code, 500)
        self.assertEqual(linhas_do_usuario(self.ana.pk), antes)
        self.assertGreater(Transaction.objects.filter(user=self.ana).count(), TRANSACOES_EXTRAS)
        self.assertFalse(SystemLog.objects.filter(action='CLEAR_DATA').exists())

    # ADMIN-27 --------------------------------------------------------------

    def test_administrador_limpando_os_proprios_dados_recebe_400(self, destruir):
        Transaction.objects.create(
            user=self.admin, type='EXPENSE', status='COMPLETED', account=Account.objects.get(user=self.admin),
            description='Café', amount=Decimal('5.00'), date=date(2026, 10, 1),
        )
        antes = linhas_do_usuario(self.admin.pk)

        resposta = self.limpar(self.admin)

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.json(), {
            'detail': 'Você não pode limpar os próprios dados pelo painel.', 'code': 'own_account',
        })
        self.assertEqual(linhas_do_usuario(self.admin.pk), antes)


class ModelosDaLimpezaTests(PainelAdminTestCase):

    def test_todo_modelo_do_usuario_e_apagado_ou_mantido(self):
        """Um modelo novo em `MODELOS_DO_USUARIO` entra na limpeza sem outra mudança (AD-050)."""
        apagados = {modelo._meta.label for modelo, _ in modelos_da_limpeza()}
        todos = {rotulo for rotulo, _ in MODELOS_DO_USUARIO}

        self.assertEqual(apagados | set(MANTIDOS_NA_LIMPEZA), todos)
        self.assertEqual(apagados & set(MANTIDOS_NA_LIMPEZA), set())
        self.assertEqual(
            set(MANTIDOS_NA_LIMPEZA),
            {'api.Sessao', 'api.EmailVerificationToken', 'api.PasswordResetToken', 'api.AceiteDosTermos',
             'api.DecisaoDeConsentimento', 'admin.LogEntry'},
        )


@mock.patch(DESTRUIR, return_value=OK)
class LimpezasSimultaneasTests(TransactionTestCase):

    def setUp(self):
        self.admin = criar_admin()
        self.ana = criar_usuario_com_dados()

    def limpar_em_paralelo(self, usuario):
        """Duas limpezas do mesmo usuário, que partem juntas e se sobrepõem."""
        barreira = threading.Barrier(2, timeout=20)
        respostas, erros = [], []
        criar_de_verdade = padrao.criar_padrao_do_cadastro

        def criar_devagar(alvo):
            # Alarga a janela em que as duas limpezas se sobrepõem
            time.sleep(0.5)
            criar_de_verdade(alvo)

        def trabalho():
            try:
                cliente = APIClient()
                cliente.force_authenticate(user=self.admin)
                barreira.wait()
                respostas.append(cliente.post(rota(usuario), {'admin_password': SENHA}, format='json'))
            except Exception as erro:  # noqa: BLE001 - repassado ao teste abaixo
                erros.append(erro)
            finally:
                connection.close()

        with mock.patch('api.limpeza.criar_padrao_do_cadastro', side_effect=criar_devagar):
            threads = [threading.Thread(target=trabalho) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=60)

        self.assertFalse(any(t.is_alive() for t in threads), 'thread presa')
        self.assertEqual(erros, [])
        self.assertEqual([r.status_code for r in respostas], [200, 200])

    def assert_um_unico_padrao(self, usuario):
        self.assertEqual(Category.objects.filter(user=usuario).count(), len(CATEGORIAS_PADRAO))
        self.assertEqual(set(categorias(usuario)), CATEGORIAS_PADRAO)
        self.assertEqual(contas(usuario), [('Carteira', 'WALLET', 0, True)])
        self.assertFalse(Transaction.objects.filter(user=usuario).exists())

    def test_duas_limpezas_simultaneas_terminam_com_um_unico_padrao(self, destruir):
        self.limpar_em_paralelo(self.ana)

        self.assert_um_unico_padrao(self.ana)

    def test_duas_limpezas_simultaneas_de_um_usuario_sem_dados_nao_duplicam_o_padrao(self, destruir):
        vazio = User.objects.create_user(email='vazio@teste.fluxar', password=SENHA, name='Vazio')
        Category.objects.filter(user=vazio).delete()
        Account.objects.filter(user=vazio).delete()

        self.limpar_em_paralelo(vazio)

        self.assert_um_unico_padrao(vazio)

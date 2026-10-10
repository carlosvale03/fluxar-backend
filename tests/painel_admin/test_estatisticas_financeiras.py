"""
Estatísticas financeiras do usuário no painel admin pelas regras dos
relatórios (ADMIN-29, AD-029, AD-046, SALDO-31).

Os números do painel são comparados com o dashboard do próprio usuário nos
mesmos 30 dias (`days=30`), com hoje em 20/03/2026 em Brasília.
"""
from datetime import date
from decimal import Decimal

from accounts.models import Account
from api.models import User
from tests.relatorios.base import RelatoriosTestCase, agora_em

CHAVES = {
    'total_balance', 'avg_income_value', 'avg_expense_value',
    'income_count_per_day', 'expense_count_per_day', 'last_transaction_date',
}


def por_dia(valor):
    """O total dos 30 dias dividido por 30, em centavos."""
    return str((Decimal(valor) / 30).quantize(Decimal('0.01')))


class EstatisticasFinanceirasTests(RelatoriosTestCase):

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(
            email='estatisticas.admin@teste.fluxar', password='senha-de-teste-123',
            name='Admin', role='ADMIN', plan='PREMIUM_PLUS',
        )

    def resumo_do_usuario(self):
        self.client.force_authenticate(user=self.a.usuario)
        with agora_em(2026, 3, 20):
            resposta = self.client.get('/api/reports/dashboard/', {'days': 30})
        self.assertEqual(resposta.status_code, 200, resposta.data)
        return resposta.data['summary']

    def estatisticas(self):
        self.client.force_authenticate(user=self.admin)
        with agora_em(2026, 3, 20):
            resposta = self.client.get(f'/api/admin/users/{self.a.usuario.pk}/financial-stats/')
        self.assertEqual(resposta.status_code, 200, resposta.data)
        return resposta.json()

    def test_receitas_e_despesas_batem_com_o_relatorio_do_usuario(self):
        self.lancar('INCOME', '5000.00', date(2026, 3, 5))
        self.lancar('INCOME', '300.00', date(2026, 3, 6), status='PENDING')
        self.lancar('EXPENSE', '100.00', date(2026, 3, 5))
        self.lancar('EXPENSE', '50.00', date(2026, 3, 12), status='PENDING')
        self.transferir(self.conta('SAVINGS'), self.a.conta, '200.00', date(2026, 3, 7))
        # Fora dos 30 dias
        self.lancar('EXPENSE', '999.00', date(2026, 2, 10))
        # Compra de 10/03 que vence em 15/04: conta na data da compra
        self.comprar(self.cartao(5, 15), '80.00', date(2026, 3, 10))

        resumo = self.resumo_do_usuario()
        estatisticas = self.estatisticas()

        self.assertEqual(set(estatisticas), CHAVES)
        self.assertEqual((resumo['monthly_income'], resumo['monthly_expense']), ('5000.00', '180.00'))
        self.assertEqual(estatisticas['avg_income_value'], por_dia(resumo['monthly_income']))
        self.assertEqual(estatisticas['avg_expense_value'], por_dia(resumo['monthly_expense']))
        self.assertEqual(estatisticas['avg_expense_value'], '6.00')
        self.assertAlmostEqual(estatisticas['income_count_per_day'], 1 / 30)
        self.assertAlmostEqual(estatisticas['expense_count_per_day'], 2 / 30)

    def test_ajuste_de_saldo_fica_fora(self):
        self.lancar('INCOME', '250.25', date(2026, 3, 8), description='Ajuste de saldo', is_balance_adjustment=True)
        self.lancar('EXPENSE', '90.00', date(2026, 3, 8), description='Ajuste de saldo', is_balance_adjustment=True)
        self.lancar('INCOME', '300.00', date(2026, 3, 8))

        estatisticas = self.estatisticas()

        self.assertEqual((estatisticas['avg_income_value'], estatisticas['avg_expense_value']), ('10.00', '0.00'))
        self.assertAlmostEqual(estatisticas['income_count_per_day'], 1 / 30)
        self.assertEqual(estatisticas['expense_count_per_day'], 0)

    def test_transacao_de_conta_excluida_fica_fora_e_o_saldo_soma_so_as_ativas(self):
        ativa_antes = Decimal(self.estatisticas()['total_balance'])
        antiga = self.conta('CHECKING', '700.00', nome='Antiga')
        self.lancar('EXPENSE', '120.00', date(2026, 3, 9), conta=antiga)
        self.lancar('INCOME', '600.00', date(2026, 3, 9), conta=antiga)
        Account.objects.filter(pk=antiga.pk).update(is_active=False)
        # A compra no cartão da conta ativa continua contando
        self.comprar(self.cartao(5, 15), '30.00', date(2026, 3, 10))

        estatisticas = self.estatisticas()

        self.assertEqual(estatisticas['avg_income_value'], '0.00')
        self.assertEqual(estatisticas['avg_expense_value'], '1.00')
        self.assertAlmostEqual(estatisticas['expense_count_per_day'], 1 / 30)
        self.assertEqual(Decimal(estatisticas['total_balance']), ativa_antes)

    def test_compra_parcelada_entra_pela_data_do_relatorio(self):
        # 3 x 100,00 em 25/02: a 1ª conta em 25/02 (dentro dos 30 dias) e a
        # 2ª em 25/03 (depois de hoje), qualquer que seja o vencimento
        self.comprar(self.cartao(5, 15), '300.00', date(2026, 2, 25), parcelas=3)

        resumo = self.resumo_do_usuario()
        estatisticas = self.estatisticas()

        self.assertEqual(resumo['monthly_expense'], '100.00')
        self.assertEqual(estatisticas['avg_expense_value'], por_dia('100.00'))
        self.assertAlmostEqual(estatisticas['expense_count_per_day'], 1 / 30)

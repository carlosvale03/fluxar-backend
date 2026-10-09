"""
Gasto dos orçamentos pelas mesmas despesas dos relatórios (T6, REL-06,
REL-19).
"""
from datetime import date
from decimal import Decimal

from budgets.models import Budget
from budgets.services import BudgetService
from transactions.models import Category

from .base import RelatoriosTestCase


class GastoDoOrcamentoTests(RelatoriosTestCase):

    def setUp(self):
        super().setUp()
        self.cartao_ = self.cartao(5, 15)
        self.comida = Category.objects.create(user=self.a.usuario, name='Comida', type='EXPENSE')

    def orcamento(self, mes, limite='1000.00', categoria=None):
        return Budget.objects.create(
            user=self.a.usuario, category=categoria or self.comida, month=mes, year=2026,
            amount_limit=Decimal(limite),
        )

    def gasto(self, orcamento):
        return BudgetService.get_budget_usage(orcamento)['total_spent']

    def test_compra_parcelada_conta_so_a_parcela_de_cada_mes(self):
        self.comprar(self.cartao_, '300.00', date(2026, 1, 31), parcelas=3, categoria=self.comida)

        self.assertEqual(
            [self.gasto(self.orcamento(mes)) for mes in (1, 2, 3, 4)],
            [Decimal('100.00'), Decimal('100.00'), Decimal('100.00'), Decimal('0.00')],
        )

    def test_pendente_e_ajuste_ficam_fora_e_a_subcategoria_entra(self):
        mercado = Category.objects.create(
            user=self.a.usuario, name='Mercado', type='EXPENSE', parent=self.comida,
        )
        self.lancar('EXPENSE', '40.00', date(2026, 3, 3), status='PENDING', category=self.comida)
        self.lancar('EXPENSE', '20.00', date(2026, 3, 4), category=mercado)
        self.lancar('EXPENSE', '15.00', date(2026, 3, 4), category=self.comida)
        # Outra categoria e ajuste de saldo ficam fora
        self.lancar('EXPENSE', '500.00', date(2026, 3, 5), category=self.a.despesa)
        self.lancar('EXPENSE', '7.00', date(2026, 3, 6), category=self.comida, is_balance_adjustment=True)

        self.assertEqual(self.gasto(self.orcamento(3)), Decimal('35.00'))

    def test_compra_no_cartao_com_fatura_aberta_conta_no_mes_da_compra(self):
        # 10/03 depois do fechamento: fatura de 15/04, ainda aberta
        self.comprar(self.cartao_, '80.00', date(2026, 3, 10), categoria=self.comida)

        self.assertEqual(self.gasto(self.orcamento(3)), Decimal('80.00'))
        self.assertEqual(self.gasto(self.orcamento(4)), Decimal('0.00'))


class MesmoEstouroNoScoreENoDashboardTests(RelatoriosTestCase):

    def test_score_e_dashboard_contam_o_mesmo_orcamento_estourado(self):
        comida = Category.objects.create(user=self.a.usuario, name='Comida', type='EXPENSE')
        lazer = Category.objects.create(user=self.a.usuario, name='Lazer', type='EXPENSE')
        for categoria in (comida, lazer):
            Budget.objects.create(
                user=self.a.usuario, category=categoria, month=3, year=2026, amount_limit=Decimal('100.00'),
            )
        cartao = self.cartao(5, 15)
        # Compra de 10/03 na fatura de abril: estoura o orçamento de março
        self.comprar(cartao, '120.00', date(2026, 3, 10), categoria=comida)
        self.comprar(cartao, '30.00', date(2026, 3, 11), categoria=lazer)

        resp = self.client.get('/api/reports/dashboard/', {'month': 3, 'year': 2026})

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['budgets'], {'ok_count': 1, 'near_limit_count': 0, 'over_limit_count': 1})
        # Sem receita e sem liquidez, o score é só a parte dos orçamentos
        self.assertEqual(resp.data['summary']['financial_score'], 15)

        lista = self.client.get('/api/budgets/', {'month': 3, 'year': 2026})
        self.assertEqual(lista.status_code, 200, lista.data)
        status = {str(item['category']): item['status'] for item in lista.data}
        self.assertEqual(status, {str(comida.pk): 'OVER_LIMIT', str(lazer.pk): 'OK'})

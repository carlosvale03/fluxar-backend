"""
Saúde financeira e score no dashboard (T5, REL-14, REL-19 a REL-22).

Nos testes do score, a conta corrente fica sem saldo e as despesas são
compras no cartão pendentes: sem receita e sem liquidez, o score é só a
parte dos orçamentos.
"""
from datetime import date
from decimal import Decimal

from accounts.models import Account
from budgets.models import Budget
from goals.models import Goal
from goals.services import GoalService
from transactions.models import Category

from .base import RelatoriosTestCase

URL = '/api/reports/dashboard/'
MARCO = {'month': 3, 'year': 2026}


class SaudeTestCase(RelatoriosTestCase):

    def resumo(self):
        resp = self.client.get(URL, MARCO)
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data['summary']


class ScoreDeOrcamentosTests(SaudeTestCase):

    def setUp(self):
        super().setUp()
        self.cartao_ = self.cartao(5, 15)

    def orcamentos(self, quantidade, gasto):
        """`quantidade` orçamentos de R$ 100,00 em março, cada um com `gasto` em compras no cartão."""
        for n in range(quantidade):
            categoria = Category.objects.create(user=self.a.usuario, name=f'Categoria {n}', type='EXPENSE')
            Budget.objects.create(
                user=self.a.usuario, category=categoria, month=3, year=2026, amount_limit=Decimal('100.00'),
            )
            self.comprar(self.cartao_, gasto, date(2026, 3, 2), categoria=categoria)

    def test_quatro_orcamentos_dentro_do_limite_valem_20_pontos(self):
        self.orcamentos(4, '60.00')

        self.assertEqual(self.resumo()['financial_score'], 20)

    def test_um_orcamento_estourado_tira_5_pontos(self):
        self.orcamentos(4, '60.00')
        self.orcamentos(1, '130.00')

        self.assertEqual(self.resumo()['financial_score'], 15)

    def test_cinco_orcamentos_estourados_zeram_a_parte(self):
        self.orcamentos(5, '130.00')

        self.assertEqual(self.resumo()['financial_score'], 0)


class TaxaDePoupancaTests(SaudeTestCase):

    def setUp(self):
        super().setUp()
        cofrinho = self.conta('PIGGY_BANK')
        self.investimento = self.conta('INVESTMENT')
        self.meta = Goal.objects.create(
            user=self.a.usuario, name='Viagem', target_amount=Decimal('5000.00'), account=cofrinho,
        )

    def guardar_700(self):
        GoalService.aportar(self.meta, Decimal('500.00'), date(2026, 3, 6), account=self.a.conta)
        self.transferir(self.a.conta, self.investimento, '300.00', date(2026, 3, 7))
        GoalService.resgatar(self.meta, Decimal('100.00'), date(2026, 3, 20), account=self.a.conta)

    def test_taxa_e_o_guardado_sobre_as_receitas(self):
        self.lancar('INCOME', '5000.00', date(2026, 3, 5))
        self.guardar_700()

        resumo = self.resumo()

        self.assertEqual(resumo['saved_this_month'], '700.00')
        self.assertEqual(resumo['savings_rate'], 14.0)

    def test_sem_receitas_a_taxa_e_indisponivel(self):
        Account.objects.filter(pk=self.a.conta.pk).update(initial_balance=Decimal('1000.00'), balance=Decimal('1000.00'))
        self.a.conta.refresh_from_db()
        self.guardar_700()
        # Receita de outro mês não entra
        self.lancar('INCOME', '5000.00', date(2026, 2, 5))

        resumo = self.resumo()

        self.assertEqual(resumo['saved_this_month'], '700.00')
        self.assertIsNone(resumo['savings_rate'])


class LiquidezTests(SaudeTestCase):

    def test_liquidez_nao_soma_cofrinhos_nem_investimentos(self):
        Account.objects.filter(pk=self.a.conta.pk).update(initial_balance=Decimal('3000.00'), balance=Decimal('3000.00'))
        self.conta('PIGGY_BANK', '800.00')
        self.conta('INVESTMENT', '2000.00')
        self.comprar(self.cartao(5, 15), '500.00', date(2026, 3, 2))

        resumo = self.resumo()

        self.assertEqual(resumo['total_liquid_balance'], '3000.00')
        self.assertEqual(resumo['liquidity_ratio'], 6.0)

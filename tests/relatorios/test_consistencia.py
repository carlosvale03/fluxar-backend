"""
Mesmos números em todas as telas (T10, REL-01, REL-06, REL-13, REL-20): o
cenário do Independent Test de cada história, conferido no dashboard, na
saúde financeira, no calendário, na pizza, na comparação mensal, nos
relatórios avançados e no orçamento.
"""
from datetime import date
from decimal import Decimal

from accounts.models import Account
from accounts.saldo import recalcular
from budgets.models import Budget
from goals.models import Goal
from goals.services import GoalService

from .base import RelatoriosTestCase, agora_em


class ConsistenciaTests(RelatoriosTestCase):

    def obter(self, url, parametros=None):
        with agora_em(2026, 3, 20):
            resp = self.client.get(url, parametros or {})
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data

    def test_despesas_e_a_pagar_batem_entre_as_rotas_e_o_orcamento(self):
        orcamento = Budget.objects.create(
            user=self.a.usuario, category=self.a.despesa, month=3, year=2026, amount_limit=Decimal('1000.00'),
        )
        self.lancar('EXPENSE', '100.00', date(2026, 3, 5), category=self.a.despesa)
        self.lancar('EXPENSE', '50.00', date(2026, 3, 12), status='PENDING', category=self.a.despesa)
        # 10/03 depois do fechamento de 05/03: fatura de 15/04, ainda aberta
        self.comprar(self.cartao(5, 15), '80.00', date(2026, 3, 10), categoria=self.a.despesa)

        resumo = self.obter('/api/reports/dashboard/')['summary']
        calendario = self.obter('/api/reports/calendar/')
        pizza = self.obter('/api/reports/charts/simple/')['expense_by_category']
        comparacao = self.obter('/api/reports/charts/monthly-comparison/', {'months': 1})
        avancados = self.obter('/api/reports/charts/advanced/')
        gasto_do_orcamento = self.obter(f'/api/budgets/{orcamento.pk}/')['total_spent']

        self.assertEqual(
            {
                'dashboard': resumo['monthly_expense'],
                'calendário': calendario['total_expense'],
                'pizza': dinheiro_somado(fatia['amount'] for fatia in pizza),
                'comparação': comparacao[-1]['expense'],
                'avançados': avancados['fixed_vs_variable']['total'],
                'orçamento': gasto_do_orcamento,
            },
            dict.fromkeys(('dashboard', 'calendário', 'pizza', 'comparação', 'avançados', 'orçamento'), '180.00'),
        )
        self.assertEqual(resumo['payable'], '50.00')

    def test_patrimonio_e_dinheiro_guardado_batem_entre_as_rotas(self):
        Account.objects.filter(pk=self.a.conta.pk).update(initial_balance=Decimal('3000.00'))
        recalcular(self.a.conta.pk)
        self.a.conta.refresh_from_db()
        cofrinho = self.conta('PIGGY_BANK', '800.00')
        investimento = self.conta('INVESTMENT', '2000.00')
        self.comprar(self.cartao(5, 15), '450.00', date(2026, 3, 10))
        meta = Goal.objects.create(
            user=self.a.usuario, name='Viagem', target_amount=Decimal('5000.00'), account=cofrinho,
        )
        self.lancar('INCOME', '5000.00', date(2026, 3, 5))
        GoalService.aportar(meta, Decimal('500.00'), date(2026, 3, 6), account=self.a.conta)
        self.transferir(self.a.conta, investimento, '300.00', date(2026, 3, 7))
        GoalService.resgatar(meta, Decimal('100.00'), date(2026, 3, 8), account=self.a.conta)

        resumo = self.obter('/api/reports/dashboard/')['summary']
        avancados = self.obter('/api/reports/charts/advanced/')

        # Corrente 7.300 + cofrinho 1.200 + investimento 2.300 - cartão 450
        self.assertEqual(resumo['net_worth'], '10350.00')
        self.assertEqual(resumo['net_worth_breakdown'], {
            'available': '7300.00', 'reserves': '1200.00', 'investments': '2300.00', 'open_invoices': '450.00',
        })
        self.assertEqual(avancados['net_worth_evolution'][-1], {'date': '2026-03-31', 'balance': '10350.00'})
        self.assertEqual(resumo['total_investment_balance'], avancados['investment_analysis']['total_invested'])
        self.assertEqual((resumo['saved_this_month'], resumo['savings_rate']), ('700.00', 14.0))
        self.assertEqual(avancados['investment_analysis']['monthly_history'][-1]['contribution'], '300.00')


def dinheiro_somado(valores):
    return f"{sum((Decimal(valor) for valor in valores), Decimal('0.00')):.2f}"

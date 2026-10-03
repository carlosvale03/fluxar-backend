"""
Dinheiro como texto com duas casas em todas as rotas, inclusive nos
relatórios; percentuais e razões continuam números (CONTRATO-16, AD-041).
"""
import re
from datetime import date, timedelta
from decimal import Decimal

from django.test import SimpleTestCase

from accounts.models import Account, CreditCard, CreditCardInvoice
from api.models import User
from budgets.models import Budget
from core.valores import dinheiro
from goals.models import Goal
from reports.models import FocusedMonitorItem
from transactions.models import Tag

from .base import URL_TRANSACOES, ContratosTestCase

DINHEIRO = re.compile(r'^-?\d+\.\d{2}$')


class FuncaoDinheiroTests(SimpleTestCase):

    def test_duas_casas_com_arredondamento_meio_para_cima(self):
        self.assertEqual(dinheiro(Decimal('1234.565')), '1234.57')
        self.assertEqual(dinheiro(Decimal('1234.564')), '1234.56')
        self.assertEqual(dinheiro(Decimal('-10.005')), '-10.01')

    def test_zero_none_inteiro_e_ponto_flutuante(self):
        self.assertEqual(dinheiro(None), '0.00')
        self.assertEqual(dinheiro(Decimal('-0')), '0.00')
        self.assertEqual(dinheiro(5), '5.00')
        self.assertEqual(dinheiro(0.1 + 0.2), '0.30')


class DinheiroTestCase(ContratosTestCase):

    def assert_dinheiro(self, valor, onde):
        self.assertIsInstance(valor, str, onde)
        self.assertRegex(valor, DINHEIRO, onde)

    def assert_numero(self, valor, onde):
        self.assertIsInstance(valor, (int, float), onde)
        self.assertNotIsInstance(valor, bool, onde)

    def get_json(self, url, parametros=None):
        resp = self.client.get(url, parametros or {})
        self.assertEqual(resp.status_code, 200, url)
        return resp.json()


class RelatoriosTests(DinheiroTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.dia = date.today() - timedelta(days=2)
        u = cls.a.usuario
        cls.tag = Tag.objects.create(user=u, name='Viagem')
        cls.cartao = CreditCard.objects.create(
            user=u, name='Cartão', limit=Decimal('2000.00'), closing_day=10, due_day=20, account=cls.a.conta,
        )
        Account.objects.create(user=u, name='Corretora', type='INVESTMENT', initial_balance=Decimal('5000.00'))
        FocusedMonitorItem.objects.create(user=u, category=cls.a.despesa)

    def setUp(self):
        super().setUp()
        self.lancar('INCOME', '1000.00', date=self.dia, category=self.a.receita)
        despesa = self.lancar('EXPENSE', '123.45', date=self.dia, category=self.a.despesa)
        despesa.tags.add(self.tag)
        self.lancar('EXPENSE', '10.10', date=self.dia - timedelta(days=40), category=self.a.despesa)

    def test_dashboard(self):
        dados = self.get_json('/api/reports/dashboard/', {'days': 30})
        resumo = dados['summary']
        for campo in ('total_balance', 'monthly_income', 'monthly_expense', 'net_result', 'total_credit_limit',
                      'total_current_invoices', 'net_worth', 'total_liquid_balance', 'total_investment_balance'):
            self.assert_dinheiro(resumo[campo], campo)
        self.assertEqual(resumo['monthly_expense'], '123.45')
        for campo in ('savings_rate', 'liquidity_ratio', 'financial_score'):
            self.assert_numero(resumo[campo], campo)
        cartao = dados['credit_cards'][0]
        for campo in ('limit', 'current_invoice', 'available_limit'):
            self.assert_dinheiro(cartao[campo], campo)
        self.assertEqual(cartao['limit'], '2000.00')

    def test_zero_vem_como_texto(self):
        self.client.force_authenticate(user=self.b.usuario)
        resumo = self.get_json('/api/reports/dashboard/', {'days': 30})['summary']
        self.assertEqual(resumo['monthly_income'], '0.00')
        self.assertEqual(resumo['monthly_expense'], '0.00')

    def test_calendario_e_graficos_simples(self):
        calendario = self.get_json('/api/reports/calendar/', {'days': 30})
        self.assert_dinheiro(calendario['total_income'], 'total_income')
        self.assertEqual(calendario['total_expense'], '123.45')
        for dia in calendario['days']:
            for campo in ('total_incomes', 'total_expenses', 'net_amount'):
                self.assert_dinheiro(dia[campo], campo)

        graficos = self.get_json('/api/reports/charts/simple/', {'days': 30})
        self.assertTrue(graficos['income_vs_expense'])
        for barra in graficos['income_vs_expense']:
            self.assert_dinheiro(barra['income'], 'income')
            self.assert_dinheiro(barra['expense'], 'expense')
        for lista in ('expense_by_category', 'income_by_category'):
            self.assertTrue(graficos[lista], lista)
            for fatia in graficos[lista]:
                self.assert_dinheiro(fatia['amount'], lista)

    def test_graficos_avancados(self):
        dados = self.get_json('/api/reports/charts/advanced/', {'days': 30})
        for ponto in dados['net_worth_evolution']:
            self.assert_dinheiro(ponto['balance'], 'balance')
        investimentos = dados['investment_analysis']
        self.assertEqual(investimentos['total_invested'], '5000.00')
        for mes in investimentos['monthly_history']:
            self.assert_dinheiro(mes['contribution'], 'contribution')
            self.assert_dinheiro(mes['returns'], 'returns')
        self.assertEqual(investimentos['asset_allocation'][0]['value'], '5000.00')
        monitor = dados['custom_monitoring'][0]
        self.assert_dinheiro(monitor['current_month'], 'current_month')
        self.assert_dinheiro(monitor['average_month'], 'average_month')
        for projecao in dados['financial_freedom_projection']:
            self.assert_dinheiro(projecao['value'], 'projection')
        for campo in ('fixed', 'variable', 'total'):
            self.assert_dinheiro(dados['fixed_vs_variable'][campo], campo)
        self.assert_dinheiro(dados['daily_spending_report']['safe_daily_spend'], 'safe_daily_spend')
        self.assert_dinheiro(dados['daily_spending_report']['available_for_month'], 'available_for_month')
        self.assert_numero(dados['daily_spending_report']['remaining_days'], 'remaining_days')
        self.assert_numero(dados['risk_analysis']['volatility_score'], 'volatility_score')
        for dia in dados['spend_by_weekday']:
            self.assert_dinheiro(dia['amount'], 'weekday')

    def test_comparacao_mensal(self):
        meses = self.get_json('/api/reports/charts/monthly-comparison/', {'months': 3})
        self.assertEqual(len(meses), 3)
        for mes in meses:
            for campo in ('income', 'expense', 'balance'):
                self.assert_dinheiro(mes[campo], campo)

    def test_tags(self):
        insights = self.get_json('/api/reports/charts/tag-insights/', {'tag_id': self.tag.pk, 'months': 3})
        self.assert_dinheiro(insights['focus_monitor']['current_month'], 'current_month')
        self.assert_dinheiro(insights['focus_monitor']['average_month'], 'average_month')
        for mes in insights['history_chart']:
            self.assert_dinheiro(mes['income'], 'income')
            self.assert_dinheiro(mes['expense'], 'expense')

        distribuicao = self.get_json('/api/reports/charts/tag-distribution/', {'days': 30})
        self.assertEqual(
            {(t['name'], t['amount']) for t in distribuicao['expense_by_tag']}, {('Viagem', '123.45')},
        )
        self.assertEqual([t['amount'] for t in distribuicao['income_by_tag']], ['1000.00'])

    def test_estatisticas_do_admin(self):
        admin = User.objects.create_user(
            email='contratos.admin@teste.fluxar', password='x', name='Admin',
            is_staff=True, role='ADMIN', plan='PREMIUM',
        )
        self.client.force_authenticate(user=admin)

        estatisticas = self.get_json(f'/api/admin/users/{self.a.usuario.pk}/financial-stats/')
        for campo in ('total_balance', 'avg_income_value', 'avg_expense_value'):
            self.assert_dinheiro(estatisticas[campo], campo)
        self.assert_numero(estatisticas['income_count_per_day'], 'income_count_per_day')

        geral = self.get_json('/api/admin/stats/')
        self.assertEqual(geral['estimated_revenue'], '19.90')
        self.assert_numero(geral['conversion_rate'], 'conversion_rate')


class SerializersTests(DinheiroTestCase):

    def test_cartao(self):
        cartao = CreditCard.objects.create(
            user=self.a.usuario, name='Cartão', limit=Decimal('2000.00'), closing_day=10, due_day=20,
            account=self.a.conta,
        )
        CreditCardInvoice.objects.create(
            card=cartao, month=9, year=2026, closing_date=date(2026, 9, 10), due_date=date(2026, 9, 20),
        )
        dados = self.get_json(f'/api/credit-cards/{cartao.pk}/')
        self.assert_dinheiro(dados['available_limit'], 'available_limit')
        self.assert_dinheiro(dados['current_invoice_total'], 'current_invoice_total')
        self.assertEqual(dados['limit'], '2000.00')

    def test_transacao(self):
        self.lancar('EXPENSE', '50.00')
        self.lancar('INCOME', '20.50')
        valores = {t['type']: t['signed_amount'] for t in self.get_json(URL_TRANSACOES)['results']}
        self.assertEqual(valores, {'EXPENSE': '-50.00', 'INCOME': '20.50'})

    def test_orcamento(self):
        orcamento = Budget.objects.create(
            user=self.a.usuario, category=self.a.despesa, month=9, year=2026, amount_limit=Decimal('200.00'),
        )
        self.lancar('EXPENSE', '50.00', category=self.a.despesa)
        dados = self.get_json(f'/api/budgets/{orcamento.pk}/')
        self.assertEqual(dados['total_spent'], '50.00')
        self.assert_numero(dados['percentage_used'], 'percentage_used')

    def test_meta(self):
        meta = Goal.objects.create(
            user=self.a.usuario, name='Viagem', target_amount=Decimal('1200.00'),
            current_amount=Decimal('200.00'), target_date=date.today() + timedelta(days=400),
        )
        dados = self.get_json(f'/api/goals/{meta.pk}/')
        self.assertEqual(dados['current_amount'], '200.00')
        self.assertEqual(dados['amount_remaining'], '1000.00')
        self.assert_dinheiro(dados['suggested_monthly_saving'], 'suggested_monthly_saving')
        self.assert_numero(dados['progress_percentage'], 'progress_percentage')

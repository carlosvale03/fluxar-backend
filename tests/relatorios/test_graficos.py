"""
Calendário, gráficos simples, comparação mensal e tags pelas regras comuns
(T7, REL-01 a REL-03, REL-05, REL-07, REL-10, REL-17).
"""
import inspect
from datetime import date
from decimal import Decimal

from accounts.models import Account
from reports.services import ReportService
from transactions.models import Tag

from .base import RelatoriosTestCase, agora_em

CALENDARIO = '/api/reports/calendar/'
SIMPLES = '/api/reports/charts/simple/'
COMPARACAO = '/api/reports/charts/monthly-comparison/'
INSIGHTS = '/api/reports/charts/tag-insights/'
DISTRIBUICAO = '/api/reports/charts/tag-distribution/'
MARCO = {'month': 3, 'year': 2026}


def rotulo(ano, mes):
    return date(ano, mes, 1).strftime('%b/%y')


class GraficosTestCase(RelatoriosTestCase):

    def setUp(self):
        super().setUp()
        self.tag = Tag.objects.create(user=self.a.usuario, name='Casa')

    def obter(self, url, parametros):
        resp = self.client.get(url, parametros)
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data

    def mes(self, comparacao, ano, mes):
        return next(item for item in comparacao if item['month'] == rotulo(ano, mes))

    def cenario_de_despesas(self):
        """Independent Test de REL-01, em março de 2026, tudo na mesma categoria e tag."""
        for transacao in (
            self.lancar('EXPENSE', '100.00', date(2026, 3, 5), category=self.a.despesa),
            self.lancar('EXPENSE', '50.00', date(2026, 3, 12), status='PENDING', category=self.a.despesa),
            # 10/03 depois do fechamento de 05/03: fatura de 15/04, ainda aberta
            *self.comprar(self.cartao(5, 15), '80.00', date(2026, 3, 10), categoria=self.a.despesa),
        ):
            transacao.tags.add(self.tag)


class MesmasDespesasTests(GraficosTestCase):

    def test_despesas_de_rel_01_no_calendario_na_pizza_na_comparacao_e_nas_tags(self):
        self.cenario_de_despesas()

        calendario = self.obter(CALENDARIO, MARCO)
        pizza = self.obter(SIMPLES, MARCO)['expense_by_category']
        comparacao = self.obter(COMPARACAO, {'months': 2, 'month': 4, 'year': 2026})
        distribuicao = self.obter(DISTRIBUICAO, MARCO)['expense_by_tag']

        self.assertEqual(calendario['total_expense'], '180.00')
        dias = {dia['date']: dia['total_expenses'] for dia in calendario['days']}
        self.assertEqual(dias, {'2026-03-05': '100.00', '2026-03-10': '80.00'})
        self.assertEqual(pizza, [{'category_name': 'Mercado A', 'amount': '180.00', 'color': '#CBD5E1'}])
        self.assertEqual(self.mes(comparacao, 2026, 3)['expense'], '180.00')
        # A compra conta em março, não no mês da fatura (abril)
        self.assertEqual(self.mes(comparacao, 2026, 4)['expense'], '0.00')
        self.assertEqual(
            distribuicao, [{'id': str(self.tag.pk), 'name': 'Casa', 'amount': '180.00', 'color': '#CBD5E1'}],
        )

    def test_insights_da_tag_contam_as_mesmas_despesas_no_mes_atual(self):
        self.cenario_de_despesas()

        with agora_em(2026, 3, 20):
            insights = self.obter(INSIGHTS, {'tag_id': str(self.tag.pk), 'months': 3})

        self.assertEqual(insights['focus_monitor']['current_month'], '180.00')
        self.assertEqual(insights['history_chart'][-1], {
            'month': rotulo(2026, 3), 'income': '0.00', 'expense': '180.00',
        })

    def test_parcelas_contam_uma_por_mes_na_comparacao(self):
        self.comprar(self.cartao(5, 15), '300.00', date(2026, 1, 31), parcelas=3)

        comparacao = self.obter(COMPARACAO, {'months': 4, 'month': 4, 'year': 2026})

        self.assertEqual(
            [(item['month'], item['expense']) for item in comparacao],
            [(rotulo(2026, 1), '100.00'), (rotulo(2026, 2), '100.00'),
             (rotulo(2026, 3), '100.00'), (rotulo(2026, 4), '0.00')],
        )

    def test_despesa_efetivada_de_conta_excluida_continua_nos_graficos(self):
        antiga = self.conta('CHECKING', nome='Antiga')
        self.lancar('EXPENSE', '25.00', date(2026, 3, 3), conta=antiga, category=self.a.despesa)
        Account.objects.filter(pk=antiga.pk).update(is_active=False)

        self.assertEqual(self.obter(CALENDARIO, MARCO)['total_expense'], '25.00')
        self.assertEqual(self.obter(SIMPLES, MARCO)['expense_by_category'][0]['amount'], '25.00')
        self.assertEqual(self.mes(self.obter(COMPARACAO, {'months': 1, **MARCO}), 2026, 3)['expense'], '25.00')


class ReceitasTests(GraficosTestCase):

    def test_receita_pendente_transferencia_e_ajuste_ficam_fora(self):
        efetivada = self.lancar('INCOME', '5000.00', date(2026, 3, 5), category=self.a.receita)
        pendente = self.lancar('INCOME', '300.00', date(2026, 3, 6), status='PENDING', category=self.a.receita)
        ajuste = self.lancar(
            'INCOME', '250.25', date(2026, 3, 8), description='Ajuste de saldo', is_balance_adjustment=True,
        )
        self.lancar('EXPENSE', '0.20', date(2026, 3, 8), description='Ajuste de saldo', is_balance_adjustment=True)
        self.transferir(self.conta('SAVINGS'), self.a.conta, '200.00', date(2026, 3, 7))
        for transacao in (efetivada, pendente, ajuste):
            transacao.tags.add(self.tag)

        calendario = self.obter(CALENDARIO, MARCO)
        simples = self.obter(SIMPLES, MARCO)
        comparacao = self.mes(self.obter(COMPARACAO, {'months': 1, **MARCO}), 2026, 3)
        distribuicao = self.obter(DISTRIBUICAO, MARCO)

        self.assertEqual((calendario['total_income'], calendario['total_expense']), ('5000.00', '0.00'))
        self.assertEqual(simples['income_by_category'], [
            {'category_name': 'Salário A', 'amount': '5000.00', 'color': '#CBD5E1'},
        ])
        self.assertEqual(simples['expense_by_category'], [])
        self.assertEqual((comparacao['income'], comparacao['expense']), ('5000.00', '0.00'))
        self.assertEqual(
            distribuicao['income_by_tag'],
            [{'id': str(self.tag.pk), 'name': 'Casa', 'amount': '5000.00', 'color': '#CBD5E1'}],
        )
        self.assertEqual(distribuicao['expense_by_tag'], [])


class MesesDoCalendarioTests(GraficosTestCase):

    SEIS_MESES = [rotulo(2025, 10), rotulo(2025, 11), rotulo(2025, 12),
                  rotulo(2026, 1), rotulo(2026, 2), rotulo(2026, 3)]

    def test_comparacao_de_seis_meses_a_partir_de_marco_vai_de_outubro_a_marco(self):
        comparacao = self.obter(COMPARACAO, {'months': 6, **MARCO})

        self.assertEqual([item['month'] for item in comparacao], self.SEIS_MESES)

    def test_historico_da_tag_de_seis_meses_a_partir_de_31_de_marco(self):
        with agora_em(2026, 3, 31):
            insights = self.obter(INSIGHTS, {'tag_id': str(self.tag.pk), 'months': 6})

        self.assertEqual([item['month'] for item in insights['history_chart']], self.SEIS_MESES)


class SemPontoFlutuanteTests(GraficosTestCase):

    def test_nenhum_float_em_valor_de_dinheiro(self):
        for funcao in (
            ReportService.get_calendar_data, ReportService.get_simple_charts,
            ReportService.get_monthly_comparison, ReportService.get_tag_insights,
            ReportService.get_tag_distribution,
        ):
            with self.subTest(funcao=funcao.__name__):
                self.assertNotIn('float(', inspect.getsource(funcao))

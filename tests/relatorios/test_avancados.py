"""
Relatórios avançados (T8, REL-09 a REL-11, REL-16, REL-17).
"""
from datetime import date
from decimal import Decimal

from accounts.models import Account
from reports.models import FocusedMonitorItem
from transactions.models import Category

from .base import RelatoriosTestCase, agora_em

URL = '/api/reports/charts/advanced/'


def rotulo(ano, mes):
    return date(ano, mes, 1).strftime('%b/%y')


class AvancadosTestCase(RelatoriosTestCase):

    def avancados(self, ano, mes, dia, hora=15):
        """O relatório avançado do mês corrente, com o relógio no dia dado."""
        with agora_em(ano, mes, dia, hora=hora):
            resp = self.client.get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.json()


class MapaDeCalorTests(AvancadosTestCase):

    def test_despesa_lancada_as_22h_de_brasilia_aparece_as_22h(self):
        # 01h UTC de 11/03 = 22h de terça, 10/03, em Brasília
        with agora_em(2026, 3, 11, hora=1):
            self.lancar('EXPENSE', '45.00', date(2026, 3, 10))
        # Pendente fica fora (REL-03)
        with agora_em(2026, 3, 11, hora=13):
            self.lancar('EXPENSE', '45.00', date(2026, 3, 10), status='PENDING')

        dados = self.avancados(2026, 3, 20)

        self.assertEqual(dados['spending_frequency'], [{'day_of_week': 3, 'hour_of_day': 22, 'count': 1}])


class EvolucaoDoPatrimonioTests(AvancadosTestCase):

    def test_um_ponto_por_mes_no_fim_do_mes_com_a_divida_do_cartao(self):
        Account.objects.filter(pk=self.a.conta.pk).update(initial_balance=Decimal('1000.00'))
        self.lancar('INCOME', '500.00', date(2026, 1, 15))
        # Pendente não muda o patrimônio
        self.lancar('EXPENSE', '70.00', date(2026, 2, 3), status='PENDING')
        # Compra de 20/02 ainda não paga: dívida desde fevereiro
        self.comprar(self.cartao(5, 15), '300.00', date(2026, 2, 20))

        dados = self.avancados(2026, 3, 31)

        self.assertEqual(dados['net_worth_evolution'], [
            {'date': '2025-10-31', 'balance': '1000.00'},
            {'date': '2025-11-30', 'balance': '1000.00'},
            {'date': '2025-12-31', 'balance': '1000.00'},
            {'date': '2026-01-31', 'balance': '1500.00'},
            {'date': '2026-02-28', 'balance': '1200.00'},
            {'date': '2026-03-31', 'balance': '1200.00'},
        ])


class InvestimentosTests(AvancadosTestCase):

    def test_historico_com_um_mes_do_calendario_por_item(self):
        investimento = self.conta('INVESTMENT', nome='Corretora')
        outro = self.conta('INVESTMENT', nome='Tesouro')
        self.transferir(self.a.conta, investimento, '200.00', date(2026, 1, 31))
        self.transferir(investimento, self.a.conta, '100.00', date(2026, 2, 10))
        self.transferir(self.a.conta, investimento, '300.00', date(2026, 3, 5))
        # Entre contas de investimento não é aporte nem resgate
        self.transferir(investimento, outro, '50.00', date(2026, 3, 6))

        historico = self.avancados(2026, 3, 31)['investment_analysis']['monthly_history']

        self.assertEqual(historico, [
            {'month': rotulo(2025, 10), 'contribution': '0.00', 'returns': '0.00'},
            {'month': rotulo(2025, 11), 'contribution': '0.00', 'returns': '0.00'},
            {'month': rotulo(2025, 12), 'contribution': '0.00', 'returns': '0.00'},
            {'month': rotulo(2026, 1), 'contribution': '200.00', 'returns': '0.00'},
            {'month': rotulo(2026, 2), 'contribution': '0.00', 'returns': '100.00'},
            {'month': rotulo(2026, 3), 'contribution': '300.00', 'returns': '0.00'},
        ])


class MonitorDeFocoTests(AvancadosTestCase):

    def setUp(self):
        super().setUp()
        self.monitor = FocusedMonitorItem.objects.create(user=self.a.usuario, category=self.a.despesa)
        self.lancar('EXPENSE', '100.00', date(2026, 3, 5), category=self.a.despesa)
        self.lancar('EXPENSE', '50.00', date(2026, 3, 12), status='PENDING', category=self.a.despesa)
        # 10/03 depois do fechamento de 05/03: fatura de 15/04
        self.comprar(self.cartao(5, 15), '80.00', date(2026, 3, 10), categoria=self.a.despesa)

    def monitor_(self):
        dados = self.avancados(2026, 3, 20)
        return next(m for m in dados['custom_monitoring'] if m['id'] == str(self.monitor.pk))

    def test_mes_atual_pelas_regras_e_sem_historico_nos_meses_anteriores(self):
        monitor = self.monitor_()

        self.assertEqual(
            (monitor['current_month'], monitor['average_month'], monitor['status']), ('180.00', '0.00', 'warning'),
        )

    def test_media_dos_meses_anteriores_com_movimento(self):
        self.lancar('EXPENSE', '90.00', date(2026, 2, 10), category=self.a.despesa)
        self.lancar('EXPENSE', '150.00', date(2025, 12, 10), category=self.a.despesa)

        monitor = self.monitor_()

        self.assertEqual(
            (monitor['current_month'], monitor['average_month'], monitor['status']), ('180.00', '120.00', 'warning'),
        )


class ProximoGrandeGastoTests(AvancadosTestCase):

    def test_projecao_para_o_dia_31_em_fevereiro_vira_28(self):
        aluguel = Category.objects.create(user=self.a.usuario, name='Aluguel', type='EXPENSE')
        self.lancar('EXPENSE', '10.00', date(2026, 1, 5))
        self.lancar('EXPENSE', '300.00', date(2025, 12, 31), category=aluguel)
        self.lancar('EXPENSE', '300.00', date(2026, 1, 31), category=aluguel)

        gasto = self.avancados(2026, 1, 31)['next_big_expense']

        self.assertEqual(gasto, {
            'description': 'Aluguel', 'amount': '300.00', 'date': '2026-02-28', 'category': 'Aluguel',
        })

    def test_receita_agendada_nao_e_gasto_e_despesa_agendada_e(self):
        viagem = Category.objects.create(user=self.a.usuario, name='Viagem', type='EXPENSE')
        self.lancar('EXPENSE', '10.00', date(2026, 3, 2))
        self.lancar('INCOME', '9000.00', date(2026, 4, 5), status='PENDING', category=self.a.receita)
        self.lancar('EXPENSE', '700.00', date(2026, 4, 10), status='PENDING', category=viagem)

        gasto = self.avancados(2026, 3, 20)['next_big_expense']

        self.assertEqual(gasto, {
            'description': 'Viagem', 'amount': '700.00', 'date': '2026-04-10', 'category': 'Viagem',
        })


class SemPontoFlutuanteTests(AvancadosTestCase):

    # Percentuais e razões continuam números (AD-041)
    NUMEROS_PERMITIDOS = {'risk_analysis.volatility_score'}

    def floats(self, valor, caminho=''):
        if isinstance(valor, float):
            yield caminho
        elif isinstance(valor, dict):
            for chave, item in valor.items():
                yield from self.floats(item, f'{caminho}.{chave}' if caminho else chave)
        elif isinstance(valor, list):
            for item in valor:
                yield from self.floats(item, caminho)

    def test_valores_em_dinheiro_saem_como_texto_sem_ponto_flutuante(self):
        investimento = self.conta('INVESTMENT', '1000.00', nome='Corretora')
        self.transferir(self.a.conta, investimento, '333.33', date(2026, 3, 5))
        self.lancar('INCOME', '3000.00', date(2026, 3, 1))
        self.lancar('EXPENSE', '100.10', date(2026, 2, 7), category=self.a.despesa)
        self.lancar('EXPENSE', '0.10', date(2026, 3, 7), category=self.a.despesa)
        self.lancar('EXPENSE', '0.20', date(2026, 3, 8), category=self.a.despesa)
        FocusedMonitorItem.objects.create(user=self.a.usuario, category=self.a.despesa)

        dados = self.avancados(2026, 3, 20)

        self.assertEqual(set(self.floats(dados)), self.NUMEROS_PERMITIDOS)
        investimentos = dados['investment_analysis']
        self.assertEqual(investimentos['total_invested'], '1333.33')
        self.assertEqual(investimentos['asset_allocation'][0]['value'], '1333.33')
        self.assertEqual(investimentos['monthly_history'][-1]['contribution'], '333.33')
        self.assertEqual(dados['fixed_vs_variable']['total'], '0.30')

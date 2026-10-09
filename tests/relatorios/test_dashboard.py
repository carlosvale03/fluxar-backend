"""
Dashboard pelas regras comuns (T4, REL-01 a REL-05, REL-08, REL-13, REL-15,
REL-18).
"""
from datetime import date
from decimal import Decimal

from accounts.faturas import obter_fatura
from accounts.models import Account, CreditCardInvoice

from .base import RelatoriosTestCase, agora_em

URL = '/api/reports/dashboard/'


class DashboardTestCase(RelatoriosTestCase):

    def resumo(self, parametros=None):
        resp = self.client.get(URL, parametros or {})
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data['summary']

    def cenario_de_despesas(self):
        """Independent Test de REL-01, em março de 2026."""
        self.lancar('EXPENSE', '100.00', date(2026, 3, 5))
        self.lancar('EXPENSE', '50.00', date(2026, 3, 12), status='PENDING')
        # 10/03 depois do fechamento de 05/03: fatura de 15/04, ainda aberta
        self.comprar(self.cartao(5, 15), '80.00', date(2026, 3, 10))


class DespesasEAPagarTests(DashboardTestCase):

    def test_despesas_do_mes_e_a_pagar_a_parte(self):
        self.cenario_de_despesas()

        resumo = self.resumo({'month': 3, 'year': 2026})

        self.assertEqual(resumo['monthly_expense'], '180.00')
        self.assertEqual(resumo['payable'], '50.00')

    def test_intervalo_de_dias_usa_as_mesmas_regras(self):
        self.cenario_de_despesas()

        with agora_em(2026, 3, 20):
            resumo = self.resumo({'days': 30})

        self.assertEqual(resumo['monthly_expense'], '180.00')
        self.assertEqual(resumo['payable'], '50.00')

    def test_receitas_so_efetivadas_sem_transferencia_e_sem_ajuste(self):
        self.lancar('INCOME', '5000.00', date(2026, 3, 5))
        self.lancar('INCOME', '300.00', date(2026, 3, 6), status='PENDING')
        self.transferir(self.conta('SAVINGS'), self.a.conta, '200.00', date(2026, 3, 7))
        self.lancar('INCOME', '250.25', date(2026, 3, 8), description='Ajuste de saldo', is_balance_adjustment=True)
        self.lancar('EXPENSE', '0.20', date(2026, 3, 8), description='Ajuste de saldo', is_balance_adjustment=True)

        resumo = self.resumo({'month': 3, 'year': 2026})

        self.assertEqual(resumo['monthly_income'], '5000.00')
        self.assertEqual(resumo['monthly_expense'], '0.00')
        self.assertEqual(resumo['net_result'], '5000.00')

    def test_sem_mes_usa_o_mes_atual_de_brasilia(self):
        self.cenario_de_despesas()
        self.lancar('EXPENSE', '999.00', date(2026, 4, 1))

        # 02h UTC de 01/04 = 23h de 31/03 em Brasília
        with agora_em(2026, 4, 1, hora=2):
            resumo = self.resumo()

        self.assertEqual(resumo['monthly_expense'], '180.00')


class PatrimonioTests(DashboardTestCase):

    def test_patrimonio_dividido_em_quatro_partes(self):
        Account.objects.filter(pk=self.a.conta.pk).update(initial_balance=Decimal('3000.00'), balance=Decimal('3000.00'))
        self.conta('PIGGY_BANK', '800.00')
        self.conta('INVESTMENT', '2000.00')
        self.comprar(self.cartao(5, 15), '450.00', date(2026, 3, 10))

        resumo = self.resumo({'month': 3, 'year': 2026})

        self.assertEqual(resumo['net_worth'], '5350.00')
        self.assertEqual(resumo['net_worth_breakdown'], {
            'available': '3000.00', 'reserves': '800.00', 'investments': '2000.00', 'open_invoices': '450.00',
        })


class FaturasDoMesTests(DashboardTestCase):

    def test_soma_so_as_faturas_nao_pagas_que_vencem_no_mes_atual(self):
        cartao = self.cartao(5, 15)
        outro = self.cartao(25, 10)
        # Vencem em 15/03: R$ 150,00 pendentes
        self.comprar(cartao, '120.00', date(2026, 2, 10))
        self.comprar(cartao, '30.00', date(2026, 2, 20))
        # Vence em 15/04
        self.comprar(cartao, '80.00', date(2026, 3, 10))
        # Fatura de 10/03 do outro cartão, paga
        paga = obter_fatura(outro, 3, 2026)
        self.lancar(
            'CREDIT_CARD', '60.00', paga.due_date, credit_card=outro, invoice=paga,
            purchase_date=date(2026, 2, 1), payment_date=date(2026, 3, 10),
        )
        CreditCardInvoice.objects.filter(pk=paga.pk).update(status='PAID')

        with agora_em(2026, 3, 10):
            # O período escolhido não muda as faturas do mês atual
            resumo = self.resumo({'month': 1, 'year': 2026})

        self.assertEqual(resumo['total_current_invoices'], '150.00')

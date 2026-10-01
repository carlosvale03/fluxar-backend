"""
Totais do dashboard e do admin (SALDO-28 a SALDO-31).

A tem a conta corrente com R$ 1.000,00, uma conta de investimento com
R$ 500,00 e uma conta excluída antes da correção, ainda com R$ 300,00. As
demais contas de A (carteira, poupança e cofrinho) estão zeradas.
"""
from decimal import Decimal

from accounts.models import Account
from reports.services import ReportService
from transactions.models import Transaction
from tests.saldo.base import SaldoTestCase

URL_DASHBOARD = '/api/reports/dashboard/'


def decimal(valor):
    return Decimal(str(valor)).quantize(Decimal('0.01'))


class TotaisTests(SaldoTestCase):

    def setUp(self):
        super().setUp()
        self.investimento = Account.objects.create(
            user=self.a.usuario, name='Corretora', type='INVESTMENT',
            initial_balance=Decimal('500.00'),
        )
        self.excluida = Account.objects.create(
            user=self.a.usuario, name='Antiga', type='CHECKING',
            initial_balance=Decimal('300.00'),
        )
        # Excluída com saldo, como as contas excluídas antes da correção
        Account.objects.filter(pk=self.excluida.pk).update(is_active=False)

    def resumo(self):
        resp = self.cliente.get(URL_DASHBOARD)
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data['summary']

    def lista_de_contas(self):
        resp = self.cliente.get('/api/accounts/')
        self.assertEqual(resp.status_code, 200, resp.data)
        return {c['id']: (c['type'], Decimal(c['balance'])) for c in resp.data}

    def test_saldo_em_contas_soma_corrente_poupanca_e_carteira_ativas(self):
        self.assertEqual(decimal(self.resumo()['total_liquid_balance']), Decimal('1000.00'))

    def test_saldo_total_soma_as_contas_ativas_de_qualquer_tipo(self):
        resumo = self.resumo()
        self.assertEqual(decimal(resumo['total_balance']), Decimal('1500.00'))
        # O patrimônio parte do saldo total, menos as faturas atuais (zeradas aqui)
        self.assertEqual(decimal(resumo['net_worth']), Decimal('1500.00'))

    def test_saldo_de_investimentos_soma_so_as_contas_de_investimento_ativas(self):
        self.assertEqual(decimal(self.resumo()['total_investment_balance']), Decimal('500.00'))

    def test_estatisticas_do_admin_somam_so_as_contas_ativas(self):
        stats = ReportService.get_user_financial_stats(self.a.usuario)
        self.assertEqual(decimal(stats['total_balance']), Decimal('1500.00'))

    def test_totais_usam_o_mesmo_valor_da_lista_de_contas(self):
        """
        Uma despesa efetivada gravada sem signals deixa o razão da conta
        corrente em R$ 900,00 enquanto a lista mostra R$ 1.000,00: os totais
        seguem a lista (SALDO-28).
        """
        Transaction.objects.bulk_create([Transaction(
            user=self.a.usuario, account=self.a.conta, type='EXPENSE', status='COMPLETED',
            description='Gravada sem signal', amount=Decimal('100.00'), date='2026-09-15',
        )])
        lista = self.lista_de_contas()
        self.assertEqual(lista[str(self.a.conta.id)][1], Decimal('1000.00'))
        self.assertNotIn(str(self.excluida.id), lista)

        liquido = sum(v for t, v in lista.values() if t in ('CHECKING', 'SAVINGS', 'WALLET'))
        investimento = sum(v for t, v in lista.values() if t == 'INVESTMENT')
        total = sum(v for _, v in lista.values())
        resumo = self.resumo()
        stats = ReportService.get_user_financial_stats(self.a.usuario)

        self.assertEqual(
            (
                decimal(resumo['total_liquid_balance']), decimal(resumo['total_investment_balance']),
                decimal(resumo['total_balance']), decimal(stats['total_balance']),
            ),
            (liquido, investimento, total, total),
        )
        self.assertEqual(total, Decimal('1500.00'))

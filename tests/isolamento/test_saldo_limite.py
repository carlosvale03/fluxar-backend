from datetime import date
from decimal import Decimal

from accounts.services import AccountService
from transactions.models import Transaction
from tests.isolamento.base import DoisUsuariosTestCase


class SaldoELimiteSoDoDonoTests(DoisUsuariosTestCase):

    def lancar(self, usuario, tipo, valor, status='COMPLETED', **relacoes):
        return Transaction.objects.create(
            user=usuario, type=tipo, status=status, description='Lançamento',
            amount=Decimal(valor), date=date(2026, 9, 5), **relacoes,
        )

    def test_transacoes_de_b_na_conta_de_a_nao_mudam_o_saldo_de_a(self):
        self.lancar(self.a.usuario, 'EXPENSE', '100.00', account=self.a.conta)
        # Transações de B gravadas à força na conta de A, como antes da correção
        self.lancar(self.b.usuario, 'INCOME', '500.00', account=self.a.conta)
        self.lancar(self.b.usuario, 'EXPENSE', '70.00', account=self.a.conta)

        self.assertEqual(AccountService.get_balance(self.a.conta), Decimal('900.00'))

        # O saldo total do dashboard soma as contas de A pelo mesmo cálculo
        # (Carteira 0, Conta A 900 e Cofrinho A 0)
        resp = self.como(self.a.usuario).get('/api/reports/dashboard/', {'month': 9, 'year': 2026})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['summary']['total_balance'], Decimal('900.00'))

    def test_compras_de_b_no_cartao_de_a_nao_mudam_o_limite_de_a(self):
        """
        A compra de B entra sem fatura: o total guardado da fatura vem do
        signal `update_invoice_total`, e quem corrige esse total é a correção
        de dados (T22). Aqui só o limite, que é somado na leitura.
        """
        self.lancar(self.a.usuario, 'CREDIT_CARD', '300.00', status='PENDING', credit_card=self.a.cartao)
        # Compra de B gravada à força no cartão de A, como antes da correção
        self.lancar(self.b.usuario, 'CREDIT_CARD', '800.00', status='PENDING', credit_card=self.a.cartao)

        resp = self.como(self.a.usuario).get(f'/api/credit-cards/{self.a.cartao.id}/')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Decimal(str(resp.data['available_limit'])), Decimal('1700.00'))

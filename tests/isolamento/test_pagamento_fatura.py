from datetime import date
from decimal import Decimal

from accounts.models import Account, CreditCardInvoice
from transactions.models import Transaction
from tests.isolamento.base import DoisUsuariosTestCase


class PagamentoEEstornoSoComComprasDoDonoTests(DoisUsuariosTestCase):
    """
    Compra de B gravada à força na fatura de A, como antes da correção: pagar
    e estornar a fatura de A mexe só nas compras de A (ISOL-14).
    """

    def setUp(self):
        self.cliente = self.como(self.a.usuario)
        self.compra_a = self.compra(self.a.usuario, self.a.cartao, self.a.conta, '100.00')
        self.url = f'/api/invoices/{self.a.fatura.id}/'

    def compra(self, usuario, cartao, conta, valor, status='PENDING'):
        return Transaction.objects.create(
            user=usuario, type='CREDIT_CARD', status=status, description='Loja',
            amount=Decimal(valor), date=date(2026, 9, 5), account=conta,
            credit_card=cartao, invoice=self.a.fatura,
        )

    def forjar_compra_de_b(self, status='PENDING'):
        return self.compra(self.b.usuario, self.b.cartao, self.b.conta, '50.00', status)

    def forjar_compra_de_b_no_cartao_de_a(self, status='PENDING'):
        """Compra de B gravada à força com o cartão e a fatura de A."""
        return self.compra(self.b.usuario, self.a.cartao, self.b.conta, '50.00', status)

    def estado(self, t):
        t.refresh_from_db()
        return (
            t.user_id, t.status, t.account_id, t.amount, t.invoice_id,
            t.payment_date, t.description,
        )

    def saldo(self, conta):
        return Account.objects.get(pk=conta.pk).balance

    def pagar(self, valor):
        resp = self.cliente.post(
            f'{self.url}pay/',
            {'amount': valor, 'date': '2026-09-20', 'account_id': str(self.a.cofrinho.id)},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_pagamento_da_fatura_nao_muda_a_compra_de_b(self):
        compra_b = self.forjar_compra_de_b()
        antes_b = self.estado(compra_b)
        saldo_b = self.saldo(self.b.conta)

        self.pagar('100.00')

        self.assertEqual(self.estado(compra_b), antes_b)
        self.assertEqual(
            self.estado(self.compra_a)[1:4], ('COMPLETED', self.a.cofrinho.id, Decimal('100.00')),
        )
        # O cofrinho de A cai só os 100.00 da compra de A, sem os 50.00 de B
        self.assertEqual(self.saldo(self.a.cofrinho), Decimal('-100.00'))
        self.assertEqual(self.saldo(self.b.conta), saldo_b)
        self.assertEqual(CreditCardInvoice.objects.get(pk=self.a.fatura.pk).status, 'PAID')

    def test_pagamento_parcial_divide_so_a_compra_de_a(self):
        compra_b = self.forjar_compra_de_b()
        antes_b = self.estado(compra_b)

        self.pagar('30.00')

        self.assertEqual(self.estado(compra_b), antes_b)
        self.assertEqual(
            self.estado(self.compra_a)[1:4], ('COMPLETED', self.a.cofrinho.id, Decimal('30.00')),
        )
        restante = Transaction.objects.get(description='Loja (Restante)')
        self.assertEqual(
            (restante.user_id, restante.amount, restante.invoice.month),
            (self.a.usuario.id, Decimal('70.00'), 10),
        )
        self.assertEqual(self.saldo(self.a.cofrinho), Decimal('-30.00'))

    def test_estorno_do_pagamento_nao_muda_a_compra_de_b(self):
        # Compra de B já efetivada na conta de B, ligada à força à fatura de A
        compra_b = self.forjar_compra_de_b(status='COMPLETED')
        self.pagar('100.00')
        antes_b = self.estado(compra_b)
        saldo_b = self.saldo(self.b.conta)

        resp = self.cliente.post(f'{self.url}unpay/', format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.estado(compra_b), antes_b)
        self.assertEqual(antes_b[1:3], ('COMPLETED', self.b.conta.id))
        self.assertEqual(self.saldo(self.b.conta), saldo_b)
        self.assertEqual(self.estado(self.compra_a)[1], 'PENDING')
        self.assertEqual(CreditCardInvoice.objects.get(pk=self.a.fatura.pk).status, 'OPEN')

    def test_pagamento_nao_muda_a_compra_de_b_no_cartao_de_a(self):
        compra_b = self.forjar_compra_de_b_no_cartao_de_a()
        antes_b = self.estado(compra_b)
        saldo_b = self.saldo(self.b.conta)

        # O total da fatura é só a compra de A (FATURA-26 recusa valor maior); a de B,
        # menor e da mesma data, viria antes na ordem de pagamento se entrasse
        self.pagar('100.00')

        self.assertEqual(self.estado(compra_b), antes_b)
        self.assertEqual(antes_b[1:3], ('PENDING', self.b.conta.id))
        self.assertEqual(
            self.estado(self.compra_a)[1:4], ('COMPLETED', self.a.cofrinho.id, Decimal('100.00')),
        )
        self.assertEqual(self.saldo(self.a.cofrinho), Decimal('-100.00'))
        self.assertEqual(self.saldo(self.b.conta), saldo_b)
        self.assertEqual(CreditCardInvoice.objects.get(pk=self.a.fatura.pk).status, 'PAID')

    def test_estorno_nao_muda_a_compra_de_b_no_cartao_de_a(self):
        compra_b = self.forjar_compra_de_b_no_cartao_de_a(status='COMPLETED')
        self.pagar('100.00')
        self.assertEqual(self.saldo(self.a.cofrinho), Decimal('-100.00'))
        antes_b = self.estado(compra_b)
        saldo_b = self.saldo(self.b.conta)

        resp = self.cliente.post(f'{self.url}unpay/', format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.estado(compra_b), antes_b)
        self.assertEqual(antes_b[1:3], ('COMPLETED', self.b.conta.id))
        self.assertEqual(self.saldo(self.b.conta), saldo_b)
        self.assertEqual(self.estado(self.compra_a)[1], 'PENDING')
        self.assertEqual(CreditCardInvoice.objects.get(pk=self.a.fatura.pk).status, 'OPEN')

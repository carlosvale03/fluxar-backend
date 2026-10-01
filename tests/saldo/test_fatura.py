"""
Pagamento e estorno de fatura (SALDO-23 a SALDO-27).

A fatura de setembro do cartão de A tem uma compra pendente de R$ 1.000,00.
O pagamento sai de uma conta própria com R$ 3.000,00, para separar o saldo
dela do da conta corrente, que é a conta padrão do cartão.
"""
from datetime import date
from decimal import Decimal

from rest_framework.exceptions import ValidationError

from accounts.models import Account, CreditCardInvoice
from accounts.services import CreditCardService
from transactions.models import Transaction
from tests.saldo.base import SaldoTestCase

FATURA_JA_PAGA = 'Fatura já está paga.'


class FaturaTestCase(SaldoTestCase):

    def setUp(self):
        super().setUp()
        self.pagadora = Account.objects.create(
            user=self.a.usuario, name='Pagadora', type='CHECKING',
            initial_balance=Decimal('3000.00'),
        )
        self.compra = self.compra_pendente('1000.00')
        self.url = f'/api/invoices/{self.a.fatura.id}/'

    def compra_pendente(self, valor, descricao='Loja'):
        """Compra pendente como a criada por `create_credit_card_expense`."""
        return self.lancar(
            self.a.cartao.account, 'CREDIT_CARD', valor, status='PENDING',
            description=descricao, credit_card=self.a.cartao, invoice=self.a.fatura,
            date=date(2026, 9, 5),
        )

    def pagar(self, valor='1000.00'):
        return self.cliente.post(f'{self.url}pay/', {
            'account_id': str(self.pagadora.id), 'amount': valor, 'date': '2026-09-20',
        }, format='json')

    def status_da_fatura(self):
        return CreditCardInvoice.objects.get(pk=self.a.fatura.pk).status


class PagamentoDeFaturaTests(FaturaTestCase):

    def test_pagamento_debita_exatamente_o_valor_da_conta_pagadora(self):
        resp = self.pagar()

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.saldo(self.pagadora), Decimal('2000.00'))
        # A conta padrão do cartão não muda
        self.assertEqual(self.saldo(self.a.conta), Decimal('1000.00'))
        self.assertEqual(self.status_da_fatura(), 'PAID')

    def test_pagar_de_novo_recebe_400_sem_segundo_debito(self):
        self.pagar()
        # Uma compra nova cai na fatura já paga: um segundo pagamento a debitaria
        self.compra_pendente('200.00', descricao='Outra loja')

        resp = self.pagar('200.00')

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {'detail': FATURA_JA_PAGA})
        self.assertEqual(self.saldo(self.pagadora), Decimal('2000.00'))
        self.assertEqual(Transaction.objects.get(description='Outra loja').status, 'PENDING')

    def test_servico_com_fatura_lida_antes_do_pagamento_recusa_o_segundo(self):
        """
        Duas requisições simultâneas leem a fatura ainda aberta. O service
        relê a fatura sob trava e recusa a que chega depois do primeiro
        pagamento (SALDO-26).
        """
        lida_antes = CreditCardInvoice.objects.get(pk=self.a.fatura.pk)
        CreditCardService.pay_invoice(
            self.a.usuario, CreditCardInvoice.objects.get(pk=self.a.fatura.pk),
            self.pagadora, Decimal('1000.00'), date(2026, 9, 20),
        )
        self.compra_pendente('200.00', descricao='Outra loja')

        with self.assertRaises(ValidationError) as erro:
            CreditCardService.pay_invoice(
                self.a.usuario, lida_antes, self.pagadora, Decimal('200.00'), date(2026, 9, 20),
            )

        self.assertEqual(erro.exception.detail, {'detail': FATURA_JA_PAGA})
        self.assertEqual(self.saldo(self.pagadora), Decimal('2000.00'))
        self.assertEqual(Transaction.objects.get(description='Outra loja').status, 'PENDING')

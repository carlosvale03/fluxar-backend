"""
Ciclo completo pela API (FATURA-21, FATURA-34, FATURA-37 e o Success
Criteria da spec): criar compras, pagar, estornar e pagar de novo deixa
faturas, compras e totais idênticos aos de um único pagamento, e o saldo da
conta de pagamento acompanha cada passo (SALDO-23 a SALDO-25).

O cartão de A fecha no dia 10 e vence no dia 20. As compras de 05/09/2026
caem na fatura que vence em 20/09. O pagamento sai de uma conta própria com
R$ 2.000,00; a conta corrente é a conta padrão do cartão.
"""
from decimal import Decimal

from accounts.models import Account, CreditCardInvoice
from transactions.models import Transaction
from tests.faturas.base import URL_COMPRA, FaturasTestCase


class FluxoCompletoTests(FaturasTestCase):

    def setUp(self):
        super().setUp()
        self.cartao_ = self.cartao(10, 20)
        self.pagadora = Account.objects.create(
            user=self.a.usuario, name='Pagadora', type='CHECKING', initial_balance=Decimal('2000.00'),
        )
        for descricao, valor, parcelas in (('Mercado', '400.00', 1), ('Loja', '900.00', 3), ('Farmácia', '150.00', 1)):
            resp = self.client.post(URL_COMPRA, {
                'credit_card': str(self.cartao_.id), 'amount': valor, 'date': '2026-09-05',
                'description': descricao, 'category': str(self.a.categoria.id), 'installments': parcelas,
            }, format='json')
            self.assertEqual(resp.status_code, 201, resp.data)
        self.setembro = self.fatura(self.cartao_, 9, 2026)
        # Mercado 400 + Loja 1/3 300 + Farmácia 150
        self.assertEqual(self.total(self.setembro), Decimal('850.00'))

    def pagar(self, valor):
        resp = self.client.post(f'/api/invoices/{self.setembro.id}/pay/', {
            'account_id': str(self.pagadora.id), 'amount': valor, 'date': '2026-09-15',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def estornar(self):
        resp = self.client.post(f'/api/invoices/{self.setembro.id}/unpay/', format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def foto(self):
        """Compras, faturas e saldos, sem os ids das compras (o restante é recriado a cada pagamento)."""
        compras = sorted(
            (t.status, t.amount, t.description, t.invoice.month, t.invoice.year, t.date,
             t.purchase_date, t.account_id, t.payment_date, t.installment_number)
            for t in Transaction.objects.filter(credit_card=self.cartao_).select_related('invoice')
        )
        faturas = sorted(
            CreditCardInvoice.objects.filter(card=self.cartao_).values_list('month', 'year', 'status', 'total_amount'),
        )
        return compras, faturas, self.saldos()

    def saldos(self):
        return (
            Account.objects.get(pk=self.pagadora.pk).balance,
            Account.objects.get(pk=self.a.conta.pk).balance,
        )

    def test_pagar_parcial_estornar_e_pagar_de_novo_e_igual_a_um_pagamento(self):
        antes = self.foto()
        self.assertEqual(self.saldos(), (Decimal('2000.00'), Decimal('1000.00')))

        # Mesma data: paga Farmácia (150) e Loja 1/3 (300) e divide o Mercado (400 em 200 + 200)
        self.pagar('650.00')
        um_pagamento = self.foto()
        self.assertEqual(self.saldos(), (Decimal('1350.00'), Decimal('1000.00')))
        self.assertEqual(self.total(self.setembro), Decimal('650.00'))
        self.assertEqual(self.total(self.fatura(self.cartao_, 10, 2026)), Decimal('500.00'))

        self.estornar()
        self.assertEqual(self.foto(), antes)
        self.assertEqual(self.saldos(), (Decimal('2000.00'), Decimal('1000.00')))
        self.assertEqual(CreditCardInvoice.objects.get(pk=self.setembro.pk).status, 'OPEN')

        self.pagar('650.00')
        self.assertEqual(self.foto(), um_pagamento)
        self.assertEqual(self.saldos(), (Decimal('1350.00'), Decimal('1000.00')))

    def test_pagar_total_estornar_e_pagar_de_novo_e_igual_a_um_pagamento(self):
        antes = self.foto()

        self.pagar('850.00')
        um_pagamento = self.foto()
        self.assertEqual(self.saldos(), (Decimal('1150.00'), Decimal('1000.00')))
        self.assertEqual(
            set(Transaction.objects.filter(invoice=self.setembro).values_list('status', flat=True)),
            {'COMPLETED'},
        )

        self.estornar()
        self.assertEqual(self.foto(), antes)
        self.assertEqual(self.saldos(), (Decimal('2000.00'), Decimal('1000.00')))

        self.pagar('850.00')
        self.assertEqual(self.foto(), um_pagamento)
        self.assertEqual(self.saldos(), (Decimal('1150.00'), Decimal('1000.00')))

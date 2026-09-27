from datetime import date
from decimal import Decimal

from accounts.models import CreditCardInvoice
from transactions.models import Transaction
from tests.isolamento.base import DoisUsuariosTestCase


class TotalDaFaturaSoDoDonoTests(DoisUsuariosTestCase):
    """
    O total guardado da fatura vem do signal `update_invoice_total`, que roda
    a cada compra salva ou excluída na fatura (ISOL-14).
    """

    def compra(self, usuario, valor):
        return Transaction.objects.create(
            user=usuario, type='CREDIT_CARD', status='PENDING', description='Compra',
            amount=Decimal(valor), date=date(2026, 9, 5),
            credit_card=self.a.cartao, invoice=self.a.fatura,
        )

    def total_da_fatura_de_a(self):
        return CreditCardInvoice.objects.get(pk=self.a.fatura.pk).total_amount

    def setUp(self):
        # Compra de B gravada à força na fatura de A, como antes da correção
        self.compra(self.b.usuario, '800.00')

    def test_salvar_compra_de_a_soma_so_as_compras_de_a(self):
        self.compra(self.a.usuario, '300.00')
        self.compra(self.a.usuario, '50.00')

        self.assertEqual(self.total_da_fatura_de_a(), Decimal('350.00'))

    def test_excluir_compra_de_a_soma_so_as_compras_de_a_restantes(self):
        self.compra(self.a.usuario, '300.00')
        excluida = self.compra(self.a.usuario, '50.00')

        excluida.delete()

        self.assertEqual(self.total_da_fatura_de_a(), Decimal('300.00'))

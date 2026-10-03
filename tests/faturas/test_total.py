"""
Total da fatura igual à soma das compras ligadas a ela (FATURA-14,
FATURA-18, ISOL-14).
"""
from decimal import Decimal

from accounts.faturas import colocar, obter_fatura, recalcular_totais
from accounts.models import CreditCardInvoice
from transactions.models import Transaction
from tests.faturas.base import FaturasTestCase


class TotalDaFaturaTests(FaturasTestCase):

    def setUp(self):
        super().setUp()
        self.cartao_ = self.cartao(10, 20)
        self.setembro = obter_fatura(self.cartao_, 9, 2026)
        self.outubro = obter_fatura(self.cartao_, 10, 2026)

    def test_mover_uma_compra_atualiza_o_total_da_antiga_e_da_nova(self):
        movida = self.compra(self.cartao_, self.setembro, '300.00')
        self.compra(self.cartao_, self.setembro, '100.00')
        self.compra(self.cartao_, self.outubro, '50.00')

        colocar(movida, self.outubro)

        self.assertEqual(self.total(self.setembro), Decimal('100.00'))
        self.assertEqual(self.total(self.outubro), Decimal('350.00'))

    def test_mudar_o_valor_e_excluir_atualizam_o_total(self):
        compra = self.compra(self.cartao_, self.setembro, '300.00')
        self.compra(self.cartao_, self.setembro, '100.00')

        compra.amount = Decimal('250.00')
        compra.save()
        self.assertEqual(self.total(self.setembro), Decimal('350.00'))

        compra.delete()
        self.assertEqual(self.total(self.setembro), Decimal('100.00'))

    def test_compras_de_outro_usuario_ligadas_a_fatura_nao_entram_no_total(self):
        # Compra de B gravada à força na fatura de A
        self.compra(self.cartao_, self.setembro, '800.00', usuario=self.b.usuario)
        self.compra(self.cartao_, self.setembro, '300.00')
        CreditCardInvoice.objects.filter(pk=self.setembro.pk).update(total_amount=Decimal('9.99'))

        recalcular_totais(self.setembro.pk, None)

        self.assertEqual(self.total(self.setembro), Decimal('300.00'))

    def test_recalcular_totais_corrige_o_total_depois_de_update_em_massa(self):
        self.compra(self.cartao_, self.setembro, '300.00')
        self.compra(self.cartao_, self.setembro, '100.00')

        # QuerySet.update() não dispara signals; quem usa chama recalcular_totais
        Transaction.objects.filter(invoice=self.setembro).update(invoice=self.outubro)
        recalcular_totais(self.setembro.pk, self.outubro.pk)

        self.assertEqual(self.total(self.setembro), Decimal('0.00'))
        self.assertEqual(self.total(self.outubro), Decimal('400.00'))

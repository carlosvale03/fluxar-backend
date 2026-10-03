"""
Exclusão da compra no cartão (FATURA-19, FATURA-20): excluir uma parcela
exclui a compra inteira, e compra com parte em fatura paga não sai.
"""
from decimal import Decimal

from accounts.models import CreditCardInvoice
from transactions.models import Transaction
from tests.faturas.base import URL_COMPRA, URL_TRANSACOES, FaturasTestCase

MENSAGEM = 'Estorne o pagamento da fatura antes de alterar esta compra.'


class ExclusaoDaCompraTests(FaturasTestCase):

    def setUp(self):
        super().setUp()
        self.cartao_ = self.cartao(10, 20)
        resp = self.client.post(URL_COMPRA, {
            'credit_card': str(self.cartao_.id), 'amount': '1200.00', 'date': '2026-09-05',
            'description': 'Loja', 'category': str(self.a.categoria.id), 'installments': 12,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.faturas = list(CreditCardInvoice.objects.filter(card=self.cartao_))
        self.assertEqual(len(self.faturas), 12)

    def parcela(self, numero):
        return Transaction.objects.get(credit_card=self.cartao_, installment_number=numero)

    def excluir(self, parcela):
        return self.client.delete(f'{URL_TRANSACOES}{parcela.id}/')

    def test_excluir_a_parcela_5_exclui_as_12_e_os_totais_caem(self):
        for fatura in self.faturas:
            self.assertEqual(self.total(fatura), Decimal('100.00'))

        resp = self.excluir(self.parcela(5))

        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Transaction.objects.filter(credit_card=self.cartao_).exists())
        for fatura in self.faturas:
            self.assertEqual(self.total(fatura), Decimal('0.00'))

    def test_excluir_a_parcela_1_tambem_exclui_as_12(self):
        resp = self.excluir(self.parcela(1))

        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Transaction.objects.filter(credit_card=self.cartao_).exists())
        for fatura in self.faturas:
            self.assertEqual(self.total(fatura), Decimal('0.00'))

    def test_compra_com_parcela_em_fatura_paga_recebe_400_e_nada_sai(self):
        paga = self.parcela(3).invoice
        CreditCardInvoice.objects.filter(pk=paga.pk).update(status='PAID')

        resp = self.excluir(self.parcela(7))

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {'detail': MENSAGEM})
        self.assertEqual(Transaction.objects.filter(credit_card=self.cartao_).count(), 12)
        for fatura in self.faturas:
            self.assertEqual(self.total(fatura), Decimal('100.00'))

"""
Data da compra (FATURA-16, AD-039): a transação expõe `purchase_date`, que
só existe na compra no cartão.
"""
from datetime import date
from decimal import Decimal

from accounts.faturas import obter_fatura
from transactions.models import Transaction
from tests.faturas.base import URL_TRANSACOES, FaturasTestCase


class DataDaCompraTests(FaturasTestCase):

    def despesa(self, **extra):
        return Transaction.objects.create(
            user=self.a.usuario, account=self.a.conta, type='EXPENSE', status='COMPLETED',
            description='Mercado', amount=Decimal('50.00'), date=date(2026, 9, 15), **extra,
        )

    def test_transacao_devolve_purchase_date_e_nulo_fora_da_compra_no_cartao(self):
        cartao = self.cartao(10, 20)
        compra = self.compra(cartao, obter_fatura(cartao, 9, 2026), '80.00', purchase_date=date(2026, 9, 3))
        despesa = self.despesa()

        resp_compra = self.client.get(f'{URL_TRANSACOES}{compra.id}/')
        resp_despesa = self.client.get(f'{URL_TRANSACOES}{despesa.id}/')

        self.assertEqual(resp_compra.data['purchase_date'], '2026-09-03')
        self.assertEqual(resp_compra.data['date'], '2026-09-20')
        self.assertIn('purchase_date', resp_despesa.data)
        self.assertIsNone(resp_despesa.data['purchase_date'])

    def test_purchase_date_enviado_numa_receita_ou_despesa_e_ignorado(self):
        resp = self.client.post(URL_TRANSACOES, {
            'type': 'INCOME', 'status': 'COMPLETED', 'description': 'Salário',
            'amount': '100.00', 'date': '2026-09-15', 'purchase_date': '2026-09-01',
            'account': str(self.a.conta.id),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(Transaction.objects.get(pk=resp.data['id']).purchase_date)

        despesa = self.despesa()
        resp = self.client.patch(
            f'{URL_TRANSACOES}{despesa.id}/', {'purchase_date': '2026-09-01'}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(Transaction.objects.get(pk=despesa.pk).purchase_date)

"""
Limite disponível com uma fórmula só (FATURA-42): limite do cartão menos as
compras pendentes dele, em todas as faturas, na tela do cartão e no
dashboard.
"""
from datetime import date
from decimal import Decimal

from accounts.faturas import obter_fatura
from tests.faturas.base import FaturasTestCase


class LimiteDisponivelTests(FaturasTestCase):

    def setUp(self):
        super().setUp()
        # Cartão de R$ 5.000,00 com R$ 1.200,00 pendentes em duas faturas
        self.cartao_ = self.cartao(10, 20, limit=Decimal('5000.00'))
        self.setembro = obter_fatura(self.cartao_, 9, 2026)
        self.outubro = obter_fatura(self.cartao_, 10, 2026)
        self.compra(self.cartao_, self.setembro, '400.00', date=date(2026, 9, 20))
        self.compra(self.cartao_, self.setembro, '600.00', date=date(2026, 9, 20))
        self.compra(self.cartao_, self.outubro, '200.00', date=date(2026, 10, 20))

    def limites(self):
        """O limite disponível na tela do cartão e no dashboard."""
        cartao = self.client.get(f'/api/credit-cards/{self.cartao_.id}/')
        dashboard = self.client.get('/api/reports/dashboard/', {'month': 9, 'year': 2026})
        self.assertEqual(cartao.status_code, 200)
        self.assertEqual(dashboard.status_code, 200)
        return cartao.data['available_limit'], dashboard.data['credit_cards'][0]['available_limit']

    def test_tela_do_cartao_e_dashboard_mostram_o_limite_menos_as_pendentes(self):
        self.assertEqual(self.limites(), ('3800.00', '3800.00'))

    def test_continuam_iguais_depois_de_um_pagamento_parcial(self):
        resp = self.client.post(f'/api/invoices/{self.setembro.id}/pay/', {
            'account_id': str(self.a.conta.id), 'amount': '700.00', 'date': '2026-09-20',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        # Restam R$ 300,00 da compra dividida mais R$ 200,00 de outubro
        self.assertEqual(self.limites(), ('4500.00', '4500.00'))

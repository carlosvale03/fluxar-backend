from datetime import date
from decimal import Decimal

from transactions.models import Category, Transaction
from tests.isolamento.base import DoisUsuariosTestCase

URL = '/api/budgets/'


class UsoDoOrcamentoTests(DoisUsuariosTestCase):

    def setUp(self):
        self.cliente = self.como(self.a.usuario)
        # Subcategoria de B pendurada à força na categoria do orçamento de A
        self.sub_de_b = Category.objects.create(
            user=self.b.usuario, name='Pendurada B', type='EXPENSE', parent=self.a.categoria,
        )
        # Despesa de A ligada à força a essa subcategoria
        self.despesa(self.sub_de_b, '70.00')

    def despesa(self, categoria, valor):
        return Transaction.objects.create(
            user=self.a.usuario, type='EXPENSE', status='COMPLETED', description='Despesa',
            amount=Decimal(valor), date=date(2026, 9, 5), account=self.a.conta, category=categoria,
        )

    def uso(self):
        resp = self.cliente.get(f'{URL}{self.a.orcamento.id}/')
        self.assertEqual(resp.status_code, 200)
        return resp.data['total_spent'], resp.data['percentage_used'], resp.data['status']

    def test_gasto_nao_soma_despesa_na_subcategoria_de_b(self):
        self.assertEqual(self.uso(), (Decimal('0.00'), Decimal('0.00'), 'OK'))

    def test_gasto_continua_somando_categoria_e_subcategoria_proprias(self):
        self.despesa(self.a.subcategoria, '40.00')
        self.despesa(self.a.categoria, '20.00')

        # 60.00 de 300.00: a despesa de 70.00 na subcategoria de B fica fora
        self.assertEqual(self.uso(), (Decimal('60.00'), Decimal('20.00'), 'OK'))

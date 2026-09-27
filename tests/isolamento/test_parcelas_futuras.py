from datetime import date
from decimal import Decimal

from transactions.models import Transaction
from tests.isolamento.base import DoisUsuariosTestCase

URL = '/api/transactions/'


class EdicaoDeParcelasFuturasSoDoDonoTests(DoisUsuariosTestCase):
    """
    Parcela de B gravada à força na série de parcelas de A, como antes da
    correção: a edição `ALL_FUTURE` muda só as parcelas de A (ISOL-14).
    """

    def setUp(self):
        self.cliente = self.como(self.a.usuario)
        self.p1 = self.parcela(self.a, 1)
        self.p2 = self.parcela(self.a, 2, pai=self.p1)
        self.p3 = self.parcela(self.a, 3, pai=self.p1)
        self.parcela_b = self.parcela(self.b, 3, pai=self.p1, valor='50.00')

    def parcela(self, dados, numero, pai=None, valor='100.00'):
        return Transaction.objects.create(
            user=dados.usuario, type='CREDIT_CARD', status='PENDING',
            description=f'Compra {numero}/3', amount=Decimal(valor),
            date=date(2026, 8 + numero, 5), credit_card=dados.cartao,
            category=dados.categoria, is_installment=True,
            installment_number=numero, installment_total=3, parent_transaction=pai,
        )

    def estado(self, t):
        t.refresh_from_db()
        return (t.user_id, t.amount, t.category_id, t.updated_at)

    def editar_todas_as_futuras(self, parcela):
        resp = self.cliente.patch(
            f'{URL}{parcela.id}/',
            {'amount': '10.00', 'category': str(self.a.subcategoria.id), 'update_scope': 'ALL_FUTURE'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_edicao_a_partir_da_primeira_parcela_nao_muda_a_parcela_de_b(self):
        antes_b = self.estado(self.parcela_b)

        self.editar_todas_as_futuras(self.p1)

        self.assertEqual(self.estado(self.parcela_b), antes_b)
        self.assertEqual(antes_b[:3], (self.b.usuario.id, Decimal('50.00'), self.b.categoria.id))
        for parcela in (self.p1, self.p2, self.p3):
            with self.subTest(parcela=parcela.installment_number):
                self.assertEqual(
                    self.estado(parcela)[:3],
                    (self.a.usuario.id, Decimal('10.00'), self.a.subcategoria.id),
                )

    def test_edicao_a_partir_de_parcela_do_meio_muda_so_as_futuras_de_a(self):
        antes_b = self.estado(self.parcela_b)
        antes_p1 = self.estado(self.p1)

        self.editar_todas_as_futuras(self.p2)

        self.assertEqual(self.estado(self.parcela_b), antes_b)
        self.assertEqual(self.estado(self.p1), antes_p1)
        for parcela in (self.p2, self.p3):
            with self.subTest(parcela=parcela.installment_number):
                self.assertEqual(
                    self.estado(parcela)[:3],
                    (self.a.usuario.id, Decimal('10.00'), self.a.subcategoria.id),
                )

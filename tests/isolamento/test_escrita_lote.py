from datetime import date
from decimal import Decimal

from transactions.models import RecurringTransaction, Transaction
from tests.isolamento.base import DoisUsuariosTestCase

URL = '/api/transactions/bulk-update/'


class EdicaoEmLoteTests(DoisUsuariosTestCase):

    def setUp(self):
        self.cliente = self.como(self.a.usuario)
        self.serie = RecurringTransaction.objects.create(
            user=self.a.usuario, description='Academia', amount=Decimal('80.00'),
            type='EXPENSE', account=self.a.conta, category=self.a.categoria,
            frequency='MONTHLY', start_date=date(2026, 9, 5),
        )
        self.ocorrencias = [
            Transaction.objects.create(
                user=self.a.usuario, type='EXPENSE', status='PENDING',
                description='Academia', amount=Decimal('80.00'), date=date(2026, mes, 5),
                account=self.a.conta, category=self.a.categoria, recurring_source=self.serie,
            )
            for mes in (9, 10, 11)
        ]

    def estado_da_serie(self):
        return list(
            Transaction.objects.filter(recurring_source=self.serie)
            .order_by('date').values_list('category_id', 'description', 'amount')
        )

    def test_categoria_de_b_inexistente_ou_modelo_e_recusada_sem_alterar_ocorrencias(self):
        antes = self.estado_da_serie()
        resp_inexistente = self.cliente.patch(URL, {
            'recurring_source': str(self.serie.id), 'category': self.ID_INEXISTENTE,
            'description': 'Alterada',
        }, format='json')

        for descricao, categoria in (
            ('categoria de B', str(self.b.categoria.id)),
            ('categoria-modelo', str(self.categoria_modelo.id)),
        ):
            with self.subTest(descricao):
                resp = self.cliente.patch(URL, {
                    'recurring_source': str(self.serie.id), 'category': categoria,
                    'description': 'Alterada',
                }, format='json')
                self.assert_mesma_recusa(resp, resp_inexistente, 'category', 'Categoria não encontrada.')

        self.assertEqual(self.estado_da_serie(), antes)
        self.assertEqual(len(antes), 3)
        self.assertFalse(Transaction.objects.filter(category=self.b.categoria).exists())

    def test_edicao_em_lote_com_categoria_de_a_continua_funcionando(self):
        resp = self.cliente.patch(URL, {
            'recurring_source': str(self.serie.id), 'category': str(self.a.subcategoria.id),
            'description': 'Alterada',
        }, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            self.estado_da_serie(),
            [(self.a.subcategoria.id, 'Alterada', Decimal('80.00'))] * 3,
        )

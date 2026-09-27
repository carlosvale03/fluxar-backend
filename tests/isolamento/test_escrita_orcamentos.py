from decimal import Decimal

from budgets.models import Budget
from tests.isolamento.base import DoisUsuariosTestCase

URL = '/api/budgets/'


class EscritaOrcamentoTests(DoisUsuariosTestCase):

    def setUp(self):
        self.cliente = self.como(self.a.usuario)

    def novo(self, categoria):
        return {'category': categoria, 'month': 10, 'year': 2026, 'amount_limit': '150.00'}

    def estado_dos_orcamentos(self):
        return sorted(
            Budget.objects.values_list('user_id', 'category_id', 'month', 'year', 'amount_limit'),
            key=str,
        )

    def assert_criacao_recusada(self, categoria):
        antes = self.estado_dos_orcamentos()
        resp_inexistente = self.cliente.post(URL, self.novo(self.ID_INEXISTENTE), format='json')
        resp = self.cliente.post(URL, self.novo(categoria), format='json')

        self.assert_mesma_recusa(resp, resp_inexistente, 'category', 'Categoria não encontrada.')
        self.assertEqual(self.estado_dos_orcamentos(), antes)
        self.assertFalse(Budget.objects.filter(month=10, year=2026).exists())

    def test_criacao_com_categoria_de_b_e_recusada(self):
        self.assert_criacao_recusada(str(self.b.categoria.id))

    def test_criacao_com_categoria_modelo_e_recusada(self):
        self.assert_criacao_recusada(str(self.categoria_modelo.id))

    def test_edicao_com_categoria_de_b_ou_modelo_e_recusada(self):
        url = f'{URL}{self.a.orcamento.id}/'
        antes = self.estado_dos_orcamentos()
        resp_inexistente = self.cliente.patch(url, {'category': self.ID_INEXISTENTE}, format='json')

        for descricao, categoria in (
            ('categoria de B', str(self.b.categoria.id)),
            ('categoria-modelo', str(self.categoria_modelo.id)),
        ):
            with self.subTest(descricao):
                resp = self.cliente.patch(url, {'category': categoria}, format='json')
                self.assert_mesma_recusa(resp, resp_inexistente, 'category', 'Categoria não encontrada.')

        self.assertEqual(self.estado_dos_orcamentos(), antes)
        self.assertEqual(Budget.objects.get(pk=self.a.orcamento.pk).category, self.a.categoria)

    def test_criacao_com_categoria_de_a_continua_funcionando(self):
        resp = self.cliente.post(URL, self.novo(str(self.a.categoria.id)), format='json')

        self.assertEqual(resp.status_code, 201, resp.data)
        novo = Budget.objects.get(pk=resp.data['id'])
        self.assertEqual(novo.user, self.a.usuario)
        self.assertEqual(novo.category, self.a.categoria)
        self.assertEqual(novo.amount_limit, Decimal('150.00'))

    def test_edicao_com_categoria_de_a_continua_funcionando(self):
        resp = self.cliente.patch(
            f'{URL}{self.a.orcamento.id}/', {'category': str(self.a.subcategoria.id)}, format='json',
        )

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(Budget.objects.get(pk=self.a.orcamento.pk).category, self.a.subcategoria)

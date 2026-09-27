from transactions.models import Category
from tests.isolamento.base import DoisUsuariosTestCase

URL = '/api/categories/'


class EscritaCategoriaPaiTests(DoisUsuariosTestCase):

    def setUp(self):
        self.cliente = self.como(self.a.usuario)

    def pais_recusados(self):
        # (descrição, ID da categoria-pai recusada)
        return [
            ('pai de B', str(self.b.categoria.id)),
            ('pai categoria-modelo', str(self.categoria_modelo.id)),
        ]

    def assert_b_intacto(self):
        self.assertEqual(
            list(Category.objects.filter(parent=self.b.categoria).values_list('id', flat=True)),
            [self.b.subcategoria.id],
        )
        self.assertFalse(Category.objects.filter(parent=self.categoria_modelo).exists())

    def test_criacao_com_pai_alheio_inexistente_ou_modelo_e_recusada(self):
        total_antes = Category.objects.count()
        resp_inexistente = self.cliente.post(URL, {
            'name': 'Nova', 'type': 'EXPENSE', 'parent': self.ID_INEXISTENTE,
        }, format='json')

        for descricao, pai in self.pais_recusados():
            with self.subTest(descricao):
                resp = self.cliente.post(URL, {
                    'name': 'Nova', 'type': 'EXPENSE', 'parent': pai,
                }, format='json')
                self.assert_mesma_recusa(resp, resp_inexistente, 'parent', 'Categoria não encontrada.')

        self.assertEqual(Category.objects.count(), total_antes)
        self.assertFalse(Category.objects.filter(name='Nova').exists())
        self.assert_b_intacto()

    def test_edicao_com_pai_alheio_inexistente_ou_modelo_e_recusada(self):
        categoria = Category.objects.create(user=self.a.usuario, name='Solta', type='EXPENSE')
        url = f'{URL}{categoria.id}/'
        resp_inexistente = self.cliente.patch(url, {'parent': self.ID_INEXISTENTE}, format='json')

        for descricao, pai in self.pais_recusados():
            with self.subTest(descricao):
                resp = self.cliente.patch(url, {'parent': pai}, format='json')
                self.assert_mesma_recusa(resp, resp_inexistente, 'parent', 'Categoria não encontrada.')

        categoria.refresh_from_db()
        self.assertIsNone(categoria.parent_id)
        self.assert_b_intacto()

    def test_subcategoria_sob_categoria_propria_continua_funcionando(self):
        resp = self.cliente.post(URL, {
            'name': 'Nova', 'type': 'EXPENSE', 'parent': str(self.a.categoria.id),
        }, format='json')

        self.assertEqual(resp.status_code, 201, resp.data)
        nova = Category.objects.get(pk=resp.data['id'])
        self.assertEqual(nova.user, self.a.usuario)
        self.assertEqual(nova.parent, self.a.categoria)

        solta = Category.objects.create(user=self.a.usuario, name='Solta', type='EXPENSE')
        resp_edicao = self.cliente.patch(
            f'{URL}{solta.id}/', {'parent': str(self.a.categoria.id)}, format='json',
        )

        self.assertEqual(resp_edicao.status_code, 200, resp_edicao.data)
        solta.refresh_from_db()
        self.assertEqual(solta.parent, self.a.categoria)

from transactions.models import Category
from tests.isolamento.base import DoisUsuariosTestCase

URL = '/api/categories/'


class LeituraArvoreDeCategoriasTests(DoisUsuariosTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Subcategoria de B pendurada à força numa categoria de A, como antes da correção
        cls.sub_de_b = Category.objects.create(
            user=cls.b.usuario, name='Intrusa B', type='EXPENSE', parent=cls.a.categoria,
        )

    def test_a_nao_ve_na_arvore_a_subcategoria_de_b(self):
        cliente = self.como(self.a.usuario)

        lista = cliente.get(URL)
        detalhe = cliente.get(f'{URL}{self.a.categoria.id}/')

        self.assertEqual(lista.status_code, 200)
        categoria_na_lista = next(c for c in lista.data if c['id'] == str(self.a.categoria.id))
        self.assertEqual([s['name'] for s in categoria_na_lista['subcategories']], ['Feira A'])
        self.assertNotIn('Intrusa B', str(lista.data))
        self.assertNotIn(str(self.sub_de_b.id), str(lista.data))

        self.assertEqual(detalhe.status_code, 200)
        self.assertEqual([s['id'] for s in detalhe.data['subcategories']], [str(self.a.subcategoria.id)])
        self.assertNotIn('Intrusa B', str(detalhe.data))

    def test_b_nao_recebe_o_nome_da_categoria_de_a(self):
        cliente = self.como(self.b.usuario)

        forjada = cliente.get(f'{URL}{self.sub_de_b.id}/')
        normal = cliente.get(f'{URL}{self.b.subcategoria.id}/')

        self.assertEqual(forjada.status_code, 200)
        self.assertIsNone(forjada.data['parent'])
        self.assertIsNone(forjada.data['parent_name'])
        self.assertNotIn('Mercado A', str(forjada.data))
        self.assertNotIn(str(self.a.categoria.id), str(forjada.data))
        # A subcategoria sob categoria própria continua mostrando o pai
        self.assertEqual(normal.status_code, 200)
        self.assertEqual(normal.data['parent'], self.b.categoria.id)
        self.assertEqual(normal.data['parent_name'], 'Mercado B')

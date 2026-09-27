from decimal import Decimal

from budgets.models import Budget
from transactions.models import Category
from tests.isolamento.base import DoisUsuariosTestCase

URL = '/api/budgets/'


class LeituraDoOrcamentoTests(DoisUsuariosTestCase):

    def setUp(self):
        self.cliente = self.como(self.a.usuario)
        # Ícone e cor para conferir que nada da categoria alheia aparece
        Category.objects.filter(pk=self.b.categoria.pk).update(icon='icone-b', color='#bbbbbb')
        Category.objects.filter(pk=self.categoria_modelo.pk).update(icon='icone-modelo', color='#cccccc')

    def forjar_orcamento(self, categoria):
        # Ligação cruzada gravada à força, como antes da correção
        return Budget.objects.create(
            user=self.a.usuario, category=categoria, month=10, year=2026,
            amount_limit=Decimal('100.00'),
        )

    def item_da_lista(self, orcamento_id):
        resp = self.cliente.get(URL, {'month': 10, 'year': 2026})
        self.assertEqual(resp.status_code, 200)
        itens = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        return next(item for item in itens if item['id'] == str(orcamento_id))

    def assert_sem_a_categoria(self, orcamento, categoria, textos):
        detalhe = self.cliente.get(f'{URL}{orcamento.id}/')
        self.assertEqual(detalhe.status_code, 200)

        for dados in (detalhe.data, self.item_da_lista(orcamento.id)):
            self.assertIsNone(dados['category'])
            self.assertIsNone(dados['category_detail'])
            texto = str(dados)
            self.assertNotIn(str(categoria.id), texto)
            for trecho in textos:
                self.assertNotIn(trecho, texto)

    def test_orcamento_de_a_com_categoria_de_b_nao_mostra_a_categoria(self):
        orcamento = self.forjar_orcamento(self.b.categoria)

        self.assert_sem_a_categoria(
            orcamento, self.b.categoria, ('Mercado B', 'Feira B', 'icone-b', '#bbbbbb'),
        )

    def test_orcamento_de_a_com_categoria_modelo_nao_mostra_a_categoria(self):
        orcamento = self.forjar_orcamento(self.categoria_modelo)

        self.assert_sem_a_categoria(
            orcamento, self.categoria_modelo, ('Modelo', 'icone-modelo', '#cccccc'),
        )

    def test_formato_do_orcamento_com_categoria_propria_nao_muda(self):
        Category.objects.filter(pk=self.a.categoria.pk).update(icon='icone-a', color='#aaaaaa')

        detalhe = self.cliente.get(f'{URL}{self.a.orcamento.id}/')

        self.assertEqual(detalhe.status_code, 200)
        self.assertEqual(detalhe.data['category'], self.a.categoria.id)
        self.assertEqual(detalhe.data['category_detail']['id'], str(self.a.categoria.id))
        self.assertEqual(detalhe.data['category_detail']['name'], 'Mercado A')
        self.assertEqual(detalhe.data['category_detail']['icon'], 'icone-a')
        self.assertEqual(detalhe.data['category_detail']['color'], '#aaaaaa')
        self.assertEqual(
            [sub['name'] for sub in detalhe.data['category_detail']['subcategories']], ['Feira A'],
        )
        resp = self.cliente.get(URL, {'month': 9, 'year': 2026})
        itens = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual([item for item in itens if item['id'] == str(self.a.orcamento.id)], [detalhe.data])

from decimal import Decimal

from budgets.models import Budget
from tests.isolamento.base import DoisUsuariosTestCase

URL = '/api/budgets/bulk_import/'


class ImportacaoDeOrcamentosSemCategoriaAlheiaTests(DoisUsuariosTestCase):
    """
    Orçamentos de A ligados à força à categoria de B e à categoria-modelo, como
    antes da correção: a importação para outro mês não copia essas ligações
    (ISOL-01, ISOL-10).
    """

    def setUp(self):
        self.cliente = self.como(self.a.usuario)
        self.orcamento_categoria_b = self.forjar(self.b.categoria)
        self.orcamento_modelo = self.forjar(self.categoria_modelo)

    def forjar(self, categoria):
        return Budget.objects.create(
            user=self.a.usuario, category=categoria, month=9, year=2026,
            amount_limit=Decimal('100.00'),
        )

    def importar(self, *orcamentos):
        return self.cliente.post(
            URL, {'source_ids': [str(o.id) for o in orcamentos], 'month': 10, 'year': 2026},
            format='json',
        )

    def orcamentos_de_outubro(self):
        return list(
            Budget.objects.filter(month=10, year=2026)
            .values_list('user_id', 'category_id', 'amount_limit')
        )

    def test_importa_so_os_orcamentos_de_categorias_proprias(self):
        resp = self.importar(self.a.orcamento, self.orcamento_categoria_b, self.orcamento_modelo)

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual((resp.data['imported_count'], resp.data['skipped_count']), (1, 2))
        self.assertEqual(
            self.orcamentos_de_outubro(),
            [(self.a.usuario.id, self.a.categoria.id, Decimal('300.00'))],
        )
        self.assertFalse(Budget.objects.filter(category=self.b.categoria, month=10).exists())
        self.assertFalse(Budget.objects.filter(category=self.categoria_modelo, month=10).exists())

    def test_so_orcamentos_de_categoria_alheia_nao_criam_nada(self):
        resp = self.importar(self.orcamento_categoria_b, self.orcamento_modelo)

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['skipped'], 2)
        self.assertEqual(self.orcamentos_de_outubro(), [])

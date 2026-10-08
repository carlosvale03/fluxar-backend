"""
Sugestão de categoria pelas correções do usuário (IMPORT-43, IMPORT-44,
IMPORT-47, IMPORT-49).

A linha sem categoria no arquivo recebe a categoria da correção mais
recente do mesmo usuário para a mesma descrição normalizada, quando essa
categoria existe, está ativa e tem o tipo da linha.
"""
from datetime import timedelta

from django.utils import timezone

from transactions.models import Category, CorrecaoDeCategoria, Transaction

from .base import MAPEAMENTO, arquivo_csv
from .test_gravacao import CABECALHO, GravacaoTestCase

URL_TRANSACOES = '/api/transactions/'


class SugestaoTestCase(GravacaoTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.transporte = Category.objects.create(user=cls.a.usuario, name='Transporte', type='EXPENSE')
        cls.lazer = Category.objects.create(user=cls.a.usuario, name='Lazer', type='EXPENSE')

    def corrigir(self, descricao_normalizada, categoria, usuario=None, ha_minutos=0):
        correcao = CorrecaoDeCategoria.objects.create(
            user=usuario or self.a.usuario, descricao=descricao_normalizada,
            descricao_normalizada=descricao_normalizada, categoria_depois=categoria,
        )
        CorrecaoDeCategoria.objects.filter(pk=correcao.pk).update(
            criada_em=timezone.now() - timedelta(minutes=ha_minutos),
        )

    def importar_linhas(self, *linhas, cabecalho=CABECALHO, mapeamento=MAPEAMENTO):
        resp = self.importar(arquivo_csv([cabecalho, *linhas]), mapeamento=mapeamento)
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp

    def unica_do_lote(self, resp):
        return self.do_lote(resp).get()


class SugestaoTests(SugestaoTestCase):

    def test_independent_test_da_correcao_a_sugestao(self):
        """IMPORT-42 a IMPORT-44: a troca de "UBER *TRIP 1234" sugere Transporte para "UBER *TRIP 5678"."""
        primeira = self.importar_linhas(['10/09/2026', 'UBER *TRIP 1234', '-23,90'])
        transacao = self.unica_do_lote(primeira)
        self.assertEqual((transacao.category, primeira.data['suggested']), (None, 0))
        resp = self.client.patch(
            f'{URL_TRANSACOES}{transacao.pk}/', {'category': str(self.transporte.pk)}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)

        segunda = self.importar_linhas(['12/09/2026', 'UBER *TRIP 5678', '-31,50'])

        self.assertEqual((segunda.data['imported'], segunda.data['suggested']), (1, 1))
        sugerida = self.unica_do_lote(segunda)
        self.assertEqual((sugerida.category, sugerida.categoria_sugerida), (self.transporte, True))
        lista = self.client.get(URL_TRANSACOES, {'import_batch': segunda.data['batch_id'], 'suggested_category': 'true'})
        self.assertEqual([item['category_suggested'] for item in lista.data['results']], [True])

    def test_vale_a_correcao_mais_recente(self):
        """IMPORT-43: duas correções para a mesma descrição, vale a mais recente."""
        self.corrigir('padaria sao joao', self.transporte, ha_minutos=10)
        self.corrigir('padaria sao joao', self.lazer, ha_minutos=1)

        resp = self.importar_linhas(['10/09/2026', 'PADARIA SÃO JOÃO 77', '-8,00'])

        self.assertEqual(resp.data['suggested'], 1)
        self.assertEqual(self.unica_do_lote(resp).category, self.lazer)

    def test_linha_com_categoria_no_arquivo_mantem_a_do_arquivo(self):
        """Assumption "Linhas com categoria no arquivo": a do arquivo vale, sem sugestão."""
        self.corrigir('uber *trip', self.transporte)
        mapeamento = {**MAPEAMENTO, 'category_column': 'Categoria'}

        resp = self.importar_linhas(
            ['10/09/2026', 'UBER *TRIP 5678', '-31,50', 'Lazer'],
            ['11/09/2026', 'UBER *TRIP 9999', '-12,00', ''],
            cabecalho=[*CABECALHO, 'Categoria'], mapeamento=mapeamento,
        )

        self.assertEqual((resp.data['imported'], resp.data['suggested']), (2, 1))
        da_planilha = self.do_lote(resp).get(description='UBER *TRIP 5678')
        self.assertEqual((da_planilha.category, da_planilha.categoria_sugerida), (self.lazer, False))
        sugerida = self.do_lote(resp).get(description='UBER *TRIP 9999')
        self.assertEqual((sugerida.category, sugerida.categoria_sugerida), (self.transporte, True))

    def test_categoria_excluida_ou_de_outro_tipo_nao_e_sugerida(self):
        """IMPORT-47: a correção mais recente com categoria excluída deixa a linha sem sugestão."""
        excluida = Category.objects.create(user=self.a.usuario, name='Antiga', type='EXPENSE')
        self.corrigir('cinema', self.lazer, ha_minutos=10)
        self.corrigir('cinema', excluida, ha_minutos=1)
        resp = self.client.delete(f'/api/categories/{excluida.pk}/')
        self.assertEqual(resp.status_code, 204)
        self.corrigir('livraria', None)  # categoria apagada do banco
        self.corrigir('pix recebido', self.transporte)  # despesa para uma linha de receita

        resp = self.importar_linhas(
            ['10/09/2026', 'CINEMA 2', '-40,00'],
            ['10/09/2026', 'LIVRARIA', '-55,00'],
            ['10/09/2026', 'PIX RECEBIDO', '100,00'],
        )

        self.assertEqual((resp.data['imported'], resp.data['suggested']), (3, 0))
        self.assertEqual(
            list(self.do_lote(resp).values_list('category', 'categoria_sugerida')),
            [(None, False)] * 3,
        )

    def test_correcoes_de_outro_usuario_nunca_sao_usadas(self):
        """IMPORT-49: a correção de B não sugere nada na importação de A."""
        categoria_de_b = Category.objects.create(user=self.b.usuario, name='Transporte B', type='EXPENSE')
        self.corrigir('uber *trip', categoria_de_b, usuario=self.b.usuario)

        resp = self.importar_linhas(['10/09/2026', 'UBER *TRIP 5678', '-31,50'])

        self.assertEqual(resp.data['suggested'], 0)
        transacao = self.unica_do_lote(resp)
        self.assertEqual((transacao.category, transacao.categoria_sugerida), (None, False))
        self.assertFalse(Transaction.objects.filter(category=categoria_de_b).exists())

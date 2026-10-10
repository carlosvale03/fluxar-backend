"""
Relatório de gastos puxados: `GET /api/reports/linked-expenses/`
(VINCULO-20, VINCULO-34 e VINCULO-35).
"""
from datetime import date

from django.core.cache import cache

from core import travas
from tests.permissoes.base import fechar, liberacao_de_testes
from transactions.models import Category
from transactions.vinculos import vincular

from .base import VinculosTestCase, compra, despesa

URL = '/api/reports/linked-expenses/'
SETEMBRO = {'month': 9, 'year': 2026}
OUTUBRO = {'month': 10, 'year': 2026}


class RelatorioTestCase(VinculosTestCase):

    def setUp(self):
        super().setUp()
        cache.clear()
        travas.invalidar()
        self.addCleanup(travas.invalidar)

    def relatorio(self, parametros):
        resposta = self.client.get(URL, parametros)
        self.assertEqual(resposta.status_code, 200, getattr(resposta, 'data', None))
        return resposta.data

    def passeio(self, dia, transporte='60.00', dia_do_transporte=None, categoria_do_transporte='transporte'):
        cinema = despesa(self.a, 'Cinema', '50.00', dia=dia, categoria=self.a.cinema)
        categoria = getattr(self.a, categoria_do_transporte) if categoria_do_transporte else None
        ida = despesa(self.a, 'Transporte', transporte, dia=dia_do_transporte or dia, categoria=categoria)
        vincular(ida, cinema)
        return cinema, ida

    def grupo(self, categoria, total, *puxados):
        return {
            'category_id': str(categoria.pk), 'category_name': categoria.name, 'color': categoria.color,
            'total': total,
            'pulled': [
                {'category_id': str(c.pk), 'category_name': c.name, 'color': c.color, 'amount': valor}
                for c, valor in puxados
            ],
        }


class AgrupamentoTests(RelatorioTestCase):

    def test_tres_cinemas_com_transporte_de_60_dao_lazer_puxando_180_de_transporte(self):
        for dia in (5, 12, 20):
            self.passeio(date(2026, 9, dia))

        dados = self.relatorio(SETEMBRO)

        self.assertEqual(dados['groups'], [self.grupo(self.a.lazer, '180.00', (self.a.transporte, '180.00'))])
        self.assertEqual(dados['period'], {'start_date': '2026-09-01', 'end_date': '2026-09-30'})

    def test_transporte_do_mes_seguinte_entra_no_mes_seguinte(self):
        self.passeio(date(2026, 9, 30), dia_do_transporte=date(2026, 10, 1))

        self.assertEqual(self.relatorio(SETEMBRO)['groups'], [])
        self.assertEqual(
            self.relatorio(OUTUBRO)['groups'], [self.grupo(self.a.lazer, '60.00', (self.a.transporte, '60.00'))],
        )

    def test_sem_categoria_e_subcategoria_entram_pela_raiz(self):
        metro = Category.objects.create(user=self.a.usuario, name='Metrô A', type='EXPENSE', parent=self.a.transporte)
        neto = Category.objects.create(user=self.a.usuario, name='Linha 1 A', type='EXPENSE', parent=metro)
        cinema, _ = self.passeio(date(2026, 9, 12), transporte='30.00', categoria_do_transporte=None)
        vincular(despesa(self.a, 'Metrô', '7.50', categoria=neto), cinema)
        vincular(despesa(self.a, 'Ônibus', '4.50', categoria=metro), cinema)
        # Lazer puxando Lazer fica na própria categoria
        vincular(despesa(self.a, 'Fliperama', '25.00', categoria=self.a.lazer), cinema)

        [grupo] = self.relatorio(SETEMBRO)['groups']

        self.assertEqual(grupo['total'], '67.00')
        self.assertEqual(grupo['pulled'], [
            {'category_id': None, 'category_name': 'Sem categoria', 'color': '#CBD5E1', 'amount': '30.00'},
            {'category_id': str(self.a.lazer.pk), 'category_name': 'Lazer A', 'color': '#AA0000', 'amount': '25.00'},
            {'category_id': str(self.a.transporte.pk), 'category_name': 'Transporte A', 'color': '#0000AA',
             'amount': '12.00'},
        ])

    def test_grupos_do_maior_total_para_o_menor(self):
        self.passeio(date(2026, 9, 5), transporte='10.00')
        jantar = despesa(self.a, 'Jantar', '90.00', categoria=self.a.alimentacao)
        vincular(despesa(self.a, 'Táxi', '35.00', categoria=self.a.transporte), jantar)

        grupos = self.relatorio(SETEMBRO)['groups']

        self.assertEqual([(g['category_name'], g['total']) for g in grupos], [
            ('Alimentação A', '35.00'), ('Lazer A', '10.00'),
        ])


class RegrasDeDespesaTests(RelatorioTestCase):
    """VINCULO-35: as mesmas regras de tipo e período dos gráficos de despesa."""

    def test_parcelas_entram_cada_uma_no_mes_dela_e_pendentes_ficam_de_fora(self):
        cinema = despesa(self.a, 'Cinema', '50.00', categoria=self.a.cinema)
        jantar = compra(self.a, 'Jantar', '120.00', parcelas=3, dia=date(2026, 9, 12), categoria=self.a.alimentacao)
        vincular(jantar[2], cinema)
        vincular(despesa(self.a, 'Uber', '22.00', categoria=self.a.transporte, status='PENDING'), cinema)

        for parametros in (SETEMBRO, OUTUBRO):
            with self.subTest(**parametros):
                self.assertEqual(
                    self.relatorio(parametros)['groups'],
                    [self.grupo(self.a.lazer, '40.00', (self.a.alimentacao, '40.00'))],
                )

    def test_mes_sem_vinculos_devolve_grupos_vazios(self):
        despesa(self.a, 'Mercado', '200.00', categoria=self.a.alimentacao)
        dados = self.relatorio({'month': 8, 'year': 2026})
        self.assertEqual(dados, {'groups': [], 'period': {'start_date': '2026-08-01', 'end_date': '2026-08-31'}})

    def test_vinculos_de_outro_usuario_nao_entram(self):
        cinema_b = despesa(self.b, 'Cinema B', '50.00', categoria=self.b.lazer)
        vincular(despesa(self.b, 'Transporte B', '60.00', categoria=self.b.transporte), cinema_b)
        self.assertEqual(self.relatorio(SETEMBRO)['groups'], [])


class TravaTests(RelatorioTestCase):
    """VINCULO-20."""

    def test_com_o_recurso_travado_o_relatorio_recebe_403(self):
        liberacao_de_testes(False)
        fechar('vinculos')
        resposta = self.client.get(URL, SETEMBRO)
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(resposta.data, {
            'detail': 'Este recurso não está disponível no seu plano.', 'code': 'plan_locked', 'feature': 'vinculos',
        })

    def test_parametro_desconhecido_recebe_400(self):
        resposta = self.client.get(URL, {'principalId': 'x'})
        self.assertEqual(resposta.status_code, 400)

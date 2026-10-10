"""
Custo total e principal na API (VINCULO-15, VINCULO-26 a VINCULO-28).
"""
from datetime import date

from django.db import connection
from django.test.utils import CaptureQueriesContext

from transactions.vinculos import vincular

from .base import VinculosTestCase, compra, despesa

URL_GRAFICOS = '/api/reports/charts/simple/'


class CustoTotalTestCase(VinculosTestCase):

    def setUp(self):
        super().setUp()
        self.cinema = despesa(self.a, 'Cinema', '50.00', categoria=self.a.cinema)
        self.transporte = despesa(self.a, 'Transporte', '45.00', categoria=self.a.transporte)

    def detalhe(self, transacao):
        resposta = self.client.get(f'/api/transactions/{transacao.pk}/')
        self.assertEqual(resposta.status_code, 200, resposta.data)
        return resposta.data

    def campos(self, dados):
        return {campo: dados[campo] for campo in ('principal', 'principal_detail', 'dependents_count', 'total_cost')}


class PrincipalEDependenteTests(CustoTotalTestCase):

    def test_principal_devolve_o_custo_total_e_a_quantidade_de_dependentes(self):
        vincular(self.transporte, self.cinema)
        self.assertEqual(self.campos(self.detalhe(self.cinema)), {
            'principal': None, 'principal_detail': None, 'dependents_count': 1, 'total_cost': '95.00',
        })

    def test_dependente_devolve_a_principal_com_descricao_e_data(self):
        vincular(self.transporte, self.cinema)
        self.assertEqual(self.campos(self.detalhe(self.transporte)), {
            'principal': str(self.cinema.pk),
            'principal_detail': {'id': str(self.cinema.pk), 'description': 'Cinema', 'date': '2026-09-12'},
            'dependents_count': 0,
            'total_cost': None,
        })

    def test_transacao_sem_vinculo_tem_os_campos_vazios(self):
        self.assertEqual(self.campos(self.detalhe(self.cinema)), {
            'principal': None, 'principal_detail': None, 'dependents_count': 0, 'total_cost': None,
        })

    def test_excluir_a_dependente_tira_o_valor_dela_do_custo(self):
        pipoca = despesa(self.a, 'Pipoca', '20.00')
        vincular(self.transporte, self.cinema)
        vincular(pipoca, self.cinema)
        self.assertEqual(self.detalhe(self.cinema)['total_cost'], '115.00')

        self.assertEqual(self.client.delete(f'/api/transactions/{self.transporte.pk}/').status_code, 204)

        dados = self.detalhe(self.cinema)
        self.assertEqual((dados['dependents_count'], dados['total_cost']), (1, '70.00'))


class ParcelasTests(CustoTotalTestCase):
    """VINCULO-27."""

    def test_jantar_em_3_parcelas_de_40_soma_120_no_custo_do_cinema(self):
        parcelas = compra(self.a, 'Jantar', '120.00', parcelas=3, categoria=self.a.alimentacao)
        vincular(parcelas[1], self.cinema)

        self.assertEqual(self.detalhe(self.cinema)['total_cost'], '170.00')
        for parcela in parcelas:
            with self.subTest(parcela=parcela.installment_number):
                dados = self.detalhe(parcela)
                self.assertEqual(dados['principal'], str(self.cinema.pk))
                self.assertEqual(dados['principal_detail']['description'], 'Cinema')

    def test_compra_parcelada_principal_soma_todas_as_parcelas_em_cada_uma(self):
        parcelas = compra(self.a, 'Show', '300.00', parcelas=3, dia=date(2026, 9, 3), categoria=self.a.lazer)
        vincular(self.transporte, parcelas[2])

        for parcela in parcelas:
            with self.subTest(parcela=parcela.installment_number):
                dados = self.detalhe(parcela)
                self.assertEqual((dados['dependents_count'], dados['total_cost']), (1, '345.00'))
        # A dependente mostra a compra pela raiz, com a data da compra
        self.assertEqual(self.detalhe(self.transporte)['principal_detail'], {
            'id': str(parcelas[0].pk), 'description': 'Show (1/3)', 'date': '2026-09-03',
        })


class TotaisELista(CustoTotalTestCase):
    """VINCULO-28 e a lista sem uma consulta por linha."""

    def test_grafico_por_categoria_continua_igual_com_o_vinculo(self):
        parametros = {'month': 9, 'year': 2026}
        antes = self.client.get(URL_GRAFICOS, parametros).data['expense_by_category']

        vincular(self.transporte, self.cinema)

        depois = self.client.get(URL_GRAFICOS, parametros).data['expense_by_category']
        self.assertEqual(depois, antes)
        por_nome = {item['category_name']: item['amount'] for item in depois}
        self.assertEqual(por_nome, {'Lazer A': '50.00', 'Transporte A': '45.00'})

    def consultas_de_transacoes_na_lista(self):
        with CaptureQueriesContext(connection) as consultas:
            resposta = self.client.get('/api/transactions/', {'page_size': 50})
        self.assertEqual(resposta.status_code, 200)
        linhas = resposta.data['results']
        return len(linhas), sum('"transactions_transaction"' in c['sql'] for c in consultas.captured_queries), linhas

    def test_lista_com_20_vinculadas_nao_faz_uma_consulta_por_linha(self):
        vincular(self.transporte, self.cinema)
        quantas, consultas_com_2, _ = self.consultas_de_transacoes_na_lista()
        self.assertEqual(quantas, 2)

        for numero in range(18):
            vincular(despesa(self.a, f'Extra {numero}', '1.00'), self.cinema)
        quantas, consultas_com_20, linhas = self.consultas_de_transacoes_na_lista()

        self.assertEqual(quantas, 20)
        self.assertEqual(consultas_com_20, consultas_com_2)
        [cinema] = [linha for linha in linhas if linha['id'] == str(self.cinema.pk)]
        self.assertEqual((cinema['dependents_count'], cinema['total_cost']), (19, '113.00'))

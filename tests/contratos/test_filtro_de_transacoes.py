"""
Mesmo filtro na lista de transações, nas exportações e nos relatórios
(CONTRATO-10, CONTRATO-11, CONTRATO-13, CONTRATO-15, CONTRATO-22, AD-022).
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from data_exchange.services import ExportService
from transactions.models import Category, RecurringTransaction

from .base import URL_TRANSACOES, ContratosTestCase

URL_PDF = '/api/export/transactions/pdf/'
URL_XLS = '/api/export/transactions/xls/'


class FiltroDeTransacoesTestCase(ContratosTestCase):

    def ids_na_lista(self, parametros):
        resp = self.client.get(URL_TRANSACOES, {**parametros, 'page_size': 100})
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = [item['id'] for item in resp.data['results']]
        self.assertEqual(len(ids), resp.data['count'])
        return ids

    def ids_exportados(self, url, parametros):
        metodo = 'generate_pdf' if url == URL_PDF else 'generate_xls'
        with patch.object(ExportService, metodo, return_value=b'arquivo') as gerador:
            resp = self.client.get(url, parametros)
        self.assertEqual(resp.status_code, 200)
        return [str(t.id) for t in gerador.call_args.args[0]]

    def assert_mesmo_conjunto(self, parametros, esperados):
        """A lista e as duas exportações devolvem exatamente `esperados`, uma vez cada."""
        esperados = sorted(str(t.id) for t in esperados)
        self.assertEqual(sorted(self.ids_na_lista(parametros)), esperados, 'lista')
        self.assertEqual(sorted(self.ids_exportados(URL_PDF, parametros)), esperados, 'pdf')
        self.assertEqual(sorted(self.ids_exportados(URL_XLS, parametros)), esperados, 'xls')


class VariasCategoriasTests(FiltroDeTransacoesTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        u = cls.a.usuario
        cls.alimentacao = Category.objects.create(user=u, name='Alimentação', type='EXPENSE')
        cls.restaurante = Category.objects.create(user=u, name='Restaurante', type='EXPENSE', parent=cls.alimentacao)
        cls.mercado = Category.objects.create(user=u, name='Mercado', type='EXPENSE', parent=cls.alimentacao)
        cls.transporte = Category.objects.create(user=u, name='Transporte', type='EXPENSE')
        cls.lazer = Category.objects.create(user=u, name='Lazer', type='EXPENSE')

    def setUp(self):
        super().setUp()
        self.t_alim = self.lancar(category=self.alimentacao)
        self.t_rest = self.lancar(category=self.restaurante)
        self.t_merc = self.lancar(category=self.mercado)
        self.t_transp = self.lancar(category=self.transporte)
        self.t_lazer = self.lancar(category=self.lazer)

    def test_pai_com_subcategorias_e_outra_categoria(self):
        self.assert_mesmo_conjunto(
            {'categoryId': [self.alimentacao.pk, self.transporte.pk]},
            [self.t_alim, self.t_rest, self.t_merc, self.t_transp],
        )

    def test_pai_sem_subcategorias_traz_so_as_dele(self):
        self.assert_mesmo_conjunto({'categoryId': [self.transporte.pk]}, [self.t_transp])

    def test_pai_e_filha_juntos_nao_repetem(self):
        self.assert_mesmo_conjunto(
            {'categoryId': [self.alimentacao.pk, self.mercado.pk]},
            [self.t_alim, self.t_rest, self.t_merc],
        )

    def test_descendentes_em_qualquer_nivel_inclusive_inativas(self):
        neta = Category.objects.create(
            user=self.a.usuario, name='Pizzaria', type='EXPENSE', parent=self.restaurante, is_active=False,
        )
        t_neta = self.lancar(category=neta)
        self.assert_mesmo_conjunto(
            {'categoryId': [self.alimentacao.pk]}, [self.t_alim, self.t_rest, self.t_merc, t_neta],
        )

    def test_categoria_de_outro_usuario_nao_traz_nada(self):
        filha_de_b = Category.objects.create(
            user=self.b.usuario, name='Filha de B', type='EXPENSE', parent=self.b.despesa,
        )
        self.lancar(usuario=self.b, category=self.b.despesa)
        self.lancar(usuario=self.b, category=filha_de_b)

        self.assert_mesmo_conjunto({'categoryId': [self.b.despesa.pk]}, [])


class TipoEPeriodoTests(FiltroDeTransacoesTestCase):

    def test_despesas_incluem_compras_no_cartao(self):
        despesa = self.lancar('EXPENSE')
        compra = self.lancar('CREDIT_CARD')
        self.lancar('INCOME')
        self.lancar('INVOICE_PAYMENT')
        self.lancar('TRANSFER_OUT', transfer_id=uuid.uuid4())

        self.assert_mesmo_conjunto({'type': 'EXPENSE'}, [despesa, compra])

    def test_tipo_invalido(self):
        resp = self.client.get(URL_TRANSACOES, {'type': 'ROXO'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('type', resp.data)

    def test_data_com_hora_e_recusada(self):
        for url in (URL_TRANSACOES, URL_PDF, URL_XLS):
            resp = self.client.get(url, {'startDate': '2026-09-01T03:00:00Z'})
            self.assertEqual(resp.status_code, 400, url)
            self.assertEqual(resp.data['startDate'], ['Data inválida. Use o formato AAAA-MM-DD.'], url)
            resp = self.client.get(url, {'endDate': '30/09/2026'})
            self.assertEqual(resp.data['endDate'], ['Data inválida. Use o formato AAAA-MM-DD.'], url)

    def test_fim_do_periodo_nao_inclui_o_dia_seguinte(self):
        primeiro = self.lancar(date=date(2026, 9, 1))
        ultimo = self.lancar(date=date(2026, 9, 30))
        self.lancar(date=date(2026, 10, 1))
        self.lancar(date=date(2026, 8, 31))

        self.assert_mesmo_conjunto({'startDate': '2026-09-01', 'endDate': '2026-09-30'}, [primeiro, ultimo])

    def test_relatorio_usa_o_mesmo_significado_de_despesa(self):
        dia = date.today() - timedelta(days=2)
        self.lancar('EXPENSE', '50.00', date=dia)
        self.lancar('CREDIT_CARD', '30.00', date=dia)
        self.lancar('INCOME', '100.00', date=dia)

        resp = self.client.get(URL_TRANSACOES, {'type': 'EXPENSE', 'startDate': dia.isoformat()})
        soma_da_lista = sum(Decimal(item['amount']) for item in resp.data['results'])
        relatorio = self.client.get('/api/reports/dashboard/', {'days': 30})

        self.assertEqual(soma_da_lista, Decimal('80.00'))
        self.assertEqual(Decimal(str(relatorio.data['summary']['monthly_expense'])), Decimal('80.00'))


class RecorrentesETransferenciasTests(FiltroDeTransacoesTestCase):

    def test_so_transacoes_de_serie(self):
        serie = RecurringTransaction.objects.create(
            user=self.a.usuario, description='Aluguel', amount=Decimal('900.00'), type='EXPENSE',
            account=self.a.conta, frequency='MONTHLY', start_date=date(2026, 9, 1),
        )
        da_serie = self.lancar(recurring_source=serie)
        self.lancar()

        self.assertEqual(self.ids_na_lista({'is_recurring': 'true'}), [str(da_serie.id)])

    def test_transfer_id_devolve_as_duas_pernas(self):
        grupo = uuid.uuid4()
        saida = self.lancar('TRANSFER_OUT', transfer_id=grupo)
        entrada = self.lancar('TRANSFER_IN', transfer_id=grupo)
        self.lancar('TRANSFER_OUT', transfer_id=uuid.uuid4())

        self.assertEqual(sorted(self.ids_na_lista({'transfer_id': grupo})), sorted([str(saida.id), str(entrada.id)]))

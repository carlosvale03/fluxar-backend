from datetime import date
from decimal import Decimal

from transactions.models import Category, Transaction
from tests.isolamento.base import DoisUsuariosTestCase

URL_TAG = '/api/reports/charts/tag-insights/'


class MonitorDeFocoNoRelatorioTests(DoisUsuariosTestCase):

    def test_monitor_de_a_nao_usa_subcategoria_de_b_sob_a_categoria_monitorada(self):
        # Subcategoria de B pendurada à força na categoria monitorada por A, e uma
        # transação de A ligada a ela, como antes da correção
        sub_de_b = Category.objects.create(
            user=self.b.usuario, name='Intrusa B', type='EXPENSE', parent=self.a.categoria,
        )
        hoje = date.today()
        Transaction.objects.create(
            user=self.a.usuario, type='EXPENSE', status='COMPLETED', description='Forjada',
            amount=Decimal('500.00'), date=hoje, account=self.a.conta, category=sub_de_b,
        )
        # A subcategoria própria continua entrando na soma do monitor
        Transaction.objects.create(
            user=self.a.usuario, type='EXPENSE', status='COMPLETED', description='Feira',
            amount=Decimal('40.00'), date=hoje, account=self.a.conta, category=self.a.subcategoria,
        )

        resp = self.como(self.a.usuario).get('/api/reports/charts/advanced/')

        self.assertEqual(resp.status_code, 200)
        monitor = next(m for m in resp.data['custom_monitoring'] if m['id'] == str(self.a.monitor.id))
        self.assertEqual(monitor['name'], 'Mercado A')
        self.assertEqual(monitor['current_month'], '40.00')


class RelatorioDeTagTests(DoisUsuariosTestCase):

    def setUp(self):
        self.cliente = self.como(self.a.usuario)

    def test_tag_de_b_responde_404_igual_a_tag_inexistente(self):
        resp_inexistente = self.cliente.get(URL_TAG, {'tag_id': self.ID_INEXISTENTE})
        resp = self.cliente.get(URL_TAG, {'tag_id': str(self.b.tag.id)})

        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp_inexistente.status_code, 404)
        self.assertEqual(resp.data, resp_inexistente.data)
        self.assertNotIn('Viagem B', str(resp.data))

    def test_tag_id_malformado_responde_404_igual_a_tag_inexistente(self):
        resp_inexistente = self.cliente.get(URL_TAG, {'tag_id': self.ID_INEXISTENTE})
        resp = self.cliente.get(URL_TAG, {'tag_id': 'nao-e-um-uuid'})

        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.data, resp_inexistente.data)

    def test_tag_de_a_continua_respondendo(self):
        resp = self.cliente.get(URL_TAG, {'tag_id': str(self.a.tag.id)})

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['tag_name'], 'Viagem A')

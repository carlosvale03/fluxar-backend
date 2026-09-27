from reports.models import FocusedMonitorItem
from tests.isolamento.base import DoisUsuariosTestCase

URL = '/api/focused-monitors/'


class EscritaMonitorDeFocoTests(DoisUsuariosTestCase):

    def setUp(self):
        self.cliente = self.como(self.a.usuario)

    def estado_dos_monitores(self):
        return sorted(FocusedMonitorItem.objects.values_list('user_id', 'category_id', 'tag_id'), key=str)

    def assert_recusa(self, campo, valor, mensagem):
        antes = self.estado_dos_monitores()
        resp_inexistente = self.cliente.post(URL, {campo: self.ID_INEXISTENTE}, format='json')
        resp = self.cliente.post(URL, {campo: valor}, format='json')

        self.assert_mesma_recusa(resp, resp_inexistente, campo, mensagem)
        self.assertEqual(self.estado_dos_monitores(), antes)

    def test_monitor_com_categoria_de_b_e_recusado(self):
        self.assert_recusa('category', str(self.b.subcategoria.id), 'Categoria não encontrada.')

    def test_monitor_com_categoria_modelo_e_recusado(self):
        self.assert_recusa('category', str(self.categoria_modelo.id), 'Categoria não encontrada.')

    def test_monitor_com_tag_de_b_e_recusado(self):
        self.assert_recusa('tag', str(self.b.tag.id), 'Tag não encontrada.')

    def test_monitor_com_categoria_de_a_continua_funcionando(self):
        resp = self.cliente.post(URL, {'category': str(self.a.subcategoria.id)}, format='json')

        self.assertEqual(resp.status_code, 201, resp.data)
        monitor = FocusedMonitorItem.objects.get(pk=resp.data['id'])
        self.assertEqual((monitor.user, monitor.category, monitor.tag), (self.a.usuario, self.a.subcategoria, None))
        self.assertEqual(resp.data['category_name'], 'Feira A')

    def test_monitor_com_tag_de_a_continua_funcionando(self):
        resp = self.cliente.post(URL, {'tag': str(self.a.tag.id)}, format='json')

        self.assertEqual(resp.status_code, 201, resp.data)
        monitor = FocusedMonitorItem.objects.get(pk=resp.data['id'])
        self.assertEqual((monitor.user, monitor.category, monitor.tag), (self.a.usuario, None, self.a.tag))
        self.assertEqual(resp.data['tag_name'], 'Viagem A')


class LeituraMonitorDeFocoTests(DoisUsuariosTestCase):

    def test_monitor_de_a_ligado_a_categoria_ou_tag_de_b_nao_mostra_dados_de_b(self):
        # Ligações cruzadas gravadas à força, como antes da correção
        monitor_tag = FocusedMonitorItem.objects.create(user=self.a.usuario, tag=self.b.tag)
        monitor_categoria = FocusedMonitorItem.objects.create(user=self.a.usuario, category=self.b.subcategoria)

        resp = self.como(self.a.usuario).get(URL)

        self.assertEqual(resp.status_code, 200)
        itens = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        por_id = {item['id']: item for item in itens}
        self.assertIsNone(por_id[str(monitor_tag.id)]['tag_name'])
        self.assertIsNone(por_id[str(monitor_tag.id)]['tag'])
        self.assertIsNone(por_id[str(monitor_categoria.id)]['category_name'])
        self.assertIsNone(por_id[str(monitor_categoria.id)]['category'])
        self.assertNotIn('Viagem B', str(resp.data))
        self.assertNotIn('Feira B', str(resp.data))
        # O monitor próprio continua com o nome da categoria de A
        self.assertEqual(por_id[str(self.a.monitor.id)]['category_name'], 'Mercado A')

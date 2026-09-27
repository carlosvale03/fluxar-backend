from reports.models import FocusedMonitorItem
from transactions.models import Category, Tag
from tests.isolamento.base import DoisUsuariosTestCase

URL = '/api/reports/charts/advanced/'


class MonitoresNoRelatorioAvancadoTests(DoisUsuariosTestCase):
    """
    Monitores de A ligados à força a categoria ou tag de B, como antes da
    correção, ficam fora do relatório avançado de A (ISOL-15).
    """

    def setUp(self):
        Category.objects.filter(pk=self.b.categoria.pk).update(icon='icone-de-b', color='#b0b0b0')
        Tag.objects.filter(pk=self.b.tag.pk).update(color='#b1b1b1')

    def monitores_de_a(self):
        resp = self.como(self.a.usuario).get(URL)
        self.assertEqual(resp.status_code, 200)
        return resp.data['custom_monitoring']

    def assert_sem_dados_de_b(self, monitores):
        texto = str(monitores)
        for dado_de_b in ('Mercado B', 'Viagem B', 'icone-de-b', '#b0b0b0', '#b1b1b1'):
            self.assertNotIn(dado_de_b, texto)

    def test_monitor_ligado_a_categoria_de_b_nao_aparece(self):
        intruso = FocusedMonitorItem.objects.create(user=self.a.usuario, category=self.b.categoria)

        monitores = self.monitores_de_a()

        ids = [m['id'] for m in monitores]
        self.assertNotIn(str(intruso.id), ids)
        self.assert_sem_dados_de_b(monitores)
        # O monitor próprio de A continua aparecendo
        proprio = next(m for m in monitores if m['id'] == str(self.a.monitor.id))
        self.assertEqual((proprio['name'], proprio['type']), ('Mercado A', 'category'))

    def test_monitor_ligado_a_tag_de_b_nao_aparece(self):
        intruso = FocusedMonitorItem.objects.create(user=self.a.usuario, tag=self.b.tag)
        monitor_tag_a = FocusedMonitorItem.objects.create(user=self.a.usuario, tag=self.a.tag)

        monitores = self.monitores_de_a()

        ids = [m['id'] for m in monitores]
        self.assertNotIn(str(intruso.id), ids)
        self.assert_sem_dados_de_b(monitores)
        # O monitor de tag própria de A continua aparecendo
        proprio = next(m for m in monitores if m['id'] == str(monitor_tag_a.id))
        self.assertEqual((proprio['name'], proprio['type']), ('Viagem A', 'tag'))

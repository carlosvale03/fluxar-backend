"""
Parâmetro `months` da comparação mensal e dos insights de tag: inteiro de 1
a 24 (T3, REL-12).
"""
from transactions.models import Tag

from .base import RelatoriosTestCase

COMPARACAO = '/api/reports/charts/monthly-comparison/'
TAG = '/api/reports/charts/tag-insights/'
MENSAGEM = 'O parâmetro months aceita de 1 a 24.'
INVALIDOS = ('1000', '0', 'abc', '2.5', '-3', '25', '')


class ParametroMonthsTests(RelatoriosTestCase):

    def setUp(self):
        super().setUp()
        self.tag = Tag.objects.create(user=self.a.usuario, name='Viagem')

    def rotas(self, months=None):
        extra = {} if months is None else {'months': months}
        return {
            'comparação': self.client.get(COMPARACAO, extra),
            'tag': self.client.get(TAG, {'tag_id': str(self.tag.pk), **extra}),
        }

    def test_fora_de_1_a_24_ou_nao_inteiro_recebe_400(self):
        for valor in INVALIDOS:
            for rota, resp in self.rotas(valor).items():
                with self.subTest(rota=rota, months=valor):
                    self.assertEqual(resp.status_code, 400)
                    self.assertEqual(resp.data['detail'], MENSAGEM)

    def test_24_e_1_funcionam(self):
        for valor, meses in (('24', 24), ('1', 1)):
            respostas = self.rotas(valor)
            for rota, resp in respostas.items():
                with self.subTest(rota=rota, months=valor):
                    self.assertEqual(resp.status_code, 200, resp.data)
            self.assertEqual(len(respostas['comparação'].data), meses)

    def test_sem_o_parametro_usa_6_meses(self):
        respostas = self.rotas()

        for rota, resp in respostas.items():
            with self.subTest(rota=rota):
                self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(respostas['comparação'].data), 6)

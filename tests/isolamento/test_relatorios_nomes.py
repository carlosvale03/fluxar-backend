"""
Transações de A ligadas à força à conta, à categoria, à categoria-pai e à
tag de B, como antes da correção: os relatórios de A tratam essas relações como
ausentes e não mostram nome, ícone ou cor de B (ISOL-15). Os valores
continuam somados, só que sem o rótulo de B.
"""
import calendar
from datetime import date, timedelta
from decimal import Decimal

from transactions.models import Category, Tag, Transaction
from tests.isolamento.base import DoisUsuariosTestCase

URL_SIMPLES = '/api/reports/charts/simple/'
URL_TAGS = '/api/reports/charts/tag-distribution/'
URL_AVANCADO = '/api/reports/charts/advanced/'
DIA = date(2026, 9, 5)
DADOS_DE_B = ('Conta B', 'Mercado B', 'Feira B', 'Viagem B', 'icone-de-b', '#b0b0b0', '#b1b1b1')


def mes_anterior(dia, meses=1):
    """Primeiro dia do mês `meses` antes do mês de `dia`."""
    for _ in range(meses):
        dia = dia.replace(day=1) - timedelta(days=1)
    return dia.replace(day=1)


class RelatoriosComRelacoesDeBTestCase(DoisUsuariosTestCase):

    def setUp(self):
        Category.objects.filter(pk=self.b.categoria.pk).update(icon='icone-de-b', color='#b0b0b0')
        Tag.objects.filter(pk=self.b.tag.pk).update(color='#b1b1b1')
        Category.objects.filter(pk=self.a.categoria.pk).update(color='#a0a0a0')
        Tag.objects.filter(pk=self.a.tag.pk).update(color='#a2a2a2')
        self.cliente = self.como(self.a.usuario)

    def transacao(self, valor, tipo='EXPENSE', dia=DIA, tags=(), status='COMPLETED', conta=None, **relacoes):
        t = Transaction.objects.create(
            user=self.a.usuario, type=tipo, status=status, description='Compra',
            amount=Decimal(valor), date=dia, account=conta or self.a.conta, **relacoes,
        )
        t.tags.set(tags)
        return t

    def forjada(self, valor, **kwargs):
        """Transação de A gravada à força na conta de B, com as relações de B passadas."""
        return self.transacao(valor, conta=self.b.conta, **kwargs)

    def obter(self, url, parametros=None):
        resp = self.cliente.get(url, parametros or {})
        self.assertEqual(resp.status_code, 200, resp.data)
        texto = str(resp.data)
        for dado_de_b in DADOS_DE_B:
            self.assertNotIn(dado_de_b, texto)
        return resp.data


class GraficoSimplesTests(RelatoriosComRelacoesDeBTestCase):

    def obter_grafico(self):
        return self.obter(URL_SIMPLES, {'month': 9, 'year': 2026})

    def test_despesa_com_categoria_de_b_entra_em_sem_categoria(self):
        pendurada = Category.objects.create(
            user=self.a.usuario, name='Pendurada A', type='EXPENSE', color='#a1a1a1',
            parent=self.b.categoria,
        )
        self.forjada('40.00', category=self.b.categoria)
        self.forjada('10.00', category=self.b.subcategoria)
        self.transacao('5.00')
        self.transacao('25.00', category=self.a.categoria)
        self.transacao('12.00', category=self.a.subcategoria)
        self.transacao('15.00', category=pendurada)

        dados = self.obter_grafico()

        self.assertEqual(dados['expense_by_category'], [
            {'category_name': 'Sem Categoria', 'amount': 55.0, 'color': '#CBD5E1'},
            {'category_name': 'Mercado A', 'amount': 37.0, 'color': '#a0a0a0'},
            {'category_name': 'Pendurada A', 'amount': 15.0, 'color': '#a1a1a1'},
        ])

    def test_receita_com_categoria_de_b_entra_em_sem_categoria(self):
        self.forjada('100.00', tipo='INCOME', category=self.b.categoria)
        self.transacao('60.00', tipo='INCOME', category=self.a.categoria)

        dados = self.obter_grafico()

        self.assertEqual(dados['income_by_category'], [
            {'category_name': 'Sem Categoria', 'amount': 100.0, 'color': '#CBD5E1'},
            {'category_name': 'Mercado A', 'amount': 60.0, 'color': '#a0a0a0'},
        ])


class DistribuicaoPorTagTests(RelatoriosComRelacoesDeBTestCase):

    def obter_distribuicao(self):
        dados = self.obter(URL_TAGS, {'month': 9, 'year': 2026})
        self.assertNotIn(str(self.b.tag.id), str(dados))
        return dados

    def test_despesa_com_tag_de_b_fica_so_com_as_tags_de_a(self):
        self.forjada('40.00', tags=[self.a.tag, self.b.tag])
        self.forjada('20.00', tags=[self.b.tag])
        self.transacao('7.00')

        dados = self.obter_distribuicao()

        self.assertEqual(dados['expense_by_tag'], [
            {'id': str(self.a.tag.id), 'name': 'Viagem A', 'amount': 40.0, 'color': '#a2a2a2'},
            {'id': 'others', 'name': 'Outros', 'amount': 27.0, 'color': '#94a3b8'},
        ])

    def test_receita_com_tag_de_b_fica_so_com_as_tags_de_a(self):
        self.forjada('70.00', tipo='INCOME', tags=[self.b.tag])
        self.forjada('30.00', tipo='INCOME', tags=[self.a.tag, self.b.tag])

        dados = self.obter_distribuicao()

        self.assertEqual(dados['income_by_tag'], [
            {'id': str(self.a.tag.id), 'name': 'Viagem A', 'amount': 30.0, 'color': '#a2a2a2'},
            {'id': 'others', 'name': 'Outros', 'amount': 70.0, 'color': '#94a3b8'},
        ])


class RelatorioAvancadoTests(RelatoriosComRelacoesDeBTestCase):
    """
    O relatório avançado usa o mês corrente: o período vai do dia 1 ao último
    dia do mês de hoje.
    """

    def setUp(self):
        super().setUp()
        hoje = date.today()
        self.inicio = hoje.replace(day=1)
        self.fim = hoje.replace(day=calendar.monthrange(hoje.year, hoje.month)[1])

    def obter_avancado(self):
        return self.obter(URL_AVANCADO)

    def proximo_gasto_agendado(self, dono):
        # Gasto pequeno para a média por transação ficar abaixo do agendado
        self.transacao('10.00', dia=self.inicio)
        agendado = self.fim + timedelta(days=5)
        self.transacao('500.00', dia=agendado, status='PENDING', conta=dono.conta, category=dono.categoria)
        return agendado, self.obter_avancado()['next_big_expense']

    def test_gasto_agendado_com_categoria_de_b_aparece_como_geral(self):
        agendado, gasto = self.proximo_gasto_agendado(self.b)

        self.assertEqual(gasto, {
            'description': 'Geral', 'amount': 500.0,
            'date': agendado.strftime('%Y-%m-%d'), 'category': 'Geral',
        })

    def test_gasto_agendado_com_categoria_de_a_mostra_o_nome(self):
        agendado, gasto = self.proximo_gasto_agendado(self.a)

        self.assertEqual(gasto, {
            'description': 'Mercado A', 'amount': 500.0,
            'date': agendado.strftime('%Y-%m-%d'), 'category': 'Mercado A',
        })

    def gasto_que_se_repete(self, dono):
        self.transacao('10.00', dia=self.inicio)
        for inicio_do_mes in (self.inicio, mes_anterior(self.inicio)):
            self.transacao(
                '300.00', dia=inicio_do_mes.replace(day=10), conta=dono.conta, category=dono.categoria,
            )
        proximo_mes = self.fim + timedelta(days=1)
        return proximo_mes.replace(day=10), self.obter_avancado()['next_big_expense']

    def test_gasto_que_se_repete_com_categoria_de_b_aparece_como_geral(self):
        previsto, gasto = self.gasto_que_se_repete(self.b)

        self.assertEqual(gasto, {
            'description': 'Geral', 'amount': 300.0,
            'date': previsto.strftime('%Y-%m-%d'), 'category': 'Geral',
        })

    def test_gasto_que_se_repete_com_categoria_de_a_mostra_o_nome(self):
        previsto, gasto = self.gasto_que_se_repete(self.a)

        self.assertEqual(gasto, {
            'description': 'Mercado A', 'amount': 300.0,
            'date': previsto.strftime('%Y-%m-%d'), 'category': 'Mercado A',
        })

    def categoria_sensivel(self, dono):
        for meses in (0, 1, 2):
            self.transacao(
                '100.00', dia=mes_anterior(self.inicio, meses).replace(day=5),
                conta=dono.conta, category=dono.categoria,
            )
        return self.obter_avancado()['risk_analysis']['sensitive_category']

    def test_categoria_sensivel_nao_usa_a_categoria_de_b(self):
        self.assertIsNone(self.categoria_sensivel(self.b))

    def test_categoria_sensivel_usa_a_categoria_de_a(self):
        self.assertEqual(self.categoria_sensivel(self.a), 'Mercado A')

    def test_gasto_fixo_nao_usa_o_nome_da_categoria_de_b(self):
        Category.objects.filter(pk=self.b.categoria.pk).update(name='Aluguel B')
        aluguel_a = Category.objects.create(user=self.a.usuario, name='Aluguel A', type='EXPENSE')
        self.forjada('100.00', dia=self.inicio, category=self.b.categoria)
        self.transacao('30.00', dia=self.inicio, category=aluguel_a)

        dados = self.obter_avancado()

        self.assertNotIn('Aluguel B', str(dados))
        # Só a categoria própria de A conta como gasto fixo
        self.assertEqual(dados['fixed_vs_variable'], {'fixed': 30.0, 'variable': 100.0, 'total': 130.0})

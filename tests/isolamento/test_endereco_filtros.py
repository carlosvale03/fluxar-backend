"""
ISOL-12 e ISOL-13 com o comportamento atual: um ID de outro usuário no
endereço responde 404, e num filtro devolve o resultado vazio, sempre igual
à resposta para um ID inexistente.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from accounts.models import Account, CreditCard, CreditCardInvoice
from budgets.models import Budget
from data_exchange.services import ExportService
from goals.models import Goal, GoalDeposit
from reports.models import FocusedMonitorItem
from transactions.models import Category, Tag, Transaction
from tests.isolamento.base import DoisUsuariosTestCase


def criar_transacoes(dados):
    """Uma despesa na conta, com categoria e tag, e uma compra no cartão, com fatura."""
    despesa = Transaction.objects.create(
        user=dados.usuario, type='EXPENSE', status='PENDING', description='Despesa',
        amount=Decimal('35.00'), date=date(2026, 9, 5), account=dados.conta,
        category=dados.categoria,
    )
    despesa.tags.set([dados.tag])
    compra = Transaction.objects.create(
        user=dados.usuario, type='CREDIT_CARD', status='PENDING', description='Compra',
        amount=Decimal('80.00'), date=date(2026, 9, 6), account=dados.conta,
        credit_card=dados.cartao, invoice=dados.fatura, category=dados.categoria,
    )
    compra.tags.set([dados.tag])
    return despesa, compra


class EnderecoComIdDeOutroUsuarioTests(DoisUsuariosTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.despesa_b, cls.compra_b = criar_transacoes(cls.b)

    def setUp(self):
        self.cliente = self.como(self.a.usuario)

    def chamar(self, metodo, url, dados):
        if metodo == 'get':
            return self.cliente.get(url)
        return getattr(self.cliente, metodo)(url, dados, format='json')

    def assert_404_igual(self, metodo, url_b, url_inexistente, dados=None, status=404):
        resp_inexistente = self.chamar(metodo, url_inexistente, dados or {})
        resp = self.chamar(metodo, url_b, dados or {})

        self.assertEqual(resp.status_code, status, (metodo, url_b))
        self.assertEqual(resp_inexistente.status_code, status, (metodo, url_inexistente))
        self.assertEqual(resp.data, resp_inexistente.data)

    def assert_leitura_edicao_exclusao(self, prefixo, obj_b, dados_edicao):
        url_b = f'{prefixo}{obj_b.pk}/'
        url_inexistente = f'{prefixo}{self.ID_INEXISTENTE}/'
        self.assert_404_igual('get', url_b, url_inexistente)
        self.assert_404_igual('patch', url_b, url_inexistente, dados_edicao)
        self.assert_404_igual('put', url_b, url_inexistente, dados_edicao)
        self.assert_404_igual('delete', url_b, url_inexistente)

    def test_conta_de_b(self):
        self.assert_leitura_edicao_exclusao('/api/accounts/', self.b.conta, {'name': 'Invadida'})

        conta = Account.objects.get(pk=self.b.conta.pk)
        self.assertEqual((conta.name, conta.is_active), ('Conta B', True))

    def test_cartao_de_b(self):
        self.assert_leitura_edicao_exclusao('/api/credit-cards/', self.b.cartao, {'name': 'Invadido'})
        self.assert_404_igual(
            'get', f'/api/credit-cards/{self.b.cartao.pk}/invoices/',
            f'/api/credit-cards/{self.ID_INEXISTENTE}/invoices/',
        )

        cartao = CreditCard.objects.get(pk=self.b.cartao.pk)
        self.assertEqual((cartao.name, cartao.is_active), ('Cartão B', True))

    def test_fatura_de_b(self):
        """
        A rota de faturas não tem edição nem exclusão (405 para qualquer ID, a
        mesma resposta); a escrita é pelas ações pay e unpay, que respondem 404.
        """
        url_b = f'/api/invoices/{self.b.fatura.pk}/'
        url_inexistente = f'/api/invoices/{self.ID_INEXISTENTE}/'
        self.assert_404_igual('get', url_b, url_inexistente)
        pagamento = {'amount': '80.00', 'date': '2026-09-20', 'account_id': str(self.a.conta.id)}
        self.assert_404_igual('post', f'{url_b}pay/', f'{url_inexistente}pay/', pagamento)
        self.assert_404_igual('post', f'{url_b}unpay/', f'{url_inexistente}unpay/')
        self.assert_404_igual('patch', url_b, url_inexistente, {'status': 'PAID'}, status=405)
        self.assert_404_igual('delete', url_b, url_inexistente, status=405)

        self.assertEqual(CreditCardInvoice.objects.get(pk=self.b.fatura.pk).status, 'OPEN')
        self.assertEqual(Transaction.objects.get(pk=self.compra_b.pk).status, 'PENDING')

    def test_categoria_de_b(self):
        self.assert_leitura_edicao_exclusao('/api/categories/', self.b.categoria, {'name': 'Invadida'})

        categoria = Category.objects.get(pk=self.b.categoria.pk)
        self.assertEqual((categoria.name, categoria.is_active), ('Mercado B', True))

    def test_tag_de_b(self):
        self.assert_leitura_edicao_exclusao('/api/tags/', self.b.tag, {'name': 'Invadida'})

        self.assertEqual(Tag.objects.get(pk=self.b.tag.pk).name, 'Viagem B')

    def test_transacao_de_b(self):
        self.assert_leitura_edicao_exclusao('/api/transactions/', self.despesa_b, {'amount': '1.00'})

        self.assertEqual(Transaction.objects.get(pk=self.despesa_b.pk).amount, Decimal('35.00'))

    def test_orcamento_de_b(self):
        self.assert_leitura_edicao_exclusao('/api/budgets/', self.b.orcamento, {'amount_limit': '1.00'})

        self.assertEqual(Budget.objects.get(pk=self.b.orcamento.pk).amount_limit, Decimal('300.00'))

    def test_meta_de_b(self):
        self.assert_leitura_edicao_exclusao('/api/goals/', self.b.meta, {'name': 'Invadida'})
        url_b = f'/api/goals/{self.b.meta.pk}/'
        url_inexistente = f'/api/goals/{self.ID_INEXISTENTE}/'
        movimento = {'amount': '10.00', 'account_id': str(self.a.conta.id)}
        self.assert_404_igual('post', f'{url_b}deposit/', f'{url_inexistente}deposit/', movimento)
        self.assert_404_igual('post', f'{url_b}withdraw/', f'{url_inexistente}withdraw/', movimento)
        self.assert_404_igual('get', f'{url_b}history/', f'{url_inexistente}history/')

        self.assertEqual(Goal.objects.get(pk=self.b.meta.pk).name, 'Meta B')
        self.assertFalse(GoalDeposit.objects.filter(goal=self.b.meta).exists())

    def test_monitor_de_b(self):
        self.assert_leitura_edicao_exclusao(
            '/api/focused-monitors/', self.b.monitor, {'category': str(self.a.categoria.id)},
        )

        self.assertEqual(FocusedMonitorItem.objects.get(pk=self.b.monitor.pk).category, self.b.categoria)


class FiltrosComIdDeOutroUsuarioTests(DoisUsuariosTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.despesa_a, cls.compra_a = criar_transacoes(cls.a)
        criar_transacoes(cls.b)

    def setUp(self):
        self.cliente = self.como(self.a.usuario)

    def assert_lista_vazia_igual(self, url, parametro, id_b, id_a, colecao=False):
        resp_inexistente = self.cliente.get(url, {parametro: self.ID_INEXISTENTE})
        resp = self.cliente.get(url, {parametro: id_b})
        resp_propria = self.cliente.get(url, {parametro: id_a})
        # Coleções vêm como array; as transações, paginadas (AD-021)
        itens = (lambda r: r.data) if colecao else (lambda r: r.data['results'])

        self.assertEqual(resp.status_code, 200, parametro)
        self.assertEqual(itens(resp), [], parametro)
        self.assertEqual(resp.data, resp_inexistente.data, parametro)
        # O mesmo filtro com o ID de A encontra os dados de A
        self.assertNotEqual(itens(resp_propria), [], parametro)

    def test_filtro_de_conta_nas_transacoes(self):
        self.assert_lista_vazia_igual('/api/transactions/', 'accountId', self.b.conta.id, self.a.conta.id)
        # O alias antigo saiu do contrato (CONTRATO-14)
        resp = self.cliente.get('/api/transactions/', {'account': self.b.conta.id})
        self.assertEqual((resp.status_code, resp.data['detail']), (400, 'Filtro desconhecido: account.'))

    def test_filtro_de_cartao_nas_transacoes(self):
        self.assert_lista_vazia_igual('/api/transactions/', 'credit_card', self.b.cartao.id, self.a.cartao.id)

    def test_filtro_de_fatura_nas_transacoes(self):
        self.assert_lista_vazia_igual('/api/transactions/', 'invoice', self.b.fatura.id, self.a.fatura.id)

    def test_filtro_de_categoria_nas_transacoes(self):
        self.assert_lista_vazia_igual('/api/transactions/', 'categoryId', self.b.categoria.id, self.a.categoria.id)
        # O alias antigo saiu do contrato (CONTRATO-14)
        resp = self.cliente.get('/api/transactions/', {'category': self.b.categoria.id})
        self.assertEqual((resp.status_code, resp.data['detail']), (400, 'Filtro desconhecido: category.'))

    def test_filtro_de_tags_nas_transacoes(self):
        self.assert_lista_vazia_igual('/api/transactions/', 'tagIds', self.b.tag.id, self.a.tag.id)

    def test_filtro_de_categoria_nos_orcamentos(self):
        self.assert_lista_vazia_igual(
            '/api/budgets/', 'category', self.b.categoria.id, self.a.categoria.id, colecao=True,
        )

    def transacoes_exportadas(self, url, metodo, parametros):
        """
        A exportação devolve um arquivo (PDF ou planilha), então o teste
        confere o queryset que a view entrega ao gerador do arquivo: é dele que
        sai cada linha exportada, e o conteúdo binário não é comparável.
        """
        with patch.object(ExportService, metodo, return_value=b'arquivo') as gerador:
            resp = self.cliente.get(url, parametros)
        self.assertEqual(resp.status_code, 200)
        return list(gerador.call_args.args[0])

    def assert_exportacao_vazia(self, url, metodo):
        filtros = {
            'accountId': (self.b.conta.id, self.a.conta.id),
            'categoryId': (self.b.categoria.id, self.a.categoria.id),
            'tagIds': (self.b.tag.id, self.a.tag.id),
        }
        for parametro, (id_b, id_a) in filtros.items():
            self.assertEqual(self.transacoes_exportadas(url, metodo, {parametro: id_b}), [], parametro)
            self.assertEqual(self.transacoes_exportadas(url, metodo, {parametro: self.ID_INEXISTENTE}), [], parametro)
            self.assertNotEqual(self.transacoes_exportadas(url, metodo, {parametro: id_a}), [], parametro)

    def test_filtros_na_exportacao_em_pdf(self):
        self.assert_exportacao_vazia('/api/export/transactions/pdf/', 'generate_pdf')

    def test_filtros_na_exportacao_em_planilha(self):
        self.assert_exportacao_vazia('/api/export/transactions/xls/', 'generate_xls')

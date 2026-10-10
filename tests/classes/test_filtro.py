"""
Filtro por classe na lista de transações e nas exportações (CLASSE-34 a
CLASSE-39).

A lista e as duas exportações devem trazer exatamente as mesmas transações
(AD-022); nas exportações, o gerador do arquivo é simulado para ler o
conjunto recebido, como em `tests/contratos/test_filtro_de_transacoes.py`.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from accounts.models import Account, CreditCard
from data_exchange.services import ExportService
from transactions.models import Category, Transaction
from transactions.services import TransactionService

from .base import ClassesTestCase, categoria, criar_classe, criar_usuario

URL_TRANSACOES = '/api/transactions/'
URL_PDF = '/api/export/transactions/pdf/'
URL_XLS = '/api/export/transactions/xls/'


class FiltroPorClasseTests(ClassesTestCase):

    def setUp(self):
        super().setUp()
        ana = self.ana
        self.conta = Account.objects.create(user=ana, name='Corrente', type='CHECKING', initial_balance=Decimal('5000'))
        poupanca = Account.objects.create(user=ana, name='Poupança', type='SAVINGS')
        cartao = CreditCard.objects.create(
            user=ana, name='Cartão', limit=Decimal('10000.00'), closing_day=5, due_day=15, account=self.conta,
        )
        doces = Category.objects.get(user=ana, name='Doces')
        self.comida = Category.objects.get(user=ana, name='Comida')
        mercado = categoria(ana, 'Mercado')
        dia = date(2026, 9, 10)

        self.doce = self.lancar('Doce', doces, dia)
        [self.doce_no_cartao] = TransactionService.create_credit_card_expense(
            ana, cartao, Decimal('50.00'), dia, 'Doce no cartão', doces, installments=1,
        )
        self.almoco = self.lancar('Almoço', self.comida, dia)
        self.sem_categoria = self.lancar('Sem categoria', None, dia)
        self.no_mercado = self.lancar('No mercado', mercado, dia)
        [self.cartao_sem_categoria] = TransactionService.create_credit_card_expense(
            ana, cartao, Decimal('20.00'), dia, 'Cartão sem categoria', None, installments=1,
        )
        # Fora de qualquer filtro de classe (CLASSE-36)
        self.lancar('Salário', Category.objects.get(user=ana, name='Salário'), dia, tipo='INCOME')
        self.lancar('Receita sem categoria', None, dia, tipo='INCOME')
        TransactionService.create_transfer(ana, self.conta, poupanca, Decimal('100.00'), dia)
        self.lancar('Pagamento da fatura', None, dia, tipo='INVOICE_PAYMENT')

    def lancar(self, descricao, categoria_, dia, tipo='EXPENSE'):
        return Transaction.objects.create(
            user=self.ana, type=tipo, status='COMPLETED', amount=Decimal('10.00'), date=dia,
            account=self.conta, category=categoria_, description=descricao,
        )

    def ids_na_lista(self, parametros):
        resposta = self.client.get(URL_TRANSACOES, {**parametros, 'page_size': 100})
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(len(resposta.data['results']), resposta.data['count'])
        return sorted(item['id'] for item in resposta.data['results'])

    def ids_exportados(self, url, parametros):
        metodo = 'generate_pdf' if url == URL_PDF else 'generate_xls'
        with patch.object(ExportService, metodo, return_value=b'arquivo') as gerador:
            resposta = self.client.get(url, parametros)
        self.assertEqual(resposta.status_code, 200)
        return sorted(str(t.id) for t in gerador.call_args.args[0])

    def assert_traz(self, parametros, esperadas):
        esperados = sorted(str(t.id) for t in esperadas)
        self.assertEqual(self.ids_na_lista(parametros), esperados, 'lista')
        self.assertEqual(self.ids_exportados(URL_PDF, parametros), esperados, 'pdf')
        self.assertEqual(self.ids_exportados(URL_XLS, parametros), esperados, 'xls')

    def assert_recusa(self, parametros, valor):
        esperado = {'classId': [f'Classe inválida no filtro: {valor}.']}
        for url in (URL_TRANSACOES, URL_PDF, URL_XLS):
            with self.subTest(url=url):
                resposta = self.client.get(url, parametros)
                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.json(), esperado)

    def test_uma_classe_traz_as_despesas_e_compras_no_cartao_dela(self):
        self.assert_traz({'classId': str(self.dispensavel().pk)}, [self.doce, self.doce_no_cartao])

    def test_sem_classe_traz_as_sem_categoria_e_as_de_categoria_sem_classe(self):
        self.assert_traz(
            {'classId': 'sem_classe'}, [self.sem_categoria, self.no_mercado, self.cartao_sem_categoria],
        )

    def test_uma_classe_e_sem_classe_juntas_trazem_os_dois_grupos(self):
        self.assert_traz(
            {'classId': [str(self.dispensavel().pk), 'sem_classe']},
            [self.doce, self.doce_no_cartao, self.sem_categoria, self.no_mercado, self.cartao_sem_categoria],
        )

    def test_duas_classes_trazem_as_duas(self):
        self.assert_traz(
            {'classId': [str(self.dispensavel().pk), str(self.essencial().pk)]},
            [self.doce, self.doce_no_cartao, self.almoco],
        )

    def test_classe_combinada_com_categoria_traz_so_o_que_atende_aos_dois(self):
        self.assert_traz({'classId': str(self.dispensavel().pk), 'categoryId': str(self.comida.pk)}, [])
        self.assert_traz({'classId': str(self.essencial().pk), 'categoryId': str(self.comida.pk)}, [self.almoco])

    def test_subcategoria_entra_pela_classe_herdada(self):
        delivery = categoria(self.ana, 'Delivery', parent=self.comida)
        pedido = self.lancar('Pedido', delivery, date(2026, 9, 11))

        self.assert_traz({'classId': str(self.essencial().pk)}, [self.almoco, pedido])

    def test_classe_sem_categorias_nao_traz_nada(self):
        dividas = criar_classe(self.ana, 'Dívidas')

        self.assert_traz({'classId': str(dividas.pk)}, [])

    def test_classe_de_outro_usuario_e_recusada(self):
        da_bia = criar_classe(criar_usuario('bia@teste.fluxar'), 'Da Bia')

        self.assert_recusa({'classId': str(da_bia.pk)}, str(da_bia.pk))

    def test_texto_qualquer_e_recusado_mesmo_junto_de_uma_classe_valida(self):
        self.assert_recusa({'classId': 'qualquer'}, 'qualquer')
        self.assert_recusa({'classId': [str(self.essencial().pk), 'Sem Classe']}, 'Sem Classe')

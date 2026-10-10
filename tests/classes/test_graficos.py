"""
Divisão das despesas por classe nos gráficos simples (CLASSE-13, CLASSE-28
a CLASSE-30).

A usuária tem o padrão do cadastro: Comida em Essencial e Doces em
Dispensável (CLASSE-24).
"""
from datetime import date
from decimal import Decimal

from accounts.models import Account, CreditCard
from tests.permissoes.base import LIMITES, RECURSOS, fechar, liberacao_de_testes
from transactions.models import Category, Transaction
from transactions.services import TransactionService

from .base import ClassesTestCase, categoria, criar_usuario

ROTA = '/api/reports/charts/simple/'
SEM_CLASSE = {'class_id': None, 'class_name': 'Sem classe', 'color': '#94A3B8'}


class GraficosTestCase(ClassesTestCase):

    def setUp(self):
        super().setUp()
        self.conta = Account.objects.create(user=self.ana, name='Corrente', type='CHECKING')
        self.comida = Category.objects.get(user=self.ana, name='Comida')
        self.doces = Category.objects.get(user=self.ana, name='Doces')

    def lancar(self, valor, dia, categoria_=None, tipo='EXPENSE', status='COMPLETED', usuario=None):
        return Transaction.objects.create(
            user=usuario or self.ana, type=tipo, status=status, amount=Decimal(valor), date=dia,
            account=self.conta, category=categoria_, description='Lançamento',
        )

    def graficos(self, mes=9, ano=2026):
        resposta = self.client.get(ROTA, {'month': mes, 'year': ano})
        self.assertEqual(resposta.status_code, 200, resposta.data)
        return resposta.json()

    def classe(self, nome, cor, valor, classe_):
        return {'class_id': str(classe_.pk), 'class_name': nome, 'color': cor, 'amount': valor}

    def soma(self, linhas):
        return sum((Decimal(linha['amount']) for linha in linhas), Decimal('0'))


class DivisaoPorClasseTests(GraficosTestCase):

    def test_divide_as_despesas_do_periodo_por_classe_com_sem_classe(self):
        self.lancar('600.00', date(2026, 9, 5), self.comida)
        self.lancar('300.00', date(2026, 9, 6), self.doces)
        self.lancar('100.00', date(2026, 9, 7))

        dados = self.graficos()

        self.assertEqual(dados['expense_by_class'], [
            self.classe('Essencial', '#16A34A', '600.00', self.essencial()),
            self.classe('Dispensável', '#F97316', '300.00', self.dispensavel()),
            {**SEM_CLASSE, 'amount': '100.00'},
        ])
        self.assertEqual(self.soma(dados['expense_by_class']), self.soma(dados['expense_by_category']))

    def test_soma_por_classe_igual_a_soma_por_categoria_com_cartao_e_pendentes(self):
        cartao = CreditCard.objects.create(
            user=self.ana, name='Cartão', limit=Decimal('10000.00'), closing_day=5, due_day=15, account=self.conta,
        )
        # Parcelada em 3 a partir de agosto: só a parcela de setembro conta no mês
        TransactionService.create_credit_card_expense(
            self.ana, cartao, Decimal('90.00'), date(2026, 8, 20), 'Compra', self.doces, installments=3,
        )
        TransactionService.create_credit_card_expense(
            self.ana, cartao, Decimal('45.50'), date(2026, 9, 2), 'Compra', None, installments=1,
        )
        aluguel = Category.objects.get(user=self.ana, name='Aluguel')
        mercado = categoria(self.ana, 'Mercado')
        self.lancar('800.00', date(2026, 9, 1), aluguel)
        self.lancar('70.25', date(2026, 9, 3), mercado)
        # Despesa pendente, receita e ajuste de saldo ficam fora dos dois gráficos
        self.lancar('999.00', date(2026, 9, 4), self.comida, status='PENDING')
        self.lancar('5000.00', date(2026, 9, 4), Category.objects.get(user=self.ana, name='Salário'), tipo='INCOME')

        dados = self.graficos()

        self.assertEqual(self.soma(dados['expense_by_class']), self.soma(dados['expense_by_category']))
        self.assertEqual(self.soma(dados['expense_by_class']), Decimal('945.75'))
        self.assertEqual(dados['expense_by_class'], [
            self.classe('Essencial', '#16A34A', '800.00', self.essencial()),
            {**SEM_CLASSE, 'amount': '115.75'},
            self.classe('Dispensável', '#F97316', '30.00', self.dispensavel()),
        ])

    def test_mudar_a_classe_da_categoria_muda_tambem_o_mes_anterior(self):
        self.lancar('300.00', date(2026, 8, 10), self.doces)
        self.assertEqual(self.graficos(8)['expense_by_class'], [
            self.classe('Dispensável', '#F97316', '300.00', self.dispensavel()),
        ])

        resposta = self.client.patch(
            f'/api/categories/{self.doces.pk}/', {'expense_class': str(self.essencial().pk)}, format='json',
        )

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(self.graficos(8)['expense_by_class'], [
            self.classe('Essencial', '#16A34A', '300.00', self.essencial()),
        ])

    def test_categoria_excluida_continua_na_classe_dela(self):
        self.lancar('300.00', date(2026, 9, 10), self.doces)
        self.client.delete(f'/api/categories/{self.doces.pk}/')

        self.assertEqual(self.graficos()['expense_by_class'], [
            self.classe('Dispensável', '#F97316', '300.00', self.dispensavel()),
        ])

    def test_periodo_sem_despesas_devolve_a_lista_vazia(self):
        self.lancar('300.00', date(2026, 8, 10), self.doces)

        self.assertEqual(self.graficos(9)['expense_by_class'], [])

    def test_so_as_despesas_da_usuaria_entram(self):
        bia = criar_usuario('bia@teste.fluxar')
        Transaction.objects.create(
            user=bia, type='EXPENSE', status='COMPLETED', amount=Decimal('50.00'), date=date(2026, 9, 5),
            account=Account.objects.create(user=bia, name='Da Bia', type='CHECKING'),
            category=Category.objects.get(user=bia, name='Comida'), description='Da Bia',
        )
        self.lancar('10.00', date(2026, 9, 5), self.comida)

        self.assertEqual(self.graficos()['expense_by_class'], [
            self.classe('Essencial', '#16A34A', '10.00', self.essencial()),
        ])

    def test_despesa_com_categoria_de_outro_usuario_entra_em_sem_classe(self):
        # Dado antigo: a despesa da Ana aponta para uma categoria da Bia
        bia = criar_usuario('bia@teste.fluxar')
        self.lancar('50.00', date(2026, 9, 5), Category.objects.get(user=bia, name='Comida'))
        self.lancar('10.00', date(2026, 9, 6), self.comida)

        dados = self.graficos()

        self.assertEqual(dados['expense_by_class'], [
            {**SEM_CLASSE, 'amount': '50.00'},
            self.classe('Essencial', '#16A34A', '10.00', self.essencial()),
        ])
        self.assertEqual(self.soma(dados['expense_by_class']), self.soma(dados['expense_by_category']))
        self.assertEqual(self.soma(dados['expense_by_class']), Decimal('60.00'))


class DivisaoSemTravaDePlanoTests(GraficosTestCase):

    def test_a_divisao_por_classe_aparece_em_qualquer_plano(self):
        liberacao_de_testes(False)
        for chave in RECURSOS:
            fechar(chave)
        for chave in LIMITES:
            fechar(chave, limite=0)
        self.ana.plan = 'COMMON'
        self.ana.save(update_fields=['plan'])
        self.lancar('20.00', date(2026, 9, 5), self.comida)

        self.assertEqual(self.graficos()['expense_by_class'], [
            self.classe('Essencial', '#16A34A', '20.00', self.essencial()),
        ])

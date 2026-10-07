"""
Coleções completas e listas paginadas num formato único (CONTRATO-01 a
CONTRATO-04, AD-021).
"""
from datetime import date
from decimal import Decimal

from accounts.models import Account, CreditCard, CreditCardInvoice
from api.models import SystemLog, User
from budgets.models import Budget
from goals.models import Goal
from reports.models import FocusedMonitorItem
from transactions.models import Category, Tag

from .base import CHAVES_DA_PAGINA, URL_TRANSACOES, ContratosTestCase


class ColecoesCompletasTests(ContratosTestCase):
    """CONTRATO-01: cada coleção pequena vem como array, com todos os itens."""

    def assert_array_completo(self, url, esperados):
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, url)
        self.assertIsInstance(resp.data, list, url)
        self.assertEqual({str(item['id']) for item in resp.data}, {str(i) for i in esperados}, url)

    def test_15_tags(self):
        tags = [Tag.objects.create(user=self.a.usuario, name=f'Tag {i}').pk for i in range(15)]
        self.assert_array_completo('/api/tags/', tags)

    def test_12_orcamentos(self):
        orcamentos = [
            Budget.objects.create(
                user=self.a.usuario, category=self.a.despesa, month=mes, year=2026,
                amount_limit=Decimal('100.00'),
            ).pk
            for mes in range(1, 13)
        ]
        self.assert_array_completo('/api/budgets/', orcamentos)

    def test_11_cartoes(self):
        cartoes = [
            CreditCard.objects.create(
                user=self.a.usuario, name=f'Cartão {i}', limit=Decimal('1000.00'),
                closing_day=10, due_day=20, account=self.a.conta,
            ).pk
            for i in range(11)
        ]
        self.assert_array_completo('/api/credit-cards/', cartoes)

    def test_11_metas(self):
        metas = [
            Goal.objects.create(user=self.a.usuario, name=f'Meta {i}', target_amount=Decimal('500.00')).pk
            for i in range(11)
        ]
        self.assert_array_completo('/api/goals/', metas)

    def test_11_monitores(self):
        monitores = [
            FocusedMonitorItem.objects.create(
                user=self.a.usuario,
                category=Category.objects.create(user=self.a.usuario, name=f'Monitorada {i}', type='EXPENSE'),
            ).pk
            for i in range(11)
        ]
        self.assert_array_completo('/api/focused-monitors/', monitores)

    def test_contas_faturas_e_categorias(self):
        for i in range(11):
            Account.objects.create(user=self.a.usuario, name=f'Conta {i}', type='CHECKING')
        contas = Account.objects.filter(user=self.a.usuario, is_active=True).values_list('pk', flat=True)
        self.assert_array_completo('/api/accounts/', contas)

        cartao = CreditCard.objects.create(
            user=self.a.usuario, name='Cartão', limit=Decimal('1000.00'),
            closing_day=10, due_day=20, account=self.a.conta,
        )
        faturas = [
            CreditCardInvoice.objects.create(
                card=cartao, month=mes, year=2026,
                closing_date=date(2026, mes, 10), due_date=date(2026, mes, 20),
            ).pk
            for mes in range(1, 12)
        ]
        self.assert_array_completo('/api/invoices/', faturas)
        self.assert_array_completo(f'/api/credit-cards/{cartao.pk}/invoices/', faturas)

        for i in range(11):
            Category.objects.create(user=self.a.usuario, name=f'Raiz {i}', type='EXPENSE')
        raizes = Category.objects.filter(
            user=self.a.usuario, is_active=True, parent__isnull=True,
        ).values_list('pk', flat=True)
        self.assertGreater(len(raizes), 11)
        self.assert_array_completo('/api/categories/', raizes)


class TransacoesPaginadasTests(ContratosTestCase):
    """CONTRATO-02 a CONTRATO-04 na lista de transações."""

    def test_formato_unico(self):
        self.lancar_varias(25)

        resp = self.client.get(URL_TRANSACOES)

        self.assertEqual(resp.status_code, 200)
        # As transações acrescentam o total de cada dia (CONTRATO-09)
        self.assertEqual(set(resp.data), CHAVES_DA_PAGINA | {'day_totals'})
        self.assertEqual(resp.data['count'], 25)
        self.assertEqual(resp.data['total_pages'], 2)
        self.assertEqual(resp.data['current_page'], 1)
        self.assertIsNone(resp.data['previous'])
        self.assertIn('page=2', resp.data['next'])

        segunda = self.client.get(URL_TRANSACOES, {'page': 2})
        self.assertEqual(segunda.data['current_page'], 2)
        self.assertIsNone(segunda.data['next'])
        self.assertIsNotNone(segunda.data['previous'])
        self.assertEqual(len(segunda.data['results']), 5)

    def test_tamanho_da_pagina(self):
        self.lancar_varias(110)

        self.assertEqual(len(self.client.get(URL_TRANSACOES).data['results']), 20)
        maxima = self.client.get(URL_TRANSACOES, {'page_size': 150})
        self.assertEqual(len(maxima.data['results']), 100)
        self.assertEqual(maxima.data['total_pages'], 2)
        pequena = self.client.get(URL_TRANSACOES, {'page_size': 5})
        self.assertEqual(len(pequena.data['results']), 5)
        self.assertEqual(pequena.data['total_pages'], 22)

    def test_pagina_alem_da_ultima(self):
        self.lancar_varias(25)

        resp = self.client.get(URL_TRANSACOES, {'page': 99})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['results'], [])
        self.assertEqual(resp.data['count'], 25)
        self.assertEqual(resp.data['total_pages'], 2)
        self.assertEqual(resp.data['current_page'], 99)
        self.assertIsNone(resp.data['next'])

    def test_pagina_que_nao_e_numero(self):
        self.lancar_varias(3)

        resp = self.client.get(URL_TRANSACOES, {'page': 'abc'})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['results'], [])
        self.assertEqual(resp.data['count'], 3)
        self.assertEqual(resp.data['total_pages'], 1)
        self.assertEqual(resp.data['current_page'], 1)


class ListasDoAdminPaginadasTests(ContratosTestCase):
    """CONTRATO-02 e CONTRATO-03 nas listas de usuários e de logs do admin."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.admin = User.objects.create_user(
            email='contratos.admin@teste.fluxar', password='senha-de-teste-123',
            name='Admin', is_staff=True, role='ADMIN',
        )
        for i in range(25):
            User.objects.create_user(email=f'contratos.u{i}@teste.fluxar', password='x', name=f'U{i}')
            SystemLog.objects.create(
                user=cls.a.usuario, action='TESTE', description=f'Log {i}', admin_name='Admin',
            )

    def setUp(self):
        self.client.force_authenticate(user=self.admin)

    def assert_paginada(self, url, total):
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, url)
        self.assertEqual(set(resp.data), CHAVES_DA_PAGINA, url)
        self.assertEqual(resp.data['count'], total, url)
        self.assertEqual(len(resp.data['results']), 20, url)
        self.assertEqual(resp.data['total_pages'], 2, url)
        self.assertIn('page=2', resp.data['next'], url)

        alem = self.client.get(url, {'page': 7, 'page_size': 5})
        self.assertEqual(alem.status_code, 200, url)
        self.assertEqual(alem.data['results'], [], url)
        self.assertEqual((alem.data['count'], alem.data['total_pages'], alem.data['current_page']),
                         (total, -(-total // 5), 7), url)

    def test_usuarios(self):
        self.assert_paginada('/api/admin/users/', User.objects.filter(is_active=True).count())

    def test_busca_de_usuarios_continua(self):
        resp = self.client.get('/api/admin/users/', {'search': 'contratos.u1'})
        # u1 e u10 a u19
        self.assertEqual(resp.data['count'], 11)

    def test_logs_globais(self):
        self.assert_paginada('/api/admin/logs/', SystemLog.objects.count())

    def test_logs_de_um_usuario(self):
        self.assert_paginada(f'/api/admin/users/{self.a.usuario.pk}/logs/', 25)

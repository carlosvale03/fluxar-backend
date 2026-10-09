"""
Recusa de filtro desconhecido (CONTRATO-14, AD-022): toda rota GET aceita só
os parâmetros da tabela do design e recusa os demais com HTTP 400.
"""
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from accounts.models import CreditCard, CreditCardInvoice
from api.models import User
from budgets.models import Budget
from data_exchange.services import ExportService
from goals.models import Goal
from reports.models import FocusedMonitorItem
from transactions.models import Tag

from .base import URL_TRANSACOES, ContratosTestCase


class FiltroDesconhecidoTests(ContratosTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.tag = Tag.objects.create(user=cls.a.usuario, name='Viagem')
        cls.cartao = CreditCard.objects.create(
            user=cls.a.usuario, name='Cartão', limit=Decimal('1000.00'),
            closing_day=10, due_day=20, account=cls.a.conta,
        )
        cls.fatura = CreditCardInvoice.objects.create(
            card=cls.cartao, month=9, year=2026,
            closing_date=date(2026, 9, 10), due_date=date(2026, 9, 20),
        )
        cls.meta = Goal.objects.create(user=cls.a.usuario, name='Meta', target_amount=Decimal('500.00'))
        cls.monitor = FocusedMonitorItem.objects.create(user=cls.a.usuario, tag=cls.tag)
        cls.orcamento = Budget.objects.create(
            user=cls.a.usuario, category=cls.a.despesa, month=9, year=2026, amount_limit=Decimal('100.00'),
        )
        cls.admin = User.objects.create_user(
            email='contratos.admin@teste.fluxar', password='senha-de-teste-123',
            name='Admin', is_staff=True, role='ADMIN',
        )

    def assert_recusado(self, url, parametros, nome):
        resp = self.client.get(url, parametros)
        self.assertEqual(resp.status_code, 400, url)
        self.assertEqual(resp.data['detail'], f'Filtro desconhecido: {nome}.', url)

    def assert_aceito(self, url, parametros):
        resp = self.client.get(url, parametros)
        self.assertEqual(resp.status_code, 200, (url, getattr(resp, 'data', None)))

    def test_limit_nas_transacoes(self):
        self.assert_recusado(URL_TRANSACOES, {'limit': 50}, 'limit')

    def test_colecao_sem_filtros(self):
        self.assert_recusado('/api/tags/', {'x': 1}, 'x')
        # Coleções não paginam: `page` também é desconhecido (AD-021)
        self.assert_recusado('/api/tags/', {'page': 2}, 'page')

    def test_nome_reportado_em_ordem_alfabetica(self):
        self.assert_recusado(URL_TRANSACOES, {'zeta': 1, 'alfa': 2, 'page': 1}, 'alfa')

    def test_aliases_antigos_saem(self):
        self.assert_recusado(URL_TRANSACOES, {'account': self.a.conta.pk}, 'account')
        self.assert_recusado(URL_TRANSACOES, {'category': self.a.despesa.pk}, 'category')
        self.assert_recusado(URL_TRANSACOES, {'tagIds[]': self.tag.pk}, 'tagIds[]')

    def test_parametros_da_tabela_aceitos(self):
        self.assert_aceito(URL_TRANSACOES, {
            'page': 1, 'page_size': 10, 'accountId': self.a.conta.pk, 'credit_card': self.cartao.pk,
            'invoice': self.fatura.pk, 'month': 9, 'year': 2026, 'startDate': '2026-09-01',
            'endDate': '2026-09-30', 'type': 'EXPENSE', 'categoryId': self.a.despesa.pk,
            'tagIds': self.tag.pk, 'search': 'x', 'is_recurring': 'true', 'transfer_id': uuid.uuid4(),
        })
        self.assert_aceito('/api/categories/', {'type': 'EXPENSE'})
        self.assert_aceito('/api/budgets/', {'month': 9, 'year': 2026, 'category': self.a.despesa.pk})
        self.assert_aceito('/api/budgets/', {'start_month': 1, 'start_year': 2026, 'end_month': 12, 'end_year': 2026})
        self.assert_aceito('/api/reports/dashboard/', {'month': 9, 'year': 2026, 'days': 30})
        for acao in ('calendar', 'charts/simple', 'charts/tag-distribution'):
            self.assert_aceito(f'/api/reports/{acao}/', {'month': 9, 'year': 2026, 'period': 30, 'days': 30})
        self.assert_aceito('/api/reports/charts/advanced/', {'period': 30, 'days': 30})
        self.assert_aceito('/api/reports/charts/monthly-comparison/', {'months': 6, 'month': 9, 'year': 2026})
        self.assert_aceito('/api/reports/charts/tag-insights/', {'tag_id': self.tag.pk, 'months': 6})
        parametros_da_exportacao = {
            'accountId': self.a.conta.pk, 'categoryId': self.a.despesa.pk, 'type': 'EXPENSE',
            'startDate': '2026-09-01', 'endDate': '2026-09-30', 'tagIds': self.tag.pk, 'search': 'x',
        }
        with patch.object(ExportService, 'generate_pdf', return_value=b'pdf'), \
                patch.object(ExportService, 'generate_xls', return_value=b'xls'):
            self.assert_aceito('/api/export/transactions/pdf/', parametros_da_exportacao)
            self.assert_aceito('/api/export/transactions/xls/', parametros_da_exportacao)

    def test_relatorios_recusam_parametros_de_outra_acao(self):
        self.assert_recusado('/api/reports/charts/advanced/', {'month': 9}, 'month')
        self.assert_recusado('/api/reports/dashboard/', {'period': 30}, 'period')
        self.assert_recusado('/api/reports/charts/tag-insights/', {'tag_id': self.tag.pk, 'year': 2026}, 'year')
        with patch.object(ExportService, 'generate_pdf', return_value=b'pdf'):
            self.assert_recusado('/api/export/transactions/pdf/', {'page': 1}, 'page')

    def test_rotas_sem_filtros(self):
        rotas = [
            '/api/accounts/', f'/api/accounts/{self.a.conta.pk}/',
            '/api/credit-cards/', f'/api/credit-cards/{self.cartao.pk}/',
            f'/api/credit-cards/{self.cartao.pk}/invoices/',
            '/api/invoices/', f'/api/invoices/{self.fatura.pk}/',
            f'/api/invoices/{self.fatura.pk}/transactions/',
            f'/api/categories/{self.a.despesa.pk}/', f'/api/tags/{self.tag.pk}/',
            f'/api/budgets/{self.orcamento.pk}/',
            '/api/goals/', f'/api/goals/{self.meta.pk}/', f'/api/goals/{self.meta.pk}/history/',
            '/api/focused-monitors/', f'/api/focused-monitors/{self.monitor.pk}/',
            '/api/users/me/', '/api/auth/me/',
        ]
        for url in rotas:
            self.assert_aceito(url, {})
            self.assert_recusado(url, {'filtro': 1}, 'filtro')

    def test_rotas_do_admin(self):
        self.client.force_authenticate(user=self.admin)
        self.assert_aceito('/api/admin/users/', {
            'page': 1, 'page_size': 10, 'search': 'a', 'show_archived': 'false', 'role': 'USER', 'plan': 'COMMON',
        })
        self.assert_aceito('/api/admin/logs/', {'page': 1, 'page_size': 10})
        self.assert_aceito(f'/api/admin/users/{self.a.usuario.pk}/logs/', {'page': 1, 'page_size': 10})
        self.assert_recusado('/api/admin/logs/', {'search': 'x'}, 'search')
        for url in ('/api/admin/stats/', '/api/admin/settings/', f'/api/admin/users/{self.a.usuario.pk}/',
                    f'/api/admin/users/{self.a.usuario.pk}/financial-stats/'):
            self.assert_aceito(url, {})
            self.assert_recusado(url, {'filtro': 1}, 'filtro')

    def test_rotas_publicas_que_leem_parametros(self):
        self.client.force_authenticate(user=None)
        # O `token` da verificação é conhecido: o link inválido segue a resposta própria
        resp = self.client.get('/api/auth/verify-email/', {'token': uuid.uuid4()})
        self.assertEqual((resp.status_code, resp.data['detail']), (400, 'Link inválido ou expirado.'))
        self.assert_recusado('/api/auth/verify-email/', {'token': uuid.uuid4(), 'x': 1}, 'x')
        self.assertEqual(self.client.get('/api/health/').status_code, 200)

    def test_outros_metodos_nao_sao_afetados(self):
        resp = self.client.post('/api/tags/?x=1', {'name': 'Nova'}, format='json')
        self.assertEqual(resp.status_code, 201)
        resp = self.client.patch(f'/api/tags/{self.tag.pk}/?x=1', {'name': 'Editada'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Tag.objects.get(pk=self.tag.pk).name, 'Editada')
        # A exclusão da meta responde 200 com `piggy_bank_empty` (META-30)
        resp = self.client.delete(f'/api/goals/{self.meta.pk}/?x=1')
        self.assertEqual(resp.status_code, 200)

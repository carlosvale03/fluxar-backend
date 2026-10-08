"""
Erros em português no formato do DRF: erros de campo por campo, e `detail`
com `code` nos demais; nenhuma resposta leva a chave `error` nem o texto de
uma exceção (CONTRATO-29, CONTRATO-30).
"""
import re
import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import Account
from budgets.models import Budget
from goals.models import Goal
from goals.services import GoalService

from .base import URL_TRANSACOES, ContratosTestCase

CAMPO_OBRIGATORIO = ['Este campo é obrigatório.']
APPS_COM_VIEWS = ('accounts', 'api', 'budgets', 'data_exchange', 'goals', 'reports', 'transactions')


class InventarioTests(ContratosTestCase):

    def test_nenhuma_view_devolve_error_nem_texto_de_excecao(self):
        for app in APPS_COM_VIEWS:
            codigo = (Path(settings.BASE_DIR) / app / 'views.py').read_text(encoding='utf-8')
            self.assertIsNone(re.search(r"""['"]error['"]\s*:""", codigo), app)
            self.assertIsNone(re.search(r'str\(e\)', codigo), app)


class FormatoDosErrosTests(ContratosTestCase):

    def test_objeto_inexistente(self):
        resp = self.client.get(f'/api/accounts/{uuid.uuid4()}/')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.data, {'detail': 'Não encontrado.', 'code': 'not_found'})

    def test_filtro_desconhecido_leva_o_codigo(self):
        resp = self.client.get(URL_TRANSACOES, {'limit': 50})
        self.assertEqual(resp.data, {'detail': 'Filtro desconhecido: limit.', 'code': 'invalid'})

    def test_campo_obrigatorio_em_portugues(self):
        resp = self.client.post('/api/tags/', {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {'name': CAMPO_OBRIGATORIO})

    def test_orcamento_duplicado_tem_erro_no_campo_da_categoria(self):
        Budget.objects.create(
            user=self.a.usuario, category=self.a.despesa, month=9, year=2026, amount_limit=Decimal('100.00'),
        )
        resp = self.client.post('/api/budgets/', {
            'category': str(self.a.despesa.pk), 'month': 9, 'year': 2026, 'amount_limit': '200.00',
        }, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {'category': ['Já existe um orçamento para esta categoria neste mês.']})
        self.assertEqual(Budget.objects.filter(user=self.a.usuario).count(), 1)

    def test_erro_inesperado_vira_500_sem_o_texto_da_excecao(self):
        cofrinho = Account.objects.create(user=self.a.usuario, name='Cofrinho', type='PIGGY_BANK')
        meta = Goal.objects.create(user=self.a.usuario, name='Meta', target_amount=Decimal('100.00'), account=cofrinho)
        self.client.raise_request_exception = False

        with patch.object(GoalService, 'aportar', side_effect=RuntimeError('segredo interno do banco')):
            resp = self.client.post(f'/api/goals/{meta.pk}/deposit/', {
                'amount': '10.00', 'account_id': str(self.a.conta.pk),
            }, format='json')

        self.assertEqual(resp.status_code, 500)
        self.assertNotIn('segredo', resp.content.decode('utf-8', 'ignore'))


class RotasReescritasTests(ContratosTestCase):

    def setUp(self):
        super().setUp()
        cofrinho = Account.objects.create(user=self.a.usuario, name='Cofrinho', type='PIGGY_BANK')
        self.meta = Goal.objects.create(
            user=self.a.usuario, name='Meta', target_amount=Decimal('100.00'), account=cofrinho,
        )

    def test_metas(self):
        resp = self.client.post(f'/api/goals/{self.meta.pk}/deposit/', {}, format='json')
        self.assertEqual(resp.data, {'amount': CAMPO_OBRIGATORIO, 'account_id': CAMPO_OBRIGATORIO})

        resp = self.client.post(f'/api/goals/{self.meta.pk}/withdraw/', {
            'amount': '10.00', 'account_to': str(self.a.conta.pk),
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 'invalid')
        # Resgate acima do valor da meta (META-17)
        self.assertEqual(resp.data['detail'], 'A meta tem R$ 0,00 para resgatar.')

        Goal.objects.filter(pk=self.meta.pk).update(current_amount=Decimal('5.00'))
        resp = self.client.delete(f'/api/goals/{self.meta.pk}/')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {
            'detail': 'Resgate o valor da meta antes de excluí-la.',
            'code': 'invalid',
        })

    def test_orcamentos_transacoes_e_relatorios(self):
        resp = self.client.post('/api/budgets/bulk_import/', {}, format='json')
        self.assertEqual(resp.data, {
            'detail': 'Parâmetros source_ids, month e year são obrigatórios.', 'code': 'invalid',
        })
        resp = self.client.post('/api/budgets/bulk_import/', {
            'source_ids': [str(uuid.uuid4())], 'month': 9, 'year': 2026,
        }, format='json')
        self.assertEqual((resp.status_code, resp.data), (404, {
            'detail': 'Nenhum orçamento de origem encontrado.', 'code': 'not_found',
        }))

        resp = self.client.delete(f'{URL_TRANSACOES}bulk-delete/')
        self.assertEqual(resp.data, {'detail': 'Informe recurring_source ou transfer_id.', 'code': 'invalid'})
        resp = self.client.patch(f'{URL_TRANSACOES}bulk-update/', {}, format='json')
        self.assertEqual(resp.data, {'recurring_source': CAMPO_OBRIGATORIO})

        resp = self.client.get('/api/reports/charts/tag-insights/')
        self.assertEqual((resp.status_code, resp.data), (400, {'tag_id': CAMPO_OBRIGATORIO}))
        resp = self.client.get('/api/reports/charts/tag-insights/', {'tag_id': uuid.uuid4()})
        self.assertEqual((resp.status_code, resp.data), (404, {'detail': 'Tag não encontrada.', 'code': 'not_found'}))
        resp = self.client.get('/api/reports/dashboard/', {'month': 'x'})
        self.assertEqual(resp.data, {'detail': 'Mês/Ano inválidos.', 'code': 'invalid'})

    def test_importacao(self):
        resp = self.client.post('/api/import/ofx/', {'account_id': str(self.a.conta.pk)}, format='multipart')
        self.assertEqual((resp.status_code, resp.data), (400, {'file': ['Arquivo não enviado.']}))

        arquivo = SimpleUploadedFile('lixo.xlsx', b'nada de planilha aqui', content_type='application/octet-stream')
        resp = self.client.post('/api/import/spreadsheet/preflight/', {'file': arquivo}, format='multipart')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {
            'file': ['Não foi possível ler o arquivo.'],
        })

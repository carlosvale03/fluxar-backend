"""
Datas sem hora no aporte e no resgate de meta e datas com hora em ISO 8601
com fuso (CONTRATO-22, CONTRATO-23, CONTRATO-25).
"""
import re
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from accounts.models import Account
from goals.models import Goal, GoalDeposit
from transactions.models import Transaction

from .base import URL_TRANSACOES, ContratosTestCase

DATA_INVALIDA = ['Data inválida. Use o formato AAAA-MM-DD.']
ISO_COM_FUSO = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$')


class DataDoMovimentoDaMetaTests(ContratosTestCase):

    def setUp(self):
        super().setUp()
        cofrinho = Account.objects.create(user=self.a.usuario, name='Cofrinho', type='PIGGY_BANK')
        self.meta = Goal.objects.create(
            user=self.a.usuario, name='Viagem', target_amount=Decimal('1000.00'), account=cofrinho,
        )

    def aportar(self, **extra):
        return self.client.post(f'/api/goals/{self.meta.pk}/deposit/', {
            'amount': '100.00', 'account_id': str(self.a.conta.pk), **extra,
        }, format='json')

    def resgatar(self, **extra):
        return self.client.post(f'/api/goals/{self.meta.pk}/withdraw/', {
            'amount': '40.00', 'account_to': str(self.a.conta.pk), **extra,
        }, format='json')

    def test_aporte_grava_a_data_enviada(self):
        resp = self.aportar(date='2026-12-31')

        self.assertEqual(resp.status_code, 200, resp.data)
        movimento = GoalDeposit.objects.get(goal=self.meta)
        self.assertEqual(movimento.date, date(2026, 12, 31))
        self.assertEqual(
            set(Transaction.objects.filter(transfer_id=movimento.transaction_id).values_list('date', flat=True)),
            {date(2026, 12, 31)},
        )

    def test_data_com_hora_ou_invalida_e_recusada_sem_gravar(self):
        for valor in ('2026-12-31T03:00:00Z', '31/12/2026', '2026-02-30'):
            resp = self.aportar(date=valor)
            self.assertEqual(resp.status_code, 400, valor)
            self.assertEqual(resp.data['date'], DATA_INVALIDA, valor)
        self.assertFalse(GoalDeposit.objects.exists())
        self.assertFalse(Transaction.objects.filter(user=self.a.usuario).exists())

    def test_sem_data_grava_hoje_em_brasilia(self):
        # 23h de 3 de outubro em Brasília já é dia 4 em UTC
        agora = datetime(2026, 10, 4, 2, 0, tzinfo=dt_timezone.utc)
        with mock.patch('django.utils.timezone.now', return_value=agora):
            self.assertEqual(self.aportar().status_code, 200)
            self.assertEqual(self.resgatar().status_code, 200)

        self.assertEqual(
            sorted(GoalDeposit.objects.values_list('type', 'date')),
            [('DEPOSIT', date(2026, 10, 3)), ('WITHDRAWAL', date(2026, 10, 3))],
        )

    def test_resgate_grava_a_data_enviada_e_recusa_data_com_hora(self):
        self.assertEqual(self.aportar(date='2026-12-01').status_code, 200)

        resp = self.resgatar(date='2026-12-31T10:00:00-03:00')
        self.assertEqual((resp.status_code, resp.data['date']), (400, DATA_INVALIDA))

        self.assertEqual(self.resgatar(date='2026-12-31').status_code, 200)
        self.assertEqual(GoalDeposit.objects.get(type='WITHDRAWAL').date, date(2026, 12, 31))

    def test_campo_datetime_nao_e_mais_lido(self):
        agora = datetime(2026, 10, 3, 15, 0, tzinfo=dt_timezone.utc)
        with mock.patch('django.utils.timezone.now', return_value=agora):
            self.assertEqual(self.aportar(datetime='2026-12-31').status_code, 200)

        self.assertEqual(GoalDeposit.objects.get().date, date(2026, 10, 3))


class DataComHoraTests(ContratosTestCase):

    def test_created_at_em_iso_8601_com_fuso(self):
        self.lancar()

        item = self.client.get(URL_TRANSACOES).json()['results'][0]

        self.assertRegex(item['created_at'], ISO_COM_FUSO)
        self.assertEqual(item['date'], '2026-09-15')

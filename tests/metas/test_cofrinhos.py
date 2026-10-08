"""
Cofrinhos, meta concluída e sugestão mensal (META-02, META-04, META-23, META-24).
"""
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from accounts.models import Account
from goals.models import Goal
from goals.valores import recalcular
from tests.metas.base import MetasTestCase, registrar, transferir

URL_COFRINHOS = '/api/goals/piggy-banks/'


class CofrinhosTests(MetasTestCase):

    def aporte(self, meta, valor):
        transferencia = transferir(self.a.conta, meta.account, valor)
        registrar(meta, 'DEPOSIT', valor, conta=self.a.conta, transferencia=transferencia)
        recalcular(meta.pk)

    def test_um_item_por_cofrinho_com_saldo_soma_das_metas_e_saldo_livre_em_texto(self):
        arquivada = Goal.objects.create(
            user=self.a.usuario, name='Antiga', target_amount=Decimal('100.00'),
            account=self.a.cofrinho, is_active=False,
        )
        self.aporte(self.a.meta, '300.00')
        self.aporte(arquivada, '50.00')
        # Dinheiro que entra por fora fica livre
        transferir(self.a.conta, self.a.cofrinho, '25.50')
        reserva = Account.objects.create(user=self.a.usuario, name='Reserva', type='PIGGY_BANK')
        Goal.objects.create(user=self.a.usuario, name='Casa', target_amount=Decimal('10.00'), account=reserva)
        # Cofrinho sem meta não aparece
        Account.objects.create(user=self.a.usuario, name='Vazio', type='PIGGY_BANK')

        resp = self.client.get(URL_COFRINHOS)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, [
            {'account_id': self.a.cofrinho.pk, 'name': 'Cofrinho A', 'balance': '375.50',
             'goals_total': '350.00', 'free_balance': '25.50'},
            {'account_id': reserva.pk, 'name': 'Reserva', 'balance': '0.00',
             'goals_total': '0.00', 'free_balance': '0.00'},
        ])

    def test_saldo_livre_negativo_aparece_negativo(self):
        self.aporte(self.a.meta, '300.00')
        # Transferência comum de R$ 500,00 para fora do cofrinho, com R$ 300,00 nele
        transferir(self.a.cofrinho, self.a.conta, '500.00')

        resp = self.client.get(URL_COFRINHOS)

        self.assertEqual(resp.data, [
            {'account_id': self.a.cofrinho.pk, 'name': 'Cofrinho A', 'balance': '-200.00',
             'goals_total': '300.00', 'free_balance': '-500.00'},
        ])

    def test_meta_que_atinge_o_alvo_fica_concluida_e_ainda_recebe_aporte(self):
        resp = self.client.post(f'/api/goals/{self.a.meta.pk}/deposit/', {
            'amount': '1000.00', 'account_id': str(self.a.conta.pk), 'date': '2026-09-15',
        }, format='json')
        self.assertEqual((resp.status_code, resp.data['status']), (200, 'COMPLETED'))

        resp = self.client.post(f'/api/goals/{self.a.meta.pk}/deposit/', {
            'amount': '0.01', 'account_id': str(self.a.conta.pk),
            'date': '2026-09-15',
        }, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual((resp.data['status'], resp.data['current_amount']), ('COMPLETED', '1000.01'))


class SugestaoMensalTests(MetasTestCase):

    def detalhe(self, alvo):
        Goal.objects.filter(pk=self.a.meta.pk).update(target_date=alvo)
        registrar(self.a.meta, 'DEPOSIT', '400.00')
        recalcular(self.a.meta.pk)
        # 23h de 31 de outubro em Brasília já é 1º de novembro em UTC
        agora = datetime(2026, 11, 1, 2, 0, tzinfo=dt_timezone.utc)
        with mock.patch('django.utils.timezone.now', return_value=agora):
            return self.client.get(f'/api/goals/{self.a.meta.pk}/').data

    def test_conta_os_meses_a_partir_do_dia_de_brasilia(self):
        dados = self.detalhe(date(2026, 12, 15))

        # De outubro a dezembro: 2 meses para os R$ 600,00 que faltam
        self.assertEqual(dados['months_remaining'], 2)
        self.assertEqual(dados['suggested_monthly_saving'], '300.00')

    def test_minimo_de_um_mes(self):
        dados = self.detalhe(date(2026, 10, 31))

        self.assertEqual(dados['months_remaining'], 1)
        self.assertEqual(dados['suggested_monthly_saving'], '600.00')

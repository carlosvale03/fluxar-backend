"""
Correção dos valores gravados (META-10, META-11).

A migração recalcula todas as metas pela regra META-01; a que ficaria
negativa vai a zero com um registro de correção, e a meta mostra uma vez o
valor de antes e o de depois. O relógio fica em 2026-10-09 01:00 UTC: em
Brasília ainda é 2026-10-08.
"""
import importlib
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.apps import apps
from django.db import connection, migrations
from django.db.migrations.executor import MigrationExecutor

from goals.models import Goal, GoalDeposit
from transactions.models import Transaction
from tests.metas.base import DIA, MetasTestCase, registrar, transferir

# O nome do módulo começa com dígito, por isso o import_module
migracao = importlib.import_module('goals.migrations.0009_recalcula_metas')


class MigracaoDoRecalculoTests(MetasTestCase):

    def corrigir(self, registro=apps):
        agora = datetime(2026, 10, 9, 1, 0, tzinfo=dt_timezone.utc)
        with mock.patch('django.utils.timezone.now', return_value=agora):
            migracao.recalcular(registro, None)

    def meta_com_resgate_maior_que_os_aportes(self):
        """Como depois de FIN-09: o aporte de R$ 50,00 sumiu e o resgate de R$ 100,00 ficou."""
        registrar(self.a.meta, 'DEPOSIT', '50.00')
        registrar(self.a.meta, 'WITHDRAWAL', '100.00', conta=self.a.conta)
        Goal.objects.filter(pk=self.a.meta.pk).update(current_amount=Decimal('50.00'))

    def test_e_a_migracao_seguinte_a_dos_campos(self):
        self.assertEqual(set(migracao.Migration.dependencies), {
            ('goals', '0008_valor_derivado_das_metas'),
            ('transactions', '0010_importacao'),
        })
        [operacao] = migracao.Migration.operations
        self.assertIsInstance(operacao, migrations.RunPython)
        self.assertIs(operacao.code, migracao.recalcular)
        self.assertIs(operacao.reverse_code, migrations.RunPython.noop)

    def test_meta_inflada_pelo_rateio_volta_a_soma_dos_registros(self):
        # Registros antigos: aporte manual por transferência e rateio de uma receita pendente
        transfer_id, _, _ = transferir(self.a.conta, self.a.cofrinho, '300.00')
        registrar(self.a.meta, 'DEPOSIT', '300.00', conta=self.a.conta, transaction_id=transfer_id)
        receita = Transaction.objects.create(
            user=self.a.usuario, account=self.a.cofrinho, type='INCOME', status='PENDING',
            description='Guardado', amount=Decimal('80.00'), date=DIA,
        )
        registrar(self.a.meta, 'DEPOSIT', '40.00', transaction_id=receita.pk, description='Automático: Guardado')
        registrar(self.a.meta, 'WITHDRAWAL', '25.00', description='Automático: Lanche')
        Goal.objects.filter(pk=self.a.meta.pk).update(current_amount=Decimal('999.99'))

        self.corrigir()

        meta = self.recarregar(self.a.meta)
        self.assertEqual(meta.current_amount, Decimal('275.00'))
        self.assertIsNone(meta.valor_antes_da_correcao)
        self.assertFalse(GoalDeposit.objects.filter(eh_correcao=True).exists())

    def test_meta_negativa_vai_a_zero_com_registro_de_correcao(self):
        self.meta_com_resgate_maior_que_os_aportes()

        self.corrigir()

        meta = self.recarregar(self.a.meta)
        self.assertEqual((meta.current_amount, meta.valor_antes_da_correcao), (Decimal('0.00'), Decimal('-50.00')))
        correcao = GoalDeposit.objects.get(goal=self.a.meta, eh_correcao=True)
        self.assertEqual(
            (correcao.type, correcao.amount, correcao.description, correcao.date, correcao.account_id),
            ('DEPOSIT', Decimal('50.00'), 'Correção do valor da meta', date(2026, 10, 8), self.a.cofrinho.pk),
        )

        resp = self.client.get(f'/api/goals/{self.a.meta.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['correction'], {'before': '-50.00', 'after': '0.00'})
        self.assertEqual(resp.data['current_amount'], '0.00')

    def test_depois_de_dismiss_correction_o_aviso_nao_aparece_mais(self):
        self.meta_com_resgate_maior_que_os_aportes()
        self.corrigir()

        resp = self.client.post(f'/api/goals/{self.a.meta.pk}/dismiss-correction/')

        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['correction'])
        self.assertIsNone(self.client.get(f'/api/goals/{self.a.meta.pk}/').data['correction'])
        self.assertIsNone(self.client.get('/api/goals/').data[0]['correction'])
        # O valor e o registro de correção continuam
        self.assertEqual(self.valor(self.a.meta), Decimal('0.00'))
        self.assertTrue(GoalDeposit.objects.filter(goal=self.a.meta, eh_correcao=True).exists())

    def test_meta_sem_correcao_nao_traz_aviso(self):
        resp = self.client.get(f'/api/goals/{self.a.meta.pk}/')

        self.assertIsNone(resp.data['correction'])

    def test_banco_sem_metas_nao_faz_nada(self):
        Goal.objects.all().delete()

        self.corrigir()

        self.assertFalse(Goal.objects.exists())
        self.assertFalse(GoalDeposit.objects.exists())

    def test_funciona_com_o_registro_historico_de_models(self):
        self.meta_com_resgate_maior_que_os_aportes()
        estado = MigrationExecutor(connection).loader.project_state(('goals', '0009_recalcula_metas'))

        self.corrigir(estado.apps)

        self.assertEqual(self.recarregar(self.a.meta).valor_antes_da_correcao, Decimal('-50.00'))
        self.assertEqual(self.valor(self.a.meta), Decimal('0.00'))

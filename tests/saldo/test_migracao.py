"""
Migração de correção dos saldos (SALDO-37, SALDO-38).

Na implantação, as ocorrências geradas por série que estejam efetivadas com
data depois de hoje voltam a pendentes, menos a primeira de cada série, e o
saldo de todas as contas é recalculado por SALDO-01. O relógio fica em
2026-10-01 02:00 UTC: em Brasília ainda é 2026-09-30.
"""
import importlib
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.apps import apps
from django.db import connection, migrations
from django.db.migrations.executor import MigrationExecutor

from accounts.models import Account
from accounts.saldo import calcular
from transactions.models import RecurringTransaction, Transaction
from tests.saldo.base import SaldoTestCase

# O nome do módulo começa com dígito, por isso o import_module
migracao = importlib.import_module('transactions.migrations.0008_corrige_saldos')


def relogio_em_2026_10_01_2h_utc():
    return mock.patch(
        'django.utils.timezone.now',
        return_value=datetime(2026, 10, 1, 2, 0, tzinfo=dt_timezone.utc),
    )


class MigracaoDeCorrecaoDosSaldosTests(SaldoTestCase):

    def setUp(self):
        super().setUp()
        self.serie = self.criar_serie('Salário', 'INCOME', '5000.00')
        datas = [date(2026, 9, 15), date(2026, 9, 30), date(2026, 10, 1), date(2026, 11, 15), date(2026, 12, 15)]
        # Como antes da correção: todas as ocorrências gravadas efetivadas
        self.ocorrencias = [
            self.lancar(self.a.conta, 'INCOME', '5000.00', date=d, recurring_source=self.serie)
            for d in datas
        ]
        self.pendente = self.lancar(
            self.a.conta, 'INCOME', '5000.00', status='PENDING',
            date=date(2027, 1, 15), recurring_source=self.serie,
        )

        # Série cuja primeira ocorrência já tem data futura
        self.serie_futura = self.criar_serie('Aluguel', 'EXPENSE', '800.00')
        self.primeira_futura = self.lancar(
            self.a.poupanca, 'EXPENSE', '800.00', date=date(2026, 10, 10),
            recurring_source=self.serie_futura,
        )
        self.segunda_futura = self.lancar(
            self.a.poupanca, 'EXPENSE', '800.00', date=date(2026, 11, 10),
            recurring_source=self.serie_futura,
        )

        # Efetivada com data futura fora de série: continua efetivada (AD-002)
        self.avulsa = self.lancar(self.a.conta, 'EXPENSE', '100.00', date=date(2026, 12, 1))

        # Conta excluída com movimento e transação de B gravada à força na conta de A
        self.excluida = Account.objects.create(
            user=self.a.usuario, name='Antiga', type='CHECKING', initial_balance=Decimal('50.00'),
        )
        self.lancar(self.excluida, 'EXPENSE', '20.00')
        self.lancar(self.a.conta, 'INCOME', '999.00', usuario=self.b.usuario)
        Account.objects.filter(pk=self.excluida.pk).update(is_active=False)

        # Saldos gravados errados pelos bugs antigos
        Account.objects.filter(user__in=[self.a.usuario, self.b.usuario]).update(balance=Decimal('12345.67'))

    def criar_serie(self, descricao, tipo, valor):
        return RecurringTransaction.objects.create(
            user=self.a.usuario, description=descricao, amount=Decimal(valor), type=tipo,
            account=self.a.conta, frequency='MONTHLY', start_date=date(2026, 9, 15),
        )

    def status(self, *transacoes):
        return [Transaction.objects.get(pk=t.pk).status for t in transacoes]

    def corrigir(self, registro=apps):
        with relogio_em_2026_10_01_2h_utc():
            migracao.corrigir(registro, None)

    def test_depende_das_ultimas_migracoes_de_transactions_e_accounts(self):
        self.assertEqual(set(migracao.Migration.dependencies), {
            ('transactions', '0007_corrige_isolamento'),
            ('accounts', '0004_account_balance'),
        })
        [operacao] = migracao.Migration.operations
        self.assertIsInstance(operacao, migrations.RunPython)
        self.assertIs(operacao.code, migracao.corrigir)
        self.assertIs(operacao.reverse_code, migrations.RunPython.noop)

    def test_ocorrencias_futuras_efetivadas_voltam_a_pendentes_menos_a_primeira(self):
        self.corrigir()

        # Até hoje em Brasília (30/09) continuam efetivadas; 01/10 em diante voltam
        self.assertEqual(
            self.status(*self.ocorrencias, self.pendente),
            ['COMPLETED', 'COMPLETED', 'PENDING', 'PENDING', 'PENDING', 'PENDING'],
        )
        # A primeira de cada série fica como estava, mesmo com data futura
        self.assertEqual(self.status(self.primeira_futura, self.segunda_futura), ['COMPLETED', 'PENDING'])
        self.assertEqual(self.status(self.avulsa), ['COMPLETED'])

    def test_primeira_ocorrencia_desempata_pela_criacao(self):
        """Duas ocorrências na mesma data: a primeira é a criada antes."""
        serie = self.criar_serie('Assinatura', 'EXPENSE', '30.00')
        criada_antes = self.lancar(self.a.conta, 'EXPENSE', '30.00', date=date(2026, 10, 20), recurring_source=serie)
        criada_depois = self.lancar(self.a.conta, 'EXPENSE', '30.00', date=date(2026, 10, 20), recurring_source=serie)

        self.corrigir()

        self.assertEqual(self.status(criada_antes, criada_depois), ['COMPLETED', 'PENDING'])

    def test_saldos_de_todas_as_contas_ficam_iguais_a_saldo_01(self):
        self.corrigir()

        contas = Account.objects.filter(user__in=[self.a.usuario, self.b.usuario])
        self.assertEqual(
            {c.pk: c.balance for c in contas},
            {c.pk: calcular(c) for c in contas},
        )
        # 1.000 + 2 salários até hoje - a avulsa; sem a receita de B
        self.assertEqual(self.saldo(self.a.conta), Decimal('10900.00'))
        self.assertEqual(self.saldo(self.a.poupanca), Decimal('-800.00'))
        self.assertEqual(self.saldo(self.excluida), Decimal('30.00'))
        self.assertEqual(self.saldo(self.b.conta), Decimal('1000.00'))

    def test_funciona_com_o_registro_historico_de_models(self):
        estado = MigrationExecutor(connection).loader.project_state(
            ('transactions', '0008_corrige_saldos'),
        )

        self.corrigir(estado.apps)

        self.assertEqual(self.status(self.ocorrencias[3]), ['PENDING'])
        self.assertEqual(self.saldo(self.a.conta), Decimal('10900.00'))

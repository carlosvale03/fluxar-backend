import importlib
from decimal import Decimal

from django.apps import apps
from django.db import connection, migrations
from django.db.migrations.executor import MigrationExecutor

from accounts.models import Account
from core.isolation import find_cross_links
from tests.isolamento.base import DoisUsuariosTestCase
from tests.isolamento.ligacoes import gravar_ligacoes_cruzadas

# O nome do módulo começa com dígito, por isso o import_module
migracao = importlib.import_module('transactions.migrations.0007_corrige_isolamento')


class MigracaoDaCorrecaoTests(DoisUsuariosTestCase):

    def test_depende_das_ultimas_migracoes_das_apps_corrigidas(self):
        self.assertEqual(set(migracao.Migration.dependencies), {
            ('transactions', '0006_transaction_payment_date'),
            ('accounts', '0004_account_balance'),
            ('budgets', '0001_initial'),
            ('goals', '0007_alter_goal_image'),
            ('reports', '0001_initial'),
        })
        [operacao] = migracao.Migration.operations
        self.assertIsInstance(operacao, migrations.RunPython)
        self.assertIs(operacao.code, migracao.corrigir)
        self.assertIs(operacao.reverse_code, migrations.RunPython.noop)

    def test_corrigir_desfaz_as_ligacoes_gravadas(self):
        gravar_ligacoes_cruzadas(self.a, self.b, self.categoria_modelo)

        migracao.corrigir(apps, None)

        self.assertEqual(find_cross_links(apps), [])
        # A conta de B deixa de contar a receita de A (SALDO-01)
        self.assertEqual(Account.objects.get(pk=self.b.conta.pk).balance, Decimal('1000.00'))

    def test_corrigir_funciona_com_o_registro_historico_de_models(self):
        gravar_ligacoes_cruzadas(self.a, self.b, self.categoria_modelo)
        estado = MigrationExecutor(connection).loader.project_state(
            ('transactions', '0007_corrige_isolamento'),
        )

        migracao.corrigir(estado.apps, None)

        self.assertEqual(find_cross_links(apps), [])
        self.assertEqual(Account.objects.get(pk=self.b.conta.pk).balance, Decimal('1000.00'))

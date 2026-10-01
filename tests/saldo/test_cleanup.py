"""
Comando de limpeza do banco (SALDO-47).

O `cleanup_db` não pode apagar o histórico das contas excluídas nem mudar o
saldo das contas ativas. Ele só apaga contas excluídas sem nada ligado a
elas, e a opção `--all-transactions`, que apagava todas as transações,
deixa de existir.
"""
from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.models import Account
from goals.models import GoalDeposit
from transactions.models import RecurringTransaction, Transaction
from transactions.services import TransactionService
from tests.saldo.base import SaldoTestCase


class CleanupDbTests(SaldoTestCase):

    def setUp(self):
        super().setUp()
        # Conta que teve movimento, inclusive uma transferência com a corrente,
        # e foi zerada e excluída
        self.excluida = Account.objects.create(
            user=self.a.usuario, name='Antiga', type='CHECKING', initial_balance=Decimal('0.00'),
        )
        self.lancar(self.excluida, 'INCOME', '200.00')
        TransactionService.create_transfer(
            user=self.a.usuario, account_from=self.excluida, account_to=self.a.conta,
            amount=Decimal('200.00'), date=date(2026, 9, 16),
        )
        Account.objects.filter(pk=self.excluida.pk).update(is_active=False)

    def limpar(self):
        call_command('cleanup_db', stdout=StringIO())

    def fotografia(self):
        """Contas com saldo e todas as transações, campo a campo."""
        return (
            sorted(Account.objects.values_list('id', 'is_active', 'balance')),
            sorted(Transaction.objects.values_list('id', 'account_id', 'type', 'status', 'amount')),
        )

    def test_mantem_o_historico_da_conta_excluida_e_os_saldos_das_ativas(self):
        self.assertEqual(self.saldo(self.a.conta), Decimal('1200.00'))
        antes = self.fotografia()

        self.limpar()

        self.assertEqual(self.fotografia(), antes)
        self.assertEqual(
            sorted(Transaction.objects.filter(account=self.excluida).values_list('type', 'amount')),
            [('INCOME', Decimal('200.00')), ('TRANSFER_OUT', Decimal('200.00'))],
        )
        self.assertEqual(self.saldo(self.a.conta), Decimal('1200.00'))

    def test_mantem_conta_excluida_com_aporte_de_meta_ou_serie(self):
        com_aporte = Account.objects.create(user=self.a.usuario, name='Aporte', type='CHECKING')
        GoalDeposit.objects.create(
            goal=self.a.meta, account=com_aporte, amount=Decimal('10.00'), date=date(2026, 9, 15),
        )
        com_serie = Account.objects.create(user=self.a.usuario, name='Série', type='CHECKING')
        RecurringTransaction.objects.create(
            user=self.a.usuario, description='Aluguel', amount=Decimal('10.00'), type='EXPENSE',
            account=com_serie, frequency='MONTHLY', start_date=date(2026, 9, 1),
        )
        Account.objects.filter(pk__in=[com_aporte.pk, com_serie.pk]).update(is_active=False)

        self.limpar()

        self.assertEqual(Account.objects.filter(pk__in=[com_aporte.pk, com_serie.pk]).count(), 2)
        self.assertEqual(GoalDeposit.objects.filter(account=com_aporte).count(), 1)
        self.assertEqual(RecurringTransaction.objects.filter(account=com_serie).count(), 1)

    def test_apaga_so_a_conta_excluida_sem_nada_ligado(self):
        vazia = Account.objects.create(user=self.a.usuario, name='Vazia', type='CHECKING')
        Account.objects.filter(pk=vazia.pk).update(is_active=False)

        self.limpar()

        self.assertFalse(Account.objects.filter(pk=vazia.pk).exists())
        self.assertTrue(Account.objects.filter(pk=self.excluida.pk).exists())

    def test_opcao_all_transactions_nao_existe_mais(self):
        antes = self.fotografia()

        with self.assertRaises(CommandError):
            call_command('cleanup_db', '--all-transactions', stdout=StringIO())

        self.assertEqual(self.fotografia(), antes)

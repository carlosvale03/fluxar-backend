from datetime import date
from decimal import Decimal

from goals.models import Goal, GoalDeposit
from transactions.models import Transaction
from tests.isolamento.base import DoisUsuariosTestCase


class SignalMetasDoCofrinhoTests(DoisUsuariosTestCase):
    """
    O signal de metas roda em `transaction.on_commit`; dentro do TestCase, o
    `captureOnCommitCallbacks(execute=True)` executa o callback ao fim do bloco.
    """

    def setUp(self):
        # Meta de B ligada à força ao cofrinho de A, como antes da correção
        Goal.objects.filter(pk=self.b.meta.pk).update(account=self.a.cofrinho)

    def test_entrada_no_cofrinho_de_a_nao_gera_aporte_na_meta_de_b(self):
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.como(self.a.usuario).post('/api/transactions/', {
                'type': 'INCOME', 'status': 'COMPLETED', 'description': 'Guardado',
                'amount': '100.00', 'date': '2026-09-15', 'account': str(self.a.cofrinho.id),
            }, format='json')

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(GoalDeposit.objects.filter(goal=self.b.meta).exists())
        self.assertEqual(Goal.objects.get(pk=self.b.meta.pk).current_amount, Decimal('0.00'))
        # A meta de A recebe o movimento inteiro
        aporte = GoalDeposit.objects.get(goal=self.a.meta)
        self.assertEqual((aporte.type, aporte.amount, aporte.account), ('DEPOSIT', Decimal('100.00'), self.a.cofrinho))
        self.assertEqual(Goal.objects.get(pk=self.a.meta.pk).current_amount, Decimal('100.00'))

    def test_saida_do_cofrinho_de_a_nao_resgata_da_meta_de_b(self):
        Goal.objects.filter(pk=self.a.meta.pk).update(current_amount=Decimal('100.00'))
        Goal.objects.filter(pk=self.b.meta.pk).update(current_amount=Decimal('300.00'))

        with self.captureOnCommitCallbacks(execute=True):
            Transaction.objects.create(
                user=self.a.usuario, type='EXPENSE', status='COMPLETED', description='Retirada',
                amount=Decimal('40.00'), date=date(2026, 9, 15), account=self.a.cofrinho,
            )

        self.assertFalse(GoalDeposit.objects.filter(goal=self.b.meta).exists())
        self.assertEqual(Goal.objects.get(pk=self.b.meta.pk).current_amount, Decimal('300.00'))
        resgate = GoalDeposit.objects.get(goal=self.a.meta)
        self.assertEqual((resgate.type, resgate.amount), ('WITHDRAWAL', Decimal('40.00')))
        self.assertEqual(Goal.objects.get(pk=self.a.meta.pk).current_amount, Decimal('60.00'))

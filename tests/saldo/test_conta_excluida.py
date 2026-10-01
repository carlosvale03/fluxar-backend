"""
Conta excluída (SALDO-35, SALDO-36, AD-003).

Uma conta excluída não recebe movimentação nova: transação, transferência,
pagamento de fatura, aporte e resgate que a indiquem recebem HTTP 400 com o
erro no campo da conta, a mesma resposta de uma conta inexistente.
"""
from decimal import Decimal

from accounts.models import Account, CreditCardInvoice
from goals.models import Goal, GoalDeposit
from transactions.models import Transaction
from tests.saldo.base import SaldoTestCase, URL_TRANSACOES

CONTA_NAO_ENCONTRADA = 'Conta não encontrada.'


class ContaExcluidaTestCase(SaldoTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.excluida = Account.objects.create(
            user=cls.a.usuario, name='Antiga A', type='CHECKING',
            initial_balance=Decimal('0.00'),
        )
        Account.objects.filter(pk=cls.excluida.pk).update(is_active=False)

    def setUp(self):
        super().setUp()
        Goal.objects.filter(pk=self.a.meta.pk).update(current_amount=Decimal('500.00'))

    def estado(self):
        return (
            sorted(Account.objects.values_list('id', 'balance', 'is_active')),
            sorted(Transaction.objects.values_list('id', 'type', 'status', 'account_id', 'amount', 'description')),
            sorted(CreditCardInvoice.objects.values_list('id', 'status')),
            sorted(Goal.objects.values_list('id', 'current_amount')),
            GoalDeposit.objects.count(),
        )


class OperacaoNovaEmContaExcluidaTests(ContaExcluidaTestCase):

    def assert_recusa(self, url, corpo, campo):
        antes = self.estado()
        resp = self.cliente.post(url, corpo, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data[campo], [CONTA_NAO_ENCONTRADA])
        self.assertEqual(self.estado(), antes)

    def test_transacao_em_conta_excluida_recusada(self):
        self.assert_recusa(URL_TRANSACOES, self.payload(account=str(self.excluida.id)), 'account')

    def test_transferencia_com_origem_excluida_recusada(self):
        self.assert_recusa(f'{URL_TRANSACOES}transfer/', {
            'account_from': str(self.excluida.id), 'account_to': str(self.a.conta.id),
            'amount': '100.00', 'date': '2026-09-15',
        }, 'account_from')

    def test_transferencia_com_destino_excluido_recusada(self):
        self.assert_recusa(f'{URL_TRANSACOES}transfer/', {
            'account_from': str(self.a.conta.id), 'account_to': str(self.excluida.id),
            'amount': '100.00', 'date': '2026-09-15',
        }, 'account_to')

    def test_pagamento_de_fatura_com_conta_excluida_recusado(self):
        self.lancar(
            self.a.conta, 'CREDIT_CARD', '100.00', status='PENDING',
            credit_card=self.a.cartao, invoice=self.a.fatura,
        )
        self.assert_recusa(f'/api/invoices/{self.a.fatura.id}/pay/', {
            'account_id': str(self.excluida.id), 'amount': '100.00', 'date': '2026-09-20',
        }, 'account_id')

    def test_aporte_de_conta_excluida_recusado(self):
        self.assert_recusa(f'/api/goals/{self.a.meta.id}/deposit/', {
            'account_id': str(self.excluida.id), 'amount': '100.00', 'date': '2026-09-15',
        }, 'account_id')

    def test_resgate_para_conta_excluida_recusado(self):
        self.assert_recusa(f'/api/goals/{self.a.meta.id}/withdraw/', {
            'account_to': str(self.excluida.id), 'amount': '100.00', 'date': '2026-09-15',
        }, 'account_to')

    def test_edicao_que_move_a_transacao_para_conta_excluida_recusada(self):
        t = self.lancar(self.a.conta, 'EXPENSE', '100.00')
        antes = self.estado()
        resp = self.cliente.patch(f'{URL_TRANSACOES}{t.id}/', {'account': str(self.excluida.id)}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data['account'], [CONTA_NAO_ENCONTRADA])
        self.assertEqual(self.estado(), antes)

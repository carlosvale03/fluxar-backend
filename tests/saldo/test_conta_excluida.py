"""
Conta excluída (SALDO-35, SALDO-36, AD-003).

Uma conta excluída não recebe movimentação nova: transação, transferência,
pagamento de fatura, aporte e resgate que a indiquem recebem HTTP 400 com o
erro no campo da conta, a mesma resposta de uma conta inexistente.
"""
import uuid
from datetime import date
from decimal import Decimal

from rest_framework.exceptions import ValidationError

from accounts.models import Account, CreditCard, CreditCardInvoice
from goals.models import Goal, GoalDeposit
from transactions.models import Transaction
from transactions.services import TransactionService
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


MENSAGEM_HISTORICO = 'Esta transação é de uma conta excluída e não pode ser alterada.'


class HistoricoDaContaExcluidaTests(ContaExcluidaTestCase):
    """
    O histórico da conta excluída fica só para leitura (SALDO-36): editar ou
    excluir uma transação dela, ou uma transferência com uma perna nela,
    recebe 400 sem mudar nada.
    """

    def setUp(self):
        super().setUp()
        self.antiga = self.lancar(self.excluida, 'INCOME', '100.00', description='Antiga')
        self.transferencia = uuid.uuid4()
        self.saida = self.lancar(
            self.a.conta, 'TRANSFER_OUT', '50.00', transfer_id=self.transferencia, description='Para a antiga',
        )
        self.entrada = self.lancar(
            self.excluida, 'TRANSFER_IN', '50.00', transfer_id=self.transferencia, description='Da corrente',
        )

    def url(self, t):
        return f'{URL_TRANSACOES}{t.id}/'

    def corpo_put(self, t, **extra):
        dados = {
            'type': t.type, 'status': 'COMPLETED', 'description': 'Editada',
            'amount': '999.00', 'date': '2026-09-20',
        }
        dados.update(extra)
        return dados

    def assert_recusa(self, chamada):
        antes = self.estado()
        resp = chamada()
        self.assertEqual(resp.status_code, 400, getattr(resp, 'data', None))
        self.assertEqual(resp.data, {'detail': MENSAGEM_HISTORICO})
        self.assertEqual(self.estado(), antes)

    def test_patch_de_transacao_da_conta_excluida_recusado(self):
        self.assert_recusa(lambda: self.cliente.patch(self.url(self.antiga), {'amount': '999.00'}, format='json'))

    def test_put_de_transacao_da_conta_excluida_recusado(self):
        self.assert_recusa(lambda: self.cliente.put(
            self.url(self.antiga), self.corpo_put(self.antiga, account=str(self.a.conta.id)), format='json',
        ))

    def test_delete_de_transacao_da_conta_excluida_recusado(self):
        self.assert_recusa(lambda: self.cliente.delete(self.url(self.antiga)))

    def test_patch_da_perna_ativa_de_transferencia_com_conta_excluida_recusado(self):
        self.assert_recusa(lambda: self.cliente.patch(self.url(self.saida), {'amount': '999.00'}, format='json'))

    def test_put_da_perna_ativa_de_transferencia_com_conta_excluida_recusado(self):
        self.assert_recusa(lambda: self.cliente.put(self.url(self.saida), self.corpo_put(self.saida), format='json'))

    def test_delete_das_pernas_de_transferencia_com_conta_excluida_recusado(self):
        self.assert_recusa(lambda: self.cliente.delete(self.url(self.saida)))
        self.assert_recusa(lambda: self.cliente.delete(self.url(self.entrada)))

    def test_exclusao_em_lote_de_transferencia_com_conta_excluida_recusada(self):
        self.assert_recusa(lambda: self.cliente.delete(
            f'{URL_TRANSACOES}bulk-delete/?transfer_id={self.transferencia}',
        ))

    def test_perna_de_outro_usuario_em_conta_excluida_nao_bloqueia_a_transferencia(self):
        # Transferência de A entre contas ativas; B tem, gravada à força, uma
        # perna com o mesmo transfer_id numa conta excluída de B
        transferencia = uuid.uuid4()
        saida = self.lancar(self.a.conta, 'TRANSFER_OUT', '30.00', transfer_id=transferencia)
        self.lancar(self.a.poupanca, 'TRANSFER_IN', '30.00', transfer_id=transferencia)
        excluida_b = Account.objects.create(user=self.b.usuario, name='Antiga B', initial_balance=Decimal('0.00'))
        self.lancar(excluida_b, 'TRANSFER_IN', '30.00', transfer_id=transferencia)
        Account.objects.filter(pk=excluida_b.pk).update(is_active=False)

        resp = self.cliente.patch(self.url(saida), {'description': 'Para a poupança'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        resp = self.cliente.delete(f'{URL_TRANSACOES}bulk-delete/?transfer_id={transferencia}')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(Transaction.objects.filter(transfer_id=transferencia, user=self.a.usuario).exists())


class CompraNoCartaoComContaExcluidaTests(ContaExcluidaTestCase):
    """O cartão cuja conta de pagamento foi excluída não aceita compra nova (SALDO-35)."""

    def setUp(self):
        super().setUp()
        self.cartao = CreditCard.objects.create(
            user=self.a.usuario, name='Cartão da antiga', limit=Decimal('1000.00'),
            closing_day=10, due_day=20, account=self.excluida,
        )

    def test_compra_pela_rota_recusada(self):
        antes = self.estado()

        resp = self.cliente.post(f'{URL_TRANSACOES}credit-card-expense/', {
            'credit_card': str(self.cartao.id), 'amount': '100.00', 'date': '2026-09-05',
            'description': 'Loja', 'category': str(self.a.despesa.id), 'installments': 2,
        }, format='json')

        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data, {'detail': CONTA_NAO_ENCONTRADA})
        self.assertEqual(self.estado(), antes)

    def test_compra_pelo_service_recusada(self):
        antes = self.estado()

        with self.assertRaises(ValidationError) as erro:
            TransactionService.create_credit_card_expense(
                user=self.a.usuario, card=self.cartao, amount=Decimal('100.00'),
                date=date(2026, 9, 5), description='Loja', category=self.a.despesa,
            )

        self.assertEqual(erro.exception.detail, {'detail': CONTA_NAO_ENCONTRADA})
        self.assertEqual(self.estado(), antes)


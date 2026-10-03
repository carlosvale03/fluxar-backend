"""
Operações atômicas (SALDO-10).

Uma falha forçada no meio de uma operação que move dinheiro desfaz a
operação inteira: nenhuma transação nova, nenhuma transação alterada e todos
os saldos como antes. Os services são testados direto e pela rota.
"""
from datetime import date
from decimal import Decimal
from unittest import mock

from accounts.models import Account, CreditCardInvoice
from accounts.services import CreditCardService
from goals.models import Goal, GoalDeposit
from transactions.models import Transaction
from transactions.serializers import TransactionSerializer
from transactions.services import TransactionService
from tests.saldo.base import SaldoTestCase, URL_TRANSACOES


class FalhaSimulada(Exception):
    pass


def falhar_na_chamada(alvo, atributo, numero):
    """
    Troca `alvo.atributo` por uma versão que funciona normalmente até a
    chamada `numero`, que levanta `FalhaSimulada`.
    """
    original = getattr(alvo, atributo)
    chamadas = []

    def substituto(*args, **kwargs):
        chamadas.append(1)
        if len(chamadas) == numero:
            raise FalhaSimulada('falha simulada')
        return original(*args, **kwargs)

    return mock.patch.object(alvo, atributo, side_effect=substituto)


class AtomicidadeTests(SaldoTestCase):

    def estado(self):
        """Saldos das contas, todas as transações campo a campo, faturas e metas."""
        return (
            sorted(Account.objects.values_list('id', 'balance')),
            sorted(Transaction.objects.values_list('id', 'status', 'account_id', 'amount', 'invoice_id', 'payment_date')),
            sorted(CreditCardInvoice.objects.values_list('id', 'status')),
            sorted(Goal.objects.values_list('id', 'current_amount')),
            GoalDeposit.objects.count(),
        )

    def compra_pendente(self, valor='100.00'):
        return self.lancar(
            self.a.conta, 'CREDIT_CARD', valor, status='PENDING',
            credit_card=self.a.cartao, invoice=self.a.fatura,
        )

    # Transferência: falha na criação da segunda perna

    def test_transferencia_que_falha_na_segunda_perna_nao_grava_nada(self):
        antes = self.estado()
        with falhar_na_chamada(Transaction.objects, 'create', 2):
            with self.assertRaises(FalhaSimulada):
                TransactionService.create_transfer(
                    user=self.a.usuario, account_from=self.a.conta, account_to=self.a.poupanca,
                    amount=Decimal('100.00'), date=date(2026, 9, 15),
                )
        self.assertEqual(self.estado(), antes)

    def test_transferencia_pela_rota_que_falha_na_segunda_perna_nao_grava_nada(self):
        antes = self.estado()
        with falhar_na_chamada(Transaction.objects, 'create', 2):
            with self.assertRaises(FalhaSimulada):
                self.cliente.post(f'{URL_TRANSACOES}transfer/', {
                    'account_from': str(self.a.conta.id), 'account_to': str(self.a.poupanca.id),
                    'amount': '100.00', 'date': '2026-09-15',
                }, format='json')
        self.assertEqual(self.estado(), antes)

    # Compra parcelada no cartão: falha na segunda parcela

    def test_compra_parcelada_que_falha_na_segunda_parcela_nao_grava_nada(self):
        antes = self.estado()
        with falhar_na_chamada(Transaction.objects, 'create', 2):
            with self.assertRaises(FalhaSimulada):
                TransactionService.create_credit_card_expense(
                    user=self.a.usuario, card=self.a.cartao, amount=Decimal('300.00'),
                    date=date(2026, 9, 5), description='Loja', category=self.a.despesa,
                    installments=3,
                )
        self.assertEqual(self.estado(), antes)

    # Pagamento de fatura: falha ao gravar a fatura, depois de pagar as compras

    def test_pagamento_que_falha_no_meio_nao_grava_nada(self):
        self.compra_pendente()
        antes = self.estado()
        with mock.patch.object(CreditCardInvoice, 'save', side_effect=FalhaSimulada('falha simulada')):
            with self.assertRaises(FalhaSimulada):
                CreditCardService.pay_invoice(
                    self.a.usuario, CreditCardInvoice.objects.get(pk=self.a.fatura.pk),
                    Account.objects.get(pk=self.a.conta.pk), Decimal('100.00'), date(2026, 9, 20),
                )
        self.assertEqual(self.estado(), antes)

    def test_pagamento_pela_rota_que_falha_no_meio_nao_grava_nada(self):
        self.compra_pendente()
        antes = self.estado()
        self.cliente.raise_request_exception = False
        with mock.patch.object(CreditCardInvoice, 'save', side_effect=FalhaSimulada('falha simulada')):
            resp = self.cliente.post(f'/api/invoices/{self.a.fatura.id}/pay/', {
                'account_id': str(self.a.conta.id), 'amount': '100.00', 'date': '2026-09-20',
            }, format='json')
        # A falha inesperada sobe como 500 (FATURA-28); nada do que veio antes dela fica gravado
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(self.estado(), antes)

    # Estorno de fatura: falha ao reabrir a fatura, depois de mexer nas compras

    def test_estorno_que_falha_no_meio_nao_grava_nada(self):
        self.compra_pendente()
        CreditCardService.pay_invoice(
            self.a.usuario, CreditCardInvoice.objects.get(pk=self.a.fatura.pk),
            Account.objects.get(pk=self.a.conta.pk), Decimal('100.00'), date(2026, 9, 20),
        )
        antes = self.estado()
        self.cliente.raise_request_exception = False
        with mock.patch.object(CreditCardInvoice, 'save', side_effect=FalhaSimulada('falha simulada')):
            resp = self.cliente.post(f'/api/invoices/{self.a.fatura.id}/unpay/')
        # A falha inesperada sobe como 500 (FATURA-28)
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(self.estado(), antes)

    # Aporte em meta: falha ao registrar o histórico, depois da transferência

    def test_aporte_que_falha_no_historico_nao_grava_nada(self):
        antes = self.estado()
        with mock.patch.object(GoalDeposit.objects, 'create', side_effect=FalhaSimulada('falha simulada')):
            resp = self.cliente.post(f'/api/goals/{self.a.meta.id}/deposit/', {
                'account_id': str(self.a.conta.id), 'amount': '100.00', 'date': '2026-09-15',
            }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.estado(), antes)

    # Requisição sem service próprio: a edição falha depois de gravar

    def test_edicao_que_falha_depois_de_gravar_desfaz_a_requisicao(self):
        t = self.lancar(self.a.conta, 'EXPENSE', '100.00')
        antes = self.estado()
        with mock.patch.object(TransactionSerializer, 'to_representation', side_effect=FalhaSimulada('falha simulada')):
            with self.assertRaises(FalhaSimulada):
                self.cliente.patch(f'{URL_TRANSACOES}{t.id}/', {'amount': '400.00'}, format='json')
        self.assertEqual(self.estado(), antes)

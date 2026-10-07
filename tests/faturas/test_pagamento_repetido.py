"""
Pagamento repetido (FATURA-30, FATURA-32, FATURA-33, AD-007).

A fatura de setembro de 2026 do cartão de A tem uma compra pendente de
R$ 400,00. O pagamento sai da conta corrente de A (R$ 1.000,00).
"""
import uuid
from datetime import date
from decimal import Decimal

from accounts.faturas import obter_fatura
from accounts.models import Account, CreditCardInvoice, PagamentoDeFatura
from transactions.models import Transaction
from tests.faturas.base import FaturasTestCase

CHAVE_COM_OUTROS_DADOS = 'Este identificador de pagamento já foi usado com outros dados.'
FATURA_JA_PAGA = 'Fatura já está paga.'


class PagamentoRepetidoTests(FaturasTestCase):

    def setUp(self):
        super().setUp()
        self.cartao_ = self.cartao(10, 20)
        self.setembro = obter_fatura(self.cartao_, 9, 2026)
        self.compra_ = self.compra(self.cartao_, self.setembro, '400.00', purchase_date=date(2026, 9, 1))
        self.outra_conta = Account.objects.create(
            user=self.a.usuario, name='Outra', type='CHECKING', initial_balance=Decimal('500.00'),
        )
        self.chave = str(uuid.uuid4())

    def corpo(self, **extra):
        dados = {
            'account_id': str(self.a.conta.id), 'amount': '400.00', 'date': '2026-09-15',
            'idempotency_key': self.chave,
        }
        dados.update(extra)
        return dados

    def pagar(self, fatura=None, **extra):
        fatura = fatura or self.setembro
        return self.client.post(f'/api/invoices/{fatura.id}/pay/', self.corpo(**extra), format='json')

    def saldo(self, conta=None):
        return Account.objects.get(pk=(conta or self.a.conta).pk).balance

    def test_dez_pedidos_com_a_mesma_chave_recebem_a_mesma_resposta_e_pagam_uma_vez(self):
        respostas = [self.pagar() for _ in range(10)]

        self.assertEqual({r.status_code for r in respostas}, {200})
        self.assertTrue(all(r.data == respostas[0].data for r in respostas))
        pagamento = PagamentoDeFatura.objects.get()
        self.assertEqual(respostas[0].data, {
            'status': 'Pagamento processado com sucesso.',
            'payment': {
                'id': str(pagamento.id), 'invoice_id': str(self.setembro.id), 'amount': '400.00',
                'account_id': str(self.a.conta.id), 'date': '2026-09-15', 'idempotency_key': self.chave,
            },
        })
        # Um único débito
        self.assertEqual(self.saldo(), Decimal('600.00'))
        self.assertEqual(
            Transaction.objects.filter(account=self.a.conta, status='COMPLETED').count(), 1,
        )

    def assert_recusa_sem_pagar(self, resp, pagamentos=1, saldo=Decimal('600.00')):
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {'detail': CHAVE_COM_OUTROS_DADOS, 'code': 'invalid'})
        self.assertEqual(PagamentoDeFatura.objects.count(), pagamentos)
        self.assertEqual(self.saldo(), saldo)
        self.assertEqual(self.saldo(self.outra_conta), Decimal('500.00'))

    def test_mesma_chave_com_outro_valor_conta_ou_data_e_recusada(self):
        self.assertEqual(self.pagar().status_code, 200)

        for extra in ({'amount': '300.00'}, {'account_id': str(self.outra_conta.id)}, {'date': '2026-09-16'}):
            with self.subTest(extra=extra):
                self.assert_recusa_sem_pagar(self.pagar(**extra))

    def test_mesma_chave_com_outra_fatura_e_recusada(self):
        outubro = obter_fatura(self.cartao_, 10, 2026)
        compra_de_outubro = self.compra(self.cartao_, outubro, '400.00', purchase_date=date(2026, 9, 12))
        self.assertEqual(self.pagar().status_code, 200)

        self.assert_recusa_sem_pagar(self.pagar(outubro))

        self.assertEqual(CreditCardInvoice.objects.get(pk=outubro.pk).status, 'OPEN')
        self.assertEqual(Transaction.objects.get(pk=compra_de_outubro.pk).status, 'PENDING')

    def test_chave_nova_ou_sem_chave_em_fatura_paga_e_recusada(self):
        self.assertEqual(self.pagar().status_code, 200)
        # Uma compra nova na fatura paga: um segundo pagamento a debitaria
        self.compra(self.cartao_, self.setembro, '100.00', purchase_date=date(2026, 9, 2))

        for extra in ({'idempotency_key': str(uuid.uuid4())}, {'idempotency_key': None}):
            with self.subTest(extra=extra):
                resp = self.pagar(amount='100.00', **extra)
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(resp.data, {'detail': FATURA_JA_PAGA, 'code': 'invalid'})
                self.assertEqual(PagamentoDeFatura.objects.count(), 1)
                self.assertEqual(self.saldo(), Decimal('600.00'))

    def test_pedido_sem_o_campo_da_chave_numa_fatura_paga_e_recusado(self):
        self.assertEqual(self.pagar().status_code, 200)
        corpo = self.corpo()
        del corpo['idempotency_key']

        resp = self.client.post(f'/api/invoices/{self.setembro.id}/pay/', corpo, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {'detail': FATURA_JA_PAGA, 'code': 'invalid'})
        self.assertEqual(self.saldo(), Decimal('600.00'))

    def test_repetir_a_chave_depois_do_estorno_devolve_a_resposta_original_sem_pagar(self):
        original = self.pagar()
        estorno = self.client.post(f'/api/invoices/{self.setembro.id}/unpay/', format='json')
        self.assertEqual(estorno.status_code, 200, estorno.data)
        self.assertEqual(self.saldo(), Decimal('1000.00'))

        repetido = self.pagar()

        self.assertEqual(repetido.status_code, 200)
        self.assertEqual(repetido.data, original.data)
        self.assertEqual(PagamentoDeFatura.objects.count(), 1)
        self.assertEqual(self.saldo(), Decimal('1000.00'))
        self.assertEqual(CreditCardInvoice.objects.get(pk=self.setembro.pk).status, 'OPEN')
        self.assertEqual(Transaction.objects.get(pk=self.compra_.pk).status, 'PENDING')

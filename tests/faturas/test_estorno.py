"""
Estorno do pagamento (FATURA-28, FATURA-34 a FATURA-38).

O cartão de A fecha no dia 10 e vence no dia 20. A fatura de setembro de
2026 tem compras de R$ 400,00 e R$ 600,00, e a de outubro, uma de R$ 200,00.
O pagamento sai da conta corrente de A (R$ 1.000,00).
"""
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from accounts import faturas
from accounts.faturas import obter_fatura
from accounts.models import Account, CreditCardInvoice, ItemDePagamento, PagamentoDeFatura
from transactions.models import Transaction
from tests.faturas.base import FaturasTestCase

ESTORNE_A_SEGUINTE = 'Estorne primeiro o pagamento da fatura seguinte.'


class FalhaSimulada(Exception):
    pass


def hoje_em(ano, mes, dia):
    """Simula `timezone.now()` às 15h UTC (12h em Brasília) do dia dado."""
    return mock.patch(
        'django.utils.timezone.now',
        return_value=datetime(ano, mes, dia, 15, 0, tzinfo=dt_timezone.utc),
    )


class EstornoTestCase(FaturasTestCase):

    def setUp(self):
        super().setUp()
        self.cartao_ = self.cartao(10, 20)
        self.setembro = obter_fatura(self.cartao_, 9, 2026)
        self.outubro = obter_fatura(self.cartao_, 10, 2026)
        self.c400 = self.compra(
            self.cartao_, self.setembro, '400.00', description='Mercado', purchase_date=date(2026, 9, 1),
        )
        self.c600 = self.compra(
            self.cartao_, self.setembro, '600.00', description='Loja', purchase_date=date(2026, 9, 2),
        )
        self.c200 = self.compra(self.cartao_, self.outubro, '200.00', purchase_date=date(2026, 9, 12))

    def pagar(self, fatura, valor):
        resp = self.client.post(f'/api/invoices/{fatura.id}/pay/', {
            'account_id': str(self.a.conta.id), 'amount': valor, 'date': '2026-09-15',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def estornar(self, fatura=None):
        return self.client.post(f'/api/invoices/{(fatura or self.setembro).id}/unpay/', format='json')

    def estado(self, compra):
        t = Transaction.objects.get(pk=compra.pk)
        return (t.status, t.amount, t.description, t.invoice_id, t.date, t.account_id, t.payment_date)

    def pendente_em_setembro(self, valor, descricao):
        return ('PENDING', Decimal(valor), descricao, self.setembro.id, date(2026, 9, 20), self.a.conta.id, None)

    def saldo(self):
        return Account.objects.get(pk=self.a.conta.pk).balance

    def restante(self):
        return Transaction.objects.get(description='Loja (Restante)')

    def tudo(self):
        return (
            sorted(Transaction.objects.values_list(
                'id', 'status', 'account_id', 'amount', 'invoice_id', 'payment_date', 'description', 'date',
            )),
            sorted(CreditCardInvoice.objects.values_list('id', 'status', 'total_amount')),
            sorted(Account.objects.values_list('id', 'balance')),
            sorted(PagamentoDeFatura.objects.values_list('id', 'estornado_em')),
        )


class EstornoDoPagamentoParcialTests(EstornoTestCase):

    def test_pagar_700_e_estornar_volta_tudo_como_antes(self):
        """Independent Test da spec."""
        self.pagar(self.setembro, '700.00')
        restante = self.restante()

        resp = self.estornar()

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.estado(self.c400), self.pendente_em_setembro('400.00', 'Mercado'))
        self.assertEqual(self.estado(self.c600), self.pendente_em_setembro('600.00', 'Loja'))
        self.assertFalse(Transaction.objects.filter(pk=restante.pk).exists())
        self.assertEqual(self.total(self.setembro), Decimal('1000.00'))
        self.assertEqual(self.total(self.outubro), Decimal('200.00'))
        self.assertEqual(CreditCardInvoice.objects.get(pk=self.setembro.pk).status, 'OPEN')
        self.assertEqual(self.saldo(), Decimal('1000.00'))
        # O registro fica, marcado como estornado
        self.assertIsNotNone(PagamentoDeFatura.objects.get(fatura=self.setembro).estornado_em)

    def test_restante_editado_volta_somado_a_parte_paga(self):
        self.pagar(self.setembro, '700.00')
        restante = self.restante()
        restante.amount = Decimal('250.00')
        restante.save()

        self.estornar()

        self.assertEqual(self.estado(self.c600), self.pendente_em_setembro('550.00', 'Loja'))
        self.assertFalse(Transaction.objects.filter(pk=restante.pk).exists())
        self.assertEqual(self.total(self.setembro), Decimal('950.00'))
        self.assertEqual(self.total(self.outubro), Decimal('200.00'))

    def test_restante_excluido_volta_so_a_parte_paga(self):
        self.pagar(self.setembro, '700.00')
        Transaction.objects.filter(pk=self.restante().pk).delete()

        resp = self.estornar()

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.estado(self.c600), self.pendente_em_setembro('300.00', 'Loja'))
        self.assertEqual(self.total(self.setembro), Decimal('700.00'))


class CompraMovidaTests(EstornoTestCase):

    def test_compras_movidas_voltam_para_a_fatura_original(self):
        self.pagar(self.setembro, '400.00')
        self.assertEqual(Transaction.objects.get(pk=self.c600.pk).invoice_id, self.outubro.id)
        self.assertEqual(self.total(self.outubro), Decimal('800.00'))

        resp = self.estornar()

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.estado(self.c600), self.pendente_em_setembro('600.00', 'Loja'))
        self.assertEqual(self.estado(self.c400), self.pendente_em_setembro('400.00', 'Mercado'))
        self.assertEqual(self.total(self.setembro), Decimal('1000.00'))
        self.assertEqual(self.total(self.outubro), Decimal('200.00'))

    def test_compra_movida_que_saiu_da_fatura_seguinte_fica_onde_esta(self):
        self.pagar(self.setembro, '400.00')
        novembro = obter_fatura(self.cartao_, 11, 2026)
        faturas.colocar(Transaction.objects.get(pk=self.c600.pk), novembro)

        self.estornar()

        self.assertEqual(Transaction.objects.get(pk=self.c600.pk).invoice_id, novembro.id)
        self.assertEqual(self.total(self.setembro), Decimal('400.00'))


class RecusaDoEstornoTests(EstornoTestCase):

    def test_fatura_seguinte_paga_recebe_400_e_nada_muda(self):
        self.pagar(self.setembro, '700.00')
        self.pagar(self.outubro, '500.00')
        antes = self.tudo()

        resp = self.estornar()

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {'detail': ESTORNE_A_SEGUINTE})
        self.assertEqual(self.tudo(), antes)

    def test_falha_no_meio_do_estorno_deixa_tudo_como_estava(self):
        """FATURA-28: a falha ao trazer de volta a compra movida, depois de reabrir as pagas, desfaz tudo."""
        self.pagar(self.setembro, '400.00')
        antes = self.tudo()

        self.client.raise_request_exception = False
        with mock.patch.object(faturas, 'colocar', side_effect=FalhaSimulada('falha simulada')):
            resp = self.estornar()

        self.assertEqual(resp.status_code, 500)
        self.assertEqual(self.tudo(), antes)


class StatusDepoisDoEstornoTests(EstornoTestCase):

    def status_exibido(self):
        resp = self.client.get(f'/api/invoices/{self.setembro.id}/')
        self.assertEqual(resp.status_code, 200)
        return resp.data['status']

    def test_volta_aberta_antes_do_fechamento_e_fechada_a_partir_dele(self):
        self.pagar(self.setembro, '1000.00')
        self.estornar()

        self.assertEqual(CreditCardInvoice.objects.get(pk=self.setembro.pk).status, 'OPEN')
        with hoje_em(2026, 9, 9):
            self.assertEqual(self.status_exibido(), 'OPEN')
        with hoje_em(2026, 9, 10):
            self.assertEqual(self.status_exibido(), 'CLOSED')
        self.assertEqual(self.total(self.setembro), Decimal('1000.00'))


class EstornoSemRegistroTests(EstornoTestCase):

    def test_pagamento_feito_antes_da_feature_ainda_pode_ser_estornado(self):
        # Como o pagamento antigo deixava: compras pagas e fatura paga, sem registro
        Transaction.objects.filter(invoice=self.setembro).update(
            status='COMPLETED', payment_date=date(2026, 9, 15),
        )
        CreditCardInvoice.objects.filter(pk=self.setembro.pk).update(status='PAID')
        Account.objects.filter(pk=self.a.conta.pk).update(balance=Decimal('0.00'))

        resp = self.estornar()

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.estado(self.c400), self.pendente_em_setembro('400.00', 'Mercado'))
        self.assertEqual(self.estado(self.c600), self.pendente_em_setembro('600.00', 'Loja'))
        self.assertEqual(CreditCardInvoice.objects.get(pk=self.setembro.pk).status, 'OPEN')
        self.assertEqual(self.saldo(), Decimal('1000.00'))
        self.assertFalse(ItemDePagamento.objects.exists())

"""
Pagamento total e parcial (FATURA-21 a FATURA-28).

O cartão de A fecha no dia 10 e vence no dia 20: a fatura de setembro de
2026 fecha em 10/09 e vence em 20/09. O pagamento sai da conta corrente de
A, com saldo inicial de R$ 1.000,00.
"""
from datetime import date
from decimal import Decimal
from unittest import mock

from accounts import faturas
from accounts.faturas import obter_fatura
from accounts.models import Account, CreditCardInvoice, ItemDePagamento, PagamentoDeFatura
from transactions.models import Transaction
from tests.faturas.base import FaturasTestCase

VALOR_MAIOR = 'O valor pago não pode ser maior que o total da fatura.'


class FalhaSimulada(Exception):
    pass


class PagamentoTestCase(FaturasTestCase):

    def setUp(self):
        super().setUp()
        self.cartao_ = self.cartao(10, 20)
        self.setembro = obter_fatura(self.cartao_, 9, 2026)

    def pagar(self, fatura, valor, **extra):
        return self.client.post(f'/api/invoices/{fatura.id}/pay/', {
            'account_id': str(self.a.conta.id), 'amount': valor, 'date': '2026-09-15', **extra,
        }, format='json')

    def ler(self, compra):
        return Transaction.objects.get(pk=compra.pk)

    def saldo(self):
        return Account.objects.get(pk=self.a.conta.pk).balance

    def status(self, fatura):
        return CreditCardInvoice.objects.get(pk=fatura.pk).status


class PagamentoParcialTests(PagamentoTestCase):
    """Independent Test: R$ 700,00 de uma fatura de R$ 1.000,00."""

    def setUp(self):
        super().setUp()
        self.outubro = obter_fatura(self.cartao_, 10, 2026)
        self.c400 = self.compra(
            self.cartao_, self.setembro, '400.00', description='Mercado', purchase_date=date(2026, 9, 1),
        )
        self.c600 = self.compra(
            self.cartao_, self.setembro, '600.00', description='Loja', purchase_date=date(2026, 9, 2),
        )
        self.compra(self.cartao_, self.outubro, '200.00', purchase_date=date(2026, 9, 12))

    def test_paga_700_de_1000_e_leva_300_para_a_fatura_seguinte(self):
        self.assertEqual(self.total(self.outubro), Decimal('200.00'))

        resp = self.pagar(self.setembro, '700.00')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.status(self.setembro), 'PAID')
        self.assertEqual(self.total(self.setembro), Decimal('700.00'))
        self.assertEqual(self.total(self.outubro), Decimal('500.00'))

        c400, c600 = self.ler(self.c400), self.ler(self.c600)
        self.assertEqual(
            (c400.status, c400.amount, c400.account_id, c400.payment_date, c400.invoice_id),
            ('COMPLETED', Decimal('400.00'), self.a.conta.id, date(2026, 9, 15), self.setembro.id),
        )
        # A compra em que o valor acabou fica com a parte paga (FATURA-23)
        self.assertEqual(
            (c600.status, c600.amount, c600.description, c600.payment_date, c600.invoice_id),
            ('COMPLETED', Decimal('300.00'), 'Loja (Parcial)', date(2026, 9, 15), self.setembro.id),
        )
        restante = Transaction.objects.get(description='Loja (Restante)')
        self.assertEqual(
            (restante.status, restante.amount, restante.invoice_id, restante.date,
             restante.purchase_date, restante.parent_transaction_id, restante.account_id,
             restante.credit_card_id),
            ('PENDING', Decimal('300.00'), self.outubro.id, date(2026, 10, 20),
             date(2026, 9, 2), self.c600.id, self.cartao_.account_id, self.cartao_.id),
        )
        # O débito na conta é exatamente o valor pago
        self.assertEqual(self.saldo(), Decimal('300.00'))

    def test_registra_o_pagamento_com_os_itens(self):
        self.pagar(self.setembro, '700.00')

        pagamento = PagamentoDeFatura.objects.get(fatura=self.setembro)
        self.assertEqual(
            (pagamento.user_id, pagamento.conta_id, pagamento.valor, pagamento.data,
             pagamento.fatura_seguinte_id, pagamento.estornado_em),
            (self.a.usuario.id, self.a.conta.id, Decimal('700.00'), date(2026, 9, 15),
             self.outubro.id, None),
        )
        restante = Transaction.objects.get(description='Loja (Restante)')
        itens = sorted(
            pagamento.itens.values_list('tipo', 'compra_id', 'restante_id', 'valor_original', 'descricao_original'),
        )
        self.assertEqual(itens, [
            (ItemDePagamento.DIVIDIDA, self.c600.id, restante.id, Decimal('600.00'), 'Loja'),
            (ItemDePagamento.PAGA, self.c400.id, None, None, ''),
        ])


class PagamentoTotalTests(PagamentoTestCase):

    def test_paga_todas_as_compras_e_a_fatura(self):
        compras = [
            self.compra(self.cartao_, self.setembro, valor, purchase_date=date(2026, 9, 1))
            for valor in ('250.00', '750.00')
        ]

        resp = self.pagar(self.setembro, '1000.00')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.status(self.setembro), 'PAID')
        self.assertEqual(self.total(self.setembro), Decimal('1000.00'))
        for compra in compras:
            lida = self.ler(compra)
            self.assertEqual(
                (lida.status, lida.account_id, lida.payment_date, lida.invoice_id, lida.amount),
                ('COMPLETED', self.a.conta.id, date(2026, 9, 15), self.setembro.id, compra.amount),
            )
        # Nada sobrou: nenhuma fatura seguinte criada
        self.assertFalse(CreditCardInvoice.objects.filter(card=self.cartao_, month=10).exists())
        self.assertIsNone(PagamentoDeFatura.objects.get(fatura=self.setembro).fatura_seguinte)
        self.assertEqual(self.saldo(), Decimal('0.00'))


class OrdemDoPagamentoTests(PagamentoTestCase):

    def test_paga_em_ordem_de_data_da_compra_e_depois_de_valor(self):
        """FATURA-22: 02/09 R$ 50,00 antes de 03/09 R$ 30,00; no mesmo dia, o menor valor antes."""
        tarde = self.compra(self.cartao_, self.setembro, '30.00', purchase_date=date(2026, 9, 3))
        cedo_maior = self.compra(self.cartao_, self.setembro, '70.00', purchase_date=date(2026, 9, 2))
        cedo_menor = self.compra(self.cartao_, self.setembro, '50.00', purchase_date=date(2026, 9, 2))

        self.pagar(self.setembro, '120.00')

        self.assertEqual(self.ler(cedo_menor).status, 'COMPLETED')
        self.assertEqual(self.ler(cedo_maior).status, 'COMPLETED')
        self.assertEqual(self.ler(tarde).status, 'PENDING')
        self.assertNotEqual(self.ler(tarde).invoice_id, self.setembro.id)

    def test_compra_antiga_sem_data_da_compra_usa_a_data_gravada(self):
        antiga = self.compra(self.cartao_, self.setembro, '40.00', date=date(2026, 8, 30))
        nova = self.compra(self.cartao_, self.setembro, '10.00', purchase_date=date(2026, 9, 1))

        self.pagar(self.setembro, '40.00')

        self.assertEqual(self.ler(antiga).status, 'COMPLETED')
        self.assertEqual(self.ler(nova).status, 'PENDING')


class RolagemTests(PagamentoTestCase):

    def test_compras_nao_pagas_vao_para_a_primeira_fatura_seguinte_nao_paga_criada_se_faltar(self):
        paga = self.compra(self.cartao_, self.setembro, '100.00', purchase_date=date(2026, 9, 1))
        movida = self.compra(self.cartao_, self.setembro, '200.00', purchase_date=date(2026, 9, 2))
        # Outubro já está paga (pagamento antecipado); novembro ainda não existe
        outubro = obter_fatura(self.cartao_, 10, 2026)
        CreditCardInvoice.objects.filter(pk=outubro.pk).update(status='PAID')
        self.assertFalse(CreditCardInvoice.objects.filter(card=self.cartao_, month=11).exists())

        resp = self.pagar(self.setembro, '100.00')

        self.assertEqual(resp.status_code, 200, resp.data)
        novembro = self.fatura(self.cartao_, 11, 2026)
        # Criada com as datas de FATURA-01 a FATURA-04
        self.assertEqual((novembro.closing_date, novembro.due_date), (date(2026, 11, 10), date(2026, 11, 20)))
        lida = self.ler(movida)
        self.assertEqual(
            (lida.status, lida.invoice_id, lida.date, lida.purchase_date, lida.amount, lida.payment_date),
            ('PENDING', novembro.id, date(2026, 11, 20), date(2026, 9, 2), Decimal('200.00'), None),
        )
        self.assertEqual(self.ler(paga).status, 'COMPLETED')
        self.assertEqual(self.status(self.setembro), 'PAID')
        self.assertEqual(self.total(self.setembro), Decimal('100.00'))
        self.assertEqual(self.total(novembro), Decimal('200.00'))
        pagamento = PagamentoDeFatura.objects.get(fatura=self.setembro)
        self.assertEqual(pagamento.fatura_seguinte_id, novembro.id)
        self.assertEqual(
            list(pagamento.itens.filter(tipo=ItemDePagamento.MOVIDA).values_list('compra_id', flat=True)),
            [movida.id],
        )


class RecusaEFalhaTests(PagamentoTestCase):

    def setUp(self):
        super().setUp()
        self.c1 = self.compra(self.cartao_, self.setembro, '400.00', purchase_date=date(2026, 9, 1))
        self.c2 = self.compra(self.cartao_, self.setembro, '600.00', purchase_date=date(2026, 9, 2))
        self.c3 = self.compra(self.cartao_, self.setembro, '50.00', purchase_date=date(2026, 9, 3))

    def estado(self):
        return (
            sorted(Transaction.objects.values_list(
                'id', 'status', 'account_id', 'amount', 'invoice_id', 'payment_date', 'description', 'date',
            )),
            sorted(CreditCardInvoice.objects.values_list('id', 'status', 'total_amount')),
            sorted(Account.objects.values_list('id', 'balance')),
            PagamentoDeFatura.objects.count(),
            ItemDePagamento.objects.count(),
        )

    def test_valor_maior_que_o_total_recebe_400_e_nada_muda(self):
        antes = self.estado()

        resp = self.pagar(self.setembro, '1050.01')

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {'detail': VALOR_MAIOR})
        self.assertEqual(self.estado(), antes)

    def test_falha_no_meio_do_pagamento_deixa_tudo_como_estava(self):
        """FATURA-28: a falha ao mover a última compra, depois de pagar e dividir, desfaz tudo."""
        antes = self.estado()
        colocar = faturas.colocar
        chamadas = []

        def falha_na_segunda(compra, fatura):
            chamadas.append(compra)
            if len(chamadas) == 2:
                raise FalhaSimulada('falha simulada')
            return colocar(compra, fatura)

        self.client.raise_request_exception = False
        with mock.patch.object(faturas, 'colocar', side_effect=falha_na_segunda):
            resp = self.pagar(self.setembro, '700.00')

        # Erro inesperado vira 500, sem o texto da exceção
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(len(chamadas), 2)
        self.assertEqual(self.estado(), antes)
        self.assertFalse(CreditCardInvoice.objects.filter(card=self.cartao_, month=10).exists())

"""
Data de cada transação nos relatórios e marca do ajuste de saldo (T1,
REL-01, REL-02, REL-03, REL-11, AD-046).
"""
import importlib
from datetime import date
from decimal import Decimal

from django.apps import apps

from accounts.faturas import pagar
from goals import trocos
from goals.models import Goal, Troco
from transactions.models import Transaction
from transactions.services import TransactionService

from .base import RelatoriosTestCase

# O nome do módulo começa com dígito, por isso o import_module
migracao = importlib.import_module('transactions.migrations.0011_relatorios')

TV_EM_12X = [
    date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30),
    date(2026, 5, 31), date(2026, 6, 30), date(2026, 7, 31), date(2026, 8, 31),
    date(2026, 9, 30), date(2026, 10, 31), date(2026, 11, 30), date(2026, 12, 31),
]


class DataDaCompraNoCartaoTests(RelatoriosTestCase):

    def setUp(self):
        super().setUp()
        # Fecha no dia 5 e vence no dia 15
        self.cartao_ = self.cartao(5, 15)

    def test_compra_conta_na_data_da_compra_mesmo_com_vencimento_no_mes_seguinte(self):
        # 10/03 é depois do fechamento de 05/03: fatura que vence em 15/04
        [compra] = self.comprar(self.cartao_, '80.00', date(2026, 3, 10))

        compra = self.ler(compra)
        self.assertEqual(compra.date, date(2026, 4, 15))
        self.assertEqual(compra.report_date, date(2026, 3, 10))

    def test_parcela_n_conta_n_menos_1_meses_depois_no_ultimo_dia_quando_falta(self):
        parcelas = self.comprar(self.cartao_, '1200.00', date(2026, 1, 31), parcelas=12)

        lidas = Transaction.objects.filter(pk__in=[p.pk for p in parcelas]).order_by('installment_number')
        self.assertEqual([p.report_date for p in lidas], TV_EM_12X)
        self.assertEqual({p.amount for p in lidas}, {Decimal('100.00')})

    def test_editar_a_data_da_compra_recalcula_todas_as_parcelas(self):
        parcelas = self.comprar(self.cartao_, '300.00', date(2026, 1, 31), parcelas=3)

        TransactionService.editar_compra(self.ler(parcelas[1]), {'purchase_date': date(2026, 2, 10)})

        lidas = Transaction.objects.filter(pk__in=[p.pk for p in parcelas]).order_by('installment_number')
        self.assertEqual(
            [p.report_date for p in lidas], [date(2026, 2, 10), date(2026, 3, 10), date(2026, 4, 10)],
        )

    def test_restante_do_pagamento_parcial_mantem_a_data_da_parcela(self):
        parcelas = self.comprar(self.cartao_, '300.00', date(2026, 1, 31), parcelas=3)
        segunda = self.ler(parcelas[1])

        pagar(self.a.usuario, segunda.invoice, self.a.conta, Decimal('40.00'), date(2026, 3, 15))

        restante = Transaction.objects.get(description__endswith='(Restante)')
        self.assertEqual(restante.amount, Decimal('60.00'))
        self.assertNotEqual(restante.invoice_id, segunda.invoice_id)
        self.assertEqual(restante.report_date, date(2026, 2, 28))
        self.assertEqual(self.ler(segunda).report_date, date(2026, 2, 28))

    def test_compra_antiga_sem_data_da_compra_fica_com_a_date(self):
        antiga = self.lancar(
            'CREDIT_CARD', '50.00', date(2026, 4, 15), status='PENDING', credit_card=self.cartao_,
            is_installment=True, installment_number=3, installment_total=4,
        )

        self.assertEqual(self.ler(antiga).report_date, date(2026, 4, 15))


class DataDosDemaisTiposTests(RelatoriosTestCase):

    def test_despesa_receita_e_transferencia_ficam_com_a_date(self):
        despesa = self.lancar('EXPENSE', '10.00', date(2026, 3, 31), status='PENDING')
        receita = self.lancar('INCOME', '10.00', date(2026, 2, 28))
        cofrinho = self.conta('PIGGY_BANK')
        self.transferir(self.a.conta, cofrinho, '5.00', date(2026, 1, 31))

        self.assertEqual(self.ler(despesa).report_date, date(2026, 3, 31))
        self.assertEqual(self.ler(receita).report_date, date(2026, 2, 28))
        self.assertEqual(
            sorted(Transaction.objects.filter(transfer_id__isnull=False).values_list('report_date', flat=True)),
            [date(2026, 1, 31), date(2026, 1, 31)],
        )

    def test_editar_a_date_recalcula(self):
        despesa = self.lancar('EXPENSE', '10.00', date(2026, 3, 31))
        despesa.date = date(2026, 4, 2)
        despesa.save()

        self.assertEqual(self.ler(despesa).report_date, date(2026, 4, 2))


class AjusteDeSaldoTests(RelatoriosTestCase):

    def ajustar(self, novo_saldo):
        resp = self.client.post(
            f'/api/accounts/{self.a.conta.pk}/adjust-balance/', {'new_balance': novo_saldo}, format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        return Transaction.objects.filter(account=self.a.conta).latest('created_at')

    def test_ajuste_para_cima_e_para_baixo_grava_a_marca(self):
        para_cima = self.ajustar('100.00')
        para_baixo = self.ajustar('99.80')

        self.assertEqual((para_cima.type, para_cima.is_balance_adjustment), ('INCOME', True))
        self.assertEqual(
            (para_baixo.type, para_baixo.amount, para_baixo.is_balance_adjustment),
            ('EXPENSE', Decimal('0.20'), True),
        )

    def test_lancamento_comum_nao_tem_a_marca(self):
        self.assertFalse(self.ler(self.lancar('EXPENSE', '10.00', date(2026, 3, 1))).is_balance_adjustment)


class TrocosEAjusteDeSaldoTests(RelatoriosTestCase):

    def setUp(self):
        super().setUp()
        cofrinho = self.conta('PIGGY_BANK')
        meta = Goal.objects.create(
            user=self.a.usuario, name='Trocos', target_amount=Decimal('100.00'), account=cofrinho,
        )
        trocos.configurar(self.a.usuario, True, meta)

    def test_trocos_ignoram_o_ajuste_pelo_campo_e_nao_pela_descricao(self):
        marcado = self.lancar(
            'EXPENSE', '12.35', date(2026, 3, 1), description='Correção', is_balance_adjustment=True,
        )
        so_com_a_descricao = self.lancar('EXPENSE', '12.30', date(2026, 3, 1), description='Ajuste de saldo')

        self.assertEqual(
            list(Troco.objects.values_list('despesa_id', 'valor')),
            [(so_com_a_descricao.pk, Decimal('0.70'))],
        )
        self.assertFalse(Troco.objects.filter(despesa_id=marcado.pk).exists())


class MigracaoTests(RelatoriosTestCase):

    def test_preenche_a_data_no_relatorio_e_marca_os_ajustes_antigos(self):
        cartao = self.cartao(5, 15)
        parcelas = self.comprar(cartao, '200.00', date(2026, 1, 31), parcelas=2)
        antiga = self.lancar('CREDIT_CARD', '50.00', date(2026, 4, 15), status='PENDING', credit_card=cartao)
        despesa = self.lancar('EXPENSE', '10.00', date(2026, 3, 31))
        ajuste = self.lancar('INCOME', '5.00', date(2026, 3, 2), description='Ajuste de saldo')
        # Como estavam antes da migração: sem data no relatório certa e sem marca
        Transaction.objects.update(report_date=date(2000, 1, 1), is_balance_adjustment=False)

        migracao.preencher(apps, None)

        self.assertEqual(
            [self.ler(p).report_date for p in parcelas], [date(2026, 1, 31), date(2026, 2, 28)],
        )
        self.assertEqual(self.ler(antiga).report_date, date(2026, 4, 15))
        self.assertEqual(self.ler(despesa).report_date, date(2026, 3, 31))
        self.assertEqual(self.ler(ajuste).report_date, date(2026, 3, 2))
        self.assertEqual(
            list(Transaction.objects.filter(is_balance_adjustment=True).values_list('pk', flat=True)),
            [ajuste.pk],
        )

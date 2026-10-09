"""
Regras comuns dos relatórios em `reports/regras.py` (T2, REL-01 a REL-05,
REL-07, REL-08, REL-10, REL-13, REL-14, REL-16 a REL-18, REL-20).
"""
from datetime import date
from decimal import Decimal

from accounts.faturas import obter_fatura
from accounts.models import Account, CreditCardInvoice
from goals.models import Goal
from goals.services import GoalService
from reports import regras
from transactions.models import Transaction

from .base import RelatoriosTestCase, agora_em

MARCO = (date(2026, 3, 1), date(2026, 3, 31))


class DespesasEAPagarTests(RelatoriosTestCase):

    def test_efetivada_e_compra_no_cartao_com_fatura_aberta_entram_e_a_pendente_vai_para_a_pagar(self):
        self.lancar('EXPENSE', '100.00', date(2026, 3, 5))
        self.lancar('EXPENSE', '50.00', date(2026, 3, 12), status='PENDING')
        # 10/03 depois do fechamento de 05/03: fatura de 15/04, ainda aberta
        self.comprar(self.cartao(5, 15), '80.00', date(2026, 3, 10))

        despesas = regras.total(regras.despesas(self.a.usuario, *MARCO))
        a_pagar = regras.total(regras.a_pagar(self.a.usuario, *MARCO))

        self.assertEqual(despesas, Decimal('180.00'))
        self.assertIsInstance(despesas, Decimal)
        self.assertEqual(a_pagar, Decimal('50.00'))

    def test_transferencia_pagamento_de_fatura_e_ajuste_ficam_fora_das_despesas(self):
        self.lancar('EXPENSE', '30.00', date(2026, 3, 5))
        self.transferir(self.a.conta, self.conta('SAVINGS'), '200.00', date(2026, 3, 6))
        self.lancar('INVOICE_PAYMENT', '400.00', date(2026, 3, 15))
        self.lancar('EXPENSE', '0.20', date(2026, 3, 16), description='Ajuste de saldo', is_balance_adjustment=True)
        self.lancar('EXPENSE', '9.00', date(2026, 3, 17), status='PENDING', is_balance_adjustment=True)

        self.assertEqual(regras.total(regras.despesas(self.a.usuario, *MARCO)), Decimal('30.00'))
        self.assertEqual(regras.total(regras.a_pagar(self.a.usuario, *MARCO)), Decimal('0.00'))

    def test_parcela_conta_so_no_mes_dela(self):
        self.comprar(self.cartao(5, 15), '1200.00', date(2026, 1, 31), parcelas=12)

        fevereiro = regras.despesas(self.a.usuario, date(2026, 2, 1), date(2026, 2, 28))

        self.assertEqual(regras.total(fevereiro), Decimal('100.00'))
        self.assertEqual(list(fevereiro.values_list('report_date', flat=True)), [date(2026, 2, 28)])

    def test_pendente_de_mes_passado_continua_em_a_pagar_daquele_mes(self):
        self.lancar('EXPENSE', '70.00', date(2026, 2, 10), status='PENDING')

        fevereiro = (date(2026, 2, 1), date(2026, 2, 28))
        with agora_em(2026, 4, 10):
            self.assertEqual(regras.total(regras.a_pagar(self.a.usuario, *fevereiro)), Decimal('70.00'))
            self.assertEqual(regras.total(regras.despesas(self.a.usuario, *fevereiro)), Decimal('0.00'))

    def test_despesa_efetivada_de_conta_excluida_conta_no_periodo(self):
        antiga = self.conta('CHECKING', nome='Antiga')
        self.lancar('EXPENSE', '25.00', date(2026, 3, 3), conta=antiga)
        self.lancar('INCOME', '40.00', date(2026, 3, 3), conta=antiga)
        Account.objects.filter(pk=antiga.pk).update(is_active=False)

        self.assertEqual(regras.total(regras.despesas(self.a.usuario, *MARCO)), Decimal('25.00'))
        self.assertEqual(regras.total(regras.receitas(self.a.usuario, *MARCO)), Decimal('40.00'))


class ReceitasTests(RelatoriosTestCase):

    def test_so_as_efetivadas_sem_transferencia_e_sem_ajuste(self):
        self.lancar('INCOME', '5000.00', date(2026, 3, 5))
        self.lancar('INCOME', '300.00', date(2026, 3, 6), status='PENDING')
        self.transferir(self.conta('SAVINGS'), self.a.conta, '200.00', date(2026, 3, 7))
        self.lancar('INCOME', '250.25', date(2026, 3, 8), description='Ajuste de saldo', is_balance_adjustment=True)
        self.lancar('INCOME', '10.00', date(2026, 4, 1))

        receitas = regras.total(regras.receitas(self.a.usuario, *MARCO))

        self.assertEqual(receitas, Decimal('5000.00'))
        self.assertIsInstance(receitas, Decimal)


class CalendarioTests(RelatoriosTestCase):

    def test_seis_meses_a_partir_de_31_de_marco_vao_de_outubro_a_marco(self):
        self.assertEqual(regras.meses_do_calendario(date(2026, 3, 31), 6), [
            (2025, 10), (2025, 11), (2025, 12), (2026, 1), (2026, 2), (2026, 3),
        ])

    def test_limites_do_mes_com_o_ultimo_dia(self):
        self.assertEqual(regras.limites_do_mes(2028, 2), (date(2028, 2, 1), date(2028, 2, 29)))
        self.assertEqual(regras.limites_do_mes(2026, 4), (date(2026, 4, 1), date(2026, 4, 30)))

    def test_as_23h_de_brasilia_do_ultimo_dia_o_mes_ainda_e_o_de_brasilia(self):
        # 02h UTC de 01/05 = 23h de 30/04 em Brasília
        with agora_em(2026, 5, 1, hora=2):
            self.assertEqual(regras.mes_atual(), (2026, 4))

    def test_hora_e_dia_da_semana_em_brasilia(self):
        # 01h UTC de 11/03 = 22h de terça, 10/03, em Brasília
        with agora_em(2026, 3, 11, hora=1):
            despesa = self.lancar('EXPENSE', '10.00', date(2026, 3, 10))

        lida = Transaction.objects.filter(pk=despesa.pk).annotate(
            hora=regras.hora_em_brasilia(), dia=regras.dia_da_semana_em_brasilia(),
        ).get()
        self.assertEqual((lida.hora, lida.dia), (22, 3))


class PatrimonioTests(RelatoriosTestCase):

    def test_atual_soma_as_contas_e_tira_as_compras_nao_pagas(self):
        Account.objects.filter(pk=self.a.conta.pk).update(initial_balance=Decimal('3000.00'), balance=Decimal('3000.00'))
        self.conta('PIGGY_BANK', '800.00')
        self.conta('INVESTMENT', '2000.00')
        cartao = self.cartao(5, 15)
        self.comprar(cartao, '450.00', date(2026, 3, 10))
        # Conta excluída fica fora (SALDO-31)
        excluida = self.conta('CHECKING', '999.00', nome='Antiga')
        Account.objects.filter(pk=excluida.pk).update(is_active=False)

        partes = regras.patrimonio(self.a.usuario)

        self.assertEqual(partes, {
            'disponivel': Decimal('3000.00'), 'reservas': Decimal('800.00'),
            'investimentos': Decimal('2000.00'), 'faturas_em_aberto': Decimal('450.00'),
            'total': Decimal('5350.00'),
        })
        self.assertTrue(all(isinstance(valor, Decimal) for valor in partes.values()))

    def test_no_fim_de_um_mes_passado_conta_so_o_efetivado_ate_o_dia_e_as_compras_nao_pagas_nele(self):
        Account.objects.filter(pk=self.a.conta.pk).update(initial_balance=Decimal('1000.00'))
        investimento = self.conta('INVESTMENT')
        self.lancar('INCOME', '500.00', date(2026, 1, 15))
        self.lancar('EXPENSE', '100.00', date(2026, 1, 20), status='PENDING')
        self.lancar('EXPENSE', '200.00', date(2026, 2, 10))
        self.transferir(self.a.conta, investimento, '100.00', date(2026, 2, 20))
        # Compra de 20/01 paga em 15/02
        self.lancar(
            'CREDIT_CARD', '300.00', date(2026, 2, 15), purchase_date=date(2026, 1, 20),
            payment_date=date(2026, 2, 15),
        )
        # Compra de 10/02 ainda não paga
        self.lancar('CREDIT_CARD', '50.00', date(2026, 3, 15), status='PENDING', purchase_date=date(2026, 2, 10))

        janeiro = regras.patrimonio(self.a.usuario, em=date(2026, 1, 31))
        fevereiro = regras.patrimonio(self.a.usuario, em=date(2026, 2, 28))

        self.assertEqual(janeiro, {
            'disponivel': Decimal('1500.00'), 'reservas': Decimal('0.00'), 'investimentos': Decimal('0.00'),
            'faturas_em_aberto': Decimal('300.00'), 'total': Decimal('1200.00'),
        })
        self.assertEqual(fevereiro, {
            'disponivel': Decimal('900.00'), 'reservas': Decimal('0.00'), 'investimentos': Decimal('100.00'),
            'faturas_em_aberto': Decimal('50.00'), 'total': Decimal('950.00'),
        })


class DinheiroGuardadoTests(RelatoriosTestCase):

    def setUp(self):
        super().setUp()
        Account.objects.filter(pk=self.a.conta.pk).update(initial_balance=Decimal('10000.00'), balance=Decimal('10000.00'))
        self.a.conta.refresh_from_db()
        self.cofrinho = self.conta('PIGGY_BANK')
        self.investimento = self.conta('INVESTMENT')
        self.meta = Goal.objects.create(
            user=self.a.usuario, name='Viagem', target_amount=Decimal('5000.00'), account=self.cofrinho,
        )

    def guardado(self):
        return regras.dinheiro_guardado(self.a.usuario, *MARCO)

    def test_aporte_mais_transferencia_para_investimento_menos_resgate(self):
        GoalService.aportar(self.meta, Decimal('500.00'), date(2026, 3, 5), account=self.a.conta)
        self.transferir(self.a.conta, self.investimento, '300.00', date(2026, 3, 6))
        GoalService.resgatar(self.meta, Decimal('100.00'), date(2026, 3, 20), account=self.a.conta)
        # Fora do período
        self.transferir(self.a.conta, self.investimento, '999.00', date(2026, 4, 1))

        guardado = self.guardado()

        self.assertEqual(guardado, Decimal('700.00'))
        self.assertIsInstance(guardado, Decimal)

    def test_cofrinho_para_investimento_nao_conta(self):
        self.transferir(self.a.conta, self.cofrinho, '400.00', date(2026, 2, 10))
        self.transferir(self.cofrinho, self.investimento, '200.00', date(2026, 3, 10))
        self.transferir(self.investimento, self.cofrinho, '50.00', date(2026, 3, 11))

        self.assertEqual(self.guardado(), Decimal('0.00'))

    def test_aporte_do_saldo_livre_nao_conta(self):
        self.transferir(self.a.conta, self.cofrinho, '100.00', date(2026, 2, 10))

        GoalService.aportar(self.meta, Decimal('50.00'), date(2026, 3, 10))

        self.assertEqual(Goal.objects.get(pk=self.meta.pk).current_amount, Decimal('50.00'))
        self.assertEqual(self.guardado(), Decimal('0.00'))


class FaturasDoMesTests(RelatoriosTestCase):

    def test_soma_o_em_aberto_das_faturas_nao_pagas_que_vencem_no_mes_de_brasilia(self):
        cartao = self.cartao(5, 15)
        outro = self.cartao(25, 10)
        # Vence em 15/03: duas compras pendentes
        self.comprar(cartao, '120.00', date(2026, 2, 10))
        self.comprar(cartao, '30.00', date(2026, 2, 20))
        # Vence em 15/04: fica fora
        self.comprar(cartao, '80.00', date(2026, 3, 10))
        # Fatura de outro cartão que vence em 10/03, já paga
        paga = obter_fatura(outro, 3, 2026)
        self.lancar(
            'CREDIT_CARD', '60.00', paga.due_date, credit_card=outro, invoice=paga,
            purchase_date=date(2026, 2, 1), payment_date=date(2026, 3, 10),
        )
        CreditCardInvoice.objects.filter(pk=paga.pk).update(status='PAID')

        with agora_em(2026, 3, 10):
            self.assertEqual(regras.faturas_do_mes(self.a.usuario), Decimal('150.00'))
        # 02h UTC de 01/04 = 23h de 31/03 em Brasília: ainda março
        with agora_em(2026, 4, 1, hora=2):
            self.assertEqual(regras.faturas_do_mes(self.a.usuario), Decimal('150.00'))
        with agora_em(2026, 4, 1, hora=15):
            self.assertEqual(regras.faturas_do_mes(self.a.usuario), Decimal('80.00'))

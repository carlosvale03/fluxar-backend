"""
Fatura de cada compra e primeira fatura não paga (FATURA-07, FATURA-12,
FATURA-13, FATURA-15, FATURA-25).
"""
from datetime import date
from decimal import Decimal

from accounts.faturas import (
    alocar_parcelas, colocar, dividir_valor, fatura_da_compra, obter_fatura, primeira_nao_paga,
)
from accounts.models import CreditCardInvoice
from transactions.models import Transaction
from transactions.services import TransactionService
from tests.faturas.base import FaturasTestCase


class ObterFaturaTests(FaturasTestCase):

    def test_cria_a_fatura_com_as_datas_dos_dias_do_cartao(self):
        cartao = self.cartao(31, 30)

        fatura = obter_fatura(cartao, 2, 2024)

        self.assertEqual((fatura.closing_date, fatura.due_date), (date(2024, 1, 31), date(2024, 2, 29)))
        self.assertEqual(fatura.status, 'OPEN')

    def test_fatura_existente_mantem_as_datas_depois_de_mudar_os_dias(self):
        cartao = self.cartao(10, 20)
        existente = obter_fatura(cartao, 9, 2026)

        cartao.closing_day, cartao.due_day = 5, 15
        cartao.save()

        self.assertEqual(obter_fatura(cartao, 9, 2026).pk, existente.pk)
        self.assertEqual(
            (self.fatura(cartao, 9, 2026).closing_date, self.fatura(cartao, 9, 2026).due_date),
            (date(2026, 9, 10), date(2026, 9, 20)),
        )
        # A criada depois usa os dias novos (FATURA-07)
        nova = obter_fatura(cartao, 10, 2026)
        self.assertEqual((nova.closing_date, nova.due_date), (date(2026, 10, 5), date(2026, 10, 15)))

    def test_get_or_create_invoice_usa_a_mesma_regra(self):
        cartao = self.cartao(31, 30)

        fatura = TransactionService._get_or_create_invoice(cartao, 2, 2025)

        self.assertEqual((fatura.closing_date, fatura.due_date), (date(2025, 1, 31), date(2025, 2, 28)))


class FaturaDaCompraTests(FaturasTestCase):

    def test_avanca_quando_a_fatura_existente_ja_fechou_na_data_da_compra(self):
        cartao = self.cartao(10, 20)
        obter_fatura(cartao, 9, 2026)  # fecha em 10/09
        cartao.closing_day = 15
        cartao.save()

        # Pelos dias novos, 12/09 cairia na fatura de setembro, que já fechou em 10/09
        self.assertEqual(fatura_da_compra(cartao, date(2026, 9, 12)), (10, 2026))

    def test_nao_cria_fatura(self):
        cartao = self.cartao(10, 20)

        self.assertEqual(fatura_da_compra(cartao, date(2026, 9, 5)), (9, 2026))
        self.assertFalse(CreditCardInvoice.objects.filter(card=cartao).exists())


class PrimeiraNaoPagaTests(FaturasTestCase):

    def test_compra_que_cairia_em_fatura_paga_vai_para_a_seguinte_criada_se_faltar(self):
        cartao = self.cartao(10, 20)
        paga = obter_fatura(cartao, 9, 2026)
        paga.status = 'PAID'
        paga.save()

        fatura = primeira_nao_paga(cartao, *fatura_da_compra(cartao, date(2026, 9, 5)))

        self.assertEqual((fatura.month, fatura.year), (10, 2026))
        self.assertEqual(fatura.status, 'OPEN')
        self.assertEqual((fatura.closing_date, fatura.due_date), (date(2026, 10, 10), date(2026, 10, 20)))

    def test_fatura_nao_paga_existente_e_a_propria(self):
        cartao = self.cartao(10, 20)
        aberta = obter_fatura(cartao, 9, 2026)

        self.assertEqual(primeira_nao_paga(cartao, 9, 2026).pk, aberta.pk)


class AlocarParcelasTests(FaturasTestCase):

    def test_compra_em_4x_no_dia_do_fechamento_30(self):
        # Edge case da spec: fechamento no dia 30, vencimento no dia 7, compra em 30/01/2026
        cartao = self.cartao(30, 7)

        faturas = alocar_parcelas(cartao, date(2026, 1, 30), 4)

        self.assertEqual(self.meses(faturas), [(3, 2026), (4, 2026), (5, 2026), (6, 2026)])

    def test_fatura_paga_no_caminho_e_pulada_sem_repetir_fatura(self):
        cartao = self.cartao(10, 20)
        paga = obter_fatura(cartao, 10, 2026)
        paga.status = 'PAID'
        paga.save()

        faturas = alocar_parcelas(cartao, date(2026, 9, 5), 3)

        self.assertEqual(self.meses(faturas), [(9, 2026), (11, 2026), (12, 2026)])


class DividirValorTests(FaturasTestCase):

    def test_100_em_3x(self):
        self.assertEqual(
            dividir_valor(Decimal('100.00'), 3),
            [Decimal('33.34'), Decimal('33.33'), Decimal('33.33')],
        )

    def test_soma_das_parcelas_e_o_valor_da_compra(self):
        for valor, quantidade in (('100.00', 7), ('0.05', 4), ('1234.56', 12), ('10.00', 1)):
            parcelas = dividir_valor(Decimal(valor), quantidade)
            self.assertEqual(len(parcelas), quantidade)
            self.assertEqual(sum(parcelas), Decimal(valor), (valor, quantidade))
            self.assertTrue(all(p == p.quantize(Decimal('0.01')) for p in parcelas))


class ColocarTests(FaturasTestCase):

    def test_grava_a_fatura_e_o_vencimento_dela_juntos(self):
        cartao = self.cartao(10, 20)
        setembro = obter_fatura(cartao, 9, 2026)
        outubro = obter_fatura(cartao, 10, 2026)
        compra = self.compra(cartao, setembro, '50.00')

        colocar(compra, outubro)

        gravada = Transaction.objects.get(pk=compra.pk)
        self.assertEqual(gravada.invoice_id, outubro.pk)
        self.assertEqual(gravada.date, date(2026, 10, 20))

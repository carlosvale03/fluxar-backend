"""
Datas de fechamento e vencimento e o mês da fatura de cada compra
(FATURA-01 a FATURA-04, FATURA-10, FATURA-11).

Os testes percorrem todos os pares de dia de fechamento e de vencimento, de
1 a 31, em todos os meses de 2024 a 2027 (2024 é bissexto).
"""
import calendar
from datetime import date, timedelta

from django.test import SimpleTestCase

from accounts.faturas import datas_da_fatura, dia_no_mes, mes_da_fatura, mes_seguinte

DIAS = range(1, 32)
MESES = [(mes, ano) for ano in range(2024, 2028) for mes in range(1, 13)]


def ultimo_dia(ano, mes):
    return calendar.monthrange(ano, mes)[1]


class DiaNoMesTests(SimpleTestCase):

    def test_dia_que_nao_existe_usa_o_ultimo_dia_do_mes(self):
        self.assertEqual(dia_no_mes(2026, 4, 31), date(2026, 4, 30))
        self.assertEqual(dia_no_mes(2024, 2, 30), date(2024, 2, 29))
        self.assertEqual(dia_no_mes(2025, 2, 30), date(2025, 2, 28))

    def test_ajuste_nao_se_acumula_nos_meses_seguintes(self):
        # Fechamento no dia 31: 30/04, e volta a 31/05 (FATURA-02)
        self.assertEqual(datas_da_fatura(31, 10, 5, 2026)[0], date(2026, 4, 30))
        self.assertEqual(datas_da_fatura(31, 10, 6, 2026)[0], date(2026, 5, 31))


class DatasDaFaturaTests(SimpleTestCase):

    def test_todas_as_combinacoes_de_dias_e_meses(self):
        for fechamento_dia in DIAS:
            for vencimento_dia in DIAS:
                for mes, ano in MESES:
                    fechamento, vencimento = datas_da_fatura(fechamento_dia, vencimento_dia, mes, ano)
                    contexto = (fechamento_dia, vencimento_dia, mes, ano)

                    # Vencimento no mês da fatura, no dia cadastrado ou no último (FATURA-01, FATURA-02)
                    self.assertEqual((vencimento.month, vencimento.year), (mes, ano), contexto)
                    self.assertEqual(vencimento.day, min(vencimento_dia, ultimo_dia(ano, mes)), contexto)

                    # Fechamento no mesmo mês (FATURA-03) ou no anterior (FATURA-04)
                    if vencimento_dia > fechamento_dia:
                        esperado = (mes, ano)
                    else:
                        esperado = (12, ano - 1) if mes == 1 else (mes - 1, ano)
                    self.assertEqual((fechamento.month, fechamento.year), esperado, contexto)
                    self.assertEqual(
                        fechamento.day,
                        min(fechamento_dia, ultimo_dia(fechamento.year, fechamento.month)),
                        contexto,
                    )

    def test_vencimento_no_dia_30_em_fevereiro(self):
        self.assertEqual(datas_da_fatura(20, 30, 2, 2024)[1], date(2024, 2, 29))
        self.assertEqual(datas_da_fatura(20, 30, 2, 2025)[1], date(2025, 2, 28))

    def test_vencimento_maior_que_fechamento_vence_no_mesmo_mes(self):
        self.assertEqual(datas_da_fatura(10, 20, 9, 2026), (date(2026, 9, 10), date(2026, 9, 20)))

    def test_vencimento_menor_ou_igual_ao_fechamento_vence_no_mes_seguinte(self):
        self.assertEqual(datas_da_fatura(30, 7, 3, 2026), (date(2026, 2, 28), date(2026, 3, 7)))
        self.assertEqual(datas_da_fatura(15, 15, 1, 2026), (date(2025, 12, 15), date(2026, 1, 15)))


class MesDaFaturaTests(SimpleTestCase):

    def test_compra_no_fechamento_ajustado_vai_para_a_fatura_seguinte(self):
        # Fechamento no dia 31: 30/04 é o fechamento de abril (FATURA-01, FATURA-11)
        self.assertEqual(mes_da_fatura(31, 10, date(2026, 4, 30)), (6, 2026))
        # A véspera fica na fatura que fecha em abril (FATURA-10)
        self.assertEqual(mes_da_fatura(31, 10, date(2026, 4, 29)), (5, 2026))

    def test_compra_cai_na_fatura_que_fecha_no_mes_ou_no_seguinte(self):
        """
        Em todas as combinações, a véspera do fechamento cai na fatura que fecha
        nesse dia, e o próprio dia do fechamento cai na fatura seguinte.
        """
        for fechamento_dia in DIAS:
            for vencimento_dia in DIAS:
                for mes, ano in MESES:
                    fechamento, _ = datas_da_fatura(fechamento_dia, vencimento_dia, mes, ano)
                    contexto = (fechamento_dia, vencimento_dia, mes, ano)
                    self.assertEqual(
                        mes_da_fatura(fechamento_dia, vencimento_dia, fechamento - timedelta(days=1)),
                        (mes, ano), contexto,
                    )
                    self.assertEqual(
                        mes_da_fatura(fechamento_dia, vencimento_dia, fechamento),
                        mes_seguinte(mes, ano), contexto,
                    )

    def test_mes_seguinte_vira_o_ano(self):
        self.assertEqual(mes_seguinte(12, 2026), (1, 2027))
        self.assertEqual(mes_seguinte(3, 2026), (4, 2026))

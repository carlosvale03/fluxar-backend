"""Total de cada dia na lista de transações, sobre o filtro inteiro (CONTRATO-09)."""
import uuid
from datetime import date

from .base import URL_TRANSACOES, ContratosTestCase

DIA_15 = date(2026, 9, 15)
DIA_20 = date(2026, 9, 20)


class TotalDoDiaTests(ContratosTestCase):

    def test_dia_em_duas_paginas_tem_o_mesmo_total(self):
        for _ in range(15):
            self.lancar('EXPENSE', '2.00', date=DIA_20)
        for _ in range(10):
            self.lancar('EXPENSE', '1.25', date=DIA_15)

        primeira = self.client.get(URL_TRANSACOES, {'page': 1})
        segunda = self.client.get(URL_TRANSACOES, {'page': 2})

        # A página 1 tem 5 lançamentos do dia 15; a página 2, os outros 5
        self.assertEqual(primeira.data['day_totals'], {'2026-09-20': '-30.00', '2026-09-15': '-12.50'})
        self.assertEqual(segunda.data['day_totals'], {'2026-09-15': '-12.50'})

    def test_entradas_somam_e_saidas_subtraem(self):
        grupo = uuid.uuid4()
        self.lancar('INCOME', '100.00')
        self.lancar('TRANSFER_IN', '20.00', transfer_id=grupo)
        self.lancar('EXPENSE', '30.00')
        self.lancar('CREDIT_CARD', '10.00')
        self.lancar('TRANSFER_OUT', '5.00', transfer_id=grupo)
        self.lancar('INVOICE_PAYMENT', '7.00')

        resp = self.client.get(URL_TRANSACOES)

        self.assertEqual(resp.data['day_totals'], {'2026-09-15': '68.00'})

    def test_respeita_o_filtro_ativo(self):
        self.lancar('INCOME', '100.00')
        self.lancar('EXPENSE', '30.00')
        self.lancar('CREDIT_CARD', '10.50')
        self.lancar('EXPENSE', '99.00', usuario=self.b)

        resp = self.client.get(URL_TRANSACOES, {'type': 'EXPENSE'})

        self.assertEqual(resp.data['day_totals'], {'2026-09-15': '-40.50'})

    def test_pagina_vazia_nao_tem_totais(self):
        self.lancar('EXPENSE', '30.00')

        resp = self.client.get(URL_TRANSACOES, {'page': 9})

        self.assertEqual(resp.data['day_totals'], {})

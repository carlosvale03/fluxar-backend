"""
Valores e datas em texto no formato brasileiro (IMPORT-09, IMPORT-10,
IMPORT-12, IMPORT-13, IMPORT-15, AD-009).

Os exemplos de valor são os da spec e os de `lerValorDigitado` no frontend
(`src/lib/dinheiro.ts`): as duas leituras seguem a mesma regra.
"""
from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from core.valores import VALOR_INVALIDO, ler_valor_em_texto
from data_exchange.importacao.texto import DATA_INVALIDA, ler_data_em_texto, normalizar


class ValorEmTextoTests(SimpleTestCase):

    def assert_valor(self, texto, esperado):
        valor = ler_valor_em_texto(texto)
        self.assertIsInstance(valor, Decimal)
        self.assertEqual(valor, Decimal(esperado), texto)

    def test_com_virgula_a_virgula_e_decimal(self):
        """IMPORT-09: a vírgula é decimal e os pontos são de milhar."""
        self.assert_valor('1.234,56', '1234.56')
        self.assert_valor('R$ -45,00', '-45.00')
        self.assert_valor('45,5', '45.50')
        self.assert_valor('1.234.567,89', '1234567.89')

    def test_sem_virgula_ponto_de_milhar_com_grupos_de_tres(self):
        """IMPORT-10: "1.500" e "1.500.000" são milhares."""
        self.assert_valor('1.500', '1500.00')
        self.assert_valor('1.500.000', '1500000.00')
        self.assert_valor('R$ 2.000', '2000.00')

    def test_sem_virgula_ponto_decimal_nos_demais_casos(self):
        """IMPORT-10: "12.5" e "0.50" são decimais."""
        self.assert_valor('12.5', '12.50')
        self.assert_valor('0.50', '0.50')
        self.assert_valor('-12.50', '-12.50')
        self.assert_valor('100', '100.00')

    def test_valor_ilegivel_zero_ou_com_mais_de_duas_casas_e_invalido(self):
        """IMPORT-12: "abc", "0,00" e "1,234" levantam "Valor inválido"."""
        for texto in ('abc', '0,00', '1,234', '0.500', '', 'R$', '-', '1.2.3'):
            with self.subTest(texto=texto):
                with self.assertRaisesMessage(ValueError, VALOR_INVALIDO):
                    ler_valor_em_texto(texto)
        self.assertEqual(VALOR_INVALIDO, 'Valor inválido')


class DataEmTextoTests(SimpleTestCase):

    def test_tres_formatos_com_o_dia_antes_do_mes(self):
        """IMPORT-13: os três formatos dão 4 de março de 2026."""
        for texto in ('04/03/2026', '04/03/26', '2026-03-04', ' 4/3/2026 '):
            with self.subTest(texto=texto):
                self.assertEqual(ler_data_em_texto(texto), date(2026, 3, 4))

    def test_data_inexistente_ou_em_outro_formato_e_invalida(self):
        """IMPORT-15: "29/02/2025" e "2026/03/04" levantam "Data inválida"."""
        for texto in ('29/02/2025', '2026/03/04', '31/04/2026', 'ontem', '', '04-03-2026'):
            with self.subTest(texto=texto):
                with self.assertRaisesMessage(ValueError, DATA_INVALIDA):
                    ler_data_em_texto(texto)
        self.assertEqual(DATA_INVALIDA, 'Data inválida')


class NormalizarTests(SimpleTestCase):

    def test_sem_acentos_minusculas_e_sem_espacos_nas_pontas(self):
        """IMPORT-16 e IMPORT-23: a comparação não diferencia maiúsculas nem acentos."""
        self.assertEqual(normalizar('  Crédito '), 'credito')
        self.assertEqual(normalizar('SAÍDA'), 'saida')
        self.assertEqual(normalizar('Alimentação'), normalizar('alimentacao'))
        self.assertEqual(normalizar(None), '')

"""
Leitura do arquivo: formatos, limites, CSV brasileiro, XLSX tipado, OFX de
uma conta e número de cada linha (IMPORT-01, IMPORT-02, IMPORT-04 a
IMPORT-08, IMPORT-11, IMPORT-14, IMPORT-32).

A etapa de mapeamento (preflight) usa a mesma leitura, com os mesmos
formatos e limites; por isso os casos de recusa passam pela rota dela.
"""
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.exceptions import ValidationError

from data_exchange.importacao.leitura import LinhaBruta, TransacaoOfx, ler_ofx, ler_planilha

from .base import (
    MAPEAMENTO, ImportacaoTestCase, arquivo_csv, arquivo_ofx, arquivo_xlsx, transacao_ofx,
)

FORMATO_NAO_SUPORTADO = 'Formato não suportado. Envie um arquivo OFX, CSV ou XLSX.'
ARQUIVO_GRANDE_DEMAIS = 'O arquivo passa do limite de 5 MB.'
LINHAS_DEMAIS = 'O arquivo passa do limite de 10.000 linhas.'
ARQUIVO_ILEGIVEL = 'Não foi possível ler o arquivo.'
MAIS_DE_UMA_CONTA = 'O arquivo tem mais de uma conta. Exporte um arquivo por conta.'

CABECALHO = ['Data', 'Descrição', 'Valor']


class FormatosTests(ImportacaoTestCase):

    def test_xls_e_txt_recebem_formato_nao_suportado(self):
        """IMPORT-02: outra extensão, inclusive .xls, recebe 400 com a mensagem da spec."""
        for nome in ('extrato.xls', 'extrato.txt', 'extrato'):
            with self.subTest(nome=nome):
                arquivo = SimpleUploadedFile(nome, b'Data;Valor\n01/09/2026;10,00\n')
                self.assert_recusado(self.preflight(arquivo), FORMATO_NAO_SUPORTADO)

        with self.assertRaises(ValidationError) as recusa:
            ler_ofx(SimpleUploadedFile('extrato.txt', b'<OFX>'))
        self.assertEqual(recusa.exception.detail, {'file': [FORMATO_NAO_SUPORTADO]})

    def test_csv_e_xlsx_sao_aceitos(self):
        """IMPORT-01: .csv e .xlsx (em maiúsculas também) passam pela leitura."""
        linhas = [CABECALHO, ['10/09/2026', 'Padaria', '-45,00']]
        for arquivo in (arquivo_csv(linhas), arquivo_xlsx(linhas, nome='EXTRATO.XLSX')):
            with self.subTest(nome=arquivo.name):
                resp = self.preflight(arquivo)
                self.assertEqual((resp.status_code, resp.data), (200, {'accounts': []}))

    def test_arquivo_de_6_mb_e_recusado_antes_de_ler(self):
        """IMPORT-04: mais de 5 MB recebe 400, sem ler nenhuma linha."""
        conteudo = b'Data;Descricao;Valor\n' + b'10/09/2026;Padaria;-45,00\n' * 250_000
        self.assertGreater(len(conteudo), 6 * 1024 * 1024)

        resp = self.preflight(SimpleUploadedFile('grande.csv', conteudo))
        self.assert_recusado(resp, ARQUIVO_GRANDE_DEMAIS)

        with patch('data_exchange.importacao.leitura.pd.read_csv') as read_csv, \
                self.assertRaises(ValidationError) as recusa:
            ler_planilha(SimpleUploadedFile('grande.csv', conteudo), MAPEAMENTO, 'INCOME_EXPENSE')
        self.assertEqual(recusa.exception.detail, {'file': [ARQUIVO_GRANDE_DEMAIS]})
        read_csv.assert_not_called()

    def test_mais_de_10_000_linhas_de_dados_e_recusado(self):
        """IMPORT-05: 10.001 linhas de dados recebem 400; 10.000 passam."""
        dados = [['10/09/2026', 'Padaria', '-45,00']]
        resp = self.preflight(arquivo_csv([CABECALHO] + dados * 10_001))
        self.assert_recusado(resp, LINHAS_DEMAIS)

        resp = self.preflight(arquivo_csv([CABECALHO] + dados * 10_000 + [['', '', '']] * 5))
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_coluna_mapeada_ausente_cita_as_colunas(self):
        """IMPORT-06: a mensagem diz quais colunas mapeadas faltam no arquivo."""
        mapeamento = {**MAPEAMENTO, 'category_column': 'Categoria', 'account_column': 'Conta'}
        resp = self.preflight(arquivo_csv([CABECALHO, ['10/09/2026', 'Padaria', '-45,00']]), mapeamento)
        self.assert_recusado(resp, 'Colunas não encontradas no arquivo: Categoria, Conta.')

    def test_arquivo_corrompido_e_ilegivel(self):
        """IMPORT-06: arquivo que não pode ser lido recebe "Não foi possível ler o arquivo."."""
        for arquivo in (
            SimpleUploadedFile('lixo.xlsx', b'nada de planilha aqui'),
            SimpleUploadedFile('vazio.csv', b''),
        ):
            with self.subTest(nome=arquivo.name):
                self.assert_recusado(self.preflight(arquivo), ARQUIVO_ILEGIVEL)

        with self.assertRaises(ValidationError) as recusa:
            ler_ofx(SimpleUploadedFile('lixo.ofx', b'nada de OFX aqui'))
        self.assertEqual(recusa.exception.detail, {'file': [ARQUIVO_ILEGIVEL]})


class CsvTests(ImportacaoTestCase):

    def test_csv_do_excel_em_portugues(self):
        """IMPORT-08: `;` e Windows-1252, com acentos, lido sem erro e como texto."""
        arquivo = arquivo_csv(
            [['Data', 'Descrição', 'Valor', 'Tipo'], ['04/03/2026', 'Salário', '1.234,56', 'Crédito']],
            separador=';', codificacao='cp1252',
        )
        linhas = ler_planilha(arquivo, {**MAPEAMENTO, 'type_column': 'Tipo'}, 'INCOME_EXPENSE')

        self.assertEqual(linhas, [LinhaBruta(2, {
            'Data': '04/03/2026', 'Descrição': 'Salário', 'Valor': '1.234,56', 'Tipo': 'Crédito',
        })])

    def test_csv_com_virgula_e_utf8_com_bom(self):
        """IMPORT-08: `,` e UTF-8 com BOM também são reconhecidos sozinhos."""
        conteudo = '﻿Data,Descrição,Valor\n10/09/2026,Pão de queijo,"-12,50"\n'.encode('utf-8')
        linhas = ler_planilha(SimpleUploadedFile('extrato.csv', conteudo), MAPEAMENTO, 'INCOME_EXPENSE')

        self.assertEqual(linhas, [LinhaBruta(2, {
            'Data': '10/09/2026', 'Descrição': 'Pão de queijo', 'Valor': '-12,50',
        })])

    def test_linhas_vazias_somem_e_as_demais_mantem_o_numero(self):
        """IMPORT-32 e IMPORT-30: cabeçalho = 1; linhas vazias não contam."""
        conteudo = (
            'Data;Descrição;Valor\n'
            '01/09/2026;Linha 2;1,00\n'
            '\n'
            '03/09/2026;Linha 4;3,00\n'
            ';;\n'
            ' ; ; \n'
            '06/09/2026;Linha 7;6,00\n'
            '\n'
        ).encode('utf-8')
        linhas = ler_planilha(SimpleUploadedFile('extrato.csv', conteudo), MAPEAMENTO, 'INCOME_EXPENSE')

        self.assertEqual(
            [(l.numero, l.valores['Descrição']) for l in linhas],
            [(2, 'Linha 2'), (4, 'Linha 4'), (7, 'Linha 7')],
        )

    def test_arquivo_so_com_o_cabecalho_nao_tem_linhas(self):
        """Edge case: arquivo só com o cabeçalho é lido com zero linhas."""
        self.assertEqual(ler_planilha(arquivo_csv([CABECALHO]), MAPEAMENTO, 'INCOME_EXPENSE'), [])


class XlsxTests(ImportacaoTestCase):

    def test_celulas_numericas_e_de_data_mantem_o_tipo(self):
        """IMPORT-11 e IMPORT-14: 1500 chega como número e a data, como data."""
        arquivo = arquivo_xlsx([
            CABECALHO,
            [datetime(2026, 3, 4), 'Aluguel', 1500],
            [None, None, None],
            ['04/03/2026', 'Texto', '1.500'],
            [date(2026, 3, 5), 'Centavos', -45.5],
        ])
        linhas = ler_planilha(arquivo, MAPEAMENTO, 'INCOME_EXPENSE')

        self.assertEqual([l.numero for l in linhas], [2, 4, 5])
        self.assertEqual(linhas[0].valores, {'Data': datetime(2026, 3, 4), 'Descrição': 'Aluguel', 'Valor': 1500})
        self.assertIsInstance(linhas[0].valores['Valor'], int)
        self.assertEqual(linhas[1].valores, {'Data': '04/03/2026', 'Descrição': 'Texto', 'Valor': '1.500'})
        self.assertEqual(linhas[2].valores['Valor'], -45.5)
        self.assertEqual(linhas[2].valores['Data'], datetime(2026, 3, 5))


class OfxTests(ImportacaoTestCase):

    def test_ofx_com_duas_contas_e_recusado(self):
        """IMPORT-07: mais de uma conta recebe 400 com a mensagem da spec."""
        arquivo = arquivo_ofx(transacao_ofx('1', '20260910', '-45.00', memo='Padaria'), contas=('1', '2'))
        with self.assertRaises(ValidationError) as recusa:
            ler_ofx(arquivo)
        self.assertEqual(recusa.exception.detail, {'file': [MAIS_DE_UMA_CONTA]})

    def test_transacoes_com_a_posicao_no_extrato(self):
        """IMPORT-30: o número de cada transação é a posição dela, a partir de 1."""
        arquivo = arquivo_ofx(
            transacao_ofx('A1', '20260910', '-45.00', memo='Padaria'),
            transacao_ofx('A2', '20260911', '100.50', favorecido='Cliente'),
        )
        self.assertEqual(ler_ofx(arquivo), [
            TransacaoOfx(1, date(2026, 9, 10), Decimal('-45.00'), 'Padaria', '', 'A1'),
            TransacaoOfx(2, date(2026, 9, 11), Decimal('100.50'), '', 'Cliente', 'A2'),
        ])


class PreflightTests(ImportacaoTestCase):

    def test_lista_as_contas_da_planilha(self):
        """A etapa de mapeamento devolve os nomes de conta sem repetir."""
        arquivo = arquivo_csv([
            CABECALHO + ['Conta'],
            ['10/09/2026', 'Padaria', '-45,00', 'Nubank '],
            ['11/09/2026', 'Mercado', '-10,00', 'Itaú'],
            ['', '', '', ''],
            ['12/09/2026', 'Feira', '-5,00', 'Nubank'],
            ['13/09/2026', 'Sem conta', '-5,00', ''],
        ])
        resp = self.preflight(arquivo, {**MAPEAMENTO, 'account_column': 'Conta'})
        self.assertEqual((resp.status_code, resp.data), (200, {'accounts': ['Itaú', 'Nubank']}))

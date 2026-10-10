"""
Leitura de todas as abas do arquivo (IMPCOMP-01 a IMPCOMP-03).

O XLSX traz todas as abas, cada uma com o nome, o cabeçalho (a primeira
linha não vazia) e as linhas numeradas como na planilha; o CSV é uma aba
única com o nome do arquivo; o limite de 10.000 linhas vale para a soma.
"""
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.exceptions import ValidationError

from data_exchange.importacao.leitura import LinhaBruta, ler_abas

from .base import ImportacaoTestCase, arquivo_csv, arquivo_xlsx
from .mobills import CABECALHO, CABECALHO_TRANSFERENCIAS, arquivo_mobills

LINHAS_DEMAIS = 'O arquivo passa do limite de 10.000 linhas.'
ARQUIVO_GRANDE_DEMAIS = 'O arquivo passa do limite de 5 MB.'
ARQUIVO_ILEGIVEL = 'Não foi possível ler o arquivo.'
FORMATO_NAO_SUPORTADO = 'Formato não suportado. Envie um arquivo OFX, CSV ou XLSX.'


class LeituraDasAbasTests(ImportacaoTestCase):

    def assert_recusa(self, arquivo, mensagem):
        with self.assertRaises(ValidationError) as recusa:
            ler_abas(arquivo)
        self.assertEqual(recusa.exception.detail, {'file': [mensagem]})

    def test_xlsx_de_quatro_abas_devolve_as_quatro(self):
        """IMPCOMP-01: nome, cabeçalho e linhas de cada aba, na ordem do arquivo."""
        abas = ler_abas(arquivo_mobills())

        self.assertEqual(
            [(aba.nome, aba.cabecalho) for aba in abas],
            [('Receitas e Despesas', CABECALHO), ('Despesas', CABECALHO),
             ('Receitas', CABECALHO), ('Transferências', CABECALHO_TRANSFERENCIAS)],
        )
        # 57 linhas + a linha "Total"; a linha vazia antes do total é pulada
        primeira = abas[0]
        self.assertEqual(len(primeira.linhas), 58)
        self.assertEqual([linha.numero for linha in primeira.linhas][:3], [2, 3, 4])
        self.assertEqual(primeira.linhas[-1].numero, 60)
        self.assertEqual(primeira.linhas[0].valores['Descrição'], 'Lançamento 1')
        self.assertEqual(primeira.linhas[0].valores['Situação'], 'Paga')
        self.assertEqual(len(abas[3].linhas), 10)
        self.assertEqual(abas[3].linhas[-1].numero, 12)

    def test_cabecalho_e_a_primeira_linha_nao_vazia_e_a_numeracao_e_a_da_planilha(self):
        """IMPCOMP-01, IMPORT-30, IMPORT-32: linhas vazias puladas sem mudar o número das seguintes."""
        arquivo = arquivo_xlsx(abas=[
            ('Extrato', [
                [None, None],
                ['Data', 'Valor'],
                ['10/09/2026', 10],
                [None, None],
                ['11/09/2026', -5.5],
            ]),
            ('Vazia', []),
        ])
        extrato, vazia = ler_abas(arquivo)

        self.assertEqual(extrato.cabecalho, ['Data', 'Valor'])
        self.assertEqual(extrato.linhas, [
            LinhaBruta(3, {'Data': '10/09/2026', 'Valor': 10}),
            LinhaBruta(5, {'Data': '11/09/2026', 'Valor': -5.5}),
        ])
        self.assertEqual((vazia.nome, vazia.cabecalho, vazia.linhas), ('Vazia', [], []))

    def test_linha_total_e_marcada_como_candidata_a_resumo(self):
        """IMPCOMP-15: a leitura marca a linha cuja primeira célula começa com "Total"."""
        abas = ler_abas(arquivo_mobills())
        candidatas = [(linha.numero, linha.valores['Data']) for linha in abas[0].linhas if linha.resumo]
        self.assertEqual(candidatas, [(60, 'Total (57)')])

    def test_csv_e_uma_aba_com_o_nome_do_arquivo(self):
        """IMPCOMP-02: o CSV vira uma aba só, com o nome do arquivo e a numeração da planilha."""
        arquivo = arquivo_csv([
            ['Data', 'Descrição', 'Valor'],
            ['10/09/2026', 'Padaria', '-45,00'],
            ['', '', ''],
            ['11/09/2026', 'Salário', '1.500,00'],
        ], nome='banco.csv')
        abas = ler_abas(arquivo)

        self.assertEqual(len(abas), 1)
        self.assertEqual((abas[0].nome, abas[0].cabecalho), ('banco.csv', ['Data', 'Descrição', 'Valor']))
        self.assertEqual(abas[0].linhas, [
            LinhaBruta(2, {'Data': '10/09/2026', 'Descrição': 'Padaria', 'Valor': '-45,00'}),
            LinhaBruta(4, {'Data': '11/09/2026', 'Descrição': 'Salário', 'Valor': '1.500,00'}),
        ])

    def test_csv_windows_1252_com_virgula_e_lido(self):
        """IMPCOMP-02 com IMPORT-08: separador e codificação detectados."""
        arquivo = arquivo_csv(
            [['Data', 'Histórico', 'Valor'], ['10/09/2026', 'Café', '-4.50']],
            separador=',', codificacao='cp1252',
        )
        aba = ler_abas(arquivo)[0]
        self.assertEqual(aba.linhas, [LinhaBruta(2, {'Data': '10/09/2026', 'Histórico': 'Café', 'Valor': '-4.50'})])

    def test_soma_das_abas_acima_de_10_000_linhas_e_recusada(self):
        """IMPCOMP-03: duas abas de 6.000 linhas recebem a mensagem do limite."""
        dados = [['10/09/2026', 'Padaria', -45]] * 6_000
        arquivo = arquivo_xlsx(abas=[
            ('Janeiro', [['Data', 'Descrição', 'Valor']] + dados),
            ('Fevereiro', [['Data', 'Descrição', 'Valor']] + dados),
        ])
        self.assert_recusa(arquivo, LINHAS_DEMAIS)

    def test_10_000_linhas_na_soma_das_abas_passam(self):
        """IMPCOMP-03: exatamente 10.000 linhas de dados, divididas em duas abas, são lidas."""
        dados = [['10/09/2026', 'Padaria', -45]] * 5_000
        arquivo = arquivo_xlsx(abas=[
            ('Janeiro', [['Data', 'Descrição', 'Valor']] + dados),
            ('Fevereiro', [['Data', 'Descrição', 'Valor']] + dados),
        ])
        self.assertEqual([len(aba.linhas) for aba in ler_abas(arquivo)], [5_000, 5_000])

    def test_formato_tamanho_e_arquivo_ilegivel(self):
        """IMPORT-02, IMPORT-04 e IMPORT-06 continuam valendo na leitura das abas."""
        self.assert_recusa(SimpleUploadedFile('extrato.xls', b'abc'), FORMATO_NAO_SUPORTADO)
        self.assert_recusa(SimpleUploadedFile('extrato.ofx', b'<OFX>'), FORMATO_NAO_SUPORTADO)
        grande = SimpleUploadedFile('grande.xlsx', b'0' * (5 * 1024 * 1024 + 1))
        self.assert_recusa(grande, ARQUIVO_GRANDE_DEMAIS)
        self.assert_recusa(SimpleUploadedFile('quebrado.xlsx', b'nao e um xlsx'), ARQUIVO_ILEGIVEL)

"""
Base dos testes de importação.

O usuário A tem uma conta corrente com saldo inicial de R$ 1.000,00, uma
poupança zerada e categorias de receita e de despesa; o usuário B serve
para os testes de isolamento. Os arquivos de exemplo (CSV, XLSX e OFX) são
gerados no próprio teste.
"""
import io
import json
from decimal import Decimal
from types import SimpleNamespace

from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook
from rest_framework.test import APITestCase

from accounts.models import Account
from api.models import User
from transactions.models import Category

URL_OFX = '/api/import/ofx/'
URL_PLANILHA = '/api/import/spreadsheet/'
URL_PREFLIGHT = '/api/import/spreadsheet/preflight/'

MAPEAMENTO = {'date_column': 'Data', 'description_column': 'Descrição', 'amount_column': 'Valor'}

CABECALHO_OFX = """OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<SIGNONMSGSRSV1><SONRS><STATUS><CODE>0<SEVERITY>INFO</STATUS><DTSERVER>20260915<LANGUAGE>POR</SONRS></SIGNONMSGSRSV1>
<BANKMSGSRSV1>{extratos}</BANKMSGSRSV1>
</OFX>
"""

EXTRATO_OFX = """<STMTTRNRS><TRNUID>1<STATUS><CODE>0<SEVERITY>INFO</STATUS>
<STMTRS><CURDEF>BRL<BANKACCTFROM><BANKID>001<ACCTID>{conta}<ACCTTYPE>CHECKING</BANKACCTFROM>
<BANKTRANLIST><DTSTART>20260901<DTEND>20260930
{transacoes}
</BANKTRANLIST>
<LEDGERBAL><BALAMT>0.00<DTASOF>20260930</LEDGERBAL>
</STMTRS></STMTTRNRS>"""


def transacao_ofx(fitid, data, valor, memo='', favorecido=''):
    """Uma `<STMTTRN>`; `data` em AAAAMMDD e `valor` com ponto e sinal."""
    partes = [f'<STMTTRN><TRNTYPE>OTHER<DTPOSTED>{data}<TRNAMT>{valor}<FITID>{fitid}']
    if favorecido:
        partes.append(f'<NAME>{favorecido}')
    if memo:
        partes.append(f'<MEMO>{memo}')
    partes.append('</STMTTRN>')
    return ''.join(partes)


def arquivo_ofx(*transacoes, contas=('123',), nome='extrato.ofx'):
    """Um OFX com as `transacoes` em cada uma das `contas`."""
    extratos = ''.join(
        EXTRATO_OFX.format(conta=conta, transacoes='\n'.join(transacoes)) for conta in contas
    )
    conteudo = CABECALHO_OFX.format(extratos=extratos).encode('ascii')
    return SimpleUploadedFile(nome, conteudo, content_type='application/x-ofx')


def arquivo_csv(linhas, nome='extrato.csv', separador=';', codificacao='utf-8'):
    """Um CSV com as `linhas` (listas de textos; a primeira é o cabeçalho)."""
    texto = '\n'.join(separador.join(linha) for linha in linhas) + '\n'
    return SimpleUploadedFile(nome, texto.encode(codificacao), content_type='text/csv')


def arquivo_xlsx(linhas=None, nome='extrato.xlsx', abas=None):
    """
    Um XLSX com as `linhas` na primeira aba, ou com as `abas` (pares
    `(nome da aba, linhas)`, na ordem); os valores mantêm o tipo.
    """
    planilha = Workbook()
    if abas is None:
        abas = [(planilha.active.title, linhas)]
    planilha.remove(planilha.active)
    for titulo, linhas_da_aba in abas:
        aba = planilha.create_sheet(titulo)
        for linha in linhas_da_aba:
            aba.append(list(linha))
    conteudo = io.BytesIO()
    planilha.save(conteudo)
    return SimpleUploadedFile(
        nome, conteudo.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


def criar_dados(letra):
    usuario = User.objects.create_user(
        email=f'importacao.{letra.lower()}@teste.fluxar',
        password='senha-de-teste-123',
        name=f'Usuário {letra}',
    )
    conta = Account.objects.create(
        user=usuario, name=f'Corrente {letra}', type='CHECKING',
        initial_balance=Decimal('1000.00'),
    )
    poupanca = Account.objects.create(
        user=usuario, name=f'Poupança {letra}', type='SAVINGS',
        initial_balance=Decimal('0.00'),
    )
    receita = Category.objects.create(user=usuario, name=f'Salário {letra}', type='INCOME')
    despesa = Category.objects.create(user=usuario, name=f'Mercado {letra}', type='EXPENSE')
    return SimpleNamespace(usuario=usuario, conta=conta, poupanca=poupanca, receita=receita, despesa=despesa)


class ImportacaoTestCase(APITestCase):
    """Usuários A (`self.a`) e B (`self.b`), com o cliente autenticado como A."""

    @classmethod
    def setUpTestData(cls):
        cls.a = criar_dados('A')
        cls.b = criar_dados('B')

    def setUp(self):
        self.client.force_authenticate(user=self.a.usuario)

    def preflight(self, arquivo, mapeamento=None, import_type='INCOME_EXPENSE'):
        return self.client.post(URL_PREFLIGHT, {
            'file': arquivo, 'mapping': json.dumps(mapeamento or MAPEAMENTO), 'import_type': import_type,
        }, format='multipart')

    def assert_recusado(self, resp, mensagem, campo='file'):
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data, {campo: [mensagem]})

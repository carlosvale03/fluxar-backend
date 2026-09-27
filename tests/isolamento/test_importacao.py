import json
from datetime import date
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import Account
from transactions.models import Transaction
from tests.isolamento.base import DoisUsuariosTestCase

URL_OFX = '/api/import/ofx/'
URL_PLANILHA = '/api/import/spreadsheet/'

OFX = """OFXHEADER:100
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
<BANKMSGSRSV1><STMTTRNRS><TRNUID>1<STATUS><CODE>0<SEVERITY>INFO</STATUS>
<STMTRS><CURDEF>BRL<BANKACCTFROM><BANKID>001<ACCTID>123<ACCTTYPE>CHECKING</BANKACCTFROM>
<BANKTRANLIST><DTSTART>20260901<DTEND>20260930
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260910<TRNAMT>-45.00<FITID>1<MEMO>Padaria</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL><BALAMT>955.00<DTASOF>20260930</LEDGERBAL>
</STMTRS></STMTTRNRS></BANKMSGSRSV1>
</OFX>
"""

MAPEAMENTO = {'date_column': 'Data', 'description_column': 'Descricao', 'amount_column': 'Valor'}


class ImportacaoTests(DoisUsuariosTestCase):

    def setUp(self):
        self.cliente = self.como(self.a.usuario)

    def arquivo_ofx(self):
        return SimpleUploadedFile('extrato.ofx', OFX.encode('ascii'), content_type='application/x-ofx')

    def arquivo_planilha(self, conteudo='Data,Descricao,Valor\n10/09/2026,Padaria,-45.00\n'):
        return SimpleUploadedFile('extrato.csv', conteudo.encode('utf-8'), content_type='text/csv')

    def enviar_ofx(self, conta):
        return self.cliente.post(URL_OFX, {'file': self.arquivo_ofx(), 'account_id': conta}, format='multipart')

    def enviar_planilha(self, conta, **extra):
        dados = {
            'file': extra.pop('arquivo', None) or self.arquivo_planilha(),
            'mapping': json.dumps(extra.pop('mapeamento', MAPEAMENTO)),
            'import_type': 'INCOME_EXPENSE',
        }
        if conta is not None:
            dados['account_id'] = conta
        dados.update(extra)
        return self.cliente.post(URL_PLANILHA, dados, format='multipart')

    def assert_nada_gravado(self, total_transacoes):
        self.assertEqual(Transaction.objects.count(), total_transacoes)
        self.assertFalse(Transaction.objects.filter(account=self.b.conta).exists())
        self.assertEqual(Account.objects.get(pk=self.b.conta.pk).balance, Decimal('1000.00'))

    # --- Recusa da conta padrão ---

    def test_ofx_com_conta_de_b_e_recusado(self):
        total = Transaction.objects.count()
        resp_inexistente = self.enviar_ofx(self.ID_INEXISTENTE)
        resp = self.enviar_ofx(str(self.b.conta.id))

        self.assert_mesma_recusa(resp, resp_inexistente, 'account_id', 'Conta não encontrada.')
        self.assert_nada_gravado(total)

    def test_planilha_com_conta_de_b_e_recusada(self):
        total = Transaction.objects.count()
        resp_inexistente = self.enviar_planilha(self.ID_INEXISTENTE)
        resp = self.enviar_planilha(str(self.b.conta.id))

        self.assert_mesma_recusa(resp, resp_inexistente, 'account_id', 'Conta não encontrada.')
        self.assert_nada_gravado(total)

    # --- Mapeamento de contas ---

    def test_mapeamento_para_conta_de_b_nao_grava_na_conta_de_b(self):
        ids_antes = set(Transaction.objects.values_list('id', flat=True))
        self.enviar_planilha(
            None,
            arquivo=self.arquivo_planilha('Data,Descricao,Valor,Conta\n10/09/2026,Padaria,-45.00,Banco B\n'),
            mapeamento={**MAPEAMENTO, 'account_column': 'Conta'},
            account_mapping=json.dumps({'Banco B': str(self.b.conta.id)}),
        )

        novas = Transaction.objects.exclude(id__in=ids_antes)
        self.assertFalse(Transaction.objects.filter(account=self.b.conta).exists())
        self.assertEqual({t.user for t in novas} - {self.a.usuario}, set())
        self.assertEqual(Account.objects.get(pk=self.b.conta.pk).balance, Decimal('1000.00'))

    # --- Caminho feliz ---

    def test_ofx_com_conta_de_a_continua_funcionando(self):
        resp = self.enviar_ofx(str(self.a.conta.id))

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['imported'], 1)
        importada = Transaction.objects.get(description='Padaria')
        self.assertEqual(
            (importada.user, importada.account, importada.type, importada.amount, importada.date),
            (self.a.usuario, self.a.conta, 'EXPENSE', Decimal('45.00'), date(2026, 9, 10)),
        )

    def test_planilha_com_conta_de_a_continua_funcionando(self):
        resp = self.enviar_planilha(str(self.a.conta.id))

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['imported'], 1)
        importada = Transaction.objects.get(description='Padaria')
        self.assertEqual(
            (importada.user, importada.account, importada.type, importada.amount, importada.date),
            (self.a.usuario, self.a.conta, 'EXPENSE', Decimal('45.00'), date(2026, 9, 10)),
        )

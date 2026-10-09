"""
Gravação linha a linha e resumo da importação (IMPORT-23, IMPORT-25,
IMPORT-27 a IMPORT-31, IMPORT-34).

Cada linha grava num savepoint próprio: uma falha de banco rejeita só a
linha. A resposta é sempre 200 com o resumo quando o arquivo é aceito.
"""
import json
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.db import connection

from accounts.models import Account
from accounts.saldo import calcular
from transactions.models import Category, Tag, Transaction

from .base import (
    MAPEAMENTO, URL_OFX, URL_PLANILHA, ImportacaoTestCase, arquivo_csv, arquivo_ofx, arquivo_xlsx,
    transacao_ofx,
)

CABECALHO = ['Data', 'Descrição', 'Valor']
CHAVES_DO_RESUMO = {'total', 'imported', 'ignored', 'rejected', 'suggested', 'batch_id', 'rejected_rows'}


class GravacaoTestCase(ImportacaoTestCase):

    def importar(self, arquivo, mapeamento=MAPEAMENTO, conta=None, import_type='INCOME_EXPENSE', mapa=None):
        dados = {'file': arquivo, 'mapping': json.dumps(mapeamento), 'import_type': import_type}
        if conta is not False:
            dados['account_id'] = str((conta or self.a.conta).id)
        if mapa:
            dados['account_mapping'] = json.dumps(mapa)
        return self.client.post(URL_PLANILHA, dados, format='multipart')

    def importar_ofx(self, arquivo, conta=None):
        return self.client.post(
            URL_OFX, {'file': arquivo, 'account_id': str((conta or self.a.conta).id)}, format='multipart',
        )

    def assert_resumo(self, resp, total, imported, ignored, rejected_rows=()):
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), CHAVES_DO_RESUMO)
        self.assertEqual(
            (resp.data['total'], resp.data['imported'], resp.data['ignored'], resp.data['rejected'],
             resp.data['suggested']),
            (total, imported, ignored, len(rejected_rows), 0),
        )
        self.assertEqual(resp.data['rejected_rows'], [{'line': l, 'reason': r} for l, r in rejected_rows])
        uuid.UUID(resp.data['batch_id'])

    def do_lote(self, resp):
        return Transaction.objects.filter(import_batch=resp.data['batch_id'])

    def saldo(self, conta):
        conta = Account.objects.get(pk=conta.pk)
        self.assertEqual(conta.balance, calcular(conta))  # SALDO-01
        return conta.balance


class ResultadoTests(GravacaoTestCase):

    def test_grava_as_validas_e_lista_as_rejeitadas_com_o_numero_do_arquivo(self):
        """Independent Test de IMPORT-27 a IMPORT-33: 10 linhas, rejeitadas 3, 6 e 9."""
        linhas = [CABECALHO]
        for numero in range(2, 12):
            linhas.append([f'{numero:02d}/09/2026', f'Linha {numero}', f'-{numero},00'])
        linhas[3 - 1][0] = '31/02/2026'
        linhas[6 - 1][0] = 'ontem'
        linhas[9 - 1][1] = 'x' * 300

        resp = self.importar(arquivo_csv(linhas))

        self.assert_resumo(resp, 10, 7, 0, [
            (3, 'Data inválida'), (6, 'Data inválida'), (9, 'Texto longo demais: descrição'),
        ])
        gravadas = self.do_lote(resp)
        self.assertEqual(
            sorted(gravadas.values_list('description', flat=True)),
            sorted(f'Linha {n}' for n in (2, 4, 5, 7, 8, 10, 11)),
        )
        linha_2 = gravadas.get(description='Linha 2')
        self.assertEqual(
            (linha_2.user, linha_2.account, linha_2.type, linha_2.status, linha_2.amount, linha_2.date, linha_2.fitid),
            (self.a.usuario, self.a.conta, 'EXPENSE', 'COMPLETED', Decimal('2.00'), date(2026, 9, 2), None),
        )
        # 1000 - (2 + 4 + 5 + 7 + 8 + 10 + 11)
        self.assertEqual(self.saldo(self.a.conta), Decimal('953.00'))

    def test_erro_de_banco_rejeita_so_a_linha_sem_o_texto_da_excecao(self):
        """IMPORT-28: a linha 5 falha no banco; as outras ficam e a categoria dela não é reaproveitada."""
        linhas = [CABECALHO + ['Categoria']]
        for numero in range(2, 8):
            linhas.append(['10/09/2026', f'Linha {numero}', '-1,00', 'Nova' if numero >= 5 else ''])
        criar = Transaction.objects.create

        def criar_com_falha(**dados):
            if dados.get('description') == 'Linha 5':
                with connection.cursor() as cursor:
                    cursor.execute('SELECT 1/0')  # erro real do Postgres
            return criar(**dados)

        with patch.object(Transaction.objects, 'create', side_effect=criar_com_falha), \
                self.assertLogs('data_exchange.importacao.gravacao', level='ERROR') as logs:
            resp = self.importar(arquivo_csv(linhas), {**MAPEAMENTO, 'category_column': 'Categoria'})

        self.assert_resumo(resp, 6, 5, 0, [(5, 'Erro ao gravar a linha')])
        self.assertNotIn('division', json.dumps(resp.data))
        # O log registra só a classe da exceção, sem a mensagem nem o
        # traceback, que podem trazer dados da linha (LGPD-21)
        self.assertIn('(DataError)', logs.records[0].getMessage())
        self.assertIsNone(logs.records[0].exc_info)
        self.assertEqual(
            sorted(self.do_lote(resp).values_list('description', flat=True)),
            ['Linha 2', 'Linha 3', 'Linha 4', 'Linha 6', 'Linha 7'],
        )
        # A categoria criada no savepoint desfeito não ficou no cache: a linha 6 criou a dela
        nova = Category.objects.get(user=self.a.usuario, name='Nova')
        self.assertEqual(
            set(self.do_lote(resp).filter(category__isnull=False).values_list('category', flat=True)), {nova.pk},
        )
        self.assertEqual(self.saldo(self.a.conta), Decimal('995.00'))

    def test_reimportar_o_mesmo_arquivo_responde_200_sem_gravar(self):
        """IMPORT-31: tudo já existia, 200 com zero gravadas."""
        linhas = [CABECALHO, ['10/09/2026', 'Café', '-5,00'], ['10/09/2026', 'Café', '-5,00']]
        primeira = self.importar(arquivo_csv(linhas))
        self.assert_resumo(primeira, 2, 2, 0)

        segunda = self.importar(arquivo_csv(linhas))

        self.assert_resumo(segunda, 2, 0, 2)
        self.assertEqual(Transaction.objects.filter(account=self.a.conta, description='Café').count(), 2)
        self.assertEqual(self.saldo(self.a.conta), Decimal('990.00'))

    def test_arquivo_so_com_o_cabecalho_responde_200_com_zeros(self):
        """Edge case: arquivo só com o cabeçalho."""
        self.assert_resumo(self.importar(arquivo_csv([CABECALHO])), 0, 0, 0)

    def test_status_pendente_nao_entra_no_saldo(self):
        """IMPORT-20 e SALDO-01: pendente gravada como pendente; o saldo final segue a regra."""
        mapeamento = {**MAPEAMENTO, 'status_column': 'Situação', 'type_column': 'Tipo'}
        resp = self.importar(arquivo_csv([
            CABECALHO + ['Situação', 'Tipo'],
            ['10/09/2026', 'Aluguel', '1.500', 'Pendente', 'Débito'],
            ['10/09/2026', 'Salário', '3.000,00', 'Pago', 'Crédito'],
        ]), mapeamento)

        self.assert_resumo(resp, 2, 2, 0)
        self.assertEqual(
            sorted(self.do_lote(resp).values_list('description', 'type', 'status', 'amount')),
            [('Aluguel', 'EXPENSE', 'PENDING', Decimal('1500.00')),
             ('Salário', 'INCOME', 'COMPLETED', Decimal('3000.00'))],
        )
        self.assertEqual(self.saldo(self.a.conta), Decimal('4000.00'))


class CategoriasETagsTests(GravacaoTestCase):

    def test_reaproveita_sem_diferenciar_maiusculas_nem_acentos_e_cria_uma_vez(self):
        """IMPORT-23: "alimentação" usa "Alimentação"; a categoria nova é criada uma vez só."""
        alimentacao = Category.objects.create(user=self.a.usuario, name='Alimentação', type='EXPENSE')
        viagem = Tag.objects.create(user=self.a.usuario, name='Viagem')
        mapeamento = {**MAPEAMENTO, 'category_column': 'Categoria', 'subcategory_column': 'Sub',
                      'tags_column': 'Tags'}
        arquivo = arquivo_xlsx([
            CABECALHO + ['Categoria', 'Sub', 'Tags'],
            [date(2026, 9, 10), 'Almoço', -30, 'alimentação', None, 'viagem'],
            [date(2026, 9, 11), 'Jantar', -40, 'ALIMENTACAO', None, 'VIAGEM, trabalho'],
            [date(2026, 9, 12), 'Cinema', -25, 'Lazer novo', 'Filmes', 'Trabalho'],
            [date(2026, 9, 13), 'Show', -50, 'lazer NOVO', 'filmes', None],
        ])

        resp = self.importar(arquivo, mapeamento)

        self.assert_resumo(resp, 4, 4, 0)
        lote = self.do_lote(resp)
        self.assertEqual(set(lote.filter(description__in=['Almoço', 'Jantar']).values_list('category', flat=True)),
                         {alimentacao.pk})
        lazer = Category.objects.get(user=self.a.usuario, name='Lazer novo', parent=None)
        filmes = Category.objects.get(user=self.a.usuario, name='Filmes')
        self.assertEqual((lazer.type, filmes.type, filmes.parent_id), ('EXPENSE', 'EXPENSE', lazer.pk))
        self.assertEqual(Category.objects.filter(user=self.a.usuario, name__iexact='lazer novo').count(), 1)
        self.assertEqual(set(lote.filter(description__in=['Cinema', 'Show']).values_list('category', flat=True)),
                         {filmes.pk})
        trabalho = Tag.objects.get(user=self.a.usuario, name='trabalho')
        self.assertEqual(Tag.objects.filter(user=self.a.usuario, name__iexact='trabalho').count(), 1)
        self.assertEqual(set(lote.get(description='Jantar').tags.all()), {viagem, trabalho})
        self.assertEqual(set(lote.get(description='Cinema').tags.all()), {trabalho})


class TransferenciaTests(GravacaoTestCase):

    def test_transferencia_cria_as_duas_pernas_pelas_regras_do_saldo(self):
        """IMPORT-25 e IMPORT-26: as duas pernas, com o lote; mesma conta é rejeitada."""
        mapeamento = {'date_column': 'Data', 'amount_column': 'Valor', 'description_column': 'Descrição',
                      'source_account_column': 'Origem', 'dest_account_column': 'Destino'}
        resp = self.importar(arquivo_csv([
            ['Data', 'Descrição', 'Valor', 'Origem', 'Destino'],
            ['10/09/2026', 'Reserva', '200,00', 'Banco', 'Corrente A'],
            ['11/09/2026', 'Volta', '200,00', 'Banco', 'Banco'],
        ]), mapeamento, conta=False, import_type='TRANSFER', mapa={'Banco': str(self.a.poupanca.id)})

        self.assert_resumo(resp, 2, 1, 0, [(3, 'Origem e destino iguais')])
        saida = self.do_lote(resp).get(type='TRANSFER_OUT')
        entrada = self.do_lote(resp).get(type='TRANSFER_IN')
        self.assertEqual(
            (saida.account, entrada.account, saida.transfer_id, saida.amount, entrada.amount, saida.date,
             saida.status, entrada.status, saida.description),
            (self.a.poupanca, self.a.conta, entrada.transfer_id, Decimal('200.00'), Decimal('200.00'),
             date(2026, 9, 10), 'COMPLETED', 'COMPLETED', 'Reserva'),
        )
        self.assertIsNotNone(saida.transfer_id)
        self.assertEqual(self.saldo(self.a.poupanca), Decimal('-200.00'))
        self.assertEqual(self.saldo(self.a.conta), Decimal('1200.00'))


class OfxTests(GravacaoTestCase):

    def test_ofx_grava_com_fitid_e_reimportar_ignora(self):
        """IMPORT-29, IMPORT-30, IMPORT-34: FITID gravado; zero rejeita na posição; reimportar ignora."""
        def arquivo():
            return arquivo_ofx(
                transacao_ofx('A1', '20260910', '-45.00', memo='Padaria'),
                transacao_ofx('A2', '20260911', '0.00', memo='Tarifa zerada'),
                transacao_ofx('A3', '20260912', '100.00', favorecido='Cliente'),
            )

        resp = self.importar_ofx(arquivo())

        self.assert_resumo(resp, 3, 2, 0, [(2, 'Valor inválido')])
        self.assertEqual(
            sorted(self.do_lote(resp).values_list('fitid', 'type', 'amount', 'description')),
            [('A1', 'EXPENSE', Decimal('45.00'), 'Padaria'), ('A3', 'INCOME', Decimal('100.00'), 'Cliente')],
        )
        self.assertEqual(self.saldo(self.a.conta), Decimal('1055.00'))

        Transaction.objects.filter(fitid='A1').update(description='Padaria (editada)')
        self.assert_resumo(self.importar_ofx(arquivo()), 3, 0, 2, [(2, 'Valor inválido')])
        self.assertEqual(Transaction.objects.filter(account=self.a.conta).count(), 2)

    def test_ofx_ilegivel_recebe_400(self):
        """IMPORT-06: a rota do OFX usa a mesma leitura."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        resp = self.importar_ofx(SimpleUploadedFile('extrato.ofx', b'lixo'))
        self.assert_recusado(resp, 'Não foi possível ler o arquivo.')

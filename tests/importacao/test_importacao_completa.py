"""
Rotas da importação completa (IMPCOMP-13, IMPCOMP-23, IMPCOMP-24,
IMPCOMP-28 a IMPCOMP-31, IMPCOMP-34 a IMPCOMP-36, IMPCOMP-45, IMPCOMP-47,
IMPCOMP-48, IMPCOMP-50 a IMPCOMP-52).

`POST /api/import/analise/` devolve o plano, as linhas com o estado e o
resumo sem gravar nada; `POST /api/import/` cria as contas do plano, grava
todas as abas usadas e acerta o saldo das contas criadas.
"""
import json
import uuid
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache

from accounts.models import Account
from core import travas
from tests.permissoes.base import fechar, liberacao_de_testes
from transactions.models import Tag, Transaction

from .base import ImportacaoTestCase, arquivo_csv
from .mobills import NOMES, arquivo_mobills, lancamentos, transferencias

URL_ANALISE = '/api/import/analise/'
URL_IMPORTACAO = '/api/import/'
CONTA_NAO_ENCONTRADA = 'Conta não encontrada.'
BLOQUEADO = 'Este recurso não está disponível no seu plano.'


def dinheiro(valor):
    return str(Decimal(str(valor)).quantize(Decimal('0.01')))


def saldo_informado(indice):
    return dinheiro(Decimal('1000.00') + indice * Decimal('111.11') - Decimal('3000.00'))


class ImportacaoCompletaTestCase(ImportacaoTestCase):

    def setUp(self):
        super().setUp()
        cache.clear()
        travas.invalidar()
        self.addCleanup(travas.invalidar)
        liberacao_de_testes(False)

    def enviar(self, url, arquivo, plano=None, bruto=None):
        corpo = {'file': arquivo}
        if plano is not None:
            corpo['plano'] = json.dumps(plano)
        if bruto is not None:
            corpo['plano'] = bruto
        return self.client.post(url, corpo, format='multipart')

    def analisar(self, arquivo, plano=None, **kwargs):
        return self.enviar(URL_ANALISE, arquivo, plano, **kwargs)

    def importar(self, arquivo, plano=None, **kwargs):
        return self.enviar(URL_IMPORTACAO, arquivo, plano, **kwargs)

    def plano_de_criacao(self):
        """As 11 contas do Mobills marcadas para criar, cada uma com um saldo atual."""
        return {'contas': {
            nome: {'acao': 'criar', 'nome': nome, 'tipo': 'CHECKING', 'saldo_atual': saldo_informado(i),
                   'institution': None, 'color': None}
            for i, nome in enumerate(NOMES)
        }}

    def gravados(self):
        return (Account.objects.count(), Transaction.objects.count())

    def assert_400(self, resp, corpo):
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data, corpo)


class AnaliseTests(ImportacaoCompletaTestCase):

    def test_analise_do_mobills_devolve_plano_linhas_e_resumo_sem_gravar(self):
        """IMPCOMP-13, IMPCOMP-31 e IMPCOMP-37: tudo válido, sem gravar conta nem transação."""
        antes = self.gravados()
        resp = self.analisar(arquivo_mobills())

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.gravados(), antes)
        self.assertEqual(set(resp.data), {'plano', 'linhas', 'resumo'})
        plano = resp.data['plano']
        self.assertEqual(plano['modelo'], 'MOBILLS')
        self.assertEqual(
            [(a['nome'], a['papel']) for a in plano['abas']],
            [('Receitas e Despesas', 'RECEITAS_DESPESAS'), ('Despesas', 'IGNORAR'),
             ('Receitas', 'IGNORAR'), ('Transferências', 'TRANSFERENCIAS')],
        )
        self.assertEqual(list(plano['contas']), NOMES)

        receitas = [l[2] for l in lancamentos() if l[2] > 0]
        despesas = [-l[2] for l in lancamentos() if l[2] < 0]
        self.assertEqual(resp.data['resumo'], {
            'validas': 66, 'rejeitadas': 0, 'repetidas': 0, 'excluidas': 0,
            # A "Carteira" do cadastro é vinculada; as outras 10 são novas
            'contas_novas': 10,
            'receitas': {'quantidade': 15, 'valor': dinheiro(sum(receitas))},
            'despesas': {'quantidade': 42, 'valor': dinheiro(sum(despesas))},
            'transferencias': {'quantidade': 9, 'valor': dinheiro(sum(t[3] for t in transferencias()))},
            'summary_rows': 2,
        })
        self.assertEqual(len(resp.data['linhas']), 66)
        self.assertEqual(resp.data['linhas'][0], {
            'chave': 'Receitas e Despesas:2', 'aba': 'Receitas e Despesas', 'numero': 2, 'estado': 'VALIDA',
            'motivo': None, 'conta': 'Nubank', 'destino': None, 'data': '2026-08-01',
            'descricao': 'Lançamento 1', 'tipo': 'INCOME', 'categoria': 'Salário', 'subcategoria': None,
            'valor': '1000.00', 'situacao': 'COMPLETED', 'tags': [],
        })
        transferencia = resp.data['linhas'][57]
        self.assertEqual(
            (transferencia['chave'], transferencia['tipo'], transferencia['conta'], transferencia['destino'],
             transferencia['valor'], transferencia['descricao']),
            ('Transferências:2', 'TRANSFER', 'Nubank', 'Itaú', '50.25', 'Transferência via Importação'),
        )

    def test_rejeitada_corrigida_excluida_e_restaurada(self):
        """IMPCOMP-31 a IMPCOMP-34 e IMPCOMP-42: estados e resumo seguem o plano de cada análise."""
        arquivo = lambda: arquivo_csv([  # noqa: E731
            ['Data', 'Descrição', 'Valor', 'Conta'],
            ['10/09/2026', 'Padaria', '-4,50', 'Corrente A'],
            ['31/02/2026', 'Mercado', '-80,00', 'Corrente A'],
            ['12/09/2026', 'Cinema', '-20,00', 'Corrente A'],
        ], nome='setembro.csv')

        resp = self.analisar(arquivo())
        estados = [(l['chave'], l['estado'], l['motivo']) for l in resp.data['linhas']]
        self.assertEqual(estados, [
            ('setembro.csv:2', 'VALIDA', None), ('setembro.csv:3', 'REJEITADA', 'Data inválida'),
            ('setembro.csv:4', 'VALIDA', None),
        ])
        self.assertEqual(resp.data['linhas'][1]['data'], '31/02/2026')
        self.assertEqual(resp.data['linhas'][1]['valor'], '-80,00')

        plano = {'linhas': {'setembro.csv:3': {'data': '28/02/2026'}, 'setembro.csv:4': {'excluir': True}}}
        resp = self.analisar(arquivo(), plano)
        estados = [(l['chave'], l['estado'], l['data']) for l in resp.data['linhas']]
        self.assertEqual(estados, [
            ('setembro.csv:2', 'VALIDA', '2026-09-10'), ('setembro.csv:3', 'VALIDA', '2026-02-28'),
            ('setembro.csv:4', 'EXCLUIDA', '2026-09-12'),
        ])
        resumo = resp.data['resumo']
        self.assertEqual((resumo['validas'], resumo['rejeitadas'], resumo['excluidas']), (2, 0, 1))
        self.assertEqual(resumo['despesas'], {'quantidade': 2, 'valor': '84.50'})
        self.assertEqual(resp.data['plano']['linhas'], plano['linhas'])

        # Restaurar é tirar a chave do plano
        resp = self.analisar(arquivo(), {'linhas': {'setembro.csv:3': {'data': '28/02/2026'}}})
        self.assertEqual([l['estado'] for l in resp.data['linhas']], ['VALIDA', 'VALIDA', 'VALIDA'])

    def test_plano_editado_muda_papel_e_colunas_da_analise(self):
        """IMPCOMP-14: o papel e as colunas do plano são usados na análise."""
        plano = {'abas': [{'nome': 'Transferências', 'papel': 'IGNORAR'}]}
        resp = self.analisar(arquivo_mobills(), plano)
        self.assertEqual(resp.data['resumo']['transferencias']['quantidade'], 0)
        self.assertEqual(resp.data['resumo']['validas'], 57)


class ImportacaoTests(ImportacaoCompletaTestCase):

    def test_importacao_do_mobills_cria_as_contas_grava_tudo_e_acerta_os_saldos(self):
        """IMPCOMP-25, IMPCOMP-26, IMPCOMP-30, IMPCOMP-45 e IMPCOMP-47."""
        resp = self.importar(arquivo_mobills(), self.plano_de_criacao())

        self.assertEqual(resp.status_code, 200, resp.data)
        dados = resp.data
        self.assertEqual(
            (dados['total'], dados['imported'], dados['ignored'], dados['rejected'], dados['rejected_rows']),
            (66, 66, 0, 0, []),
        )
        self.assertEqual(dados['by_sheet'], {
            'Receitas e Despesas': {'imported': 57, 'ignored': 0, 'rejected': 0},
            'Transferências': {'imported': 9, 'ignored': 0, 'rejected': 0},
        })
        self.assertEqual((dados['summary_rows'], dados['excluded']), (2, 0))
        self.assertEqual([c['name'] for c in dados['accounts_created']], NOMES)

        lote = Transaction.objects.filter(import_batch=dados['batch_id'])
        self.assertEqual(lote.filter(type__in=('INCOME', 'EXPENSE')).count(), 57)
        self.assertEqual(lote.filter(type='TRANSFER_OUT').count(), 9)
        for i, criada in enumerate(dados['accounts_created']):
            conta = Account.objects.get(pk=criada['id'])
            self.assertEqual(
                (conta.user, conta.name, conta.type, conta.balance),
                (self.a.usuario, NOMES[i], 'CHECKING', Decimal(saldo_informado(i))),
            )

    def test_reimportar_com_as_contas_vinculadas_grava_zero(self):
        """IMPCOMP-48 e IMPCOMP-31: a segunda importação ignora tudo, e a análise marca tudo como repetida."""
        primeira = self.importar(arquivo_mobills(), self.plano_de_criacao()).data
        vinculadas = {'contas': {c['name']: {'acao': 'vincular', 'id': c['id']} for c in primeira['accounts_created']}}
        antes = self.gravados()

        analise = self.analisar(arquivo_mobills(), vinculadas).data
        self.assertEqual({l['estado'] for l in analise['linhas']}, {'REPETIDA'})
        self.assertEqual((analise['resumo']['repetidas'], analise['resumo']['contas_novas']), (66, 0))

        segunda = self.importar(arquivo_mobills(), vinculadas)
        self.assertEqual(segunda.status_code, 200, segunda.data)
        self.assertEqual(
            (segunda.data['imported'], segunda.data['ignored'], segunda.data['rejected'], segunda.data['accounts_created']),
            (0, 66, 0, []),
        )
        self.assertEqual(segunda.data['by_sheet']['Transferências'], {'imported': 0, 'ignored': 9, 'rejected': 0})
        self.assertEqual(self.gravados(), antes)

    def test_dois_nomes_vinculados_a_mesma_conta(self):
        """IMPCOMP-23: as linhas dos dois nomes vão para a conta escolhida."""
        arquivo = arquivo_csv([
            ['Data', 'Descrição', 'Valor', 'Conta'],
            ['10/09/2026', 'Padaria', '-4,50', 'Banco X'],
            ['11/09/2026', 'Mercado', '-80,00', 'Banco Y'],
        ])
        plano = {'contas': {nome: {'acao': 'vincular', 'id': str(self.a.conta.pk)} for nome in ('Banco X', 'Banco Y')}}
        resp = self.importar(arquivo, plano)

        self.assertEqual((resp.data['imported'], resp.data['accounts_created']), (2, []))
        lote = Transaction.objects.filter(import_batch=resp.data['batch_id'])
        self.assertEqual({t.account_id for t in lote}, {self.a.conta.pk})
        self.a.conta.refresh_from_db()
        self.assertEqual(self.a.conta.balance, Decimal('915.50'))

    def test_linha_excluida_nao_e_gravada_e_rejeitada_traz_a_aba(self):
        """IMPCOMP-34, IMPCOMP-21 e IMPCOMP-47: excluída fora da gravação; rejeitada com a aba."""
        arquivo = arquivo_csv([
            ['Data', 'Descrição', 'Valor', 'Conta'],
            ['10/09/2026', 'Padaria', '-4,50', 'Corrente A'],
            ['11/09/2026', 'Mercado', '-80,00', 'Corrente A'],
            ['xx', 'Cinema', '-20,00', 'Corrente A'],
        ], nome='setembro.csv')
        resp = self.importar(arquivo, {'linhas': {'setembro.csv:3': {'excluir': True}}})

        self.assertEqual(
            (resp.data['total'], resp.data['imported'], resp.data['rejected'], resp.data['excluded']), (2, 1, 1, 1),
        )
        self.assertEqual(resp.data['rejected_rows'], [{'line': 4, 'reason': 'Data inválida', 'sheet': 'setembro.csv'}])
        self.assertEqual(resp.data['by_sheet'], {'setembro.csv': {'imported': 1, 'ignored': 0, 'rejected': 1}})
        self.assertFalse(Transaction.objects.filter(description='Mercado').exists())

    def test_falha_depois_de_criar_as_contas_desfaz_tudo(self):
        """IMPCOMP-29: uma falha que sobe até a view não deixa conta nem transação."""
        antes = self.gravados()
        with patch('data_exchange.importacao.completa.acertar_saldos', side_effect=RuntimeError('falha')):
            with self.assertRaises(RuntimeError):
                self.importar(arquivo_mobills(), self.plano_de_criacao())
        self.assertEqual(self.gravados(), antes)


class LimiteETravasTests(ImportacaoCompletaTestCase):

    def test_contas_alem_do_limite_recusam_sem_gravar(self):
        """IMPCOMP-27: com limite de 5 contas, as 11 a criar recebem 403 e nada é gravado."""
        fechar('limite_contas', limite=5)
        antes = self.gravados()
        resp = self.importar(arquivo_mobills(), self.plano_de_criacao())

        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(
            resp.data,
            {'detail': 'Você atingiu o limite do seu plano.', 'code': 'plan_limit_reached',
             'feature': 'limite_contas', 'limit': 5},
        )
        self.assertEqual(self.gravados(), antes)

    def test_importacao_planilha_travada_recusa_analise_e_importacao(self):
        """IMPCOMP-50: 403 plan_locked nas duas rotas."""
        fechar('importacao_planilha')
        for url in (URL_ANALISE, URL_IMPORTACAO):
            with self.subTest(url=url):
                resp = self.enviar(url, arquivo_mobills())
                self.assertEqual(resp.status_code, 403)
                self.assertEqual(resp.data, {'detail': BLOQUEADO, 'code': 'plan_locked', 'feature': 'importacao_planilha'})

    def test_tags_travadas_importam_sem_tags_tambem_as_corrigidas(self):
        """IMPCOMP-51: a coluna de tags e as tags das correções ficam de fora."""
        fechar('tags')
        arquivo = lambda: arquivo_csv([  # noqa: E731
            ['Data', 'Descrição', 'Valor', 'Conta', 'Tags'],
            ['10/09/2026', 'Padaria', '-4,50', 'Corrente A', 'casa'],
            ['11/09/2026', 'Mercado', '-80,00', 'Corrente A', ''],
        ])
        plano = {'linhas': {'extrato.csv:3': {'tags': ['viagem']}}}

        analise = self.analisar(arquivo(), plano).data
        self.assertNotIn('tags_column', analise['plano']['abas'][0]['colunas'])
        self.assertEqual([l['tags'] for l in analise['linhas']], [[], []])

        resp = self.importar(arquivo(), plano)
        self.assertEqual(resp.data['imported'], 2)
        self.assertFalse(Tag.objects.filter(user=self.a.usuario).exists())
        self.assertFalse(Transaction.tags.through.objects.filter(transaction__user=self.a.usuario).exists())


class PlanoInvalidoTests(ImportacaoCompletaTestCase):

    def test_conta_vinculada_de_outro_usuario_inexistente_ou_excluida(self):
        """IMPCOMP-24: 400 com "Conta não encontrada." na conta do plano, sem gravar nada."""
        excluida = Account.objects.create(user=self.a.usuario, name='Antiga', type='CHECKING', is_active=False)
        for conta_id in (str(self.b.conta.pk), str(uuid.uuid4()), str(excluida.pk), 'abc', None):
            with self.subTest(conta_id=conta_id):
                antes = self.gravados()
                resp = self.importar(arquivo_mobills(), {'contas': {'Nubank': {'acao': 'vincular', 'id': conta_id}}})
                self.assert_400(resp, {'plano': {'contas': {'Nubank': {'id': [CONTA_NAO_ENCONTRADA]}}}})
                self.assertEqual(self.gravados(), antes)
        resp = self.analisar(arquivo_mobills(), {'contas': {'Nubank': {'acao': 'vincular', 'id': str(self.b.conta.pk)}}})
        self.assert_400(resp, {'plano': {'contas': {'Nubank': {'id': [CONTA_NAO_ENCONTRADA]}}}})

    def test_conta_a_criar_invalida_recebe_o_erro_no_campo(self):
        """IMPCOMP-28: nome vazio ou longo, tipo fora da lista, saldo ilegível ou com três casas."""
        casos = {
            'nome': {'nome': ''},
            'tipo': {'tipo': 'CREDIT_CARD'},
            'saldo_atual': {'saldo_atual': 'abc'},
        }
        casos_extras = [('nome', {'nome': 'x' * 101}), ('saldo_atual', {'saldo_atual': '10.123'})]
        base = {'acao': 'criar', 'nome': 'Nubank', 'tipo': 'CHECKING', 'saldo_atual': '-15.30'}
        for campo, troca in list(casos.items()) + casos_extras:
            with self.subTest(campo=campo, troca=troca):
                antes = self.gravados()
                resp = self.importar(arquivo_mobills(), {'contas': {'Nubank': {**base, **troca}}})
                self.assertEqual(resp.status_code, 400, resp.data)
                self.assertEqual(list(resp.data), ['plano'])
                self.assertEqual(list(resp.data['plano']['contas']['Nubank']), [campo])
                self.assertEqual(self.gravados(), antes)

        sem_campos = self.importar(arquivo_mobills(), {'contas': {'Nubank': {'acao': 'criar'}}})
        self.assertEqual(set(sem_campos.data['plano']['contas']['Nubank']), {'nome', 'tipo', 'saldo_atual'})

    def test_json_malformado_e_formato_errado(self):
        """IMPCOMP-36: 400 no campo `plano`."""
        self.assert_400(self.analisar(arquivo_mobills(), bruto='{abas: '), {'plano': ['Plano inválido: JSON malformado.']})
        self.assert_400(self.importar(arquivo_mobills(), bruto='[1'), {'plano': ['Plano inválido: JSON malformado.']})

        resp = self.analisar(arquivo_mobills(), {'abas': [{'nome': 'Despesas', 'papel': 'OUTRO'}]})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(list(resp.data['plano']['abas'][0]), ['papel'])

        resp = self.analisar(arquivo_mobills(), {'abas': [{'nome': 'Despesas', 'papel': 'IGNORAR', 'colunas': {'cor': 'Data'}}]})
        self.assert_400(resp, {'plano': {'abas': {0: {'colunas': ['Campo desconhecido: cor.']}}}})

        resp = self.analisar(arquivo_mobills(), {'linhas': {'Despesas:2': {'excluir': 'talvez', 'tags': 5}}})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(set(resp.data['plano']['linhas']['Despesas:2']), {'excluir', 'tags'})

        resp = self.analisar(arquivo_mobills(), [1, 2])
        self.assertEqual(resp.status_code, 400)
        self.assertIn('plano', resp.data)

    def test_chave_de_linha_inexistente(self):
        """IMPCOMP-35: 400 "Linha inexistente no arquivo: <chave>.", também na importação, sem gravar."""
        antes = self.gravados()
        for url in (URL_ANALISE, URL_IMPORTACAO):
            with self.subTest(url=url):
                resp = self.enviar(url, arquivo_mobills(), {'linhas': {'Receitas e Despesas:999': {'excluir': True}}})
                self.assert_400(resp, {'plano': ['Linha inexistente no arquivo: Receitas e Despesas:999.']})
        self.assertEqual(self.gravados(), antes)

    def test_arquivo_ausente_e_coluna_do_plano_inexistente(self):
        """IMPORT-06 e IMPCOMP-22 nas rotas: sem arquivo, e coluna do plano fora do cabeçalho."""
        self.assert_400(self.client.post(URL_ANALISE, {}, format='multipart'), {'file': ['Arquivo não enviado.']})
        plano = {'abas': [{'nome': 'Transferências', 'papel': 'TRANSFERENCIAS', 'colunas': {
            'date_column': 'Data', 'source_account_column': 'Conta origem', 'dest_account_column': 'Conta destino',
            'amount_column': 'Valor', 'description_column': 'Descrição da transferência',
        }}]}
        antes = self.gravados()
        resp = self.importar(arquivo_mobills(), plano)
        self.assert_400(resp, {'file': ['Colunas não encontradas no arquivo: Descrição da transferência.']})
        self.assertEqual(self.gravados(), antes)


class LogsTests(ImportacaoCompletaTestCase):

    def test_logs_nao_levam_nomes_de_conta_descricoes_nem_valores(self):
        """IMPCOMP-52: só contagens e ids na análise e na importação."""
        with self.assertLogs('data_exchange.importacao', level='INFO') as logs:
            self.analisar(arquivo_mobills())
            self.importar(arquivo_mobills(), self.plano_de_criacao())
        texto = '\n'.join(logs.output)
        self.assertEqual(len(logs.output), 2)
        proibidos = NOMES + [l[1] for l in lancamentos()] + ['1000', '50.25', 'Salário', 'Mercado']
        proibidos += [saldo_informado(i) for i in range(len(NOMES))]
        for proibido in proibidos:
            self.assertNotIn(proibido, texto)

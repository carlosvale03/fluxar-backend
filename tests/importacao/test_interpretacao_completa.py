"""
Interpretação da importação completa (IMPCOMP-15 a IMPCOMP-22, IMPCOMP-32 a
IMPCOMP-34).

Rodapé "Total" pulado, situações pendentes ampliadas, entrada e saída,
transferência numa aba de receitas e despesas, rejeição com a aba e
correções e exclusões de linha do plano.
"""
import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

from rest_framework.exceptions import ValidationError

from accounts.models import Account
from data_exchange.importacao.deteccao import detectar_plano
from data_exchange.importacao.gravacao import Gravacao
from data_exchange.importacao.interpretacao import (
    LinhaImportada, Rejeicao, ResolvedorDeContas, interpretar_aba,
)
from data_exchange.importacao.leitura import ler_abas

from .base import URL_PREFLIGHT, ImportacaoTestCase, arquivo_csv, arquivo_xlsx
from .mobills import NOMES, arquivo_mobills

CABECALHO = ['Data', 'Descrição', 'Valor', 'Conta', 'Situação', 'Categoria', 'Tags']


class InterpretacaoCompletaTestCase(ImportacaoTestCase):

    def contas(self):
        return {'Corrente A': self.a.conta, 'Poupança A': self.a.poupanca}

    def interpretar(self, linhas, nome='Extrato', correcoes=None, plano=None, tags_liberadas=True, indice=0):
        """Interpreta a aba `indice` de um XLSX com uma aba `nome` e as `linhas` (a primeira é o cabeçalho)."""
        abas = ler_abas(arquivo_xlsx(abas=[(nome, linhas)]))
        plano_da_aba = (plano or detectar_plano(abas, self.a.usuario)['abas'])[indice]
        return interpretar_aba(
            abas[indice], plano_da_aba, ResolvedorDeContas(self.contas()), correcoes or {}, tags_liberadas,
        )

    def resultados(self, linhas, **kwargs):
        interpretadas, _ = self.interpretar(linhas, **kwargs)
        return [linha.resultado for linha in interpretadas]


class RodapeTests(InterpretacaoCompletaTestCase):

    def test_linha_total_sem_descricao_e_conta_e_pulada_e_contada(self):
        """IMPCOMP-15: "Total (2)" é resumo; um lançamento "Total" com conta é importado."""
        interpretadas, resumos = self.interpretar([
            ['Descrição', 'Data', 'Valor', 'Conta'],
            ['Padaria', '10/09/2026', -4.5, 'Corrente A'],
            ['Total da fatura', '11/09/2026', -100, 'Corrente A'],
            [None, None, None, None],
            ['Total (2)', None, -104.5, None],
        ])
        # A primeira célula é a descrição, preenchida: nenhuma linha é resumo
        self.assertEqual(resumos, 0)
        self.assertEqual([l.chave for l in interpretadas], ['Extrato:2', 'Extrato:3', 'Extrato:5'])
        total = interpretadas[1].resultado
        self.assertIsInstance(total, LinhaImportada)
        self.assertEqual((total.descricao, total.valor, total.tipo), ('Total da fatura', Decimal('100.00'), 'EXPENSE'))

        interpretadas, resumos = self.interpretar([
            CABECALHO,
            ['10/09/2026', 'Padaria', -4.5, 'Corrente A', 'Paga', None, None],
            ['Total', 'Total', -100, 'Corrente A', 'Paga', None, None],
            [None] * 7,
            ['Total (2)', None, -104.5, None, None, None, None],
        ])
        # Só o rodapé é pulado; a linha "Total" com descrição e conta segue as regras comuns
        self.assertEqual(resumos, 1)
        self.assertEqual([l.chave for l in interpretadas], ['Extrato:2', 'Extrato:3'])
        self.assertEqual(interpretadas[1].resultado, Rejeicao(3, 'Data inválida', 'Extrato'))

    def test_arquivo_do_mobills_nao_tem_rejeicao_por_total_nem_por_situacao(self):
        """IMPCOMP-15 e IMPCOMP-17: 57 receitas e despesas e 9 transferências válidas, um rodapé por aba."""
        abas = ler_abas(arquivo_mobills())
        plano = detectar_plano(abas, self.a.usuario)
        provisorias = {nome: Account(pk=uuid4(), user=self.a.usuario, name=nome) for nome in NOMES}
        resolvedor = ResolvedorDeContas(provisorias)

        lancamentos, resumos_1 = interpretar_aba(abas[0], plano['abas'][0], resolvedor, {})
        transferencias, resumos_4 = interpretar_aba(abas[3], plano['abas'][3], resolvedor, {})

        self.assertEqual((resumos_1, resumos_4), (1, 1))
        self.assertEqual(len(lancamentos), 57)
        self.assertEqual(len(transferencias), 9)
        todas = [l.resultado for l in lancamentos + transferencias]
        self.assertEqual([r for r in todas if isinstance(r, Rejeicao)], [])
        self.assertEqual({r.status for r in todas}, {'COMPLETED'})
        self.assertEqual({r.tipo for r in todas}, {'INCOME', 'EXPENSE', 'TRANSFER'})
        primeira = transferencias[0].resultado
        self.assertEqual(
            (primeira.conta.name, primeira.destino.name, primeira.valor, primeira.data, primeira.aba),
            ('Nubank', 'Itaú', Decimal('50.25'), date(2026, 9, 1), 'Transferências'),
        )


class SituacaoTests(InterpretacaoCompletaTestCase):

    def test_situacoes_pendentes_e_efetivadas(self):
        """IMPCOMP-16 e IMPCOMP-17: os textos pendentes sem maiúsculas e acentos; o resto é efetivada."""
        situacoes = {
            'Paga': 'COMPLETED', 'Recebida': 'COMPLETED', None: 'COMPLETED', 'pago': 'COMPLETED',
            'Não paga': 'PENDING', 'NAO PAGA': 'PENDING', 'não  paga': 'PENDING', 'A pagar': 'PENDING',
            'a receber': 'PENDING', 'Agendada': 'PENDING', 'PENDENTE': 'PENDING', 'pending': 'PENDING',
        }
        linhas = [CABECALHO] + [
            ['10/09/2026', 'Conta de luz', -80, 'Corrente A', situacao, None, None] for situacao in situacoes
        ]
        resultados = self.resultados(linhas)
        self.assertEqual([r.status for r in resultados], list(situacoes.values()))


class EntradaESaidaTests(InterpretacaoCompletaTestCase):

    CABECALHO = ['Data', 'Histórico', 'Entrada', 'Saída', 'Banco']

    def test_entrada_vira_receita_e_saida_vira_despesa(self):
        """IMPCOMP-18: a coluna preenchida define o tipo, com o valor sem sinal."""
        receita, despesa, texto = self.resultados([
            self.CABECALHO,
            ['10/09/2026', 'Salário', 1500, None, 'Corrente A'],
            ['11/09/2026', 'Mercado', None, 80.5, 'Corrente A'],
            ['12/09/2026', 'Estorno', '-12,30', '', 'Poupança A'],
        ])
        self.assertEqual((receita.tipo, receita.valor, receita.descricao), ('INCOME', Decimal('1500.00'), 'Salário'))
        self.assertEqual((despesa.tipo, despesa.valor), ('EXPENSE', Decimal('80.50')))
        self.assertEqual((texto.tipo, texto.valor, texto.conta), ('INCOME', Decimal('12.30'), self.a.poupanca))

    def test_entrada_e_saida_juntas_ou_nenhuma_rejeitam(self):
        """IMPCOMP-19: as duas preenchidas ou nenhuma rejeitam com "Valor inválido"."""
        resultados = self.resultados([
            self.CABECALHO,
            ['10/09/2026', 'Duas', 10, 20, 'Corrente A'],
            ['11/09/2026', 'Nenhuma', None, None, 'Corrente A'],
        ])
        self.assertEqual(resultados, [
            Rejeicao(2, 'Valor inválido', 'Extrato'), Rejeicao(3, 'Valor inválido', 'Extrato'),
        ])


class TransferenciaNaAbaTests(InterpretacaoCompletaTestCase):

    def test_tipo_transferencia_com_destino_vira_transferencia(self):
        """IMPCOMP-20: da conta da linha para a conta de destino, com o valor sem sinal."""
        transferencia, despesa = self.resultados([
            ['Data', 'Descrição', 'Valor', 'Conta', 'Tipo', 'Destino'],
            ['10/09/2026', 'Reserva', -200, 'Corrente A', 'Transferência', 'Poupança A'],
            ['11/09/2026', 'Padaria', -4.5, 'Corrente A', 'Despesa', None],
        ])
        self.assertEqual(
            (transferencia.tipo, transferencia.conta, transferencia.destino, transferencia.valor,
             transferencia.descricao, transferencia.aba),
            ('TRANSFER', self.a.conta, self.a.poupanca, Decimal('200.00'), 'Reserva', 'Extrato'),
        )
        self.assertEqual(despesa.tipo, 'EXPENSE')

    def test_tipo_transferencia_sem_coluna_de_destino_e_tipo_desconhecido(self):
        """IMPCOMP-20 com IMPORT-17: sem destino mapeado, a linha segue a regra do tipo desconhecido."""
        resultados = self.resultados([
            ['Data', 'Descrição', 'Valor', 'Conta', 'Tipo'],
            ['10/09/2026', 'Reserva', -200, 'Corrente A', 'Transferência'],
        ])
        self.assertEqual(resultados, [Rejeicao(2, 'Tipo desconhecido: Transferência', 'Extrato')])


class RejeicaoComAbaTests(InterpretacaoCompletaTestCase):

    def test_rejeicao_traz_a_aba_o_numero_e_o_motivo(self):
        """IMPCOMP-21: na interpretação e no resumo da gravação."""
        interpretadas, _ = self.interpretar([
            CABECALHO,
            ['10/09/2026', 'Padaria', -4.5, 'Corrente A', 'Paga', None, None],
            ['31/02/2026', 'Mercado', -10, 'Corrente A', 'Paga', None, None],
            ['12/09/2026', 'Cinema', -20, 'Itaú', 'Paga', None, None],
        ], nome='Setembro')
        resultados = [l.resultado for l in interpretadas]
        self.assertEqual(resultados[1:], [
            Rejeicao(3, 'Data inválida', 'Setembro'), Rejeicao(4, 'Conta não mapeada: Itaú', 'Setembro'),
        ])

        resumo = Gravacao(self.a.usuario).importar(resultados)
        self.assertEqual(resumo['rejected_rows'], [
            {'line': 3, 'reason': 'Data inválida', 'sheet': 'Setembro'},
            {'line': 4, 'reason': 'Conta não mapeada: Itaú', 'sheet': 'Setembro'},
        ])
        self.assertEqual((resumo['total'], resumo['imported'], resumo['rejected']), (3, 1, 2))


class CorrecoesTests(InterpretacaoCompletaTestCase):

    LINHAS = [
        CABECALHO,
        ['10/09/2026', 'Padaria', -4.5, 'Corrente A', 'Paga', None, None],
        ['data ruim', 'Mercado', -10, 'Corrente A', 'Paga', None, None],
    ]

    def test_corrigir_a_data_torna_a_linha_valida(self):
        """IMPCOMP-32: o campo corrigido substitui a célula e passa pelas mesmas validações."""
        resultados = self.resultados(self.LINHAS, correcoes={'Extrato:3': {'data': '04/09/2026'}})
        corrigida = resultados[1]
        self.assertIsInstance(corrigida, LinhaImportada)
        self.assertEqual((corrigida.data, corrigida.descricao, corrigida.valor), (date(2026, 9, 4), 'Mercado', Decimal('10.00')))

    def test_correcao_invalida_volta_rejeitada(self):
        """IMPCOMP-33: uma correção inválida volta como rejeição, com o motivo da validação."""
        resultados = self.resultados(self.LINHAS, correcoes={
            'Extrato:2': {'valor': 'abc'}, 'Extrato:3': {'data': '31/02/2026', 'conta': 'Itaú'},
        })
        self.assertEqual(resultados, [
            Rejeicao(2, 'Valor inválido', 'Extrato'), Rejeicao(3, 'Data inválida', 'Extrato'),
        ])

    def test_correcao_de_campos_sem_coluna_na_aba(self):
        """IMPCOMP-32: tipo, conta de destino, categoria e tags corrigidos mesmo sem a coluna na aba."""
        linhas = [['Data', 'Descrição', 'Valor', 'Conta'], ['10/09/2026', 'Reserva', 200, 'Corrente A'],
                  ['11/09/2026', 'Feira', 30, 'Corrente A']]
        transferencia, despesa = self.resultados(linhas, correcoes={
            'Extrato:2': {'tipo': 'transferência', 'destino': 'Poupança A'},
            'Extrato:3': {'tipo': 'Despesa', 'categoria': 'Mercado', 'tags': ['feira', 'casa'],
                          'situacao': 'A pagar', 'descricao': 'Feira livre'},
        })
        self.assertEqual((transferencia.tipo, transferencia.destino), ('TRANSFER', self.a.poupanca))
        self.assertEqual(
            (despesa.tipo, despesa.valor, despesa.categoria, despesa.tags, despesa.status, despesa.descricao),
            ('EXPENSE', Decimal('30.00'), 'Mercado', ['feira', 'casa'], 'PENDING', 'Feira livre'),
        )

    def test_valor_corrigido_numa_aba_de_entrada_e_saida_vale_com_sinal(self):
        """IMPCOMP-32 com IMPORT-18: o valor corrigido substitui a entrada e a saída da linha."""
        linhas = [['Data', 'Histórico', 'Entrada', 'Saída', 'Banco'], ['10/09/2026', 'Duas', 10, 20, 'Corrente A']]
        corrigida, = self.resultados(linhas, correcoes={'Extrato:2': {'valor': '-20,00'}})
        self.assertEqual((corrigida.tipo, corrigida.valor), ('EXPENSE', Decimal('20.00')))

    def test_linha_excluida_fica_como_excluida(self):
        """IMPCOMP-34: a linha excluída no plano sai marcada, e as outras não."""
        interpretadas, _ = self.interpretar(self.LINHAS, correcoes={'Extrato:2': {'excluir': True}})
        self.assertEqual([(l.chave, l.excluida) for l in interpretadas], [('Extrato:2', True), ('Extrato:3', False)])

    def test_tags_travadas_ficam_de_fora_tambem_nas_correcoes(self):
        """IMPCOMP-51 na interpretação: sem tags, também as da correção."""
        linhas = [CABECALHO, ['10/09/2026', 'Padaria', -4.5, 'Corrente A', 'Paga', None, 'casa']]
        com, = self.resultados(linhas, correcoes={'Extrato:2': {'tags': 'viagem'}})
        sem, = self.resultados(linhas, correcoes={'Extrato:2': {'tags': 'viagem'}}, tags_liberadas=False)
        self.assertEqual((com.tags, sem.tags), (['viagem'], []))


class DescricaoDaTransferenciaTests(InterpretacaoCompletaTestCase):

    def test_coluna_de_descricao_ausente_numa_aba_de_transferencias_e_recusada(self):
        """IMPCOMP-22: a mensagem de IMPORT-06 com a coluna que falta."""
        linhas = [['Data', 'Origem', 'Destino', 'Valor'], ['10/09/2026', 'Corrente A', 'Poupança A', 50]]
        plano = [{'nome': 'Extrato', 'papel': 'TRANSFERENCIAS', 'colunas': {
            'date_column': 'Data', 'source_account_column': 'Origem', 'dest_account_column': 'Destino',
            'amount_column': 'Valor', 'description_column': 'Memo',
        }}]
        with self.assertRaises(ValidationError) as recusa:
            self.interpretar(linhas, plano=plano)
        self.assertEqual(recusa.exception.detail, {'file': ['Colunas não encontradas no arquivo: Memo.']})

    def test_rota_antiga_tambem_confere_a_descricao_da_transferencia(self):
        """IMPCOMP-22: o preflight de transferências recusa a coluna de descrição que não existe."""
        mapeamento = {'date_column': 'Data', 'amount_column': 'Valor', 'description_column': 'Descrição',
                      'source_account_column': 'Origem', 'dest_account_column': 'Destino'}
        arquivo = arquivo_csv([['Data', 'Origem', 'Destino', 'Valor'], ['10/09/2026', 'A', 'B', '50,00']])
        resp = self.client.post(URL_PREFLIGHT, {
            'file': arquivo, 'mapping': json.dumps(mapeamento), 'import_type': 'TRANSFER',
        }, format='multipart')
        self.assert_recusado(resp, 'Colunas não encontradas no arquivo: Descrição.')

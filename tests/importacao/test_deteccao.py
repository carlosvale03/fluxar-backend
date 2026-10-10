"""
Detecção do plano (IMPCOMP-04 a IMPCOMP-12, IMPCOMP-14).

Colunas pelos sinônimos, papel de cada aba, modelo do Mobills, abas
contidas em outra, contas do arquivo com a sugestão de vincular ou criar e
o plano editado prevalecendo sobre o detectado. A detecção não grava nada.
"""
from datetime import date
from decimal import Decimal

from rest_framework.exceptions import ValidationError

from accounts.models import Account
from data_exchange.importacao.deteccao import (
    colunas_da_aba, detectar_plano, papel_da_aba, tipo_sugerido,
)
from data_exchange.importacao.leitura import Aba, ler_abas
from transactions.models import Transaction

from .base import ImportacaoTestCase, arquivo_csv, arquivo_xlsx
from .mobills import (
    CABECALHO, CONTAS, abas_do_mobills, arquivo_mobills, efeito_por_conta, lancamentos, transferencias,
)


def aba(*cabecalho):
    return Aba('Aba', list(cabecalho), [])


class ColunasTests(ImportacaoTestCase):

    def test_historico_quantia_e_banco_viram_descricao_valor_e_conta(self):
        """IMPCOMP-04: os sinônimos ligam cada cabeçalho a um campo."""
        self.assertEqual(colunas_da_aba(aba('Data', 'Histórico', 'Quantia', 'Banco')), {
            'date_column': 'Data', 'description_column': 'Histórico',
            'amount_column': 'Quantia', 'account_column': 'Banco',
        })

    def test_cada_sinonimo_da_spec_liga_ao_campo(self):
        """IMPCOMP-04: todos os sinônimos, sem diferença de maiúsculas, acentos e espaços extras."""
        sinonimos = {
            'date_column': ['data', 'Date', 'DT', 'Data da Transação', '  DATA   DA transacao '],
            'description_column': ['Descrição', 'HISTÓRICO', 'memo', 'Título', 'Lançamento'],
            'amount_column': ['Valor', 'quantia', 'AMOUNT'],
            'account_column': ['Conta', 'banco', 'Carteira'],
            'source_account_column': ['Conta origem', 'CONTA  ORIGEM', 'Origem', 'De'],
            'dest_account_column': ['Conta destino', 'Destino', 'para'],
            'type_column': ['Tipo'],
            'status_column': ['Situação', 'status'],
            'category_column': ['Categoria'],
            'subcategory_column': ['Subcategoria'],
            'tags_column': ['Tags', 'Etiquetas'],
            'income_column': ['Entrada', 'Crédito'],
            'expense_column': ['Saída', 'débito'],
        }
        for campo, nomes in sinonimos.items():
            for nome in nomes:
                with self.subTest(nome=nome):
                    self.assertEqual(colunas_da_aba(aba(nome)), {campo: nome})

    def test_cabecalho_desconhecido_fica_de_fora(self):
        """IMPCOMP-04: um cabeçalho sem sinônimo não liga a nenhum campo."""
        self.assertEqual(colunas_da_aba(aba('Observação', 'Valor total')), {})


class PapelTests(ImportacaoTestCase):

    def test_papel_pelas_colunas(self):
        """IMPCOMP-05 a IMPCOMP-07: transferências, receitas e despesas ou ignorada."""
        casos = [
            (('Data', 'Origem', 'Destino', 'Valor'), ('TRANSFERENCIAS', None)),
            # Origem e destino prevalecem mesmo com data e valor
            (('Data', 'Valor', 'Conta origem', 'Conta destino', 'Conta'), ('TRANSFERENCIAS', None)),
            (('Data', 'Valor'), ('RECEITAS_DESPESAS', None)),
            (('Data', 'Entrada', 'Saída', 'Histórico'), ('RECEITAS_DESPESAS', None)),
            (('Data', 'Entrada'), ('IGNORAR', 'Colunas não reconhecidas')),
            (('Valor', 'Descrição'), ('IGNORAR', 'Colunas não reconhecidas')),
            (('Origem', 'Valor'), ('IGNORAR', 'Colunas não reconhecidas')),
            ((), ('IGNORAR', 'Colunas não reconhecidas')),
        ]
        for cabecalho, esperado in casos:
            with self.subTest(cabecalho=cabecalho):
                self.assertEqual(papel_da_aba(colunas_da_aba(aba(*cabecalho))), esperado)


class ModeloMobillsTests(ImportacaoTestCase):

    def test_mobills_e_reconhecido_e_ignora_despesas_e_receitas(self):
        """IMPCOMP-08: modelo, papéis das quatro abas e colunas da exportação."""
        plano = detectar_plano(ler_abas(arquivo_mobills()), self.a.usuario)

        self.assertEqual(plano['modelo'], 'MOBILLS')
        self.assertEqual(
            [(a['nome'], a['papel'], a['motivo']) for a in plano['abas']],
            [
                ('Receitas e Despesas', 'RECEITAS_DESPESAS', None),
                ('Despesas', 'IGNORAR', 'Contida na aba Receitas e Despesas'),
                ('Receitas', 'IGNORAR', 'Contida na aba Receitas e Despesas'),
                ('Transferências', 'TRANSFERENCIAS', None),
            ],
        )
        self.assertEqual(plano['abas'][0]['colunas'], {
            'date_column': 'Data', 'description_column': 'Descrição', 'amount_column': 'Valor',
            'account_column': 'Conta', 'status_column': 'Situação', 'category_column': 'Categoria',
            'subcategory_column': 'Subcategoria', 'tags_column': 'Tags',
        })
        self.assertEqual(plano['abas'][3]['colunas'], {
            'date_column': 'Data', 'source_account_column': 'Conta origem',
            'dest_account_column': 'Conta destino', 'amount_column': 'Valor', 'tags_column': 'Tags',
        })
        self.assertEqual(plano['abas'][0]['cabecalho'], CABECALHO)

    def test_outros_cabecalhos_nao_sao_o_modelo_mobills(self):
        """IMPCOMP-08: com um cabeçalho diferente, o modelo não é reconhecido."""
        abas = abas_do_mobills()
        nome, linhas = abas[0]
        abas[0] = (nome, [['Data', 'Histórico'] + CABECALHO[2:]] + linhas[1:])
        plano = detectar_plano(ler_abas(arquivo_xlsx(abas=abas)), self.a.usuario)
        self.assertIsNone(plano['modelo'])

    def test_csv_nao_e_o_modelo_mobills(self):
        """IMPCOMP-08: um CSV comum usa a detecção genérica."""
        arquivo = arquivo_csv([['Data', 'Descrição', 'Valor'], ['10/09/2026', 'Padaria', '-4,50']])
        plano = detectar_plano(ler_abas(arquivo), self.a.usuario)
        self.assertIsNone(plano['modelo'])
        self.assertEqual([(a['nome'], a['papel']) for a in plano['abas']], [('extrato.csv', 'RECEITAS_DESPESAS')])


class AbasContidasTests(ImportacaoTestCase):

    CABECALHO = ['Data', 'Histórico', 'Quantia', 'Banco']
    LINHAS = [
        ['10/09/2026', 'Padaria', -4.5, 'Inter'],
        ['11/09/2026', 'Salário', 1500, 'Inter'],
        ['12/09/2026', 'Mercado', -80, 'Nubank'],
    ]

    def plano(self, *abas):
        return detectar_plano(ler_abas(arquivo_xlsx(abas=list(abas))), self.a.usuario)

    def papeis(self, plano):
        return [(a['nome'], a['papel'], a['motivo']) for a in plano['abas']]

    def test_aba_repetida_dentro_de_outra_e_ignorada(self):
        """IMPCOMP-09: num arquivo que não é do Mobills, a aba contida é ignorada com o motivo."""
        plano = self.plano(
            ('Extrato', [self.CABECALHO] + self.LINHAS + [['Total (3)', None, 1415.5, None]]),
            ('Saídas', [self.CABECALHO, self.LINHAS[2], self.LINHAS[0], [None] * 4, ['Total (2)', None, -84.5, None]]),
        )
        self.assertIsNone(plano['modelo'])
        self.assertEqual(self.papeis(plano), [
            ('Extrato', 'RECEITAS_DESPESAS', None),
            ('Saídas', 'IGNORAR', 'Contida na aba Extrato'),
        ])

    def test_duas_abas_iguais_ignoram_a_segunda(self):
        """Edge case: duas abas iguais, a segunda fica contida na primeira."""
        plano = self.plano(
            ('Agosto', [self.CABECALHO] + self.LINHAS),
            ('Cópia', [self.CABECALHO] + self.LINHAS),
        )
        self.assertEqual(self.papeis(plano), [
            ('Agosto', 'RECEITAS_DESPESAS', None),
            ('Cópia', 'IGNORAR', 'Contida na aba Agosto'),
        ])

    def test_repeticoes_contam_e_linha_diferente_mantem_a_aba(self):
        """IMPCOMP-09: contando as repetições; uma linha a mais ou diferente mantém a aba usada."""
        plano = self.plano(
            ('Extrato', [self.CABECALHO] + self.LINHAS),
            ('Repetida', [self.CABECALHO, self.LINHAS[0], self.LINHAS[0]]),
            ('Outra conta', [self.CABECALHO, self.LINHAS[0][:3] + ['Itaú']]),
        )
        self.assertEqual(self.papeis(plano), [
            ('Extrato', 'RECEITAS_DESPESAS', None),
            ('Repetida', 'RECEITAS_DESPESAS', None),
            ('Outra conta', 'RECEITAS_DESPESAS', None),
        ])

    def test_aba_sem_linhas_e_aba_sem_colunas(self):
        """Edge case: aba só com o cabeçalho segue sem linhas; aba sem colunas é ignorada."""
        plano = self.plano(
            ('Extrato', [self.CABECALHO] + self.LINHAS),
            ('Só cabeçalho', [self.CABECALHO]),
            ('Notas', [['Observação'], ['qualquer coisa']]),
        )
        self.assertEqual(self.papeis(plano), [
            ('Extrato', 'RECEITAS_DESPESAS', None),
            ('Só cabeçalho', 'RECEITAS_DESPESAS', None),
            ('Notas', 'IGNORAR', 'Colunas não reconhecidas'),
        ])


class ContasDoArquivoTests(ImportacaoTestCase):

    def test_as_11_contas_do_mobills_com_linhas_soma_periodo_e_tipo(self):
        """IMPCOMP-10 e IMPCOMP-12: cada conta uma vez, com o resumo e o tipo sugerido."""
        plano = detectar_plano(ler_abas(arquivo_mobills()), self.a.usuario)

        efeito = efeito_por_conta()
        esperadas = {}
        for nome, tipo in CONTAS.items():
            datas = [l[0] for l in lancamentos() if l[3] == nome]
            datas += [t[0] for t in transferencias() if nome in (t[1], t[2])]
            datas = sorted(date(int(d[6:]), int(d[3:5]), int(d[:2])) for d in datas)
            quantidade = sum(1 for l in lancamentos() if l[3] == nome)
            quantidade += sum(1 for t in transferencias() if nome in (t[1], t[2]))
            esperadas[nome] = {
                'acao': 'criar', 'nome': nome, 'tipo': tipo, 'saldo_atual': '0.00',
                'institution': None, 'color': None,
                'arquivo': {
                    'quantidade': quantidade, 'soma': str(efeito[nome]),
                    'primeira_data': datas[0].isoformat(), 'ultima_data': datas[-1].isoformat(),
                },
            }
        # O cadastro cria a "Carteira" do usuário: a conta de mesmo nome é vinculada (IMPCOMP-11)
        carteira = Account.objects.get(user=self.a.usuario, name='Carteira', is_active=True)
        esperadas['Carteira'] = {'acao': 'vincular', 'id': str(carteira.pk), 'arquivo': esperadas['Carteira']['arquivo']}
        self.assertEqual(plano['contas'], esperadas)

    def test_nome_igual_a_conta_ativa_sugere_vincular(self):
        """IMPCOMP-11: "nubank " vincula à conta "Nubank"; conta excluída de mesmo nome sugere criar."""
        nubank = Account.objects.create(user=self.a.usuario, name='Nubank', type='CHECKING')
        Account.objects.create(user=self.a.usuario, name='Inter', type='CHECKING', is_active=False)
        Account.objects.create(user=self.b.usuario, name='Itaú', type='CHECKING')
        arquivo = arquivo_csv([
            ['Data', 'Descrição', 'Valor', 'Conta'],
            ['10/09/2026', 'Padaria', '-4,50', 'nubank '],
            ['11/09/2026', 'Mercado', '-10,00', '  NUBANK'],
            ['12/09/2026', 'Salário', '100,00', 'Inter'],
            ['13/09/2026', 'Cinema', '-20,00', 'itau'],
        ])
        contas = detectar_plano(ler_abas(arquivo), self.a.usuario)['contas']

        self.assertEqual(list(contas), ['nubank', 'Inter', 'itau'])
        self.assertEqual(contas['nubank'], {
            'acao': 'vincular', 'id': str(nubank.pk),
            'arquivo': {'quantidade': 2, 'soma': '-14.50', 'primeira_data': '2026-09-10', 'ultima_data': '2026-09-11'},
        })
        self.assertEqual((contas['Inter']['acao'], contas['Inter']['tipo']), ('criar', 'CHECKING'))
        # A conta "Itaú" é de outro usuário: a sugestão é criar
        self.assertEqual((contas['itau']['acao'], contas['itau']['nome']), ('criar', 'itau'))

    def test_tipo_sugerido_pelas_palavras_do_nome(self):
        """IMPCOMP-12: carteira, poupança ou reserva, investimento ou CDB, cofrinho e os demais."""
        casos = {
            'Minha Carteira': 'WALLET', 'POUPANÇA': 'SAVINGS', 'XMeta - Reserva': 'SAVINGS',
            'Investimentos': 'INVESTMENT', 'XC - cdb banco': 'INVESTMENT', 'Cofrinho': 'PIGGY_BANK',
            'XC - Nubank': 'CHECKING', 'XMeta - Viagem': 'CHECKING',
        }
        for nome, tipo in casos.items():
            with self.subTest(nome=nome):
                self.assertEqual(tipo_sugerido(nome), tipo)

    def test_deteccao_nao_grava_nada(self):
        """IMPCOMP-13: detectar o plano do Mobills não cria conta nem transação."""
        contas, transacoes = Account.objects.count(), Transaction.objects.count()
        detectar_plano(ler_abas(arquivo_mobills()), self.a.usuario)
        self.assertEqual((Account.objects.count(), Transaction.objects.count()), (contas, transacoes))


class PlanoEditadoTests(ImportacaoTestCase):

    def test_papel_colunas_e_contas_do_plano_prevalecem(self):
        """IMPCOMP-14: o plano editado substitui os papéis, as colunas e as contas detectados."""
        editado = {
            'abas': [
                {'nome': 'Despesas', 'papel': 'RECEITAS_DESPESAS', 'colunas': {
                    'date_column': 'Data', 'amount_column': 'Valor', 'account_column': 'Conta',
                    'description_column': 'Categoria',
                }},
                {'nome': 'Transferências', 'papel': 'IGNORAR'},
            ],
            'contas': {
                'nubank': {'acao': 'vincular', 'conta': self.a.conta},
                'Itaú': {'acao': 'criar', 'nome': 'Itaú PJ', 'tipo': 'SAVINGS', 'saldo_atual': Decimal('-12.5'),
                         'institution': 'itau', 'color': '#123456'},
            },
            'linhas': {'Despesas:3': {'excluir': True}},
        }
        plano = detectar_plano(ler_abas(arquivo_mobills()), self.a.usuario, editado)

        self.assertEqual(
            [(a['nome'], a['papel'], a['motivo']) for a in plano['abas']],
            [
                ('Receitas e Despesas', 'RECEITAS_DESPESAS', None),
                ('Despesas', 'RECEITAS_DESPESAS', None),
                ('Receitas', 'IGNORAR', 'Contida na aba Receitas e Despesas'),
                ('Transferências', 'IGNORAR', None),
            ],
        )
        self.assertEqual(plano['abas'][1]['colunas'], editado['abas'][0]['colunas'])
        # Sem colunas no plano, ficam as detectadas
        self.assertEqual(plano['abas'][3]['colunas']['source_account_column'], 'Conta origem')
        self.assertEqual(plano['contas']['Nubank']['acao'], 'vincular')
        self.assertEqual(plano['contas']['Nubank']['id'], str(self.a.conta.pk))
        itau = dict(plano['contas']['Itaú'])
        itau.pop('arquivo')
        self.assertEqual(itau, {
            'acao': 'criar', 'nome': 'Itaú PJ', 'tipo': 'SAVINGS', 'saldo_atual': '-12.50',
            'institution': 'itau', 'color': '#123456',
        })
        self.assertEqual(plano['linhas'], {'Despesas:3': {'excluir': True}})

    def test_aba_do_plano_que_nao_existe_no_arquivo_e_recusada(self):
        """IMPCOMP-14: uma aba do plano que não existe no arquivo recebe 400 no plano."""
        editado = {'abas': [{'nome': 'Fevereiro', 'papel': 'IGNORAR'}]}
        with self.assertRaises(ValidationError) as recusa:
            detectar_plano(ler_abas(arquivo_mobills()), self.a.usuario, editado)
        self.assertEqual(recusa.exception.detail, {'plano': ['Aba inexistente no arquivo: Fevereiro.']})

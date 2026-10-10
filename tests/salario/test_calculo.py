"""
Modelos da literatura e cálculo da divisão (SALARIO-02, SALARIO-03,
SALARIO-06, SALARIO-26 a SALARIO-28, SALARIO-30, SALARIO-34).
"""
import uuid
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from salario.calculo import AjustesAcimaDoRecebido, dividir
from salario.modelos import MODELOS, POR_CODIGO

CONTA_DO_SALARIO = uuid.uuid4()
OUTRA_CONTA = uuid.uuid4()


def parte(nome, regra, valor, destino='GOAL', conta_id=None):
    return SimpleNamespace(
        id=uuid.uuid4(), nome=nome, tipo_de_regra=regra, valor=Decimal(valor),
        tipo_de_destino=destino, conta_id=conta_id,
    )


def fixa(nome, valor, destino='GOAL', conta_id=None):
    return parte(nome, 'FIXED', valor, destino, conta_id)


def percentual(nome, valor, destino='GOAL', conta_id=None):
    return parte(nome, 'PERCENT', valor, destino, conta_id)


def resumo(modelo):
    return [(p.nome, p.percentual, p.tipo_de_destino, p.referencia) for p in modelo.partes]


class ModelosTests(SimpleTestCase):

    def test_sao_quatro_modelos_na_ordem_com_a_obra_de_origem(self):
        self.assertEqual(
            [(m.codigo, m.nome, m.autor, m.obra) for m in MODELOS],
            [
                ('pague_se_primeiro', 'Pague-se primeiro', 'George S. Clason', 'O Homem Mais Rico da Babilônia'),
                ('50_30_20', '50/30/20', 'Elizabeth Warren e Amelia Warren Tyagi', 'All Your Worth'),
                ('seis_potes', 'Seis potes', 'T. Harv Eker', 'Os Segredos da Mente Milionária'),
                ('personalizado', 'Personalizado', None, None),
            ],
        )

    def test_pague_se_primeiro_guarda_10_por_cento_sem_destino(self):
        self.assertEqual(resumo(POR_CODIGO['pague_se_primeiro']), [('Guardar', Decimal('10'), None, '')])

    def test_50_30_20_gasta_na_conta_do_salario_e_guarda_sem_destino(self):
        self.assertEqual(resumo(POR_CODIGO['50_30_20']), [
            ('Essenciais', Decimal('50'), 'SALARY_ACCOUNT', 'ESSENCIAL'),
            ('Dispensáveis', Decimal('30'), 'SALARY_ACCOUNT', 'DISPENSAVEL'),
            ('Guardar', Decimal('20'), None, ''),
        ])

    def test_seis_potes_tem_as_seis_partes_da_obra(self):
        self.assertEqual(resumo(POR_CODIGO['seis_potes']), [
            ('Necessidades', Decimal('55'), 'SALARY_ACCOUNT', 'ESSENCIAL'),
            ('Liberdade financeira', Decimal('10'), None, ''),
            ('Poupança para gastos futuros', Decimal('10'), None, ''),
            ('Educação', Decimal('10'), 'SALARY_ACCOUNT', ''),
            ('Diversão', Decimal('10'), 'SALARY_ACCOUNT', 'DISPENSAVEL'),
            ('Doações', Decimal('5'), 'SALARY_ACCOUNT', ''),
        ])
        self.assertEqual(sum(p.percentual for p in POR_CODIGO['seis_potes'].partes), Decimal('100'))

    def test_personalizado_comeca_sem_partes(self):
        self.assertEqual(POR_CODIGO['personalizado'].partes, ())


class DividirTests(SimpleTestCase):

    def valores(self, divisao):
        return [item.valor for item in divisao.itens]

    def test_50_30_20_sobre_3000_divide_tudo_e_so_o_guardar_sai_da_conta(self):
        partes = [
            percentual('Essenciais', '50', 'SALARY_ACCOUNT'),
            percentual('Dispensáveis', '30', 'SALARY_ACCOUNT'),
            percentual('Guardar', '20', 'GOAL'),
        ]

        divisao = dividir(Decimal('3000.00'), partes)

        self.assertEqual(self.valores(divisao), [Decimal('1500.00'), Decimal('900.00'), Decimal('600.00')])
        # Sem sobra: as partes somam o recebido
        self.assertEqual(sum(self.valores(divisao)), Decimal('3000.00'))
        self.assertEqual([i.gera_transacao for i in divisao.itens], [False, False, True])
        self.assertEqual((divisao.total, divisao.livre), (Decimal('600.00'), Decimal('2400.00')))
        self.assertFalse(any(i.reduzida for i in divisao.itens))

    def test_percentual_e_arredondado_para_baixo_e_a_diferenca_fica_livre(self):
        divisao = dividir(Decimal('1000.00'), [percentual('Guardar', '33.33')])

        self.assertEqual(self.valores(divisao), [Decimal('333.30')])
        self.assertEqual((divisao.total, divisao.livre), (Decimal('333.30'), Decimal('666.70')))

    def test_centavo_quebrado_vai_para_baixo(self):
        # 10% de 1.234,59 = 123,459: fica 123,45
        divisao = dividir(Decimal('1234.59'), [percentual('Guardar', '10')])

        self.assertEqual(self.valores(divisao), [Decimal('123.45')])
        self.assertEqual(divisao.livre, Decimal('1111.14'))

    def test_percentual_vale_sobre_o_recebido_na_ordem_do_plano(self):
        divisao = dividir(Decimal('1000.00'), [fixa('Aluguel', '500'), percentual('Guardar', '50')])

        self.assertEqual(self.valores(divisao), [Decimal('500'), Decimal('500.00')])
        self.assertEqual(divisao.livre, Decimal('0.00'))

    def test_salario_menor_reduz_a_ultima_parte(self):
        divisao = dividir(Decimal('1000.00'), [fixa('Primeira', '700'), fixa('Segunda', '500')])

        self.assertEqual(self.valores(divisao), [Decimal('700'), Decimal('300')])
        self.assertEqual([i.reduzida for i in divisao.itens], [False, True])
        self.assertEqual(divisao.livre, Decimal('0.00'))

    def test_salario_menor_zera_a_ultima_e_reduz_a_anterior(self):
        divisao = dividir(Decimal('1000.00'), [fixa('A', '800'), fixa('B', '300'), fixa('C', '200')])

        self.assertEqual(self.valores(divisao), [Decimal('800'), Decimal('200'), Decimal('0')])
        self.assertEqual([i.reduzida for i in divisao.itens], [False, True, True])
        # A parte zerada não gera transação
        self.assertEqual([i.gera_transacao for i in divisao.itens], [True, True, False])
        self.assertEqual((divisao.total, divisao.livre), (Decimal('1000'), Decimal('0.00')))

    def test_ajuste_vale_so_na_divisao(self):
        guardar = percentual('Guardar', '20')

        divisao = dividir(Decimal('3000.00'), [guardar], ajustes={str(guardar.id): Decimal('450.00')})

        self.assertEqual(self.valores(divisao), [Decimal('450.00')])
        self.assertEqual(divisao.livre, Decimal('2550.00'))
        # A parte do plano continua como estava
        self.assertEqual((guardar.tipo_de_regra, guardar.valor), ('PERCENT', Decimal('20')))
        self.assertEqual(self.valores(dividir(Decimal('3000.00'), [guardar])), [Decimal('600.00')])

    def test_parte_ajustada_nao_e_reduzida_e_a_reducao_vai_para_as_outras(self):
        primeira, segunda = fixa('Primeira', '500'), fixa('Segunda', '300')

        divisao = dividir(Decimal('1000.00'), [primeira, segunda], ajustes={primeira.id: Decimal('900.00')})

        self.assertEqual(self.valores(divisao), [Decimal('900.00'), Decimal('100')])
        self.assertEqual([i.reduzida for i in divisao.itens], [False, True])

    def test_ajustes_que_passam_do_recebido_sao_recusados(self):
        guardar = fixa('Guardar', '100')

        with self.assertRaises(AjustesAcimaDoRecebido):
            dividir(Decimal('1000.00'), [guardar], ajustes={str(guardar.id): Decimal('1000.01')})

    def test_partes_que_nao_geram_transacao(self):
        partes = [
            fixa('Na conta do salário', '100', 'SALARY_ACCOUNT'),
            fixa('Na própria conta do recebimento', '100', 'ACCOUNT', CONTA_DO_SALARIO),
            fixa('Zerada pelo ajuste', '100', 'GOAL'),
            fixa('Outra conta', '100', 'ACCOUNT', OUTRA_CONTA),
            fixa('Meta', '100', 'GOAL'),
            fixa('Sem destino', '100', None),
        ]

        divisao = dividir(
            Decimal('3000.00'), partes, ajustes={str(partes[2].id): Decimal('0')},
            conta_do_recebimento=CONTA_DO_SALARIO,
        )

        self.assertEqual(
            [i.gera_transacao for i in divisao.itens], [False, False, False, True, True, True],
        )
        self.assertEqual((divisao.total, divisao.livre), (Decimal('300'), Decimal('2700.00')))

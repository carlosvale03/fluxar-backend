"""
API do plano de divisão (SALARIO-01, SALARIO-04, SALARIO-05, SALARIO-07 a
SALARIO-14, SALARIO-16, SALARIO-18, SALARIO-55).
"""
import uuid
from datetime import date
from decimal import Decimal

from accounts.models import Account
from api.models import TravaDePlano
from core import travas
from goals.models import Goal
from tests.permissoes.base import fechar, liberacao_de_testes
from transactions.models import Category, Transaction

from .base import (
    URL_MODELOS, URL_PLANO, URL_SIMULAR, SalarioTestCase, hoje_em, parte, plano_50_30_20,
)

SOMA_ACIMA = {'detail': 'A soma dos percentuais passa de 100%.', 'code': 'invalid'}
DESTINO_INDISPONIVEL = 'Escolha uma conta ativa que não seja cofrinho ou uma meta ativa.'
BLOQUEADO = {
    'detail': 'Este recurso não está disponível no seu plano.', 'code': 'plan_locked',
    'feature': 'gestao_do_salario',
}


def resumo(partes):
    return [
        (p['name'], p['rule_type'], p['value'], p['destination_type'], p['account'], p['goal'], p['reference'])
        for p in partes
    ]


class ModelosTests(SalarioTestCase):

    def test_devolve_os_quatro_modelos_com_a_obra_e_as_partes(self):
        resposta = self.client.get(URL_MODELOS)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            [(m['code'], m['name'], m['author'], m['book']) for m in resposta.data],
            [
                ('pague_se_primeiro', 'Pague-se primeiro', 'George S. Clason', 'O Homem Mais Rico da Babilônia'),
                ('50_30_20', '50/30/20', 'Elizabeth Warren e Amelia Warren Tyagi', 'All Your Worth'),
                ('seis_potes', 'Seis potes', 'T. Harv Eker', 'Os Segredos da Mente Milionária'),
                ('personalizado', 'Personalizado', None, None),
            ],
        )
        self.assertEqual(resposta.data[1]['parts'], [
            {'name': 'Essenciais', 'rule_type': 'PERCENT', 'value': '50.00',
             'destination_type': 'SALARY_ACCOUNT', 'reference': 'ESSENCIAL'},
            {'name': 'Dispensáveis', 'rule_type': 'PERCENT', 'value': '30.00',
             'destination_type': 'SALARY_ACCOUNT', 'reference': 'DISPENSAVEL'},
            {'name': 'Guardar', 'rule_type': 'PERCENT', 'value': '20.00', 'destination_type': None, 'reference': ''},
        ])
        self.assertEqual(resposta.data[3]['parts'], [])


class SalvarPlanoTests(SalarioTestCase):

    def test_sem_plano_salvo_comeca_vazio(self):
        resposta = self.client.get(URL_PLANO)

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(resposta.data['has_plan'])
        self.assertEqual(resposta.data['parts'], [])

    def test_salva_o_50_30_20_com_guardar_na_meta_e_reabre_igual(self):
        self.salvar_plano(plano_50_30_20(guardar_na=self.a.viagem))

        resposta = self.client.get(URL_PLANO)

        self.assertTrue(resposta.data['has_plan'])
        self.assertEqual(resumo(resposta.data['parts']), [
            ('Essenciais', 'PERCENT', '50.00', 'SALARY_ACCOUNT', None, None, 'ESSENCIAL'),
            ('Dispensáveis', 'PERCENT', '30.00', 'SALARY_ACCOUNT', None, None, 'DISPENSAVEL'),
            ('Guardar', 'PERCENT', '20.00', 'GOAL', None, str(self.a.viagem.pk), ''),
        ])
        self.assertEqual(
            [p['destination_name'] for p in resposta.data['parts']],
            ['Fica na conta do salário', 'Fica na conta do salário', 'Viagem A'],
        )

    def test_mudar_a_ordem_grava_a_nova(self):
        partes = [
            parte('Reserva', 'FIXED', '300.00', 'ACCOUNT', account=self.a.poupanca),
            parte('Guardar', 'PERCENT', '10.00', 'GOAL', goal=self.a.viagem),
        ]
        self.salvar_plano(partes)

        self.salvar_plano(partes[::-1])

        resposta = self.client.get(URL_PLANO)
        self.assertEqual([p['name'] for p in resposta.data['parts']], ['Guardar', 'Reserva'])
        self.assertEqual(resposta.data['parts'][1]['account'], str(self.a.poupanca.pk))

    def test_personalizado_salva_o_plano_sem_partes(self):
        self.salvar_plano([])

        resposta = self.client.get(URL_PLANO)

        self.assertTrue(resposta.data['has_plan'])
        self.assertEqual(resposta.data['parts'], [])

    def test_meta_com_data_mostra_quanto_pede_por_mes(self):
        Goal.objects.filter(pk=self.a.viagem.pk).update(target_date=date(2027, 4, 20))
        with hoje_em(2026, 10, 10):
            self.salvar_plano([parte('Guardar', 'PERCENT', '20.00', 'GOAL', goal=self.a.viagem)])
            resposta = self.client.get(URL_PLANO)

        # R$ 6.000,00 em 6 meses
        self.assertEqual(resposta.data['parts'][0]['goal_monthly_needed'], '1000.00')
        self.assertEqual(resposta.data['parts'][0]['goal_target_date'], '2027-04-20')


class ValidacaoDasPartesTests(SalarioTestCase):

    def put(self, partes):
        return self.client.put(URL_PLANO, {'parts': partes}, format='json')

    def test_percentuais_acima_de_100_sao_recusados(self):
        self.salvar_plano(plano_50_30_20())
        partes = plano_50_30_20() + [parte('Extra', 'PERCENT', '10.00', 'SALARY_ACCOUNT')]

        resposta = self.put(partes)

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data, SOMA_ACIMA)
        # O plano salvo não muda
        self.assertEqual(len(self.client.get(URL_PLANO).data['parts']), 3)

    def test_percentuais_somando_exatamente_100_passam(self):
        self.salvar_plano(plano_50_30_20())

    def test_valor_fixo_abaixo_de_um_centavo_recebe_erro_no_valor_da_parte(self):
        resposta = self.put([
            parte('Guardar', 'PERCENT', '10.00', 'SALARY_ACCOUNT'),
            parte('Aluguel', 'FIXED', '0.00', 'SALARY_ACCOUNT'),
        ])

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data, {'parts': [{}, {'value': ['O valor fixo deve ser de pelo menos R$ 0,01.']}]})

    def test_percentual_fora_do_intervalo_recebe_erro_no_valor_da_parte(self):
        for valor in ('100.01', '0.00', '-5.00'):
            with self.subTest(valor=valor):
                resposta = self.put([parte('Guardar', 'PERCENT', valor, 'SALARY_ACCOUNT')])

                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(
                    resposta.data, {'parts': [{'value': ['O percentual deve ficar entre 0,01% e 100%.']}]},
                )
        self.salvar_plano([parte('Tudo', 'PERCENT', '100.00', 'SALARY_ACCOUNT')])
        self.salvar_plano([parte('Pouco', 'PERCENT', '0.01', 'SALARY_ACCOUNT')])

    def test_conta_ou_meta_de_outro_usuario_recebe_a_mesma_resposta_de_um_id_inexistente(self):
        casos = (
            ('ACCOUNT', 'account', self.b.poupanca.pk, {'account': ['Conta não encontrada.']}),
            ('GOAL', 'goal', self.b.viagem.pk, {'goal': ['Meta não encontrada.']}),
        )
        for destino, campo, de_outro, erro in casos:
            with self.subTest(destino=destino):
                respostas = []
                for pk in (de_outro, uuid.uuid4() if campo == 'account' else 999999):
                    corpo = parte('Parte', 'FIXED', '10.00', destino)
                    corpo[campo] = str(pk)
                    respostas.append(self.put([corpo]))

                for resposta in respostas:
                    self.assertEqual(resposta.status_code, 400)
                    self.assertEqual(resposta.data, {'parts': [erro]})

    def test_cofrinho_conta_inativa_e_meta_inativa_recebem_a_mensagem_do_destino(self):
        inativa = Account.objects.create(user=self.a.usuario, name='Antiga', type='CHECKING', is_active=False)
        arquivada = Goal.objects.create(
            user=self.a.usuario, name='Arquivada', target_amount=Decimal('100'), account=self.a.cofrinho,
            is_active=False,
        )
        casos = (
            ('cofrinho', parte('P', 'FIXED', '10.00', 'ACCOUNT', account=self.a.cofrinho), 'account'),
            ('conta inativa', parte('P', 'FIXED', '10.00', 'ACCOUNT', account=inativa), 'account'),
            ('meta inativa', parte('P', 'FIXED', '10.00', 'GOAL', goal=arquivada), 'goal'),
        )
        for nome, corpo, campo in casos:
            with self.subTest(nome):
                resposta = self.put([corpo])

                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.data, {'parts': [{campo: [DESTINO_INDISPONIVEL]}]})


class CategoriasDeSalarioTests(SalarioTestCase):

    def test_sem_configuracao_traz_salario_e_as_subcategorias(self):
        bonus = Category.objects.create(user=self.a.usuario, name='Bônus', type='INCOME', parent=self.a.salario)
        Category.objects.create(user=self.b.usuario, name='Salário', type='INCOME')

        resposta = self.client.get(URL_PLANO)

        self.assertEqual(set(resposta.data['salary_categories']), {str(self.a.salario.pk), str(bonus.pk)})

    def test_categorias_configuradas_substituem_as_padrao(self):
        investimento = Category.objects.get(user=self.a.usuario, name='Investimento', type='INCOME')

        self.salvar_plano([], salary_categories=[str(investimento.pk)])

        self.assertEqual(self.client.get(URL_PLANO).data['salary_categories'], [str(investimento.pk)])

    def test_so_aceita_categorias_de_receita_do_usuario(self):
        despesa = Category.objects.filter(user=self.a.usuario, type='EXPENSE').first()
        de_outro = self.b.salario
        for categoria in (despesa, de_outro):
            with self.subTest(categoria=categoria.name):
                resposta = self.client.put(
                    URL_PLANO, {'parts': [], 'salary_categories': [str(categoria.pk)]}, format='json',
                )

                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.data, {'salary_categories': ['Categoria não encontrada.']})


class SimulacaoTests(SalarioTestCase):

    def test_simula_pelo_plano_salvo_sem_criar_transacao(self):
        self.salvar_plano(plano_50_30_20(guardar_na=self.a.viagem))
        antes = Transaction.objects.count()

        resposta = self.client.post(URL_SIMULAR, {'amount': '3000.00'}, format='json')

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(
            [(i['name'], i['amount'], i['generates_transaction']) for i in resposta.data['items']],
            [('Essenciais', '1500.00', False), ('Dispensáveis', '900.00', False), ('Guardar', '600.00', True)],
        )
        self.assertEqual(resposta.data['items'][2]['destination_name'], 'Viagem A')
        self.assertEqual((resposta.data['total'], resposta.data['free']), ('600.00', '2400.00'))
        self.assertEqual(Transaction.objects.count(), antes)

    def test_simula_partes_ainda_nao_salvas_mesmo_sem_destino(self):
        resposta = self.client.post(URL_SIMULAR, {
            'amount': '1000.00',
            'parts': [parte('Aluguel', 'FIXED', '700.00', 'SALARY_ACCOUNT'), parte('Guardar', 'FIXED', '500.00')],
        }, format='json')

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(
            [(i['name'], i['amount'], i['reduced']) for i in resposta.data['items']],
            [('Aluguel', '700.00', False), ('Guardar', '300.00', True)],
        )
        self.assertEqual(resposta.data['free'], '700.00')

    def test_percentual_arredonda_para_baixo_no_centavo(self):
        # 10% de 1.234,55 = 123,455: para baixo dá 123,45 (meio para cima daria 123,46)
        resposta = self.client.post(URL_SIMULAR, {
            'amount': '1234.55', 'parts': [parte('Guardar', 'PERCENT', '10.00')],
        }, format='json')

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(resposta.data['items'][0]['amount'], '123.45')
        self.assertEqual((resposta.data['total'], resposta.data['free']), ('123.45', '1111.10'))

    def test_simulacao_recusa_valor_vazio_e_percentuais_acima_de_100(self):
        self.assertEqual(self.client.post(URL_SIMULAR, {'amount': '0'}, format='json').status_code, 400)
        resposta = self.client.post(URL_SIMULAR, {
            'amount': '1000.00', 'parts': [parte('A', 'PERCENT', '60.00'), parte('B', 'PERCENT', '41.00')],
        }, format='json')
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data, SOMA_ACIMA)


class TravaELogsTests(SalarioTestCase):

    def test_com_o_recurso_travado_as_rotas_recebem_403(self):
        liberacao_de_testes(False)
        fechar('gestao_do_salario')
        try:
            chamadas = (
                lambda: self.client.get(URL_MODELOS),
                lambda: self.client.get(URL_PLANO),
                lambda: self.client.put(URL_PLANO, {'parts': []}, format='json'),
                lambda: self.client.post(URL_SIMULAR, {'amount': '10.00'}, format='json'),
            )
            for chamar in chamadas:
                resposta = chamar()
                self.assertEqual(resposta.status_code, 403)
                self.assertEqual(resposta.data, BLOQUEADO)
        finally:
            TravaDePlano.objects.all().delete()
            travas.invalidar()

    def test_logs_nao_levam_valores_nem_nomes(self):
        with self.assertLogs('salario', level='INFO') as logs:
            self.salvar_plano([
                parte('Viagem dos sonhos', 'FIXED', '1234.56', 'GOAL', goal=self.a.viagem),
                parte('Reserva', 'PERCENT', '12.34', 'ACCOUNT', account=self.a.poupanca),
            ])

        texto = '\n'.join(logs.output)
        for dado in ('Viagem', 'Reserva', 'Poupança', '1234.56', '1.234,56', '12.34', '12,34'):
            self.assertNotIn(dado, texto)

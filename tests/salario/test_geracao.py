"""
Geração das transações da divisão (SALARIO-18, SALARIO-32 a SALARIO-38,
SALARIO-40 a SALARIO-43).
"""
import uuid
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from accounts.models import Account
from goals.models import Goal
from goals.services import GoalService
from salario.models import DivisaoDoSalario
from transactions.models import Transaction
from transactions.services import TransactionService

from .base import (
    URL_DIVISOES, URL_PLANO, SalarioTestCase, hoje_em, parte, plano_50_30_20, receita, url_da_divisao,
)

JA_DIVIDIDO = {'detail': 'Este salário já foi dividido.', 'code': 'invalid'}


def erro(mensagem):
    return {'detail': mensagem, 'code': 'invalid'}


class GeracaoTestCase(SalarioTestCase):

    def setUp(self):
        super().setUp()
        self.salario = receita(self.a)

    def gerar(self, recebimento=None, chave=None, **extra):
        corpo = {'receipt': str((recebimento or self.salario).pk), **extra}
        if chave is not None:
            corpo['idempotency_key'] = str(chave)
        with hoje_em(2026, 10, 10):
            return self.client.post(URL_DIVISOES, corpo, format='json')

    def da_divisao(self, divisao_id):
        return Transaction.objects.filter(divisao_do_salario=divisao_id)


class GeraAsTransacoesTests(GeracaoTestCase):

    def test_aporte_efetivado_de_hoje_entra_so_na_meta_escolhida(self):
        # O cofrinho da Viagem é dividido com o Carro, que já tem R$ 100,00
        Account.objects.filter(pk=self.a.cofrinho.pk).update(initial_balance=Decimal('100.00'), balance=Decimal('100.00'))
        carro = Goal.objects.create(
            user=self.a.usuario, name='Carro', target_amount=Decimal('5000.00'), account=self.a.cofrinho,
        )
        GoalService.aportar(carro, Decimal('100.00'), date(2026, 10, 1))
        self.salvar_plano(plano_50_30_20(guardar_na=self.a.viagem))

        resposta = self.gerar(chave=uuid.uuid4())

        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual((resposta.data['total'], resposta.data['free']), ('600.00', '2400.00'))
        self.assertEqual(resposta.data['date'], '2026-10-10')
        self.assertEqual(resposta.data['can_undo_until'], '2026-10-17')
        [gerada] = resposta.data['transactions']
        self.assertEqual(
            (gerada['kind'], gerada['amount'], gerada['date'], gerada['destination_name'], gerada['goal']),
            ('GOAL_DEPOSIT', '600.00', '2026-10-10', 'Viagem A', str(self.a.viagem.pk)),
        )
        pernas = self.da_divisao(resposta.data['id'])
        self.assertEqual(
            sorted((p.type, p.account_id, p.amount, p.status, p.date) for p in pernas),
            sorted([
                ('TRANSFER_OUT', self.a.conta.pk, Decimal('600.00'), 'COMPLETED', date(2026, 10, 10)),
                ('TRANSFER_IN', self.a.cofrinho.pk, Decimal('600.00'), 'COMPLETED', date(2026, 10, 10)),
            ]),
        )
        self.assertEqual(self.valor_da_meta(self.a.viagem), Decimal('600.00'))
        self.assertEqual(self.valor_da_meta(carro), Decimal('100.00'))
        self.assertEqual(self.saldo(self.a.conta), Decimal('2400.00'))
        self.assertEqual(self.saldo(self.a.cofrinho), Decimal('700.00'))

    def test_geracao_na_virada_do_dia_em_utc_usa_a_data_de_brasilia(self):
        # 02h30 UTC do dia 11 ainda é 23h30 do dia 10 em Brasília (AD-008)
        self.salvar_plano([parte('Reserva', 'FIXED', '500.00', 'ACCOUNT', account=self.a.poupanca)])
        noite = datetime(2026, 10, 11, 2, 30, tzinfo=dt_timezone.utc)
        with mock.patch('django.utils.timezone.now', return_value=noite):
            resposta = self.client.post(URL_DIVISOES, {'receipt': str(self.salario.pk)}, format='json')

        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual(resposta.data['date'], '2026-10-10')
        self.assertEqual(resposta.data['transactions'][0]['date'], '2026-10-10')
        self.assertEqual(resposta.data['can_undo_until'], '2026-10-17')
        self.assertEqual(
            {p.date for p in self.da_divisao(resposta.data['id'])}, {date(2026, 10, 10)},
        )

    def test_parte_com_destino_numa_conta_cria_a_transferencia_e_todas_levam_o_id_da_divisao(self):
        self.salvar_plano([
            parte('Aluguel', 'FIXED', '1000.00', 'SALARY_ACCOUNT'),
            parte('Reserva', 'FIXED', '500.00', 'ACCOUNT', account=self.a.poupanca),
            parte('Guardar', 'PERCENT', '10.00', 'GOAL', goal=self.a.viagem),
        ])

        resposta = self.gerar()

        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual(
            [(t['kind'], t['destination_name'], t['amount']) for t in resposta.data['transactions']],
            [('TRANSFER', 'Poupança A', '500.00'), ('GOAL_DEPOSIT', 'Viagem A', '300.00')],
        )
        self.assertEqual(self.da_divisao(resposta.data['id']).count(), 4)
        self.assertEqual(Transaction.objects.filter(divisao_do_salario__isnull=False).count(), 4)
        self.assertEqual(self.saldo(self.a.poupanca), Decimal('500.00'))
        self.assertEqual(self.saldo(self.a.conta), Decimal('2200.00'))
        self.assertEqual((resposta.data['total'], resposta.data['free']), ('800.00', '2200.00'))
        # A divisão relida é igual à resposta da geração
        self.assertEqual(self.client.get(url_da_divisao(resposta.data['id'])).data, resposta.data)

    def test_parte_na_propria_conta_do_recebimento_nao_gera_transacao(self):
        self.salvar_plano([
            parte('Fica', 'FIXED', '500.00', 'ACCOUNT', account=self.a.conta),
            parte('Guardar', 'FIXED', '200.00', 'GOAL', goal=self.a.viagem),
        ])

        resposta = self.gerar()

        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual(len(resposta.data['transactions']), 1)
        self.assertEqual(
            [(i['name'], i['generates_transaction']) for i in resposta.data['items']],
            [('Fica', False), ('Guardar', True)],
        )
        self.assertEqual(self.da_divisao(resposta.data['id']).count(), 2)

    def test_ajuste_da_revisao_vale_na_geracao(self):
        self.salvar_plano(plano_50_30_20(guardar_na=self.a.viagem))
        guardar_id = self.client.get(URL_PLANO).data['parts'][2]['id']

        resposta = self.gerar(adjustments={guardar_id: '450.00'})

        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual(self.valor_da_meta(self.a.viagem), Decimal('450.00'))
        self.assertEqual(resposta.data['free'], '2550.00')

    def test_divisao_de_outro_usuario_nao_e_encontrada(self):
        self.salvar_plano(plano_50_30_20(guardar_na=self.a.viagem))
        divisao_id = self.gerar().data['id']

        self.client.force_authenticate(user=self.b.usuario)
        resposta = self.client.get(url_da_divisao(divisao_id))

        self.assertEqual(resposta.status_code, 404)

    def test_logs_da_geracao_nao_levam_valores_nem_nomes(self):
        self.salvar_plano(plano_50_30_20(guardar_na=self.a.viagem))

        with self.assertLogs('salario', level='INFO') as logs:
            self.assertEqual(self.gerar().status_code, 201)

        texto = '\n'.join(logs.output)
        for dado in ('Viagem', 'Guardar', 'Corrente', '600.00', '3000.00', '2400.00', '600,00'):
            self.assertNotIn(dado, texto)


class TudoOuNadaTests(GeracaoTestCase):

    def setUp(self):
        super().setUp()
        self.salvar_plano([
            parte('Reserva', 'FIXED', '500.00', 'ACCOUNT', account=self.a.poupanca),
            parte('Guardar', 'FIXED', '600.00', 'GOAL', goal=self.a.viagem),
        ])

    def assert_nada_gravado(self):
        self.assertFalse(DivisaoDoSalario.objects.exists())
        self.assertFalse(Transaction.objects.filter(divisao_do_salario__isnull=False).exists())
        self.assertEqual(Transaction.objects.filter(type__startswith='TRANSFER').count(), 0)
        self.assertEqual(self.saldo(self.a.conta), Decimal('3000.00'))
        self.assertEqual(self.saldo(self.a.poupanca), Decimal('0.00'))
        self.assertEqual(self.valor_da_meta(self.a.viagem), Decimal('0.00'))

    def test_falha_inesperada_no_segundo_item_nao_deixa_nada_gravado(self):
        original = TransactionService.create_transfer
        chamadas = []

        def falha_na_segunda(**kwargs):
            chamadas.append(kwargs)
            if len(chamadas) == 2:
                raise RuntimeError('falha forçada')
            return original(**kwargs)

        self.client.raise_request_exception = False
        with mock.patch.object(TransactionService, 'create_transfer', side_effect=falha_na_segunda):
            resposta = self.gerar()

        self.assertEqual(resposta.status_code, 500)
        self.assertEqual(len(chamadas), 2)
        self.assert_nada_gravado()

    def test_recusa_no_segundo_item_desfaz_o_primeiro(self):
        # O cofrinho da meta é a própria conta do salário: a transferência é recusada
        Goal.objects.filter(pk=self.a.viagem.pk).update(account=self.a.conta)

        resposta = self.gerar()

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data, erro('A conta de origem e a de destino devem ser diferentes.'))
        self.assert_nada_gravado()


class RepeticaoTests(GeracaoTestCase):

    def setUp(self):
        super().setUp()
        self.salvar_plano(plano_50_30_20(guardar_na=self.a.viagem))

    def test_mesma_chave_devolve_a_mesma_divisao_sem_gerar_de_novo(self):
        chave = uuid.uuid4()
        primeira = self.gerar(chave=chave)
        antes = Transaction.objects.count()

        segunda = self.gerar(chave=chave)

        self.assertEqual(segunda.status_code, 201)
        self.assertEqual(segunda.data, primeira.data)
        self.assertEqual(Transaction.objects.count(), antes)
        self.assertEqual(DivisaoDoSalario.objects.count(), 1)
        self.assertEqual(self.valor_da_meta(self.a.viagem), Decimal('600.00'))

    def test_mesma_chave_responde_mesmo_com_o_recebimento_excluido(self):
        chave = uuid.uuid4()
        primeira = self.gerar(chave=chave)
        recebimento_id = self.salario.pk
        Transaction.objects.filter(pk=recebimento_id).delete()

        with hoje_em(2026, 10, 10):
            segunda = self.client.post(
                URL_DIVISOES, {'receipt': str(recebimento_id), 'idempotency_key': str(chave)}, format='json',
            )

        self.assertEqual(segunda.status_code, 201)
        self.assertEqual(segunda.data['id'], primeira.data['id'])

    def test_outro_pedido_para_o_mesmo_salario_e_recusado(self):
        self.assertEqual(self.gerar(chave=uuid.uuid4()).status_code, 201)
        antes = Transaction.objects.count()

        for chave in (uuid.uuid4(), None):
            with self.subTest(chave=chave):
                resposta = self.gerar(chave=chave)

                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.data, JA_DIVIDIDO)
        self.assertEqual(Transaction.objects.count(), antes)

    def test_mesma_chave_com_outro_salario_e_recusada(self):
        chave = uuid.uuid4()
        self.gerar(chave=chave)
        outro = receita(self.a, data=date(2026, 10, 6))

        resposta = self.gerar(recebimento=outro, chave=chave)

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data, erro('Este identificador de divisão já foi usado com outro salário.'))
        self.assertEqual(DivisaoDoSalario.objects.count(), 1)


class RecusasTests(GeracaoTestCase):

    def test_parte_sem_destino_e_recusada(self):
        self.salvar_plano(plano_50_30_20())

        resposta = self.gerar()

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data, erro('Escolha o destino de todas as partes.'))
        self.assertFalse(DivisaoDoSalario.objects.exists())

    def test_destino_que_deixou_de_estar_ativo_e_recusado(self):
        casos = {
            'meta arquivada': lambda: Goal.objects.filter(pk=self.a.viagem.pk).update(is_active=False),
            'meta excluída': lambda: Goal.objects.filter(pk=self.a.viagem.pk).delete(),
            'conta inativa': lambda: Account.objects.filter(pk=self.a.poupanca.pk).update(is_active=False),
        }
        for nome, mudar in casos.items():
            with self.subTest(nome):
                self.a.viagem = Goal.objects.create(
                    user=self.a.usuario, name='Viagem A', target_amount=Decimal('6000.00'), account=self.a.cofrinho,
                )
                Account.objects.filter(pk=self.a.poupanca.pk).update(is_active=True)
                self.salvar_plano([
                    parte('Reserva', 'FIXED', '100.00', 'ACCOUNT', account=self.a.poupanca),
                    parte('Guardar', 'PERCENT', '20.00', 'GOAL', goal=self.a.viagem),
                ])
                mudar()

                resposta = self.gerar()

                self.assertEqual(resposta.status_code, 400)
                nome_da_parte = 'Reserva' if nome == 'conta inativa' else 'Guardar'
                self.assertEqual(
                    resposta.data, erro(f'O destino da parte {nome_da_parte} não está mais disponível.'),
                )
        self.assertFalse(DivisaoDoSalario.objects.exists())
        self.assertFalse(Transaction.objects.filter(divisao_do_salario__isnull=False).exists())

    def test_plano_sem_parte_que_gere_transacao_e_recusado(self):
        for partes in ([], [parte('Gastos', 'PERCENT', '80.00', 'SALARY_ACCOUNT')]):
            with self.subTest(partes=len(partes)):
                self.salvar_plano(partes)

                resposta = self.gerar()

                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.data, erro('Nenhuma parte do plano gera transação.'))

    def test_recebimento_que_nao_e_salario_recebido_e_recusado(self):
        self.salvar_plano(plano_50_30_20(guardar_na=self.a.viagem))
        sem_conta = receita(self.a)
        Transaction.objects.filter(pk=sem_conta.pk).update(account=None)
        for recebimento in (receita(self.a, status='PENDING'), receita(self.b), sem_conta):
            with self.subTest(status=recebimento.status, usuario=recebimento.user_id, pk=recebimento.pk):
                resposta = self.gerar(recebimento=recebimento)

                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.data, {'receipt': ['Escolha um salário recebido para dividir.']})
        self.assertFalse(DivisaoDoSalario.objects.exists())

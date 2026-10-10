"""
Desfazer a divisão (SALARIO-18, SALARIO-46 a SALARIO-51).
"""
from datetime import date
from decimal import Decimal
from unittest import mock

from accounts.models import Account
from api.models import TravaDePlano
from core import travas
from goals.models import Goal
from goals.services import GoalService
from salario.models import DivisaoDoSalario
from tests.permissoes.base import fechar, liberacao_de_testes
from transactions.models import Transaction

from .base import (
    URL_DIVISOES, URL_PENDENTES, URL_PLANO, SalarioTestCase, hoje_em, parte, receita, url_da_divisao,
    url_do_desfazer,
)


def erro(mensagem):
    return {'detail': mensagem, 'code': 'invalid'}


class DesfazerTestCase(SalarioTestCase):

    def setUp(self):
        super().setUp()
        # O cofrinho da Viagem é dividido com o Carro, que tem R$ 100,00
        Account.objects.filter(pk=self.a.cofrinho.pk).update(initial_balance=Decimal('100.00'), balance=Decimal('100.00'))
        self.carro = Goal.objects.create(
            user=self.a.usuario, name='Carro', target_amount=Decimal('5000.00'), account=self.a.cofrinho,
        )
        GoalService.aportar(self.carro, Decimal('100.00'), date(2026, 10, 1))
        self.salvar_plano([
            parte('Reserva', 'FIXED', '500.00', 'ACCOUNT', account=self.a.poupanca),
            parte('Guardar', 'PERCENT', '20.00', 'GOAL', goal=self.a.viagem),
        ])
        self.salario = receita(self.a)
        with hoje_em(2026, 10, 10):
            resposta = self.client.post(URL_DIVISOES, {'receipt': str(self.salario.pk)}, format='json')
        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.divisao_id = resposta.data['id']

    def desfazer(self, dia=(2026, 10, 11), divisao_id=None):
        with hoje_em(*dia):
            return self.client.post(url_do_desfazer(divisao_id or self.divisao_id), format='json')

    def geradas(self):
        return Transaction.objects.filter(divisao_do_salario=self.divisao_id)

    def estado(self):
        return {
            'conta': self.saldo(self.a.conta),
            'poupanca': self.saldo(self.a.poupanca),
            'cofrinho': self.saldo(self.a.cofrinho),
            'viagem': self.valor_da_meta(self.a.viagem),
            'carro': self.valor_da_meta(self.carro),
            'transacoes': Transaction.objects.count(),
        }


class DesfazTests(DesfazerTestCase):

    def test_remove_tudo_e_devolve_saldos_e_metas_ao_que_eram(self):
        self.assertEqual(self.geradas().count(), 4)

        resposta = self.desfazer()

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertIsNotNone(resposta.data['undone_at'])
        self.assertFalse(self.geradas().exists())
        self.assertEqual(self.saldo(self.a.conta), Decimal('3000.00'))
        self.assertEqual(self.saldo(self.a.poupanca), Decimal('0.00'))
        self.assertEqual(self.saldo(self.a.cofrinho), Decimal('100.00'))
        self.assertEqual(self.valor_da_meta(self.a.viagem), Decimal('0.00'))
        self.assertEqual(self.valor_da_meta(self.carro), Decimal('100.00'))

    def test_salario_volta_para_a_lista_e_pode_ser_dividido_de_novo(self):
        self.desfazer()

        with hoje_em(2026, 10, 11):
            pendentes = self.client.get(URL_PENDENTES).data
            nova = self.client.post(URL_DIVISOES, {'receipt': str(self.salario.pk)}, format='json')

        self.assertEqual([p['id'] for p in pendentes], [str(self.salario.pk)])
        self.assertEqual(nova.status_code, 201, nova.data)
        self.assertEqual(self.valor_da_meta(self.a.viagem), Decimal('600.00'))

    def test_no_ultimo_dia_do_prazo_ainda_desfaz(self):
        resposta = self.desfazer(dia=(2026, 10, 17))

        self.assertEqual(resposta.status_code, 200, resposta.data)

    def test_depois_de_7_dias_o_prazo_acabou(self):
        antes = self.estado()

        resposta = self.desfazer(dia=(2026, 10, 18))

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data, erro('O prazo para desfazer esta divisão acabou.'))
        self.assertEqual(self.estado(), antes)

    def test_desfazer_de_novo_responde_que_ja_foi_desfeita_sem_remover_nada(self):
        self.desfazer()
        with hoje_em(2026, 10, 11):
            self.client.post(URL_DIVISOES, {'receipt': str(self.salario.pk)}, format='json')
        antes = self.estado()

        resposta = self.desfazer()

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data, erro('Esta divisão já foi desfeita.'))
        self.assertEqual(self.estado(), antes)

    def test_divisao_de_outro_usuario_nao_e_encontrada(self):
        self.client.force_authenticate(user=self.b.usuario)

        resposta = self.desfazer()

        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(self.geradas().count(), 4)

    def test_logs_do_desfazer_nao_levam_valores_nem_nomes(self):
        with self.assertLogs('salario', level='INFO') as logs:
            self.assertEqual(self.desfazer().status_code, 200)

        texto = '\n'.join(logs.output)
        for dado in ('Viagem', 'Reserva', 'Poupança', '600.00', '500.00'):
            self.assertNotIn(dado, texto)


class RecusasTests(DesfazerTestCase):

    def assert_recusado(self, mensagem):
        antes = self.estado()

        resposta = self.desfazer()

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data, erro(mensagem))
        self.assertEqual(self.estado(), antes)
        self.assertIsNone(DivisaoDoSalario.objects.get(pk=self.divisao_id).desfeita_em)

    def test_aporte_editado_impede_o_desfazer(self):
        entrada = self.geradas().get(type='TRANSFER_IN', account=self.a.cofrinho)
        saida = self.geradas().get(type='TRANSFER_OUT', transfer_id=entrada.transfer_id)
        saida.amount = Decimal('550.00')
        saida.save()

        self.assert_recusado('O aporte em Viagem A mudou.')

    def test_transferencia_excluida_impede_o_desfazer(self):
        self.geradas().get(type='TRANSFER_IN', account=self.a.poupanca).delete()

        self.assert_recusado('A transferência para Poupança A mudou.')

    def test_transferencia_que_voltou_a_pendente_impede_o_desfazer(self):
        entrada = self.geradas().get(type='TRANSFER_IN', account=self.a.poupanca)
        entrada.status = 'PENDING'
        entrada.save()

        self.assert_recusado('A transferência para Poupança A mudou.')

    def test_meta_sem_o_valor_aportado_impede_o_desfazer(self):
        GoalService.resgatar(self.a.viagem, Decimal('100.00'), date(2026, 10, 11))

        self.assert_recusado('A meta Viagem A não tem mais o valor aportado pela divisão.')

    def test_falha_no_meio_mantem_a_divisao_inteira(self):
        original = Transaction.delete
        chamadas = []

        def falha_na_segunda(transacao, *args, **kwargs):
            chamadas.append(transacao.pk)
            if len(chamadas) == 2:
                raise RuntimeError('falha forçada')
            return original(transacao, *args, **kwargs)

        antes = self.estado()
        self.client.raise_request_exception = False
        with mock.patch.object(Transaction, 'delete', autospec=True, side_effect=falha_na_segunda):
            resposta = self.desfazer()

        self.assertEqual(resposta.status_code, 500)
        self.assertEqual(len(chamadas), 2)
        self.assertEqual(self.estado(), antes)
        self.assertEqual(self.geradas().count(), 4)
        self.assertIsNone(DivisaoDoSalario.objects.get(pk=self.divisao_id).desfeita_em)
        self.assertIsNone(self.client.get(url_da_divisao(self.divisao_id)).data['undone_at'])


class DivisoesQueAindaPodemSerDesfeitasTests(DesfazerTestCase):
    """`GET /salary/divisions/?undoable=true` (SALARIO-45, SALARIO-49)."""

    def desfaziveis(self, dia=(2026, 10, 11)):
        with hoje_em(*dia):
            resposta = self.client.get(URL_DIVISOES, {'undoable': 'true'})
        self.assertEqual(resposta.status_code, 200, resposta.data)
        return resposta.data

    def test_lista_a_divisao_no_formato_do_detalhe_ate_o_setimo_dia(self):
        detalhe = self.client.get(url_da_divisao(self.divisao_id)).data

        self.assertEqual(self.desfaziveis(), [detalhe])
        self.assertEqual(self.desfaziveis(dia=(2026, 10, 17)), [detalhe])
        self.assertEqual(detalhe['can_undo_until'], '2026-10-17')

    def test_no_oitavo_dia_a_divisao_sai_da_lista(self):
        self.assertEqual(self.desfaziveis(dia=(2026, 10, 18)), [])

    def test_divisao_desfeita_sai_da_lista(self):
        self.desfazer()

        self.assertEqual(self.desfaziveis(), [])

    def test_mais_recente_primeiro_e_sem_as_de_outro_usuario(self):
        outro_salario = receita(self.a, data=date(2026, 10, 6))
        with hoje_em(2026, 10, 12):
            nova = self.client.post(URL_DIVISOES, {'receipt': str(outro_salario.pk)}, format='json')
        self.assertEqual(nova.status_code, 201, nova.data)
        self.client.force_authenticate(user=self.b.usuario)
        with hoje_em(2026, 10, 12):
            self.client.put(URL_PLANO, {'parts': [
                parte('Reserva', 'FIXED', '100.00', 'ACCOUNT', account=self.b.poupanca),
            ]}, format='json')
            do_outro = self.client.post(URL_DIVISOES, {'receipt': str(receita(self.b).pk)}, format='json')
        self.assertEqual(do_outro.status_code, 201, do_outro.data)
        self.client.force_authenticate(user=self.a.usuario)

        ids = [d['id'] for d in self.desfaziveis(dia=(2026, 10, 12))]

        self.assertEqual(ids, [nova.data['id'], self.divisao_id])

    def test_sem_undoable_true_e_com_parametro_desconhecido_recusa(self):
        self.assertEqual(self.client.get(URL_DIVISOES).status_code, 400)
        self.assertEqual(self.client.get(URL_DIVISOES, {'undoable': 'false'}).status_code, 400)
        resposta = self.client.get(URL_DIVISOES, {'undoable': 'true', 'page': 2})
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data['detail'], 'Filtro desconhecido: page.')

    def test_com_o_recurso_travado_recebe_403(self):
        liberacao_de_testes(False)
        fechar('gestao_do_salario')
        try:
            resposta = self.client.get(URL_DIVISOES, {'undoable': 'true'})
        finally:
            TravaDePlano.objects.all().delete()
            travas.invalidar()

        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(resposta.data['code'], 'plan_locked')

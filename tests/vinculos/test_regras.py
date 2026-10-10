"""
Regras do vínculo (VINCULO-04 a VINCULO-10, VINCULO-12 a VINCULO-17,
VINCULO-22 e VINCULO-23): `transactions/vinculos.py` e os caminhos que
mudam ou excluem transações vinculadas.
"""
from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from api.exclusao import excluir_definitivamente
from api.models import RegistroDeExclusao, User
from transactions.models import RecurringTransaction, Transaction
from transactions.services import TransactionService
from transactions.vinculos import desvincular, vincular

from .base import VinculosTestCase, compra, despesa, fotografia

TIPO_NAO_VINCULAVEL = 'Só despesas e compras no cartão podem ser vinculadas.'
DEPENDENTE_COMO_PRINCIPAL = 'Uma transação dependente não pode ser principal.'
PRINCIPAL_COMO_DEPENDENTE = 'Uma transação principal não pode virar dependente.'
A_SI_MESMA = 'Uma transação não pode ser vinculada a ela mesma.'


class RegrasTestCase(VinculosTestCase):

    def setUp(self):
        super().setUp()
        self.cinema = despesa(self.a, 'Cinema', '50.00', categoria=self.a.cinema)
        self.transporte = despesa(self.a, 'Transporte', '45.00', categoria=self.a.transporte)
        self.pipoca = despesa(self.a, 'Pipoca', '20.00', categoria=self.a.alimentacao)

    def assert_recusa(self, mensagem, dependente, principal):
        with self.assertRaises(ValidationError) as ctx:
            vincular(dependente, principal)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail, {'detail': mensagem})

    def principal_de(self, transacao):
        return self.recarregar(transacao).principal_id


class TiposTests(RegrasTestCase):
    """VINCULO-05."""

    def test_receita_nao_e_dependente_nem_principal(self):
        salario = Transaction.objects.create(
            user=self.a.usuario, type='INCOME', status='COMPLETED', account=self.a.conta,
            description='Salário', amount=Decimal('3000.00'), date=date(2026, 9, 5),
        )
        self.assert_recusa(TIPO_NAO_VINCULAVEL, salario, self.cinema)
        self.assert_recusa(TIPO_NAO_VINCULAVEL, self.transporte, salario)
        self.assertIsNone(self.principal_de(salario))
        self.assertIsNone(self.principal_de(self.transporte))

    def test_transferencia_nao_se_vincula(self):
        TransactionService.create_transfer(
            self.a.usuario, self.a.conta, self.a.poupanca, Decimal('100.00'), date(2026, 9, 12),
        )
        saida = Transaction.objects.get(user=self.a.usuario, type='TRANSFER_OUT')
        entrada = Transaction.objects.get(user=self.a.usuario, type='TRANSFER_IN')
        self.assert_recusa(TIPO_NAO_VINCULAVEL, saida, self.cinema)
        self.assert_recusa(TIPO_NAO_VINCULAVEL, self.cinema, entrada)
        self.assertFalse(Transaction.objects.filter(principal__isnull=False).exists())

    def test_pagamento_de_fatura_nao_se_vincula(self):
        pagamento = Transaction.objects.create(
            user=self.a.usuario, type='INVOICE_PAYMENT', status='COMPLETED', account=self.a.conta,
            description='Pagamento da fatura', amount=Decimal('80.00'), date=date(2026, 9, 15),
        )
        self.assert_recusa(TIPO_NAO_VINCULAVEL, pagamento, self.cinema)
        self.assert_recusa(TIPO_NAO_VINCULAVEL, self.cinema, pagamento)
        self.assertFalse(Transaction.objects.filter(principal__isnull=False).exists())

    def test_despesa_e_compra_no_cartao_se_vinculam(self):
        [jantar] = compra(self.a, 'Jantar', '80.00', categoria=self.a.alimentacao)
        vincular(jantar, self.cinema)
        vincular(self.transporte, self.cinema)
        self.assertEqual(self.principal_de(jantar), self.cinema.pk)
        self.assertEqual(self.principal_de(self.transporte), self.cinema.pk)


class NivelUnicoTests(RegrasTestCase):
    """VINCULO-06 a VINCULO-08."""

    def test_dependente_nao_pode_ser_principal(self):
        vincular(self.transporte, self.cinema)
        self.assert_recusa(DEPENDENTE_COMO_PRINCIPAL, self.pipoca, self.transporte)
        self.assertIsNone(self.principal_de(self.pipoca))

    def test_principal_nao_pode_virar_dependente(self):
        vincular(self.transporte, self.cinema)
        self.assert_recusa(PRINCIPAL_COMO_DEPENDENTE, self.cinema, self.pipoca)
        self.assertIsNone(self.principal_de(self.cinema))
        self.assertEqual(self.principal_de(self.transporte), self.cinema.pk)

    def test_transacao_nao_se_vincula_a_ela_mesma(self):
        self.assert_recusa(A_SI_MESMA, self.cinema, self.cinema)
        # Duas parcelas da mesma compra são a mesma compra (VINCULO-12)
        parcelas = compra(self.a, 'Jantar', '120.00', parcelas=3)
        self.assert_recusa(A_SI_MESMA, parcelas[2], parcelas[1])
        self.assertFalse(Transaction.objects.filter(principal__isnull=False).exists())

    def test_o_banco_recusa_a_transacao_principal_dela_mesma(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Transaction.objects.filter(pk=self.cinema.pk).update(principal=self.cinema)


class TrocaERepeticaoTests(RegrasTestCase):
    """VINCULO-04, VINCULO-09 e VINCULO-10."""

    def test_ligar_a_outra_principal_troca_a_principal(self):
        vincular(self.transporte, self.cinema)
        vincular(self.transporte, self.pipoca)
        self.assertEqual(self.principal_de(self.transporte), self.pipoca.pk)
        self.assertFalse(Transaction.objects.filter(principal=self.cinema).exists())

    def test_ligar_a_mesma_principal_nao_muda_nada(self):
        vincular(self.transporte, self.cinema)
        antes = self.recarregar(self.transporte).updated_at
        vincular(self.transporte, self.cinema)
        depois = self.recarregar(self.transporte)
        self.assertEqual(depois.principal_id, self.cinema.pk)
        self.assertEqual(depois.updated_at, antes)
        self.assertEqual(Transaction.objects.filter(principal=self.cinema).count(), 1)

    def test_desfazer_remove_so_o_vinculo(self):
        vincular(self.transporte, self.cinema)
        campos = ('description', 'amount', 'date', 'category_id', 'account_id', 'status')
        antes = [getattr(self.recarregar(t), c) for t in (self.cinema, self.transporte) for c in campos]
        desvincular(self.transporte)
        depois = [getattr(self.recarregar(t), c) for t in (self.cinema, self.transporte) for c in campos]
        self.assertIsNone(self.principal_de(self.transporte))
        self.assertEqual(antes, depois)
        self.assertEqual(Transaction.objects.filter(pk__in=[self.cinema.pk, self.transporte.pk]).count(), 2)


class ParcelasERecorrenciasTests(RegrasTestCase):
    """VINCULO-12 e VINCULO-13."""

    def test_parcela_3_de_10_como_dependente_liga_a_compra_pela_raiz(self):
        parcelas = compra(self.a, 'Hotel', '1000.00', parcelas=10, categoria=self.a.lazer)
        vincular(parcelas[2], self.cinema)
        raiz = self.recarregar(parcelas[0])
        self.assertEqual(raiz.principal_id, self.cinema.pk)
        self.assertEqual(
            Transaction.objects.filter(principal__isnull=False).values_list('pk', flat=True).get(), raiz.pk,
        )

    def test_parcela_como_principal_liga_a_dependente_a_raiz(self):
        parcelas = compra(self.a, 'Viagem', '300.00', parcelas=3, categoria=self.a.lazer)
        vincular(self.transporte, parcelas[1])
        self.assertEqual(self.principal_de(self.transporte), parcelas[0].pk)

    def test_ocorrencia_recorrente_liga_so_ela(self):
        resposta = self.client.post('/api/transactions/', {
            'type': 'EXPENSE', 'status': 'COMPLETED', 'description': 'Estacionamento', 'amount': '15.00',
            'date': '2026-09-01', 'account': str(self.a.conta.pk), 'category': str(self.a.transporte.pk),
            'is_recurring': True, 'frequency': 'MONTHLY',
        }, format='json')
        self.assertEqual(resposta.status_code, 201, resposta.data)
        serie = RecurringTransaction.objects.get(user=self.a.usuario)
        ocorrencias = list(Transaction.objects.filter(recurring_source=serie).order_by('date'))
        self.assertEqual(len(ocorrencias), 12)

        vincular(ocorrencias[3], self.cinema)

        ligadas = Transaction.objects.filter(recurring_source=serie, principal__isnull=False)
        self.assertEqual(list(ligadas.values_list('pk', flat=True)), [ocorrencias[3].pk])


class ExclusaoETrocaDeTipoTests(RegrasTestCase):
    """VINCULO-14 a VINCULO-16."""

    def test_excluir_a_principal_mantem_as_dependentes_sem_vinculo(self):
        vincular(self.transporte, self.cinema)
        vincular(self.pipoca, self.cinema)
        resposta = self.client.delete(f'/api/transactions/{self.cinema.pk}/')
        self.assertEqual(resposta.status_code, 204)
        self.assertFalse(Transaction.objects.filter(pk=self.cinema.pk).exists())
        for dependente in (self.transporte, self.pipoca):
            self.assertIsNone(self.principal_de(dependente))

    def test_excluir_a_compra_principal_mantem_as_dependentes(self):
        parcelas = compra(self.a, 'Show', '300.00', parcelas=3, categoria=self.a.lazer)
        vincular(self.transporte, parcelas[2])
        resposta = self.client.delete(f'/api/transactions/{parcelas[1].pk}/')
        self.assertEqual(resposta.status_code, 204)
        self.assertFalse(Transaction.objects.filter(pk__in=[p.pk for p in parcelas]).exists())
        self.assertIsNone(self.principal_de(self.transporte))

    def test_excluir_a_dependente_nao_muda_a_principal(self):
        vincular(self.transporte, self.cinema)
        vincular(self.pipoca, self.cinema)
        antes = Transaction.objects.filter(pk=self.cinema.pk).values().get()
        resposta = self.client.delete(f'/api/transactions/{self.transporte.pk}/')
        self.assertEqual(resposta.status_code, 204)
        self.assertEqual(Transaction.objects.filter(pk=self.cinema.pk).values().get(), antes)
        self.assertEqual(
            list(Transaction.objects.filter(principal=self.cinema).values_list('pk', flat=True)), [self.pipoca.pk],
        )

    def test_despesa_que_vira_receita_perde_os_vinculos(self):
        vincular(self.transporte, self.cinema)
        vincular(self.pipoca, self.cinema)
        # Como dependente
        resposta = self.client.patch(f'/api/transactions/{self.pipoca.pk}/', {'type': 'INCOME'}, format='json')
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertIsNone(self.principal_de(self.pipoca))
        # Como principal
        resposta = self.client.patch(f'/api/transactions/{self.cinema.pk}/', {'type': 'INCOME'}, format='json')
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertIsNone(self.principal_de(self.transporte))
        self.assertEqual(Transaction.objects.filter(pk__in=[
            self.cinema.pk, self.transporte.pk, self.pipoca.pk,
        ]).count(), 3)

    def test_serie_que_vira_receita_perde_os_vinculos_das_pendentes(self):
        resposta = self.client.post('/api/transactions/', {
            'type': 'EXPENSE', 'status': 'COMPLETED', 'description': 'Aula', 'amount': '30.00',
            'date': '2026-09-01', 'account': str(self.a.conta.pk), 'is_recurring': True, 'frequency': 'MONTHLY',
        }, format='json')
        self.assertEqual(resposta.status_code, 201, resposta.data)
        serie = RecurringTransaction.objects.get(user=self.a.usuario)
        pendente = Transaction.objects.filter(recurring_source=serie, status='PENDING').order_by('date').first()
        vincular(pendente, self.cinema)
        resposta = self.client.patch('/api/transactions/bulk-update/', {
            'recurring_source': str(serie.pk), 'type': 'INCOME',
        }, format='json')
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertIsNone(self.principal_de(pendente))


class EfeitosTests(RegrasTestCase):
    """VINCULO-17, VINCULO-22 e VINCULO-23."""

    def test_saldos_faturas_e_orcamentos_iguais_ao_vincular_trocar_e_desfazer(self):
        parcelas = compra(self.a, 'Jantar', '120.00', parcelas=3, categoria=self.a.lazer)
        inicial = fotografia(self.a)
        self.assertEqual(inicial[0][self.a.conta.pk], Decimal('885.00'))

        vincular(parcelas[1], self.cinema)
        self.assertEqual(fotografia(self.a), inicial)
        vincular(parcelas[0], self.pipoca)
        self.assertEqual(fotografia(self.a), inicial)
        vincular(self.transporte, self.cinema)
        self.assertEqual(fotografia(self.a), inicial)
        desvincular(parcelas[2])
        desvincular(self.transporte)
        self.assertEqual(fotografia(self.a), inicial)

    def test_exclusao_da_conta_apaga_as_transacoes_vinculadas(self):
        vincular(self.transporte, self.cinema)
        outro_cinema = despesa(self.b, 'Cinema B', '50.00')
        outro_transporte = despesa(self.b, 'Transporte B', '45.00')
        vincular(outro_transporte, outro_cinema)
        usuario_id = self.a.usuario.pk

        excluir_definitivamente(self.a.usuario, RegistroDeExclusao.ROTINA)

        self.assertFalse(User.objects.filter(pk=usuario_id).exists())
        self.assertFalse(Transaction.objects.filter(user_id=usuario_id).exists())
        self.assertEqual(self.principal_de(outro_transporte), outro_cinema.pk)

    def test_logs_do_vinculo_nao_tem_descricao_nem_valor(self):
        with self.assertLogs('transactions.vinculos', level='INFO') as logs:
            vincular(self.transporte, self.cinema)
            vincular(self.transporte, self.pipoca)
            desvincular(self.transporte)
        texto = '\n'.join(logs.output)
        self.assertIn(str(self.transporte.pk), texto)
        for dado in ('Cinema', 'Transporte', 'Pipoca', '50.00', '45.00', '20.00', '50,00', '45,00'):
            self.assertNotIn(dado, texto)

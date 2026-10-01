"""
Ajuste de saldo (SALDO-40 a SALDO-42, SALDO-35).

O usuário informa o novo saldo em `POST /api/accounts/{id}/adjust-balance/`;
a diferença, calculada em decimal, vira uma transação efetivada com a data
de hoje no fuso de Brasília. O relógio fica em 2026-10-01 02:00 UTC, quando
em Brasília ainda é 2026-09-30.
"""
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from accounts.models import Account
from core.fields import CONTA_NAO_ENCONTRADA
from transactions.models import Transaction
from tests.saldo.base import SaldoTestCase

HOJE_EM_BRASILIA = date(2026, 9, 30)
JA_NESSE_VALOR = 'O saldo já está nesse valor.'


class AjusteDeSaldoTests(SaldoTestCase):

    def setUp(self):
        super().setUp()
        self.conta = Account.objects.create(
            user=self.a.usuario, name='Banco', type='CHECKING',
            initial_balance=Decimal('1000.10'),
        )

    def ajustar(self, novo_saldo, conta=None):
        conta = conta or self.conta
        with mock.patch(
            'django.utils.timezone.now',
            return_value=datetime(2026, 10, 1, 2, 0, tzinfo=dt_timezone.utc),
        ):
            return self.cliente.post(
                f'/api/accounts/{conta.id}/adjust-balance/', {'new_balance': novo_saldo}, format='json',
            )

    def ajustes(self, conta=None):
        return list(
            Transaction.objects.filter(account=conta or self.conta)
            .values_list('type', 'amount', 'status', 'date', 'description', 'category_id', 'user_id'),
        )

    def test_ajuste_para_baixo_com_centavos_vira_saida_da_diferenca(self):
        resp = self.ajustar('999.90')

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(self.ajustes(), [
            ('EXPENSE', Decimal('0.20'), 'COMPLETED', HOJE_EM_BRASILIA, 'Ajuste de saldo', None, self.a.usuario.id),
        ])
        self.assertEqual(self.saldo(self.conta), Decimal('999.90'))
        self.assertEqual(Decimal(resp.data['balance']), Decimal('999.90'))

    def test_ajuste_para_cima_vira_entrada_da_diferenca(self):
        resp = self.ajustar('1250.35')

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(self.ajustes(), [
            ('INCOME', Decimal('250.25'), 'COMPLETED', HOJE_EM_BRASILIA, 'Ajuste de saldo', None, self.a.usuario.id),
        ])
        self.assertEqual(self.saldo(self.conta), Decimal('1250.35'))

    def test_ajuste_para_saldo_negativo_e_permitido(self):
        resp = self.ajustar('-50.25')

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(self.ajustes(), [
            ('EXPENSE', Decimal('1050.35'), 'COMPLETED', HOJE_EM_BRASILIA, 'Ajuste de saldo', None, self.a.usuario.id),
        ])
        self.assertEqual(self.saldo(self.conta), Decimal('-50.25'))

    def test_ajuste_parte_do_saldo_guardado_atual(self):
        """A diferença considera as transações já lançadas, não só o saldo inicial."""
        self.lancar(self.conta, 'INCOME', '100.00')

        self.ajustar('1000.10')

        self.assertEqual(
            list(Transaction.objects.filter(account=self.conta, description='Ajuste de saldo')
                 .values_list('type', 'amount')),
            [('EXPENSE', Decimal('100.00'))],
        )
        self.assertEqual(self.saldo(self.conta), Decimal('1000.10'))

    def test_mesmo_saldo_nao_registra_transacao(self):
        resp = self.ajustar('1000.10')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data, {'message': JA_NESSE_VALOR})
        self.assertEqual(self.ajustes(), [])
        self.assertEqual(self.saldo(self.conta), Decimal('1000.10'))

    def test_conta_excluida_recebe_400(self):
        Account.objects.filter(pk=self.conta.pk).update(is_active=False)

        resp = self.ajustar('0.00')

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {'detail': CONTA_NAO_ENCONTRADA})
        self.assertEqual(self.ajustes(), [])
        self.assertEqual(self.saldo(self.conta), Decimal('1000.10'))

    def test_novo_saldo_com_mais_de_duas_casas_recebe_400(self):
        resp = self.ajustar('999.905')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('new_balance', resp.data)
        self.assertEqual(self.ajustes(), [])

    def test_conta_de_outro_usuario_recebe_404(self):
        resp = self.ajustar('0.00', conta=self.b.conta)

        self.assertEqual(resp.status_code, 404)
        self.assertEqual(self.ajustes(self.b.conta), [])
        self.assertEqual(self.saldo(self.b.conta), Decimal('1000.00'))

    def test_id_malformado_recebe_404(self):
        resp = self.cliente.post(
            '/api/accounts/nao-e-um-uuid/adjust-balance/', {'new_balance': '0.00'}, format='json',
        )

        self.assertEqual(resp.status_code, 404)

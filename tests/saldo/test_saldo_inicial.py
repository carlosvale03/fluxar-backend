"""
Saldo inicial e criação da conta (SALDO-43, SALDO-01).

Mudar o saldo inicial muda o saldo atual pela mesma diferença, e a conta
recém-criada já responde com o saldo igual ao saldo inicial.
"""
from decimal import Decimal

from accounts.models import Account
from tests.saldo.base import SaldoTestCase

URL = '/api/accounts/'


class SaldoInicialTests(SaldoTestCase):

    def setUp(self):
        super().setUp()
        self.lancar(self.a.conta, 'EXPENSE', '300.00')
        self.lancar(self.a.conta, 'INCOME', '80.00', status='PENDING')
        self.assertEqual(self.saldo(self.a.conta), Decimal('700.00'))

    def mudar_saldo_inicial(self, valor):
        resp = self.cliente.patch(f'{URL}{self.a.conta.id}/', {'initial_balance': valor}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp

    def test_subir_o_saldo_inicial_sobe_o_saldo_pela_diferenca(self):
        resp = self.mudar_saldo_inicial('1200.00')
        self.assertEqual(self.saldo(self.a.conta), Decimal('900.00'))
        self.assertEqual(resp.data['balance'], '900.00')

    def test_baixar_o_saldo_inicial_baixa_o_saldo_pela_diferenca(self):
        self.mudar_saldo_inicial('850.00')
        self.assertEqual(self.saldo(self.a.conta), Decimal('550.00'))


class CriacaoDaContaTests(SaldoTestCase):

    def test_resposta_da_criacao_traz_o_saldo_igual_ao_saldo_inicial(self):
        resp = self.cliente.post(URL, {
            'name': 'Nova', 'type': 'CHECKING', 'initial_balance': '350.50',
        }, format='json')

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['balance'], '350.50')
        self.assertEqual(Account.objects.get(pk=resp.data['id']).balance, Decimal('350.50'))

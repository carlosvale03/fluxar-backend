"""
Exclusão de conta (SALDO-32, SALDO-33, SALDO-34, AD-003).

A conta só sai com saldo zero e sem transações pendentes. Excluída, ela some
da lista de contas e as transações efetivadas dela continuam no histórico.
"""
from decimal import Decimal

from accounts.models import Account
from transactions.models import Transaction
from tests.saldo.base import SaldoTestCase

URL = '/api/accounts/'
SALDO_NAO_ZERADO = 'Zere o saldo antes de excluir a conta: transfira ou ajuste o valor restante.'
COM_PENDENTES = 'Resolva as transações pendentes antes de excluir a conta: efetive, mova ou exclua cada uma.'


class ExclusaoDeContaTests(SaldoTestCase):

    def excluir(self, conta):
        return self.cliente.delete(f'{URL}{conta.id}/')

    def ids_na_lista(self):
        resp = self.cliente.get(URL)
        self.assertEqual(resp.status_code, 200)
        return {item['id'] for item in resp.data}

    def assert_recusa(self, conta, mensagem):
        saldo = self.saldo(conta)
        resp = self.excluir(conta)
        self.assertEqual(resp.status_code, 400, getattr(resp, 'data', None))
        self.assertEqual(resp.data, {'detail': mensagem})
        self.assertTrue(Account.objects.get(pk=conta.pk).is_active)
        self.assertEqual(self.saldo(conta), saldo)
        self.assertIn(str(conta.id), self.ids_na_lista())

    def test_conta_com_saldo_positivo_nao_e_excluida(self):
        self.assertEqual(self.saldo(self.a.conta), Decimal('1000.00'))
        self.assert_recusa(self.a.conta, SALDO_NAO_ZERADO)

    def test_conta_com_saldo_negativo_nao_e_excluida(self):
        self.lancar(self.a.poupanca, 'EXPENSE', '50.00')
        self.assertEqual(self.saldo(self.a.poupanca), Decimal('-50.00'))
        self.assert_recusa(self.a.poupanca, SALDO_NAO_ZERADO)

    def test_conta_com_transacao_pendente_nao_e_excluida(self):
        self.lancar(self.a.poupanca, 'EXPENSE', '50.00', status='PENDING')
        self.assertEqual(self.saldo(self.a.poupanca), Decimal('0.00'))
        self.assert_recusa(self.a.poupanca, COM_PENDENTES)

    def test_conta_zerada_e_sem_pendentes_sai_da_lista_e_mantem_o_historico(self):
        receita = self.lancar(self.a.poupanca, 'INCOME', '100.00')
        despesa = self.lancar(self.a.poupanca, 'EXPENSE', '100.00')
        self.assertEqual(self.saldo(self.a.poupanca), Decimal('0.00'))

        resp = self.excluir(self.a.poupanca)

        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Account.objects.get(pk=self.a.poupanca.pk).is_active)
        self.assertNotIn(str(self.a.poupanca.id), self.ids_na_lista())
        historico = self.cliente.get('/api/transactions/', {'account': str(self.a.poupanca.id)})
        self.assertEqual(historico.status_code, 200)
        self.assertEqual(
            {item['id'] for item in historico.data['results']}, {str(receita.id), str(despesa.id)},
        )
        self.assertEqual(
            set(Transaction.objects.filter(account=self.a.poupanca).values_list('status', flat=True)),
            {'COMPLETED'},
        )

    def test_patch_com_is_active_falso_nao_exclui_a_conta(self):
        resp = self.cliente.patch(f'{URL}{self.a.poupanca.id}/', {'is_active': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(Account.objects.get(pk=self.a.poupanca.pk).is_active)
        self.assertIn(str(self.a.poupanca.id), self.ids_na_lista())

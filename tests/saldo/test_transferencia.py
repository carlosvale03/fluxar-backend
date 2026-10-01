"""
Transferências (SALDO-11 a SALDO-17).

Uma transferência tem duas pernas ligadas pelo mesmo `transfer_id`: a saída
na conta de origem e a entrada na de destino. Criar, editar ou excluir uma
transferência nunca muda a soma dos saldos das contas do usuário.
"""
from decimal import Decimal

from django.db.models import Sum

from accounts.models import Account
from goals.models import Goal, GoalDeposit
from transactions.models import Transaction
from tests.saldo.base import SaldoTestCase, URL_TRANSACOES

URL_TRANSFERENCIA = f'{URL_TRANSACOES}transfer/'
MESMA_CONTA = 'A conta de origem e a de destino devem ser diferentes.'


class TransferenciaTestCase(SaldoTestCase):

    def soma(self, usuario=None):
        """A soma dos saldos de todas as contas do usuário (A por padrão)."""
        usuario = usuario or self.a.usuario
        return Account.objects.filter(user=usuario).aggregate(total=Sum('balance'))['total']

    def estado(self):
        return (
            sorted(Account.objects.values_list('id', 'balance')),
            sorted(Transaction.objects.values_list('id', 'type', 'status', 'account_id', 'amount', 'date', 'description')),
            sorted(Goal.objects.values_list('id', 'current_amount')),
            GoalDeposit.objects.count(),
        )


class CriacaoDeTransferenciaTests(TransferenciaTestCase):

    def transferir(self, **extra):
        corpo = {
            'account_from': str(self.a.conta.id), 'account_to': str(self.a.poupanca.id),
            'amount': '100.00', 'date': '2026-09-15', 'description': 'Reserva do mês',
        }
        corpo.update(extra)
        return self.cliente.post(URL_TRANSFERENCIA, corpo, format='json')

    def test_cria_a_saida_na_origem_e_a_entrada_no_destino(self):
        soma = self.soma()
        resp = self.transferir()
        self.assertEqual(resp.status_code, 201, resp.data)

        self.assertEqual(self.saldo(self.a.conta), Decimal('900.00'))
        self.assertEqual(self.saldo(self.a.poupanca), Decimal('100.00'))
        self.assertEqual(self.soma(), soma)

        saida = Transaction.objects.get(user=self.a.usuario, type='TRANSFER_OUT')
        entrada = Transaction.objects.get(user=self.a.usuario, type='TRANSFER_IN')
        self.assertEqual(saida.account_id, self.a.conta.id)
        self.assertEqual(entrada.account_id, self.a.poupanca.id)
        self.assertIsNotNone(saida.transfer_id)
        self.assertEqual(saida.transfer_id, entrada.transfer_id)
        self.assertEqual((saida.amount, entrada.amount), (Decimal('100.00'), Decimal('100.00')))
        self.assertEqual((saida.status, entrada.status), ('COMPLETED', 'COMPLETED'))

    def test_respeita_a_descricao_enviada_nas_duas_pernas(self):
        self.transferir(description='Reserva do mês')

        descricoes = set(
            Transaction.objects.filter(user=self.a.usuario, transfer_id__isnull=False)
            .values_list('description', flat=True)
        )
        self.assertEqual(descricoes, {'Reserva do mês'})

    def test_origem_igual_ao_destino_recusada(self):
        antes = self.estado()
        resp = self.transferir(account_to=str(self.a.conta.id))

        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data, {'detail': MESMA_CONTA})
        self.assertEqual(self.estado(), antes)


class AporteEResgateNoProprioCofrinhoTests(TransferenciaTestCase):
    """Aporte e resgate seguem as regras de transferência (edge case da spec)."""

    def setUp(self):
        super().setUp()
        Goal.objects.filter(pk=self.a.meta.pk).update(current_amount=Decimal('500.00'))

    def assert_recusa(self, url, corpo):
        antes = self.estado()
        resp = self.cliente.post(url, corpo, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data, {'detail': MESMA_CONTA})
        self.assertEqual(self.estado(), antes)

    def test_aporte_a_partir_do_proprio_cofrinho_recusado(self):
        self.assert_recusa(f'/api/goals/{self.a.meta.id}/deposit/', {
            'account_id': str(self.a.cofrinho.id), 'amount': '100.00', 'date': '2026-09-15',
        })

    def test_resgate_para_o_proprio_cofrinho_recusado(self):
        self.assert_recusa(f'/api/goals/{self.a.meta.id}/withdraw/', {
            'account_to': str(self.a.cofrinho.id), 'amount': '100.00', 'date': '2026-09-15',
        })

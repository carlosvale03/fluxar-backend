"""
Transferências (SALDO-11 a SALDO-17).

Uma transferência tem duas pernas ligadas pelo mesmo `transfer_id`: a saída
na conta de origem e a entrada na de destino. Criar, editar ou excluir uma
transferência nunca muda a soma dos saldos das contas do usuário.
"""
from decimal import Decimal

from django.db.models import Sum
from rest_framework.exceptions import ValidationError

from accounts.models import Account
from goals.models import Goal, GoalDeposit
from transactions.models import Transaction
from transactions.services import TransactionService
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


CONTA_NAO_ENCONTRADA = 'Conta não encontrada.'
TIPO_NAO_ALTERAVEL = 'O tipo só pode ser trocado entre receita e despesa.'


class EdicaoDeTransferenciaTests(TransferenciaTestCase):
    """
    Editar uma perna aplica valor, data e status às duas (SALDO-13, SALDO-15)
    e move o efeito da perna cuja conta mudou (SALDO-14). A descrição é de
    cada perna.
    """

    def setUp(self):
        super().setUp()
        self.c = Account.objects.create(
            user=self.a.usuario, name='Conta C', type='CHECKING', initial_balance=Decimal('0.00'),
        )
        resp = self.cliente.post(URL_TRANSFERENCIA, {
            'account_from': str(self.a.conta.id), 'account_to': str(self.a.poupanca.id),
            'amount': '100.00', 'date': '2026-09-15', 'description': 'Reserva',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.saida = Transaction.objects.get(user=self.a.usuario, type='TRANSFER_OUT')
        self.entrada = Transaction.objects.get(user=self.a.usuario, type='TRANSFER_IN')
        self.soma_inicial = self.soma()

    def editar(self, perna, corpo, metodo='patch'):
        resp = getattr(self.cliente, metodo)(f'{URL_TRANSACOES}{perna.id}/', corpo, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.saida.refresh_from_db()
        self.entrada.refresh_from_db()
        return resp

    def assert_saldos(self, a, b, c):
        self.assertEqual(
            (self.saldo(self.a.conta), self.saldo(self.a.poupanca), self.saldo(self.c)),
            (Decimal(a), Decimal(b), Decimal(c)),
        )
        self.assertEqual(self.soma(), self.soma_inicial)

    def test_valor_destino_origem_e_status_em_sequencia(self):
        self.assert_saldos('900.00', '100.00', '0.00')

        # Valor de R$ 100,00 para R$ 150,00 nas duas pernas
        self.editar(self.saida, {'amount': '150.00'})
        self.assertEqual((self.saida.amount, self.entrada.amount), (Decimal('150.00'), Decimal('150.00')))
        self.assert_saldos('850.00', '150.00', '0.00')

        # Destino de B para C
        self.editar(self.saida, {'target_account_id': str(self.c.id)})
        self.assertEqual(self.entrada.account_id, self.c.id)
        self.assertEqual(self.saida.account_id, self.a.conta.id)
        self.assert_saldos('850.00', '0.00', '150.00')

        # Origem de A para B
        self.editar(self.saida, {'account': str(self.a.poupanca.id)})
        self.assertEqual((self.saida.account_id, self.entrada.account_id), (self.a.poupanca.id, self.c.id))
        self.assert_saldos('1000.00', '-150.00', '150.00')

        # Status pela perna de entrada: as duas ficam pendentes
        self.editar(self.entrada, {'status': 'PENDING'})
        self.assertEqual((self.saida.status, self.entrada.status), ('PENDING', 'PENDING'))
        self.assert_saldos('1000.00', '0.00', '0.00')

        # E voltam a efetivadas pela perna de saída
        self.editar(self.saida, {'status': 'COMPLETED'})
        self.assertEqual((self.saida.status, self.entrada.status), ('COMPLETED', 'COMPLETED'))
        self.assert_saldos('1000.00', '-150.00', '150.00')

    def test_put_pela_perna_de_entrada_como_a_tela_envia(self):
        # A tela edita a perna de entrada com a conta dela em `account` e a
        # da outra perna em `target_account_id`
        self.editar(self.entrada, {
            'type': 'TRANSFER_IN', 'status': 'COMPLETED', 'description': 'Reserva para C',
            'amount': '120.00', 'date': '2026-09-20',
            'account': str(self.c.id), 'target_account_id': str(self.a.poupanca.id),
        }, metodo='put')

        self.assertEqual((self.entrada.account_id, self.saida.account_id), (self.c.id, self.a.poupanca.id))
        self.assertEqual((self.saida.amount, self.entrada.amount), (Decimal('120.00'), Decimal('120.00')))
        self.assertEqual((self.saida.date.isoformat(), self.entrada.date.isoformat()), ('2026-09-20', '2026-09-20'))
        # A descrição é de cada perna
        self.assertEqual((self.entrada.description, self.saida.description), ('Reserva para C', 'Reserva'))
        self.assert_saldos('1000.00', '-120.00', '120.00')

    def test_mudar_a_data_muda_as_duas_pernas(self):
        self.editar(self.saida, {'date': '2026-09-30'})
        self.assertEqual(
            (self.saida.date.isoformat(), self.entrada.date.isoformat()), ('2026-09-30', '2026-09-30'),
        )

    def test_mudar_o_tipo_de_uma_perna_recusado(self):
        antes = self.estado()
        for perna, tipo in ((self.saida, 'TRANSFER_IN'), (self.entrada, 'TRANSFER_OUT'), (self.saida, 'EXPENSE')):
            with self.subTest(perna=perna.type, tipo=tipo):
                resp = self.cliente.patch(f'{URL_TRANSACOES}{perna.id}/', {'type': tipo}, format='json')
                self.assertEqual(resp.status_code, 400, resp.data)
                self.assertEqual(resp.data['type'], [TIPO_NAO_ALTERAVEL])
                self.assertEqual(self.estado(), antes)

    def test_servico_recusa_mudar_o_tipo_mesmo_fora_do_serializer(self):
        antes = self.estado()
        with self.assertRaises(ValidationError) as erro:
            TransactionService.editar_transferencia(self.saida, {'type': 'EXPENSE'}, self.a.usuario)
        self.assertEqual(erro.exception.detail, {'type': [TIPO_NAO_ALTERAVEL]})
        self.assertEqual(self.estado(), antes)

    def test_as_duas_pernas_na_mesma_conta_recusado(self):
        antes = self.estado()
        for perna, corpo in (
            (self.saida, {'target_account_id': str(self.a.conta.id)}),
            (self.saida, {'account': str(self.a.poupanca.id)}),
            (self.entrada, {'account': str(self.a.conta.id)}),
            (self.saida, {'account': str(self.c.id), 'target_account_id': str(self.c.id)}),
        ):
            with self.subTest(perna=perna.type, corpo=corpo):
                resp = self.cliente.patch(f'{URL_TRANSACOES}{perna.id}/', corpo, format='json')
                self.assertEqual(resp.status_code, 400, resp.data)
                self.assertEqual(resp.data, {'detail': MESMA_CONTA})
                self.assertEqual(self.estado(), antes)

    def test_conta_excluida_ou_de_outro_usuario_recusada(self):
        excluida = Account.objects.create(
            user=self.a.usuario, name='Antiga A', type='CHECKING', initial_balance=Decimal('0.00'),
        )
        Account.objects.filter(pk=excluida.pk).update(is_active=False)
        antes = self.estado()
        for campo, conta in (
            ('account', excluida), ('target_account_id', excluida),
            ('account', self.b.conta), ('target_account_id', self.b.conta),
        ):
            with self.subTest(campo=campo, conta=conta.name):
                resp = self.cliente.patch(f'{URL_TRANSACOES}{self.saida.id}/', {campo: str(conta.id)}, format='json')
                self.assertEqual(resp.status_code, 400, resp.data)
                self.assertEqual(resp.data[campo], [CONTA_NAO_ENCONTRADA])
                self.assertEqual(self.estado(), antes)


class ExclusaoDeTransferenciaTests(TransferenciaTestCase):
    """Excluir uma perna exclui as duas e desfaz o efeito nas duas contas (SALDO-16)."""

    def transferir(self, valor):
        resp = self.cliente.post(URL_TRANSFERENCIA, {
            'account_from': str(self.a.conta.id), 'account_to': str(self.a.poupanca.id),
            'amount': valor, 'date': '2026-09-15', 'description': 'Reserva',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        pernas = Transaction.objects.filter(user=self.a.usuario, transfer_id__isnull=False).order_by('-created_at')
        transfer_id = pernas.first().transfer_id
        return (
            Transaction.objects.get(transfer_id=transfer_id, type='TRANSFER_OUT'),
            Transaction.objects.get(transfer_id=transfer_id, type='TRANSFER_IN'),
        )

    def assert_exclui(self, perna, outra):
        soma = self.soma()
        resp = self.cliente.delete(f'{URL_TRANSACOES}{perna.id}/')
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Transaction.objects.filter(pk__in=[perna.pk, outra.pk]).exists())
        self.assertEqual(self.soma(), soma)

    def test_excluir_a_perna_de_saida_exclui_as_duas(self):
        saida, entrada = self.transferir('100.00')
        self.assertEqual((self.saldo(self.a.conta), self.saldo(self.a.poupanca)), (Decimal('900.00'), Decimal('100.00')))

        self.assert_exclui(saida, entrada)
        self.assertEqual((self.saldo(self.a.conta), self.saldo(self.a.poupanca)), (Decimal('1000.00'), Decimal('0.00')))

    def test_excluir_a_perna_de_entrada_exclui_as_duas(self):
        # Outra transferência continua e só a excluída sai do saldo
        self.transferir('30.00')
        saida, entrada = self.transferir('100.00')
        self.assertEqual((self.saldo(self.a.conta), self.saldo(self.a.poupanca)), (Decimal('870.00'), Decimal('130.00')))

        self.assert_exclui(entrada, saida)
        self.assertEqual((self.saldo(self.a.conta), self.saldo(self.a.poupanca)), (Decimal('970.00'), Decimal('30.00')))
        self.assertEqual(Transaction.objects.filter(user=self.a.usuario, transfer_id__isnull=False).count(), 2)

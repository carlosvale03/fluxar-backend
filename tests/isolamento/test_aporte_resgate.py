from decimal import Decimal

from accounts.models import Account
from goals.models import Goal, GoalDeposit
from transactions.models import Transaction
from tests.isolamento.base import DoisUsuariosTestCase


class AporteEResgateTests(DoisUsuariosTestCase):
    """
    Aporte (`deposit`) aceita a conta em `account_id` ou `account_from`;
    resgate (`withdraw`), em `account_to` ou `account_id`. O erro sai no campo
    que a requisição usou (AD-010).
    """

    def setUp(self):
        self.cliente = self.como(self.a.usuario)
        # Saldo na meta de A, para que o resgate seja possível
        Goal.objects.filter(pk=self.a.meta.pk).update(current_amount=Decimal('200.00'))

    def url(self, acao):
        return f'/api/goals/{self.a.meta.id}/{acao}/'

    def assert_recusa(self, acao, campo):
        total_movimentos = GoalDeposit.objects.count()
        total_transacoes = Transaction.objects.count()
        dados = {'amount': '50.00', 'date': '2026-09-15'}

        resp_inexistente = self.cliente.post(self.url(acao), {**dados, campo: self.ID_INEXISTENTE}, format='json')
        resp = self.cliente.post(self.url(acao), {**dados, campo: str(self.b.conta.id)}, format='json')

        self.assert_mesma_recusa(resp, resp_inexistente, campo, 'Conta não encontrada.')
        self.assertEqual(GoalDeposit.objects.count(), total_movimentos)
        self.assertEqual(Transaction.objects.count(), total_transacoes)
        self.assertEqual(Goal.objects.get(pk=self.a.meta.pk).current_amount, Decimal('200.00'))
        self.assertEqual(Account.objects.get(pk=self.b.conta.pk).balance, Decimal('1000.00'))

    def assert_movimento_feito(self, acao, campo, tipo, valor_esperado_na_meta):
        resp = self.cliente.post(self.url(acao), {
            'amount': '50.00', 'date': '2026-09-15', campo: str(self.a.conta.id),
        }, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        movimento = GoalDeposit.objects.get(goal=self.a.meta)
        self.assertEqual((movimento.type, movimento.account, movimento.amount), (tipo, self.a.conta, Decimal('50.00')))
        pernas = Transaction.objects.filter(transfer_id=movimento.transaction_id)
        self.assertEqual({t.account for t in pernas}, {self.a.conta, self.a.cofrinho})
        self.assertEqual({t.user for t in pernas}, {self.a.usuario})
        self.assertEqual(Goal.objects.get(pk=self.a.meta.pk).current_amount, valor_esperado_na_meta)

    # --- Aporte ---

    def test_aporte_com_conta_de_b_em_account_id_e_recusado(self):
        self.assert_recusa('deposit', 'account_id')

    def test_aporte_com_conta_de_b_em_account_from_e_recusado(self):
        self.assert_recusa('deposit', 'account_from')

    def test_aporte_com_conta_de_a_em_account_id_continua_funcionando(self):
        self.assert_movimento_feito('deposit', 'account_id', 'DEPOSIT', Decimal('250.00'))

    def test_aporte_com_conta_de_a_em_account_from_continua_funcionando(self):
        self.assert_movimento_feito('deposit', 'account_from', 'DEPOSIT', Decimal('250.00'))

    # --- Resgate ---

    def test_resgate_com_conta_de_b_em_account_to_e_recusado(self):
        self.assert_recusa('withdraw', 'account_to')

    def test_resgate_com_conta_de_b_em_account_id_e_recusado(self):
        self.assert_recusa('withdraw', 'account_id')

    def test_resgate_com_conta_de_a_em_account_to_continua_funcionando(self):
        self.assert_movimento_feito('withdraw', 'account_to', 'WITHDRAWAL', Decimal('150.00'))

    def test_resgate_com_conta_de_a_em_account_id_continua_funcionando(self):
        self.assert_movimento_feito('withdraw', 'account_id', 'WITHDRAWAL', Decimal('150.00'))

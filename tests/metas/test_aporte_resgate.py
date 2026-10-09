"""
Aporte e resgate com outra conta ou com o saldo livre do cofrinho (META-12 a
META-21).

O aporte aceita a conta em `account_id` ou `account_from`, ou o saldo livre
com `from_free_balance: true`; o resgate, em `account_to` ou `account_id`, ou
o saldo livre com `to_free_balance: true`.
"""
from decimal import Decimal

from accounts.models import Account
from goals.models import Goal, GoalDeposit
from goals.valores import recalcular, saldo_livre
from transactions.models import Transaction
from tests.metas.base import DIA, MetasTestCase, registrar, transferir

CONTA_NAO_ENCONTRADA = ['Conta não encontrada.']
MESMA_CONTA = 'A conta de origem e a de destino devem ser diferentes.'


class AporteEResgateTests(MetasTestCase):

    def aportar(self, **corpo):
        return self.client.post(f'/api/goals/{self.a.meta.pk}/deposit/', {'date': '2026-09-15', **corpo}, format='json')

    def resgatar(self, **corpo):
        return self.client.post(f'/api/goals/{self.a.meta.pk}/withdraw/', {'date': '2026-09-15', **corpo}, format='json')

    def guardar_no_cofrinho(self, valor):
        """Transferência comum da corrente para o cofrinho: só saldo livre."""
        transferir(self.a.conta, self.a.cofrinho, valor)

    def meta_com(self, valor):
        """Põe `valor` no cofrinho e na meta, por um aporte com transferência."""
        transferencia = transferir(self.a.conta, self.a.cofrinho, valor)
        registrar(self.a.meta, 'DEPOSIT', valor, conta=self.a.conta, transferencia=transferencia)
        recalcular(self.a.meta.pk)

    def livre(self):
        return saldo_livre(self.recarregar(self.a.cofrinho))

    def fotografia(self):
        return (
            sorted(Transaction.objects.values_list('id', 'account_id', 'amount')),
            sorted(GoalDeposit.objects.values_list('id', 'amount')),
            sorted(Goal.objects.values_list('id', 'current_amount')),
            sorted(Account.objects.values_list('id', 'balance')),
        )

    # --- META-13, META-14 ---

    def test_aporte_do_saldo_livre_sobe_a_meta_sem_transacao_e_respeita_o_limite(self):
        self.guardar_no_cofrinho('200.00')
        transacoes = Transaction.objects.count()

        resp = self.aportar(amount='150.00', from_free_balance=True)

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['current_amount'], '150.00')
        self.assertEqual(self.valor(self.a.meta), Decimal('150.00'))
        self.assertEqual(Transaction.objects.count(), transacoes)
        registro = GoalDeposit.objects.get(goal=self.a.meta)
        self.assertEqual(
            (registro.type, registro.amount, registro.account_id, registro.transaction_id,
             registro.transacao_saida_id, registro.transacao_entrada_id),
            ('DEPOSIT', Decimal('150.00'), self.a.cofrinho.pk, None, None, None),
        )
        self.assertEqual(self.livre(), Decimal('50.00'))

        resp = self.aportar(amount='100.00', from_free_balance=True)

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['detail'], 'O saldo livre do cofrinho é de R$ 50,00.')
        self.assertEqual(self.valor(self.a.meta), Decimal('150.00'))
        self.assertEqual(GoalDeposit.objects.count(), 1)

    # --- META-12 ---

    def test_aporte_de_outra_conta_cria_a_transferencia_e_registra_so_nessa_meta(self):
        outra = Goal.objects.create(
            user=self.a.usuario, name='Carro', target_amount=Decimal('100.00'), account=self.a.cofrinho,
        )

        resp = self.aportar(amount='300.00', account_id=str(self.a.conta.pk))

        self.assertEqual(resp.status_code, 200, resp.data)
        registro = GoalDeposit.objects.get()
        saida = Transaction.objects.get(type='TRANSFER_OUT')
        entrada = Transaction.objects.get(type='TRANSFER_IN')
        self.assertEqual(
            (registro.goal_id, registro.type, registro.amount, registro.account_id),
            (self.a.meta.pk, 'DEPOSIT', Decimal('300.00'), self.a.conta.pk),
        )
        self.assertEqual(
            (registro.transaction_id, registro.transacao_saida_id, registro.transacao_entrada_id),
            (saida.transfer_id, saida.pk, entrada.pk),
        )
        self.assertEqual((saida.account_id, entrada.account_id), (self.a.conta.pk, self.a.cofrinho.pk))
        self.assertEqual(self.valor(self.a.meta), Decimal('300.00'))
        self.assertEqual(self.valor(outra), Decimal('0.00'))
        self.assertEqual(self.saldo(self.a.conta), Decimal('700.00'))
        self.assertEqual(self.saldo(self.a.cofrinho), Decimal('300.00'))
        self.assertEqual(self.livre(), Decimal('0.00'))

    def test_aporte_com_o_proprio_cofrinho_como_origem_e_recusado_pela_saldo_17(self):
        self.guardar_no_cofrinho('200.00')
        antes = self.fotografia()

        resp = self.aportar(amount='100.00', account_from=str(self.a.cofrinho.pk))

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['detail'], MESMA_CONTA)
        self.assertEqual(self.fotografia(), antes)

    # --- META-15, META-16 ---

    def test_resgate_para_outra_conta_cria_a_transferencia(self):
        self.meta_com('500.00')

        resp = self.resgatar(amount='120.00', account_to=str(self.a.conta.pk))

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['current_amount'], '380.00')
        registro = GoalDeposit.objects.get(type='WITHDRAWAL')
        saida = Transaction.objects.get(transfer_id=registro.transaction_id, type='TRANSFER_OUT')
        entrada = Transaction.objects.get(transfer_id=registro.transaction_id, type='TRANSFER_IN')
        self.assertEqual(
            (registro.account_id, registro.transacao_saida_id, registro.transacao_entrada_id),
            (self.a.conta.pk, saida.pk, entrada.pk),
        )
        self.assertEqual((saida.account_id, entrada.account_id), (self.a.cofrinho.pk, self.a.conta.pk))
        self.assertEqual(self.saldo(self.a.cofrinho), Decimal('380.00'))
        self.assertEqual(self.saldo(self.a.conta), Decimal('620.00'))

    def test_resgate_para_o_saldo_livre_registra_sem_transferencia(self):
        self.meta_com('500.00')
        transacoes = Transaction.objects.count()

        resp = self.resgatar(amount='200.00', to_free_balance=True)

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(Transaction.objects.count(), transacoes)
        registro = GoalDeposit.objects.get(type='WITHDRAWAL')
        self.assertEqual(
            (registro.amount, registro.account_id, registro.transaction_id, registro.transacao_saida_id),
            (Decimal('200.00'), self.a.cofrinho.pk, None, None),
        )
        self.assertEqual(self.valor(self.a.meta), Decimal('300.00'))
        self.assertEqual(self.saldo(self.a.cofrinho), Decimal('500.00'))
        self.assertEqual(self.livre(), Decimal('200.00'))

    # --- META-17, META-18 ---

    def test_resgate_acima_do_valor_da_meta_e_recusado(self):
        self.meta_com('1234.56')
        antes = self.fotografia()

        for corpo in ({'account_to': str(self.a.conta.pk)}, {'to_free_balance': True}):
            resp = self.resgatar(amount='1234.57', **corpo)
            self.assertEqual(resp.status_code, 400)
            self.assertEqual(resp.data['detail'], 'A meta tem R$ 1.234,56 para resgatar.')
        self.assertEqual(self.fotografia(), antes)

    def test_resgate_para_outra_conta_acima_do_saldo_do_cofrinho_e_recusado(self):
        # Meta com R$ 500,00 num cofrinho que tem R$ 300,00 (despesa paga pelo cofrinho)
        self.meta_com('500.00')
        Transaction.objects.create(
            user=self.a.usuario, account=self.a.cofrinho, type='EXPENSE', status='COMPLETED',
            description='Passagem', amount=Decimal('200.00'), date=DIA,
        )
        antes = self.fotografia()

        resp = self.resgatar(amount='300.01', account_to=str(self.a.conta.pk))

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['detail'], 'O cofrinho tem só R$ 300,00.')
        self.assertEqual(self.fotografia(), antes)
        # Até o saldo do cofrinho passa
        self.assertEqual(self.resgatar(amount='300.00', account_to=str(self.a.conta.pk)).status_code, 200)
        self.assertEqual(self.valor(self.a.meta), Decimal('200.00'))

    # --- META-19 ---

    def test_valor_menor_que_um_centavo_recebe_400_no_campo(self):
        self.meta_com('500.00')
        antes = self.fotografia()

        for valor in ('0.00', '0', '-5.00', '0.001'):
            for resp in (
                self.aportar(amount=valor, account_id=str(self.a.conta.pk)),
                self.aportar(amount=valor, from_free_balance=True),
                self.resgatar(amount=valor, account_to=str(self.a.conta.pk)),
                self.resgatar(amount=valor, to_free_balance=True),
            ):
                self.assertEqual(resp.status_code, 400, valor)
                self.assertEqual(list(resp.data), ['amount'], valor)
        self.assertEqual(self.fotografia(), antes)

    # --- META-20 ---

    def test_conta_de_outro_usuario_recebe_a_mesma_recusa_de_id_inexistente(self):
        self.meta_com('500.00')
        antes = self.fotografia()
        inexistente = '00000000-0000-0000-0000-000000000000'

        for acao, campo in ((self.aportar, 'account_id'), (self.aportar, 'account_from'),
                            (self.resgatar, 'account_to'), (self.resgatar, 'account_id')):
            de_b = acao(amount='10.00', **{campo: str(self.b.conta.pk)})
            nenhuma = acao(amount='10.00', **{campo: inexistente})
            self.assertEqual((de_b.status_code, de_b.data), (400, {campo: CONTA_NAO_ENCONTRADA}), campo)
            self.assertEqual((nenhuma.status_code, nenhuma.data), (400, {campo: CONTA_NAO_ENCONTRADA}), campo)
        self.assertEqual(self.fotografia(), antes)

    def test_sem_conta_e_sem_saldo_livre_a_conta_e_obrigatoria(self):
        resp = self.aportar(amount='10.00')
        self.assertEqual(resp.data, {'account_id': ['Este campo é obrigatório.']})

        resp = self.resgatar(amount='10.00', to_free_balance=False)
        self.assertEqual(resp.data, {'account_to': ['Este campo é obrigatório.']})

    # --- META-21 ---

    def test_meta_arquivada_nao_recebe_aporte_e_ainda_permite_resgate(self):
        self.meta_com('500.00')
        self.guardar_no_cofrinho('100.00')
        Goal.objects.filter(pk=self.a.meta.pk).update(is_active=False)
        antes = self.fotografia()

        for corpo in ({'account_id': str(self.a.conta.pk)}, {'from_free_balance': True}):
            resp = self.aportar(amount='10.00', **corpo)
            self.assertEqual(resp.status_code, 400)
            self.assertEqual(resp.data['detail'], 'Metas arquivadas não recebem aportes.')
        self.assertEqual(self.fotografia(), antes)

        resp = self.resgatar(amount='100.00', account_to=str(self.a.conta.pk))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.valor(self.a.meta), Decimal('400.00'))

"""
Vínculo dos registros das metas com as transações (META-03, META-06 a META-09).

Os testes passam pela API de transações, que roda com `ATOMIC_REQUESTS`: a
recusa da META-09 desfaz a requisição inteira.
"""
from datetime import date
from decimal import Decimal

from accounts.models import Account
from goals.models import Goal, GoalDeposit
from goals.valores import recalcular, saldo_livre
from transactions.models import Transaction
from tests.metas.base import DIA, MetasTestCase, registrar, transferir

URL = '/api/transactions/'
FICARIA_NEGATIVA = 'A meta Viagem A ficaria negativa. Desfaça o resgate antes.'


class VinculoTests(MetasTestCase):

    def setUp(self):
        super().setUp()
        self.poupanca = Account.objects.create(
            user=self.a.usuario, name='Poupança A', type='SAVINGS', initial_balance=Decimal('0.00'),
        )

    def aportar(self, valor='500.00'):
        """Aporte de `valor` da corrente na meta Viagem, ligado às duas pernas."""
        transferencia = transferir(self.a.conta, self.a.cofrinho, valor)
        registro = registrar(self.a.meta, 'DEPOSIT', valor, conta=self.a.conta, transferencia=transferencia)
        recalcular(self.a.meta.pk)
        return transferencia, registro

    def resgatar(self, valor):
        """Resgate de `valor` da meta Viagem para a corrente, ligado às duas pernas."""
        transferencia = transferir(self.a.cofrinho, self.a.conta, valor)
        registro = registrar(self.a.meta, 'WITHDRAWAL', valor, conta=self.a.conta, transferencia=transferencia)
        recalcular(self.a.meta.pk)
        return transferencia, registro

    def livre(self):
        return saldo_livre(self.recarregar(self.a.cofrinho))

    def fotografia(self):
        return (
            sorted(Transaction.objects.values_list('id', 'account_id', 'amount', 'date', 'status')),
            sorted(GoalDeposit.objects.values_list('id', 'amount', 'date', 'account_id')),
            sorted(Goal.objects.values_list('id', 'current_amount')),
            sorted(Account.objects.values_list('id', 'balance')),
        )

    # --- META-03 ---

    def test_transferencia_comum_para_o_cofrinho_muda_so_o_saldo_livre(self):
        self.aportar('100.00')
        livre_antes = self.livre()

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(f'{URL}transfer/', {
                'account_from': str(self.a.conta.id), 'account_to': str(self.a.cofrinho.id),
                'amount': '200.00', 'date': '2026-09-15',
            }, format='json')

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(self.livre() - livre_antes, Decimal('200.00'))
        self.assertEqual(self.valor(self.a.meta), Decimal('100.00'))
        self.assertEqual(GoalDeposit.objects.count(), 1)

    def test_despesa_paga_pelo_cofrinho_muda_so_o_saldo_livre(self):
        self.aportar('100.00')

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(URL, {
                'type': 'EXPENSE', 'status': 'COMPLETED', 'description': 'Passagem',
                'amount': '300.00', 'date': '2026-09-15', 'account': str(self.a.cofrinho.id),
            }, format='json')

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(self.valor(self.a.meta), Decimal('100.00'))
        self.assertEqual(self.livre(), Decimal('-300.00'))
        self.assertEqual(GoalDeposit.objects.count(), 1)

    # --- META-06 ---

    def test_excluir_a_transferencia_do_aporte_zera_a_meta_na_mesma_requisicao(self):
        (transfer_id, saida, _), registro = self.aportar('500.00')
        self.assertEqual(self.valor(self.a.meta), Decimal('500.00'))

        resp = self.client.delete(f'{URL}{saida.id}/')

        self.assertEqual(resp.status_code, 204)
        self.assertEqual(self.valor(self.a.meta), Decimal('0.00'))
        self.assertFalse(GoalDeposit.objects.filter(pk=registro.pk).exists())
        self.assertFalse(Transaction.objects.filter(transfer_id=transfer_id).exists())
        self.assertEqual(self.saldo(self.a.conta), Decimal('1000.00'))

    def test_excluir_pela_perna_do_cofrinho_tambem_remove_o_registro(self):
        (_, _, entrada), registro = self.aportar('500.00')

        resp = self.client.delete(f'{URL}{entrada.id}/')

        self.assertEqual(resp.status_code, 204)
        self.assertEqual(self.valor(self.a.meta), Decimal('0.00'))
        self.assertFalse(GoalDeposit.objects.filter(pk=registro.pk).exists())

    def test_excluir_a_transacao_de_um_registro_antigo_remove_o_registro(self):
        transfer_id, saida, _ = transferir(self.a.conta, self.a.cofrinho, '120.00')
        antigo = registrar(self.a.meta, 'DEPOSIT', '120.00', conta=self.a.conta, transaction_id=transfer_id)
        recalcular(self.a.meta.pk)

        resp = self.client.delete(f'{URL}{saida.id}/')

        self.assertEqual(resp.status_code, 204)
        self.assertFalse(GoalDeposit.objects.filter(pk=antigo.pk).exists())
        self.assertEqual(self.valor(self.a.meta), Decimal('0.00'))

    # --- META-07 ---

    def test_mudar_valor_e_data_da_transferencia_muda_o_registro_igual(self):
        (_, saida, _), registro = self.aportar('500.00')

        resp = self.client.patch(f'{URL}{saida.id}/', {'amount': '350.00', 'date': '2026-09-20'}, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        registro = self.recarregar(registro)
        self.assertEqual((registro.amount, registro.date), (Decimal('350.00'), date(2026, 9, 20)))
        self.assertEqual(self.valor(self.a.meta), Decimal('350.00'))

    def test_transferencia_pendente_deixa_de_contar_e_volta_ao_ser_efetivada(self):
        (_, saida, _), _ = self.aportar('500.00')

        resp = self.client.patch(f'{URL}{saida.id}/', {'status': 'PENDING'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.valor(self.a.meta), Decimal('0.00'))

        resp = self.client.patch(f'{URL}{saida.id}/', {'status': 'COMPLETED'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.valor(self.a.meta), Decimal('500.00'))

    # --- META-08 ---

    def test_trocar_o_destino_do_aporte_para_outra_conta_remove_o_registro(self):
        (_, _, entrada), registro = self.aportar('500.00')

        resp = self.client.patch(f'{URL}{entrada.id}/', {'account': str(self.poupanca.id)}, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(GoalDeposit.objects.filter(pk=registro.pk).exists())
        self.assertEqual(self.valor(self.a.meta), Decimal('0.00'))
        self.assertEqual(self.saldo(self.poupanca), Decimal('500.00'))

    def test_trocar_a_origem_do_resgate_para_outra_conta_remove_o_registro(self):
        self.aportar('500.00')
        (_, _, entrada), registro = self.resgatar('200.00')

        # Pela perna de entrada: a outra perna passa a sair da poupança
        resp = self.client.patch(
            f'{URL}{entrada.id}/', {'target_account_id': str(self.poupanca.id)}, format='json',
        )

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(GoalDeposit.objects.filter(pk=registro.pk).exists())
        self.assertEqual(self.valor(self.a.meta), Decimal('500.00'))

    # --- META-09 ---

    def test_excluir_o_aporte_depois_de_um_resgate_e_recusado_e_nada_muda(self):
        (_, saida, _), _ = self.aportar('500.00')
        self.resgatar('200.00')
        antes = self.fotografia()

        resp = self.client.delete(f'{URL}{saida.id}/')

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['detail'], FICARIA_NEGATIVA)
        self.assertEqual(self.fotografia(), antes)
        self.assertEqual(self.valor(self.a.meta), Decimal('300.00'))

    def test_reduzir_o_aporte_abaixo_do_resgatado_e_recusado_e_nada_muda(self):
        (_, saida, _), _ = self.aportar('500.00')
        self.resgatar('200.00')
        antes = self.fotografia()

        resp = self.client.patch(f'{URL}{saida.id}/', {'amount': '150.00'}, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['detail'], FICARIA_NEGATIVA)
        self.assertEqual(self.fotografia(), antes)

    def test_transacao_comum_no_cofrinho_excluida_nao_muda_a_meta(self):
        self.aportar('100.00')
        receita = Transaction.objects.create(
            user=self.a.usuario, account=self.a.cofrinho, type='INCOME', status='COMPLETED',
            description='Guardado', amount=Decimal('50.00'), date=DIA,
        )

        resp = self.client.delete(f'{URL}{receita.id}/')

        self.assertEqual(resp.status_code, 204)
        self.assertEqual(self.valor(self.a.meta), Decimal('100.00'))
        self.assertEqual(GoalDeposit.objects.count(), 1)

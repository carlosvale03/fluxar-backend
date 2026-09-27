from datetime import date
from decimal import Decimal

from transactions.models import Transaction
from transactions.services import TransactionService
from tests.isolamento.base import DoisUsuariosTestCase

URL = '/api/transactions/'


class SignalsDaTransferenciaTests(DoisUsuariosTestCase):

    def setUp(self):
        self.cliente = self.como(self.a.usuario)
        transfer_id = TransactionService.create_transfer(
            user=self.a.usuario, account_from=self.a.conta, account_to=self.a.cofrinho,
            amount=Decimal('25.00'), date=date(2026, 9, 4),
        )
        self.saida = Transaction.objects.get(transfer_id=transfer_id, type='TRANSFER_OUT')
        self.entrada = Transaction.objects.get(transfer_id=transfer_id, type='TRANSFER_IN')
        # Transação de B gravada à força com o transfer_id da transferência de A
        self.intrusa = Transaction.objects.create(
            user=self.b.usuario, type='TRANSFER_IN', description='Intrusa',
            amount=Decimal('999.00'), date=date(2026, 8, 1), account=self.b.conta,
            transfer_id=transfer_id,
        )

    def editar_saida(self):
        resp = self.cliente.patch(
            f'{URL}{self.saida.id}/', {'amount': '60.00', 'date': '2026-09-10'}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)

    def excluir_saida(self):
        resp = self.cliente.delete(f'{URL}{self.saida.id}/')
        self.assertEqual(resp.status_code, 204)

    def test_editar_a_perna_de_a_nao_muda_a_transacao_de_b(self):
        self.editar_saida()

        intrusa = Transaction.objects.get(pk=self.intrusa.pk)
        self.assertEqual((intrusa.amount, intrusa.date), (Decimal('999.00'), date(2026, 8, 1)))

    def test_editar_a_perna_de_a_continua_atualizando_a_parceira_de_a(self):
        self.editar_saida()

        entrada = Transaction.objects.get(pk=self.entrada.pk)
        self.assertEqual((entrada.amount, entrada.date), (Decimal('60.00'), date(2026, 9, 10)))

    def test_excluir_a_perna_de_a_nao_exclui_a_transacao_de_b(self):
        self.excluir_saida()

        self.assertTrue(Transaction.objects.filter(pk=self.intrusa.pk).exists())

    def test_excluir_a_perna_de_a_continua_excluindo_a_parceira_de_a(self):
        self.excluir_saida()

        self.assertFalse(Transaction.objects.filter(pk__in=[self.saida.pk, self.entrada.pk]).exists())

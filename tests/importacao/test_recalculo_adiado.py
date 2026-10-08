"""
Recálculo de saldo adiado durante a importação (IMPORT-40, AD-038, AD-043).

Dentro de `recalculo_adiado()`, as gravações só anotam as contas; a saída
do contexto recalcula cada conta uma vez, e o saldo final segue SALDO-01.
"""
import threading
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.db import connection

from accounts.models import Account
from accounts.saldo import calcular, recalcular, recalculo_adiado
from transactions.models import Transaction

from .base import ImportacaoTestCase


class RecalculoAdiadoTests(ImportacaoTestCase):

    def lancar(self, conta, tipo='INCOME', valor='10.00'):
        return Transaction.objects.create(
            user=conta.user, account=conta, type=tipo, status='COMPLETED',
            description='Venda', amount=Decimal(valor), date=date(2026, 9, 15),
        )

    def saldo(self, conta):
        return Account.objects.get(pk=conta.pk).balance

    def test_cem_transacoes_disparam_um_recalculo_so(self):
        """IMPORT-40: 100 gravações numa conta, um recálculo na saída, com o saldo de SALDO-01."""
        with patch('accounts.saldo.calcular', wraps=calcular) as espiao:
            with recalculo_adiado():
                for _ in range(100):
                    self.lancar(self.a.conta)
                self.lancar(self.a.poupanca, valor='5.00')
                # Ainda não recalculado dentro do contexto
                self.assertEqual(self.saldo(self.a.conta), Decimal('1000.00'))
                self.assertEqual(espiao.call_count, 0)

        self.assertEqual(sorted(c.args[0].pk for c in espiao.call_args_list),
                         sorted([self.a.conta.pk, self.a.poupanca.pk]))
        self.assertEqual(self.saldo(self.a.conta), Decimal('2000.00'))
        self.assertEqual(self.saldo(self.a.conta), calcular(Account.objects.get(pk=self.a.conta.pk)))
        self.assertEqual(self.saldo(self.a.poupanca), Decimal('5.00'))

    def test_fora_do_contexto_cada_gravacao_recalcula(self):
        """Fora do contexto, o comportamento não muda."""
        self.lancar(self.a.conta)
        self.assertEqual(self.saldo(self.a.conta), Decimal('1010.00'))
        self.lancar(self.a.conta, tipo='EXPENSE', valor='30.00')
        self.assertEqual(self.saldo(self.a.conta), Decimal('980.00'))

    def test_aninhado_so_o_mais_externo_recalcula(self):
        """O contexto interno não recalcula; o externo recalcula na saída."""
        with recalculo_adiado():
            with recalculo_adiado():
                self.lancar(self.a.conta)
            self.assertEqual(self.saldo(self.a.conta), Decimal('1000.00'))
            self.lancar(self.a.conta)
        self.assertEqual(self.saldo(self.a.conta), Decimal('1020.00'))

        # Depois do contexto, volta a recalcular na hora
        self.lancar(self.a.conta)
        self.assertEqual(self.saldo(self.a.conta), Decimal('1030.00'))

    def test_outra_thread_nao_entra_no_adiamento(self):
        """O adiamento vale só para a thread que abriu o contexto."""
        def outra_thread():
            try:
                recalcular(self.b.conta.pk)
            finally:
                connection.close()

        with patch('accounts.saldo.calcular', wraps=calcular) as espiao:
            with recalculo_adiado():
                self.lancar(self.a.conta)
                thread = threading.Thread(target=outra_thread)
                thread.start()
                thread.join(timeout=30)

        # A conta da outra thread não foi anotada no adiamento desta
        self.assertEqual([c.args[0].pk for c in espiao.call_args_list], [self.a.conta.pk])

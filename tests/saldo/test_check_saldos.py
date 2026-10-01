"""
Verificação de consistência dos saldos (SALDO-39).

`check_saldos` lista cada conta cujo saldo guardado difere do calculado por
SALDO-01, com o id e os dois valores e sem nomes, e o total no fim.
"""
from decimal import Decimal
from io import StringIO

from django.core.management import call_command

from accounts.models import Account
from tests.saldo.base import SaldoTestCase


class CheckSaldosTests(SaldoTestCase):

    def conferir(self):
        saida = StringIO()
        call_command('check_saldos', stdout=saida)
        return saida.getvalue().splitlines()

    def test_lista_a_conta_divergente_com_id_e_os_dois_valores(self):
        self.lancar(self.a.conta, 'EXPENSE', '100.00')
        # Saldo gravado à força, sem passar pelo recálculo; vale também para
        # conta excluída
        Account.objects.filter(pk=self.a.conta.pk).update(balance=Decimal('950.00'))
        Account.objects.filter(pk=self.a.poupanca.pk).update(balance=Decimal('-10.50'), is_active=False)

        linhas = self.conferir()

        self.assertEqual(sorted(linhas[:-1]), sorted([
            f'{self.a.conta.id} 950.00 900.00',
            f'{self.a.poupanca.id} -10.50 0.00',
        ]))
        self.assertEqual(linhas[-1], 'Contas com saldo divergente: 2')
        saida = '\n'.join(linhas)
        for nome in (self.a.conta.name, self.a.poupanca.name, self.a.usuario.name, self.a.usuario.email):
            self.assertNotIn(nome, saida)

    def test_sem_divergencia_o_total_e_zero(self):
        self.lancar(self.a.conta, 'EXPENSE', '100.00')

        self.assertEqual(self.conferir(), ['Contas com saldo divergente: 0'])

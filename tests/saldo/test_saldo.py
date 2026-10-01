"""
Saldo recalculado do razão (SALDO-01 a SALDO-08, AD-038).

A conta corrente de A começa com saldo inicial de R$ 1.000,00 e nenhuma
transação. Depois de cada operação, o saldo guardado é o que SALDO-01 manda:
saldo inicial + entradas efetivadas - saídas efetivadas do dono da conta.
"""
from datetime import date
from decimal import Decimal

from accounts.models import Account
from accounts.saldo import calcular, recalcular
from accounts.services import AccountService
from transactions.models import Transaction
from tests.saldo.base import SaldoTestCase, URL_TRANSACOES


class SaldoPelaApiTests(SaldoTestCase):

    def criar(self, **extra):
        resp = self.cliente.post(URL_TRANSACOES, self.payload(**extra), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return Transaction.objects.get(pk=resp.data['id'])

    def editar(self, transacao, **dados):
        resp = self.cliente.patch(f'{URL_TRANSACOES}{transacao.id}/', dados, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_criar_receita_efetivada_soma_o_valor(self):
        self.criar(type='INCOME', amount='200.00', category=str(self.a.receita.id))
        self.assertEqual(self.saldo(self.a.conta), Decimal('1200.00'))

    def test_criar_despesa_efetivada_subtrai_o_valor(self):
        self.criar(type='EXPENSE', amount='300.00')
        self.assertEqual(self.saldo(self.a.conta), Decimal('700.00'))

    def test_criar_pendente_nao_muda_o_saldo(self):
        self.criar(status='PENDING', amount='300.00')
        self.assertEqual(self.saldo(self.a.conta), Decimal('1000.00'))

    def test_efetivar_pendente_aplica_o_valor(self):
        t = self.criar(status='PENDING', amount='300.00')
        self.editar(t, status='COMPLETED')
        self.assertEqual(self.saldo(self.a.conta), Decimal('700.00'))

    def test_voltar_para_pendente_desfaz_o_efeito(self):
        t = self.criar(amount='300.00')
        self.assertEqual(self.saldo(self.a.conta), Decimal('700.00'))
        self.editar(t, status='PENDING')
        self.assertEqual(self.saldo(self.a.conta), Decimal('1000.00'))

    def test_mudar_o_valor_ajusta_pela_diferenca(self):
        t = self.criar(amount='300.00')
        self.editar(t, amount='120.50')
        self.assertEqual(self.saldo(self.a.conta), Decimal('879.50'))

    def test_mudar_o_tipo_ajusta_pela_diferenca(self):
        t = self.criar(type='EXPENSE', amount='300.00')
        self.editar(t, type='INCOME', category=str(self.a.receita.id))
        self.assertEqual(self.saldo(self.a.conta), Decimal('1300.00'))

    def test_mudar_de_conta_move_o_efeito(self):
        t = self.criar(type='INCOME', amount='250.00', category=str(self.a.receita.id))
        self.editar(t, account=str(self.a.poupanca.id))
        self.assertEqual(self.saldo(self.a.conta), Decimal('1000.00'))
        self.assertEqual(self.saldo(self.a.poupanca), Decimal('250.00'))

    def test_excluir_efetivada_desfaz_o_efeito(self):
        t = self.criar(amount='300.00')
        resp = self.cliente.delete(f'{URL_TRANSACOES}{t.id}/')
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(self.saldo(self.a.conta), Decimal('1000.00'))

    def test_efetivada_com_data_futura_entra_no_saldo(self):
        self.criar(amount='300.00', date='2027-03-01')
        self.assertEqual(self.saldo(self.a.conta), Decimal('700.00'))


class RegraDoSaldoTests(SaldoTestCase):

    def test_todos_os_tipos_entram_pela_regra(self):
        conta = self.a.conta
        self.lancar(conta, 'INCOME', '500.00')
        self.lancar(conta, 'TRANSFER_IN', '200.00')
        self.lancar(conta, 'EXPENSE', '100.00')
        self.lancar(conta, 'TRANSFER_OUT', '50.00')
        self.lancar(conta, 'CREDIT_CARD', '30.00')
        self.lancar(conta, 'INVOICE_PAYMENT', '20.00')
        # Pendentes de todos os tipos ficam de fora (SALDO-02)
        for tipo in ('INCOME', 'TRANSFER_IN', 'EXPENSE', 'TRANSFER_OUT', 'CREDIT_CARD', 'INVOICE_PAYMENT'):
            self.lancar(conta, tipo, '7.00', status='PENDING')

        # 1000 + 500 + 200 - 100 - 50 - 30 - 20
        self.assertEqual(self.saldo(conta), Decimal('1500.00'))
        conta_atual = Account.objects.get(pk=conta.pk)
        self.assertEqual(calcular(conta_atual), Decimal('1500.00'))
        self.assertEqual(AccountService.get_balance(conta_atual), Decimal('1500.00'))

    def test_transacao_de_outro_usuario_na_conta_nao_entra(self):
        # Gravada à força: dono B, conta de A
        self.lancar(self.a.conta, 'INCOME', '400.00', usuario=self.b.usuario)
        self.assertEqual(self.saldo(self.a.conta), Decimal('1000.00'))
        self.assertEqual(calcular(Account.objects.get(pk=self.a.conta.pk)), Decimal('1000.00'))

    def test_saldo_errado_e_corrigido_na_proxima_gravacao(self):
        # O saldo vem do razão, não de incrementos sobre o valor guardado
        Account.objects.filter(pk=self.a.conta.pk).update(balance=Decimal('5.00'))
        self.lancar(self.a.conta, 'EXPENSE', '100.00')
        self.assertEqual(self.saldo(self.a.conta), Decimal('900.00'))

    def test_recalcular_ignora_none_e_grava_cada_conta(self):
        Account.objects.filter(pk__in=[self.a.conta.pk, self.a.poupanca.pk]).update(balance=Decimal('1.00'))
        recalcular(None, self.a.conta.pk, self.a.poupanca.pk, None)
        self.assertEqual(self.saldo(self.a.conta), Decimal('1000.00'))
        self.assertEqual(self.saldo(self.a.poupanca), Decimal('0.00'))

    def test_mudar_de_conta_pelo_orm_recalcula_as_duas(self):
        t = self.lancar(self.a.conta, 'EXPENSE', '100.00', date=date(2026, 9, 1))
        t.account = self.a.poupanca
        t.save()
        self.assertEqual(self.saldo(self.a.conta), Decimal('1000.00'))
        self.assertEqual(self.saldo(self.a.poupanca), Decimal('-100.00'))

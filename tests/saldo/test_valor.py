"""
Valor positivo com até duas casas (SALDO-09).

Em cada operação que move dinheiro, 0, -10 e 100.123 recebem HTTP 400 com o
erro no campo `amount`, sem mudar nenhum saldo; 100.1 é aceito.
"""
from decimal import Decimal

from accounts.models import Account, CreditCardInvoice
from goals.models import Goal, GoalDeposit
from transactions.models import Transaction
from tests.saldo.base import SaldoTestCase, URL_TRANSACOES

RECUSADOS = (0, '0.00', '-10', -10, '100.123')
MENSAGEM_NAO_POSITIVO = 'O valor deve ser maior que zero.'


class ValorDasOperacoesTests(SaldoTestCase):

    def setUp(self):
        super().setUp()
        # Saldo na meta, para que o resgate seja possível
        Goal.objects.filter(pk=self.a.meta.pk).update(current_amount=Decimal('500.00'))

    # Cada operação: (url, corpo sem o valor)
    def transacao(self):
        return URL_TRANSACOES, self.payload()

    def transferencia(self):
        return f'{URL_TRANSACOES}transfer/', {
            'account_from': str(self.a.conta.id), 'account_to': str(self.a.poupanca.id),
            'date': '2026-09-15',
        }

    def compra_no_cartao(self):
        return f'{URL_TRANSACOES}credit-card-expense/', {
            'credit_card': str(self.a.cartao.id), 'date': '2026-09-15',
            'description': 'Loja', 'category': str(self.a.despesa.id),
        }

    def pagamento_de_fatura(self):
        return f'/api/invoices/{self.a.fatura.id}/pay/', {
            'account_id': str(self.a.conta.id), 'date': '2026-09-20',
        }

    def aporte(self):
        return f'/api/goals/{self.a.meta.id}/deposit/', {
            'account_id': str(self.a.conta.id), 'date': '2026-09-15',
        }

    def resgate(self):
        return f'/api/goals/{self.a.meta.id}/withdraw/', {
            'account_to': str(self.a.conta.id), 'date': '2026-09-15',
        }

    def estado(self):
        return (
            sorted(Account.objects.filter(user=self.a.usuario).values_list('id', 'balance')),
            Transaction.objects.count(),
            GoalDeposit.objects.count(),
            Goal.objects.get(pk=self.a.meta.pk).current_amount,
            CreditCardInvoice.objects.get(pk=self.a.fatura.pk).status,
        )

    def assert_recusa(self, operacao):
        url, corpo = operacao()
        antes = self.estado()
        for valor in RECUSADOS:
            with self.subTest(valor=valor):
                resp = self.cliente.post(url, {**corpo, 'amount': valor}, format='json')
                self.assertEqual(resp.status_code, 400, resp.data)
                self.assertIn('amount', resp.data)
                if Decimal(str(valor)) <= 0:
                    self.assertEqual(resp.data['amount'], [MENSAGEM_NAO_POSITIVO])
                self.assertEqual(self.estado(), antes)

    def assert_aceito(self, operacao, status_esperado):
        url, corpo = operacao()
        resp = self.cliente.post(url, {**corpo, 'amount': '100.1'}, format='json')
        self.assertEqual(resp.status_code, status_esperado, resp.data)
        return resp

    def test_transacao_recusa_valor_invalido(self):
        self.assert_recusa(self.transacao)

    def test_transacao_aceita_uma_casa(self):
        self.assert_aceito(self.transacao, 201)
        self.assertEqual(self.saldo(self.a.conta), Decimal('899.90'))

    def test_transferencia_recusa_valor_invalido(self):
        self.assert_recusa(self.transferencia)

    def test_transferencia_aceita_uma_casa(self):
        self.assert_aceito(self.transferencia, 201)
        self.assertEqual(self.saldo(self.a.conta), Decimal('899.90'))
        self.assertEqual(self.saldo(self.a.poupanca), Decimal('100.10'))

    def test_compra_no_cartao_recusa_valor_invalido(self):
        self.assert_recusa(self.compra_no_cartao)

    def test_compra_no_cartao_aceita_uma_casa(self):
        self.assert_aceito(self.compra_no_cartao, 201)
        compra = Transaction.objects.get(type='CREDIT_CARD', user=self.a.usuario)
        self.assertEqual(compra.amount, Decimal('100.10'))

    def test_pagamento_de_fatura_recusa_valor_invalido(self):
        self.assert_recusa(self.pagamento_de_fatura)

    def test_pagamento_de_fatura_aceita_uma_casa(self):
        self.lancar(
            self.a.conta, 'CREDIT_CARD', '100.10', status='PENDING',
            credit_card=self.a.cartao, invoice=self.a.fatura,
        )
        self.assert_aceito(self.pagamento_de_fatura, 200)
        self.assertEqual(self.saldo(self.a.conta), Decimal('899.90'))

    def test_aporte_recusa_valor_invalido(self):
        self.assert_recusa(self.aporte)

    def test_aporte_aceita_uma_casa(self):
        self.assert_aceito(self.aporte, 200)
        self.assertEqual(self.saldo(self.a.conta), Decimal('899.90'))
        self.assertEqual(self.saldo(self.a.cofrinho), Decimal('100.10'))

    def test_resgate_recusa_valor_invalido(self):
        self.assert_recusa(self.resgate)

    def test_resgate_aceita_uma_casa(self):
        self.assert_aceito(self.resgate, 200)
        self.assertEqual(self.saldo(self.a.conta), Decimal('1100.10'))
        self.assertEqual(self.saldo(self.a.cofrinho), Decimal('-100.10'))

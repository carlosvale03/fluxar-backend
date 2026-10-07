"""
Operações simultâneas na mesma conta (SALDO-44, SALDO-45 e SALDO-26).

Usa `TransactionTestCase`: com o `TestCase`, tudo roda numa transação só e
as threads, cada uma com a própria conexão, não veriam os dados do teste nem
disputariam as travas de verdade. Cada thread espera as outras numa
`threading.Barrier`, faz a requisição pela API e fecha a conexão no fim.

O `TransactionTestCase` esvazia as tabelas dos modelos depois de cada teste.
A tabela do cache (`createcachetable`) não é de modelo e fica intacta, e os
dados de cada teste (usuário, categorias padrão e "Carteira") são criados no
próprio `setUp`, então os outros testes não dependem do que é apagado aqui.
"""
import threading
from datetime import date
from decimal import Decimal

from django.db import connection
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from accounts.models import Account
from accounts.saldo import calcular
from tests.saldo.base import URL_TRANSACOES, criar_dados
from transactions.models import Transaction

FATURA_JA_PAGA = 'Fatura já está paga.'


class ConcorrenciaTests(TransactionTestCase):

    def setUp(self):
        self.a = criar_dados('A')

    def em_paralelo(self, n, requisicao):
        """
        Roda `requisicao(cliente)` em `n` threads que partem juntas e devolve
        as respostas. Falha o teste se alguma thread levantar exceção.
        """
        barreira = threading.Barrier(n, timeout=20)
        respostas, erros = [], []

        def trabalho():
            try:
                cliente = APIClient()
                cliente.force_authenticate(user=self.a.usuario)
                barreira.wait()
                respostas.append(requisicao(cliente))
            except Exception as erro:  # noqa: BLE001 - repassado ao teste abaixo
                erros.append(erro)
            finally:
                connection.close()

        threads = [threading.Thread(target=trabalho) for _ in range(n)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
        self.assertFalse(any(t.is_alive() for t in threads), 'thread presa')
        self.assertEqual(erros, [])
        self.assertEqual(len(respostas), n)
        return respostas

    def saldo(self, conta):
        conta = Account.objects.get(pk=conta.pk)
        # O saldo guardado é o de SALDO-01
        self.assertEqual(conta.balance, calcular(conta))
        return conta.balance

    def test_vinte_criacoes_simultaneas_somam_todas(self):
        """SALDO-44: o saldo final é o mesmo das 20 criações em sequência."""
        corpo = {
            'type': 'INCOME', 'status': 'COMPLETED', 'description': 'Venda',
            'amount': '10.00', 'date': '2026-09-15',
            'account': str(self.a.conta.id), 'category': str(self.a.receita.id),
        }

        respostas = self.em_paralelo(20, lambda c: c.post(URL_TRANSACOES, corpo, format='json'))

        self.assertEqual([r.status_code for r in respostas], [201] * 20)
        self.assertEqual(Transaction.objects.filter(account=self.a.conta).count(), 20)
        self.assertEqual(self.saldo(self.a.conta), Decimal('1200.00'))

    def test_duas_efetivacoes_simultaneas_contam_uma_vez(self):
        """SALDO-45: a mesma pendente efetivada duas vezes ao mesmo tempo soma uma vez."""
        pendente = Transaction.objects.create(
            user=self.a.usuario, account=self.a.conta, type='EXPENSE', status='PENDING',
            description='Aluguel', amount=Decimal('300.00'), date=date(2026, 9, 15),
            category=self.a.despesa,
        )
        url = f'{URL_TRANSACOES}{pendente.id}/'

        respostas = self.em_paralelo(2, lambda c: c.patch(url, {'status': 'COMPLETED'}, format='json'))

        self.assertEqual([r.status_code for r in respostas], [200, 200])
        self.assertEqual(Transaction.objects.get(pk=pendente.pk).status, 'COMPLETED')
        self.assertEqual(Transaction.objects.filter(account=self.a.conta).count(), 1)
        self.assertEqual(self.saldo(self.a.conta), Decimal('700.00'))

    def test_dois_pagamentos_simultaneos_da_mesma_fatura_debitam_uma_vez(self):
        """SALDO-26: um pagamento passa e o outro recebe 400 "Fatura já está paga."."""
        pagadora = Account.objects.create(
            user=self.a.usuario, name='Pagadora', type='CHECKING',
            initial_balance=Decimal('3000.00'),
        )
        Transaction.objects.create(
            user=self.a.usuario, account=self.a.cartao.account, type='CREDIT_CARD', status='PENDING',
            description='Loja', amount=Decimal('1000.00'), date=date(2026, 9, 5),
            credit_card=self.a.cartao, invoice=self.a.fatura, category=self.a.despesa,
        )
        url = f'/api/invoices/{self.a.fatura.id}/pay/'
        corpo = {'account_id': str(pagadora.id), 'amount': '1000.00', 'date': '2026-09-20'}

        respostas = self.em_paralelo(2, lambda c: c.post(url, corpo, format='json'))

        self.assertEqual(sorted(r.status_code for r in respostas), [200, 400])
        recusa = next(r for r in respostas if r.status_code == 400)
        self.assertEqual(recusa.data, {'detail': FATURA_JA_PAGA, 'code': 'invalid'})
        self.assertEqual(self.saldo(pagadora), Decimal('2000.00'))
        # A conta padrão do cartão não muda
        self.assertEqual(self.saldo(self.a.conta), Decimal('1000.00'))

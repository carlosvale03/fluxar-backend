"""
Base dos testes de saldo.

Cada usuário tem uma conta corrente com saldo inicial de R$ 1.000,00, uma
poupança zerada, um cofrinho com meta, um cartão pago pela conta corrente com
uma fatura e categorias de receita e de despesa. O usuário B serve para os
testes que gravam à força dados de outro usuário nas contas de A.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from rest_framework.test import APITestCase

from accounts.models import Account, CreditCard, CreditCardInvoice
from api.models import User
from goals.models import Goal
from transactions.models import Category, Transaction

URL_TRANSACOES = '/api/transactions/'


def criar_dados(letra):
    """
    Cria um usuário e os objetos dele. A criação pelo ORM já dispara as
    categorias padrão e a conta "Carteira" (transactions/signals.py).
    """
    usuario = User.objects.create_user(
        email=f'saldo.{letra.lower()}@teste.fluxar',
        password='senha-de-teste-123',
        name=f'Usuário {letra}',
    )
    conta = Account.objects.create(
        user=usuario, name=f'Corrente {letra}', type='CHECKING',
        initial_balance=Decimal('1000.00'),
    )
    poupanca = Account.objects.create(
        user=usuario, name=f'Poupança {letra}', type='SAVINGS',
        initial_balance=Decimal('0.00'),
    )
    cofrinho = Account.objects.create(
        user=usuario, name=f'Cofrinho {letra}', type='PIGGY_BANK',
        initial_balance=Decimal('0.00'),
    )
    meta = Goal.objects.create(
        user=usuario, name=f'Meta {letra}', target_amount=Decimal('500.00'),
        account=cofrinho,
    )
    cartao = CreditCard.objects.create(
        user=usuario, name=f'Cartão {letra}', limit=Decimal('5000.00'),
        closing_day=10, due_day=20, account=conta,
    )
    fatura = CreditCardInvoice.objects.create(
        card=cartao, month=9, year=2026,
        closing_date=date(2026, 9, 10), due_date=date(2026, 9, 20),
    )
    receita = Category.objects.create(user=usuario, name=f'Salário {letra}', type='INCOME')
    despesa = Category.objects.create(user=usuario, name=f'Mercado {letra}', type='EXPENSE')
    return SimpleNamespace(
        usuario=usuario, conta=conta, poupanca=poupanca, cofrinho=cofrinho,
        meta=meta, cartao=cartao, fatura=fatura, receita=receita, despesa=despesa,
    )


class SaldoTestCase(APITestCase):
    """Usuários A (`self.a`) e B (`self.b`), com o cliente autenticado como A."""

    @classmethod
    def setUpTestData(cls):
        cls.a = criar_dados('A')
        cls.b = criar_dados('B')

    def setUp(self):
        self.cliente = self.como(self.a.usuario)

    def como(self, usuario):
        """Autentica o cliente de teste como `usuario` e devolve o cliente."""
        self.client.force_authenticate(user=usuario)
        return self.client

    def saldo(self, conta):
        """O saldo guardado da conta, lido do banco."""
        return Account.objects.get(pk=conta.pk).balance

    def lancar(self, conta, tipo, valor, status='COMPLETED', usuario=None, **extra):
        """Grava uma transação pelo ORM, sem passar pela API."""
        return Transaction.objects.create(
            user=usuario or conta.user, account=conta, type=tipo, status=status,
            description=extra.pop('description', 'Lançamento'),
            amount=Decimal(valor), date=extra.pop('date', date(2026, 9, 15)),
            **extra,
        )

    def payload(self, **extra):
        """Corpo de criação de uma despesa efetivada de R$ 50,00 na conta de A."""
        dados = {
            'type': 'EXPENSE', 'status': 'COMPLETED', 'description': 'Compra',
            'amount': '50.00', 'date': '2026-09-15',
            'account': str(self.a.conta.id), 'category': str(self.a.despesa.id),
        }
        dados.update(extra)
        return dados

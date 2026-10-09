"""
Base dos testes dos relatórios (spec `relatorios`).

O usuário A tem uma conta corrente sem saldo inicial, a "Carteira" criada
pelo signal e uma categoria de despesa e uma de receita; cada teste cria os
cartões, os cofrinhos e as contas de investimento que precisa.
"""
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from rest_framework.test import APITestCase

from accounts.models import Account, CreditCard
from api.models import User
from transactions.models import Category, Transaction
from transactions.services import TransactionService


def agora_em(ano, mes, dia, hora=15, minuto=0):
    """Simula `timezone.now()` no instante dado, em UTC (15h UTC = 12h em Brasília)."""
    return mock.patch(
        'django.utils.timezone.now',
        return_value=datetime(ano, mes, dia, hora, minuto, tzinfo=dt_timezone.utc),
    )


def criar_usuario(letra):
    usuario = User.objects.create_user(
        email=f'relatorios.{letra.lower()}@teste.fluxar',
        password='senha-de-teste-123',
        name=f'Usuário {letra}',
        plan='PREMIUM',
    )
    conta = Account.objects.create(user=usuario, name=f'Corrente {letra}', type='CHECKING')
    despesa = Category.objects.create(user=usuario, name=f'Mercado {letra}', type='EXPENSE')
    receita = Category.objects.create(user=usuario, name=f'Salário {letra}', type='INCOME')
    return SimpleNamespace(usuario=usuario, conta=conta, despesa=despesa, receita=receita)


class RelatoriosTestCase(APITestCase):
    """Usuário A (`self.a`), com o cliente autenticado como ele."""

    @classmethod
    def setUpTestData(cls):
        cls.a = criar_usuario('A')

    def setUp(self):
        self.client.force_authenticate(user=self.a.usuario)

    def conta(self, tipo, saldo_inicial='0.00', nome=None):
        return Account.objects.create(
            user=self.a.usuario, name=nome or tipo.title(), type=tipo,
            initial_balance=Decimal(saldo_inicial),
        )

    def lancar(self, tipo, valor, dia, status='COMPLETED', conta=None, **extra):
        """Transação de A gravada pelo ORM, na conta corrente se não houver outra."""
        extra.setdefault('description', 'Lançamento')
        return Transaction.objects.create(
            user=self.a.usuario, type=tipo, status=status, amount=Decimal(valor), date=dia,
            account=conta if conta is not None else self.a.conta, **extra,
        )

    def cartao(self, fechamento=5, vencimento=15, conta=None):
        return CreditCard.objects.create(
            user=self.a.usuario, name='Cartão', limit=Decimal('10000.00'),
            closing_day=fechamento, due_day=vencimento, account=conta or self.a.conta,
        )

    def comprar(self, cartao, valor, dia, parcelas=1, categoria=None):
        """Compra no cartão pelo service, como a rota de compra (FATURA-12, FATURA-16)."""
        return TransactionService.create_credit_card_expense(
            self.a.usuario, cartao, Decimal(valor), dia, 'Compra', categoria, installments=parcelas,
        )

    def transferir(self, origem, destino, valor, dia):
        return TransactionService.create_transfer(
            self.a.usuario, origem, destino, Decimal(valor), dia,
        )

    def ler(self, transacao):
        return Transaction.objects.get(pk=transacao.pk)

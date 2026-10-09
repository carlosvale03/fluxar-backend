"""
Base dos testes de metas.

Cada usuário tem uma conta corrente com saldo inicial de R$ 1.000,00, um
cofrinho zerado e a meta "Viagem" (alvo de R$ 1.000,00) nesse cofrinho. O
usuário B serve para os testes com a conta de outro usuário.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from rest_framework.test import APITestCase

from accounts.models import Account
from api.models import User
from goals.models import Goal, GoalDeposit
from transactions.models import Transaction
from transactions.services import TransactionService

DIA = date(2026, 9, 15)


def criar_dados(letra):
    """Cria um usuário com conta corrente, cofrinho e meta."""
    usuario = User.objects.create_user(
        email=f'metas.{letra.lower()}@teste.fluxar',
        password='senha-de-teste-123',
        name=f'Usuário {letra}',
    )
    conta = Account.objects.create(
        user=usuario, name=f'Corrente {letra}', type='CHECKING',
        initial_balance=Decimal('1000.00'), balance=Decimal('1000.00'),
    )
    cofrinho = Account.objects.create(
        user=usuario, name=f'Cofrinho {letra}', type='PIGGY_BANK',
        initial_balance=Decimal('0.00'), balance=Decimal('0.00'),
    )
    meta = Goal.objects.create(
        user=usuario, name=f'Viagem {letra}', target_amount=Decimal('1000.00'), account=cofrinho,
    )
    return SimpleNamespace(usuario=usuario, conta=conta, cofrinho=cofrinho, meta=meta)


def transferir(origem, destino, valor, data=DIA):
    """Cria uma transferência efetivada e devolve (transfer_id, saída, entrada)."""
    transfer_id = TransactionService.create_transfer(
        user=origem.user, account_from=origem, account_to=destino,
        amount=Decimal(valor), date=data, description='Transferência',
    )
    pernas = Transaction.objects.filter(transfer_id=transfer_id)
    return transfer_id, pernas.get(type='TRANSFER_OUT'), pernas.get(type='TRANSFER_IN')


def registrar(meta, tipo, valor, conta=None, transferencia=None, data=DIA, **extra):
    """
    Grava um registro de aporte ou resgate pelo ORM. Com `transferencia`
    (o retorno de `transferir`), o registro fica ligado às duas pernas.
    """
    ligacao = {}
    if transferencia is not None:
        transfer_id, saida, entrada = transferencia
        ligacao = {'transaction_id': transfer_id, 'transacao_saida': saida, 'transacao_entrada': entrada}
    return GoalDeposit.objects.create(
        goal=meta, account=conta or meta.account, amount=Decimal(valor), type=tipo,
        date=data, description=extra.pop('description', 'Registro'), **ligacao, **extra,
    )


class MetasTestCase(APITestCase):
    """Usuários A (`self.a`) e B (`self.b`), com o cliente autenticado como A."""

    def setUp(self):
        self.a = criar_dados('A')
        self.b = criar_dados('B')
        self.client.force_authenticate(user=self.a.usuario)

    def como(self, usuario):
        self.client.force_authenticate(user=usuario)
        return self.client

    def valor(self, meta):
        """O valor guardado da meta, lido do banco."""
        return Goal.objects.get(pk=meta.pk).current_amount

    def saldo(self, conta):
        """O saldo guardado da conta, lido do banco."""
        return Account.objects.get(pk=conta.pk).balance

    def recarregar(self, objeto):
        return type(objeto).objects.get(pk=objeto.pk)

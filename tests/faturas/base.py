"""
Base dos testes de faturas.

O usuário A tem uma conta corrente com saldo inicial de R$ 1.000,00 e uma
categoria de despesa; cada teste cria o cartão com os dias de fechamento e
de vencimento que precisa. O usuário B serve para os testes que gravam à
força dados de outro usuário nas faturas de A.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from rest_framework.test import APITestCase

from accounts.models import Account, CreditCard, CreditCardInvoice
from api.models import User
from transactions.models import Category, Transaction

URL_COMPRA = '/api/transactions/credit-card-expense/'
URL_TRANSACOES = '/api/transactions/'


def criar_usuario(letra):
    usuario = User.objects.create_user(
        email=f'faturas.{letra.lower()}@teste.fluxar',
        password='senha-de-teste-123',
        name=f'Usuário {letra}',
    )
    conta = Account.objects.create(
        user=usuario, name=f'Corrente {letra}', type='CHECKING',
        initial_balance=Decimal('1000.00'),
    )
    categoria = Category.objects.create(user=usuario, name=f'Mercado {letra}', type='EXPENSE')
    return SimpleNamespace(usuario=usuario, conta=conta, categoria=categoria)


class FaturasTestCase(APITestCase):
    """Usuários A (`self.a`) e B (`self.b`), com o cliente autenticado como A."""

    @classmethod
    def setUpTestData(cls):
        cls.a = criar_usuario('A')
        cls.b = criar_usuario('B')

    def setUp(self):
        self.client.force_authenticate(user=self.a.usuario)

    def cartao(self, fechamento, vencimento, usuario=None, **extra):
        """Cartão de A (ou de `usuario`) pago pela conta corrente dele."""
        dono = usuario or self.a.usuario
        conta = self.a.conta if dono == self.a.usuario else self.b.conta
        return CreditCard.objects.create(
            user=dono, name=extra.pop('name', 'Cartão'), limit=extra.pop('limit', Decimal('5000.00')),
            closing_day=fechamento, due_day=vencimento, account=extra.pop('account', conta), **extra,
        )

    def fatura(self, cartao, mes, ano):
        """A fatura do cartão que vence em `mes`/`ano`, lida do banco."""
        return CreditCardInvoice.objects.get(card=cartao, month=mes, year=ano)

    def meses(self, faturas):
        """`(mes, ano)` de cada fatura da lista."""
        return [(f.month, f.year) for f in faturas]

    def compra(self, cartao, fatura, valor, status='PENDING', usuario=None, **extra):
        """Compra no cartão gravada pelo ORM, sem passar pela API."""
        return Transaction.objects.create(
            user=usuario or cartao.user, type='CREDIT_CARD', status=status,
            account=cartao.account, credit_card=cartao, invoice=fatura,
            description=extra.pop('description', 'Compra'), amount=Decimal(valor),
            date=extra.pop('date', fatura.due_date if fatura else date(2026, 9, 5)),
            **extra,
        )

    def total(self, fatura):
        """O total guardado da fatura, lido do banco."""
        return CreditCardInvoice.objects.get(pk=fatura.pk).total_amount

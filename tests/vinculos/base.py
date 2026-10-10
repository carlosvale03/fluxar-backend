"""
Base dos testes do vínculo entre transações.

Cada usuário recebe uma conta corrente com R$ 1.000,00, uma poupança, um
cartão ligado à corrente, as categorias Lazer (com a subcategoria Cinema),
Transporte e Alimentação, e um orçamento de Lazer em setembro de 2026. As
transações nascem pelo ORM ou pelo serviço da compra no cartão, como nas
outras suítes.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from rest_framework.test import APITestCase

from accounts.models import Account, CreditCard, CreditCardInvoice
from api.models import User
from budgets.models import Budget
from budgets.services import BudgetService
from transactions.models import Category, Transaction
from transactions.services import TransactionService

SENHA = 'senha-de-teste-123'


def url_do_vinculo(transacao):
    return f'/api/transactions/{transacao.pk}/link/'


def criar_dados(letra):
    usuario = User.objects.create_user(
        email=f'vinculos.{letra.lower()}@teste.fluxar', password=SENHA, name=f'Usuário {letra}',
    )
    conta = Account.objects.create(
        user=usuario, name=f'Corrente {letra}', type='CHECKING',
        initial_balance=Decimal('1000.00'), balance=Decimal('1000.00'),
    )
    poupanca = Account.objects.create(user=usuario, name=f'Poupança {letra}', type='SAVINGS')
    cartao = CreditCard.objects.create(
        user=usuario, name=f'Cartão {letra}', limit=Decimal('5000.00'),
        closing_day=5, due_day=15, account=conta,
    )
    lazer = Category.objects.create(user=usuario, name=f'Lazer {letra}', type='EXPENSE', color='#AA0000')
    cinema = Category.objects.create(user=usuario, name=f'Cinema {letra}', type='EXPENSE', parent=lazer)
    transporte = Category.objects.create(
        user=usuario, name=f'Transporte {letra}', type='EXPENSE', color='#0000AA',
    )
    alimentacao = Category.objects.create(
        user=usuario, name=f'Alimentação {letra}', type='EXPENSE', color='#00AA00',
    )
    orcamento = Budget.objects.create(
        user=usuario, category=lazer, month=9, year=2026, amount_limit=Decimal('500.00'),
    )
    return SimpleNamespace(
        usuario=usuario, conta=conta, poupanca=poupanca, cartao=cartao, lazer=lazer, cinema=cinema,
        transporte=transporte, alimentacao=alimentacao, orcamento=orcamento,
    )


def despesa(d, descricao, valor, dia=date(2026, 9, 12), categoria=None, **extra):
    campos = {
        'user': d.usuario, 'type': 'EXPENSE', 'status': 'COMPLETED', 'account': d.conta,
        'description': descricao, 'amount': Decimal(valor), 'date': dia, 'category': categoria,
    }
    campos.update(extra)
    return Transaction.objects.create(**campos)


def compra(d, descricao, valor, parcelas=1, dia=date(2026, 9, 12), categoria=None):
    """A compra no cartão pelo serviço; devolve as parcelas, a raiz primeiro."""
    return TransactionService.create_credit_card_expense(
        user=d.usuario, card=d.cartao, amount=Decimal(valor), date=dia, description=descricao,
        category=categoria, installments=parcelas,
    )


def fotografia(d):
    """Saldos das contas, totais das faturas e uso do orçamento do usuário."""
    contas = {c.pk: c.balance for c in Account.objects.filter(user=d.usuario)}
    faturas = {f.pk: f.total_amount for f in CreditCardInvoice.objects.filter(card__user=d.usuario)}
    orcamentos = {
        o.pk: BudgetService.get_budget_usage(o)['total_spent'] for o in Budget.objects.filter(user=d.usuario)
    }
    return contas, faturas, orcamentos


class VinculosTestCase(APITestCase):

    def setUp(self):
        self.a = criar_dados('A')
        self.b = criar_dados('B')
        self.client.force_authenticate(user=self.a.usuario)

    def recarregar(self, transacao):
        return Transaction.objects.get(pk=transacao.pk)

"""
Base dos testes de isolamento entre usuários.

Cria dois usuários, A e B, cada um com o mesmo conjunto de objetos, para que
cada teste tente usar, a partir de A, os objetos de B.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from rest_framework.test import APITestCase

from accounts.models import Account, CreditCard, CreditCardInvoice
from api.models import User
from budgets.models import Budget
from goals.models import Goal
from reports.models import FocusedMonitorItem
from transactions.models import Category, Tag


def criar_dados(letra):
    """
    Cria um usuário e os objetos dele. A criação pelo ORM já dispara as
    categorias padrão e a conta "Carteira" (transactions/signals.py).
    """
    usuario = User.objects.create_user(
        email=f'usuario.{letra.lower()}@teste.fluxar',
        password='senha-de-teste-123',
        name=f'Usuário {letra}',
    )
    conta = Account.objects.create(
        user=usuario, name=f'Conta {letra}', type='CHECKING',
        initial_balance=Decimal('1000.00'), balance=Decimal('1000.00'),
    )
    cofrinho = Account.objects.create(
        user=usuario, name=f'Cofrinho {letra}', type='PIGGY_BANK',
        initial_balance=Decimal('0.00'), balance=Decimal('0.00'),
    )
    meta = Goal.objects.create(
        user=usuario, name=f'Meta {letra}', target_amount=Decimal('500.00'),
        account=cofrinho,
    )
    cartao = CreditCard.objects.create(
        user=usuario, name=f'Cartão {letra}', limit=Decimal('2000.00'),
        closing_day=10, due_day=20, account=conta,
    )
    fatura = CreditCardInvoice.objects.create(
        card=cartao, month=9, year=2026,
        closing_date=date(2026, 9, 10), due_date=date(2026, 9, 20),
    )
    categoria = Category.objects.create(
        user=usuario, name=f'Mercado {letra}', type='EXPENSE',
    )
    subcategoria = Category.objects.create(
        user=usuario, name=f'Feira {letra}', type='EXPENSE', parent=categoria,
    )
    tag = Tag.objects.create(user=usuario, name=f'Viagem {letra}')
    orcamento = Budget.objects.create(
        user=usuario, category=categoria, month=9, year=2026,
        amount_limit=Decimal('300.00'),
    )
    monitor = FocusedMonitorItem.objects.create(user=usuario, category=categoria)
    return SimpleNamespace(
        usuario=usuario, conta=conta, cofrinho=cofrinho, meta=meta,
        cartao=cartao, fatura=fatura, categoria=categoria,
        subcategoria=subcategoria, tag=tag, orcamento=orcamento,
        monitor=monitor,
    )


class DoisUsuariosTestCase(APITestCase):
    """
    Usuários A (`self.a`) e B (`self.b`), cada um com conta, cofrinho com meta,
    cartão com fatura, categoria com subcategoria, tag, orçamento e monitor de
    foco. `self.categoria_modelo` é uma categoria-modelo sem dono.
    """

    # UUID válido que não pertence a nenhum objeto.
    ID_INEXISTENTE = '00000000-0000-4000-8000-000000000000'

    @classmethod
    def setUpTestData(cls):
        cls.a = criar_dados('A')
        cls.b = criar_dados('B')
        cls.categoria_modelo = Category.objects.create(
            user=None, name='Modelo', type='EXPENSE', is_template=True,
        )

    def como(self, usuario):
        """Autentica o cliente de teste como `usuario` e devolve o cliente."""
        self.client.force_authenticate(user=usuario)
        return self.client

    def assert_mesma_recusa(self, resp_alheio, resp_inexistente, campo, mensagem=None):
        """
        Confere que a recusa de um ID de outro usuário é idêntica à de um ID
        inexistente: HTTP 400 nas duas, erro no `campo`, mesmas chaves de erro
        e mesmas mensagens. Com `mensagem`, confere também o texto do erro.
        """
        self.assertEqual(resp_alheio.status_code, 400)
        self.assertEqual(resp_inexistente.status_code, 400)
        self.assertIn(campo, resp_alheio.data)
        self.assertEqual(set(resp_alheio.data.keys()), set(resp_inexistente.data.keys()))
        self.assertEqual(resp_alheio.data, resp_inexistente.data)
        if mensagem is not None:
            self.assertEqual(resp_alheio.data[campo], [mensagem])

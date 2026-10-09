"""
Base dos testes de contratos entre o frontend e o backend.

O usuário A tem uma conta corrente com saldo inicial de R$ 1.000,00, uma
categoria de despesa e uma de receita; o usuário B serve para os testes de
isolamento. O cliente começa autenticado como A.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from rest_framework.test import APITestCase

from accounts.models import Account
from api.models import User
from transactions.models import Category, Transaction

URL_TRANSACOES = '/api/transactions/'
CHAVES_DA_PAGINA = {'count', 'total_pages', 'current_page', 'next', 'previous', 'results'}


def criar_usuario(letra, **extra):
    usuario = User.objects.create_user(
        email=f'contratos.{letra.lower()}@teste.fluxar',
        password='senha-de-teste-123',
        name=f'Usuário {letra}',
        **extra,
    )
    conta = Account.objects.create(
        user=usuario, name=f'Corrente {letra}', type='CHECKING',
        initial_balance=Decimal('1000.00'),
    )
    despesa = Category.objects.create(user=usuario, name=f'Mercado {letra}', type='EXPENSE')
    receita = Category.objects.create(user=usuario, name=f'Salário {letra}', type='INCOME')
    return SimpleNamespace(usuario=usuario, conta=conta, despesa=despesa, receita=receita)


class ContratosTestCase(APITestCase):
    """Usuários A (`self.a`) e B (`self.b`), com o cliente autenticado como A."""

    @classmethod
    def setUpTestData(cls):
        cls.a = criar_usuario('A')
        cls.b = criar_usuario('B')

    def setUp(self):
        self.client.force_authenticate(user=self.a.usuario)

    def lancar(self, tipo='EXPENSE', valor='10.00', usuario=None, conta=None, **extra):
        """Grava uma transação pelo ORM, sem passar pela API."""
        dono = usuario or self.a
        return Transaction.objects.create(
            user=dono.usuario, account=conta or dono.conta, type=tipo,
            status=extra.pop('status', 'COMPLETED'),
            description=extra.pop('description', 'Lançamento'),
            amount=Decimal(valor), date=extra.pop('date', date(2026, 9, 15)),
            **extra,
        )

    def lancar_varias(self, quantidade, **extra):
        """
        Grava `quantidade` despesas de uma vez, sem disparar os signals. Sem o
        `save()`, a `report_date` vai preenchida aqui (AD-046).
        """
        dia = extra.get('date', date(2026, 9, 15))
        return Transaction.objects.bulk_create([
            Transaction(
                user=self.a.usuario, account=self.a.conta, type='EXPENSE',
                status='COMPLETED', description=f'Lançamento {i}',
                amount=Decimal('1.00'), date=dia, report_date=dia,
            )
            for i in range(quantidade)
        ])

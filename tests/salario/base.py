"""
Base dos testes da gestão do salário.

Cada usuário nasce com o padrão do cadastro (a categoria de receita
"Salário", a Carteira e as classes Essencial e Dispensável) e recebe uma conta
corrente zerada, uma poupança, um cofrinho e a meta "Viagem" nesse cofrinho.
`hoje_em` simula o relógio do Django ao meio-dia de Brasília.
"""
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from rest_framework.test import APITestCase

from accounts.models import Account
from api.models import User
from goals.models import Goal
from transactions.models import Category, Transaction

SENHA = 'senha-de-teste-123'
URL_MODELOS = '/api/salary/models/'
URL_PLANO = '/api/salary/plan/'
URL_SIMULAR = '/api/salary/simulate/'
URL_PENDENTES = '/api/salary/pending/'
URL_REVISAO = '/api/salary/divisions/preview/'
URL_DIVISOES = '/api/salary/divisions/'
URL_REFERENCIAS = '/api/salary/references/'


def url_da_divisao(pk):
    return f'{URL_DIVISOES}{pk}/'


def url_do_desfazer(pk):
    return f'{URL_DIVISOES}{pk}/undo/'


def hoje_em(ano, mes, dia):
    """Simula `timezone.now()` às 15h UTC (12h em Brasília) do dia dado."""
    return mock.patch(
        'django.utils.timezone.now',
        return_value=datetime(ano, mes, dia, 15, 0, tzinfo=dt_timezone.utc),
    )


def criar_dados(letra):
    usuario = User.objects.create_user(
        email=f'salario.{letra.lower()}@teste.fluxar', password=SENHA, name=f'Usuário {letra}',
    )
    conta = Account.objects.create(user=usuario, name=f'Corrente {letra}', type='CHECKING')
    poupanca = Account.objects.create(user=usuario, name=f'Poupança {letra}', type='SAVINGS')
    cofrinho = Account.objects.create(user=usuario, name=f'Cofrinho {letra}', type='PIGGY_BANK')
    viagem = Goal.objects.create(
        user=usuario, name=f'Viagem {letra}', target_amount=Decimal('6000.00'), account=cofrinho,
    )
    salario = Category.objects.get(user=usuario, name='Salário', type='INCOME')
    return SimpleNamespace(
        usuario=usuario, conta=conta, poupanca=poupanca, cofrinho=cofrinho, viagem=viagem, salario=salario,
    )


def receita(d, valor='3000.00', data=date(2026, 10, 5), categoria=None, status='COMPLETED', conta=None, **extra):
    """Uma receita do usuário `d`, por padrão um salário efetivado na conta corrente."""
    return Transaction.objects.create(
        user=d.usuario, type='INCOME', status=status, account=conta or d.conta,
        category=categoria or d.salario, description=extra.pop('description', 'Salário'),
        amount=Decimal(valor), date=data, **extra,
    )


def parte(nome, regra, valor, destino=None, account=None, goal=None, reference=''):
    """O corpo de uma parte do plano na API."""
    return {
        'name': nome, 'rule_type': regra, 'value': valor, 'destination_type': destino,
        'account': str(account.pk) if account is not None else None,
        'goal': str(goal.pk) if goal is not None else None,
        'reference': reference,
    }


def plano_50_30_20(guardar_na=None):
    """O 50/30/20 com Guardar na meta `guardar_na` (ou sem destino)."""
    return [
        parte('Essenciais', 'PERCENT', '50.00', 'SALARY_ACCOUNT', reference='ESSENCIAL'),
        parte('Dispensáveis', 'PERCENT', '30.00', 'SALARY_ACCOUNT', reference='DISPENSAVEL'),
        parte('Guardar', 'PERCENT', '20.00', 'GOAL' if guardar_na else None, goal=guardar_na),
    ]


class SalarioTestCase(APITestCase):
    """Usuários A (`self.a`) e B (`self.b`), com o cliente autenticado como A."""

    def setUp(self):
        self.a = criar_dados('A')
        self.b = criar_dados('B')
        self.client.force_authenticate(user=self.a.usuario)

    def salvar_plano(self, partes, **extra):
        resposta = self.client.put(URL_PLANO, {'parts': partes, **extra}, format='json')
        self.assertEqual(resposta.status_code, 200, resposta.data)
        return resposta

    def saldo(self, conta):
        conta.refresh_from_db()
        return conta.balance

    def valor_da_meta(self, meta):
        meta.refresh_from_db()
        return meta.current_amount

"""
Depósito dos trocos (META-38, META-39, META-40, META-43, META-44, META-45).

`POST /api/goals/spare-change/deposit/` faz, para cada conta de origem, um
aporte na meta dos trocos com a soma dos trocos pendentes dela, e marca cada
troco como depositado. Trocos de conta excluída são descartados.
"""
import threading
from decimal import Decimal

from django.core.cache import cache
from django.db import connection
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from accounts.models import Account
from core import travas
from goals.models import Goal, GoalDeposit, Troco
from transactions.models import Transaction
from tests.metas.base import DIA, MetasTestCase, criar_dados
from tests.permissoes.base import fechar, liberacao_de_testes

URL = '/api/goals/spare-change/'
DEPOSITO = '/api/goals/spare-change/deposit/'


def preparar(teste, dados, cliente):
    """Trocos ativos na meta de `dados`, com despesas de R$ 12,30 na conta A e R$ 7,60 na conta B."""
    teste.conta_b = Account.objects.create(
        user=dados.usuario, name='Conta B', type='CHECKING',
        initial_balance=Decimal('500.00'), balance=Decimal('500.00'),
    )
    resp = cliente.put(URL, {'active': True, 'goal': dados.meta.pk}, format='json')
    teste.assertEqual(resp.status_code, 200, resp.data)
    for conta, valor in ((dados.conta, '12.30'), (teste.conta_b, '7.60')):
        Transaction.objects.create(
            user=dados.usuario, type='EXPENSE', status='COMPLETED', description='Mercado',
            account=conta, amount=Decimal(valor), date=DIA,
        )


def por_conta(deposits):
    return sorted((d['account_id'], d['amount']) for d in deposits)


class DepositoDosTrocosTests(MetasTestCase):

    def setUp(self):
        super().setUp()
        preparar(self, self.a, self.client)

    def test_um_aporte_por_conta_de_origem_com_a_soma_dos_trocos_dela(self):
        resp = self.client.post(DEPOSITO)

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(por_conta(resp.data['deposits']), sorted([
            (str(self.a.conta.pk), '0.70'), (str(self.conta_b.pk), '0.40'),
        ]))
        self.assertEqual(resp.data['discarded'], 0)
        # A meta sobe R$ 1,10, e cada aporte sai da conta que pagou a despesa
        self.assertEqual(self.valor(self.a.meta), Decimal('1.10'))
        aportes = GoalDeposit.objects.filter(goal=self.a.meta, type='DEPOSIT')
        self.assertEqual(
            sorted((str(a.account_id), a.amount) for a in aportes),
            sorted([(str(self.a.conta.pk), Decimal('0.70')), (str(self.conta_b.pk), Decimal('0.40'))]),
        )
        self.assertEqual(self.saldo(self.a.conta), Decimal('1000.00') - Decimal('12.30') - Decimal('0.70'))
        self.assertEqual(self.saldo(self.conta_b), Decimal('500.00') - Decimal('7.60') - Decimal('0.40'))
        self.assertEqual(self.saldo(self.a.cofrinho), Decimal('1.10'))
        # Cada troco fica depositado e ligado ao aporte da conta dele
        for troco in Troco.objects.filter(user=self.a.usuario):
            self.assertEqual(troco.status, 'DEPOSITADO')
            self.assertEqual(troco.aporte.account_id, troco.conta_id)
        self.assertEqual(
            (self.client.get(URL).data['pending_total'], self.client.get(URL).data['pending_count']), ('0.00', 0),
        )

    def test_reenviar_o_pedido_nao_deposita_de_novo(self):
        self.client.post(DEPOSITO)

        resp = self.client.post(DEPOSITO)

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data, {'deposits': [], 'discarded': 0})
        self.assertEqual(self.valor(self.a.meta), Decimal('1.10'))
        self.assertEqual(GoalDeposit.objects.filter(goal=self.a.meta).count(), 2)

    def test_trocos_de_conta_excluida_sao_descartados(self):
        Account.objects.filter(pk=self.conta_b.pk).update(is_active=False)

        resp = self.client.post(DEPOSITO)

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(por_conta(resp.data['deposits']), [(str(self.a.conta.pk), '0.70')])
        self.assertEqual(resp.data['discarded'], 1)
        self.assertEqual(Troco.objects.get(conta=self.conta_b).status, 'DESCARTADO')
        self.assertEqual(self.valor(self.a.meta), Decimal('0.70'))
        self.assertEqual(self.client.get(URL).data['pending_count'], 0)

    def test_trocos_pendentes_continuam_depositaveis_com_os_trocos_desativados(self):
        self.client.put(URL, {'active': False}, format='json')

        resp = self.client.post(DEPOSITO)

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['deposits']), 2)
        self.assertEqual(self.valor(self.a.meta), Decimal('1.10'))

    def test_trocos_pausados_nao_sao_depositados(self):
        Goal.objects.filter(pk=self.a.meta.pk).update(is_active=False)

        resp = self.client.post(DEPOSITO)

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['detail'], 'Os trocos estão pausados. Escolha outra meta.')
        self.assertEqual(Troco.objects.filter(user=self.a.usuario, status='PENDENTE').count(), 2)
        self.assertFalse(GoalDeposit.objects.filter(goal=self.a.meta).exists())

    def test_deposito_recebe_403_com_metas_fechada(self):
        cache.clear()
        self.addCleanup(travas.invalidar)
        liberacao_de_testes(False)
        fechar('metas')

        resp = self.client.post(DEPOSITO)

        self.assertEqual(resp.status_code, 403)
        self.assertEqual((resp.data['code'], resp.data['feature']), ('plan_locked', 'metas'))
        self.assertEqual(Troco.objects.filter(user=self.a.usuario, status='PENDENTE').count(), 2)


class DepositosSimultaneosTests(TransactionTestCase):
    """Cada thread tem a própria conexão e disputa a trava da configuração de verdade."""

    def setUp(self):
        self.a = criar_dados('A')
        cliente = APIClient()
        cliente.force_authenticate(user=self.a.usuario)
        preparar(self, self.a, cliente)

    def test_dois_pedidos_simultaneos_depositam_cada_troco_uma_vez(self):
        barreira = threading.Barrier(2, timeout=20)
        respostas, erros = [], []

        def trabalho():
            try:
                cliente = APIClient()
                cliente.force_authenticate(user=self.a.usuario)
                barreira.wait()
                respostas.append(cliente.post(DEPOSITO))
            except Exception as erro:  # noqa: BLE001 - repassado ao teste abaixo
                erros.append(erro)
            finally:
                connection.close()

        threads = [threading.Thread(target=trabalho) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        self.assertFalse(any(t.is_alive() for t in threads), 'thread presa')
        self.assertEqual(erros, [])
        self.assertEqual([r.status_code for r in respostas], [200, 200])
        self.assertEqual(sorted(len(r.data['deposits']) for r in respostas), [0, 2])
        self.assertEqual(Goal.objects.get(pk=self.a.meta.pk).current_amount, Decimal('1.10'))
        self.assertEqual(GoalDeposit.objects.filter(goal=self.a.meta).count(), 2)
        self.assertEqual(Account.objects.get(pk=self.a.cofrinho.pk).balance, Decimal('1.10'))
        self.assertFalse(Troco.objects.filter(status='PENDENTE').exists())

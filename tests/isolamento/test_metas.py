from datetime import date
from decimal import Decimal

from accounts.models import Account
from goals.models import Goal, GoalDeposit
from tests.isolamento.base import DoisUsuariosTestCase

URL = '/api/goals/'


class EscritaContaDaMetaTests(DoisUsuariosTestCase):

    def setUp(self):
        self.cliente = self.como(self.a.usuario)

    def test_criacao_com_conta_de_b_e_recusada(self):
        total_metas = Goal.objects.count()
        total_contas = Account.objects.count()
        dados = {'name': 'Viagem', 'target_amount': '800.00'}

        resp_inexistente = self.cliente.post(URL, {**dados, 'account': self.ID_INEXISTENTE}, format='json')
        resp = self.cliente.post(URL, {**dados, 'account': str(self.b.cofrinho.id)}, format='json')

        self.assert_mesma_recusa(resp, resp_inexistente, 'account', 'Conta não encontrada.')
        self.assertEqual(Goal.objects.count(), total_metas)
        self.assertEqual(Account.objects.count(), total_contas)
        self.assertEqual(list(Goal.objects.filter(account=self.b.cofrinho)), [self.b.meta])

    def test_edicao_com_conta_de_b_e_recusada(self):
        url = f'{URL}{self.a.meta.id}/'
        resp_inexistente = self.cliente.patch(url, {'account': self.ID_INEXISTENTE}, format='json')
        resp = self.cliente.patch(url, {'account': str(self.b.conta.id)}, format='json')

        self.assert_mesma_recusa(resp, resp_inexistente, 'account', 'Conta não encontrada.')
        self.assertEqual(Goal.objects.get(pk=self.a.meta.pk).account, self.a.cofrinho)

    def test_criacao_com_cofrinho_automatico_continua_funcionando(self):
        resp = self.cliente.post(URL, {'name': 'Viagem', 'target_amount': '800.00'}, format='json')

        self.assertEqual(resp.status_code, 201, resp.data)
        meta = Goal.objects.get(pk=resp.data['id'])
        self.assertEqual(meta.user, self.a.usuario)
        self.assertEqual(meta.account.user, self.a.usuario)
        self.assertEqual(meta.account.type, 'PIGGY_BANK')
        self.assertEqual(resp.data['account'], meta.account.id)

    def test_criacao_com_conta_de_a_continua_funcionando(self):
        resp = self.cliente.post(URL, {
            'name': 'Viagem', 'target_amount': '800.00', 'account': str(self.a.cofrinho.id),
        }, format='json')

        self.assertEqual(resp.status_code, 201, resp.data)
        meta = Goal.objects.get(pk=resp.data['id'])
        self.assertEqual(meta.user, self.a.usuario)
        self.assertEqual(meta.account, self.a.cofrinho)
        self.assertEqual(resp.data['account'], self.a.cofrinho.id)

    def test_edicao_com_conta_de_a_continua_funcionando(self):
        resp = self.cliente.patch(
            f'{URL}{self.a.meta.id}/', {'account': str(self.a.conta.id)}, format='json',
        )

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(Goal.objects.get(pk=self.a.meta.pk).account, self.a.conta)
        self.assertEqual(resp.data['account'], self.a.conta.id)


class LeituraContaDaMetaTests(DoisUsuariosTestCase):

    def test_meta_de_b_ligada_ao_cofrinho_de_a_nao_mostra_conta_nem_movimentos_de_a(self):
        # Ligação cruzada gravada à força, como antes da correção
        Goal.objects.filter(pk=self.b.meta.pk).update(account=self.a.cofrinho)
        movimento_de_a = GoalDeposit.objects.create(
            goal=self.b.meta, account=self.a.cofrinho, amount=Decimal('70.00'),
            type='DEPOSIT', description='Automático: Salário A', date=date(2026, 9, 5),
        )
        movimento_de_b = GoalDeposit.objects.create(
            goal=self.b.meta, account=self.b.conta, amount=Decimal('30.00'),
            type='DEPOSIT', description='Aporte B', date=date(2026, 9, 6),
        )
        cliente = self.como(self.b.usuario)

        detalhe = cliente.get(f'{URL}{self.b.meta.id}/')
        lista = cliente.get(URL)

        self.assertEqual(detalhe.status_code, 200)
        self.assertIsNone(detalhe.data['account'])
        self.assertEqual([d['id'] for d in detalhe.data['deposits']], [movimento_de_b.id])
        self.assertNotIn(movimento_de_a.id, [d['id'] for d in detalhe.data['deposits']])
        self.assertNotIn('Cofrinho A', str(detalhe.data))
        self.assertNotIn('Salário A', str(detalhe.data))

        self.assertEqual(lista.status_code, 200)
        itens = lista.data['results'] if isinstance(lista.data, dict) else lista.data
        meta_na_lista = next(item for item in itens if item['id'] == self.b.meta.id)
        self.assertIsNone(meta_na_lista['account'])
        self.assertEqual([d['id'] for d in meta_na_lista['deposits']], [movimento_de_b.id])

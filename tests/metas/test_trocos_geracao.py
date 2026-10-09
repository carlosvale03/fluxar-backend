"""
Troco de cada despesa (META-36, META-41, META-42, META-44, META-45).

Com os trocos ativos, cada despesa efetivada com conta, fora dos cofrinhos e
dos ajustes de saldo, criada depois da ativação, gera um troco pendente até o
próximo real inteiro. Editar ou excluir a despesa recalcula ou remove o troco
pendente; o troco já depositado fica como está.
"""
from decimal import Decimal

from accounts.models import Account
from goals.models import Goal, GoalDeposit, Troco
from goals.valores import recalcular
from transactions.models import Transaction
from tests.metas.base import DIA, MetasTestCase, registrar, transferir

URL = '/api/goals/spare-change/'
TRANSACOES = '/api/transactions/'


class TrocoDeCadaDespesaTests(MetasTestCase):

    def setUp(self):
        super().setUp()
        self.conta_b = Account.objects.create(
            user=self.a.usuario, name='Conta B', type='CHECKING',
            initial_balance=Decimal('500.00'), balance=Decimal('500.00'),
        )
        self.ativar()

    def ativar(self, meta=None):
        resp = self.client.put(URL, {'active': True, 'goal': (meta or self.a.meta).pk}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def despesa(self, valor, conta='padrao', status='COMPLETED', descricao='Mercado'):
        return Transaction.objects.create(
            user=self.a.usuario, type='EXPENSE', status=status, description=descricao,
            account=self.a.conta if conta == 'padrao' else conta, amount=Decimal(valor), date=DIA,
        )

    def trocos(self):
        return list(
            Troco.objects.filter(user=self.a.usuario).order_by('valor')
            .values_list('despesa_id', 'conta_id', 'valor', 'status')
        )

    def test_despesas_efetivadas_geram_o_troco_ate_o_proximo_real(self):
        a = self.despesa('12.30')
        b = self.despesa('7.60', conta=self.conta_b)

        self.assertEqual(self.trocos(), [
            (b.pk, self.conta_b.pk, Decimal('0.40'), 'PENDENTE'),
            (a.pk, self.a.conta.pk, Decimal('0.70'), 'PENDENTE'),
        ])
        resp = self.client.get(URL)
        self.assertEqual((resp.data['pending_total'], resp.data['pending_count']), ('1.10', 2))

    def test_valor_inteiro_nao_gera_troco(self):
        self.despesa('12.00')

        self.assertEqual(self.trocos(), [])

    def test_despesa_pendente_gera_o_troco_so_quando_e_efetivada(self):
        despesa = self.despesa('12.30', status='PENDING')
        self.assertEqual(self.trocos(), [])

        resp = self.client.patch(f'{TRANSACOES}{despesa.pk}/', {'status': 'COMPLETED'}, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.trocos(), [(despesa.pk, self.a.conta.pk, Decimal('0.70'), 'PENDENTE')])

    def test_despesa_sem_conta_no_cofrinho_ou_ajuste_de_saldo_nao_gera_troco(self):
        self.despesa('12.30', conta=None)
        self.despesa('12.30', conta=self.a.cofrinho)
        # O ajuste de saldo de R$ 1.000,00 para R$ 987,65 é uma despesa de R$ 12,35
        resp = self.client.post(
            f'/api/accounts/{self.a.conta.pk}/adjust-balance/', {'new_balance': '987.65'}, format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(Transaction.objects.filter(
            account=self.a.conta, type='EXPENSE', description='Ajuste de saldo', amount=Decimal('12.35'),
        ).exists())

        self.assertEqual(self.trocos(), [])

    def test_despesa_criada_antes_da_ativacao_nao_gera_troco(self):
        self.client.put(URL, {'active': False}, format='json')
        despesa = self.despesa('12.30', status='PENDING')
        self.ativar()

        resp = self.client.patch(f'{TRANSACOES}{despesa.pk}/', {'status': 'COMPLETED'}, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.trocos(), [])

    def test_trocos_desativados_ou_pausados_nao_contam_despesas_novas(self):
        self.despesa('12.30')
        self.client.put(URL, {'active': False}, format='json')
        self.despesa('5.50')
        self.ativar()
        Goal.objects.filter(pk=self.a.meta.pk).update(is_active=False)
        self.despesa('3.10')

        # Só o troco de antes da desativação, que continua pendente (META-45)
        self.assertEqual([t[2] for t in self.trocos()], [Decimal('0.70')])
        self.assertTrue(self.client.get(URL).data['paused'])

    def test_editar_a_despesa_recalcula_o_troco_pendente(self):
        despesa = self.despesa('12.30')

        resp = self.client.patch(
            f'{TRANSACOES}{despesa.pk}/', {'amount': '12.80', 'account': str(self.conta_b.pk)}, format='json',
        )

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.trocos(), [(despesa.pk, self.conta_b.pk, Decimal('0.20'), 'PENDENTE')])

    def test_despesa_que_deixa_de_gerar_troco_perde_o_troco_pendente(self):
        inteira = self.despesa('12.30')
        pendente = self.despesa('7.60')
        no_cofrinho = self.despesa('3.10')

        for despesa, dados in (
            (inteira, {'amount': '13.00'}),
            (pendente, {'status': 'PENDING'}),
            (no_cofrinho, {'account': str(self.a.cofrinho.pk)}),
        ):
            resp = self.client.patch(f'{TRANSACOES}{despesa.pk}/', dados, format='json')
            self.assertEqual(resp.status_code, 200, resp.data)

        self.assertEqual(self.trocos(), [])

    def test_excluir_a_despesa_remove_o_troco_pendente(self):
        despesa = self.despesa('12.30')
        self.despesa('7.60')

        resp = self.client.delete(f'{TRANSACOES}{despesa.pk}/')

        self.assertEqual(resp.status_code, 204)
        self.assertEqual([t[2] for t in self.trocos()], [Decimal('0.40')])

    def test_despesa_com_troco_depositado_nao_mexe_no_troco_nem_no_aporte(self):
        editada = self.despesa('12.30')
        excluida = self.despesa('7.60')
        transferencia = transferir(self.a.conta, self.a.cofrinho, '1.10')
        aporte = registrar(self.a.meta, 'DEPOSIT', '1.10', conta=self.a.conta, transferencia=transferencia)
        recalcular(self.a.meta.pk)
        Troco.objects.filter(user=self.a.usuario).update(status='DEPOSITADO', aporte=aporte)

        editar = self.client.patch(f'{TRANSACOES}{editada.pk}/', {'amount': '12.80'}, format='json')
        excluir = self.client.delete(f'{TRANSACOES}{excluida.pk}/')

        self.assertEqual((editar.status_code, excluir.status_code), (200, 204))
        self.assertEqual(self.trocos(), [
            (None, self.a.conta.pk, Decimal('0.40'), 'DEPOSITADO'),
            (editada.pk, self.a.conta.pk, Decimal('0.70'), 'DEPOSITADO'),
        ])
        self.assertEqual(set(Troco.objects.values_list('aporte_id', flat=True)), {aporte.pk})
        self.assertEqual(GoalDeposit.objects.get(pk=aporte.pk).amount, Decimal('1.10'))
        self.assertEqual(self.valor(self.a.meta), Decimal('1.10'))

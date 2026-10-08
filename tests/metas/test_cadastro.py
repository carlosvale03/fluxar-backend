"""
Cadastro, troca de cofrinho e exclusão das metas (META-25 a META-31).
"""
from decimal import Decimal

from accounts.models import Account
from goals.models import Goal
from goals.valores import recalcular
from tests.metas.base import MetasTestCase, registrar

URL = '/api/goals/'
CONTA_NAO_ENCONTRADA = ['Conta não encontrada.']


class CadastroTests(MetasTestCase):

    def criar(self, **corpo):
        return self.client.post(URL, {'name': 'Carro', 'target_amount': '500.00', **corpo}, format='json')

    # --- META-25, META-26 ---

    def test_meta_sem_cofrinho_cria_um_novo_e_outra_meta_pode_usar_o_mesmo(self):
        resp = self.criar()

        self.assertEqual(resp.status_code, 201, resp.data)
        cofrinho = Account.objects.get(pk=resp.data['account'])
        self.assertEqual((cofrinho.type, cofrinho.user_id, cofrinho.name), ('PIGGY_BANK', self.a.usuario.pk, 'Cofrinho: Carro'))

        resp = self.criar(name='Moto', account=str(cofrinho.pk))

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Goal.objects.filter(account=cofrinho).count(), 2)
        itens = self.client.get(f'{URL}piggy-banks/').data
        self.assertEqual([i['account_id'] for i in itens].count(cofrinho.pk), 1)

    def test_so_aceita_cofrinho_ativo_do_usuario(self):
        excluido = Account.objects.create(user=self.a.usuario, name='Velho', type='PIGGY_BANK', is_active=False)
        metas = Goal.objects.count()

        for conta in (self.a.conta, excluido, self.b.cofrinho):
            resp = self.criar(account=str(conta.pk))
            self.assertEqual((resp.status_code, resp.data), (400, {'account': CONTA_NAO_ENCONTRADA}), conta.name)
        self.assertEqual(Goal.objects.count(), metas)

    # --- META-27 ---

    def test_nome_vazio_e_alvo_abaixo_de_um_centavo_recebem_400_no_campo(self):
        metas = Goal.objects.count()

        resp = self.criar(name='')
        self.assertEqual((resp.status_code, list(resp.data)), (400, ['name']))
        for alvo in ('0', '0.00', '-10.00'):
            resp = self.criar(target_amount=alvo)
            self.assertEqual((resp.status_code, resp.data), (400, {'target_amount': ['O valor deve ser maior que zero.']}), alvo)
        resp = self.client.patch(f'{URL}{self.a.meta.pk}/', {'target_amount': '0.00'}, format='json')
        self.assertEqual((resp.status_code, list(resp.data)), (400, ['target_amount']))
        self.assertEqual(Goal.objects.count(), metas)
        self.assertEqual(self.recarregar(self.a.meta).target_amount, Decimal('1000.00'))

    # --- META-28 ---

    def test_trocar_o_cofrinho_com_valor_e_recusado(self):
        outro = Account.objects.create(user=self.a.usuario, name='Outro', type='PIGGY_BANK')
        registrar(self.a.meta, 'DEPOSIT', '10.00')
        recalcular(self.a.meta.pk)

        resp = self.client.patch(f'{URL}{self.a.meta.pk}/', {'account': str(outro.pk)}, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['detail'], 'Resgate o valor da meta antes de trocar o cofrinho.')
        self.assertEqual(self.recarregar(self.a.meta).account_id, self.a.cofrinho.pk)

    def test_trocar_o_cofrinho_da_meta_zerada_e_aceito(self):
        outro = Account.objects.create(user=self.a.usuario, name='Outro', type='PIGGY_BANK')

        resp = self.client.patch(f'{URL}{self.a.meta.pk}/', {'account': str(outro.pk), 'name': 'Viagem'}, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.recarregar(self.a.meta).account_id, outro.pk)

    # --- META-29, META-30 ---

    def test_excluir_meta_com_valor_e_recusado(self):
        registrar(self.a.meta, 'DEPOSIT', '10.00')
        recalcular(self.a.meta.pk)

        resp = self.client.delete(f'{URL}{self.a.meta.pk}/')

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['detail'], 'Resgate o valor da meta antes de excluí-la.')
        self.assertTrue(Goal.objects.filter(pk=self.a.meta.pk).exists())

    def test_excluir_a_ultima_meta_de_um_cofrinho_zerado_avisa_o_cofrinho_vazio(self):
        resp = self.client.delete(f'{URL}{self.a.meta.pk}/')

        self.assertEqual((resp.status_code, resp.data), (200, {'piggy_bank_empty': True}))
        self.assertFalse(Goal.objects.filter(pk=self.a.meta.pk).exists())
        # O cofrinho continua até a interface pedir a exclusão dele
        self.assertTrue(Account.objects.get(pk=self.a.cofrinho.pk).is_active)

    def test_cofrinho_com_outra_meta_ou_com_saldo_nao_fica_vazio(self):
        Goal.objects.create(user=self.a.usuario, name='Carro', target_amount=Decimal('10.00'), account=self.a.cofrinho)

        resp = self.client.delete(f'{URL}{self.a.meta.pk}/')
        self.assertEqual((resp.status_code, resp.data), (200, {'piggy_bank_empty': False}))

        Account.objects.filter(pk=self.a.cofrinho.pk).update(balance=Decimal('5.00'))
        resp = self.client.delete(f'{URL}{Goal.objects.get(name="Carro").pk}/')
        self.assertEqual((resp.status_code, resp.data), (200, {'piggy_bank_empty': False}))

    # --- META-31 ---

    def test_lista_e_detalhe_nao_trazem_o_historico(self):
        registrar(self.a.meta, 'DEPOSIT', '10.00')

        lista = self.client.get(URL)
        detalhe = self.client.get(f'{URL}{self.a.meta.pk}/')

        self.assertEqual(lista.status_code, 200)
        self.assertEqual(len(lista.data), 1)
        self.assertNotIn('deposits', lista.data[0])
        self.assertNotIn('deposits', detalhe.data)

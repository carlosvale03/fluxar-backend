"""
Inativar e reativar contas (SALDO-46 a SALDO-51).

Inativar segue as regras da exclusão, com as mensagens próprias; reativar
devolve a conta às listas, aos totais e às operações, dentro do limite
`limite_contas` do plano. A lista aceita `status=active|inactive|all`.
"""
from decimal import Decimal

from accounts.models import Account
from tests.permissoes.base import fechar, liberacao_de_testes
from tests.saldo.base import SaldoTestCase, URL_TRANSACOES
from core import travas

URL = '/api/accounts/'
SALDO_NAO_ZERADO = 'Zere o saldo antes de inativar a conta: transfira ou ajuste o valor restante.'
COM_PENDENTES = 'Resolva as transações pendentes antes de inativar a conta: efetive, mova ou exclua cada uma.'
LIMITE_ATINGIDO = {
    'detail': 'Você atingiu o limite do seu plano.', 'code': 'plan_limit_reached',
    'feature': 'limite_contas', 'limit': 3,
}


class InativarContasTests(SaldoTestCase):

    def setUp(self):
        super().setUp()
        travas.invalidar()
        self.addCleanup(travas.invalidar)
        # Inativa antes da correção, com o saldo guardado desatualizado
        self.inativa = Account.objects.create(
            user=self.a.usuario, name='Antiga', type='CHECKING',
            initial_balance=Decimal('300.00'),
        )
        Account.objects.filter(pk=self.inativa.pk).update(is_active=False, balance=Decimal('0.00'))

    def inativar(self, conta):
        return self.cliente.post(f'{URL}{conta.id}/deactivate/')

    def reativar(self, conta):
        return self.cliente.post(f'{URL}{conta.id}/reactivate/')

    def ids_na_lista(self, **params):
        resp = self.cliente.get(URL, params)
        self.assertEqual(resp.status_code, 200, resp.data)
        return {item['id'] for item in resp.data}

    def ativa(self, conta):
        return Account.objects.get(pk=conta.pk).is_active

    def limitar_contas(self):
        """Limite de 3 contas no plano comum; A já usa 3 (corrente, poupança e carteira)."""
        liberacao_de_testes(False)
        fechar('limite_contas', limite=3)
        self.assertEqual(travas.uso(self.a.usuario, 'limite_contas'), 3)

    # Inativar ------------------------------------------------------------

    def test_inativa_a_conta_zerada_e_ela_sai_da_lista_padrao(self):
        resp = self.inativar(self.a.poupanca)

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['id'], str(self.a.poupanca.id))
        self.assertFalse(resp.data['is_active'])
        self.assertFalse(self.ativa(self.a.poupanca))
        poupanca = str(self.a.poupanca.id)
        self.assertNotIn(poupanca, self.ids_na_lista())
        self.assertNotIn(poupanca, self.ids_na_lista(status='active'))
        self.assertEqual(self.ids_na_lista(status='inactive'), {poupanca, str(self.inativa.id)})
        todas = self.ids_na_lista(status='all')
        self.assertEqual(todas, set(map(str, Account.objects.filter(user=self.a.usuario).values_list('id', flat=True))))
        self.assertIn(poupanca, todas)
        self.assertIn(str(self.a.conta.id), todas)

    def test_conta_com_saldo_nao_e_inativada(self):
        resp = self.inativar(self.a.conta)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data, {'detail': SALDO_NAO_ZERADO})
        self.assertTrue(self.ativa(self.a.conta))

    def test_conta_com_saldo_negativo_nao_e_inativada(self):
        self.lancar(self.a.poupanca, 'EXPENSE', '50.00')
        resp = self.inativar(self.a.poupanca)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data, {'detail': SALDO_NAO_ZERADO})
        self.assertTrue(self.ativa(self.a.poupanca))

    def test_conta_com_transacao_pendente_nao_e_inativada(self):
        self.lancar(self.a.poupanca, 'EXPENSE', '50.00', status='PENDING')
        resp = self.inativar(self.a.poupanca)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data, {'detail': COM_PENDENTES})
        self.assertTrue(self.ativa(self.a.poupanca))

    def test_inativar_a_conta_ja_inativa_responde_200_sem_mudar(self):
        self.assertEqual(self.inativar(self.a.poupanca).status_code, 200)
        resp = self.inativar(self.a.poupanca)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['is_active'])
        self.assertFalse(self.ativa(self.a.poupanca))

    def test_inativa_tem_detalhe_e_edicao_em_404_como_antes(self):
        self.assertEqual(self.cliente.get(f'{URL}{self.inativa.id}/').status_code, 404)
        resp = self.cliente.patch(f'{URL}{self.inativa.id}/', {'name': 'Nova'}, format='json')
        self.assertEqual(resp.status_code, 404)

    # Reativar ------------------------------------------------------------

    def test_reativa_a_conta_e_ela_volta_a_lista_aos_totais_e_as_operacoes(self):
        recusada = self.cliente.post(URL_TRANSACOES, self.payload(account=str(self.inativa.id)), format='json')
        self.assertEqual(recusada.status_code, 400)

        resp = self.reativar(self.inativa)

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['is_active'])
        self.assertEqual(Decimal(resp.data['balance']), Decimal('300.00'))
        self.assertTrue(self.ativa(self.inativa))
        self.assertIn(str(self.inativa.id), self.ids_na_lista())
        self.assertNotIn(str(self.inativa.id), self.ids_na_lista(status='inactive'))
        resumo = self.cliente.get('/api/reports/dashboard/').data['summary']
        self.assertEqual(Decimal(str(resumo['total_balance'])), Decimal('1300.00'))

        criada = self.cliente.post(URL_TRANSACOES, self.payload(account=str(self.inativa.id)), format='json')
        self.assertEqual(criada.status_code, 201, criada.data)
        self.assertEqual(self.saldo(self.inativa), Decimal('250.00'))

    def test_inativar_e_reativar_pela_api(self):
        self.assertEqual(self.inativar(self.a.poupanca).status_code, 200)
        resp = self.reativar(self.a.poupanca)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn(str(self.a.poupanca.id), self.ids_na_lista())

    def test_reativar_alem_do_limite_do_plano_e_recusado(self):
        self.limitar_contas()
        resp = self.reativar(self.inativa)
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(resp.data, LIMITE_ATINGIDO)
        self.assertFalse(self.ativa(self.inativa))

    def test_reativar_abaixo_do_limite_do_plano_e_aceito(self):
        liberacao_de_testes(False)
        fechar('limite_contas', limite=4)
        resp = self.reativar(self.inativa)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(self.ativa(self.inativa))

    def test_reativar_a_conta_ja_ativa_responde_200_sem_conferir_o_limite(self):
        self.limitar_contas()
        resp = self.reativar(self.a.conta)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['is_active'])

    def test_cofrinho_de_meta_reativa_no_limite_porque_nao_conta(self):
        Account.objects.filter(pk=self.a.cofrinho.pk).update(is_active=False)
        self.limitar_contas()
        resp = self.reativar(self.a.cofrinho)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(self.ativa(self.a.cofrinho))

    # Isolamento e filtro -------------------------------------------------

    def test_conta_de_outro_usuario_recebe_404_nas_duas_acoes(self):
        inativa_de_b = Account.objects.create(
            user=self.b.usuario, name='Antiga B', type='CHECKING', initial_balance=Decimal('0.00'),
        )
        Account.objects.filter(pk=inativa_de_b.pk).update(is_active=False)

        self.assertEqual(self.inativar(self.b.poupanca).status_code, 404)
        self.assertEqual(self.reativar(inativa_de_b).status_code, 404)
        self.assertTrue(self.ativa(self.b.poupanca))
        self.assertFalse(self.ativa(inativa_de_b))
        self.assertNotIn(str(inativa_de_b.id), self.ids_na_lista(status='all'))

    def test_status_invalido_recebe_400(self):
        resp = self.cliente.get(URL, {'status': 'archived'})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {'status': ['Use active, inactive ou all.']})

    def test_parametro_desconhecido_segue_recusado(self):
        resp = self.cliente.get(URL, {'ativo': 'false'})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['detail'], 'Filtro desconhecido: ativo.')

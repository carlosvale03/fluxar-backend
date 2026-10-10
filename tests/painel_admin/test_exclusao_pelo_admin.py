"""
Exclusão pelo admin de um usuário com compras no cartão, parcelas,
transferências e metas (ADMIN-28, LGPD-13).

Os dados são criados pela API, como o próprio usuário faria. O Cloudinary é
simulado.
"""
from decimal import Decimal
from unittest import mock

from rest_framework.test import APIClient

from accounts.faturas import obter_fatura
from accounts.models import Account, CreditCard, CreditCardInvoice, PagamentoDeFatura
from api.models import RegistroDeExclusao, SystemLog, User
from goals.models import Goal, GoalDeposit
from tests.lgpd.test_exclusao_definitiva import linhas_do_usuario
from transactions.models import Category, Transaction

from .base import DESTRUIR, OK, SENHA, PainelAdminTestCase, criar_usuario

IMAGEM_DA_META = 'goals/imagem-da-casa'


def criar_dados_pela_api(usuario):
    """Compra parcelada no cartão, fatura paga, transferência e meta com aportes."""
    cliente = APIClient()
    cliente.force_authenticate(user=usuario)
    corrente = Account.objects.create(
        user=usuario, name='Corrente', type='CHECKING', initial_balance=Decimal('5000.00'),
    )
    cofrinho = Account.objects.create(user=usuario, name='Cofrinho', type='PIGGY_BANK')
    categoria = Category.objects.create(user=usuario, name='Mercado', type='EXPENSE')
    cartao = CreditCard.objects.create(
        user=usuario, name='Cartão', limit=Decimal('5000.00'), closing_day=10, due_day=20, account=corrente,
    )

    def post(rota, corpo, esperado):
        resposta = cliente.post(rota, corpo, format='json')
        assert resposta.status_code == esperado, (rota, resposta.status_code, resposta.data)
        return resposta

    post('/api/transactions/credit-card-expense/', {
        'credit_card': str(cartao.id), 'amount': '600.00', 'date': '2026-08-15',
        'description': 'Geladeira', 'category': str(categoria.id), 'installments': 6,
    }, 201)
    setembro = obter_fatura(cartao, 9, 2026)
    post(f'/api/invoices/{setembro.id}/pay/', {
        'account_id': str(corrente.id), 'amount': '100.00', 'date': '2026-09-15',
    }, 200)
    post('/api/transactions/transfer/', {
        'account_from': str(corrente.pk), 'account_to': str(cofrinho.pk),
        'amount': '300.00', 'date': '2026-09-16',
    }, 201)
    meta = Goal.objects.create(
        user=usuario, name='Casa', target_amount=Decimal('10000.00'), account=cofrinho,
    )
    for dia in ('2026-09-17', '2026-09-18'):
        post(f'/api/goals/{meta.pk}/deposit/', {
            'account_id': str(corrente.pk), 'amount': '50.00', 'date': dia,
        }, 200)
    # A imagem entra depois dos aportes: a resposta do aporte monta o link da
    # imagem, e o CI não configura o cloud_name do Cloudinary
    Goal.objects.filter(pk=meta.pk).update(image=IMAGEM_DA_META)

    # Confere que o cenário existe antes da exclusão
    assert Transaction.objects.filter(user=usuario, credit_card=cartao).count() == 6
    assert PagamentoDeFatura.objects.filter(user=usuario).exists()
    assert Transaction.objects.filter(user=usuario, transfer_id__isnull=False).exists()
    assert GoalDeposit.objects.filter(goal=meta).count() == 2


class ExclusaoPeloAdminTests(PainelAdminTestCase):

    ROTAS = (
        ('/api/admin/users/{pk}/', {'admin_password': SENHA, 'permanent': True}),
        ('/api/admin/users/{pk}/hard-delete/', {'admin_password': SENHA}),
    )

    @mock.patch(DESTRUIR, return_value=OK)
    def test_exclui_o_usuario_com_cartao_parcelas_transferencias_e_metas(self, destruir):
        for numero, (rota, corpo) in enumerate(self.ROTAS):
            with self.subTest(rota=rota):
                usuario = criar_usuario(f'completo{numero}@teste.fluxar', 'Usuario Completo')
                criar_dados_pela_api(usuario)
                usuario_id = usuario.pk

                resposta = self.client.delete(rota.format(pk=usuario_id), corpo, format='json')

                self.assertEqual(resposta.status_code, 200, resposta.data)
                self.assertFalse(User.objects.filter(pk=usuario_id).exists())
                self.assertEqual({r: n for r, n in linhas_do_usuario(usuario_id).items() if n}, {})
                self.assertFalse(GoalDeposit.objects.filter(goal__user_id=usuario_id).exists())
                self.assertFalse(CreditCardInvoice.objects.filter(card__user_id=usuario_id).exists())
                self.assertIn(mock.call(IMAGEM_DA_META), destruir.call_args_list)

    @mock.patch(DESTRUIR, return_value=OK)
    def test_ficam_o_registro_da_exclusao_pelo_admin_e_o_delete_account_no_log(self, destruir):
        criar_dados_pela_api(self.usuario)
        usuario_id = self.usuario.pk

        resposta = self.client.delete(
            f'/api/admin/users/{usuario_id}/hard-delete/', {'admin_password': SENHA}, format='json',
        )

        self.assertEqual(resposta.status_code, 200, resposta.data)
        registro = RegistroDeExclusao.objects.get(usuario_id=usuario_id)
        self.assertEqual(registro.executada_por, RegistroDeExclusao.ADMIN)
        log = SystemLog.objects.get(action='DELETE_ACCOUNT', usuario_ref=usuario_id)
        self.assertEqual(log.admin_ref, self.admin.pk)
        self.assertIsNone(log.user_id)
        self.assertEqual(log.usuario_email, '')
        self.assert_sem_dado_pessoal(log)
        itens = self.client.get(f'/api/admin/users/{usuario_id}/logs/').data['results']
        self.assertEqual([item['action'] for item in itens], ['DELETE_ACCOUNT'])

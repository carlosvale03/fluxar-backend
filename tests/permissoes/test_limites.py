"""
Limites dos planos na criação de itens (PERM-16 e PERM-21).

Criar um item com o uso já maior ou igual ao limite responde 403
`{detail, code: "plan_limit_reached", feature, limit}`. Os itens que já
existem nunca são apagados nem alterados: o limite só impede criar novos.
"""
from decimal import Decimal

from rest_framework import status

from accounts.models import Account, CreditCard
from api.models import User
from core import travas
from goals.models import Goal
from transactions.models import Category, Tag

from .base import LIMITES, RECURSOS, SENHA, PermissoesTestCase, criar_admin, criar_usuario, fechar, liberacao_de_testes

LIMITE_ATINGIDO = 'Você atingiu o limite do seu plano.'


class LimitesTestCase(PermissoesTestCase):

    def setUp(self):
        super().setUp()
        liberacao_de_testes(False)
        self.usuario = criar_usuario('comum')
        self.client.force_authenticate(user=self.usuario)
        self.raiz = Category.objects.create(user=self.usuario, name='Casa', type='EXPENSE')

    def assert_limite(self, resposta, chave, limite):
        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN, getattr(resposta, 'data', None))
        self.assertEqual(
            resposta.data,
            {'detail': LIMITE_ATINGIDO, 'code': 'plan_limit_reached', 'feature': chave, 'limit': limite},
        )

    def criar(self, chave, nome):
        """Cria pela API um item que conta no limite `chave`."""
        rotas = {
            'limite_contas': ('/api/accounts/', {'name': nome, 'type': 'CHECKING', 'initial_balance': '0.00'}),
            'limite_cartoes': ('/api/credit-cards/', {'name': nome, 'limit': '500.00', 'closing_day': 1, 'due_day': 10}),
            'limite_categorias': ('/api/categories/', {'name': nome, 'type': 'EXPENSE'}),
            'limite_subcategorias': ('/api/categories/', {'name': nome, 'type': 'EXPENSE', 'parent': str(self.raiz.pk)}),
            'limite_tags': ('/api/tags/', {'name': nome}),
            'limite_metas': ('/api/goals/', {'name': nome, 'target_amount': '100.00'}),
        }
        rota, corpo = rotas[chave]
        return self.client.post(rota, corpo, format='json')

    def uso(self, chave):
        contexto = {'parent': self.raiz} if chave == 'limite_subcategorias' else {}
        return travas.uso(self.usuario, chave, **contexto)


class LimiteDeContasTests(LimitesTestCase):

    def test_com_5_contas_e_limite_2_as_5_ficam_e_a_sexta_e_recusada(self):
        Account.objects.filter(user=self.usuario).delete()
        contas = [
            Account.objects.create(user=self.usuario, name=f'Conta {i}', type='CHECKING') for i in range(5)
        ]
        fechar('limite_contas', limite=2)

        resposta = self.criar('limite_contas', 'Sexta')

        self.assert_limite(resposta, 'limite_contas', 2)
        self.assertEqual(
            set(Account.objects.filter(user=self.usuario, is_active=True).values_list('pk', flat=True)),
            {c.pk for c in contas},
        )
        self.assertEqual(len(self.client.get('/api/accounts/').data), 5)

    def test_conta_nova_so_e_criada_quando_ha_menos_ativas_que_o_limite(self):
        Account.objects.filter(user=self.usuario).delete()
        contas = [Account.objects.create(user=self.usuario, name=f'Conta {i}', type='CHECKING') for i in range(3)]
        fechar('limite_contas', limite=2)
        self.assert_limite(self.criar('limite_contas', 'Nova'), 'limite_contas', 2)

        Account.objects.filter(pk__in=[contas[0].pk, contas[1].pk]).update(is_active=False)

        self.assertEqual(self.criar('limite_contas', 'Nova').status_code, status.HTTP_201_CREATED)
        self.assert_limite(self.criar('limite_contas', 'Outra'), 'limite_contas', 2)

    def test_meta_com_cofrinho_nao_conta_no_limite_de_contas(self):
        fechar('limite_contas', limite=self.uso('limite_contas') + 1)

        resposta = self.criar('limite_metas', 'Viagem')
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)
        cofrinho = Goal.objects.get(user=self.usuario, name='Viagem').account
        self.assertEqual((cofrinho.type, cofrinho.is_active), ('PIGGY_BANK', True))

        self.assertEqual(self.criar('limite_contas', 'Corrente').status_code, status.HTTP_201_CREATED)


class CadaLimiteTests(LimitesTestCase):

    def test_cada_limite_aceita_abaixo_e_recusa_no_limite(self):
        for chave in LIMITES:
            with self.subTest(chave=chave):
                limite = self.uso(chave) + 1
                fechar(chave, limite=limite)

                resposta = self.criar(chave, f'Primeiro {chave}')
                self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)
                self.assertEqual(self.uso(chave), limite)

                resposta = self.criar(chave, f'Segundo {chave}')
                self.assert_limite(resposta, chave, limite)
                self.assertEqual(self.uso(chave), limite)

    def test_limite_zero_recusa_o_primeiro_item(self):
        fechar('limite_tags', limite=0)
        self.assert_limite(self.criar('limite_tags', 'Viagem'), 'limite_tags', 0)
        self.assertFalse(Tag.objects.filter(user=self.usuario).exists())

    def test_subcategorias_contam_por_categoria_pai(self):
        outra = Category.objects.create(user=self.usuario, name='Lazer', type='EXPENSE')
        Category.objects.create(user=self.usuario, name='Aluguel', type='EXPENSE', parent=self.raiz)
        fechar('limite_subcategorias', limite=1)

        self.assert_limite(self.criar('limite_subcategorias', 'Luz'), 'limite_subcategorias', 1)
        resposta = self.client.post('/api/categories/', {
            'name': 'Cinema', 'type': 'EXPENSE', 'parent': str(outra.pk),
        }, format='json')
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)

    def test_editar_um_item_existente_nao_confere_o_limite(self):
        conta = Account.objects.create(user=self.usuario, name='Corrente', type='CHECKING')
        fechar('limite_contas', limite=0)
        resposta = self.client.patch(f'/api/accounts/{conta.pk}/', {'name': 'Principal'}, format='json')
        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)

    def test_liberacao_ligada_e_admin_ignoram_os_limites(self):
        fechar('limite_tags', limite=0)
        liberacao_de_testes(True)
        self.assertEqual(self.criar('limite_tags', 'Liberada').status_code, status.HTTP_201_CREATED)

        liberacao_de_testes(False)
        self.client.force_authenticate(user=criar_admin())
        resposta = self.client.post('/api/tags/', {'name': 'Do admin'}, format='json')
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)


class DescidaDePlanoTests(LimitesTestCase):

    def retrato(self):
        """Tudo o que o usuário tem, com os campos que importam."""
        u = self.usuario
        return {
            'contas': sorted(Account.objects.filter(user=u).values_list('name', 'is_active', 'balance')),
            'cartoes': sorted(CreditCard.objects.filter(user=u).values_list('name', 'is_active')),
            'categorias': sorted(Category.objects.filter(user=u).values_list('name', 'is_active', 'parent_id')),
            'tags': sorted(Tag.objects.filter(user=u).values_list('name', flat=True)),
            'metas': sorted(Goal.objects.filter(user=u).values_list('name', 'is_active', 'account_id')),
        }

    def test_baixar_o_plano_e_fechar_as_travas_nao_apaga_nem_altera_nada(self):
        User.objects.filter(pk=self.usuario.pk).update(plan='PREMIUM')
        for i in range(3):
            Account.objects.create(user=self.usuario, name=f'Conta {i}', type='CHECKING', initial_balance=Decimal('10.00'))
            CreditCard.objects.create(user=self.usuario, name=f'Cartão {i}', limit=Decimal('100.00'), closing_day=1, due_day=10)
            Tag.objects.create(user=self.usuario, name=f'Tag {i}')
            Category.objects.create(user=self.usuario, name=f'Sub {i}', type='EXPENSE', parent=self.raiz)
            Goal.objects.create(user=self.usuario, name=f'Meta {i}', target_amount=Decimal('50.00'))
        antes = self.retrato()

        for chave in RECURSOS:
            fechar(chave)
        for chave in LIMITES:
            fechar(chave, limite=0)
        admin = criar_admin()
        self.client.force_authenticate(user=admin)
        resposta = self.client.patch(
            f'/api/admin/users/{self.usuario.pk}/', {'plan': 'COMMON', 'admin_password': SENHA}, format='json',
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.client.force_authenticate(user=User.objects.get(pk=self.usuario.pk))

        self.assertEqual(self.retrato(), antes)
        contas_ativas = Account.objects.filter(user=self.usuario, is_active=True).count()
        self.assertEqual(len(self.client.get('/api/accounts/').data), contas_ativas)
        self.assert_limite(self.criar('limite_contas', 'Mais uma'), 'limite_contas', 0)
        self.assertEqual(self.retrato(), antes)

"""
Acesso no /auth/me e página de planos (PERM-17 e PERM-27).

O `/auth/me` informa o plano real, se o usuário é administrador, se a
liberação para testes está ligada, os recursos liberados e, para cada limite,
o valor e o uso atual. `GET /api/plans/` mostra o que cada plano libera e o
plano do usuário; exige login, mas não exige ser administrador.
"""
from rest_framework import status

from accounts.models import Account
from api.models import User
from transactions.models import Category

from .base import LIMITES, RECURSOS, PermissoesTestCase, criar_admin, criar_usuario, fechar, liberacao_de_testes

ME = '/api/auth/me/'
PLANOS = '/api/plans/'


class AcessoNoMeTests(PermissoesTestCase):

    def setUp(self):
        super().setUp()
        self.usuario = criar_usuario('comum')
        Account.objects.filter(user=self.usuario).delete()
        Account.objects.create(user=self.usuario, name='Corrente', type='CHECKING')
        self.client.force_authenticate(user=self.usuario)

    def test_comum_com_limite_de_2_contas_e_1_conta(self):
        liberacao_de_testes(False)
        fechar('limite_contas', limite=2)
        fechar('metas')

        access = self.client.get(ME).data['access']

        self.assertEqual(
            {k: access[k] for k in ('is_admin', 'testing_unlock', 'plan')},
            {'is_admin': False, 'testing_unlock': False, 'plan': 'COMMON'},
        )
        self.assertEqual(set(access['features']), set(RECURSOS))
        self.assertIs(access['features']['metas'], False)
        self.assertTrue(all(access['features'][c] is True for c in RECURSOS if c != 'metas'))
        self.assertEqual(set(access['limits']), set(LIMITES))
        self.assertEqual(access['limits']['limite_contas'], {'limit': 2, 'used': 1})
        self.assertEqual(access['limits']['limite_metas'], {'limit': None, 'used': 0})
        categorias = Category.objects.filter(user=self.usuario, is_active=True, parent__isnull=True).count()
        self.assertEqual(access['limits']['limite_categorias'], {'limit': None, 'used': categorias})
        # O uso de subcategorias é por categoria-pai e vem na tela de categorias
        self.assertEqual(access['limits']['limite_subcategorias'], {'limit': None})

    def test_com_a_liberacao_ligada_tudo_vem_liberado_com_o_plano_real(self):
        fechar('metas')
        fechar('limite_contas', limite=0)
        liberacao_de_testes(True)

        access = self.client.get(ME).data['access']

        self.assertIs(access['testing_unlock'], True)
        self.assertEqual(access['plan'], 'COMMON')
        self.assertEqual(access['features'], {c: True for c in RECURSOS})
        self.assertEqual(access['limits']['limite_contas'], {'limit': None, 'used': 1})
        self.assertEqual(self.client.get(ME).data['plan'], 'COMMON')

    def test_admin_aparece_como_administrador_com_tudo_liberado(self):
        liberacao_de_testes(False)
        fechar('metas')
        self.client.force_authenticate(user=criar_admin())
        access = self.client.get(ME).data['access']
        self.assertIs(access['is_admin'], True)
        self.assertIs(access['features']['metas'], True)

    def test_mudanca_de_plano_aparece_na_requisicao_seguinte(self):
        liberacao_de_testes(False)
        fechar('metas')
        self.assertIs(self.client.get(ME).data['access']['features']['metas'], False)
        User.objects.filter(pk=self.usuario.pk).update(plan='PREMIUM')
        self.client.force_authenticate(user=User.objects.get(pk=self.usuario.pk))
        access = self.client.get(ME).data['access']
        self.assertEqual(access['plan'], 'PREMIUM')
        self.assertIs(access['features']['metas'], True)

    def test_painel_admin_nao_mostra_o_acesso_do_usuario(self):
        self.client.force_authenticate(user=criar_admin())
        resposta = self.client.get(f'/api/admin/users/{self.usuario.pk}/')
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertNotIn('access', resposta.data)


class PaginaDePlanosTests(PermissoesTestCase):

    def test_mostra_as_24_travas_com_os_valores_dos_tres_planos_e_o_plano_do_usuario(self):
        fechar('exportacao_pdf', 'COMMON')
        fechar('limite_contas', 'PREMIUM', limite=5)
        self.client.force_authenticate(user=criar_usuario('premium', plan='PREMIUM'))

        resposta = self.client.get(PLANOS)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data['plan'], 'PREMIUM')
        catalogo = {t['key']: t for t in resposta.data['catalog']}
        self.assertEqual([t['key'] for t in resposta.data['catalog']], RECURSOS + LIMITES)
        for item in catalogo.values():
            self.assertTrue(item['name'] and item['description'])
            self.assertEqual(set(item['values']), {'COMMON', 'PREMIUM', 'PREMIUM_PLUS'})
        self.assertEqual(catalogo['exportacao_pdf']['type'], 'feature')
        self.assertEqual(catalogo['exportacao_pdf']['values'], {'COMMON': False, 'PREMIUM': True, 'PREMIUM_PLUS': True})
        self.assertEqual(catalogo['limite_contas']['type'], 'limit')
        self.assertEqual(
            catalogo['limite_contas']['values'],
            {'COMMON': {'limit': None}, 'PREMIUM': {'limit': 5}, 'PREMIUM_PLUS': {'limit': None}},
        )

    def test_exige_login_mas_nao_exige_admin(self):
        self.assertEqual(self.client.get(PLANOS).status_code, status.HTTP_401_UNAUTHORIZED)
        self.client.force_authenticate(user=criar_usuario('comum'))
        self.assertEqual(self.client.get(PLANOS).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(PLANOS, {'plano': 'x'}).status_code, status.HTTP_400_BAD_REQUEST)

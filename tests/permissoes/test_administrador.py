"""
Administrador pelo papel (PERM-01, PERM-02, PERM-04 e PERM-08).

O administrador do app é quem tem `role == 'ADMIN'` no banco, com a conta
ativa (AD-016). O `is_staff` não dá acesso a nenhuma função de administração
e serve só para o admin do Django.
"""
from django.test import Client
from rest_framework import status

from api.models import User
from api.sessoes import criar_sessao
from core import manutencao

from .base import SENHA, PermissoesTestCase, criar_admin, criar_usuario


def funcoes_de_administracao():
    """
    Cada função de administração da PERM-02, como (nome, método, rota, corpo).
    A rota, e o corpo quando é uma função, são montados a partir do usuário
    afetado.
    """
    return [
        ('listar e buscar usuários', 'get', lambda v: '/api/admin/users/?search=vitima', None),
        ('detalhes do usuário', 'get', lambda v: f'/api/admin/users/{v.pk}/', None),
        ('estatísticas financeiras', 'get', lambda v: f'/api/admin/users/{v.pk}/financial-stats/', None),
        ('logs do usuário', 'get', lambda v: f'/api/admin/users/{v.pk}/logs/', None),
        ('mudar plano', 'patch', lambda v: f'/api/admin/users/{v.pk}/',
         {'plan': 'PREMIUM', 'admin_password': SENHA}),
        ('mudar papel', 'patch', lambda v: f'/api/admin/users/{v.pk}/',
         {'role': 'ADMIN', 'admin_password': SENHA}),
        ('mudar status', 'patch', lambda v: f'/api/admin/users/{v.pk}/',
         {'is_active': False, 'admin_password': SENHA}),
        ('arquivar', 'delete', lambda v: f'/api/admin/users/{v.pk}/', {'admin_password': SENHA}),
        ('arquivar em massa', 'delete', lambda v: '/api/admin/users/',
         lambda v: {'admin_password': SENHA, 'user_ids': [str(v.pk)]}),
        ('excluir definitivamente', 'delete', lambda v: f'/api/admin/users/{v.pk}/hard-delete/',
         {'admin_password': SENHA}),
        ('limpar dados', 'post', lambda v: f'/api/admin/users/{v.pk}/clear-data/', {'admin_password': SENHA}),
        ('redefinir a senha', 'post', lambda v: f'/api/admin/users/{v.pk}/reset-password/',
         {'admin_password': SENHA, 'new_password': 'Outra-Senha-Forte-2026'}),
        ('estatísticas globais', 'get', lambda v: '/api/admin/stats/', None),
        ('logs globais', 'get', lambda v: '/api/admin/logs/', None),
        ('ver a manutenção', 'get', lambda v: '/api/admin/settings/', None),
        ('ligar ou desligar a manutenção', 'post', lambda v: '/api/admin/settings/',
         {'maintenance_mode': False}),
    ]


class AdministradorPeloPapelTests(PermissoesTestCase):

    def setUp(self):
        super().setUp()
        self.addCleanup(manutencao.invalidar)
        self.vitimas = 0

    def nova_vitima(self):
        self.vitimas += 1
        return criar_usuario(f'vitima{self.vitimas}')

    def chamar(self, metodo, rota, corpo, vitima):
        if callable(corpo):
            corpo = corpo(vitima)
        return getattr(self.client, metodo)(rota(vitima), corpo, format='json')

    def test_is_staff_sem_o_papel_recebe_403_em_cada_funcao(self):
        staff = criar_usuario('staff', is_staff=True, is_superuser=True)
        self.client.force_authenticate(user=staff)
        for nome, metodo, rota, corpo in funcoes_de_administracao():
            with self.subTest(funcao=nome):
                vitima = self.nova_vitima()
                resposta = self.chamar(metodo, rota, corpo, vitima)
                self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)
                vitima.refresh_from_db()
                self.assertEqual(
                    (vitima.is_active, vitima.plan, vitima.role, vitima.check_password(SENHA)),
                    (True, 'COMMON', 'USER', True),
                )

    def test_usuario_comum_recebe_403_em_cada_funcao(self):
        self.client.force_authenticate(user=criar_usuario('comum'))
        for nome, metodo, rota, corpo in funcoes_de_administracao():
            with self.subTest(funcao=nome):
                resposta = self.chamar(metodo, rota, corpo, self.nova_vitima())
                self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_sem_is_staff_usa_cada_funcao(self):
        admin = criar_admin()
        self.assertFalse(admin.is_staff)
        self.client.force_authenticate(user=admin)
        for nome, metodo, rota, corpo in funcoes_de_administracao():
            with self.subTest(funcao=nome):
                resposta = self.chamar(metodo, rota, corpo, self.nova_vitima())
                self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.content)

    def test_admin_com_a_conta_desativada_nao_e_administrador(self):
        # A conta desativada não autentica: a função de administração não é usada
        admin = criar_admin(is_active=False)
        self.client.force_authenticate(user=admin)
        resposta = self.client.get('/api/admin/stats/')
        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)

    def test_mudanca_de_papel_vale_na_requisicao_seguinte_com_o_mesmo_token(self):
        usuario = criar_usuario('promovido')
        access, _ = criar_sessao(usuario)
        cabecalho = {'HTTP_AUTHORIZATION': f'Bearer {access}'}

        self.assertEqual(self.client.get('/api/admin/stats/', **cabecalho).status_code, 403)

        User.objects.filter(pk=usuario.pk).update(role='ADMIN')
        self.assertEqual(self.client.get('/api/admin/stats/', **cabecalho).status_code, 200)

        User.objects.filter(pk=usuario.pk).update(role='USER')
        self.assertEqual(self.client.get('/api/admin/stats/', **cabecalho).status_code, 403)

    def test_promovido_pelo_painel_acessa_e_rebaixado_perde_o_acesso(self):
        admin = criar_admin()
        usuario = criar_usuario('promovido')
        access, _ = criar_sessao(usuario)
        cabecalho = {'HTTP_AUTHORIZATION': f'Bearer {access}'}
        self.client.force_authenticate(user=admin)

        resposta = self.client.patch(
            f'/api/admin/users/{usuario.pk}/', {'role': 'ADMIN', 'admin_password': SENHA}, format='json',
        )
        self.assertEqual(resposta.status_code, 200)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get('/api/admin/users/', **cabecalho).status_code, 200)

        self.client.force_authenticate(user=admin)
        resposta = self.client.patch(
            f'/api/admin/users/{usuario.pk}/', {'role': 'USER', 'admin_password': SENHA}, format='json',
        )
        self.assertEqual(resposta.status_code, 200)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get('/api/admin/users/', **cabecalho).status_code, 403)


class AdminDoDjangoTests(PermissoesTestCase):
    """O admin do Django (`/admin/`) exige `is_staff`, e não o papel (PERM-08)."""

    def test_admin_pelo_papel_sem_is_staff_nao_entra(self):
        cliente = Client()
        cliente.force_login(criar_admin(is_superuser=True))
        resposta = cliente.get('/admin/')
        self.assertEqual(resposta.status_code, 302)
        self.assertIn('/admin/login/', resposta['Location'])

    def test_quem_tem_is_staff_entra(self):
        cliente = Client()
        cliente.force_login(criar_usuario('staff', is_staff=True, is_superuser=True))
        self.assertEqual(cliente.get('/admin/').status_code, 200)

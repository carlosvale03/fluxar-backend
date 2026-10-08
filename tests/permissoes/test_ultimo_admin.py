"""
Último administrador e a própria conta (PERM-05 e PERM-06).

Nenhuma mudança de papel, arquivamento ou exclusão pode deixar o sistema sem
administrador ativo, e o administrador não tira o próprio papel nem arquiva ou
exclui a própria conta pelo painel. Como quem age é sempre um administrador
ativo, o último administrador só pode ser afetado por uma ação sobre a própria
conta; por isso a regra do último administrador é conferida antes.
"""
from rest_framework import status

from api.models import User

from .base import SENHA, PermissoesTestCase, criar_admin

ULTIMO_ADMIN = 'O sistema precisa ter pelo menos um administrador ativo.'
PROPRIA_CONTA = (
    'Você não pode remover o próprio acesso de administrador nem arquivar ou excluir a própria '
    'conta pelo painel.'
)


def acoes_sobre(usuario):
    """Cada forma de tirar o papel, arquivar ou excluir `usuario` pelo painel."""
    rota = f'/api/admin/users/{usuario.pk}/'
    return [
        ('tirar o papel', 'patch', rota, {'role': 'USER', 'admin_password': SENHA}),
        ('desativar pela edição', 'patch', rota, {'is_active': False, 'admin_password': SENHA}),
        ('arquivar', 'delete', rota, {'admin_password': SENHA}),
        ('arquivar em massa', 'delete', '/api/admin/users/',
         {'admin_password': SENHA, 'user_ids': [str(usuario.pk)]}),
        ('excluir', 'delete', rota, {'admin_password': SENHA, 'permanent': True}),
        ('excluir definitivamente', 'delete', f'{rota}hard-delete/', {'admin_password': SENHA}),
    ]


class UltimoAdministradorTests(PermissoesTestCase):

    def chamar(self, metodo, rota, corpo):
        return getattr(self.client, metodo)(rota, corpo, format='json')

    def assert_intacto(self, usuario):
        usuario = User.objects.get(pk=usuario.pk)
        self.assertEqual((usuario.role, usuario.is_active), ('ADMIN', True))

    def test_ultimo_admin_ativo_nao_perde_o_papel_nem_e_arquivado_ou_excluido(self):
        unico = criar_admin()
        self.client.force_authenticate(user=unico)
        for nome, metodo, rota, corpo in acoes_sobre(unico):
            with self.subTest(acao=nome):
                resposta = self.chamar(metodo, rota, corpo)
                self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(resposta.data['detail'], ULTIMO_ADMIN)
                self.assert_intacto(unico)

    def test_admin_arquivado_nao_conta_como_administrador_ativo(self):
        criar_admin('arquivado', is_active=False)
        unico_ativo = criar_admin()
        self.client.force_authenticate(user=unico_ativo)
        resposta = self.client.patch(
            f'/api/admin/users/{unico_ativo.pk}/', {'role': 'USER', 'admin_password': SENHA}, format='json',
        )
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resposta.data['detail'], ULTIMO_ADMIN)
        self.assert_intacto(unico_ativo)

    def test_com_dois_admins_ativos_rebaixar_um_e_aceito(self):
        ana = criar_admin('ana')
        bia = criar_admin('bia')
        self.client.force_authenticate(user=ana)
        resposta = self.client.patch(
            f'/api/admin/users/{bia.pk}/', {'role': 'USER', 'admin_password': SENHA}, format='json',
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(User.objects.get(pk=bia.pk).role, 'USER')

    def test_com_dois_admins_ativos_arquivar_ou_excluir_o_outro_e_aceito(self):
        ana = criar_admin('ana')
        self.client.force_authenticate(user=ana)
        for indice in range(2, 6):
            bia = criar_admin('bia')
            nome, metodo, rota, corpo = acoes_sobre(bia)[indice]
            with self.subTest(acao=nome):
                resposta = self.chamar(metodo, rota, corpo)
                self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.content)
                self.assertFalse(User.objects.filter(pk=bia.pk, is_active=True).exists())
            User.objects.filter(pk=bia.pk).delete()

    def test_admin_nao_tira_o_proprio_papel_nem_arquiva_ou_exclui_a_propria_conta(self):
        ana = criar_admin('ana')
        criar_admin('bia')
        self.client.force_authenticate(user=ana)
        for nome, metodo, rota, corpo in acoes_sobre(ana):
            with self.subTest(acao=nome):
                resposta = self.chamar(metodo, rota, corpo)
                self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(resposta.data['detail'], PROPRIA_CONTA)
                self.assert_intacto(ana)

    def test_admin_edita_o_proprio_plano_sem_mexer_no_papel(self):
        # Só tirar o papel, arquivar e excluir são recusados (PERM-06)
        ana = criar_admin('ana')
        self.client.force_authenticate(user=ana)
        resposta = self.client.patch(
            f'/api/admin/users/{ana.pk}/', {'plan': 'PREMIUM', 'admin_password': SENHA}, format='json',
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(User.objects.get(pk=ana.pk).plan, 'PREMIUM')

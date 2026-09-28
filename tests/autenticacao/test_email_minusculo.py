"""
E-mail sem diferença de maiúsculas e minúsculas (AUTH-02).

O e-mail é guardado em minúsculas e o login ignora a caixa. Uma conta antiga,
gravada antes da correção com maiúsculas, continua entrando com o e-mail exato
até a resolução manual (AUTH-44).
"""
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import User

SENHA = 'senha-de-teste-123'
LOGIN = '/api/auth/login/'


class EmailSemDiferencaDeCaixaTests(APITestCase):

    def test_cadastro_pelo_manager_grava_o_email_em_minusculas(self):
        usuario = User.objects.create_user(email='Ana@X.com', password=SENHA, name='Ana')

        usuario.refresh_from_db()
        self.assertEqual(usuario.email, 'ana@x.com')

    def test_superusuario_tambem_grava_o_email_em_minusculas(self):
        usuario = User.objects.create_superuser(email='Admin@X.COM', password=SENHA, name='Admin')

        usuario.refresh_from_db()
        self.assertEqual(usuario.email, 'admin@x.com')

    def test_login_com_outra_caixa_entra_na_conta(self):
        # Verificada, porque a conta pendente não entra (AUTH-13)
        usuario = User.objects.create_user(
            email='Ana@X.com', password=SENHA, name='Ana', email_verified=True,
        )

        resposta = self.client.post(LOGIN, {'email': 'ANA@X.COM', 'password': SENHA}, format='json')

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertIn('access', resposta.data)
        self.assertIn('refresh', resposta.data)
        self.assertEqual(User.objects.get_by_natural_key('ANA@X.COM').pk, usuario.pk)

    def test_conta_antiga_com_maiusculas_entra_com_o_email_exato(self):
        usuario = User.objects.create_user(
            email='caio@x.com', password=SENHA, name='Caio', email_verified=True,
        )
        # Grava à força o e-mail com maiúsculas, como uma conta de antes da correção
        User.objects.filter(pk=usuario.pk).update(email='Caio@x.com')

        resposta = self.client.post(LOGIN, {'email': 'Caio@x.com', 'password': SENHA}, format='json')

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertIn('access', resposta.data)
        self.assertEqual(User.objects.get_by_natural_key('Caio@x.com').pk, usuario.pk)

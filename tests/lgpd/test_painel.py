"""
Dados pessoais mascarados no painel admin (LGPD-19).
"""
import datetime
from decimal import Decimal

from rest_framework.test import APITestCase

from api.models import User

SENHA = 'senha-de-teste-123'


class DadosNoPainelTests(APITestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser(email='admin@teste.fluxar', password=SENHA, name='Admin')
        self.usuario = User.objects.create_user(
            email='cliente@teste.fluxar', password=SENHA, name='Cliente', email_verified=True,
            cpf='52998224712', phone_number='86999990000',
            date_of_birth=datetime.date(1990, 5, 17), monthly_income=Decimal('4321.50'),
        )

    def test_detalhe_traz_cpf_e_telefone_mascarados(self):
        self.client.force_authenticate(user=self.admin)

        dados = self.client.get(f'/api/admin/users/{self.usuario.pk}/').data

        self.assertEqual(dados['cpf'], '***.***.***-12')
        self.assertEqual(dados['phone_number'], '*******0000')

    def test_detalhe_e_lista_nao_trazem_nascimento_nem_renda(self):
        self.client.force_authenticate(user=self.admin)

        detalhe = self.client.get(f'/api/admin/users/{self.usuario.pk}/').data
        lista = self.client.get('/api/admin/users/').data['results']
        na_lista = next(item for item in lista if item['id'] == str(self.usuario.pk))

        for dados in (detalhe, na_lista):
            self.assertNotIn('date_of_birth', dados)
            self.assertNotIn('monthly_income', dados)
        self.assertEqual(na_lista['cpf'], '***.***.***-12')
        self.assertEqual(na_lista['phone_number'], '*******0000')

    def test_o_proprio_usuario_ve_os_dados_completos(self):
        self.client.force_authenticate(user=self.usuario)

        dados = self.client.get('/api/auth/me/').data

        self.assertEqual(dados['cpf'], '52998224712')
        self.assertEqual(dados['phone_number'], '86999990000')
        self.assertEqual(dados['date_of_birth'], '1990-05-17')
        self.assertEqual(dados['monthly_income'], '4321.50')

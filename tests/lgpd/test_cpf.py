"""
Validação do CPF pelos dígitos verificadores (LGPD-17, LGPD-18).
"""
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from api.models import User

SENHA = 'senha-de-teste-123'
CPF_VALIDO = '52998224725'


class ValidacaoDoCpfTests(APITestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(email='cpf@teste.fluxar', password=SENHA, name='Pessoa')
        self.client.force_authenticate(user=self.usuario)

    def salvar(self, cpf):
        return self.client.put('/api/auth/me/', {'cpf': cpf}, format='json')

    def cpf_gravado(self):
        return User.objects.get(pk=self.usuario.pk).cpf

    def test_digito_verificador_errado_recebe_400(self):
        for cpf in ('52998224724', '529.982.247-15'):
            with self.subTest(cpf=cpf):
                resposta = self.salvar(cpf)
                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.data, {'cpf': ['CPF inválido.']})
        self.assertIsNone(self.cpf_gravado())

    def test_sequencia_repetida_recebe_400(self):
        for cpf in ('111.111.111-11', '00000000000'):
            with self.subTest(cpf=cpf):
                resposta = self.salvar(cpf)
                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.data, {'cpf': ['CPF inválido.']})

    def test_quantidade_errada_de_digitos_recebe_400(self):
        resposta = self.salvar('5299822472')
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data, {'cpf': ['CPF inválido.']})

    def test_cpf_valido_com_ou_sem_pontuacao_e_guardado_com_11_digitos(self):
        for cpf in ('529.982.247-25', CPF_VALIDO):
            with self.subTest(cpf=cpf):
                resposta = self.salvar(cpf)
                self.assertEqual(resposta.status_code, 200, resposta.data)
                self.assertEqual(resposta.data['cpf'], CPF_VALIDO)
                self.assertEqual(self.cpf_gravado(), CPF_VALIDO)

    def test_cpf_de_outra_conta_e_aceito_sem_consultar_a_outra_conta(self):
        User.objects.create_user(email='dono@teste.fluxar', password=SENHA, name='Outra', cpf=CPF_VALIDO)

        with CaptureQueriesContext(connection) as consultas:
            resposta = self.salvar('529.982.247-25')

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(self.cpf_gravado(), CPF_VALIDO)
        filtros_por_cpf = [
            consulta['sql'] for consulta in consultas.captured_queries
            if 'WHERE' in consulta['sql'] and '"cpf"' in consulta['sql'].split('WHERE', 1)[1]
        ]
        self.assertEqual(filtros_por_cpf, [])

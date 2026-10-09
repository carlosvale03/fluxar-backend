"""
Dados pessoais do usuário criptografados no banco (LGPD-15, LGPD-18, LGPD-24).

A coluna é lida direto pelo cursor, sem passar pelo campo, para conferir o
que de fato fica gravado. A migração de dados é testada importando o módulo,
com valores antigos em texto puro gravados também pelo cursor.
"""
import datetime
import importlib
from decimal import Decimal

import django.apps
from django.db import connection
from rest_framework.test import APITestCase

from api.models import User

SENHA = 'senha-de-teste-123'
CPF = '52998224725'


def criar_usuario(email, **dados):
    return User.objects.create_user(email=email, password=SENHA, name='Pessoa de Teste', **dados)


def colunas(usuario):
    """CPF, telefone, nascimento e renda como estão gravados na tabela."""
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT cpf, phone_number, date_of_birth, monthly_income FROM api_user WHERE id = %s',
            [usuario.pk],
        )
        return cursor.fetchone()


def gravar_em_texto_puro(usuario, cpf, telefone, nascimento, renda):
    """Simula um usuário de antes da correção, com os quatro dados em claro."""
    with connection.cursor() as cursor:
        cursor.execute(
            'UPDATE api_user SET cpf = %s, phone_number = %s, date_of_birth = %s, monthly_income = %s '
            'WHERE id = %s',
            [cpf, telefone, nascimento, renda, usuario.pk],
        )


def rodar_migracao():
    modulo = importlib.import_module('api.migrations.0014_dados_pessoais_criptografados')
    modulo.criptografar_dados_pessoais(django.apps.apps, None)


class PerfilCriptografadoTests(APITestCase):

    def setUp(self):
        self.usuario = criar_usuario('perfil@teste.fluxar')
        self.client.force_authenticate(user=self.usuario)

    def test_perfil_salvo_fica_criptografado_e_volta_completo(self):
        resposta = self.client.put('/api/auth/me/', {
            'cpf': CPF,
            'phone_number': '86999990000',
            'date_of_birth': '1990-05-17',
            'monthly_income': '4321.50',
        }, format='json')
        self.assertEqual(resposta.status_code, 200, resposta.data)

        cpf, telefone, nascimento, renda = colunas(self.usuario)
        self.assertNotIn(CPF, cpf)
        self.assertNotIn('529982', cpf)
        self.assertNotIn('99999', telefone)
        self.assertNotIn('1990', nascimento)
        self.assertNotIn('4321', renda)

        perfil = self.client.get('/api/auth/me/').data
        self.assertEqual(perfil['cpf'], CPF)
        self.assertEqual(perfil['phone_number'], '86999990000')
        self.assertEqual(perfil['date_of_birth'], '1990-05-17')
        self.assertEqual(perfil['monthly_income'], '4321.50')

    def test_dois_usuarios_salvam_o_mesmo_cpf(self):
        outro = criar_usuario('outro@teste.fluxar', cpf=CPF)

        resposta = self.client.put('/api/auth/me/', {'cpf': CPF}, format='json')

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(User.objects.get(pk=self.usuario.pk).cpf, CPF)
        self.assertEqual(User.objects.get(pk=outro.pk).cpf, CPF)


class MigracaoDosDadosPessoaisTests(APITestCase):

    def test_dados_em_texto_puro_ficam_criptografados_com_os_mesmos_valores(self):
        antigo = criar_usuario('antigo@teste.fluxar')
        gravar_em_texto_puro(antigo, '529.982.247-25', '(86) 99999-0000', '1990-05-17', '4321.50')

        rodar_migracao()

        cpf, telefone, nascimento, renda = colunas(antigo)
        self.assertNotIn('529', cpf)
        self.assertNotIn('99999', telefone)
        self.assertNotIn('1990', nascimento)
        self.assertNotIn('4321', renda)

        antigo = User.objects.get(pk=antigo.pk)
        # O CPF passa a ser guardado só com os dígitos
        self.assertEqual(antigo.cpf, CPF)
        self.assertEqual(antigo.phone_number, '(86) 99999-0000')
        self.assertEqual(antigo.date_of_birth, datetime.date(1990, 5, 17))
        self.assertEqual(antigo.monthly_income, Decimal('4321.50'))

        self.client.force_authenticate(user=antigo)
        perfil = self.client.get('/api/auth/me/').data
        self.assertEqual(perfil['cpf'], CPF)
        self.assertEqual(perfil['date_of_birth'], '1990-05-17')
        self.assertEqual(perfil['monthly_income'], '4321.50')

    def test_campos_vazios_continuam_vazios(self):
        vazio = criar_usuario('vazio@teste.fluxar')

        rodar_migracao()

        self.assertEqual(colunas(vazio), (None, None, None, None))

    def test_valores_ja_criptografados_nao_mudam(self):
        atual = criar_usuario(
            'atual@teste.fluxar', cpf=CPF, phone_number='86988887777',
            date_of_birth=datetime.date(1985, 1, 2), monthly_income=Decimal('1500.00'),
        )
        antes = colunas(atual)

        rodar_migracao()

        self.assertEqual(colunas(atual), antes)
        atual = User.objects.get(pk=atual.pk)
        self.assertEqual(atual.cpf, CPF)
        self.assertEqual(atual.monthly_income, Decimal('1500.00'))

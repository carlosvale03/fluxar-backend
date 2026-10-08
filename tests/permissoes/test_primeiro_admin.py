"""
Primeiro administrador e divergências de papel (PERM-07 e PERM-29).

O `create_admin.py` roda a cada boot: cria o administrador configurado só
quando não há nenhum administrador ativo e nunca altera contas existentes. O
comando `divergencias_de_admin` lista quem tem `is_staff` sem o papel `ADMIN`
e quem tem o papel sem `is_staff`, sem alterar ninguém.
"""
import os
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from api.models import User
from create_admin import create_admin

from .base import criar_admin, criar_usuario

AMBIENTE = {
    'DJANGO_SUPERUSER_NAME': 'Primeiro Admin',
    'DJANGO_SUPERUSER_EMAIL': 'primeiro@permissoes.fluxar',
    'DJANGO_SUPERUSER_PASSWORD': 'Senha-Do-Primeiro-2026',
}


def estado(usuario):
    usuario = User.objects.get(pk=usuario.pk)
    return (usuario.role, usuario.is_staff, usuario.is_superuser, usuario.plan, usuario.is_active)


@mock.patch.dict(os.environ, AMBIENTE)
class PrimeiroAdminTests(TestCase):

    def rodar(self):
        with mock.patch('sys.stdout', new_callable=StringIO):
            create_admin()

    def test_com_admin_ativo_nao_cria_nem_promove_ninguem(self):
        criar_admin('atual')
        configurado = criar_usuario('primeiro')  # o e-mail configurado, rebaixado antes
        antes = estado(configurado)
        total = User.objects.count()

        self.rodar()

        self.assertEqual(User.objects.count(), total)
        self.assertEqual(estado(configurado), antes)
        self.assertEqual(antes[0], 'USER')

    def test_sem_admin_ativo_cria_o_admin_configurado(self):
        criar_admin('arquivado', is_active=False)

        self.rodar()

        novo = User.objects.get(email='primeiro@permissoes.fluxar')
        self.assertEqual(estado(novo), ('ADMIN', True, True, 'PREMIUM_PLUS', True))
        self.assertEqual(novo.name, 'Primeiro Admin')
        self.assertTrue(novo.email_verified)
        self.assertTrue(novo.check_password('Senha-Do-Primeiro-2026'))

    def test_sem_admin_ativo_nao_altera_a_conta_existente_do_email_configurado(self):
        configurado = criar_usuario('primeiro')
        antes = estado(configurado)

        self.rodar()

        self.assertEqual(estado(configurado), antes)
        self.assertEqual(User.objects.filter(role='ADMIN').count(), 0)


class DivergenciasDeAdminTests(TestCase):

    def rodar(self):
        saida = StringIO()
        call_command('divergencias_de_admin', stdout=saida)
        return saida.getvalue()

    def test_lista_as_divergencias_sem_alterar_nenhuma_conta(self):
        staff_sem_papel = criar_usuario('staff', is_staff=True)
        papel_sem_staff = criar_admin('papel')
        coerente_admin = criar_admin('coerente', is_staff=True)
        coerente_usuario = criar_usuario('comum')
        todos = [staff_sem_papel, papel_sem_staff, coerente_admin, coerente_usuario]
        antes = [estado(u) for u in todos]

        saida = self.rodar()

        linhas = saida.strip().splitlines()
        self.assertEqual(linhas[-1], 'Contas divergentes: 2')
        self.assertIn(f'{staff_sem_papel.pk} st***@permissoes.fluxar: is_staff sem o papel ADMIN', saida)
        self.assertIn(f'{papel_sem_staff.pk} pa***@permissoes.fluxar: papel ADMIN sem is_staff', saida)
        self.assertNotIn(str(coerente_admin.pk), saida)
        self.assertNotIn(str(coerente_usuario.pk), saida)
        self.assertNotIn('staff@permissoes.fluxar', saida)
        self.assertEqual([estado(u) for u in todos], antes)

    def test_sem_divergencias_termina_com_zero(self):
        criar_admin('coerente', is_staff=True)
        self.assertEqual(self.rodar().strip().splitlines()[-1], 'Contas divergentes: 0')

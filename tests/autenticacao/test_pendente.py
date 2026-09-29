"""
Conta pendente sem exclusão automática (AUTH-12).

O comando cleanup_inactive_users apagava as contas que não verificavam o
e-mail em 7 dias. Ele foi removido, e uma conta pendente há 60 dias continua
existindo.
"""
from contextlib import suppress
from datetime import timedelta

from django.core.management import CommandError, call_command
from django.test import TestCase
from django.utils import timezone

from api.models import User


class ContaPendenteSemExclusaoTests(TestCase):

    def criar_pendente_ha_60_dias(self, email, **estado):
        usuario = User.objects.create_user(email=email, password='senha-de-teste-123', name='Pendente')
        User.objects.filter(pk=usuario.pk).update(
            created_at=timezone.now() - timedelta(days=60), email_verified=False, **estado,
        )
        return usuario

    def test_comando_de_limpeza_nao_existe_mais(self):
        with self.assertRaises(CommandError):
            call_command('cleanup_inactive_users')

    def test_conta_pendente_ha_60_dias_continua_existindo(self):
        pendente = self.criar_pendente_ha_60_dias('pendente@fluxar.teste', is_active=True)
        # Conta pendente no formato de antes da migração 0009, que o comando apagava
        antiga = self.criar_pendente_ha_60_dias('antiga@fluxar.teste', is_active=False)

        with suppress(CommandError):
            call_command('cleanup_inactive_users')

        self.assertTrue(User.objects.filter(pk=pendente.pk).exists())
        self.assertTrue(User.objects.filter(pk=antiga.pk).exists())

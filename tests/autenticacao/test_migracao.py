"""
Migração dos e-mails e das contas pendentes (AUTH-43, AD-035).

A migração 0010 passa para minúsculas o e-mail das contas cujo e-mail em
minúsculas não coincide com o de outra conta, e deixa como estão as que
colidem (AUTH-44). Também marca como ativas as contas pendentes do modelo
antigo, que tinham email_verified=False e is_active=False.
"""
import importlib

import django.apps
from django.test import TestCase

from api.models import User

SENHA = 'senha-de-teste-123'


def rodar_migracao():
    modulo = importlib.import_module('api.migrations.0010_email_minusculo_e_pendentes')
    modulo.forward(django.apps.apps, None)


def criar_conta(email, **estado):
    # O manager já grava em minúsculas; o update força o e-mail de antes da correção
    usuario = User.objects.create_user(email=f'provisorio-{email.lower()}', password=SENHA, name='Conta')
    User.objects.filter(pk=usuario.pk).update(email=email, **estado)
    return usuario


def email_de(usuario):
    return User.objects.values_list('email', flat=True).get(pk=usuario.pk)


class MigracaoEmailMinusculoTests(TestCase):

    def test_emails_sem_colisao_ficam_em_minusculas_e_o_par_que_colide_fica_intacto(self):
        ana = criar_conta('Ana@x.com')
        bia = criar_conta('bia@X.com')
        caio_maiusculo = criar_conta('Caio@x.com')
        caio_minusculo = criar_conta('caio@x.com')

        rodar_migracao()

        self.assertEqual(email_de(ana), 'ana@x.com')
        self.assertEqual(email_de(bia), 'bia@x.com')
        self.assertEqual(email_de(caio_maiusculo), 'Caio@x.com')
        self.assertEqual(email_de(caio_minusculo), 'caio@x.com')

    def test_grupo_em_que_nenhum_email_esta_em_minusculas_tambem_fica_intacto(self):
        # Sem nenhum já em minúsculas, baixar a caixa de um deles ainda juntaria os dois
        dani_a = criar_conta('Dani@x.com')
        dani_b = criar_conta('DANI@x.com')

        rodar_migracao()

        self.assertEqual(email_de(dani_a), 'Dani@x.com')
        self.assertEqual(email_de(dani_b), 'DANI@x.com')


class MigracaoContasPendentesTests(TestCase):

    def estado(self, usuario):
        return User.objects.values_list('email_verified', 'is_active').get(pk=usuario.pk)

    def test_conta_pendente_do_modelo_antigo_passa_a_ativa(self):
        pendente = criar_conta('pendente@x.com', email_verified=False, is_active=False)

        rodar_migracao()

        self.assertEqual(self.estado(pendente), (False, True))

    def test_conta_verificada_e_desativada_continua_desativada(self):
        desativada = criar_conta('desativada@x.com', email_verified=True, is_active=False)

        rodar_migracao()

        self.assertEqual(self.estado(desativada), (True, False))

    def test_conta_verificada_e_ativa_nao_muda(self):
        ativa = criar_conta('ativa@x.com', email_verified=True, is_active=True)

        rodar_migracao()

        self.assertEqual(self.estado(ativa), (True, True))

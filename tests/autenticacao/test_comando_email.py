"""
Comando check_email_case (AUTH-44).

Lista os grupos de contas cujos e-mails só diferem na caixa, com o ID e o
e-mail mascarado de cada conta (AD-019), e não altera nenhuma conta.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from api.models import User

SENHA = 'senha-de-teste-123'


def criar_conta(email):
    # O manager já grava em minúsculas; o update força o e-mail de antes da correção
    usuario = User.objects.create_user(email=f'provisorio-{email.lower()}', password=SENHA, name='Conta')
    User.objects.filter(pk=usuario.pk).update(email=email)
    return usuario


def rodar_comando():
    saida = StringIO()
    call_command('check_email_case', stdout=saida)
    return saida.getvalue()


class ComandoCheckEmailCaseTests(TestCase):

    def test_lista_o_par_do_caio_com_ids_e_emails_mascarados(self):
        caio_maiusculo = criar_conta('Caio@x.com')
        caio_minusculo = criar_conta('caio@x.com')
        ana = criar_conta('ana@x.com')

        linhas = rodar_comando().strip().splitlines()

        self.assertEqual(len(linhas), 2)
        grupo, total = linhas
        self.assertIn(f'{caio_maiusculo.pk} Ca***@x.com', grupo)
        self.assertIn(f'{caio_minusculo.pk} ca***@x.com', grupo)
        self.assertNotIn(str(ana.pk), grupo)
        self.assertEqual(total, 'Total: 1 grupo(s) com e-mails que só diferem na caixa.')

    def test_saida_nao_traz_nenhum_email_inteiro(self):
        criar_conta('Caio@x.com')
        criar_conta('caio@x.com')
        criar_conta('Bia@y.com')
        criar_conta('BIA@y.com')

        saida = rodar_comando()

        for email in ('Caio@x.com', 'caio@x.com', 'Bia@y.com', 'BIA@y.com', 'bia@y.com'):
            self.assertNotIn(email, saida)
        self.assertIn('Total: 2 grupo(s)', saida)

    def test_nenhuma_conta_e_alterada(self):
        criar_conta('Caio@x.com')
        criar_conta('caio@x.com')
        criar_conta('Ana@x.com')
        antes = list(User.objects.order_by('pk').values_list('pk', 'email', 'updated_at'))

        rodar_comando()

        depois = list(User.objects.order_by('pk').values_list('pk', 'email', 'updated_at'))
        self.assertEqual(depois, antes)

    def test_sem_colisao_informa_total_zero(self):
        criar_conta('Ana@x.com')
        criar_conta('bia@x.com')

        saida = rodar_comando()

        self.assertEqual(saida.strip(), 'Total: 0 grupo(s) com e-mails que só diferem na caixa.')

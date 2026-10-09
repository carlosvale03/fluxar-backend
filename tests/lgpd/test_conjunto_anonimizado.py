"""
Conjunto anonimizado para melhorar o produto (LGPD-36 a LGPD-38).
"""
import csv
import os
import tempfile
from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from accounts.models import Account, CreditCard
from api.models import User
from core import termos
from core.conjuntos import COLUNAS, dados_para_melhoria
from transactions.models import Category, Transaction

CPF = '529.982.247-25'


def criar_pessoa(letra, consentiu):
    usuario = User.objects.create_user(
        email=f'pessoa.{letra}@teste.fluxar', password='senha-de-teste-123', name=f'Pessoa {letra.upper()}',
        cpf='52998224725',
    )
    if consentiu:
        termos.registrar_decisao(usuario, True)
    conta = Account.objects.create(user=usuario, name=f'Nubank Roxinho {letra}', type='CHECKING')
    cartao = CreditCard.objects.create(
        user=usuario, name='Cartão Black Platinum', limit=Decimal('1000'), closing_day=10, due_day=20,
        account=conta,
    )
    categoria = Category.objects.create(user=usuario, name='Mercado 24h', type='EXPENSE')
    transacao = Transaction.objects.create(
        user=usuario, account=conta, category=categoria, type='EXPENSE', status='COMPLETED',
        amount=Decimal('123.45'), date=date(2026, 9, 17),
        description=f'Pix para joao.silva@exemplo.com CPF {CPF} Nubank Roxinho {letra} cartão black platinum 4321',
    )
    return usuario, conta, cartao, transacao


class ConjuntoAnonimizadoTests(TestCase):

    def setUp(self):
        self.a, self.conta_a, self.cartao_a, self.transacao_a = criar_pessoa('a', consentiu=True)
        self.b, self.conta_b, self.cartao_b, self.transacao_b = criar_pessoa('b', consentiu=False)

    # LGPD-36 ---------------------------------------------------------------

    def test_usuario_sem_consentimento_nao_aparece(self):
        linhas = dados_para_melhoria()

        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0]['valor'], '123.45')

    # LGPD-37 ---------------------------------------------------------------

    def test_depois_de_retirar_o_consentimento_o_usuario_sai_do_proximo_conjunto(self):
        self.assertEqual(len(dados_para_melhoria()), 1)

        termos.registrar_decisao(self.a, False)

        self.assertEqual(dados_para_melhoria(), [])

    # LGPD-38 ---------------------------------------------------------------

    def test_nenhuma_linha_traz_identificadores(self):
        termos.registrar_decisao(self.b, True)

        linhas = dados_para_melhoria()

        self.assertEqual(len(linhas), 2)
        proibidos = [
            str(self.a.pk), str(self.b.pk), str(self.conta_a.pk), str(self.conta_b.pk),
            str(self.transacao_a.pk), str(self.transacao_b.pk), str(self.cartao_a.pk),
            'nubank', 'roxinho', 'black', 'platinum', 'joao', 'silva', '@', 'exemplo.com',
            'pessoa', CPF, '52998224725',
        ]
        for linha in linhas:
            self.assertEqual(set(linha), set(COLUNAS))
            texto = ' '.join(str(valor) for valor in linha.values()).lower()
            for proibido in proibidos:
                self.assertNotIn(proibido.lower(), texto)
            self.assertNotRegex(linha['descricao'], r'\d')
            self.assertNotRegex(linha['categoria'], r'\d')
            # O mês e o ano ficam; o dia, não
            self.assertEqual((linha['mes'], linha['ano']), (9, 2026))
            self.assertNotIn('17', texto)
            self.assertEqual(linha['tipo'], 'EXPENSE')
            self.assertEqual(linha['categoria'], 'mercado h')
            self.assertIn('pix para', linha['descricao'])

    def test_comando_grava_o_csv_sem_escrever_dados_na_saida(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, 'conjunto.csv')
            saida = StringIO()

            call_command('exportar_dados_de_melhoria', saida=caminho, stdout=saida)

            with open(caminho, encoding='utf-8') as arquivo:
                linhas = list(csv.DictReader(arquivo))
        self.assertEqual(len(linhas), 1)
        self.assertEqual(tuple(linhas[0]), COLUNAS)
        self.assertEqual(linhas[0]['valor'], '123.45')
        self.assertEqual(saida.getvalue().strip(), 'Linhas gravadas: 1.')

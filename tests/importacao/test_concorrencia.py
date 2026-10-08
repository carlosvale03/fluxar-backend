"""
Importações simultâneas do mesmo arquivo (IMPORT-39).

Usa `TransactionTestCase`, como `tests/saldo/test_concorrencia.py`: com o
`TestCase`, tudo roda numa transação só e as threads, cada uma com a
própria conexão, não veriam os dados do teste nem disputariam as travas de
verdade. Cada thread espera a outra numa `threading.Barrier`, envia o
arquivo pela API e fecha a conexão no fim.
"""
import json
import threading
from decimal import Decimal

from django.db import connection
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from accounts.models import Account
from accounts.saldo import calcular
from transactions.models import Transaction

from .base import MAPEAMENTO, URL_OFX, URL_PLANILHA, arquivo_csv, arquivo_ofx, criar_dados, transacao_ofx

LINHAS = [
    ['Data', 'Descrição', 'Valor'],
    ['10/09/2026', 'Café', '-5,00'],
    ['10/09/2026', 'Café', '-5,00'],
    ['11/09/2026', 'Mercado', '-100,00'],
    ['12/09/2026', 'Salário', '3.000,00'],
]


class ImportacoesSimultaneasTests(TransactionTestCase):

    def setUp(self):
        self.a = criar_dados('A')

    def em_paralelo(self, n, requisicao):
        """Roda `requisicao(cliente)` em `n` threads que partem juntas e devolve as respostas."""
        barreira = threading.Barrier(n, timeout=20)
        respostas, erros = [], []

        def trabalho():
            try:
                cliente = APIClient()
                cliente.force_authenticate(user=self.a.usuario)
                barreira.wait()
                respostas.append(requisicao(cliente))
            except Exception as erro:  # noqa: BLE001 - repassado ao teste abaixo
                erros.append(erro)
            finally:
                connection.close()

        threads = [threading.Thread(target=trabalho) for _ in range(n)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
        self.assertFalse(any(t.is_alive() for t in threads), 'thread presa')
        self.assertEqual(erros, [])
        self.assertEqual(len(respostas), n)
        return respostas

    def assert_cada_linha_uma_vez(self, respostas, linhas):
        self.assertEqual([r.status_code for r in respostas], [200, 200], [r.data for r in respostas])
        self.assertEqual(sorted(r.data['imported'] for r in respostas), [0, linhas])
        self.assertEqual(sorted(r.data['ignored'] for r in respostas), [0, linhas])
        conta = Account.objects.get(pk=self.a.conta.pk)
        self.assertEqual(conta.balance, calcular(conta))
        return conta.balance

    def test_mesma_planilha_ao_mesmo_tempo_grava_cada_linha_uma_vez(self):
        """IMPORT-39 e IMPORT-38: as duas compras iguais entram duas vezes, não quatro."""
        def importar(cliente):
            return cliente.post(URL_PLANILHA, {
                'file': arquivo_csv(LINHAS), 'mapping': json.dumps(MAPEAMENTO),
                'import_type': 'INCOME_EXPENSE', 'account_id': str(self.a.conta.id),
            }, format='multipart')

        respostas = self.em_paralelo(2, importar)

        saldo = self.assert_cada_linha_uma_vez(respostas, 4)
        self.assertEqual(Transaction.objects.filter(account=self.a.conta).count(), 4)
        self.assertEqual(Transaction.objects.filter(account=self.a.conta, description='Café').count(), 2)
        self.assertEqual(saldo, Decimal('3890.00'))

    def test_mesmo_ofx_ao_mesmo_tempo_grava_cada_fitid_uma_vez(self):
        """IMPORT-39 e IMPORT-34: cada FITID gravado uma única vez."""
        def importar(cliente):
            arquivo = arquivo_ofx(
                transacao_ofx('F1', '20260910', '-45.00', memo='Padaria'),
                transacao_ofx('F2', '20260910', '-45.00', memo='Padaria'),
                transacao_ofx('F3', '20260911', '200.00', memo='Pix'),
            )
            return cliente.post(URL_OFX, {'file': arquivo, 'account_id': str(self.a.conta.id)}, format='multipart')

        respostas = self.em_paralelo(2, importar)

        saldo = self.assert_cada_linha_uma_vez(respostas, 3)
        self.assertEqual(
            sorted(Transaction.objects.filter(account=self.a.conta).values_list('fitid', flat=True)),
            ['F1', 'F2', 'F3'],
        )
        self.assertEqual(saldo, Decimal('1110.00'))

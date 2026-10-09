"""
Exportação em PDF com transação sem conta (T9, REL-25).
"""
import re
from datetime import date
from decimal import Decimal

from transactions.models import Transaction

from tests.isolamento.test_exportacao_nomes import texto_do_pdf

from .base import RelatoriosTestCase

URL = '/api/export/transactions/pdf/'


class PdfSemContaTests(RelatoriosTestCase):

    def setUp(self):
        super().setUp()
        Transaction.objects.create(
            user=self.a.usuario, type='EXPENSE', status='COMPLETED', description='Sem conta',
            amount=Decimal('12.34'), date=date(2026, 3, 5), account=None, category=self.a.despesa,
        )
        self.lancar('INCOME', '56.78', date(2026, 3, 6), category=self.a.receita)

    def exportar(self):
        resp = self.client.get(URL, {'startDate': '2026-03-01', 'endDate': '2026-03-31'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        return resp.content

    def test_gera_o_pdf_com_a_transacao_sem_conta(self):
        conteudo = self.exportar()

        self.assertTrue(conteudo.startswith(b'%PDF'))
        texto = texto_do_pdf(conteudo)
        self.assertIn('(R$ 12.34) Tj', texto)
        self.assertIn('(R$ 56.78) Tj', texto)

    def test_a_linha_sem_conta_tem_a_conta_em_branco(self):
        texto = texto_do_pdf(self.exportar())

        # Cada texto desenhado: `BT 1 0 0 1 x y Tm (texto) Tj T* ET`; o texto
        # vazio não tem o `(...) Tj`
        linhas = {}
        for x, y, conteudo in re.findall(r'BT 1 0 0 1 (\S+) (\S+) Tm (?:\((.*?)\) Tj)? T\* ET', texto):
            linhas.setdefault(y, {})[x] = conteudo
        sem_conta = next(linha for linha in linhas.values() if linha.get('50') == '05/03/2026')
        com_conta = next(linha for linha in linhas.values() if linha.get('50') == '06/03/2026')

        # Colunas: data (50), tipo (130), conta (180), categoria (300) e valor (450)
        self.assertEqual(sem_conta, {
            '50': '05/03/2026', '130': 'Despesa', '180': '', '300': 'Mercado A', '450': 'R$ 12.34',
        })
        self.assertEqual(com_conta['180'], 'Corrente A')

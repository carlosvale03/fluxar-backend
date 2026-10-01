"""
Séries recorrentes (SALDO-20 a SALDO-22, AD-002).

A primeira ocorrência segue o status enviado e as geradas nascem pendentes,
inclusive as receitas. Alterar ou excluir a série mexe só nas pendentes; as
efetivadas ficam no histórico como estão.
"""
from decimal import Decimal

from transactions.models import RecurringTransaction, Transaction
from tests.saldo.base import SaldoTestCase, URL_TRANSACOES


class SerieTestCase(SaldoTestCase):

    def criar_serie(self, **extra):
        """Cria pela API um salário mensal de R$ 5.000,00 na conta corrente de A."""
        corpo = {
            'type': 'INCOME', 'status': 'COMPLETED', 'description': 'Salário',
            'amount': '5000.00', 'date': '2026-09-05',
            'account': str(self.a.conta.id), 'category': str(self.a.receita.id),
            'is_recurring': True, 'frequency': 'MONTHLY',
        }
        corpo.update(extra)
        resp = self.cliente.post(URL_TRANSACOES, corpo, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        primeira = Transaction.objects.get(pk=resp.data['id'])
        return primeira.recurring_source, primeira

    def ocorrencias(self, serie):
        return list(Transaction.objects.filter(recurring_source=serie).order_by('date'))


class CriacaoDeSerieTests(SerieTestCase):

    def test_receita_com_a_primeira_efetivada_soma_so_a_primeira(self):
        serie, primeira = self.criar_serie()

        ocorrencias = self.ocorrencias(serie)
        self.assertEqual(len(ocorrencias), 12)
        self.assertEqual(ocorrencias[0].pk, primeira.pk)
        self.assertEqual(primeira.status, 'COMPLETED')
        self.assertEqual([t.status for t in ocorrencias[1:]], ['PENDING'] * 11)
        self.assertEqual(self.saldo(self.a.conta), Decimal('6000.00'))

    def test_com_a_primeira_pendente_o_saldo_nao_muda(self):
        serie, _ = self.criar_serie(status='PENDING')

        self.assertEqual([t.status for t in self.ocorrencias(serie)], ['PENDING'] * 12)
        self.assertEqual(self.saldo(self.a.conta), Decimal('1000.00'))

    def test_serie_com_inicio_no_passado_gera_pendentes_mesmo_com_data_passada(self):
        serie, _ = self.criar_serie(date='2025-01-05')

        ocorrencias = self.ocorrencias(serie)
        self.assertEqual(ocorrencias[-1].date.isoformat(), '2025-12-05')
        self.assertEqual([t.status for t in ocorrencias[1:]], ['PENDING'] * 11)
        self.assertEqual(self.saldo(self.a.conta), Decimal('6000.00'))

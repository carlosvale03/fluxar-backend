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


URL_LOTE = f'{URL_TRANSACOES}bulk-update/'
CONTA_NAO_ENCONTRADA = 'Conta não encontrada.'
CATEGORIA_NAO_ENCONTRADA = 'Categoria não encontrada.'
SERIE_NAO_ENCONTRADA = 'Série não encontrada.'
TIPO_NAO_ALTERAVEL = 'O tipo só pode ser trocado entre receita e despesa.'
SERIE_ENCERRADA = 'Esta série foi encerrada e não pode ser alterada.'


class AlterarTodasTests(SerieTestCase):
    """Alterar todas as ocorrências muda só as pendentes e o modelo da série (SALDO-21)."""

    def setUp(self):
        super().setUp()
        self.serie, self.primeira = self.criar_serie()
        # O usuário efetiva a segunda ocorrência
        self.segunda = self.ocorrencias(self.serie)[1]
        resp = self.cliente.patch(f'{URL_TRANSACOES}{self.segunda.id}/', {'status': 'COMPLETED'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.saldo(self.a.conta), Decimal('11000.00'))

    def alterar(self, **corpo):
        return self.cliente.patch(URL_LOTE, {'recurring_source': str(self.serie.id), **corpo}, format='json')

    def estado(self):
        return (
            sorted(Transaction.objects.values_list(
                'id', 'type', 'status', 'account_id', 'category_id', 'amount', 'description',
            )),
            sorted(RecurringTransaction.objects.values_list(
                'id', 'type', 'account_id', 'category_id', 'amount', 'description', 'is_active',
            )),
            self.saldo(self.a.conta), self.saldo(self.a.poupanca),
        )

    def test_valor_e_conta_mudam_so_as_pendentes(self):
        resp = self.alterar(amount='5500.00', account=str(self.a.poupanca.id))
        self.assertEqual(resp.status_code, 200, resp.data)

        efetivadas, pendentes = [], []
        for t in self.ocorrencias(self.serie):
            (efetivadas if t.status == 'COMPLETED' else pendentes).append((t.amount, t.account_id))
        self.assertEqual(efetivadas, [(Decimal('5000.00'), self.a.conta.id)] * 2)
        self.assertEqual(pendentes, [(Decimal('5500.00'), self.a.poupanca.id)] * 10)

        serie = RecurringTransaction.objects.get(pk=self.serie.pk)
        self.assertEqual((serie.amount, serie.account_id), (Decimal('5500.00'), self.a.poupanca.id))
        # Pendentes não contam: os saldos seguem SALDO-01
        self.assertEqual(self.saldo(self.a.conta), Decimal('11000.00'))
        self.assertEqual(self.saldo(self.a.poupanca), Decimal('0.00'))

        # Efetivar uma pendente alterada soma o valor novo na conta nova
        terceira = self.ocorrencias(self.serie)[2]
        resp = self.cliente.patch(f'{URL_TRANSACOES}{terceira.id}/', {'status': 'COMPLETED'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.saldo(self.a.poupanca), Decimal('5500.00'))
        self.assertEqual(self.saldo(self.a.conta), Decimal('11000.00'))

    def test_descricao_categoria_e_tipo_mudam_so_as_pendentes(self):
        resp = self.alterar(description='Aluguel', category=str(self.a.despesa.id), type='EXPENSE')
        self.assertEqual(resp.status_code, 200, resp.data)

        campos = lambda t: (t.description, t.category_id, t.type)
        ocorrencias = self.ocorrencias(self.serie)
        self.assertEqual([campos(t) for t in ocorrencias[:2]], [('Salário', self.a.receita.id, 'INCOME')] * 2)
        self.assertEqual([campos(t) for t in ocorrencias[2:]], [('Aluguel', self.a.despesa.id, 'EXPENSE')] * 10)
        self.assertEqual(campos(RecurringTransaction.objects.get(pk=self.serie.pk)), ('Aluguel', self.a.despesa.id, 'EXPENSE'))
        self.assertEqual(self.saldo(self.a.conta), Decimal('11000.00'))

    def assert_recusa(self, corpo, campo, mensagem):
        antes = self.estado()
        resp = self.alterar(**corpo)
        self.assertEqual(resp.status_code, 400, resp.data)
        if campo == 'detail':
            self.assertEqual(resp.data, {'detail': mensagem})
        else:
            self.assertEqual(resp.data[campo], [mensagem])
        self.assertEqual(self.estado(), antes)

    def test_conta_excluida_recusada(self):
        excluida = self.a.poupanca
        excluida.__class__.objects.filter(pk=excluida.pk).update(is_active=False)
        self.assert_recusa({'account': str(excluida.id), 'amount': '5500.00'}, 'account', CONTA_NAO_ENCONTRADA)

    def test_conta_de_outro_usuario_recusada(self):
        self.assert_recusa({'account': str(self.b.conta.id), 'amount': '5500.00'}, 'account', CONTA_NAO_ENCONTRADA)

    def test_categoria_de_outro_usuario_recusada(self):
        self.assert_recusa({'category': str(self.b.receita.id), 'amount': '5500.00'}, 'category', CATEGORIA_NAO_ENCONTRADA)

    def test_tipo_especial_recusado(self):
        for tipo in ('TRANSFER_IN', 'TRANSFER_OUT', 'CREDIT_CARD', 'INVOICE_PAYMENT'):
            with self.subTest(tipo=tipo):
                self.assert_recusa({'type': tipo, 'amount': '5500.00'}, 'type', TIPO_NAO_ALTERAVEL)

    def test_valor_invalido_recusado(self):
        for valor in ('0', '-10.00', '100.123'):
            with self.subTest(valor=valor):
                antes = self.estado()
                resp = self.alterar(amount=valor, description='Alterada')
                self.assertEqual(resp.status_code, 400, resp.data)
                self.assertEqual(list(resp.data), ['amount'])
                if valor != '100.123':
                    self.assertEqual(resp.data['amount'], ['O valor deve ser maior que zero.'])
                self.assertEqual(self.estado(), antes)

    def test_serie_de_outro_usuario_recusada(self):
        serie_b = RecurringTransaction.objects.create(
            user=self.b.usuario, description='Salário B', amount=Decimal('100.00'), type='INCOME',
            account=self.b.conta, frequency='MONTHLY', start_date=self.primeira.date,
        )
        self.lancar(self.b.conta, 'INCOME', '100.00', status='PENDING', recurring_source=serie_b)
        antes = self.estado()
        resp = self.cliente.patch(URL_LOTE, {'recurring_source': str(serie_b.id), 'amount': '1.00'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data['recurring_source'], [SERIE_NAO_ENCONTRADA])
        self.assertEqual(self.estado(), antes)

    def test_serie_encerrada_recusada(self):
        RecurringTransaction.objects.filter(pk=self.serie.pk).update(is_active=False)
        self.assert_recusa({'amount': '5500.00'}, 'detail', SERIE_ENCERRADA)

    def test_serie_de_tipo_especial_nao_vira_receita_ou_despesa(self):
        # Série antiga de compra no cartão, gravada antes da restrição de tipos
        RecurringTransaction.objects.filter(pk=self.serie.pk).update(type='CREDIT_CARD')
        Transaction.objects.filter(recurring_source=self.serie, status='PENDING').update(type='CREDIT_CARD')
        self.assert_recusa({'type': 'EXPENSE'}, 'type', TIPO_NAO_ALTERAVEL)

"""
Gasto relacionado na criação: `POST /api/transactions/` e
`POST /api/transactions/credit-card-expense/` com `principal` (VINCULO-01,
VINCULO-11, VINCULO-12, VINCULO-13, VINCULO-18 e VINCULO-20).
"""
from django.core.cache import cache

from core import travas
from tests.permissoes.base import fechar, liberacao_de_testes
from transactions.models import RecurringTransaction, Transaction
from transactions.vinculos import vincular

from .base import VinculosTestCase, despesa

URL_TRANSACOES = '/api/transactions/'
URL_COMPRA = '/api/transactions/credit-card-expense/'
BLOQUEADO = {
    'detail': 'Este recurso não está disponível no seu plano.', 'code': 'plan_locked', 'feature': 'vinculos',
}


class GastoRelacionadoTestCase(VinculosTestCase):

    def setUp(self):
        super().setUp()
        cache.clear()
        travas.invalidar()
        self.addCleanup(travas.invalidar)
        self.cinema = despesa(self.a, 'Cinema', '50.00', categoria=self.a.cinema)

    def corpo_despesa(self, principal, **extra):
        corpo = {
            'type': 'EXPENSE', 'status': 'COMPLETED', 'description': 'Transporte', 'amount': '45.00',
            'date': '2026-09-12', 'account': str(self.a.conta.pk), 'category': str(self.a.transporte.pk),
            'principal': str(principal),
        }
        corpo.update(extra)
        return corpo

    def corpo_compra(self, principal, **extra):
        corpo = {
            'credit_card': str(self.a.cartao.pk), 'amount': '120.00', 'date': '2026-09-12',
            'description': 'Jantar', 'category': str(self.a.alimentacao.pk), 'installments': 1,
            'principal': str(principal),
        }
        corpo.update(extra)
        return corpo

    def total(self):
        return Transaction.objects.filter(user=self.a.usuario).count()


class CriacaoTests(GastoRelacionadoTestCase):

    def test_lancar_o_transporte_com_o_cinema_como_principal_cria_a_dependente(self):
        resposta = self.client.post(URL_TRANSACOES, self.corpo_despesa(self.cinema.pk), format='json')

        self.assertEqual(resposta.status_code, 201, resposta.data)
        transporte = Transaction.objects.get(pk=resposta.data['id'])
        self.assertEqual(transporte.principal_id, self.cinema.pk)
        self.assertEqual(str(resposta.data['principal']), str(self.cinema.pk))

    def test_compra_parcelada_com_principal_liga_a_raiz_da_compra(self):
        resposta = self.client.post(URL_COMPRA, self.corpo_compra(self.cinema.pk, installments=3), format='json')

        self.assertEqual(resposta.status_code, 201, resposta.data)
        parcelas = Transaction.objects.filter(user=self.a.usuario, type='CREDIT_CARD').order_by('installment_number')
        self.assertEqual(parcelas.count(), 3)
        self.assertEqual(parcelas[0].principal_id, self.cinema.pk)
        self.assertEqual([p.principal_id for p in parcelas[1:]], [None, None])
        # Cada parcela mostra a principal da compra
        self.assertEqual([str(item['principal']) for item in resposta.data], [str(self.cinema.pk)] * 3)

    def test_ocorrencia_recorrente_lancada_com_principal_liga_so_ela(self):
        resposta = self.client.post(URL_TRANSACOES, self.corpo_despesa(
            self.cinema.pk, is_recurring=True, frequency='MONTHLY',
        ), format='json')

        self.assertEqual(resposta.status_code, 201, resposta.data)
        serie = RecurringTransaction.objects.get(user=self.a.usuario)
        ligadas = Transaction.objects.filter(recurring_source=serie, principal__isnull=False)
        self.assertEqual([str(pk) for pk in ligadas.values_list('pk', flat=True)], [str(resposta.data['id'])])


class RecusaTests(GastoRelacionadoTestCase):
    """VINCULO-11 e VINCULO-18: a recusa não deixa nada gravado."""

    def test_principal_que_ja_e_dependente_recebe_400_e_nada_e_criado(self):
        transporte = despesa(self.a, 'Transporte', '45.00')
        vincular(transporte, self.cinema)
        antes = self.total()

        resposta = self.client.post(URL_TRANSACOES, self.corpo_despesa(transporte.pk, description='Pipoca'), format='json')
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data['detail'], 'Uma transação dependente não pode ser principal.')
        self.assertEqual(self.total(), antes)

        resposta = self.client.post(URL_COMPRA, self.corpo_compra(transporte.pk, installments=3), format='json')
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data['detail'], 'Uma transação dependente não pode ser principal.')
        self.assertEqual(self.total(), antes)
        self.a.cartao.refresh_from_db()
        self.assertFalse(Transaction.objects.filter(type='CREDIT_CARD').exists())

    def test_receita_com_principal_recebe_400_e_nada_e_criado(self):
        antes = self.total()
        resposta = self.client.post(URL_TRANSACOES, self.corpo_despesa(
            self.cinema.pk, type='INCOME', category=None, description='Reembolso',
        ), format='json')
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data['detail'], 'Só despesas e compras no cartão podem ser vinculadas.')
        self.assertEqual(self.total(), antes)

    def test_principal_de_outro_usuario_recebe_400_no_campo(self):
        alheia = despesa(self.b, 'Cinema B', '50.00')
        antes = self.total()
        for url, corpo in (
            (URL_TRANSACOES, self.corpo_despesa(alheia.pk)),
            (URL_COMPRA, self.corpo_compra(alheia.pk)),
        ):
            with self.subTest(url=url):
                resposta = self.client.post(url, corpo, format='json')
                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.data, {'principal': ['Transação não encontrada.']})
        self.assertEqual(self.total(), antes)


class TravaTests(GastoRelacionadoTestCase):
    """VINCULO-20."""

    def test_com_o_recurso_travado_enviar_principal_recebe_403(self):
        liberacao_de_testes(False)
        fechar('vinculos')
        antes = self.total()

        resposta = self.client.post(URL_TRANSACOES, self.corpo_despesa(self.cinema.pk), format='json')
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(resposta.data, BLOQUEADO)
        resposta = self.client.post(URL_COMPRA, self.corpo_compra(self.cinema.pk), format='json')
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(resposta.data, BLOQUEADO)
        self.assertEqual(self.total(), antes)

        # Sem `principal`, o lançamento segue liberado
        corpo = self.corpo_despesa(self.cinema.pk)
        corpo.pop('principal')
        resposta = self.client.post(URL_TRANSACOES, corpo, format='json')
        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertIsNone(resposta.data['principal'])

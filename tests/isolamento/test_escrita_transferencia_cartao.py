from decimal import Decimal

from accounts.models import Account, CreditCardInvoice
from transactions.models import Transaction
from tests.isolamento.base import DoisUsuariosTestCase

URL_TRANSFERENCIA = '/api/transactions/transfer/'
URL_COMPRA = '/api/transactions/credit-card-expense/'


class EscritaTransferenciaECompraTests(DoisUsuariosTestCase):

    def setUp(self):
        self.cliente = self.como(self.a.usuario)

    def transferencia(self, **extra):
        dados = {
            'account_from': str(self.a.conta.id), 'account_to': str(self.a.cofrinho.id),
            'amount': '100.00', 'date': '2026-09-15', 'description': 'Guardar',
        }
        dados.update(extra)
        return dados

    def compra(self, **extra):
        dados = {
            'credit_card': str(self.a.cartao.id), 'amount': '90.00', 'date': '2026-09-15',
            'description': 'Loja', 'category': str(self.a.categoria.id),
            'installments': 1, 'tags': [str(self.a.tag.id)],
        }
        dados.update(extra)
        return dados

    def assert_recusa(self, url, payload, campo, valor_b, valor_inexistente, mensagem):
        total_transacoes = Transaction.objects.count()
        total_faturas = CreditCardInvoice.objects.count()

        resp_alheio = self.cliente.post(url, payload(**{campo: valor_b}), format='json')
        resp_inexistente = self.cliente.post(url, payload(**{campo: valor_inexistente}), format='json')

        self.assert_mesma_recusa(resp_alheio, resp_inexistente, campo, mensagem)
        self.assertEqual(Transaction.objects.count(), total_transacoes)
        self.assertEqual(CreditCardInvoice.objects.count(), total_faturas)
        self.assertEqual(Account.objects.get(pk=self.b.conta.pk).balance, Decimal('1000.00'))
        self.assertEqual(CreditCardInvoice.objects.get(pk=self.b.fatura.pk).total_amount, Decimal('0.00'))

    # --- Transferência ---

    def test_transferencia_com_origem_de_b_e_recusada(self):
        self.assert_recusa(
            URL_TRANSFERENCIA, self.transferencia, 'account_from',
            str(self.b.conta.id), self.ID_INEXISTENTE, 'Conta não encontrada.',
        )

    def test_transferencia_com_origem_propria_e_destino_de_b_e_recusada(self):
        self.assert_recusa(
            URL_TRANSFERENCIA, self.transferencia, 'account_to',
            str(self.b.conta.id), self.ID_INEXISTENTE, 'Conta não encontrada.',
        )

    def test_transferencia_com_contas_de_a_continua_funcionando(self):
        resp = self.cliente.post(URL_TRANSFERENCIA, self.transferencia(), format='json')

        self.assertEqual(resp.status_code, 201, resp.data)
        pernas = Transaction.objects.filter(user=self.a.usuario, transfer_id__isnull=False)
        self.assertEqual(
            {(t.type, t.account_id) for t in pernas},
            {('TRANSFER_OUT', self.a.conta.id), ('TRANSFER_IN', self.a.cofrinho.id)},
        )
        self.assertEqual(len({t.transfer_id for t in pernas}), 1)

    # --- Compra no cartão ---

    def test_compra_com_cartao_de_b_e_recusada(self):
        self.assert_recusa(
            URL_COMPRA, self.compra, 'credit_card',
            str(self.b.cartao.id), self.ID_INEXISTENTE, 'Cartão não encontrado.',
        )

    def test_compra_com_categoria_de_b_e_recusada(self):
        self.assert_recusa(
            URL_COMPRA, self.compra, 'category',
            str(self.b.categoria.id), self.ID_INEXISTENTE, 'Categoria não encontrada.',
        )

    def test_compra_com_categoria_modelo_e_recusada(self):
        self.assert_recusa(
            URL_COMPRA, self.compra, 'category',
            str(self.categoria_modelo.id), self.ID_INEXISTENTE, 'Categoria não encontrada.',
        )

    def test_compra_com_tag_de_b_e_recusada(self):
        self.assert_recusa(
            URL_COMPRA, self.compra, 'tags',
            [str(self.a.tag.id), str(self.b.tag.id)], [self.ID_INEXISTENTE], 'Tag não encontrada.',
        )

    def test_compra_com_objetos_de_a_continua_funcionando(self):
        resp = self.cliente.post(URL_COMPRA, self.compra(), format='json')

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(len(resp.data), 1)
        t = Transaction.objects.get(pk=resp.data[0]['id'])
        self.assertEqual(t.user, self.a.usuario)
        self.assertEqual(t.type, 'CREDIT_CARD')
        self.assertEqual(t.credit_card, self.a.cartao)
        self.assertEqual(t.category, self.a.categoria)
        self.assertEqual(list(t.tags.all()), [self.a.tag])
        self.assertEqual(t.invoice.card, self.a.cartao)

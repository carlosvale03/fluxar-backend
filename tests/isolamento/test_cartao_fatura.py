from datetime import date
from decimal import Decimal

from accounts.models import Account, CreditCard, CreditCardInvoice
from transactions.models import Transaction
from tests.isolamento.base import DoisUsuariosTestCase

URL_CARTOES = '/api/credit-cards/'


class EscritaContaDoCartaoTests(DoisUsuariosTestCase):

    def setUp(self):
        self.cliente = self.como(self.a.usuario)

    def novo_cartao(self, conta):
        return {'name': 'Cartão Novo', 'limit': '1500.00', 'closing_day': 5, 'due_day': 15, 'account_id': conta}

    def test_criacao_de_cartao_com_conta_de_b_e_recusada(self):
        total_cartoes = CreditCard.objects.count()
        resp_inexistente = self.cliente.post(URL_CARTOES, self.novo_cartao(self.ID_INEXISTENTE), format='json')
        resp = self.cliente.post(URL_CARTOES, self.novo_cartao(str(self.b.conta.id)), format='json')

        self.assert_mesma_recusa(resp, resp_inexistente, 'account_id', 'Conta não encontrada.')
        self.assertEqual(CreditCard.objects.count(), total_cartoes)
        self.assertEqual(list(CreditCard.objects.filter(account=self.b.conta)), [self.b.cartao])

    def test_edicao_de_cartao_com_conta_de_b_e_recusada(self):
        url = f'{URL_CARTOES}{self.a.cartao.id}/'
        resp_inexistente = self.cliente.patch(url, {'account_id': self.ID_INEXISTENTE}, format='json')
        resp = self.cliente.patch(url, {'account_id': str(self.b.conta.id)}, format='json')

        self.assert_mesma_recusa(resp, resp_inexistente, 'account_id', 'Conta não encontrada.')
        self.assertEqual(CreditCard.objects.get(pk=self.a.cartao.pk).account, self.a.conta)

    def test_cartao_com_conta_de_a_continua_funcionando(self):
        resp = self.cliente.post(URL_CARTOES, self.novo_cartao(str(self.a.conta.id)), format='json')

        self.assertEqual(resp.status_code, 201, resp.data)
        cartao = CreditCard.objects.get(pk=resp.data['id'])
        self.assertEqual((cartao.user, cartao.account), (self.a.usuario, self.a.conta))

        resp_edicao = self.cliente.patch(
            f'{URL_CARTOES}{cartao.id}/', {'account_id': str(self.a.cofrinho.id)}, format='json',
        )

        self.assertEqual(resp_edicao.status_code, 200, resp_edicao.data)
        self.assertEqual(CreditCard.objects.get(pk=cartao.pk).account, self.a.cofrinho)
        self.assertEqual(resp_edicao.data['account']['id'], str(self.a.cofrinho.id))


class LeituraContaDoCartaoTests(DoisUsuariosTestCase):

    def test_cartao_de_a_ligado_a_conta_de_b_mostra_account_nulo(self):
        # Ligação cruzada gravada à força, como antes da correção
        CreditCard.objects.filter(pk=self.a.cartao.pk).update(account=self.b.conta)
        cliente = self.como(self.a.usuario)

        detalhe = cliente.get(f'{URL_CARTOES}{self.a.cartao.id}/')
        lista = cliente.get(URL_CARTOES)

        self.assertEqual(detalhe.status_code, 200)
        self.assertIsNone(detalhe.data['account'])
        self.assertIsNone(detalhe.data['account_id'])
        self.assertNotIn('Conta B', str(detalhe.data))

        self.assertEqual(lista.status_code, 200)
        itens = lista.data['results'] if isinstance(lista.data, dict) else lista.data
        cartao_na_lista = next(item for item in itens if item['id'] == str(self.a.cartao.id))
        self.assertIsNone(cartao_na_lista['account'])
        self.assertIsNone(cartao_na_lista['account_id'])


class PagamentoDeFaturaTests(DoisUsuariosTestCase):

    def setUp(self):
        self.cliente = self.como(self.a.usuario)
        self.compra = Transaction.objects.create(
            user=self.a.usuario, type='CREDIT_CARD', status='PENDING', description='Loja',
            amount=Decimal('100.00'), date=date(2026, 9, 5), account=self.a.conta,
            credit_card=self.a.cartao, invoice=self.a.fatura,
        )
        self.url = f'/api/invoices/{self.a.fatura.id}/pay/'

    def pagamento(self, conta):
        return {'amount': '100.00', 'date': '2026-09-20', 'account_id': conta}

    def test_pagamento_com_conta_de_b_e_recusado(self):
        saldo_b = Account.objects.get(pk=self.b.conta.pk).balance
        resp_inexistente = self.cliente.post(self.url, self.pagamento(self.ID_INEXISTENTE), format='json')
        resp = self.cliente.post(self.url, self.pagamento(str(self.b.conta.id)), format='json')

        self.assert_mesma_recusa(resp, resp_inexistente, 'account_id', 'Conta não encontrada.')
        self.compra.refresh_from_db()
        self.assertEqual((self.compra.status, self.compra.account), ('PENDING', self.a.conta))
        self.assertEqual(CreditCardInvoice.objects.get(pk=self.a.fatura.pk).status, 'OPEN')
        self.assertFalse(Transaction.objects.filter(account=self.b.conta).exists())
        self.assertEqual(Account.objects.get(pk=self.b.conta.pk).balance, saldo_b)

    def test_pagamento_com_conta_de_a_continua_funcionando(self):
        resp = self.cliente.post(self.url, self.pagamento(str(self.a.cofrinho.id)), format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.compra.refresh_from_db()
        self.assertEqual((self.compra.status, self.compra.account), ('COMPLETED', self.a.cofrinho))
        self.assertEqual(CreditCardInvoice.objects.get(pk=self.a.fatura.pk).status, 'PAID')

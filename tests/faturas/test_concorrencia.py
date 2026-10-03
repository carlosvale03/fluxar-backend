"""
Pedidos simultâneos com a mesma chave (FATURA-31, FATURA-32).

Usa `TransactionTestCase`, como `tests/saldo/test_concorrencia.py`: cada
thread tem a própria conexão, espera as outras numa `threading.Barrier` e
faz o pedido pela API, para disputar as travas e a restrição única de
verdade. Os dados de cada teste são criados no próprio `setUp`.
"""
import threading
import uuid
from datetime import date
from decimal import Decimal
from unittest import mock

from django.db import connection
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from accounts.faturas import obter_fatura
from accounts.models import Account, CreditCard, CreditCardInvoice, PagamentoDeFatura
from transactions.models import Transaction
from tests.faturas.base import criar_usuario

CHAVE_COM_OUTROS_DADOS = 'Este identificador de pagamento já foi usado com outros dados.'


class PagamentosSimultaneosTests(TransactionTestCase):

    def setUp(self):
        self.a = criar_usuario('A')
        # A trava da fatura alcança também o cartão (select_related): faturas
        # do mesmo cartão já se esperam, por isso a segunda é de outro cartão
        cartoes = [
            CreditCard.objects.create(
                user=self.a.usuario, name=nome, limit=Decimal('5000.00'),
                closing_day=10, due_day=20, account=self.a.conta,
            )
            for nome in ('Cartão', 'Outro cartão')
        ]
        self.setembro = obter_fatura(cartoes[0], 9, 2026)
        self.outra = obter_fatura(cartoes[1], 9, 2026)
        for fatura in (self.setembro, self.outra):
            Transaction.objects.create(
                user=self.a.usuario, type='CREDIT_CARD', status='PENDING', account=self.a.conta,
                credit_card=fatura.card, invoice=fatura, description='Loja',
                amount=Decimal('400.00'), date=fatura.due_date, purchase_date=date(2026, 9, 1),
            )
        self.chave = str(uuid.uuid4())

    def em_paralelo(self, requisicoes):
        """Roda cada `requisicao(cliente)` numa thread; todas partem juntas."""
        barreira = threading.Barrier(len(requisicoes), timeout=20)
        respostas, erros = [], []

        def trabalho(requisicao):
            try:
                cliente = APIClient()
                cliente.force_authenticate(user=self.a.usuario)
                barreira.wait()
                respostas.append(requisicao(cliente))
            except Exception as erro:  # noqa: BLE001 - repassado ao teste abaixo
                erros.append(erro)
            finally:
                connection.close()

        threads = [threading.Thread(target=trabalho, args=(r,)) for r in requisicoes]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
        self.assertFalse(any(t.is_alive() for t in threads), 'thread presa')
        self.assertEqual(erros, [])
        return respostas

    def pedido(self, fatura):
        corpo = {
            'account_id': str(self.a.conta.id), 'amount': '400.00', 'date': '2026-09-15',
            'idempotency_key': self.chave,
        }
        return lambda cliente: cliente.post(f'/api/invoices/{fatura.id}/pay/', corpo, format='json')

    def saldo(self):
        return Account.objects.get(pk=self.a.conta.pk).balance

    def test_dois_pedidos_simultaneos_com_a_mesma_chave_pagam_uma_vez(self):
        respostas = self.em_paralelo([self.pedido(self.setembro)] * 2)

        self.assertEqual([r.status_code for r in respostas], [200, 200])
        self.assertEqual(respostas[0].data, respostas[1].data)
        self.assertEqual(PagamentoDeFatura.objects.count(), 1)
        self.assertEqual(respostas[0].data['payment']['id'], str(PagamentoDeFatura.objects.get().id))
        self.assertEqual(self.saldo(), Decimal('600.00'))

    def test_mesma_chave_em_duas_faturas_ao_mesmo_tempo_paga_so_uma(self):
        """
        As duas faturas, de cartões diferentes, têm travas diferentes: os dois pedidos procuram a
        chave ao mesmo tempo, não a encontram e só então gravam o pagamento.
        A segunda gravação esbarra na restrição única `(user, chave)`.
        """
        criar = PagamentoDeFatura.objects.create
        juntos = threading.Barrier(2, timeout=20)

        def criar_depois_das_duas_buscas(**campos):
            juntos.wait()
            return criar(**campos)

        with mock.patch.object(PagamentoDeFatura.objects, 'create', side_effect=criar_depois_das_duas_buscas):
            respostas = self.em_paralelo([self.pedido(self.setembro), self.pedido(self.outra)])

        self.assertEqual(sorted(r.status_code for r in respostas), [200, 400])
        recusa = next(r for r in respostas if r.status_code == 400)
        self.assertEqual(recusa.data, {'detail': CHAVE_COM_OUTROS_DADOS})
        pagamento = PagamentoDeFatura.objects.get()
        status = dict(CreditCardInvoice.objects.values_list('id', 'status'))
        paga, outra = (
            (self.setembro, self.outra) if pagamento.fatura_id == self.setembro.id
            else (self.outra, self.setembro)
        )
        self.assertEqual((status[paga.id], status[outra.id]), ('PAID', 'OPEN'))
        self.assertEqual(Transaction.objects.get(invoice=outra).status, 'PENDING')
        self.assertEqual(self.saldo(), Decimal('600.00'))

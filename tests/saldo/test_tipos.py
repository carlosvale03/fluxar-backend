"""
Tipos do endpoint genérico de transações (SALDO-18, SALDO-19, SALDO-46).

O endpoint só cria receita e despesa, só troca o tipo entre essas duas, e uma
compra no cartão só é efetivada pelo pagamento da fatura. Editar uma compra
no cartão ou uma perna de transferência sem mudar o tipo continua valendo.
"""
import uuid
from decimal import Decimal

from transactions.models import Transaction
from tests.saldo.base import SaldoTestCase, URL_TRANSACOES

ESPECIAIS = ('TRANSFER_IN', 'TRANSFER_OUT', 'CREDIT_CARD', 'INVOICE_PAYMENT')
MENSAGEM_COMPRA_NO_CARTAO = 'Compras no cartão são efetivadas pelo pagamento da fatura.'


class CriacaoPorTipoTests(SaldoTestCase):

    def assert_criacao_recusada(self, tipo):
        total = Transaction.objects.count()
        resp = self.cliente.post(URL_TRANSACOES, self.payload(
            type=tipo, credit_card=str(self.a.cartao.id),
        ), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('type', resp.data)
        self.assertEqual(Transaction.objects.count(), total)
        self.assertEqual(self.saldo(self.a.conta), Decimal('1000.00'))

    def test_criacao_de_transfer_in_recusada(self):
        self.assert_criacao_recusada('TRANSFER_IN')

    def test_criacao_de_transfer_out_recusada(self):
        self.assert_criacao_recusada('TRANSFER_OUT')

    def test_criacao_de_compra_no_cartao_recusada(self):
        self.assert_criacao_recusada('CREDIT_CARD')

    def test_criacao_de_pagamento_de_fatura_recusada(self):
        self.assert_criacao_recusada('INVOICE_PAYMENT')

    def test_criacao_de_receita_e_despesa_continua_valendo(self):
        receita = self.cliente.post(URL_TRANSACOES, self.payload(
            type='INCOME', amount='300.00', category=str(self.a.receita.id),
        ), format='json')
        despesa = self.cliente.post(URL_TRANSACOES, self.payload(type='EXPENSE', amount='100.00'), format='json')
        self.assertEqual(receita.status_code, 201, receita.data)
        self.assertEqual(despesa.status_code, 201, despesa.data)
        self.assertEqual(self.saldo(self.a.conta), Decimal('1200.00'))


class TrocaDeTipoTests(SaldoTestCase):

    def estado(self, t):
        t.refresh_from_db()
        return (t.type, t.status, t.amount, t.account_id)

    def assert_troca_recusada(self, t, tipo, metodo='patch'):
        antes = self.estado(t)
        saldo = self.saldo(self.a.conta)
        if metodo == 'patch':
            resp = self.cliente.patch(f'{URL_TRANSACOES}{t.id}/', {'type': tipo}, format='json')
        else:
            resp = self.cliente.put(f'{URL_TRANSACOES}{t.id}/', self.payload(type=tipo), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('type', resp.data)
        self.assertEqual(self.estado(t), antes)
        self.assertEqual(self.saldo(self.a.conta), saldo)

    def test_troca_de_despesa_para_tipo_especial_recusada(self):
        t = self.lancar(self.a.conta, 'EXPENSE', '100.00')
        for tipo in ESPECIAIS:
            with self.subTest(tipo=tipo):
                self.assert_troca_recusada(t, tipo)
                self.assert_troca_recusada(t, tipo, metodo='put')

    def test_troca_de_tipo_especial_para_receita_ou_despesa_recusada(self):
        for tipo in ESPECIAIS:
            transfer_id = uuid.uuid4() if tipo.startswith('TRANSFER') else None
            t = self.lancar(self.a.conta, tipo, '100.00', transfer_id=transfer_id)
            for novo in ('INCOME', 'EXPENSE'):
                with self.subTest(de=tipo, para=novo):
                    self.assert_troca_recusada(t, novo)

    def test_troca_entre_tipos_especiais_recusada(self):
        t = self.lancar(self.a.conta, 'TRANSFER_OUT', '100.00', transfer_id=uuid.uuid4())
        self.assert_troca_recusada(t, 'TRANSFER_IN')

    def test_troca_entre_receita_e_despesa_continua_valendo(self):
        t = self.lancar(self.a.conta, 'EXPENSE', '100.00')
        resp = self.cliente.patch(f'{URL_TRANSACOES}{t.id}/', {
            'type': 'INCOME', 'category': str(self.a.receita.id),
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.saldo(self.a.conta), Decimal('1100.00'))

    def test_edicao_de_perna_de_transferencia_sem_mudar_o_tipo_continua_valendo(self):
        t = self.lancar(self.a.conta, 'TRANSFER_OUT', '100.00', transfer_id=uuid.uuid4())
        resp = self.cliente.put(f'{URL_TRANSACOES}{t.id}/', self.payload(
            type='TRANSFER_OUT', description='Para a poupança', amount='100.00',
        ), format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        t.refresh_from_db()
        self.assertEqual(t.description, 'Para a poupança')


class CompraNoCartaoTests(SaldoTestCase):

    def setUp(self):
        super().setUp()
        self.compra = self.lancar(
            self.a.conta, 'CREDIT_CARD', '100.00', status='PENDING',
            credit_card=self.a.cartao, invoice=self.a.fatura,
        )

    def corpo_put(self, **extra):
        dados = {
            'type': 'CREDIT_CARD', 'status': 'PENDING', 'description': 'Loja',
            'amount': '100.00', 'date': '2026-09-15', 'account': str(self.a.conta.id),
            'credit_card': str(self.a.cartao.id), 'category': str(self.a.despesa.id),
        }
        dados.update(extra)
        return dados

    def assert_efetivacao_recusada(self, resp):
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data['status'], [MENSAGEM_COMPRA_NO_CARTAO])
        self.compra.refresh_from_db()
        self.assertEqual(self.compra.status, 'PENDING')
        self.assertEqual(self.saldo(self.a.conta), Decimal('1000.00'))

    def test_efetivar_compra_no_cartao_pela_lista_recusado(self):
        resp = self.cliente.patch(f'{URL_TRANSACOES}{self.compra.id}/', {'status': 'COMPLETED'}, format='json')
        self.assert_efetivacao_recusada(resp)

    def test_efetivar_compra_no_cartao_pelo_put_recusado(self):
        resp = self.cliente.put(f'{URL_TRANSACOES}{self.compra.id}/', self.corpo_put(status='COMPLETED'), format='json')
        self.assert_efetivacao_recusada(resp)

    def test_editar_compra_no_cartao_sem_efetivar_continua_valendo(self):
        resp = self.cliente.put(f'{URL_TRANSACOES}{self.compra.id}/', self.corpo_put(
            description='Loja nova', amount='80.00',
        ), format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.compra.refresh_from_db()
        self.assertEqual(
            (self.compra.type, self.compra.status, self.compra.description, self.compra.amount),
            ('CREDIT_CARD', 'PENDING', 'Loja nova', Decimal('80.00')),
        )
        self.assertEqual(self.saldo(self.a.conta), Decimal('1000.00'))

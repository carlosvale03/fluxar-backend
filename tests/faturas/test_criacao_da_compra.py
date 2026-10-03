"""
Criação da compra no cartão (FATURA-12 a FATURA-16) pelo endpoint
`credit-card-expense`.
"""
from datetime import date, timedelta
from decimal import Decimal

from accounts.faturas import mes_seguinte, obter_fatura
from accounts.models import CreditCardInvoice
from transactions.models import Transaction
from tests.faturas.base import URL_COMPRA, FaturasTestCase


class CriacaoDaCompraTests(FaturasTestCase):

    def comprar(self, cartao, valor, data, parcelas=1):
        return self.client.post(URL_COMPRA, {
            'credit_card': str(cartao.id), 'amount': valor, 'date': data,
            'description': 'Loja', 'category': str(self.a.categoria.id),
            'installments': parcelas,
        }, format='json')

    def parcelas(self, cartao):
        return list(
            Transaction.objects.filter(credit_card=cartao).select_related('invoice')
            .order_by('installment_number', 'created_at')
        )

    def test_100_em_4x_no_fechamento_30_uma_parcela_por_fatura_de_marco_a_junho(self):
        cartao = self.cartao(30, 7)

        resp = self.comprar(cartao, '100.00', '2026-01-30', parcelas=4)

        self.assertEqual(resp.status_code, 201, resp.data)
        parcelas = self.parcelas(cartao)
        self.assertEqual(self.meses([p.invoice for p in parcelas]), [(3, 2026), (4, 2026), (5, 2026), (6, 2026)])
        for parcela in parcelas:
            self.assertEqual(parcela.purchase_date, date(2026, 1, 30))
            self.assertEqual(parcela.date, parcela.invoice.due_date)
            self.assertEqual(parcela.amount, Decimal('25.00'))
            self.assertEqual(parcela.invoice.card_id, cartao.id)
            self.assertEqual(self.total(parcela.invoice), Decimal('25.00'))
        self.assertEqual([p['purchase_date'] for p in resp.data], ['2026-01-30'] * 4)

    def test_12x_com_fechamento_29_30_e_31_nao_repete_nem_pula_mes(self):
        datas = [date(2026, 1, 28) + timedelta(days=d) for d in range(0, 40, 3)] + [
            date(2027, 2, 28), date(2028, 2, 29), date(2026, 4, 30), date(2026, 12, 31),
        ]
        for fechamento in (29, 30, 31):
            for vencimento in (5, fechamento):
                for data in datas:
                    with self.subTest(fechamento=fechamento, vencimento=vencimento, data=data):
                        cartao = self.cartao(fechamento, vencimento)
                        resp = self.comprar(cartao, '120.00', data.isoformat(), parcelas=12)
                        self.assertEqual(resp.status_code, 201, resp.data)

                        meses = self.meses([p.invoice for p in self.parcelas(cartao)])
                        esperado = [meses[0]]
                        for _ in range(11):
                            esperado.append(mes_seguinte(*esperado[-1]))
                        self.assertEqual(meses, esperado)
                        # A primeira é a fatura que fecha depois da data da compra
                        primeira = self.fatura(cartao, *meses[0])
                        self.assertGreater(primeira.closing_date, data)
                        self.assertLessEqual(primeira.closing_date - data, timedelta(days=31))

    def test_fatura_paga_no_caminho_e_pulada(self):
        cartao = self.cartao(10, 20)
        paga = obter_fatura(cartao, 10, 2026)
        CreditCardInvoice.objects.filter(pk=paga.pk).update(status='PAID')

        resp = self.comprar(cartao, '90.00', '2026-09-05', parcelas=3)

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            self.meses([p.invoice for p in self.parcelas(cartao)]),
            [(9, 2026), (11, 2026), (12, 2026)],
        )
        self.assertEqual(self.total(paga), Decimal('0.00'))

    def test_100_em_3x_divide_os_centavos_na_primeira(self):
        cartao = self.cartao(10, 20)

        resp = self.comprar(cartao, '100.00', '2026-09-05', parcelas=3)

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            [p.amount for p in self.parcelas(cartao)],
            [Decimal('33.34'), Decimal('33.33'), Decimal('33.33')],
        )

    def test_cartao_excluido_recebe_400(self):
        cartao = self.cartao(10, 20, is_active=False)

        resp = self.comprar(cartao, '50.00', '2026-09-05')

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {'credit_card': ['Cartão não encontrado.']})
        self.assertFalse(Transaction.objects.filter(credit_card=cartao).exists())

    def test_cartao_sem_conta_de_pagamento_continua_aceito(self):
        cartao = self.cartao(10, 20, account=None)

        resp = self.comprar(cartao, '50.00', '2026-09-05')

        self.assertEqual(resp.status_code, 201, resp.data)
        [compra] = self.parcelas(cartao)
        self.assertIsNone(compra.account_id)
        self.assertEqual((compra.invoice.month, compra.invoice.year), (9, 2026))
        self.assertEqual(compra.date, date(2026, 9, 20))
        self.assertEqual(compra.purchase_date, date(2026, 9, 5))

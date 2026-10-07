"""
Edição da compra no cartão (FATURA-17, FATURA-19): data da compra e cartão
valem para a compra inteira, o `date` enviado é ignorado e compra em fatura
paga não muda.
"""
from datetime import date
from decimal import Decimal

from accounts.faturas import obter_fatura
from accounts.models import CreditCardInvoice
from transactions.models import Transaction
from tests.faturas.base import URL_COMPRA, URL_TRANSACOES, FaturasTestCase

MENSAGEM = 'Estorne o pagamento da fatura antes de alterar esta compra.'


class EdicaoDaCompraTests(FaturasTestCase):

    def setUp(self):
        super().setUp()
        # Independent Test: fechamento no dia 30, vencimento no dia 7, R$ 100,00 em 4x em 30/01/2026
        self.cartao_ = self.cartao(30, 7)
        resp = self.client.post(URL_COMPRA, {
            'credit_card': str(self.cartao_.id), 'amount': '100.00', 'date': '2026-01-30',
            'description': 'Loja', 'category': str(self.a.categoria.id), 'installments': 4,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def parcelas(self):
        return list(
            Transaction.objects.filter(user=self.a.usuario, type='CREDIT_CARD')
            .select_related('invoice').order_by('installment_number')
        )

    def editar(self, parcela, **corpo):
        return self.client.patch(f'{URL_TRANSACOES}{parcela.id}/', corpo, format='json')

    def estado(self):
        return [
            (p.invoice_id, p.date, p.purchase_date, p.amount, p.description, p.credit_card_id)
            for p in self.parcelas()
        ]

    def pagar(self, mes, ano):
        CreditCardInvoice.objects.filter(card=self.cartao_, month=mes, year=ano).update(status='PAID')

    def test_mudar_a_data_da_compra_move_as_quatro_parcelas_e_os_totais(self):
        resp = self.editar(self.parcelas()[1], purchase_date='2026-01-10')

        self.assertEqual(resp.status_code, 200, resp.data)
        parcelas = self.parcelas()
        self.assertEqual(self.meses([p.invoice for p in parcelas]), [(2, 2026), (3, 2026), (4, 2026), (5, 2026)])
        for parcela in parcelas:
            self.assertEqual(parcela.purchase_date, date(2026, 1, 10))
            self.assertEqual(parcela.date, parcela.invoice.due_date)
        for mes in (2, 3, 4, 5):
            self.assertEqual(self.total(self.fatura(self.cartao_, mes, 2026)), Decimal('25.00'))
        self.assertEqual(self.total(self.fatura(self.cartao_, 6, 2026)), Decimal('0.00'))

    def test_mudar_o_cartao_realoca_nas_faturas_do_cartao_novo(self):
        outro = self.cartao(10, 20, name='Outro', account=self.a.conta)
        antigas = [p.invoice for p in self.parcelas()]

        resp = self.editar(self.parcelas()[0], credit_card=str(outro.id))

        self.assertEqual(resp.status_code, 200, resp.data)
        parcelas = self.parcelas()
        # 30/01 é depois do fechamento de janeiro (10/01): fevereiro a maio, vencendo no dia 20
        self.assertEqual(self.meses([p.invoice for p in parcelas]), [(2, 2026), (3, 2026), (4, 2026), (5, 2026)])
        for parcela in parcelas:
            self.assertEqual(parcela.credit_card_id, outro.id)
            self.assertEqual(parcela.invoice.card_id, outro.id)
            self.assertEqual(parcela.date, parcela.invoice.due_date)
            self.assertEqual(parcela.purchase_date, date(2026, 1, 30))
        for fatura in antigas:
            self.assertEqual(self.total(fatura), Decimal('0.00'))
        self.assertEqual(self.total(self.fatura(outro, 2, 2026)), Decimal('25.00'))

    def test_compra_antiga_salva_com_a_data_carregada_nao_move_nada(self):
        cartao = self.cartao(10, 20, name='Antigo')
        fatura = obter_fatura(cartao, 9, 2026)
        antiga = self.compra(cartao, fatura, '80.00', description='Antiga')  # sem purchase_date
        antes = (antiga.invoice_id, antiga.date)

        resp = self.client.put(f'{URL_TRANSACOES}{antiga.id}/', {
            'type': 'CREDIT_CARD', 'status': 'PENDING', 'description': 'Antiga editada',
            'amount': '80.00', 'date': '2026-09-20', 'purchase_date': '2026-09-20',
            'credit_card': str(cartao.id), 'account': str(self.a.conta.id),
            'category': str(self.a.categoria.id),
        }, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        antiga.refresh_from_db()
        self.assertEqual((antiga.invoice_id, antiga.date), antes)
        self.assertIsNone(antiga.purchase_date)
        self.assertEqual(antiga.description, 'Antiga editada')

    def test_date_enviado_e_ignorado(self):
        parcela = self.parcelas()[0]

        resp = self.editar(parcela, date='2026-12-01', description='Loja nova (1/4)')

        self.assertEqual(resp.status_code, 200, resp.data)
        parcela.refresh_from_db()
        self.assertEqual(parcela.date, date(2026, 3, 7))
        self.assertEqual((parcela.invoice.month, parcela.invoice.year), (3, 2026))
        self.assertEqual(parcela.description, 'Loja nova (1/4)')

    def test_editar_parcela_de_fatura_paga_recebe_400(self):
        self.pagar(3, 2026)
        antes = self.estado()

        resp = self.editar(self.parcelas()[0], description='Outra', amount='10.00')

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {'detail': MENSAGEM, 'code': 'invalid'})
        self.assertEqual(self.estado(), antes)

    def test_mudar_a_data_de_compra_com_parte_paga_recebe_400(self):
        self.pagar(3, 2026)
        antes = self.estado()

        resp = self.editar(self.parcelas()[2], purchase_date='2026-01-10')

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {'detail': MENSAGEM, 'code': 'invalid'})
        self.assertEqual(self.estado(), antes)

    def test_editar_todas_as_futuras_com_futura_em_fatura_paga_recebe_400(self):
        self.pagar(5, 2026)
        antes = self.estado()

        resp = self.editar(self.parcelas()[1], amount='30.00', update_scope='ALL_FUTURE')

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {'detail': MENSAGEM, 'code': 'invalid'})
        self.assertEqual(self.estado(), antes)

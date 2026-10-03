"""
Status exibido, próximo vencimento e dias do cartão (FATURA-05, FATURA-06,
FATURA-08, FATURA-09) e o dashboard em meses curtos (FIN-05).

`hoje()` é simulado pelo relógio do Django, ao meio-dia de Brasília.
"""
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from accounts.faturas import obter_fatura
from accounts.models import CreditCardInvoice
from tests.faturas.base import FaturasTestCase

URL_CARTOES = '/api/credit-cards/'


def hoje_em(ano, mes, dia):
    """Simula `timezone.now()` às 15h UTC (12h em Brasília) do dia dado."""
    return mock.patch(
        'django.utils.timezone.now',
        return_value=datetime(ano, mes, dia, 15, 0, tzinfo=dt_timezone.utc),
    )


class StatusExibidoTests(FaturasTestCase):

    def setUp(self):
        super().setUp()
        self.cartao_ = self.cartao(10, 20)
        self.fatura_ = obter_fatura(self.cartao_, 9, 2026)  # fecha em 10/09/2026
        self.url = f'/api/invoices/{self.fatura_.id}/'

    def status(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        return resp.data['status']

    def test_aberta_antes_do_fechamento(self):
        with hoje_em(2026, 9, 9):
            self.assertEqual(self.status(), 'OPEN')

    def test_fechada_no_dia_do_fechamento_e_depois(self):
        with hoje_em(2026, 9, 10):
            self.assertEqual(self.status(), 'CLOSED')
        with hoje_em(2026, 9, 25):
            self.assertEqual(self.status(), 'CLOSED')
        # O banco continua com OPEN: o status fechado é só exibido
        self.assertEqual(CreditCardInvoice.objects.get(pk=self.fatura_.pk).status, 'OPEN')

    def test_paga_continua_paga_depois_do_fechamento(self):
        CreditCardInvoice.objects.filter(pk=self.fatura_.pk).update(status='PAID')
        with hoje_em(2026, 9, 9):
            self.assertEqual(self.status(), 'PAID')
        with hoje_em(2026, 9, 25):
            self.assertEqual(self.status(), 'PAID')

    def test_lista_de_faturas_do_cartao_usa_o_mesmo_status(self):
        with hoje_em(2026, 9, 10):
            resp = self.client.get(f'{URL_CARTOES}{self.cartao_.id}/invoices/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([f['status'] for f in resp.data], ['CLOSED'])


class ProximoVencimentoTests(FaturasTestCase):

    def proximo(self, cartao):
        resp = self.client.get(f'{URL_CARTOES}{cartao.id}/')
        self.assertEqual(resp.status_code, 200)
        return resp.data['next_due_date']

    def test_antes_do_vencimento_e_o_deste_mes(self):
        cartao = self.cartao(10, 20)
        with hoje_em(2026, 9, 19):
            self.assertEqual(self.proximo(cartao), date(2026, 9, 20))
        with hoje_em(2026, 9, 20):
            self.assertEqual(self.proximo(cartao), date(2026, 9, 20))

    def test_depois_do_vencimento_e_o_do_mes_seguinte(self):
        cartao = self.cartao(10, 20)
        with hoje_em(2026, 12, 21):
            self.assertEqual(self.proximo(cartao), date(2027, 1, 20))

    def test_dia_que_nao_existe_usa_o_ultimo_dia_do_mes(self):
        cartao = self.cartao(20, 31)
        with hoje_em(2026, 4, 10):
            self.assertEqual(self.proximo(cartao), date(2026, 4, 30))
        with hoje_em(2028, 2, 1):
            self.assertEqual(self.proximo(cartao), date(2028, 2, 29))


class DashboardEmMesCurtoTests(FaturasTestCase):

    def test_cartao_com_vencimento_no_dia_31_em_fevereiro(self):
        cartao = self.cartao(20, 31)
        # Compra feita hoje (05/02/2027) cai na fatura que fecha em 20/02 e vence em 28/02
        fatura = obter_fatura(cartao, 2, 2027)
        self.compra(cartao, fatura, '150.00')
        faturas_antes = CreditCardInvoice.objects.count()

        with hoje_em(2027, 2, 5):
            resp = self.client.get('/api/reports/dashboard/', {'month': 2, 'year': 2027})

        self.assertEqual(resp.status_code, 200)
        [detalhe] = resp.data['credit_cards']
        self.assertEqual(detalhe['current_invoice'], Decimal('150.00'))
        # Calcular a fatura de hoje não cria fatura
        self.assertEqual(CreditCardInvoice.objects.count(), faturas_antes)

    def test_sem_fatura_de_hoje_nao_cria_e_mostra_zero(self):
        self.cartao(20, 31)

        with hoje_em(2027, 2, 5):
            resp = self.client.get('/api/reports/dashboard/', {'month': 2, 'year': 2027})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['credit_cards'][0]['current_invoice'], Decimal('0.00'))
        self.assertFalse(CreditCardInvoice.objects.exists())


class DiasDoCartaoTests(FaturasTestCase):

    def corpo(self, **extra):
        dados = {'name': 'Novo', 'limit': '1000.00', 'closing_day': 10, 'due_day': 20}
        dados.update(extra)
        return dados

    def test_cadastro_com_dia_fora_de_1_a_31_recebe_400(self):
        for campo in ('closing_day', 'due_day'):
            for dia in (0, 32):
                resp = self.client.post(URL_CARTOES, self.corpo(**{campo: dia}), format='json')
                self.assertEqual(resp.status_code, 400, (campo, dia))
                self.assertIn(campo, resp.data)

    def test_edicao_com_dia_fora_de_1_a_31_recebe_400(self):
        cartao = self.cartao(10, 20)
        for campo in ('closing_day', 'due_day'):
            for dia in (0, 32):
                resp = self.client.patch(f'{URL_CARTOES}{cartao.id}/', {campo: dia}, format='json')
                self.assertEqual(resp.status_code, 400, (campo, dia))
                self.assertIn(campo, resp.data)
        cartao.refresh_from_db()
        self.assertEqual((cartao.closing_day, cartao.due_day), (10, 20))

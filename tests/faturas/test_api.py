"""
API de faturas (FATURA-27, FATURA-44, FATURA-45).

O cartão de A fecha no dia 10 e vence no dia 20; a fatura de setembro de
2026 vence em 20/09.
"""
import uuid
from datetime import date, timedelta

from accounts.faturas import obter_fatura
from accounts.models import CreditCardInvoice
from tests.faturas.base import FaturasTestCase

URL_FATURAS = '/api/invoices/'


class ApiDeFaturasTestCase(FaturasTestCase):

    def setUp(self):
        super().setUp()
        self.cartao_ = self.cartao(10, 20)
        self.setembro = obter_fatura(self.cartao_, 9, 2026)
        self.url = f'{URL_FATURAS}{self.setembro.id}/'


class EscritaDiretaTests(ApiDeFaturasTestCase):

    def test_criar_editar_e_excluir_fatura_recebem_405(self):
        dados = {
            'card': str(self.cartao_.id), 'month': 12, 'year': 2026, 'status': 'PAID',
            'closing_date': '2026-12-10', 'due_date': '2026-12-20', 'total_amount': '1.00',
        }
        respostas = {
            'post': self.client.post(URL_FATURAS, dados, format='json'),
            'put': self.client.put(self.url, dados, format='json'),
            'patch': self.client.patch(self.url, {'status': 'PAID'}, format='json'),
            'delete': self.client.delete(self.url),
        }

        self.assertEqual({m: r.status_code for m, r in respostas.items()},
                         {'post': 405, 'put': 405, 'patch': 405, 'delete': 405})
        self.assertEqual(CreditCardInvoice.objects.filter(card=self.cartao_).count(), 1)
        lida = CreditCardInvoice.objects.get(pk=self.setembro.pk)
        self.assertEqual((lida.status, lida.month), ('OPEN', 9))


class ComprasDaFaturaTests(ApiDeFaturasTestCase):

    def test_fatura_com_35_compras_devolve_as_35_em_ordem_de_data_da_compra(self):
        compras = [
            self.compra(self.cartao_, self.setembro, '10.00', purchase_date=date(2026, 8, 1) + timedelta(days=34 - i))
            for i in range(35)
        ]

        resp = self.client.get(f'{self.url}transactions/')

        self.assertEqual(resp.status_code, 200)
        # Lista simples, sem paginação
        self.assertIsInstance(resp.data, list)
        self.assertEqual(len(resp.data), 35)
        esperado = [str(c.id) for c in sorted(compras, key=lambda c: c.purchase_date)]
        self.assertEqual([str(t['id']) for t in resp.data], esperado)

    def test_compra_de_outro_usuario_ligada_a_fatura_nao_aparece(self):
        minha = self.compra(self.cartao_, self.setembro, '10.00', purchase_date=date(2026, 9, 1))
        self.compra(self.cartao_, self.setembro, '99.00', usuario=self.b.usuario, purchase_date=date(2026, 9, 1))

        resp = self.client.get(f'{self.url}transactions/')

        self.assertEqual([str(t['id']) for t in resp.data], [str(minha.id)])


class PagamentoNaFaturaTests(ApiDeFaturasTestCase):

    def test_fatura_paga_informa_valor_conta_e_data_e_nao_paga_vem_nula(self):
        self.compra(self.cartao_, self.setembro, '400.00', purchase_date=date(2026, 9, 1))
        antes = self.client.get(self.url)
        self.assertEqual(antes.data['payment'], None)
        self.assertEqual(antes.data['credit_card_id'], str(self.cartao_.id))

        pago = self.client.post(f'{self.url}pay/', {
            'account_id': str(self.a.conta.id), 'amount': '400.00', 'date': '2026-09-15',
        }, format='json')
        self.assertEqual(pago.status_code, 200, pago.data)

        depois = self.client.get(self.url)
        self.assertEqual(depois.data['status'], 'PAID')
        self.assertEqual(depois.data['payment'], {
            'amount': '400.00', 'account_id': str(self.a.conta.id),
            'account_name': self.a.conta.name, 'date': '2026-09-15',
        })
        # A lista de faturas do cartão usa o mesmo serializer
        lista = self.client.get(f'/api/credit-cards/{self.cartao_.id}/invoices/')
        self.assertEqual(lista.data[0]['payment']['amount'], '400.00')

        self.client.post(f'{self.url}unpay/', format='json')
        self.assertEqual(self.client.get(self.url).data['payment'], None)


class FaturaDeOutroUsuarioTests(ApiDeFaturasTestCase):

    def test_rota_de_compras_da_fatura_de_b_responde_404_como_id_inexistente(self):
        fatura_b = obter_fatura(self.cartao(10, 20, usuario=self.b.usuario), 9, 2026)
        self.compra(fatura_b.card, fatura_b, '50.00', purchase_date=date(2026, 9, 1))

        de_b = self.client.get(f'{URL_FATURAS}{fatura_b.id}/transactions/')
        inexistente = self.client.get(f'{URL_FATURAS}{uuid.uuid4()}/transactions/')

        self.assertEqual((de_b.status_code, inexistente.status_code), (404, 404))
        self.assertEqual(de_b.data, inexistente.data)

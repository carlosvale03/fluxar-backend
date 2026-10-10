"""
Pedidos de geração simultâneos para o mesmo recebimento (SALARIO-39).

Usa `TransactionTestCase`, como `tests/faturas/test_concorrencia.py`: cada
thread tem a própria conexão, espera a outra numa `threading.Barrier` e faz o
pedido pela API, para disputar a trava do recebimento e as restrições únicas
de verdade.
"""
import threading
import uuid
from decimal import Decimal

from django.db import connection
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from salario.models import DivisaoDoSalario
from transactions.models import Transaction

from .base import URL_DIVISOES, URL_PLANO, criar_dados, hoje_em, plano_50_30_20, receita


class GeracoesSimultaneasTests(TransactionTestCase):

    def setUp(self):
        self.a = criar_dados('A')
        cliente = APIClient()
        cliente.force_authenticate(user=self.a.usuario)
        resposta = cliente.put(URL_PLANO, {'parts': plano_50_30_20(guardar_na=self.a.viagem)}, format='json')
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.salario = receita(self.a)

    def em_paralelo(self, corpos):
        barreira = threading.Barrier(len(corpos), timeout=20)
        respostas, erros = [], []

        def trabalho(corpo):
            try:
                cliente = APIClient()
                cliente.force_authenticate(user=self.a.usuario)
                barreira.wait()
                respostas.append(cliente.post(URL_DIVISOES, corpo, format='json'))
            except Exception as erro:  # noqa: BLE001 - repassado ao teste abaixo
                erros.append(erro)
            finally:
                connection.close()

        with hoje_em(2026, 10, 10):
            threads = [threading.Thread(target=trabalho, args=(corpo,)) for corpo in corpos]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=60)
        self.assertFalse(any(t.is_alive() for t in threads), 'thread presa')
        self.assertEqual(erros, [])
        return respostas

    def corpo(self, chave):
        return {'receipt': str(self.salario.pk), 'idempotency_key': str(chave)}

    def assert_um_lote_so(self):
        self.assertEqual(DivisaoDoSalario.objects.count(), 1)
        self.assertEqual(Transaction.objects.filter(divisao_do_salario__isnull=False).count(), 2)
        self.a.viagem.refresh_from_db()
        self.assertEqual(self.a.viagem.current_amount, Decimal('600.00'))

    def test_chaves_diferentes_geram_um_lote_e_o_outro_recebe_ja_dividido(self):
        respostas = self.em_paralelo([self.corpo(uuid.uuid4()), self.corpo(uuid.uuid4())])

        self.assertEqual(sorted(r.status_code for r in respostas), [201, 400])
        [recusa] = [r for r in respostas if r.status_code == 400]
        self.assertEqual(recusa.data, {'detail': 'Este salário já foi dividido.', 'code': 'invalid'})
        self.assert_um_lote_so()

    def test_mesma_chave_gera_um_lote_e_as_duas_respostas_sao_iguais(self):
        chave = uuid.uuid4()

        respostas = self.em_paralelo([self.corpo(chave), self.corpo(chave)])

        self.assertEqual([r.status_code for r in respostas], [201, 201])
        self.assertEqual(respostas[0].data, respostas[1].data)
        self.assert_um_lote_so()

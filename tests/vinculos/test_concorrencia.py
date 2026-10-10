"""
Pedidos simultâneos de vínculo entre as mesmas transações (VINCULO-19).

Usa `TransactionTestCase`, como `tests/salario/test_concorrencia.py`: cada
thread tem a própria conexão, espera a outra numa `threading.Barrier` e chama
`vincular`, para disputar as travas das transações de verdade.
"""
import threading

from django.db import connection
from django.test import TransactionTestCase
from rest_framework.exceptions import ValidationError

from transactions.models import Transaction
from transactions.vinculos import vincular

from .base import criar_dados, despesa


class VinculosSimultaneosTests(TransactionTestCase):

    def setUp(self):
        self.a = criar_dados('A')
        self.cinema = despesa(self.a, 'Cinema', '50.00')
        self.transporte = despesa(self.a, 'Transporte', '45.00')
        self.pipoca = despesa(self.a, 'Pipoca', '20.00')

    def em_paralelo(self, pares):
        barreira = threading.Barrier(len(pares), timeout=20)
        resultados, erros = [], []

        def trabalho(dependente_id, principal_id):
            try:
                dependente = Transaction.objects.get(pk=dependente_id)
                principal = Transaction.objects.get(pk=principal_id)
                barreira.wait()
                try:
                    vincular(dependente, principal)
                    resultados.append('ok')
                except ValidationError as erro:
                    resultados.append(erro.detail['detail'])
            except Exception as erro:  # noqa: BLE001 - repassado ao teste abaixo
                erros.append(erro)
            finally:
                connection.close()

        threads = [threading.Thread(target=trabalho, args=(d.pk, p.pk)) for d, p in pares]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
        self.assertFalse(any(t.is_alive() for t in threads), 'thread presa')
        self.assertEqual(erros, [])
        return resultados

    def assert_um_nivel_so(self):
        dependentes = Transaction.objects.filter(principal__isnull=False)
        # Nenhuma principal é dependente de outra
        self.assertFalse(dependentes.filter(principal__principal__isnull=False).exists())

    def test_a_em_b_e_b_em_a_so_um_passa(self):
        resultados = self.em_paralelo([(self.cinema, self.transporte), (self.transporte, self.cinema)])

        self.assertEqual(sorted(resultados), sorted(['ok', 'Uma transação dependente não pode ser principal.']))
        self.assertEqual(Transaction.objects.filter(principal__isnull=False).count(), 1)
        self.assert_um_nivel_so()

    def test_cadeia_simultanea_nao_monta_dois_niveis(self):
        # Pipoca em Transporte e Transporte em Cinema ao mesmo tempo
        resultados = self.em_paralelo([(self.pipoca, self.transporte), (self.transporte, self.cinema)])

        self.assertEqual(resultados.count('ok'), 1)
        self.assertEqual(len(resultados), 2)
        self.assert_um_nivel_so()

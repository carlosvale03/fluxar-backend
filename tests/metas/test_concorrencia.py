"""
Resgates simultâneos na mesma meta (META-22).

Usa `TransactionTestCase`, como `tests/saldo/test_concorrencia.py`: cada
thread tem a própria conexão e disputa a trava da meta de verdade.
"""
import threading
from decimal import Decimal

from django.db import connection
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from goals.models import Goal, GoalDeposit
from goals.valores import calcular, recalcular
from tests.metas.base import criar_dados, registrar, transferir


class ResgatesSimultaneosTests(TransactionTestCase):

    def setUp(self):
        self.a = criar_dados('A')
        transferencia = transferir(self.a.conta, self.a.cofrinho, '500.00')
        registrar(self.a.meta, 'DEPOSIT', '500.00', conta=self.a.conta, transferencia=transferencia)
        recalcular(self.a.meta.pk)

    def em_paralelo(self, n, requisicao):
        barreira = threading.Barrier(n, timeout=20)
        respostas, erros = [], []

        def trabalho():
            try:
                cliente = APIClient()
                cliente.force_authenticate(user=self.a.usuario)
                barreira.wait()
                respostas.append(requisicao(cliente))
            except Exception as erro:  # noqa: BLE001 - repassado ao teste abaixo
                erros.append(erro)
            finally:
                connection.close()

        threads = [threading.Thread(target=trabalho) for _ in range(n)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
        self.assertFalse(any(t.is_alive() for t in threads), 'thread presa')
        self.assertEqual(erros, [])
        return respostas

    def assert_so_um_passa(self, corpo):
        url = f'/api/goals/{self.a.meta.pk}/withdraw/'

        respostas = self.em_paralelo(2, lambda c: c.post(url, corpo, format='json'))

        self.assertEqual(sorted(r.status_code for r in respostas), [200, 400])
        recusa = next(r for r in respostas if r.status_code == 400)
        self.assertEqual(recusa.data['detail'], 'A meta tem R$ 200,00 para resgatar.')
        meta = Goal.objects.get(pk=self.a.meta.pk)
        self.assertEqual(meta.current_amount, Decimal('200.00'))
        self.assertEqual(calcular(meta), Decimal('200.00'))
        self.assertEqual(GoalDeposit.objects.filter(type='WITHDRAWAL').count(), 1)

    def test_dois_resgates_para_o_saldo_livre_deixam_passar_so_um(self):
        self.assert_so_um_passa({'amount': '300.00', 'to_free_balance': True})

    def test_dois_resgates_para_outra_conta_deixam_passar_so_um(self):
        self.assert_so_um_passa({'amount': '300.00', 'account_to': str(self.a.conta.pk)})

"""
Ordem das travas entre o aporte e a edição da transferência ligada à meta.

O aporte e a edição de uma transferência travam as contas em ordem de id e só
depois a meta (AD-038, AD-045). Com ordens diferentes, as duas operações
simultâneas se travam em deadlock e uma delas falha.

O teste força o pior caso: a edição para logo depois de gravar a primeira
perna, já com a conta travada e antes de travar a meta, e o aporte começa
nesse momento.
"""
import threading
import time
from decimal import Decimal
from unittest import mock

from django.db import connection
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from accounts.models import Account
from goals import vinculo
from goals.models import Goal
from goals.valores import calcular, recalcular
from tests.metas.base import criar_dados, registrar, transferir

ao_salvar_original = vinculo.ao_salvar


class AporteEEdicaoSimultaneosTests(TransactionTestCase):

    def setUp(self):
        self.a = criar_dados('A')
        self.transferencia = transferir(self.a.conta, self.a.cofrinho, '500.00')
        registrar(self.a.meta, 'DEPOSIT', '500.00', conta=self.a.conta, transferencia=self.transferencia)
        recalcular(self.a.meta.pk)

    def test_aporte_e_edicao_da_transferencia_da_mesma_meta_sem_deadlock(self):
        conta_travada = threading.Event()
        respostas, erros = {}, []

        def ao_salvar_com_pausa(transacao):
            # A edição já gravou a perna e travou a conta dela; o aporte começa agora
            if not conta_travada.is_set():
                conta_travada.set()
                time.sleep(1.5)
            return ao_salvar_original(transacao)

        def cliente():
            c = APIClient()
            c.force_authenticate(user=self.a.usuario)
            return c

        def editar():
            try:
                respostas['edicao'] = cliente().patch(
                    f'/api/transactions/{self.transferencia[1].pk}/', {'amount': '300.00'}, format='json',
                )
            except Exception as erro:  # noqa: BLE001 - repassado ao teste abaixo
                erros.append(erro)
                conta_travada.set()
            finally:
                connection.close()

        def aportar():
            try:
                conta_travada.wait(timeout=20)
                respostas['aporte'] = cliente().post(
                    f'/api/goals/{self.a.meta.pk}/deposit/',
                    {'amount': '100.00', 'account_id': str(self.a.conta.pk)}, format='json',
                )
            except Exception as erro:  # noqa: BLE001 - repassado ao teste abaixo
                erros.append(erro)
            finally:
                connection.close()

        with mock.patch.object(vinculo, 'ao_salvar', ao_salvar_com_pausa):
            threads = [threading.Thread(target=editar), threading.Thread(target=aportar)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=60)

        self.assertFalse(any(t.is_alive() for t in threads), 'thread presa')
        self.assertEqual(erros, [])
        self.assertEqual(respostas['edicao'].status_code, 200, respostas['edicao'].content)
        self.assertEqual(respostas['aporte'].status_code, 200, respostas['aporte'].content)
        # Os R$ 500,00 viram R$ 300,00, mais o aporte de R$ 100,00
        meta = Goal.objects.get(pk=self.a.meta.pk)
        self.assertEqual(meta.current_amount, Decimal('400.00'))
        self.assertEqual(calcular(meta), Decimal('400.00'))
        self.assertEqual(Account.objects.get(pk=self.a.cofrinho.pk).balance, Decimal('400.00'))
        self.assertEqual(Account.objects.get(pk=self.a.conta.pk).balance, Decimal('600.00'))

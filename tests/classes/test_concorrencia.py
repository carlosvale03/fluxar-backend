"""
Criações simultâneas de classes do mesmo usuário (CLASSE-12).

Usa `TransactionTestCase` e duas threads, cada uma com a própria conexão,
como `tests/metas/test_concorrencia.py`.
"""
import threading

from django.db import connection
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from transactions.models import ClasseDeDespesa

from .base import LIMITE_ATINGIDO, NOME_REPETIDO, ROTA, criar_classe, criar_usuario


class CriacoesSimultaneasTests(TransactionTestCase):

    def setUp(self):
        self.ana = criar_usuario()

    def em_paralelo(self, corpos):
        barreira = threading.Barrier(len(corpos), timeout=20)
        respostas, erros = [], []

        def trabalho(corpo):
            try:
                cliente = APIClient()
                cliente.force_authenticate(user=self.ana)
                barreira.wait()
                respostas.append(cliente.post(ROTA, corpo, format='json'))
            except Exception as erro:  # noqa: BLE001 - repassado ao teste abaixo
                erros.append(erro)
            finally:
                connection.close()

        threads = [threading.Thread(target=trabalho, args=(corpo,)) for corpo in corpos]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
        self.assertFalse(any(t.is_alive() for t in threads), 'thread presa')
        self.assertEqual(erros, [])
        return respostas

    def test_duas_criacoes_com_quatro_classes_terminam_com_cinco(self):
        criar_classe(self.ana, 'Dívidas')
        criar_classe(self.ana, 'Profissional')

        respostas = self.em_paralelo([
            {'name': 'Impostos e taxas', 'color': '#111111'},
            {'name': 'Viagens', 'color': '#222222'},
        ])

        self.assertEqual(sorted(r.status_code for r in respostas), [201, 400])
        recusa = next(r for r in respostas if r.status_code == 400)
        self.assertEqual(recusa.data, LIMITE_ATINGIDO)
        self.assertEqual(ClasseDeDespesa.objects.filter(user=self.ana).count(), 5)

    def test_duas_criacoes_com_o_mesmo_nome_terminam_com_uma(self):
        respostas = self.em_paralelo([
            {'name': 'Dívidas', 'color': '#111111'},
            {'name': 'dividas', 'color': '#222222'},
        ])

        self.assertEqual(sorted(r.status_code for r in respostas), [201, 400])
        recusa = next(r for r in respostas if r.status_code == 400)
        self.assertEqual(recusa.data, NOME_REPETIDO)
        self.assertEqual(ClasseDeDespesa.objects.filter(user=self.ana, nome_normalizado='dividas').count(), 1)

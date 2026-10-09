from datetime import date
from decimal import Decimal

from goals.models import GoalDeposit
from tests.isolamento.base import DoisUsuariosTestCase


class HistoricoDaMetaTests(DoisUsuariosTestCase):
    """O histórico vem paginado (META-32): os movimentos ficam em `results`."""

    def setUp(self):
        # Movimento no cofrinho de A gravado à força na meta de B, como antes da correção
        self.movimento_de_a = GoalDeposit.objects.create(
            goal=self.b.meta, account=self.a.cofrinho, amount=Decimal('70.00'),
            type='DEPOSIT', description='Automático: Salário A', date=date(2026, 9, 5),
        )
        self.aporte_de_b = GoalDeposit.objects.create(
            goal=self.b.meta, account=self.b.cofrinho, amount=Decimal('30.00'),
            type='DEPOSIT', description='Aporte B', date=date(2026, 9, 6),
        )
        self.resgate_de_b = GoalDeposit.objects.create(
            goal=self.b.meta, account=self.b.conta, amount=Decimal('10.00'),
            type='WITHDRAWAL', description='Resgate B', date=date(2026, 9, 7),
        )
        self.url = f'/api/goals/{self.b.meta.id}/history/'

    def test_historico_nao_traz_movimento_do_cofrinho_de_a(self):
        resp = self.como(self.b.usuario).get(self.url)

        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(self.movimento_de_a.id, [m['id'] for m in resp.data['results']])
        self.assertNotIn('Cofrinho A', str(resp.data))
        self.assertNotIn('Salário A', str(resp.data))

    def test_historico_continua_trazendo_os_movimentos_de_b(self):
        resp = self.como(self.b.usuario).get(self.url)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            [(m['id'], m['account_name'], m['type']) for m in resp.data['results']],
            [
                (self.resgate_de_b.id, 'Conta B', 'WITHDRAWAL'),
                (self.aporte_de_b.id, 'Cofrinho B', 'DEPOSIT'),
            ],
        )

"""
Histórico paginado, trava do plano e exclusão do usuário (META-32 a META-34).
"""
from datetime import date, timedelta
from decimal import Decimal

from django.core.cache import cache

from accounts.models import Account
from api.models import User
from core import travas
from goals.models import Goal, GoalDeposit
from goals.valores import recalcular
from transactions.models import Transaction
from tests.metas.base import DIA, MetasTestCase, registrar, transferir
from tests.permissoes.base import fechar, liberacao_de_testes


class HistoricoTests(MetasTestCase):

    def url(self):
        return f'/api/goals/{self.a.meta.pk}/history/'

    def test_quarenta_e_cinco_registros_vem_em_paginas_de_20_do_mais_recente(self):
        inicio = date(2026, 1, 1)
        for dia in range(45):
            registrar(self.a.meta, 'DEPOSIT', '1.00', data=inicio + timedelta(days=dia))

        pagina_1 = self.client.get(self.url())
        pagina_3 = self.client.get(self.url(), {'page': 3})

        self.assertEqual(pagina_1.status_code, 200)
        self.assertEqual(
            (pagina_1.data['count'], pagina_1.data['total_pages'], pagina_1.data['current_page']), (45, 3, 1),
        )
        self.assertEqual(len(pagina_1.data['results']), 20)
        self.assertIsNone(pagina_1.data['previous'])
        self.assertIn('page=2', pagina_1.data['next'])
        datas = [r['date'] for r in pagina_1.data['results']]
        self.assertEqual(datas[0], (inicio + timedelta(days=44)).isoformat())
        self.assertEqual(datas, sorted(datas, reverse=True))
        self.assertEqual(len(pagina_3.data['results']), 5)
        self.assertEqual(pagina_3.data['results'][-1]['date'], inicio.isoformat())
        self.assertEqual(len(self.client.get(self.url(), {'page_size': 50}).data['results']), 45)

    def test_cada_registro_traz_tipo_valor_data_conta_e_transacao(self):
        transferencia = transferir(self.a.conta, self.a.cofrinho, '500.00')
        registrar(self.a.meta, 'DEPOSIT', '500.00', conta=self.a.conta, transferencia=transferencia)
        registrar(self.a.meta, 'WITHDRAWAL', '120.00', data=DIA + timedelta(days=1))
        registrar(self.a.meta, 'DEPOSIT', '30.00', data=DIA + timedelta(days=2), eh_correcao=True)

        resultados = self.client.get(self.url()).data['results']

        campos = ('type', 'amount', 'date', 'account', 'account_name', 'transaction', 'is_correction')
        self.assertEqual([tuple(r[c] for c in campos) for r in resultados], [
            ('DEPOSIT', '30.00', '2026-09-17', self.a.cofrinho.pk, 'Cofrinho A', None, True),
            ('WITHDRAWAL', '120.00', '2026-09-16', self.a.cofrinho.pk, 'Cofrinho A', None, False),
            ('DEPOSIT', '500.00', '2026-09-15', self.a.conta.pk, 'Corrente A', transferencia[0], False),
        ])

    def test_parametro_desconhecido_e_recusado(self):
        resp = self.client.get(self.url(), {'x': 1})

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['detail'], 'Filtro desconhecido: x.')


class TravaDoPlanoTests(MetasTestCase):

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(travas.invalidar)
        liberacao_de_testes(False)
        fechar('metas')

    def test_rotas_novas_recebem_403_e_a_transferencia_para_o_cofrinho_continua(self):
        meta = self.a.meta.pk
        for metodo, url in (
            ('get', '/api/goals/piggy-banks/'),
            ('get', f'/api/goals/{meta}/history/'),
            ('post', f'/api/goals/{meta}/dismiss-correction/'),
            ('post', f'/api/goals/{meta}/deposit/'),
            ('post', f'/api/goals/{meta}/withdraw/'),
        ):
            resp = getattr(self.client, metodo)(url)
            self.assertEqual(resp.status_code, 403, url)
            self.assertEqual((resp.data['code'], resp.data['feature']), ('plan_locked', 'metas'), url)

        resp = self.client.post('/api/transactions/transfer/', {
            'account_from': str(self.a.conta.pk), 'account_to': str(self.a.cofrinho.pk),
            'amount': '100.00', 'date': '2026-09-15',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Account.objects.get(pk=self.a.cofrinho.pk).balance, Decimal('100.00'))


class ExclusaoDoUsuarioTests(MetasTestCase):

    def test_apaga_as_metas_e_os_registros_junto_com_os_demais_dados(self):
        transferencia = transferir(self.a.conta, self.a.cofrinho, '500.00')
        registrar(self.a.meta, 'DEPOSIT', '500.00', conta=self.a.conta, transferencia=transferencia)
        resgate = transferir(self.a.cofrinho, self.a.conta, '200.00')
        registrar(self.a.meta, 'WITHDRAWAL', '200.00', conta=self.a.conta, transferencia=resgate)
        registrar(self.a.meta, 'DEPOSIT', '50.00')
        recalcular(self.a.meta.pk)
        registrar(self.b.meta, 'DEPOSIT', '10.00')

        User.objects.get(pk=self.a.usuario.pk).delete()

        self.assertFalse(Goal.objects.filter(user_id=self.a.usuario.pk).exists())
        self.assertFalse(GoalDeposit.objects.filter(goal_id=self.a.meta.pk).exists())
        self.assertFalse(Transaction.objects.filter(user_id=self.a.usuario.pk).exists())
        # Os dados de B continuam
        self.assertEqual(GoalDeposit.objects.filter(goal=self.b.meta).count(), 1)

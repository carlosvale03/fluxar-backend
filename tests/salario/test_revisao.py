"""
Salários a dividir e revisão da divisão (SALARIO-24, SALARIO-29,
SALARIO-30, SALARIO-40).
"""
import uuid
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from salario.models import DivisaoDoSalario
from transactions.models import Category

from .base import (
    URL_PENDENTES, URL_PLANO, URL_REVISAO, SalarioTestCase, hoje_em, parte, plano_50_30_20, receita,
)

NAO_E_SALARIO = {'receipt': ['Escolha um salário recebido para dividir.']}


class SalariosADividirTests(SalarioTestCase):

    def pendentes(self):
        resposta = self.client.get(URL_PENDENTES)
        self.assertEqual(resposta.status_code, 200)
        return [item['id'] for item in resposta.data]

    def test_lista_os_salarios_efetivados_do_mes_atual_e_do_anterior(self):
        deste_mes = receita(self.a, data=date(2026, 10, 5))
        importado = receita(self.a, data=date(2026, 10, 1), import_batch=uuid.uuid4())
        do_mes_anterior = receita(self.a, data=date(2026, 9, 1))
        receita(self.a, data=date(2026, 8, 31))
        receita(self.a, data=date(2026, 10, 9), status='PENDING')
        investimento = Category.objects.get(user=self.a.usuario, name='Investimento', type='INCOME')
        receita(self.a, data=date(2026, 10, 6), categoria=investimento)
        receita(self.b, data=date(2026, 10, 6))
        dividido = receita(self.a, data=date(2026, 10, 7))
        DivisaoDoSalario.objects.create(
            user=self.a.usuario, recebimento=dividido, recebimento_ref=dividido.pk,
            valor_recebido=Decimal('3000.00'), total=Decimal('600.00'), livre=Decimal('2400.00'),
        )

        with hoje_em(2026, 10, 10):
            ids = self.pendentes()

        self.assertEqual(ids, [str(deste_mes.pk), str(importado.pk), str(do_mes_anterior.pk)])

    def test_cada_salario_traz_valor_data_conta_e_categoria(self):
        importado = receita(self.a, valor='3210.50', data=date(2026, 10, 1), import_batch=uuid.uuid4())

        with hoje_em(2026, 10, 10):
            resposta = self.client.get(URL_PENDENTES)

        self.assertEqual(resposta.data, [{
            'id': str(importado.pk), 'description': 'Salário', 'amount': '3210.50', 'date': '2026-10-01',
            'account': str(self.a.conta.pk), 'account_name': 'Corrente A',
            'category': str(self.a.salario.pk), 'category_name': 'Salário', 'imported': True,
        }])

    def test_subcategoria_de_salario_entra_na_lista(self):
        bonus = Category.objects.create(user=self.a.usuario, name='Bônus', type='INCOME', parent=self.a.salario)
        recebido = receita(self.a, data=date(2026, 10, 2), categoria=bonus)

        with hoje_em(2026, 10, 10):
            self.assertEqual(self.pendentes(), [str(recebido.pk)])

    def test_virada_do_ano_inclui_dezembro_no_mes_anterior(self):
        dezembro = receita(self.a, data=date(2026, 12, 20))
        receita(self.a, data=date(2026, 11, 30))

        with hoje_em(2027, 1, 3):
            self.assertEqual(self.pendentes(), [str(dezembro.pk)])


class RevisaoTests(SalarioTestCase):

    def setUp(self):
        super().setUp()
        self.salvar_plano(plano_50_30_20(guardar_na=self.a.viagem))
        self.guardar_id = self.client.get(URL_PLANO).data['parts'][2]['id']
        self.salario = receita(self.a)

    def revisar(self, recebimento=None, **extra):
        corpo = {'receipt': str((recebimento or self.salario).pk), **extra}
        with hoje_em(2026, 10, 10):
            return self.client.post(URL_REVISAO, corpo, format='json')

    def test_mostra_origem_destino_valor_data_total_e_livre(self):
        resposta = self.revisar()

        self.assertEqual(resposta.status_code, 200, resposta.data)
        origem = {'id': str(self.a.conta.pk), 'name': 'Corrente A'}
        self.assertEqual(resposta.data['items'], [
            {'part_id': resposta.data['items'][0]['part_id'], 'name': 'Essenciais',
             'destination_type': 'SALARY_ACCOUNT', 'destination_name': 'Fica na conta do salário',
             'amount': '1500.00', 'reduced': False, 'adjusted': False, 'generates_transaction': False,
             'origin_account': origem},
            {'part_id': resposta.data['items'][1]['part_id'], 'name': 'Dispensáveis',
             'destination_type': 'SALARY_ACCOUNT', 'destination_name': 'Fica na conta do salário',
             'amount': '900.00', 'reduced': False, 'adjusted': False, 'generates_transaction': False,
             'origin_account': origem},
            {'part_id': self.guardar_id, 'name': 'Guardar', 'destination_type': 'GOAL',
             'destination_name': 'Viagem A', 'amount': '600.00', 'reduced': False, 'adjusted': False,
             'generates_transaction': True, 'origin_account': origem},
        ])
        self.assertEqual(
            (resposta.data['total'], resposta.data['free'], resposta.data['date']),
            ('600.00', '2400.00', '2026-10-10'),
        )
        self.assertEqual(resposta.data['receipt']['id'], str(self.salario.pk))

    def test_data_e_a_de_hoje_em_brasilia(self):
        # 02h30 UTC do dia 11 ainda é 23h30 do dia 10 em Brasília (AD-008)
        noite = datetime(2026, 10, 11, 2, 30, tzinfo=dt_timezone.utc)
        with mock.patch('django.utils.timezone.now', return_value=noite):
            resposta = self.client.post(URL_REVISAO, {'receipt': str(self.salario.pk)}, format='json')

        self.assertEqual(resposta.data['date'], '2026-10-10')

    def test_ajuste_vale_so_na_revisao(self):
        resposta = self.revisar(adjustments={self.guardar_id: '450.00'})

        self.assertEqual(resposta.status_code, 200, resposta.data)
        guardar = resposta.data['items'][2]
        self.assertEqual((guardar['amount'], guardar['adjusted']), ('450.00', True))
        self.assertEqual((resposta.data['total'], resposta.data['free']), ('450.00', '2550.00'))
        # O plano salvo continua com 20%
        self.assertEqual(self.client.get(URL_PLANO).data['parts'][2]['value'], '20.00')

    def test_ajustes_que_passam_do_recebido_sao_recusados(self):
        resposta = self.revisar(adjustments={self.guardar_id: '3000.01'})

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data, {'adjustments': ['Os valores passam do salário recebido.']})

    def test_partes_reduzidas_vem_marcadas(self):
        self.salvar_plano([
            parte('Aluguel', 'FIXED', '2500.00', 'ACCOUNT', account=self.a.poupanca),
            parte('Reserva', 'FIXED', '800.00', 'GOAL', goal=self.a.viagem),
        ])

        resposta = self.revisar()

        self.assertEqual(
            [(i['amount'], i['reduced']) for i in resposta.data['items']],
            [('2500.00', False), ('500.00', True)],
        )
        self.assertEqual(resposta.data['free'], '0.00')

    def test_recebimento_que_nao_e_salario_recebido_e_recusado(self):
        investimento = Category.objects.get(user=self.a.usuario, name='Investimento', type='INCOME')
        casos = {
            'pendente': receita(self.a, status='PENDING').pk,
            'outra categoria': receita(self.a, categoria=investimento).pk,
            'de outro usuário': receita(self.b).pk,
            'inexistente': uuid.uuid4(),
        }
        for nome, pk in casos.items():
            with self.subTest(nome):
                with hoje_em(2026, 10, 10):
                    resposta = self.client.post(URL_REVISAO, {'receipt': str(pk)}, format='json')

                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.data, NAO_E_SALARIO)

    def test_salario_ja_dividido_e_recusado(self):
        DivisaoDoSalario.objects.create(
            user=self.a.usuario, recebimento=self.salario, recebimento_ref=self.salario.pk,
            valor_recebido=Decimal('3000.00'), total=Decimal('600.00'), livre=Decimal('2400.00'),
        )

        resposta = self.revisar()

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data, {'detail': 'Este salário já foi dividido.', 'code': 'invalid'})

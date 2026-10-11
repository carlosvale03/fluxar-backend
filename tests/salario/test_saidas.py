"""
Saídas desde o salário (SALARIO-64 a SALARIO-70, SALARIO-72, SALARIO-73, SALARIO-75, SALARIO-77,
AD-057).

O salário de R$ 3.000,00 cai na corrente em 05/10 e a divisão acontece em
10/10. O plano tem Necessidades (R$ 200,00 para a poupança, referência
Essencial), Diversão (R$ 100,00 na conta do salário, referência Dispensável)
e Guardar (R$ 300,00 para a meta Viagem). O cartão "Cartão A" é pago pela
corrente e vence no dia 15, depois de hoje: a compra paga entra pela data do
pagamento, não pela do vencimento.
"""
import uuid
from datetime import date
from decimal import Decimal
from unittest import mock

from accounts import faturas
from accounts.faturas import obter_fatura
from accounts.models import Account, CreditCard
from goals.services import GoalService
from salario.models import DivisaoDoSalario, SaidaDescontada
from transactions.models import Category, Transaction
from transactions.services import TransactionService

from .base import (
    URL_DIVISOES, URL_PENDENTES, URL_PLANO, URL_REVISAO, SalarioTestCase, hoje_em, parte, receita, url_da_divisao,
    url_do_desfazer,
)

SAIDA_NAO_ENCONTRADA = {'outflows': ['Saída não encontrada.']}
PARTE_NAO_ENCONTRADA = {'outflows': ['Parte não encontrada.']}
DIVISAO_MUDOU = {'detail': 'A divisão mudou desde a revisão. Confira de novo antes de gerar.', 'code': 'invalid'}


class SaidasTestCase(SalarioTestCase):

    def setUp(self):
        super().setUp()
        self.salvar_plano([
            parte('Necessidades', 'FIXED', '200.00', 'ACCOUNT', account=self.a.poupanca, reference='ESSENCIAL'),
            parte('Diversão', 'FIXED', '100.00', 'SALARY_ACCOUNT', reference='DISPENSAVEL'),
            parte('Guardar', 'FIXED', '300.00', 'GOAL', goal=self.a.viagem),
        ])
        self.necessidades, self.diversao, self.guardar = [p['id'] for p in self.client.get(URL_PLANO).data['parts']]
        self.salario = receita(self.a)
        self.comida = Category.objects.get(user=self.a.usuario, name='Comida', type='EXPENSE')
        self.lazer = Category.objects.get(user=self.a.usuario, name='Lazer', type='EXPENSE')
        self.freela = Category.objects.create(user=self.a.usuario, name='Freela', type='INCOME')

    def despesa(self, valor='130.00', data=date(2026, 10, 6), categoria=None, usuario=None, **extra):
        extra.setdefault('account', self.a.conta)
        extra.setdefault('status', 'COMPLETED')
        return Transaction.objects.create(
            user=usuario or self.a.usuario, type=extra.pop('type', 'EXPENSE'),
            category=extra.pop('category', categoria or self.comida),
            description=extra.pop('description', 'Mercado do mês'),
            amount=Decimal(valor), date=data, **extra,
        )

    def transferencia(self, destino, valor='50.00', data=date(2026, 10, 7)):
        transfer_id = TransactionService.create_transfer(
            user=self.a.usuario, account_from=self.a.conta, account_to=destino,
            amount=Decimal(valor), date=data, description='Transferência',
        )
        return Transaction.objects.get(transfer_id=transfer_id, type='TRANSFER_OUT')

    def aporte(self, valor='100.00', data=date(2026, 10, 8)):
        GoalService.aportar(self.a.viagem, Decimal(valor), data, account=self.a.conta)
        return Transaction.objects.filter(account=self.a.conta, type='TRANSFER_OUT').latest('created_at')

    def revisar(self, recebimento=None, dia=(2026, 10, 10), **extra):
        corpo = {'receipt': str((recebimento or self.salario).pk), **extra}
        with hoje_em(*dia):
            return self.client.post(URL_REVISAO, corpo, format='json')

    def gerar(self, recebimento=None, dia=(2026, 10, 10), **extra):
        corpo = {'receipt': str((recebimento or self.salario).pk), **extra}
        with hoje_em(*dia):
            return self.client.post(URL_DIVISOES, corpo, format='json')

    def listadas(self, resposta):
        self.assertEqual(resposta.status_code, 200, resposta.data)
        return [s['id'] for s in resposta.data['outflows']]

    def item(self, resposta, nome):
        return next(i for i in resposta.data['items'] if i['name'] == nome)


class SaidasElegiveisTests(SaidasTestCase):
    """SALARIO-64."""

    def test_lista_despesas_transferencias_aportes_e_pagamentos_de_fatura_da_data_do_recebimento_ate_hoje(self):
        no_dia_do_recebimento = self.despesa(data=date(2026, 10, 5))
        transferencia = self.transferencia(self.a.poupanca)
        aporte = self.aporte()
        fatura = self.despesa(valor='80.00', data=date(2026, 10, 10), type='INVOICE_PAYMENT', category=None)

        ids = self.listadas(self.revisar())

        self.assertEqual(ids, [str(no_dia_do_recebimento.pk), str(transferencia.pk), str(aporte.pk), str(fatura.pk)])

    def test_deixa_fora_as_saidas_que_nao_sairam_do_salario(self):
        # Outro salário no mesmo dia e na mesma conta: as janelas dos dois se cruzam (SALARIO-75)
        outro_salario = receita(self.a, valor='1000.00', data=date(2026, 10, 5))
        self.despesa(account=self.a.poupanca)                                    # outra conta
        self.despesa(data=date(2026, 10, 4))                                     # antes do recebimento
        self.despesa(data=date(2026, 10, 11))                                    # depois de hoje
        self.despesa(status='PENDING')                                           # pendente
        self.despesa(is_balance_adjustment=True)                                 # ajuste de saldo
        self.despesa(divisao_do_salario=uuid.uuid4())                            # gerada por uma divisão
        self.despesa(usuario=self.b.usuario)                                     # de outro usuário
        receita(self.a, valor='10.00', data=date(2026, 10, 6), categoria=self.freela)    # entrada
        descontada = self.despesa(description='Já descontada')
        # Descontada na divisão ativa do outro salário da mesma conta
        resposta = self.gerar(outro_salario, outflows={str(descontada.pk): self.diversao})
        self.assertEqual(resposta.status_code, 201, resposta.data)

        ids = self.listadas(self.revisar())

        self.assertEqual(ids, [])


class JanelaAteOProximoSalarioTests(SaidasTestCase):
    """SALARIO-75: o salário de 05/10 e o próximo, de 08/10, na mesma corrente."""

    def setUp(self):
        super().setUp()
        self.antes = self.despesa(data=date(2026, 10, 7), description='Véspera do próximo')
        self.depois = self.despesa(data=date(2026, 10, 8), description='Dia do próximo')

    def test_as_saidas_vao_ate_a_vespera_do_proximo_salario(self):
        proximo = receita(self.a, valor='500.00', data=date(2026, 10, 8))

        self.assertEqual(self.listadas(self.revisar()), [str(self.antes.pk)])
        # As do dia do próximo em diante ficam com ele
        self.assertEqual(self.listadas(self.revisar(proximo)), [str(self.depois.pk)])

    def test_saida_do_dia_do_proximo_salario_e_recusada_na_geracao(self):
        receita(self.a, valor='500.00', data=date(2026, 10, 8))

        resposta = self.gerar(outflows={str(self.depois.pk): self.necessidades})

        self.assertEqual((resposta.status_code, resposta.data), (400, SAIDA_NAO_ENCONTRADA))

    def test_sem_proximo_salario_vai_ate_hoje(self):
        self.assertEqual(self.listadas(self.revisar()), [str(self.antes.pk), str(self.depois.pk)])

    def test_so_um_salario_recebido_na_mesma_conta_depois_do_recebimento_fecha_a_janela(self):
        receita(self.a, valor='500.00', data=date(2026, 10, 8), status='PENDING')       # pendente
        receita(self.a, valor='500.00', data=date(2026, 10, 8), categoria=self.freela)  # não é salário
        receita(self.a, valor='500.00', data=date(2026, 10, 8), conta=self.a.poupanca)  # outra conta
        receita(self.a, valor='500.00', data=date(2026, 10, 8), is_balance_adjustment=True)
        receita(self.a, valor='500.00', data=date(2026, 10, 5))                         # mesmo dia
        receita(self.a, valor='500.00', data=date(2026, 10, 3))                         # anterior

        self.assertEqual(self.listadas(self.revisar()), [str(self.antes.pk), str(self.depois.pk)])

    def test_categoria_de_salario_configurada_fecha_a_janela(self):
        self.salvar_plano(
            [parte('Necessidades', 'FIXED', '200.00', 'ACCOUNT', account=self.a.poupanca)],
            salary_categories=[str(self.a.salario.pk), str(self.freela.pk)],
        )
        receita(self.a, valor='500.00', data=date(2026, 10, 8), categoria=self.freela)

        self.assertEqual(self.listadas(self.revisar()), [str(self.antes.pk)])

    def test_proximo_salario_depois_de_hoje_nao_muda_a_janela(self):
        receita(self.a, valor='500.00', data=date(2026, 10, 20))

        self.assertEqual(self.listadas(self.revisar()), [str(self.antes.pk), str(self.depois.pk)])


class SugestoesTests(SaidasTestCase):
    """SALARIO-65."""

    def test_parte_com_valor_zero_nao_e_sugerida(self):
        despesa = self.despesa(categoria=self.comida)
        transferencia = self.transferencia(self.a.poupanca)

        resposta = self.revisar(adjustments={self.necessidades: '0.00'})

        self.assertEqual(resposta.status_code, 200, resposta.data)
        sugeridas = {s['id']: s['suggested_part_id'] for s in resposta.data['outflows']}
        self.assertEqual(sugeridas, {str(despesa.pk): None, str(transferencia.pk): None})

    def test_parte_zerada_passa_a_sugestao_para_a_proxima_da_mesma_regra(self):
        self.salvar_plano([
            parte('Aluguel', 'FIXED', '3000.00', 'SALARY_ACCOUNT'),
            parte('Necessidades', 'PERCENT', '50.00', 'ACCOUNT', account=self.a.poupanca, reference='ESSENCIAL'),
            parte('Mercado', 'FIXED', '1.00', 'SALARY_ACCOUNT', reference='ESSENCIAL'),
        ])
        aluguel, necessidades, mercado = [p['id'] for p in self.client.get(URL_PLANO).data['parts']]
        despesa = self.despesa(categoria=self.comida)

        resposta = self.revisar(adjustments={aluguel: '2999.00'})

        # Necessidades fica com zero: nada sobra depois dos fixos
        self.assertEqual(
            [(i['name'], i['amount']) for i in resposta.data['items']],
            [('Aluguel', '2999.00'), ('Necessidades', '0.00'), ('Mercado', '1.00')],
        )
        self.assertEqual(resposta.data['outflows'][0]['id'], str(despesa.pk))
        self.assertEqual(resposta.data['outflows'][0]['suggested_part_id'], mercado)

    def sugeridas(self):
        resposta = self.revisar()
        self.assertEqual(resposta.status_code, 200, resposta.data)
        return {s['id']: s for s in resposta.data['outflows']}

    def test_despesa_sugere_a_primeira_parte_com_a_referencia_da_classe(self):
        essencial = self.despesa(categoria=self.comida)
        dispensavel = self.despesa(valor='45.00', categoria=self.lazer)
        sem_classe = self.despesa(
            valor='12.00', categoria=Category.objects.create(user=self.a.usuario, name='Diversos', type='EXPENSE'),
        )

        sugeridas = self.sugeridas()

        self.assertEqual(sugeridas[str(essencial.pk)]['suggested_part_id'], self.necessidades)
        self.assertEqual(sugeridas[str(dispensavel.pk)]['suggested_part_id'], self.diversao)
        self.assertIsNone(sugeridas[str(sem_classe.pk)]['suggested_part_id'])

    def test_subcategoria_herda_a_classe_da_mae(self):
        aluguel = self.despesa(categoria=Category.objects.get(user=self.a.usuario, name='Aluguel'))

        self.assertEqual(self.sugeridas()[str(aluguel.pk)]['suggested_part_id'], self.necessidades)

    def test_transferencia_sugere_a_parte_com_destino_na_conta_de_entrada(self):
        saida = self.transferencia(self.a.poupanca)

        sugerida = self.sugeridas()[str(saida.pk)]

        self.assertEqual(
            (sugerida['suggested_part_id'], sugerida['destination_name'], sugerida['type']),
            (self.necessidades, 'Poupança A', 'TRANSFER_OUT'),
        )

    def test_aporte_sugere_a_parte_com_destino_na_meta(self):
        saida = self.aporte()

        sugerida = self.sugeridas()[str(saida.pk)]

        self.assertEqual((sugerida['suggested_part_id'], sugerida['destination_name']), (self.guardar, 'Viagem A'))

    def test_pagamento_de_fatura_e_transferencia_sem_parte_ficam_sem_sugestao(self):
        fatura = self.despesa(valor='80.00', type='INVOICE_PAYMENT', category=None)
        outra = self.transferencia(Account.objects.create(user=self.a.usuario, name='Outra', type='CHECKING'))

        sugeridas = self.sugeridas()

        self.assertIsNone(sugeridas[str(fatura.pk)]['suggested_part_id'])
        self.assertIsNone(sugeridas[str(fatura.pk)]['category_name'])
        self.assertIsNone(sugeridas[str(outra.pk)]['suggested_part_id'])
        self.assertEqual(sugeridas[str(outra.pk)]['destination_name'], 'Outra')

    def test_cada_saida_traz_data_descricao_valor_tipo_e_categoria(self):
        saida = self.despesa()

        self.assertEqual(self.sugeridas()[str(saida.pk)], {
            'id': str(saida.pk), 'date': '2026-10-06', 'description': 'Mercado do mês', 'amount': '130.00',
            'type': 'EXPENSE', 'destination_name': None, 'category_name': 'Comida',
            'suggested_part_id': self.necessidades, 'part_id': None,
        })


class CalculoComSaidasTests(SaidasTestCase):
    """SALARIO-66, SALARIO-67, SALARIO-72."""

    def test_sem_outflows_lista_as_sugestoes_e_nao_desconta_nada(self):
        saida = self.despesa()

        resposta = self.revisar()

        self.assertEqual(resposta.status_code, 200, resposta.data)
        [listada] = resposta.data['outflows']
        self.assertEqual((listada['id'], listada['suggested_part_id'], listada['part_id']), (str(saida.pk), self.necessidades, None))
        necessidades = self.item(resposta, 'Necessidades')
        self.assertEqual(
            (necessidades['amount'], necessidades['spent'], necessidades['transfer'], necessidades['exceeded']),
            ('200.00', '0.00', '200.00', '0.00'),
        )
        self.assertEqual((resposta.data['total'], resposta.data['free']), ('500.00', '2500.00'))

    def test_despesa_de_130_numa_parte_de_200_deixa_70_para_transferir(self):
        saida = self.despesa()

        resposta = self.revisar(outflows={str(saida.pk): self.necessidades})

        self.assertEqual(resposta.status_code, 200, resposta.data)
        necessidades = self.item(resposta, 'Necessidades')
        self.assertEqual(
            (necessidades['amount'], necessidades['spent'], necessidades['transfer'], necessidades['exceeded'],
             necessidades['generates_transaction']),
            ('200.00', '130.00', '70.00', '0.00', True),
        )
        self.assertEqual(resposta.data['outflows'][0]['part_id'], self.necessidades)
        # Total: 70 + 300; livre: 3.000 - 370 - 130 (SALARIO-72)
        self.assertEqual((resposta.data['total'], resposta.data['free']), ('370.00', '2500.00'))

    def test_saidas_acima_da_parte_deixam_a_parte_sem_transacao_e_mostram_quanto_passou(self):
        primeira = self.despesa()
        segunda = self.despesa(valor='120.00', data=date(2026, 10, 9))

        resposta = self.revisar(outflows={str(primeira.pk): self.necessidades, str(segunda.pk): self.necessidades})

        self.assertEqual(resposta.status_code, 200, resposta.data)
        necessidades = self.item(resposta, 'Necessidades')
        self.assertEqual(
            (necessidades['amount'], necessidades['spent'], necessidades['transfer'], necessidades['exceeded'],
             necessidades['generates_transaction']),
            ('200.00', '250.00', '0.00', '50.00', False),
        )
        # As outras partes não mudam (SALARIO-67)
        self.assertEqual(
            [(i['name'], i['amount'], i['transfer']) for i in resposta.data['items'][1:]],
            [('Diversão', '100.00', '100.00'), ('Guardar', '300.00', '300.00')],
        )
        self.assertEqual((resposta.data['total'], resposta.data['free']), ('300.00', '2450.00'))

    def test_livre_desconta_tambem_as_saidas_das_partes_que_ficam_na_conta(self):
        saida = self.despesa(valor='40.00', categoria=self.lazer)

        resposta = self.revisar(outflows={str(saida.pk): self.diversao})

        diversao = self.item(resposta, 'Diversão')
        self.assertEqual((diversao['spent'], diversao['transfer'], diversao['generates_transaction']), ('40.00', '60.00', False))
        # 3.000 - (200 + 300) - 40
        self.assertEqual((resposta.data['total'], resposta.data['free']), ('500.00', '2460.00'))

    def test_saida_com_null_nao_e_descontada(self):
        saida = self.despesa()

        resposta = self.revisar(outflows={str(saida.pk): None})

        self.assertEqual(resposta.data['outflows'][0]['part_id'], None)
        self.assertEqual((resposta.data['total'], resposta.data['free']), ('500.00', '2500.00'))

    def test_ajuste_muda_o_valor_da_parte_antes_do_desconto(self):
        saida = self.despesa()

        resposta = self.revisar(adjustments={self.necessidades: '150.00'}, outflows={str(saida.pk): self.necessidades})

        necessidades = self.item(resposta, 'Necessidades')
        self.assertEqual(
            (necessidades['amount'], necessidades['adjusted'], necessidades['transfer']), ('150.00', True, '20.00'),
        )


class GeracaoComSaidasTests(SaidasTestCase):
    """SALARIO-66 a SALARIO-69."""

    def test_gera_a_transferencia_com_o_que_falta_e_registra_a_saida_descontada(self):
        saida = self.despesa()

        resposta = self.gerar(outflows={str(saida.pk): self.necessidades})

        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual(
            [(t['part_name'], t['amount']) for t in resposta.data['transactions']],
            [('Necessidades', '70.00'), ('Guardar', '300.00')],
        )
        necessidades = resposta.data['items'][0]
        self.assertEqual(
            (necessidades['amount'], necessidades['spent'], necessidades['transfer'], necessidades['exceeded']),
            ('200.00', '130.00', '70.00', '0.00'),
        )
        self.assertEqual(resposta.data['outflows'], [{
            'id': str(saida.pk), 'date': '2026-10-06', 'description': 'Mercado do mês', 'amount': '130.00',
            'type': 'EXPENSE', 'part_name': 'Necessidades',
        }])
        self.assertEqual((resposta.data['total'], resposta.data['free']), ('370.00', '2500.00'))
        self.assertEqual(self.saldo(self.a.poupanca), Decimal('70.00'))
        [registro] = SaidaDescontada.objects.all()
        self.assertEqual(
            (str(registro.divisao_id), registro.item.nome_da_parte, registro.transacao_id, registro.valor, registro.ativa),
            (resposta.data['id'], 'Necessidades', saida.pk, Decimal('130.00'), True),
        )
        divisao = DivisaoDoSalario.objects.get(pk=resposta.data['id'])
        self.assertEqual((divisao.total, divisao.livre), (Decimal('370.00'), Decimal('2500.00')))
        self.assertEqual(self.client.get(url_da_divisao(resposta.data['id'])).data, resposta.data)

    def test_parte_que_passou_nao_gera_transacao_e_as_outras_seguem(self):
        primeira = self.despesa()
        segunda = self.despesa(valor='120.00', data=date(2026, 10, 9))

        resposta = self.gerar(outflows={str(primeira.pk): self.necessidades, str(segunda.pk): self.necessidades})

        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual([t['part_name'] for t in resposta.data['transactions']], ['Guardar'])
        necessidades = resposta.data['items'][0]
        self.assertEqual(
            (necessidades['generates_transaction'], necessidades['transfer'], necessidades['exceeded']),
            (False, '0.00', '50.00'),
        )
        self.assertEqual(self.saldo(self.a.poupanca), Decimal('0.00'))
        self.assertEqual(SaidaDescontada.objects.filter(ativa=True).count(), 2)

    def test_saida_descontada_numa_divisao_ativa_nao_entra_em_outra(self):
        # Outro salário no mesmo dia e na mesma conta: as janelas dos dois se cruzam (SALARIO-75)
        outro_salario = receita(self.a, valor='1000.00', data=date(2026, 10, 5))
        saida = self.despesa()
        self.assertEqual(self.gerar(outflows={str(saida.pk): self.necessidades}).status_code, 201)

        self.assertEqual(self.listadas(self.revisar(outro_salario)), [])
        resposta = self.gerar(outro_salario, outflows={str(saida.pk): self.necessidades})

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data, SAIDA_NAO_ENCONTRADA)
        self.assertFalse(DivisaoDoSalario.objects.filter(recebimento_ref=outro_salario.pk).exists())

    def test_restricao_unica_recusa_a_mesma_saida_descontada_ao_mesmo_tempo(self):
        # Simula a corrida: a lista do segundo pedido foi lida antes de o
        # primeiro gravar a saída descontada
        # Outro salário no mesmo dia e na mesma conta: as janelas dos dois se cruzam (SALARIO-75)
        outro_salario = receita(self.a, valor='1000.00', data=date(2026, 10, 5))
        saida = self.despesa()
        self.assertEqual(self.gerar(outflows={str(saida.pk): self.necessidades}).status_code, 201)
        transacoes = Transaction.objects.count()

        with mock.patch('salario.saidas.elegiveis', return_value=Transaction.objects.filter(pk=saida.pk)) as lista:
            resposta = self.gerar(outro_salario, outflows={str(saida.pk): self.necessidades})

        # A saída passou pela lista; a recusa veio da restrição única
        lista.assert_called_once()
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data, SAIDA_NAO_ENCONTRADA)
        self.assertFalse(DivisaoDoSalario.objects.filter(recebimento_ref=outro_salario.pk).exists())
        self.assertEqual(Transaction.objects.count(), transacoes)
        self.assertEqual(SaidaDescontada.objects.count(), 1)

    def test_ids_invalidos_sao_recusados_sem_gerar_nada(self):
        pendente = self.despesa(status='PENDING')
        saida = self.despesa()
        casos = (
            ({str(uuid.uuid4()): self.necessidades}, SAIDA_NAO_ENCONTRADA),
            ({str(pendente.pk): self.necessidades}, SAIDA_NAO_ENCONTRADA),
            ({'nao-e-um-id': self.necessidades}, SAIDA_NAO_ENCONTRADA),
            ({str(saida.pk): str(uuid.uuid4())}, PARTE_NAO_ENCONTRADA),
            ({str(saida.pk): '123456789'}, PARTE_NAO_ENCONTRADA),
        )
        for outflows, esperado in casos:
            for rota in (self.revisar, self.gerar):
                with self.subTest(outflows=outflows, rota=rota.__name__):
                    resposta = rota(outflows=outflows)
                    self.assertEqual(resposta.status_code, 400)
                    # Na geração, a parte fora do plano é um plano salvo de novo (SALARIO-74)
                    if rota == self.gerar and esperado == PARTE_NAO_ENCONTRADA:
                        esperado = DIVISAO_MUDOU
                    self.assertEqual(resposta.data, esperado)
        self.assertFalse(DivisaoDoSalario.objects.exists())
        self.assertFalse(SaidaDescontada.objects.exists())

    def test_parte_de_outro_usuario_e_recusada(self):
        saida = self.despesa()
        self.client.force_authenticate(user=self.b.usuario)
        self.salvar_plano([parte('Reserva', 'FIXED', '10.00', 'ACCOUNT', account=self.b.poupanca)])
        parte_de_b = self.client.get(URL_PLANO).data['parts'][0]['id']
        self.client.force_authenticate(user=self.a.usuario)

        for rota, esperado in ((self.revisar, PARTE_NAO_ENCONTRADA), (self.gerar, DIVISAO_MUDOU)):
            with self.subTest(rota=rota.__name__):
                resposta = rota(outflows={str(saida.pk): parte_de_b})

                self.assertEqual((resposta.status_code, resposta.data), (400, esperado))

    def test_repeticao_da_mesma_chave_devolve_a_mesma_resposta(self):
        saida = self.despesa()
        chave = str(uuid.uuid4())

        primeira = self.gerar(idempotency_key=chave, outflows={str(saida.pk): self.necessidades})
        segunda = self.gerar(idempotency_key=chave, outflows={str(saida.pk): None})

        self.assertEqual((primeira.status_code, segunda.status_code), (201, 201))
        self.assertEqual(segunda.data, primeira.data)
        self.assertEqual(SaidaDescontada.objects.count(), 1)
        self.assertEqual(DivisaoDoSalario.objects.count(), 1)

    def test_logs_da_geracao_nao_levam_valores_nem_descricoes(self):
        saida = self.despesa(description='Farmácia do bairro', valor='137.45')

        with self.assertLogs('salario', level='INFO') as logs:
            self.assertEqual(self.gerar(outflows={str(saida.pk): self.necessidades}).status_code, 201)

        texto = '\n'.join(logs.output)
        for dado in ('Farmácia', '137.45', '62.55', 'Necessidades', 'Poupança'):
            self.assertNotIn(dado, texto)


class DivisaoSemTransacoesTests(SaidasTestCase):
    """SALARIO-73."""

    def test_saidas_que_cobrem_todas_as_partes_gravam_a_divisao_sem_transacoes(self):
        mercado = self.despesa(valor='200.00')
        aporte = self.aporte(valor='300.00')
        transacoes = Transaction.objects.count()

        resposta = self.gerar(outflows={str(mercado.pk): self.necessidades, str(aporte.pk): self.guardar})

        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual(resposta.data['transactions'], [])
        self.assertEqual([i['generates_transaction'] for i in resposta.data['items']], [False, False, False])
        self.assertEqual(
            [(i['name'], i['amount'], i['spent'], i['transfer']) for i in resposta.data['items']],
            [
                ('Necessidades', '200.00', '200.00', '0.00'),
                ('Diversão', '100.00', '0.00', '100.00'),
                ('Guardar', '300.00', '300.00', '0.00'),
            ],
        )
        self.assertEqual((resposta.data['total'], resposta.data['free']), ('0.00', '2500.00'))
        self.assertEqual(
            [(s['id'], s['part_name']) for s in resposta.data['outflows']],
            [(str(mercado.pk), 'Necessidades'), (str(aporte.pk), 'Guardar')],
        )
        self.assertEqual(Transaction.objects.count(), transacoes)
        self.assertEqual(SaidaDescontada.objects.filter(ativa=True).count(), 2)
        # O salário sai da lista dos que faltam dividir
        with hoje_em(2026, 10, 10):
            pendentes = self.client.get(URL_PENDENTES).data
        self.assertNotIn(str(self.salario.pk), [p['id'] for p in pendentes])

    def test_desfazer_a_divisao_sem_transacoes_libera_as_saidas_e_o_salario(self):
        mercado = self.despesa(valor='200.00')
        aporte = self.aporte(valor='300.00')
        gerada = self.gerar(outflows={str(mercado.pk): self.necessidades, str(aporte.pk): self.guardar})
        self.assertEqual(gerada.status_code, 201, gerada.data)

        with hoje_em(2026, 10, 11):
            resposta = self.client.post(url_do_desfazer(gerada.data['id']), format='json')
            pendentes = self.client.get(URL_PENDENTES).data

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertIsNotNone(resposta.data['undone_at'])
        self.assertFalse(SaidaDescontada.objects.filter(ativa=True).exists())
        self.assertIn(str(self.salario.pk), [p['id'] for p in pendentes])
        self.assertEqual(self.listadas(self.revisar(dia=(2026, 10, 11))), [str(mercado.pk), str(aporte.pk)])

    def test_sem_transacao_e_sem_saida_descontada_continua_recusada(self):
        mercado = self.despesa(valor='200.00')
        self.salvar_plano([parte('Diversão', 'FIXED', '100.00', 'SALARY_ACCOUNT')])

        for outflows in ({}, {str(mercado.pk): None}):
            with self.subTest(outflows=outflows):
                resposta = self.gerar(outflows=outflows)

                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.data, {'detail': 'Nenhuma parte do plano gera transação.', 'code': 'invalid'})
        self.assertFalse(DivisaoDoSalario.objects.exists())


class SaidasMudadasTests(SaidasTestCase):
    """SALARIO-77."""

    def setUp(self):
        super().setUp()
        self.mercado = self.despesa(valor='50.00')
        self.farmacia = self.despesa(valor='30.00', description='Farmácia')
        self.lanche = self.despesa(valor='20.00', categoria=self.lazer, description='Lanche')
        self.gerada = self.gerar(outflows={
            str(self.mercado.pk): self.necessidades, str(self.farmacia.pk): self.necessidades,
            str(self.lanche.pk): self.diversao,
        })
        self.assertEqual(self.gerada.status_code, 201, self.gerada.data)

    def mudadas(self):
        """`outflows_changed` no detalhe e na lista das divisões que ainda podem ser desfeitas."""
        with hoje_em(2026, 10, 11):
            detalhe = self.client.get(url_da_divisao(self.gerada.data['id'])).data
            [listada] = self.client.get(URL_DIVISOES, {'undoable': 'true'}).data
        self.assertEqual(listada['outflows_changed'], detalhe['outflows_changed'])
        return detalhe['outflows_changed']

    def test_divisao_recem_gerada_nao_tem_saida_mudada(self):
        self.assertEqual(self.gerada.data['outflows_changed'], 0)
        self.assertEqual(self.mudadas(), 0)

    def test_conta_as_saidas_excluidas_com_outro_valor_ou_que_deixaram_de_valer(self):
        casos = (
            ('excluída', lambda: Transaction.objects.get(pk=self.mercado.pk).delete()),
            ('outro valor', lambda: Transaction.objects.filter(pk=self.farmacia.pk).update(amount=Decimal('31.00'))),
            ('pendente', lambda: Transaction.objects.filter(pk=self.lanche.pk).update(status='PENDING')),
        )
        for quantas, (nome, mudar) in enumerate(casos, start=1):
            with self.subTest(nome):
                mudar()

                self.assertEqual(self.mudadas(), quantas)

    def test_saida_movida_para_outra_conta_conta_como_mudada(self):
        Transaction.objects.filter(pk=self.mercado.pk).update(account=self.a.poupanca)

        self.assertEqual(self.mudadas(), 1)

    def test_saida_editada_sem_mudar_valor_nem_conta_nao_conta(self):
        Transaction.objects.filter(pk=self.mercado.pk).update(description='Mercado da esquina', date=date(2026, 10, 7))

        self.assertEqual(self.mudadas(), 0)

    def test_desfazer_com_saidas_mudadas_libera_todas_e_a_desfeita_fica_com_zero(self):
        Transaction.objects.get(pk=self.mercado.pk).delete()
        Transaction.objects.filter(pk=self.farmacia.pk).update(amount=Decimal('31.00'))

        with hoje_em(2026, 10, 11):
            resposta = self.client.post(url_do_desfazer(self.gerada.data['id']), format='json')

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(resposta.data['outflows_changed'], 0)
        self.assertFalse(SaidaDescontada.objects.filter(ativa=True).exists())
        self.assertEqual(
            self.listadas(self.revisar(dia=(2026, 10, 11))), [str(self.farmacia.pk), str(self.lanche.pk)],
        )


class DesfazerComSaidasTests(SaidasTestCase):
    """SALARIO-70."""

    def test_desfazer_libera_as_saidas_e_devolve_saldos_e_metas(self):
        despesa = self.despesa()
        aporte = self.aporte(valor='100.00')
        gerada = self.gerar(outflows={str(despesa.pk): self.necessidades, str(aporte.pk): self.guardar})
        self.assertEqual(gerada.status_code, 201, gerada.data)
        self.assertEqual(
            [(t['part_name'], t['amount']) for t in gerada.data['transactions']],
            [('Necessidades', '70.00'), ('Guardar', '200.00')],
        )
        self.assertEqual(self.valor_da_meta(self.a.viagem), Decimal('300.00'))

        with hoje_em(2026, 10, 11):
            resposta = self.client.post(url_do_desfazer(gerada.data['id']), format='json')

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(SaidaDescontada.objects.filter(ativa=True).count(), 0)
        self.assertEqual(SaidaDescontada.objects.count(), 2)
        self.assertEqual(self.valor_da_meta(self.a.viagem), Decimal('100.00'))
        self.assertEqual(self.saldo(self.a.poupanca), Decimal('0.00'))
        # A divisão desfeita continua mostrando o que foi descontado
        self.assertEqual(len(resposta.data['outflows']), 2)
        self.assertEqual(
            self.listadas(self.revisar(dia=(2026, 10, 11))), [str(despesa.pk), str(aporte.pk)],
        )
        nova = self.gerar(dia=(2026, 10, 11), outflows={str(despesa.pk): self.necessidades})
        self.assertEqual(nova.status_code, 201, nova.data)


class ComprasNoCartaoTests(SaidasTestCase):
    """SALARIO-64, SALARIO-65 e SALARIO-70 para as compras no cartão pagas pela conta do salário."""

    def setUp(self):
        super().setUp()
        self.cartao = CreditCard.objects.create(
            user=self.a.usuario, name='Cartão A', limit=Decimal('5000.00'), closing_day=8, due_day=15,
            account=self.a.conta,
        )

    def compra_paga(self, valor='130.00', pagamento=date(2026, 10, 7), conta=None, mes=10, categoria=None):
        """Uma compra pendente na fatura de `mes`/2026, paga inteira em `pagamento` pela `conta`."""
        fatura = obter_fatura(self.cartao, mes, 2026)
        compra = Transaction.objects.create(
            user=self.a.usuario, type='CREDIT_CARD', status='PENDING', account=self.a.conta,
            credit_card=self.cartao, invoice=fatura, category=categoria or self.comida,
            description='Farmácia', amount=Decimal(valor), date=fatura.due_date,
            purchase_date=date(2026, mes - 1, 20),
        )
        faturas.pagar(self.a.usuario, fatura, conta or self.a.conta, Decimal(valor), pagamento)
        compra.refresh_from_db()
        return compra

    def test_compra_paga_pela_conta_do_salario_entra_pela_data_do_pagamento_com_sugestao_da_classe(self):
        antes = self.despesa(data=date(2026, 10, 6))
        compra = self.compra_paga()
        depois = self.despesa(valor='20.00', data=date(2026, 10, 8))
        self.assertEqual((compra.date, compra.status), (date(2026, 10, 15), 'COMPLETED'))

        resposta = self.revisar()

        self.assertEqual(self.listadas(resposta), [str(antes.pk), str(compra.pk), str(depois.pk)])
        self.assertEqual(resposta.data['outflows'][1], {
            'id': str(compra.pk), 'date': '2026-10-07', 'description': 'Farmácia', 'amount': '130.00',
            'type': 'CREDIT_CARD', 'destination_name': 'Cartão A', 'category_name': 'Comida',
            'suggested_part_id': self.necessidades, 'part_id': None,
        })

    def test_compra_dispensavel_sugere_a_parte_da_classe(self):
        compra = self.compra_paga(categoria=self.lazer)

        [listada] = self.revisar().data['outflows']

        self.assertEqual((listada['id'], listada['suggested_part_id']), (str(compra.pk), self.diversao))

    def test_compra_paga_por_outra_conta_antes_do_recebimento_ou_depois_de_hoje_fica_fora(self):
        self.compra_paga(conta=self.a.poupanca)                       # outra conta
        self.compra_paga(mes=11, pagamento=date(2026, 10, 4))         # antes do recebimento
        self.compra_paga(mes=12, pagamento=date(2026, 10, 11))        # depois de hoje
        Transaction.objects.create(                                   # não paga
            user=self.a.usuario, type='CREDIT_CARD', status='PENDING', account=self.a.conta,
            credit_card=self.cartao, invoice=obter_fatura(self.cartao, 1, 2027), category=self.comida,
            description='Pendente', amount=Decimal('10.00'), date=date(2026, 10, 6),
        )

        self.assertEqual(self.listadas(self.revisar()), [])

    def test_compra_de_pagamento_estornado_sai_da_lista(self):
        compra = self.compra_paga()
        self.assertEqual(self.listadas(self.revisar()), [str(compra.pk)])

        faturas.estornar(self.a.usuario, compra.invoice)

        compra.refresh_from_db()
        self.assertEqual((compra.status, compra.payment_date), ('PENDING', None))
        self.assertEqual(self.listadas(self.revisar()), [])

    def test_compra_descontada_com_o_pagamento_estornado_conta_como_mudada(self):
        compra = self.compra_paga()
        gerada = self.gerar(outflows={str(compra.pk): self.necessidades})
        self.assertEqual(gerada.data['outflows_changed'], 0)

        faturas.estornar(self.a.usuario, compra.invoice)

        with hoje_em(2026, 10, 10):
            detalhe = self.client.get(url_da_divisao(gerada.data['id']))
        self.assertEqual(detalhe.data['outflows_changed'], 1)

    def test_compra_descontada_na_geracao_e_liberada_ao_desfazer(self):
        compra = self.compra_paga()

        gerada = self.gerar(outflows={str(compra.pk): self.necessidades})

        self.assertEqual(gerada.status_code, 201, gerada.data)
        self.assertEqual(
            [(t['part_name'], t['amount']) for t in gerada.data['transactions']],
            [('Necessidades', '70.00'), ('Guardar', '300.00')],
        )
        self.assertEqual(gerada.data['outflows'], [{
            'id': str(compra.pk), 'date': '2026-10-07', 'description': 'Farmácia', 'amount': '130.00',
            'type': 'CREDIT_CARD', 'part_name': 'Necessidades',
        }])
        [registro] = SaidaDescontada.objects.filter(ativa=True)
        self.assertEqual((registro.transacao_id, registro.valor), (compra.pk, Decimal('130.00')))
        # Outro salário no mesmo dia e na mesma conta: as janelas dos dois se cruzam (SALARIO-75)
        outro_salario = receita(self.a, valor='1000.00', data=date(2026, 10, 5))
        self.assertEqual(self.listadas(self.revisar(outro_salario)), [])

        with hoje_em(2026, 10, 11):
            desfeita = self.client.post(url_do_desfazer(gerada.data['id']), format='json')

        self.assertEqual(desfeita.status_code, 200, desfeita.data)
        self.assertFalse(SaidaDescontada.objects.filter(ativa=True).exists())
        self.assertEqual(self.listadas(self.revisar(dia=(2026, 10, 11))), [str(compra.pk)])

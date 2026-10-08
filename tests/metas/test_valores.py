"""
Valor derivado das metas e saldo livre do cofrinho (META-01, META-02).

O valor é aportes menos resgates, contando os registros sem transação e os
que têm todas as transações ligadas efetivadas (AD-002).
"""
from decimal import Decimal

from accounts.models import Account
from goals.models import Goal
from goals.valores import calcular, recalcular, saldo_livre
from transactions.models import Transaction
from tests.metas.base import DIA, MetasTestCase, registrar, transferir


class ValorDaMetaTests(MetasTestCase):

    def test_soma_aportes_e_subtrai_resgates_sem_transacao(self):
        registrar(self.a.meta, 'DEPOSIT', '300.00')
        registrar(self.a.meta, 'DEPOSIT', '150.50')
        registrar(self.a.meta, 'WITHDRAWAL', '100.25')

        self.assertEqual(calcular(self.a.meta), Decimal('350.25'))

    def test_conta_a_transferencia_efetivada_e_ignora_a_pendente(self):
        efetivada = transferir(self.a.conta, self.a.cofrinho, '500.00')
        pendente = transferir(self.a.conta, self.a.cofrinho, '200.00')
        Transaction.objects.filter(transfer_id=pendente[0]).update(status='PENDING')
        registrar(self.a.meta, 'DEPOSIT', '500.00', conta=self.a.conta, transferencia=efetivada)
        registrar(self.a.meta, 'DEPOSIT', '200.00', conta=self.a.conta, transferencia=pendente)

        self.assertEqual(calcular(self.a.meta), Decimal('500.00'))

    def test_registro_conta_so_com_todas_as_pernas_efetivadas(self):
        transferencia = transferir(self.a.conta, self.a.cofrinho, '500.00')
        registrar(self.a.meta, 'DEPOSIT', '500.00', conta=self.a.conta, transferencia=transferencia)
        # Só a perna de entrada pendente já tira o registro da conta
        Transaction.objects.filter(pk=transferencia[2].pk).update(status='PENDING')

        self.assertEqual(calcular(self.a.meta), Decimal('0.00'))

    def test_registro_antigo_e_resolvido_pelo_transfer_id(self):
        efetivada = transferir(self.a.conta, self.a.cofrinho, '400.00')
        pendente = transferir(self.a.conta, self.a.cofrinho, '70.00')
        Transaction.objects.filter(transfer_id=pendente[0]).update(status='PENDING')
        # Como antes da feature: só o `transaction_id`, sem as pernas
        registrar(self.a.meta, 'DEPOSIT', '400.00', conta=self.a.conta, transaction_id=efetivada[0])
        registrar(self.a.meta, 'DEPOSIT', '70.00', conta=self.a.conta, transaction_id=pendente[0])

        self.assertEqual(calcular(self.a.meta), Decimal('400.00'))

    def test_registro_antigo_do_rateio_e_resolvido_pelo_id_da_transacao(self):
        receita = Transaction.objects.create(
            user=self.a.usuario, account=self.a.cofrinho, type='INCOME', status='PENDING',
            description='Guardado', amount=Decimal('80.00'), date=DIA,
        )
        registrar(self.a.meta, 'DEPOSIT', '80.00', transaction_id=receita.pk)
        registrar(self.a.meta, 'DEPOSIT', '20.00')

        self.assertEqual(calcular(self.a.meta), Decimal('20.00'))
        Transaction.objects.filter(pk=receita.pk).update(status='COMPLETED')
        self.assertEqual(calcular(self.a.meta), Decimal('100.00'))


class RecalcularTests(MetasTestCase):

    def test_grava_o_valor_e_devolve_as_metas_negativas(self):
        outra = Goal.objects.create(
            user=self.a.usuario, name='Carro', target_amount=Decimal('100.00'), account=self.a.cofrinho,
        )
        registrar(self.a.meta, 'DEPOSIT', '300.00')
        registrar(outra, 'DEPOSIT', '10.00')
        registrar(outra, 'WITHDRAWAL', '60.00')
        Goal.objects.filter(pk=self.a.meta.pk).update(current_amount=Decimal('999.00'))

        negativas = recalcular(self.a.meta.pk, outra.pk, None)

        self.assertEqual(self.valor(self.a.meta), Decimal('300.00'))
        self.assertEqual(self.valor(outra), Decimal('-50.00'))
        self.assertEqual([(m.pk, m.current_amount) for m in negativas], [(outra.pk, Decimal('-50.00'))])

    def test_sem_metas_negativas_devolve_lista_vazia(self):
        registrar(self.a.meta, 'DEPOSIT', '10.00')

        self.assertEqual(recalcular(self.a.meta.pk), [])
        self.assertEqual(self.valor(self.a.meta), Decimal('10.00'))


class SaldoLivreTests(MetasTestCase):

    def test_saldo_do_cofrinho_menos_todas_as_metas_inclusive_arquivadas(self):
        arquivada = Goal.objects.create(
            user=self.a.usuario, name='Antiga', target_amount=Decimal('100.00'),
            account=self.a.cofrinho, is_active=False,
        )
        Account.objects.filter(pk=self.a.cofrinho.pk).update(balance=Decimal('1000.00'))
        Goal.objects.filter(pk=self.a.meta.pk).update(current_amount=Decimal('600.00'))
        Goal.objects.filter(pk=arquivada.pk).update(current_amount=Decimal('150.00'))
        # Meta de outra conta não entra
        Goal.objects.filter(pk=self.b.meta.pk).update(current_amount=Decimal('80.00'))

        self.assertEqual(saldo_livre(self.recarregar(self.a.cofrinho)), Decimal('250.00'))

    def test_saldo_livre_pode_ficar_negativo(self):
        Account.objects.filter(pk=self.a.cofrinho.pk).update(balance=Decimal('100.00'))
        Goal.objects.filter(pk=self.a.meta.pk).update(current_amount=Decimal('300.00'))

        self.assertEqual(saldo_livre(self.recarregar(self.a.cofrinho)), Decimal('-200.00'))

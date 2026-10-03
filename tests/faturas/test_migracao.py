"""
Migração de correção das faturas (FATURA-39 a FATURA-41).

Os dados são gravados pelo ORM como os bugs antigos deixaram: compra no
cartão sem fatura (FIN-17), duas parcelas pendentes na mesma fatura (FIN-06)
e total gravado desatualizado (FIN-07). O cartão de A fecha no dia 30 e
vence no dia 7: a fatura que vence em 07/04 fecha em 30/03.
"""
import importlib
from datetime import date
from decimal import Decimal

from django.apps import apps
from django.db import connection, migrations
from django.db.migrations.executor import MigrationExecutor

from accounts.faturas import obter_fatura
from accounts.models import CreditCardInvoice
from transactions.models import Transaction
from tests.faturas.base import FaturasTestCase

# O nome do módulo começa com dígito, por isso o import_module
migracao = importlib.import_module('accounts.migrations.0006_corrige_faturas')


class MigracaoDeCorrecaoDasFaturasTests(FaturasTestCase):

    def setUp(self):
        super().setUp()
        self.cartao_ = self.cartao(30, 7)

    def corrigir(self, registro=apps):
        migracao.corrigir(registro, None)

    def ler(self, compra):
        return Transaction.objects.get(pk=compra.pk)

    def mes(self, compra):
        fatura = self.ler(compra).invoice
        return (fatura.month, fatura.year)

    def parcelada(self, meses, status=None):
        """
        Compra em `len(meses)` parcelas, a parcela n na fatura de `meses[n-1]`
        (mês do vencimento em 2026), com `date` no vencimento dela.
        """
        status = status or {}
        parcelas, raiz = [], None
        for n, mes in enumerate(meses, start=1):
            fatura = obter_fatura(self.cartao_, mes, 2026)
            parcela = self.compra(
                self.cartao_, fatura, '25.00', status=status.get(n, 'PENDING'),
                description=f'Loja ({n}/{len(meses)})', purchase_date=date(2026, 1, 30),
                is_installment=True, installment_number=n, installment_total=len(meses),
                parent_transaction=raiz,
            )
            raiz = raiz or parcela
            parcelas.append(parcela)
        return parcelas

    def test_depende_do_registro_do_pagamento_e_da_data_da_compra(self):
        self.assertEqual(set(migracao.Migration.dependencies), {
            ('accounts', '0005_pagamentodefatura_itemdepagamento'),
            ('transactions', '0009_transaction_purchase_date'),
        })
        [operacao] = migracao.Migration.operations
        self.assertIsInstance(operacao, migrations.RunPython)
        self.assertIs(operacao.code, migracao.corrigir)
        self.assertIs(operacao.reverse_code, migrations.RunPython.noop)

    def test_compra_sem_fatura_ganha_fatura_data_da_compra_e_vencimento(self):
        # 15/03 é antes do fechamento de 30/03: fatura que vence em 07/04
        sem_fatura = self.compra(self.cartao_, None, '80.00', date=date(2026, 3, 15))
        # 31/03 é depois do fechamento: fatura de 07/05, que está paga; vai para a de 07/06
        maio = obter_fatura(self.cartao_, 5, 2026)
        CreditCardInvoice.objects.filter(pk=maio.pk).update(status='PAID')
        pendente_em_paga = self.compra(self.cartao_, None, '20.00', date=date(2026, 3, 31))

        self.corrigir()

        lida = self.ler(sem_fatura)
        abril = self.fatura(self.cartao_, 4, 2026)
        self.assertEqual(
            (lida.invoice_id, lida.purchase_date, lida.date),
            (abril.id, date(2026, 3, 15), date(2026, 4, 7)),
        )
        lida = self.ler(pendente_em_paga)
        junho = self.fatura(self.cartao_, 6, 2026)
        self.assertEqual(
            (lida.invoice_id, lida.purchase_date, lida.date),
            (junho.id, date(2026, 3, 31), date(2026, 6, 7)),
        )
        self.assertEqual(self.total(abril), Decimal('80.00'))
        self.assertEqual(self.total(junho), Decimal('20.00'))

    def test_parcelas_pendentes_repetidas_ficam_uma_por_fatura_consecutiva(self):
        # Como FIN-06 deixava: a 2ª e a 3ª na fatura de abril, nenhuma em junho
        parcelas = self.parcelada([3, 4, 4, 5])

        self.corrigir()

        self.assertEqual([self.mes(p) for p in parcelas], [(3, 2026), (4, 2026), (5, 2026), (6, 2026)])
        self.assertEqual([self.ler(p).date for p in parcelas],
                         [date(2026, 3, 7), date(2026, 4, 7), date(2026, 5, 7), date(2026, 6, 7)])
        for mes in (3, 4, 5, 6):
            self.assertEqual(self.total(self.fatura(self.cartao_, mes, 2026)), Decimal('25.00'))

    def test_parcelas_pagas_nao_se_movem_e_faturas_pagas_sao_puladas(self):
        # A 1ª, paga, fica em março; a 2ª e a 3ª repetem abril; maio está paga
        parcelas = self.parcelada([3, 4, 4, 6], status={1: 'COMPLETED'})
        maio = obter_fatura(self.cartao_, 5, 2026)
        CreditCardInvoice.objects.filter(pk=maio.pk).update(status='PAID')

        self.corrigir()

        self.assertEqual([self.mes(p) for p in parcelas], [(3, 2026), (4, 2026), (6, 2026), (7, 2026)])
        self.assertEqual(self.ler(parcelas[0]).status, 'COMPLETED')
        self.assertEqual(self.ler(parcelas[0]).date, date(2026, 3, 7))

    def test_compra_sem_repeticao_nao_muda(self):
        parcelas = self.parcelada([3, 4, 6])

        self.corrigir()

        self.assertEqual([self.mes(p) for p in parcelas], [(3, 2026), (4, 2026), (6, 2026)])

    def test_restante_antigo_com_o_mesmo_numero_fica_onde_esta(self):
        """O restante de um pagamento parcial antigo não conta como parcela repetida."""
        parcelas = self.parcelada([3, 4, 5], status={1: 'COMPLETED'})
        restante = self.compra(
            self.cartao_, self.fatura(self.cartao_, 4, 2026), '10.00', description='Loja (1/3) (Restante)',
            is_installment=True, installment_number=1, installment_total=3,
            parent_transaction=parcelas[0],
        )

        self.corrigir()

        self.assertEqual([self.mes(p) for p in parcelas], [(3, 2026), (4, 2026), (5, 2026)])
        self.assertEqual(self.mes(restante), (4, 2026))

    def test_total_desatualizado_volta_a_soma_das_compras_do_dono(self):
        abril = obter_fatura(self.cartao_, 4, 2026)
        self.compra(self.cartao_, abril, '30.00')
        self.compra(self.cartao_, abril, '45.50', status='COMPLETED')
        # Compra de B gravada à força na fatura de A não entra (ISOL-14)
        self.compra(self.cartao_, abril, '999.00', usuario=self.b.usuario)
        vazia = obter_fatura(self.cartao_, 5, 2026)
        CreditCardInvoice.objects.filter(pk__in=[abril.pk, vazia.pk]).update(total_amount=Decimal('12345.67'))

        self.corrigir()

        self.assertEqual(self.total(abril), Decimal('75.50'))
        self.assertEqual(self.total(vazia), Decimal('0.00'))

    def test_banco_sem_compras_nem_faturas_nao_muda_nada(self):
        Transaction.objects.all().delete()
        CreditCardInvoice.objects.all().delete()

        self.corrigir()

        self.assertFalse(CreditCardInvoice.objects.exists())
        self.assertFalse(Transaction.objects.exists())

    def test_funciona_com_o_registro_historico_de_models(self):
        sem_fatura = self.compra(self.cartao_, None, '80.00', date=date(2026, 3, 15))
        parcelas = self.parcelada([3, 4, 4])
        estado = MigrationExecutor(connection).loader.project_state(('accounts', '0006_corrige_faturas'))

        self.corrigir(estado.apps)

        self.assertEqual(self.mes(sem_fatura), (4, 2026))
        self.assertEqual([self.mes(p) for p in parcelas], [(3, 2026), (4, 2026), (5, 2026)])
        self.assertEqual(self.total(self.fatura(self.cartao_, 4, 2026)), Decimal('105.00'))

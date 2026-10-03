"""
Registro do pagamento (AD-040, FATURA-30): a chave de idempotência não se
repete para o mesmo usuário, usuários diferentes podem usar a mesma chave e
pagamentos sem chave convivem.
"""
import uuid
from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction

from accounts.faturas import obter_fatura
from accounts.models import PagamentoDeFatura
from tests.faturas.base import FaturasTestCase


class RegistroDoPagamentoTests(FaturasTestCase):

    def setUp(self):
        super().setUp()
        self.fatura_a = obter_fatura(self.cartao(10, 20), 9, 2026)
        self.fatura_b = obter_fatura(self.cartao(10, 20, usuario=self.b.usuario), 9, 2026)

    def registrar(self, dono, fatura, conta, chave):
        return PagamentoDeFatura.objects.create(
            user=dono, fatura=fatura, conta=conta, valor=Decimal('100.00'),
            data=date(2026, 9, 20), chave=chave,
        )

    def test_a_mesma_chave_nao_se_repete_para_o_mesmo_usuario(self):
        chave = uuid.uuid4()
        self.registrar(self.a.usuario, self.fatura_a, self.a.conta, chave)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.registrar(self.a.usuario, self.fatura_a, self.a.conta, chave)

        self.assertEqual(PagamentoDeFatura.objects.filter(chave=chave).count(), 1)

    def test_usuarios_diferentes_podem_usar_a_mesma_chave(self):
        chave = uuid.uuid4()
        self.registrar(self.a.usuario, self.fatura_a, self.a.conta, chave)
        self.registrar(self.b.usuario, self.fatura_b, self.b.conta, chave)

        self.assertEqual(PagamentoDeFatura.objects.filter(chave=chave).count(), 2)

    def test_pagamentos_sem_chave_convivem(self):
        self.registrar(self.a.usuario, self.fatura_a, self.a.conta, None)
        self.registrar(self.a.usuario, self.fatura_a, self.a.conta, None)

        self.assertEqual(PagamentoDeFatura.objects.filter(user=self.a.usuario, chave=None).count(), 2)

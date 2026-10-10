"""
Modelos da gestão do salário (SALARIO-17, AD-053): a exclusão definitiva e a
limpeza levam o plano e as divisões, e o banco recusa a mesma chave e uma
segunda divisão ativa do mesmo recebimento.
"""
import uuid
from datetime import date
from decimal import Decimal
from unittest import mock

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import Account
from api.exclusao import excluir_definitivamente
from api.limpeza import limpar_dados
from api.models import RegistroDeExclusao, User
from salario.models import DivisaoDoSalario, GestaoDoSalario, ItemDaDivisao, ParteDoPlano
from tests.lgpd.test_exclusao_definitiva import DESTRUIR, OK, criar_conta_completa, pedir_exclusao
from transactions.models import Transaction


def dados_do_salario(usuario):
    """Quantas linhas do salário o usuário tem, por modelo."""
    return {
        'gestao': GestaoDoSalario.objects.filter(user=usuario).count(),
        'partes': ParteDoPlano.objects.filter(gestao__user=usuario).count(),
        'divisoes': DivisaoDoSalario.objects.filter(user=usuario).count(),
        'itens': ItemDaDivisao.objects.filter(divisao__user=usuario).count(),
    }


SEM_NADA = {'gestao': 0, 'partes': 0, 'divisoes': 0, 'itens': 0}
COM_TUDO = {'gestao': 1, 'partes': 1, 'divisoes': 1, 'itens': 1}


@mock.patch(DESTRUIR, return_value=OK)
class ExclusaoELimpezaTests(TestCase):

    def setUp(self):
        self.ana = criar_conta_completa()
        self.bia = criar_conta_completa('bia@teste.fluxar')

    def test_exclusao_definitiva_apaga_o_plano_e_as_divisoes(self, destruir):
        self.assertEqual(dados_do_salario(self.ana), COM_TUDO)
        ana_id = pedir_exclusao(self.ana).pk

        excluir_definitivamente(self.ana, RegistroDeExclusao.ROTINA)

        self.assertFalse(GestaoDoSalario.objects.filter(user_id=ana_id).exists())
        self.assertFalse(DivisaoDoSalario.objects.filter(user_id=ana_id).exists())
        self.assertFalse(ParteDoPlano.objects.filter(gestao__user_id=ana_id).exists())
        self.assertFalse(ItemDaDivisao.objects.filter(divisao__user_id=ana_id).exists())
        # Os da outra conta continuam
        self.assertEqual(dados_do_salario(self.bia), COM_TUDO)

    def test_limpeza_apaga_a_gestao_e_as_divisoes(self, destruir):
        admin = User.objects.create_user(email='admin@teste.fluxar', password='senha-de-teste-123', role='ADMIN')

        limpar_dados(self.ana, admin)

        self.assertEqual(dados_do_salario(self.ana), SEM_NADA)
        self.assertEqual(dados_do_salario(self.bia), COM_TUDO)

    def test_cadastro_novo_nasce_sem_plano_e_sem_divisoes(self, destruir):
        novo = User.objects.create_user(email='novo@teste.fluxar', password='senha-de-teste-123')

        self.assertEqual(dados_do_salario(novo), SEM_NADA)


class RestricoesDaDivisaoTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user(email='ana@teste.fluxar', password='senha-de-teste-123')
        self.bia = User.objects.create_user(email='bia@teste.fluxar', password='senha-de-teste-123')
        self.conta = Account.objects.create(user=self.ana, name='Corrente', type='CHECKING')
        self.recebimento = Transaction.objects.create(
            user=self.ana, type='INCOME', status='COMPLETED', account=self.conta,
            description='Salário', amount=Decimal('3000.00'), date=date(2026, 10, 5),
        )

    def divisao(self, usuario=None, recebimento_ref=None, chave=None, **extra):
        return DivisaoDoSalario.objects.create(
            user=usuario or self.ana, recebimento_ref=recebimento_ref or uuid.uuid4(), chave=chave,
            valor_recebido=Decimal('3000.00'), total=Decimal('600.00'), livre=Decimal('2400.00'), **extra,
        )

    def test_a_mesma_chave_nao_se_repete_para_o_mesmo_usuario(self):
        chave = uuid.uuid4()
        self.divisao(chave=chave)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.divisao(chave=chave)
        # Outro usuário pode usar a mesma chave, e sem chave não há restrição
        self.divisao(usuario=self.bia, chave=chave)
        self.divisao()
        self.divisao()
        self.assertEqual(DivisaoDoSalario.objects.count(), 4)

    def test_um_recebimento_tem_uma_so_divisao_ativa(self):
        primeira = self.divisao(recebimento=self.recebimento, recebimento_ref=self.recebimento.pk)

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.divisao(recebimento=self.recebimento, recebimento_ref=self.recebimento.pk)

        # Desfeita a primeira, o recebimento aceita uma nova divisão
        primeira.desfeita_em = timezone.now()
        primeira.save(update_fields=['desfeita_em'])
        self.divisao(recebimento=self.recebimento, recebimento_ref=self.recebimento.pk)
        self.assertEqual(DivisaoDoSalario.objects.filter(recebimento_ref=self.recebimento.pk).count(), 2)

    def test_a_divisao_continua_depois_de_o_recebimento_ser_excluido(self):
        divisao = self.divisao(recebimento=self.recebimento, recebimento_ref=self.recebimento.pk)
        recebimento_id = self.recebimento.pk

        self.recebimento.delete()

        divisao.refresh_from_db()
        self.assertIsNone(divisao.recebimento_id)
        self.assertEqual(divisao.recebimento_ref, recebimento_id)

    def test_transacao_guarda_a_divisao_que_a_gerou(self):
        self.assertIsNone(self.recebimento.divisao_do_salario)
        marca = uuid.uuid4()

        Transaction.objects.filter(pk=self.recebimento.pk).update(divisao_do_salario=marca)

        self.assertEqual(Transaction.objects.filter(divisao_do_salario=marca).count(), 1)

"""
Exclusão definitiva da conta (LGPD-10 a LGPD-14).

O Cloudinary é simulado: o teste confere quais imagens seriam removidas e
simula a falha da remoção.
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.faturas import obter_fatura
from accounts.models import Account, CreditCard, CreditCardInvoice, PagamentoDeFatura
from api.exclusao import EXCECOES, MODELOS_DO_USUARIO, ExclusaoFalhou, excluir_definitivamente
from api.models import (
    EmailVerificationToken,
    PasswordResetToken,
    RegistroDeExclusao,
    Sessao,
    SystemLog,
    User,
)
from api.sessoes import criar_sessao
from budgets.models import Budget
from core import termos
from goals.models import ConfiguracaoDeTrocos, Goal, GoalDeposit, Troco
from reports.models import FocusedMonitorItem
from salario.models import DivisaoDoSalario, GestaoDoSalario, ItemDaDivisao, ParteDoPlano
from transactions.models import Category, CorrecaoDeCategoria, RecurringTransaction, Tag, Transaction

SENHA = 'senha-de-teste-123'
AVATAR = 'avatars/avatar-da-ana'
IMAGEM_DA_META = 'goals/imagem-da-viagem'
DESTRUIR = 'cloudinary.uploader.destroy'
OK = {'result': 'ok'}


def criar_conta_completa(email='ana@teste.fluxar'):
    """Um usuário com dados em todas as partes do app."""
    usuario = User.objects.create_user(email=email, password=SENHA, name='Ana Souza', cpf='52998224725')
    User.objects.filter(pk=usuario.pk).update(avatar=AVATAR)
    usuario.refresh_from_db()
    conta = Account.objects.create(user=usuario, name='Corrente', type='CHECKING', initial_balance=Decimal('1000'))
    cofrinho = Account.objects.create(user=usuario, name='Cofrinho', type='PIGGY_BANK')
    categoria = Category.objects.create(user=usuario, name='Mercado', type='EXPENSE')
    tag = Tag.objects.create(user=usuario, name='Viagem')
    cartao = CreditCard.objects.create(
        user=usuario, name='Cartão', limit=Decimal('5000'), closing_day=10, due_day=20, account=conta,
    )
    fatura = obter_fatura(cartao, 9, 2026)
    Transaction.objects.create(
        user=usuario, type='CREDIT_CARD', status='PENDING', account=conta, credit_card=cartao,
        invoice=fatura, description='Compra', amount=Decimal('100'), date=fatura.due_date,
        purchase_date=date(2026, 9, 1),
    )
    PagamentoDeFatura.objects.create(
        user=usuario, fatura=fatura, conta=conta, valor=Decimal('100'), data=date(2026, 9, 15),
    )
    despesa = Transaction.objects.create(
        user=usuario, type='EXPENSE', status='COMPLETED', account=conta, category=categoria,
        description='Padaria', amount=Decimal('12.50'), date=date(2026, 9, 2),
    )
    despesa.tags.add(tag)
    RecurringTransaction.objects.create(
        user=usuario, description='Aluguel', amount=Decimal('900'), type='EXPENSE', account=conta,
        frequency='MONTHLY', start_date=date(2026, 9, 5),
    )
    meta = Goal.objects.create(
        user=usuario, name='Viagem', target_amount=Decimal('1000'), account=cofrinho, image=IMAGEM_DA_META,
    )
    GoalDeposit.objects.create(
        goal=meta, account=cofrinho, amount=Decimal('10'), type='DEPOSIT', date=date(2026, 9, 3),
        description='Aporte',
    )
    ConfiguracaoDeTrocos.objects.create(user=usuario, ativo=True, meta=meta)
    Troco.objects.create(user=usuario, despesa=despesa, conta=conta, valor=Decimal('0.50'))
    CorrecaoDeCategoria.objects.create(user=usuario, descricao='Padaria', descricao_normalizada='padaria')
    salario = Category.objects.create(user=usuario, name='Salário Extra', type='INCOME')
    recebimento = Transaction.objects.create(
        user=usuario, type='INCOME', status='COMPLETED', account=conta, category=salario,
        description='Salário', amount=Decimal('3000'), date=date(2026, 9, 5),
    )
    gestao = GestaoDoSalario.objects.create(user=usuario, plano_salvo=True, categorias_configuradas=True)
    gestao.categorias.add(salario)
    ParteDoPlano.objects.create(
        gestao=gestao, ordem=0, nome='Guardar', tipo_de_regra='PERCENT', valor=Decimal('10'),
        tipo_de_destino='GOAL', meta=meta,
    )
    divisao = DivisaoDoSalario.objects.create(
        user=usuario, recebimento=recebimento, recebimento_ref=recebimento.pk, conta_de_origem=conta,
        valor_recebido=Decimal('3000'), total=Decimal('300'), livre=Decimal('2700'),
    )
    ItemDaDivisao.objects.create(
        divisao=divisao, ordem=0, nome_da_parte='Guardar', tipo_de_destino='GOAL', meta=meta, valor=Decimal('300'),
    )
    Budget.objects.create(user=usuario, category=categoria, month=9, year=2026, amount_limit=Decimal('300'))
    FocusedMonitorItem.objects.create(user=usuario, category=categoria)
    criar_sessao(usuario)
    EmailVerificationToken.objects.create(user=usuario, expires_at=timezone.now() + timedelta(hours=1))
    PasswordResetToken.objects.create(user=usuario, expires_at=timezone.now() + timedelta(hours=1))
    termos.registrar_aceite(usuario)
    termos.registrar_decisao(usuario, True)
    return usuario


def pedir_exclusao(usuario):
    """Marca a conta como o pedido do usuário faria (LGPD-05)."""
    agora = timezone.now()
    usuario.is_active = False
    usuario.exclusao_pedida_em = agora - timedelta(days=31)
    usuario.exclusao_agendada_para = agora - timedelta(days=1)
    usuario.save(update_fields=['is_active', 'exclusao_pedida_em', 'exclusao_agendada_para'])
    return usuario


def linhas_do_usuario(usuario_id):
    """Quantas linhas ainda apontam para o usuário, por modelo."""
    contagem = {}
    for rotulo, campo in MODELOS_DO_USUARIO:
        modelo = apps.get_model(rotulo)
        contagem[rotulo] = modelo.objects.filter(**{f'{campo}_id': usuario_id}).count()
    return contagem


class ExclusaoDefinitivaTests(TestCase):

    def setUp(self):
        self.ana = pedir_exclusao(criar_conta_completa())
        self.ana_id = self.ana.pk
        self.bia = criar_conta_completa('bia@teste.fluxar')

    # LGPD-10 ---------------------------------------------------------------

    @mock.patch(DESTRUIR, return_value=OK)
    def test_apaga_todos_os_dados_e_as_imagens_no_cloudinary(self, destruir):
        antes_da_bia = linhas_do_usuario(self.bia.pk)

        excluir_definitivamente(self.ana, RegistroDeExclusao.ROTINA)

        self.assertFalse(User.objects.filter(pk=self.ana_id).exists())
        self.assertEqual({rotulo: n for rotulo, n in linhas_do_usuario(self.ana_id).items() if n}, {})
        self.assertFalse(GoalDeposit.objects.filter(goal__user_id=self.ana_id).exists())
        self.assertFalse(CreditCardInvoice.objects.filter(card__user_id=self.ana_id).exists())
        removidas = {chamada.args[0] for chamada in destruir.call_args_list}
        self.assertEqual(removidas, {AVATAR, IMAGEM_DA_META})
        # Os dados de outra conta continuam
        self.assertEqual(linhas_do_usuario(self.bia.pk), antes_da_bia)

    # LGPD-11 ---------------------------------------------------------------

    @mock.patch(DESTRUIR, return_value=OK)
    def test_fica_so_o_registro_sem_dados_pessoais(self, destruir):
        pedida_em = self.ana.exclusao_pedida_em
        antes = timezone.now()

        excluir_definitivamente(self.ana, RegistroDeExclusao.ROTINA)

        registro = RegistroDeExclusao.objects.get()
        self.assertEqual(registro.usuario_id, self.ana_id)
        self.assertEqual(registro.pedida_em, pedida_em)
        self.assertGreaterEqual(registro.excluida_em, antes)
        self.assertEqual(registro.executada_por, RegistroDeExclusao.ROTINA)
        valores = ' '.join(str(getattr(registro, campo.attname)) for campo in RegistroDeExclusao._meta.fields)
        for dado in ('Ana', 'ana@teste.fluxar', '52998224725'):
            self.assertNotIn(dado, valores)

    @mock.patch(DESTRUIR, return_value=OK)
    def test_logs_de_acoes_de_admin_ficam_so_com_o_id_e_os_demais_saem(self, destruir):
        acao_de_admin = SystemLog.objects.create(
            user=self.ana, action='RESET_PASSWORD', description='Senha redefinida pelo administrador.',
            admin_name='ad***@teste.fluxar',
        )
        do_sistema = SystemLog.objects.create(
            user=self.ana, action='EMAIL_VERIFIED', description='E-mail verificado.', admin_name='Sistema',
        )

        excluir_definitivamente(self.ana, RegistroDeExclusao.ROTINA)

        acao_de_admin.refresh_from_db()
        self.assertIsNone(acao_de_admin.user_id)
        self.assertEqual(acao_de_admin.usuario_ref, self.ana_id)
        self.assertFalse(SystemLog.objects.filter(pk=do_sistema.pk).exists())

    # LGPD-12 ---------------------------------------------------------------

    @mock.patch(DESTRUIR, side_effect=ConnectionError('fora do ar'))
    def test_com_o_cloudinary_falhando_nada_e_apagado(self, destruir):
        antes = linhas_do_usuario(self.ana_id)

        with self.assertRaises(ExclusaoFalhou):
            excluir_definitivamente(self.ana, RegistroDeExclusao.ROTINA)

        ana = User.objects.get(pk=self.ana_id)
        self.assertFalse(ana.is_active)
        self.assertIsNotNone(ana.exclusao_agendada_para)
        self.assertEqual(linhas_do_usuario(self.ana_id), antes)
        self.assertFalse(RegistroDeExclusao.objects.exists())

    @mock.patch(DESTRUIR, return_value={'result': 'error'})
    def test_cloudinary_recusando_a_remocao_tambem_nao_apaga_nada(self, destruir):
        with self.assertRaises(ExclusaoFalhou):
            excluir_definitivamente(self.ana, RegistroDeExclusao.ROTINA)

        self.assertTrue(User.objects.filter(pk=self.ana_id).exists())
        self.assertFalse(RegistroDeExclusao.objects.exists())


class ModelosDoUsuarioTests(TestCase):

    def test_todo_modelo_com_fk_para_o_usuario_esta_na_lista_ou_nas_excecoes(self):
        """Um modelo novo com FK para `User` fora da lista faz este teste falhar (LGPD-10)."""
        conhecidos = set(MODELOS_DO_USUARIO) | set(EXCECOES)
        usuario = get_user_model()
        encontrados = set()
        for modelo in apps.get_models():
            for campo in modelo._meta.get_fields():
                relacao = campo.is_relation and campo.concrete and getattr(campo, 'related_model', None)
                if relacao is usuario:
                    encontrados.add((modelo._meta.label, campo.name))

        self.assertEqual(encontrados - conhecidos, set())
        # E a lista não cita modelos ou campos que não existem
        self.assertEqual(conhecidos - encontrados, set())


@mock.patch(DESTRUIR, return_value=OK)
class ExclusaoPeloAdminTests(APITestCase):

    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@teste.fluxar', password=SENHA, name='Admin', role='ADMIN', is_staff=True,
        )
        self.client.force_authenticate(user=self.admin)

    ROTAS = (
        ('/api/admin/users/{pk}/', {'admin_password': SENHA, 'permanent': True}),
        ('/api/admin/users/{pk}/hard-delete/', {'admin_password': SENHA}),
    )

    def test_exclui_na_hora_inclusive_conta_pendente_com_o_registro_e_sem_o_nome(self, destruir):
        for rota, corpo in self.ROTAS:
            with self.subTest(rota=rota):
                RegistroDeExclusao.objects.all().delete()
                ana = pedir_exclusao(criar_conta_completa())
                ana_id, pedida_em = ana.pk, ana.exclusao_pedida_em

                resposta = self.client.delete(rota.format(pk=ana_id), corpo, format='json')

                self.assertEqual(resposta.status_code, 200, resposta.data)
                texto = resposta.content.decode()
                self.assertNotIn('Ana', texto)
                self.assertNotIn('ana@teste.fluxar', texto)
                self.assertFalse(User.objects.filter(pk=ana_id).exists())
                self.assertEqual({r: n for r, n in linhas_do_usuario(ana_id).items() if n}, {})
                registro = RegistroDeExclusao.objects.get(usuario_id=ana_id)
                self.assertEqual(registro.executada_por, RegistroDeExclusao.ADMIN)
                self.assertEqual(registro.pedida_em, pedida_em)

    def test_conta_ativa_e_excluida_na_hora_sem_data_de_pedido(self, destruir):
        ana = criar_conta_completa()

        resposta = self.client.delete(
            f'/api/admin/users/{ana.pk}/hard-delete/', {'admin_password': SENHA}, format='json',
        )

        self.assertEqual(resposta.status_code, 200, resposta.data)
        registro = RegistroDeExclusao.objects.get(usuario_id=ana.pk)
        self.assertIsNone(registro.pedida_em)
        self.assertEqual(registro.executada_por, RegistroDeExclusao.ADMIN)

    def test_com_o_cloudinary_falhando_o_admin_recebe_erro_e_nada_e_apagado(self, destruir):
        destruir.side_effect = ConnectionError('fora do ar')
        ana = criar_conta_completa()

        resposta = self.client.delete(
            f'/api/admin/users/{ana.pk}/hard-delete/', {'admin_password': SENHA}, format='json',
        )

        self.assertEqual(resposta.status_code, 503)
        self.assertEqual(resposta.data['code'], 'deletion_failed')
        self.assertTrue(User.objects.filter(pk=ana.pk, is_active=True).exists())
        self.assertFalse(RegistroDeExclusao.objects.exists())

    # LGPD-14 ---------------------------------------------------------------

    @mock.patch('api.views.send_verification_email', return_value=True)
    def test_depois_da_exclusao_o_mesmo_email_se_cadastra_de_novo(self, envio, destruir):
        ana = criar_conta_completa()
        self.client.delete(f'/api/admin/users/{ana.pk}/hard-delete/', {'admin_password': SENHA}, format='json')
        self.client.force_authenticate(user=None)

        resposta = self.client.post('/api/auth/register/', {
            'name': 'Ana Nova', 'email': 'ana@teste.fluxar', 'password': 'Outra-senha-forte-987',
            'password_confirm': 'Outra-senha-forte-987', 'terms_accepted': True,
        }, format='json')

        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertTrue(User.objects.filter(email='ana@teste.fluxar').exists())

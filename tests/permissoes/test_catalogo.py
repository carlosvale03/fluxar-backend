"""
Catálogo de travas, configuração e decisão de acesso (PERM-09, PERM-14,
PERM-23 e PERM-28; AD-044).

Linha ausente em `TravaDePlano` vale liberado e sem limite. A liberação para
testes fica na `GlobalSetting` `testing_unlock`, que a migração grava ligada.
`acesso(usuario)` libera tudo para o administrador e com a liberação ligada;
senão vale a configuração do plano atual do usuário.
"""
import importlib
from decimal import Decimal
from unittest.mock import patch

from django.apps import apps as apps_atuais

from accounts.models import Account
from api.models import GlobalSetting, TravaDePlano, User
from core import travas
from goals.models import Goal

from .base import LIMITES, RECURSOS, PermissoesTestCase, criar_admin, criar_usuario, fechar, liberacao_de_testes

PLANOS = ['COMMON', 'PREMIUM', 'PREMIUM_PLUS']


def fechar_tudo(plano='COMMON'):
    for chave in RECURSOS:
        fechar(chave, plano)
    for chave in LIMITES:
        fechar(chave, plano, limite=0)


class CatalogoTests(PermissoesTestCase):

    def test_catalogo_tem_os_18_recursos_e_os_6_limites_da_spec(self):
        self.assertEqual(travas.PLANOS, tuple(PLANOS))
        recursos = [c for c, t in travas.CATALOGO.items() if t.tipo == travas.RECURSO]
        limites = [c for c, t in travas.CATALOGO.items() if t.tipo == travas.LIMITE]
        self.assertEqual(sorted(recursos), sorted(RECURSOS))
        self.assertEqual(sorted(limites), sorted(LIMITES))
        for chave, trava in travas.CATALOGO.items():
            with self.subTest(chave=chave):
                self.assertTrue(trava.nome and trava.descricao)
                self.assertEqual(callable(trava.contar), trava.tipo == travas.LIMITE)

    def test_nenhum_recurso_essencial_existe_no_catalogo(self):
        # PERM-14: os essenciais não têm chave, então não há como travá-los
        essenciais = [
            'cadastro', 'login', 'perfil', 'dashboard', 'graficos_simples', 'contas', 'transacoes',
            'transferencias', 'categorias', 'pagamento_de_faturas', 'exportacao_lgpd', 'planos',
        ]
        for chave in essenciais:
            self.assertNotIn(chave, travas.CATALOGO)


class ConfiguracaoInicialTests(PermissoesTestCase):

    def test_migracao_deixa_a_liberacao_para_testes_ligada(self):
        self.assertEqual(GlobalSetting.objects.get(key='testing_unlock').value, 'true')
        self.assertIs(travas.acesso(criar_usuario('comum')).testing_unlock, True)

    def test_migracao_nao_sobrescreve_uma_liberacao_ja_gravada(self):
        GlobalSetting.objects.filter(key='testing_unlock').update(value='false')
        migracao = importlib.import_module('api.migrations.0013_liberacao_para_testes')

        migracao.gravar_liberacao(apps_atuais, None)

        self.assertEqual(GlobalSetting.objects.get(key='testing_unlock').value, 'false')

    def test_sem_a_chave_a_liberacao_vale_ligada(self):
        GlobalSetting.objects.filter(key='testing_unlock').delete()
        travas.invalidar()
        self.assertIs(travas.acesso(criar_usuario('comum')).testing_unlock, True)

    def test_sem_nenhuma_linha_tudo_fica_liberado_e_sem_limite_nos_tres_planos(self):
        liberacao_de_testes(False)
        self.assertFalse(TravaDePlano.objects.exists())
        for plano in PLANOS:
            acesso = travas.acesso(criar_usuario(f'usuario-{plano.lower()}', plan=plano))
            with self.subTest(plano=plano):
                self.assertEqual(acesso.plano, plano)
                self.assertIs(acesso.testing_unlock, False)
                for chave in RECURSOS:
                    self.assertIs(acesso.recurso_liberado(chave), True, chave)
                for chave in LIMITES:
                    self.assertIsNone(acesso.limite(chave), chave)


class AcessoTests(PermissoesTestCase):

    def setUp(self):
        super().setUp()
        fechar_tudo('COMMON')

    def test_com_a_liberacao_desligada_vale_a_configuracao_do_plano(self):
        liberacao_de_testes(False)
        comum = travas.acesso(criar_usuario('comum'))
        premium = travas.acesso(criar_usuario('premium', plan='PREMIUM'))
        for chave in RECURSOS:
            self.assertIs(comum.recurso_liberado(chave), False, chave)
            self.assertIs(premium.recurso_liberado(chave), True, chave)
        for chave in LIMITES:
            self.assertEqual(comum.limite(chave), 0, chave)
            self.assertIsNone(premium.limite(chave), chave)

    def test_admin_tem_tudo_liberado_e_sem_limite_mesmo_com_o_plano_travado(self):
        liberacao_de_testes(False)
        acesso = travas.acesso(criar_admin(plan='COMMON'))
        self.assertIs(acesso.is_admin, True)
        self.assertEqual(acesso.plano, 'COMMON')
        for chave in RECURSOS:
            self.assertIs(acesso.recurso_liberado(chave), True, chave)
        for chave in LIMITES:
            self.assertIsNone(acesso.limite(chave), chave)

    def test_admin_arquivado_nao_e_tratado_como_admin(self):
        liberacao_de_testes(False)
        acesso = travas.acesso(criar_admin(is_active=False))
        self.assertIs(acesso.is_admin, False)
        self.assertIs(acesso.recurso_liberado('metas'), False)

    def test_liberacao_ligada_libera_tudo_sem_mudar_o_plano_gravado(self):
        liberacao_de_testes(True)
        comum = criar_usuario('comum')
        acesso = travas.acesso(comum)
        self.assertIs(acesso.testing_unlock, True)
        self.assertEqual(acesso.plano, 'COMMON')
        for chave in RECURSOS:
            self.assertIs(acesso.recurso_liberado(chave), True, chave)
        for chave in LIMITES:
            self.assertIsNone(acesso.limite(chave), chave)
        self.assertEqual(User.objects.get(pk=comum.pk).plan, 'COMMON')

    def test_mudanca_de_plano_vale_na_proxima_decisao(self):
        # PERM-04: o acesso usa o plano atual do banco
        liberacao_de_testes(False)
        usuario = criar_usuario('comum')
        self.assertIs(travas.acesso(usuario).recurso_liberado('metas'), False)
        User.objects.filter(pk=usuario.pk).update(plan='PREMIUM')
        self.assertIs(travas.acesso(User.objects.get(pk=usuario.pk)).recurso_liberado('metas'), True)


class ContagemDeContasTests(PermissoesTestCase):

    def test_limite_de_contas_ignora_o_cofrinho_criado_por_uma_meta(self):
        usuario = criar_usuario('comum')
        base = travas.uso(usuario, 'limite_contas')  # a "Carteira" criada no cadastro
        Account.objects.create(user=usuario, name='Corrente', type='CHECKING')
        Account.objects.create(user=usuario, name='Antiga', type='CHECKING', is_active=False)
        cofrinho_da_meta = Account.objects.create(user=usuario, name='Cofrinho: Viagem', type='PIGGY_BANK')
        Goal.objects.create(user=usuario, name='Viagem', target_amount=Decimal('100.00'), account=cofrinho_da_meta)
        Account.objects.create(user=usuario, name='Cofrinho avulso', type='PIGGY_BANK')

        self.assertEqual(travas.uso(usuario, 'limite_contas'), base + 2)


class CacheDasTravasTests(PermissoesTestCase):

    def setUp(self):
        super().setUp()
        self.agora = 1000.0
        relogio = patch('core.travas.time.monotonic', side_effect=lambda: self.agora)
        relogio.start()
        self.addCleanup(relogio.stop)
        liberacao_de_testes(False)
        self.usuario = criar_usuario('comum')

    def gravar(self, liberado):
        TravaDePlano.objects.update_or_create(
            chave='metas', plano='COMMON', defaults={'liberado': liberado},
        )

    def test_mudanca_no_banco_vale_em_ate_30_segundos(self):
        self.assertIs(travas.acesso(self.usuario).recurso_liberado('metas'), True)
        self.gravar(False)

        self.agora = 1029.9
        self.assertIs(travas.acesso(self.usuario).recurso_liberado('metas'), True)

        self.agora = 1030.0
        self.assertIs(travas.acesso(self.usuario).recurso_liberado('metas'), False)

    def test_invalidar_faz_a_mudanca_valer_na_hora(self):
        self.assertIs(travas.acesso(self.usuario).recurso_liberado('metas'), True)
        self.gravar(False)

        travas.invalidar()

        self.assertIs(travas.acesso(self.usuario).recurso_liberado('metas'), False)

    def test_dentro_de_30_segundos_nao_consulta_o_banco_de_novo(self):
        travas.acesso(self.usuario)
        with self.assertNumQueries(0):
            for segundos in (1, 15, 29.9):
                self.agora = 1000.0 + segundos
                travas.acesso(self.usuario).recurso_liberado('metas')

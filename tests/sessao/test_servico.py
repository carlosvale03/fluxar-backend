"""
Serviço de sessões (SESSAO-07 a SESSAO-09, SESSAO-15 e SESSAO-16).

Cada sessão tem uma linha em `Sessao`, e os tokens levam o `sid` dela. O token
de acesso vale 15 minutos; o de renovação, 7 dias contados a partir do último
uso. Um token de renovação usado, de sessão encerrada ou vencida, vencido, de
conta desativada ou sem `sid` é recusado.
"""
from datetime import datetime, timedelta, timezone as dt_timezone

from django.test import TestCase
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from api.models import Sessao, User
from api.sessoes import (
    SessaoInvalida,
    criar_sessao,
    encerrar,
    encerrar_outras,
    encerrar_todas,
    renovar,
    sessao_aberta,
)

SENHA = 'Cofre-Azul-2026'


def momento(token, claim):
    return datetime.fromtimestamp(token[claim], tz=dt_timezone.utc)


class ServicoDeSessoesTestCase(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user(
            email='ana@fluxar.teste', password=SENHA, name='Ana', email_verified=True,
        )
        self.bia = User.objects.create_user(
            email='bia@fluxar.teste', password=SENHA, name='Bia', email_verified=True,
        )

    def sessao_do(self, refresh):
        return Sessao.objects.get(pk=RefreshToken(refresh)['sid'])


class CriarSessaoTests(ServicoDeSessoesTestCase):

    def test_grava_a_sessao_aberta_com_o_sid_e_o_jti_nos_tokens(self):
        access, refresh = criar_sessao(self.ana)

        acesso, renovacao = AccessToken(access), RefreshToken(refresh)
        sessao = Sessao.objects.get()
        self.assertEqual(sessao.user, self.ana)
        self.assertIsNone(sessao.encerrada_em)
        self.assertEqual(acesso['sid'], str(sessao.id))
        self.assertEqual(renovacao['sid'], str(sessao.id))
        self.assertEqual(sessao.refresh_jti, renovacao['jti'])
        self.assertEqual(acesso['user_id'], str(self.ana.pk))
        # As claims do login continuam no token (AUTH-14)
        self.assertEqual(acesso['name'], 'Ana')
        self.assertEqual(acesso['email'], 'ana@fluxar.teste')
        self.assertEqual(acesso['plan'], 'COMMON')
        self.assertEqual(acesso['role'], 'USER')

    # SESSAO-07 ---------------------------------------------------------

    def test_token_de_acesso_vale_15_minutos(self):
        access, _ = criar_sessao(self.ana)

        acesso = AccessToken(access)
        self.assertEqual(momento(acesso, 'exp') - momento(acesso, 'iat'), timedelta(minutes=15))

    def test_token_de_renovacao_e_a_sessao_valem_7_dias(self):
        antes = timezone.now().replace(microsecond=0)
        _, refresh = criar_sessao(self.ana)
        depois = timezone.now()

        renovacao = RefreshToken(refresh)
        self.assertEqual(momento(renovacao, 'exp') - momento(renovacao, 'iat'), timedelta(days=7))
        sessao = self.sessao_do(refresh)
        self.assertGreaterEqual(sessao.expira_em, antes + timedelta(days=7))
        self.assertLessEqual(sessao.expira_em, depois + timedelta(days=7))


class RenovarTests(ServicoDeSessoesTestCase):

    # SESSAO-08 ---------------------------------------------------------

    def test_emite_tokens_novos_da_mesma_sessao_com_7_dias_a_partir_do_uso(self):
        _, refresh = criar_sessao(self.ana)
        sessao = self.sessao_do(refresh)
        # Seis dias depois do login: falta um dia para a sessão vencer
        seis_dias_atras = timezone.now() - timedelta(days=6)
        Sessao.objects.filter(pk=sessao.pk).update(
            ultimo_uso=seis_dias_atras, expira_em=timezone.now() + timedelta(days=1),
        )

        antes = timezone.now().replace(microsecond=0)
        access_novo, refresh_novo = renovar(refresh)
        depois = timezone.now()

        acesso, renovacao = AccessToken(access_novo), RefreshToken(refresh_novo)
        self.assertEqual(acesso['sid'], str(sessao.id))
        self.assertEqual(renovacao['sid'], str(sessao.id))
        self.assertNotEqual(renovacao['jti'], RefreshToken(refresh)['jti'])
        self.assertEqual(momento(acesso, 'exp') - momento(acesso, 'iat'), timedelta(minutes=15))
        self.assertGreaterEqual(momento(renovacao, 'exp'), antes + timedelta(days=7))
        sessao.refresh_from_db()
        self.assertEqual(sessao.refresh_jti, renovacao['jti'])
        self.assertGreaterEqual(sessao.ultimo_uso, antes)
        self.assertLessEqual(sessao.ultimo_uso, depois)
        self.assertGreaterEqual(sessao.expira_em, antes + timedelta(days=7))
        self.assertLessEqual(sessao.expira_em, depois + timedelta(days=7))
        self.assertIsNone(sessao.encerrada_em)

    # SESSAO-09 ---------------------------------------------------------

    def test_recusa_o_token_ja_usado(self):
        _, refresh = criar_sessao(self.ana)
        _, refresh_novo = renovar(refresh)

        with self.assertRaises(SessaoInvalida):
            renovar(refresh)
        self.assertEqual(self.sessao_do(refresh_novo).refresh_jti, RefreshToken(refresh_novo)['jti'])

    def test_recusa_o_token_de_sessao_encerrada(self):
        _, refresh = criar_sessao(self.ana)
        encerrar(RefreshToken(refresh)['sid'])

        with self.assertRaises(SessaoInvalida):
            renovar(refresh)

    def test_recusa_o_token_vencido(self):
        _, refresh = criar_sessao(self.ana)
        vencido = RefreshToken(refresh)
        vencido.set_exp(from_time=timezone.now() - timedelta(days=8))

        with self.assertRaises(SessaoInvalida):
            renovar(str(vencido))

    def test_recusa_a_sessao_sem_uso_ha_7_dias(self):
        _, refresh = criar_sessao(self.ana)
        Sessao.objects.filter(pk=RefreshToken(refresh)['sid']).update(
            expira_em=timezone.now() - timedelta(seconds=1),
        )

        with self.assertRaises(SessaoInvalida):
            renovar(refresh)

    def test_recusa_o_token_de_conta_desativada(self):
        _, refresh = criar_sessao(self.ana)
        User.objects.filter(pk=self.ana.pk).update(is_active=False)

        with self.assertRaises(SessaoInvalida):
            renovar(refresh)

    def test_recusa_o_token_sem_sid(self):
        with self.assertRaises(SessaoInvalida):
            renovar(str(RefreshToken.for_user(self.ana)))

    def test_recusa_o_token_de_outro_usuario_com_o_sid_da_vitima(self):
        _, refresh_ana = criar_sessao(self.ana)
        forjado = RefreshToken.for_user(self.bia)
        forjado['sid'] = RefreshToken(refresh_ana)['sid']
        forjado['jti'] = RefreshToken(refresh_ana)['jti']

        with self.assertRaises(SessaoInvalida):
            renovar(str(forjado))


class EncerrarTests(ServicoDeSessoesTestCase):

    def abrir(self, user):
        _, refresh = criar_sessao(user)
        return self.sessao_do(refresh)

    def test_encerrar_fecha_so_a_sessao_indicada(self):
        primeira, segunda = self.abrir(self.ana), self.abrir(self.ana)

        encerrar(str(primeira.id))

        primeira.refresh_from_db()
        segunda.refresh_from_db()
        self.assertIsNotNone(primeira.encerrada_em)
        self.assertIsNone(segunda.encerrada_em)

    # SESSAO-15 ---------------------------------------------------------

    def test_encerrar_outras_mantem_a_atual_e_fecha_as_demais_do_usuario(self):
        atual, outra, mais_uma = self.abrir(self.ana), self.abrir(self.ana), self.abrir(self.ana)
        da_bia = self.abrir(self.bia)

        encerrar_outras(self.ana, str(atual.id))

        for sessao in (atual, outra, mais_uma, da_bia):
            sessao.refresh_from_db()
        self.assertIsNone(atual.encerrada_em)
        self.assertIsNotNone(outra.encerrada_em)
        self.assertIsNotNone(mais_uma.encerrada_em)
        self.assertIsNone(da_bia.encerrada_em)

    def test_encerrar_outras_nao_mantem_a_sessao_atual_de_outro_usuario(self):
        # O sid atual de outra pessoa não salva nenhuma sessão da Ana
        da_ana, da_bia = self.abrir(self.ana), self.abrir(self.bia)

        encerrar_outras(self.ana, str(da_bia.id))

        da_ana.refresh_from_db()
        da_bia.refresh_from_db()
        self.assertIsNotNone(da_ana.encerrada_em)
        self.assertIsNone(da_bia.encerrada_em)

    # SESSAO-16 ---------------------------------------------------------

    def test_encerrar_todas_fecha_todas_as_sessoes_do_usuario(self):
        primeira, segunda = self.abrir(self.ana), self.abrir(self.ana)
        da_bia = self.abrir(self.bia)

        encerrar_todas(self.ana)

        for sessao in (primeira, segunda, da_bia):
            sessao.refresh_from_db()
        self.assertIsNotNone(primeira.encerrada_em)
        self.assertIsNotNone(segunda.encerrada_em)
        self.assertIsNone(da_bia.encerrada_em)


class SessaoAbertaTests(ServicoDeSessoesTestCase):

    def setUp(self):
        super().setUp()
        _, refresh = criar_sessao(self.ana)
        self.sessao = self.sessao_do(refresh)

    def test_sessao_aberta_do_proprio_usuario(self):
        self.assertIs(sessao_aberta(str(self.sessao.id), self.ana.pk), True)

    def test_sessao_encerrada_vencida_de_outro_usuario_ou_sem_sid_nao_vale(self):
        self.assertIs(sessao_aberta(str(self.sessao.id), self.bia.pk), False)
        self.assertIs(sessao_aberta(None, self.ana.pk), False)
        self.assertIs(sessao_aberta('nao-e-um-uuid', self.ana.pk), False)

        Sessao.objects.filter(pk=self.sessao.pk).update(expira_em=timezone.now() - timedelta(seconds=1))
        self.assertIs(sessao_aberta(str(self.sessao.id), self.ana.pk), False)

        Sessao.objects.filter(pk=self.sessao.pk).update(
            expira_em=timezone.now() + timedelta(days=1), encerrada_em=timezone.now(),
        )
        self.assertIs(sessao_aberta(str(self.sessao.id), self.ana.pk), False)

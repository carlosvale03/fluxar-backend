"""
Rotina diária da exclusão definitiva (LGPD-10, LGPD-12, AD-048).

A data vencida é simulada gravando `exclusao_agendada_para` no passado; o
Cloudinary é simulado.
"""
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from api.models import GlobalSetting, RegistroDeExclusao, User
from core import manutencao

ROTA = '/api/rotina-diaria/'
TOKEN = 'token-da-rotina-de-teste'
DESTRUIR = 'cloudinary.uploader.destroy'
OK = {'result': 'ok'}


def conta_marcada(email, vence_em, avatar=None):
    """Uma conta desativada com a exclusão definitiva marcada para `vence_em`."""
    usuario = User.objects.create_user(email=email, password='senha-de-teste-123', name='Pessoa')
    agora = timezone.now()
    User.objects.filter(pk=usuario.pk).update(
        is_active=False, exclusao_pedida_em=agora - timedelta(days=30), exclusao_agendada_para=vence_em,
        avatar=avatar,
    )
    return User.objects.get(pk=usuario.pk)


@mock.patch(DESTRUIR, return_value=OK)
class RotinaDiariaTests(TestCase):

    def rodar(self):
        saida = StringIO()
        call_command('rotina_diaria', stdout=saida)
        return saida.getvalue()

    def test_apaga_a_conta_vencida_e_mantem_a_de_prazo_futuro(self, destruir):
        agora = timezone.now()
        vencida = conta_marcada('vencida@teste.fluxar', agora - timedelta(minutes=1))
        futura = conta_marcada('futura@teste.fluxar', agora + timedelta(days=3))

        saida = self.rodar()

        self.assertFalse(User.objects.filter(pk=vencida.pk).exists())
        registro = RegistroDeExclusao.objects.get(usuario_id=vencida.pk)
        self.assertEqual(registro.executada_por, RegistroDeExclusao.ROTINA)
        self.assertEqual(registro.pedida_em, vencida.exclusao_pedida_em)
        self.assertTrue(User.objects.filter(pk=futura.pk).exists())
        self.assertFalse(RegistroDeExclusao.objects.filter(usuario_id=futura.pk).exists())
        # A saída não identifica ninguém (LGPD-21)
        self.assertNotIn('vencida@teste.fluxar', saida)
        self.assertNotIn(str(vencida.pk), saida)

    def test_conta_ativa_sem_pedido_nao_e_apagada(self, destruir):
        ativa = User.objects.create_user(email='ativa@teste.fluxar', password='senha-de-teste-123', name='Ativa')

        self.rodar()

        self.assertTrue(User.objects.filter(pk=ativa.pk).exists())
        self.assertFalse(RegistroDeExclusao.objects.exists())

    def test_falha_de_uma_conta_nao_impede_a_proxima_e_ela_sai_na_execucao_seguinte(self, destruir):
        ontem = timezone.now() - timedelta(days=1)
        com_falha = conta_marcada('falha@teste.fluxar', ontem - timedelta(hours=1), avatar='avatars/quebrado')
        outra = conta_marcada('outra@teste.fluxar', ontem)

        def cloudinary_fora_do_ar_para_um(public_id):
            if public_id == 'avatars/quebrado':
                raise ConnectionError('fora do ar')
            return OK

        destruir.side_effect = cloudinary_fora_do_ar_para_um
        self.rodar()

        self.assertFalse(User.objects.filter(pk=outra.pk).exists())
        mantida = User.objects.get(pk=com_falha.pk)
        self.assertFalse(mantida.is_active)
        self.assertIsNotNone(mantida.exclusao_agendada_para)
        self.assertFalse(RegistroDeExclusao.objects.filter(usuario_id=com_falha.pk).exists())

        destruir.side_effect = None
        self.rodar()
        self.rodar()

        self.assertFalse(User.objects.filter(pk=com_falha.pk).exists())
        self.assertEqual(RegistroDeExclusao.objects.filter(usuario_id=com_falha.pk).count(), 1)
        self.assertEqual(RegistroDeExclusao.objects.filter(usuario_id=outra.pk).count(), 1)
        self.assertEqual(RegistroDeExclusao.objects.count(), 2)


@mock.patch(DESTRUIR, return_value=OK)
class RotaDaRotinaDiariaTests(APITestCase):

    def setUp(self):
        self.vencida = conta_marcada('vencida@teste.fluxar', timezone.now() - timedelta(days=1))

    @override_settings(ROTINA_DIARIA_TOKEN=TOKEN)
    def test_sem_token_ou_com_token_errado_recebe_401_e_nada_e_apagado(self, destruir):
        for cabecalho in ({}, {'HTTP_AUTHORIZATION': 'Bearer token-errado'}, {'HTTP_AUTHORIZATION': TOKEN}):
            with self.subTest(cabecalho=cabecalho):
                resposta = self.client.post(ROTA, **cabecalho)

                self.assertEqual(resposta.status_code, 401)
                self.assertTrue(User.objects.filter(pk=self.vencida.pk).exists())

    @override_settings(ROTINA_DIARIA_TOKEN=TOKEN)
    def test_com_o_token_certo_roda_e_responde_as_contagens(self, destruir):
        resposta = self.client.post(ROTA, HTTP_AUTHORIZATION=f'Bearer {TOKEN}')

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {'excluidas': 1, 'falhas': 0})
        self.assertFalse(User.objects.filter(pk=self.vencida.pk).exists())
        self.assertEqual(
            RegistroDeExclusao.objects.get(usuario_id=self.vencida.pk).executada_por, RegistroDeExclusao.ROTINA,
        )

    @override_settings(ROTINA_DIARIA_TOKEN=TOKEN)
    def test_conta_que_falha_entra_nas_falhas(self, destruir):
        destruir.side_effect = ConnectionError('fora do ar')
        User.objects.filter(pk=self.vencida.pk).update(avatar='avatars/quebrado')

        resposta = self.client.post(ROTA, HTTP_AUTHORIZATION=f'Bearer {TOKEN}')

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {'excluidas': 0, 'falhas': 1})
        self.assertTrue(User.objects.filter(pk=self.vencida.pk).exists())

    @override_settings(ROTINA_DIARIA_TOKEN='')
    def test_sem_a_variavel_configurada_a_rota_responde_404(self, destruir):
        resposta = self.client.post(ROTA, HTTP_AUTHORIZATION='Bearer qualquer')

        self.assertEqual(resposta.status_code, 404)
        self.assertTrue(User.objects.filter(pk=self.vencida.pk).exists())

    @override_settings(ROTINA_DIARIA_TOKEN=TOKEN)
    def test_roda_durante_a_manutencao(self, destruir):
        GlobalSetting.objects.create(key='maintenance_mode', value='true')
        manutencao.invalidar()
        self.addCleanup(manutencao.invalidar)

        resposta = self.client.post(ROTA, HTTP_AUTHORIZATION=f'Bearer {TOKEN}')

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(User.objects.filter(pk=self.vencida.pk).exists())

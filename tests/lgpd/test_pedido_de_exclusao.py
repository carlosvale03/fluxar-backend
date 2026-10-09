"""
Pedido de exclusão da própria conta (LGPD-03 a LGPD-06, LGPD-09).

O envio do e-mail é simulado na view; o conteúdo do aviso é conferido com o
envio dos provedores simulado.
"""
import datetime
from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from api.models import Sessao, User
from api.sessoes import criar_sessao
from api.utils import email_service

PEDIR = '/api/users/me/delete/'
ME = '/api/auth/me/'
SENHA = 'senha-de-teste-123'
ULTIMO_ADMIN = 'O sistema precisa ter pelo menos um administrador ativo.'


@mock.patch('api.views.send_account_deletion_email', return_value=True)
class PedidoDeExclusaoTests(APITestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(
            email='cliente@teste.fluxar', password=SENHA, name='Cliente', email_verified=True,
        )

    def entrar(self, usuario):
        """Abre uma sessão de verdade e devolve o token de acesso."""
        acesso, _ = criar_sessao(usuario)
        return acesso

    def pedir(self, acesso, dados):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {acesso}')
        return self.client.post(PEDIR, dados, format='json')

    def assertContaIntacta(self, usuario):
        usuario.refresh_from_db()
        self.assertTrue(usuario.is_active)
        self.assertIsNone(usuario.exclusao_pedida_em)
        self.assertIsNone(usuario.exclusao_agendada_para)
        self.assertFalse(Sessao.objects.filter(user=usuario, encerrada_em__isnull=False).exists())

    # LGPD-03, LGPD-04 ------------------------------------------------------

    def test_senha_errada_recebe_400_no_campo_e_a_conta_nao_muda(self, envio):
        resposta = self.pedir(self.entrar(self.usuario), {'password': 'senha-errada'})

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data, {'password': ['Senha incorreta.']})
        self.assertContaIntacta(self.usuario)
        envio.assert_not_called()

    def test_sem_a_senha_recebe_400_no_campo(self, envio):
        resposta = self.pedir(self.entrar(self.usuario), {})

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data, {'password': ['Este campo é obrigatório.']})
        self.assertContaIntacta(self.usuario)

    # LGPD-05 ---------------------------------------------------------------

    def test_senha_certa_desativa_encerra_as_sessoes_e_agenda_para_30_dias(self, envio):
        outro_aparelho = self.entrar(self.usuario)
        antes = timezone.now()

        resposta = self.pedir(self.entrar(self.usuario), {'password': SENHA})

        depois = timezone.now()
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_active)
        self.assertTrue(antes <= self.usuario.exclusao_pedida_em <= depois)
        self.assertEqual(
            self.usuario.exclusao_agendada_para, self.usuario.exclusao_pedida_em + timedelta(days=30),
        )
        self.assertEqual(
            resposta.data['deletion_scheduled_for'],
            self.usuario.exclusao_agendada_para.isoformat().replace('+00:00', 'Z'),
        )
        # Nenhuma sessão continua aberta, nem a do outro aparelho
        self.assertEqual(Sessao.objects.filter(user=self.usuario).count(), 2)
        self.assertFalse(Sessao.objects.filter(user=self.usuario, encerrada_em__isnull=True).exists())
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {outro_aparelho}')
        self.assertEqual(self.client.get(ME).status_code, 401)

    # LGPD-06 ---------------------------------------------------------------

    def test_envia_o_email_com_a_data_da_exclusao(self, envio):
        resposta = self.pedir(self.entrar(self.usuario), {'password': SENHA})

        self.usuario.refresh_from_db()
        envio.assert_called_once()
        usuario_enviado, data_enviada = envio.call_args.args
        self.assertEqual(usuario_enviado.pk, self.usuario.pk)
        self.assertEqual(data_enviada, self.usuario.exclusao_agendada_para)
        self.assertIs(resposta.data['email_sent'], True)

    def test_com_o_envio_falhando_o_pedido_vale_igual(self, envio):
        envio.return_value = False

        resposta = self.pedir(self.entrar(self.usuario), {'password': SENHA})

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertIs(resposta.data['email_sent'], False)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_active)
        self.assertIsNotNone(self.usuario.exclusao_agendada_para)
        self.assertFalse(Sessao.objects.filter(user=self.usuario, encerrada_em__isnull=True).exists())

    # LGPD-09 ---------------------------------------------------------------

    def test_unico_admin_ativo_recebe_400_e_a_conta_nao_muda(self, envio):
        admin = User.objects.create_superuser(email='admin@teste.fluxar', password=SENHA, name='Admin')

        resposta = self.pedir(self.entrar(admin), {'password': SENHA})

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data['detail'], ULTIMO_ADMIN)
        self.assertContaIntacta(admin)
        envio.assert_not_called()

    def test_admin_com_outro_admin_ativo_pode_pedir(self, envio):
        admin = User.objects.create_superuser(email='admin@teste.fluxar', password=SENHA, name='Admin')
        User.objects.create_superuser(email='outro.admin@teste.fluxar', password=SENHA, name='Outro')

        resposta = self.pedir(self.entrar(admin), {'password': SENHA})

        self.assertEqual(resposta.status_code, 200, resposta.data)
        admin.refresh_from_db()
        self.assertFalse(admin.is_active)


@override_settings(FRONTEND_URL='https://app.fluxar.teste')
class EmailDoPedidoTests(TestCase):

    def test_aviso_traz_a_data_e_como_desistir(self):
        usuario = User(email='cliente@teste.fluxar', name='Cliente')
        data = datetime.datetime(2026, 11, 8, 14, 30, tzinfo=datetime.timezone.utc)

        with mock.patch.object(email_service, '_send_with_fallback_chain', return_value=True) as cadeia:
            enviado = email_service.send_account_deletion_email(usuario, data)

        self.assertIs(enviado, True)
        argumentos = cadeia.call_args.kwargs
        self.assertEqual(argumentos['to_email'], 'cliente@teste.fluxar')
        for texto in (argumentos['html_content'], argumentos['plain_text']):
            self.assertIn('08/11/2026', texto)
            self.assertIn('https://app.fluxar.teste/auth/login', texto)
        self.assertIn('Cancelar exclusão', argumentos['html_content'])
        self.assertIn('Cancelar exclusao', argumentos['plain_text'])

"""
Serviço de e-mail transacional (AUTH-24, AUTH-25, AUTH-28, AUTH-29 e AUTH-30).

Nenhum teste envia e-mail de verdade: a chamada HTTP (Resend e EmailJS) é
simulada, e o SMTP usa o backend em memória do runner de testes ou um backend
de teste que sempre falha.
"""
import smtplib
from datetime import timedelta
from unittest import mock

import requests
from django.core import mail
from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend
from django.test import TestCase, override_settings
from django.utils import timezone

from api.models import EmailVerificationToken, PasswordResetToken, User
from api.utils import email_service
from api.utils.email_service import send_password_reset_email, send_verification_email

NOME_MALICIOSO = '<a href="x">clique</a>'
NOME_ESCAPADO = '&lt;a href=&quot;x&quot;&gt;clique&lt;/a&gt;'
EMAIL = 'ana.teste@fluxar.teste'
EMAIL_MASCARADO = 'an***@fluxar.teste'
FRONTEND = 'https://app.fluxar.teste'
LOGGER = 'api.utils.email_service'
BACKEND_QUE_FALHA = 'tests.autenticacao.test_email.BackendQueFalha'
EMAILJS_CONFIGURADO = {
    'EMAILJS_SERVICE_ID': 'servico-de-teste',
    'EMAILJS_TEMPLATE_ID': 'modelo-de-teste',
    'EMAILJS_PUBLIC_KEY': 'publica-de-teste',
    'EMAILJS_PRIVATE_KEY': 'privada-de-teste',
}


class BackendQueFalha(BaseEmailBackend):
    """Backend SMTP de teste que sempre falha, como um servidor fora do ar."""

    def send_messages(self, email_messages):
        raise smtplib.SMTPServerDisconnected('servidor de teste fora do ar')


def resposta(status):
    return mock.Mock(status_code=status)


class RelogioFalso:
    """Substitui o time.monotonic do serviço; o Resend simulado avança o relógio."""

    def __init__(self):
        self.agora = 1000.0

    def monotonic(self):
        return self.agora


@override_settings(
    FRONTEND_URL=FRONTEND,
    DEFAULT_FROM_EMAIL='Fluxar <nao-responda@fluxar.teste>',
    ENABLE_RESEND_PROVIDER=True,
    ENABLE_SMTP_FALLBACK=True,
    USE_EMAILJS_TESTING_FALLBACK=False,
)
@mock.patch.dict('os.environ', {'RESEND_API_KEY': 'chave-resend-de-teste'})
class ServicoDeEmailTests(TestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(
            email=EMAIL, password='senha-de-teste-123', name=NOME_MALICIOSO,
        )
        self.verificacao = EmailVerificationToken.objects.create(
            user=self.usuario, expires_at=timezone.now() + timedelta(hours=24),
        )
        self.redefinicao = PasswordResetToken.objects.create(
            user=self.usuario, expires_at=timezone.now() + timedelta(hours=1),
        )
        patcher = mock.patch.object(email_service.requests, 'post')
        self.post = patcher.start()
        self.addCleanup(patcher.stop)

    def payload_do_resend(self):
        self.assertEqual(self.post.call_args.args[0], email_service.RESEND_API_URL)
        return self.post.call_args.kwargs['json']

    def urls_chamadas(self):
        return [chamada.args[0] for chamada in self.post.call_args_list]

    # AUTH-24 -----------------------------------------------------------

    def test_nome_escapado_no_email_de_verificacao(self):
        self.post.return_value = resposta(200)

        self.assertTrue(send_verification_email(self.usuario, self.verificacao))

        payload = self.payload_do_resend()
        self.assertIn(NOME_ESCAPADO, payload['html'])
        self.assertNotIn(NOME_MALICIOSO, payload['html'])
        self.assertIn(NOME_ESCAPADO, payload['text'])
        self.assertNotIn(NOME_MALICIOSO, payload['text'])
        # O link do botão continua sendo um link de verdade
        link = f'{FRONTEND}/auth/verify-email?token={self.verificacao.token}'
        self.assertIn(f'<a href="{link}"', payload['html'])

    def test_nome_escapado_no_email_de_redefinicao(self):
        self.post.return_value = resposta(200)

        self.assertTrue(send_password_reset_email(self.usuario, self.redefinicao))

        payload = self.payload_do_resend()
        self.assertIn(NOME_ESCAPADO, payload['html'])
        self.assertNotIn(NOME_MALICIOSO, payload['html'])
        self.assertIn(NOME_ESCAPADO, payload['text'])
        self.assertNotIn(NOME_MALICIOSO, payload['text'])
        link = f'{FRONTEND}/auth/reset-password?token={self.redefinicao.token}'
        self.assertIn(f'<a href="{link}"', payload['html'])

    # AUTH-25 -----------------------------------------------------------

    def test_resend_falhando_envia_pelo_smtp_e_registra_a_falha(self):
        self.post.return_value = resposta(500)

        with self.assertLogs(LOGGER, level='INFO') as logs:
            enviado = send_verification_email(self.usuario, self.verificacao)

        self.assertIs(enviado, True)
        self.assertEqual(len(mail.outbox), 1)
        mensagem = mail.outbox[0]
        self.assertEqual(mensagem.to, [EMAIL])
        html, tipo = mensagem.alternatives[0]
        self.assertEqual(tipo, 'text/html')
        self.assertIn(NOME_ESCAPADO, html)
        self.assertNotIn(NOME_MALICIOSO, html)
        self.assertNotIn(NOME_MALICIOSO, mensagem.body)
        saida = '\n'.join(logs.output)
        self.assertIn('provedor=resend resultado=falha', saida)
        self.assertIn('provedor=smtp resultado=enviado', saida)

    @override_settings(EMAIL_BACKEND=BACKEND_QUE_FALHA)
    def test_os_dois_provedores_falhando_devolve_false(self):
        self.post.side_effect = requests.ConnectionError('resend fora do ar')

        with self.assertLogs(LOGGER, level='INFO') as logs:
            enviado = send_verification_email(self.usuario, self.verificacao)

        self.assertIs(enviado, False)
        self.assertEqual(mail.outbox, [])
        saida = '\n'.join(logs.output)
        self.assertIn('provedor=resend resultado=falha', saida)
        self.assertIn('provedor=smtp resultado=falha', saida)
        self.assertIn('resultado=nao_enviado', saida)

    def test_prazo_do_smtp_e_o_que_sobra_dos_10_segundos(self):
        relogio = RelogioFalso()

        def resend_demorando(*args, **kwargs):
            relogio.agora += 7
            raise requests.Timeout('resend demorou')

        self.post.side_effect = resend_demorando
        with mock.patch.object(email_service.time, 'monotonic', relogio.monotonic), \
                mock.patch.object(email_service, 'get_connection', wraps=get_connection) as conexao:
            enviado = send_verification_email(self.usuario, self.verificacao)

        self.assertIs(enviado, True)
        self.assertAlmostEqual(self.post.call_args.kwargs['timeout'], 10)
        self.assertEqual(conexao.call_count, 1)
        self.assertAlmostEqual(conexao.call_args.kwargs['timeout'], 3)
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_esgotando_o_prazo_nao_tenta_o_smtp(self):
        relogio = RelogioFalso()

        def resend_demorando(*args, **kwargs):
            relogio.agora += 10.5
            raise requests.Timeout('resend demorou')

        self.post.side_effect = resend_demorando
        with mock.patch.object(email_service.time, 'monotonic', relogio.monotonic), \
                mock.patch.object(email_service, 'get_connection', wraps=get_connection) as conexao, \
                self.assertLogs(LOGGER, level='INFO') as logs:
            enviado = send_verification_email(self.usuario, self.verificacao)

        self.assertIs(enviado, False)
        conexao.assert_not_called()
        self.assertEqual(mail.outbox, [])
        self.assertIn('provedor=smtp resultado=sem_tempo', '\n'.join(logs.output))

    # AUTH-29 -----------------------------------------------------------

    @override_settings(
        DEBUG=False, USE_EMAILJS_TESTING_FALLBACK=True,
        EMAIL_BACKEND=BACKEND_QUE_FALHA, **EMAILJS_CONFIGURADO,
    )
    def test_com_debug_desligado_o_emailjs_nunca_e_chamado(self):
        self.post.return_value = resposta(500)

        self.assertIs(send_verification_email(self.usuario, self.verificacao), False)
        self.assertIs(send_password_reset_email(self.usuario, self.redefinicao), False)

        self.assertNotIn(email_service.EMAILJS_API_URL, self.urls_chamadas())
        self.assertEqual(
            self.urls_chamadas(), [email_service.RESEND_API_URL, email_service.RESEND_API_URL],
        )

    @override_settings(
        DEBUG=True, USE_EMAILJS_TESTING_FALLBACK=True,
        EMAIL_BACKEND=BACKEND_QUE_FALHA, **EMAILJS_CONFIGURADO,
    )
    def test_emailjs_so_entra_com_debug_e_a_flag_de_teste(self):
        self.post.side_effect = [resposta(500), resposta(200)]

        self.assertIs(send_verification_email(self.usuario, self.verificacao), True)
        self.assertEqual(
            self.urls_chamadas(), [email_service.RESEND_API_URL, email_service.EMAILJS_API_URL],
        )
        parametros = self.post.call_args.kwargs['json']['template_params']
        self.assertEqual(parametros['to_name'], NOME_ESCAPADO)

        self.post.reset_mock(side_effect=True)
        self.post.return_value = resposta(500)
        with self.settings(USE_EMAILJS_TESTING_FALLBACK=False):
            self.assertIs(send_verification_email(self.usuario, self.verificacao), False)
        self.assertEqual(self.urls_chamadas(), [email_service.RESEND_API_URL])

    # AUTH-28 -----------------------------------------------------------

    def test_logs_trazem_tipo_provedor_resultado_e_email_mascarado(self):
        self.post.return_value = resposta(500)

        with self.assertLogs(LOGGER, level='DEBUG') as logs:
            send_password_reset_email(self.usuario, self.redefinicao)
            send_verification_email(self.usuario, self.verificacao)

        saida = '\n'.join(logs.output)
        self.assertIn(
            'tipo=redefinicao provedor=resend resultado=falha erro=RuntimeError '
            f'destinatario={EMAIL_MASCARADO}',
            saida,
        )
        self.assertIn(
            f'tipo=redefinicao provedor=smtp resultado=enviado destinatario={EMAIL_MASCARADO}',
            saida,
        )
        self.assertIn(
            f'tipo=verificacao provedor=smtp resultado=enviado destinatario={EMAIL_MASCARADO}',
            saida,
        )
        # AD-019: nenhum e-mail inteiro, nome ou token nos logs
        self.assertNotIn(EMAIL, saida)
        self.assertNotIn('clique', saida)
        self.assertNotIn(str(self.redefinicao.token)[:8], saida)
        self.assertNotIn(str(self.verificacao.token)[:8], saida)

    # AUTH-30 -----------------------------------------------------------

    @override_settings(FRONTEND_URL='https://outro-frontend.fluxar.teste/')
    def test_link_usa_o_frontend_url_configurado(self):
        self.post.return_value = resposta(200)

        send_verification_email(self.usuario, self.verificacao)
        html_verificacao = self.payload_do_resend()['html']
        send_password_reset_email(self.usuario, self.redefinicao)
        html_redefinicao = self.payload_do_resend()['html']

        self.assertIn(
            f'https://outro-frontend.fluxar.teste/auth/verify-email?token={self.verificacao.token}',
            html_verificacao,
        )
        self.assertIn(
            f'https://outro-frontend.fluxar.teste/auth/reset-password?token={self.redefinicao.token}',
            html_redefinicao,
        )
        self.assertNotIn('localhost', html_verificacao + html_redefinicao)

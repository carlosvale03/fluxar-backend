"""
Login durante o prazo da exclusão e cancelamento (LGPD-07, LGPD-08).

O login de uma conta com exclusão marcada não abre a sessão: devolve a data
da exclusão definitiva e um token de 15 minutos para cancelar. O
cancelamento reativa a conta e abre a sessão como o login.
"""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core import signing
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from accounts.models import Account
from api.cookies import NOME_DO_COOKIE
from api.models import PasswordResetToken, Sessao, User

LOGIN = '/api/auth/login/'
CANCELAR = '/api/auth/cancel-deletion/'
ESQUECI = '/api/auth/forgot-password/'
REDEFINIR = '/api/auth/reset-password/'
SENHA = 'senha-de-teste-123'
EMAIL = 'cliente@teste.fluxar'


class ExclusaoPendenteTestCase(APITestCase):

    def setUp(self):
        cache.clear()
        self.pedida_em = timezone.now() - timedelta(days=2)
        self.usuario = User.objects.create_user(
            email=EMAIL, password=SENHA, name='Cliente', email_verified=True,
            is_active=False, exclusao_pedida_em=self.pedida_em,
            exclusao_agendada_para=self.pedida_em + timedelta(days=30),
        )
        self.conta = Account.objects.create(
            user=self.usuario, name='Corrente', type='CHECKING', initial_balance=Decimal('1500.00'),
        )

    def entrar(self, senha=SENHA):
        return self.client.post(LOGIN, {'email': EMAIL, 'password': senha}, format='json')

    def cancelar(self, token):
        return self.client.post(CANCELAR, {'cancel_token': token}, format='json')


class LoginDuranteOPrazoTests(ExclusaoPendenteTestCase):

    def test_senha_certa_responde_deletion_pending_com_a_data_e_o_token_sem_sessao(self):
        resposta = self.entrar()

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data['code'], 'deletion_pending')
        self.assertEqual(
            resposta.data['deletion_scheduled_for'],
            self.usuario.exclusao_agendada_para.isoformat().replace('+00:00', 'Z'),
        )
        self.assertTrue(resposta.data['cancel_token'])
        self.assertNotIn('access', resposta.data)
        self.assertNotIn(NOME_DO_COOKIE, resposta.cookies)
        self.assertFalse(Sessao.objects.exists())

    def test_senha_errada_continua_invalid_credentials(self):
        resposta = self.entrar('senha-errada')

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data, {'detail': 'E-mail ou senha incorretos.', 'code': 'invalid_credentials'})

    def test_conta_desativada_sem_exclusao_continua_account_disabled(self):
        self.usuario.exclusao_pedida_em = None
        self.usuario.exclusao_agendada_para = None
        self.usuario.save()

        resposta = self.entrar()

        self.assertEqual(resposta.data['code'], 'account_disabled')


class CancelamentoTests(ExclusaoPendenteTestCase):

    def test_cancelar_reativa_com_os_dados_limpa_as_datas_e_abre_a_sessao(self):
        token = self.entrar().data['cancel_token']

        resposta = self.cancelar(token)

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_active)
        self.assertIsNone(self.usuario.exclusao_pedida_em)
        self.assertIsNone(self.usuario.exclusao_agendada_para)
        self.assertTrue(Account.objects.filter(pk=self.conta.pk, user=self.usuario).exists())
        # O acesso no corpo e a renovação só no cookie, da mesma sessão aberta
        self.assertNotIn('refresh', resposta.data)
        acesso = AccessToken(resposta.data['access'])
        cookie = resposta.cookies[NOME_DO_COOKIE]
        self.assertIs(cookie['httponly'], True)
        sessao = Sessao.objects.get(pk=acesso['sid'])
        self.assertEqual(sessao.user, self.usuario)
        self.assertIsNone(sessao.encerrada_em)
        self.assertEqual(RefreshToken(cookie.value)['sid'], str(sessao.id))
        # A sessão vale nas rotas protegidas
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resposta.data['access']}")
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 200)

    def test_token_vencido_recebe_400(self):
        token = self.entrar().data['cancel_token']

        daqui_a_16_minutos = timezone.now().timestamp() + 16 * 60
        with mock.patch('django.core.signing.time.time', return_value=daqui_a_16_minutos):
            resposta = self.cancelar(token)

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data['code'], 'invalid_cancel_token')
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_active)
        self.assertIsNotNone(self.usuario.exclusao_agendada_para)
        self.assertFalse(Sessao.objects.exists())

    def test_token_adulterado_ou_de_outro_uso_recebe_400(self):
        token = self.entrar().data['cancel_token']
        sem_o_salt = signing.dumps({'u': str(self.usuario.pk), 'p': self.pedida_em.isoformat()})

        for invalido in (token[:-2] + 'xx', sem_o_salt, '', None):
            with self.subTest(token=invalido):
                resposta = self.cancelar(invalido)
                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.data['code'], 'invalid_cancel_token')
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_active)
        self.assertFalse(Sessao.objects.exists())


@mock.patch('api.views.send_password_reset_email', return_value=True)
class EsqueciASenhaDuranteOPrazoTests(ExclusaoPendenteTestCase):

    def test_redefinir_a_senha_funciona_e_nao_cancela_a_exclusao(self, envio):
        self.assertEqual(self.client.post(ESQUECI, {'email': EMAIL}, format='json').status_code, 200)
        envio.assert_called_once()
        link = PasswordResetToken.objects.get(user=self.usuario, used=False)

        resposta = self.client.post(REDEFINIR, {
            'token': str(link.token), 'new_password': 'Outra-Senha-Forte-2026',
            'new_password_confirm': 'Outra-Senha-Forte-2026',
        }, format='json')

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('Outra-Senha-Forte-2026'))
        self.assertFalse(self.usuario.is_active)
        self.assertEqual(self.usuario.exclusao_pedida_em, self.pedida_em)
        # Com a senha nova, o login continua oferecendo o cancelamento
        self.assertEqual(self.entrar('Outra-Senha-Forte-2026').data['code'], 'deletion_pending')

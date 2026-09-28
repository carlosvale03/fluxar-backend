"""
Redefinição de senha por link (AUTH-20 a AUTH-22).

Todo link inválido recebe a mesma resposta: HTTP 400 com
"Link inválido ou expirado." e o código invalid_link. Os erros da senha nova
ficam no campo new_password.
"""
import uuid
from datetime import timedelta
from unittest import mock

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import PasswordResetToken, User

REDEFINIR = '/api/auth/reset-password/'
LOGIN = '/api/auth/login/'
SENHA_ANTIGA = 'Cofre-Azul-2026'
SENHA_NOVA = 'Trilha-Verde-2027'
LINK_INVALIDO = {'detail': 'Link inválido ou expirado.', 'code': 'invalid_link'}
SUCESSO = {'message': 'Senha redefinida com sucesso.'}
AUSENTE = object()


class RedefinicaoPorLinkTests(APITestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(
            email='ricardo@fluxar.teste', password=SENHA_ANTIGA, name='Ricardo Almeida',
            email_verified=True,
        )
        self.token = PasswordResetToken.objects.create(
            user=self.usuario, expires_at=timezone.now() + timedelta(hours=1),
        )

    def redefinir(self, token=None, senha=SENHA_NOVA, confirmacao=None):
        corpo = {
            'token': str(self.token.token) if token is None else token,
            'new_password': senha,
            'new_password_confirm': senha if confirmacao is None else confirmacao,
        }
        corpo = {chave: valor for chave, valor in corpo.items() if valor is not AUSENTE}
        return self.client.post(REDEFINIR, corpo, format='json')

    def entrar(self, senha):
        return self.client.post(LOGIN, {'email': 'ricardo@fluxar.teste', 'password': senha}, format='json')

    def assertSenhaNaoMudou(self):
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(SENHA_ANTIGA))
        self.assertFalse(self.usuario.check_password(SENHA_NOVA))

    def assertLinkInvalido(self, resposta):
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resposta.data, LINK_INVALIDO)
        self.assertSenhaNaoMudou()

    def assertSenhaRecusada(self, resposta, mensagens):
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual([str(m) for m in resposta.data['new_password']], mensagens)
        self.assertNotIn('new_password_confirm', resposta.data)
        self.assertSenhaNaoMudou()
        self.token.refresh_from_db()
        self.assertFalse(self.token.used)

    # AUTH-20 -----------------------------------------------------------

    def test_link_valido_troca_a_senha_e_entra_com_a_nova(self):
        resposta = self.redefinir()

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data, SUCESSO)
        self.token.refresh_from_db()
        self.assertTrue(self.token.used)
        self.assertEqual(self.entrar(SENHA_NOVA).status_code, status.HTTP_200_OK)
        self.assertEqual(self.entrar(SENHA_ANTIGA).status_code, status.HTTP_400_BAD_REQUEST)

    def test_conta_pendente_tem_o_email_confirmado_e_entra(self):
        User.objects.filter(pk=self.usuario.pk).update(email_verified=False)

        resposta = self.redefinir()

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.email_verified)
        self.assertTrue(self.usuario.is_active)
        self.assertEqual(self.entrar(SENHA_NOVA).status_code, status.HTTP_200_OK)

    def test_conta_desativada_continua_desativada(self):
        User.objects.filter(pk=self.usuario.pk).update(is_active=False, email_verified=False)

        resposta = self.redefinir()

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_active)
        self.assertTrue(self.usuario.email_verified)
        self.assertTrue(self.usuario.check_password(SENHA_NOVA))
        self.assertEqual(self.entrar(SENHA_NOVA).data['code'], 'account_disabled')

    # AUTH-21 -----------------------------------------------------------

    def test_link_reaberto_depois_de_usado_recusado(self):
        self.assertEqual(self.redefinir().status_code, status.HTTP_200_OK)

        resposta = self.redefinir(senha='Outra-Senha-Boa-99')

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resposta.data, LINK_INVALIDO)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(SENHA_NOVA))

    def test_link_vencido_recusado(self):
        daqui_a_61_minutos = timezone.now() + timedelta(minutes=61)

        with mock.patch('django.utils.timezone.now', return_value=daqui_a_61_minutos):
            resposta = self.redefinir()

        self.assertLinkInvalido(resposta)
        self.token.refresh_from_db()
        self.assertFalse(self.token.used)

    def test_link_inexistente_recusado(self):
        self.assertLinkInvalido(self.redefinir(token=str(uuid.uuid4())))

    def test_link_malformado_recusado_sem_erro_500(self):
        self.assertLinkInvalido(self.redefinir(token='nao-e-um-uuid'))

    def test_link_ausente_recusado(self):
        self.assertLinkInvalido(self.redefinir(token=AUSENTE))

    # AUTH-22 -----------------------------------------------------------

    def test_senha_curta_recusada_no_campo_da_senha(self):
        self.assertSenhaRecusada(
            self.redefinir(senha='Ab1!xyz'),
            ['Esta senha é muito curta. Ela precisa conter pelo menos 8 caracteres.'],
        )

    def test_senha_parecida_com_o_nome_do_dono_do_link_recusada(self):
        self.assertSenhaRecusada(
            self.redefinir(senha='ricardoalmeida'), ['A senha é muito parecida com nome.'],
        )

    def test_senha_comum_recusada(self):
        self.assertSenhaRecusada(self.redefinir(senha='qwertyuiop'), ['Esta senha é muito comum.'])

    def test_senha_so_com_numeros_recusada(self):
        self.assertSenhaRecusada(
            self.redefinir(senha='83920174'), ['Esta senha é inteiramente numérica.'],
        )

    def test_confirmacao_diferente_recusada_no_campo_da_senha(self):
        self.assertSenhaRecusada(
            self.redefinir(confirmacao='Trilha-Azul-2027'), ['As senhas não coincidem.'],
        )

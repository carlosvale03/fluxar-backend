"""
Cadastro (AUTH-01 a AUTH-06 e AUTH-26).

Nenhum teste envia e-mail de verdade: o envio da verificação é simulado na view.
"""
from datetime import timedelta
from unittest import mock

from django.db import IntegrityError
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import EmailVerificationToken, User

REGISTRO = '/api/auth/register/'
SENHA = 'Cofre-Azul-2026'
EMAIL_JA_CADASTRADO = 'Este e-mail já está cadastrado. Se a conta é sua, use "Esqueci a senha".'
EMAIL_NAO_ENVIADO = (
    'Conta criada, mas não conseguimos enviar o e-mail de verificação. Use "Reenviar e-mail".'
)
AUSENTE = object()


def dados(**campos):
    corpo = {
        'name': 'Ricardo Almeida',
        'email': 'ricardo@fluxar.teste',
        'password': SENHA,
        'password_confirm': SENHA,
        'terms_accepted': True,
    }
    corpo.update(campos)
    return {chave: valor for chave, valor in corpo.items() if valor is not AUSENTE}


@mock.patch('api.views.send_verification_email', return_value=True)
class ValidacaoDoCadastroTests(APITestCase):

    def cadastrar(self, **campos):
        return self.client.post(REGISTRO, dados(**campos), format='json')

    def assertRecusado(self, resposta, campo):
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(campo, resposta.data)
        return [str(mensagem) for mensagem in resposta.data[campo]]

    # AUTH-03 -----------------------------------------------------------

    def test_email_ja_cadastrado_recusado_no_campo_email(self, envio):
        User.objects.create_user(email='ricardo@fluxar.teste', password=SENHA, name='Outro')

        resposta = self.cadastrar()

        self.assertEqual(self.assertRecusado(resposta, 'email'), [EMAIL_JA_CADASTRADO])
        self.assertEqual(User.objects.filter(email__iexact='ricardo@fluxar.teste').count(), 1)
        envio.assert_not_called()

    def test_email_ja_cadastrado_com_outra_caixa_recusado(self, envio):
        User.objects.create_user(email='ana@x.com', password=SENHA, name='Ana')

        resposta = self.cadastrar(email='ANA@X.COM')

        self.assertEqual(self.assertRecusado(resposta, 'email'), [EMAIL_JA_CADASTRADO])
        self.assertEqual(User.objects.filter(email__iexact='ana@x.com').count(), 1)

    def test_conta_antiga_com_maiusculas_bloqueia_o_mesmo_email_em_minusculas(self, envio):
        antiga = User.objects.create_user(email='caio@x.com', password=SENHA, name='Caio')
        # Conta de antes da correção, gravada com maiúsculas
        User.objects.filter(pk=antiga.pk).update(email='Caio@x.com')

        resposta = self.cadastrar(email='caio@x.com')

        self.assertEqual(self.assertRecusado(resposta, 'email'), [EMAIL_JA_CADASTRADO])
        self.assertEqual(User.objects.filter(email__iexact='caio@x.com').count(), 1)

    # AUTH-04 -----------------------------------------------------------

    def test_senha_curta_recusada_no_campo_senha(self, envio):
        resposta = self.cadastrar(password='Ab1!xyz', password_confirm='Ab1!xyz')

        self.assertEqual(
            self.assertRecusado(resposta, 'password'),
            ['Esta senha é muito curta. Ela precisa conter pelo menos 8 caracteres.'],
        )
        self.assertFalse(User.objects.filter(email='ricardo@fluxar.teste').exists())

    def test_senha_parecida_com_o_nome_recusada(self, envio):
        resposta = self.cadastrar(
            email='contato@fluxar.teste', password='ricardoalmeida', password_confirm='ricardoalmeida',
        )

        self.assertEqual(
            self.assertRecusado(resposta, 'password'), ['A senha é muito parecida com nome.'],
        )
        self.assertFalse(User.objects.filter(email='contato@fluxar.teste').exists())

    def test_senha_parecida_com_o_email_recusada(self, envio):
        resposta = self.cadastrar(
            name='Ana', email='girassol@fluxar.teste',
            password='girassol2026', password_confirm='girassol2026',
        )

        self.assertEqual(
            self.assertRecusado(resposta, 'password'), ['A senha é muito parecida com e-mail.'],
        )

    def test_senha_comum_recusada(self, envio):
        resposta = self.cadastrar(password='qwertyuiop', password_confirm='qwertyuiop')

        self.assertEqual(self.assertRecusado(resposta, 'password'), ['Esta senha é muito comum.'])

    def test_senha_so_com_numeros_recusada(self, envio):
        resposta = self.cadastrar(password='83920174', password_confirm='83920174')

        self.assertEqual(self.assertRecusado(resposta, 'password'), ['Esta senha é inteiramente numérica.'])

    def test_confirmacao_diferente_recusada_no_campo_senha(self, envio):
        resposta = self.cadastrar(password_confirm='Cofre-Verde-2026')

        self.assertEqual(self.assertRecusado(resposta, 'password'), ['As senhas não coincidem.'])
        self.assertNotIn('password_confirm', resposta.data)
        self.assertFalse(User.objects.filter(email='ricardo@fluxar.teste').exists())

    # AUTH-04 e AUTH-07: o erro da senha aparece junto com o dos outros campos

    def test_email_invalido_e_senha_curta_devolvem_os_dois_erros(self, envio):
        resposta = self.cadastrar(email='nao-e-email', password='Ab1!xyz', password_confirm='Ab1!xyz')

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            [str(m) for m in resposta.data['email']], ['Insira um endereço de email válido.'],
        )
        self.assertEqual(
            [str(m) for m in resposta.data['password']],
            ['Esta senha é muito curta. Ela precisa conter pelo menos 8 caracteres.'],
        )

    def test_email_ja_cadastrado_e_senha_parecida_com_ele_devolvem_os_dois_erros(self, envio):
        User.objects.create_user(email='girassol@fluxar.teste', password=SENHA, name='Outro')

        resposta = self.cadastrar(
            name='Ana', email='girassol@fluxar.teste',
            password='girassol2026', password_confirm='girassol2026',
        )

        self.assertEqual([str(m) for m in resposta.data['email']], [EMAIL_JA_CADASTRADO])
        self.assertEqual(
            [str(m) for m in resposta.data['password']], ['A senha é muito parecida com e-mail.'],
        )

    def test_termos_ausentes_e_confirmacao_diferente_devolvem_os_dois_erros(self, envio):
        resposta = self.cadastrar(terms_accepted=AUSENTE, password_confirm='Cofre-Verde-2026')

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            [str(m) for m in resposta.data['terms_accepted']], ['É preciso aceitar os termos de uso.'],
        )
        self.assertEqual([str(m) for m in resposta.data['password']], ['As senhas não coincidem.'])
        self.assertFalse(User.objects.filter(email='ricardo@fluxar.teste').exists())

    # AUTH-05 -----------------------------------------------------------

    def test_termos_nao_aceitos_recusados(self, envio):
        resposta = self.cadastrar(terms_accepted=False)

        self.assertEqual(
            self.assertRecusado(resposta, 'terms_accepted'), ['É preciso aceitar os termos de uso.'],
        )
        self.assertFalse(User.objects.filter(email='ricardo@fluxar.teste').exists())

    def test_termos_ausentes_recusados(self, envio):
        resposta = self.cadastrar(terms_accepted=AUSENTE)

        self.assertEqual(
            self.assertRecusado(resposta, 'terms_accepted'), ['É preciso aceitar os termos de uso.'],
        )
        self.assertFalse(User.objects.filter(email='ricardo@fluxar.teste').exists())

    def test_nome_vazio_recusado(self, envio):
        resposta = self.cadastrar(name='   ')

        self.assertEqual(self.assertRecusado(resposta, 'name'), ['Informe o nome.'])
        self.assertFalse(User.objects.filter(email='ricardo@fluxar.teste').exists())

    def test_nome_com_mais_de_255_caracteres_recusado(self, envio):
        resposta = self.cadastrar(name='a' * 256)

        self.assertEqual(
            self.assertRecusado(resposta, 'name'), ['O nome pode ter no máximo 255 caracteres.'],
        )
        self.assertFalse(User.objects.filter(email='ricardo@fluxar.teste').exists())

    def test_nome_com_255_caracteres_aceito(self, envio):
        resposta = self.cadastrar(name='a' * 255)

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.get(email='ricardo@fluxar.teste').name, 'a' * 255)


@mock.patch('api.views.send_verification_email', return_value=True)
class CriacaoDaContaTests(APITestCase):

    def cadastrar(self, **campos):
        return self.client.post(REGISTRO, dados(**campos), format='json')

    # AUTH-01 -----------------------------------------------------------

    def test_cadastro_valido_cria_conta_pendente_com_link_de_24_horas_e_envia(self, envio):
        antes = timezone.now()
        resposta = self.cadastrar(email='Ricardo@Fluxar.teste')
        depois = timezone.now()

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        self.assertIs(resposta.data['email_sent'], True)
        self.assertEqual(
            resposta.data['message'],
            'Conta criada. Enviamos um link de verificação para o seu e-mail.',
        )
        usuario = User.objects.get(email='ricardo@fluxar.teste')
        self.assertFalse(usuario.email_verified)
        self.assertTrue(usuario.is_active)
        self.assertTrue(usuario.terms_accepted)
        self.assertTrue(usuario.check_password(SENHA))
        token = EmailVerificationToken.objects.get(user=usuario)
        self.assertFalse(token.used)
        self.assertGreaterEqual(token.expires_at, antes + timedelta(hours=24))
        self.assertLessEqual(token.expires_at, depois + timedelta(hours=24))
        envio.assert_called_once()
        usuario_enviado, token_enviado = envio.call_args.args
        self.assertEqual(usuario_enviado.pk, usuario.pk)
        self.assertEqual(token_enviado.pk, token.pk)

    def test_envio_na_propria_requisicao_sem_thread(self, envio):
        with mock.patch('threading.Thread') as thread:
            resposta = self.cadastrar()

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        thread.assert_not_called()
        envio.assert_called_once()

    # AUTH-26 -----------------------------------------------------------

    def test_provedores_falhando_mantem_a_conta_e_avisa(self, envio):
        envio.return_value = False

        resposta = self.cadastrar()

        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        self.assertIs(resposta.data['email_sent'], False)
        self.assertEqual(resposta.data['message'], EMAIL_NAO_ENVIADO)
        usuario = User.objects.get(email='ricardo@fluxar.teste')
        self.assertFalse(usuario.email_verified)
        self.assertTrue(usuario.is_active)
        self.assertTrue(EmailVerificationToken.objects.filter(user=usuario, used=False).exists())

    # AUTH-06 -----------------------------------------------------------

    def test_cadastro_simultaneo_com_integrity_error_responde_como_email_ja_cadastrado(self, envio):
        # Simula o outro pedido gravando o mesmo e-mail entre a validação e o INSERT
        with mock.patch.object(
            User.objects, 'create_user',
            side_effect=IntegrityError('duplicate key value violates unique constraint "api_user_email_key"'),
        ):
            resposta = self.cadastrar()

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual([str(m) for m in resposta.data['email']], [EMAIL_JA_CADASTRADO])
        self.assertFalse(User.objects.filter(email='ricardo@fluxar.teste').exists())
        self.assertFalse(EmailVerificationToken.objects.exists())
        envio.assert_not_called()

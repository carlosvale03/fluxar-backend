"""
Base dos testes do painel admin: um administrador autenticado e um usuário
comum, com nomes e e-mails que não podem aparecer no log (AD-019).
"""
from rest_framework.test import APITestCase

from api.models import SystemLog, User

SENHA = 'senha-de-teste-123'
SENHA_ERRADA = 'senha-errada-999'
NOME_DO_ADMIN = 'Admin Fulano de Tal'
EMAIL_DO_ADMIN = 'admin.teste@teste.fluxar'
ADMIN_MASCARADO = 'ad***@teste.fluxar'
NOME_DO_USUARIO = 'Cliente Beltrano'
EMAIL_DO_USUARIO = 'cliente@teste.fluxar'
USUARIO_MASCARADO = 'cl***@teste.fluxar'
SENHA_INCORRETA = {'admin_password': ['Senha do administrador incorreta.']}
DESTRUIR = 'cloudinary.uploader.destroy'
OK = {'result': 'ok'}


def criar_admin(email=EMAIL_DO_ADMIN, nome=NOME_DO_ADMIN):
    return User.objects.create_user(
        email=email, password=SENHA, name=nome, role='ADMIN', plan='PREMIUM_PLUS', email_verified=True,
    )


def criar_usuario(email=EMAIL_DO_USUARIO, nome=NOME_DO_USUARIO, **extras):
    extras.setdefault('email_verified', True)
    return User.objects.create_user(email=email, password=SENHA, name=nome, **extras)


def textos_do_registro(log):
    """Todo valor gravado num registro do log, como texto."""
    return ' '.join(str(getattr(log, campo.attname)) for campo in SystemLog._meta.fields)


class PainelAdminTestCase(APITestCase):

    def setUp(self):
        self.admin = criar_admin()
        self.usuario = criar_usuario()
        self.client.force_authenticate(user=self.admin)

    def logs(self, acao):
        return list(SystemLog.objects.filter(action=acao).order_by('timestamp'))

    def assert_sem_dado_pessoal(self, log):
        texto = textos_do_registro(log)
        for dado in (NOME_DO_ADMIN, 'Fulano', EMAIL_DO_ADMIN, NOME_DO_USUARIO, 'Beltrano', EMAIL_DO_USUARIO):
            self.assertNotIn(dado, texto)

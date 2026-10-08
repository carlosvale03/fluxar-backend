"""
Base dos testes de permissões e planos.

`criar_usuario` cria contas verificadas com a mesma senha; `criar_admin` cria
um administrador pelo papel, sem `is_staff` (AD-016).
"""
from django.core.cache import cache
from rest_framework.test import APITestCase

from api.models import User

SENHA = 'Cofre-Azul-2026'


def criar_usuario(apelido, **extra):
    campos = {'email_verified': True}
    campos.update(extra)
    return User.objects.create_user(
        email=f'{apelido}@permissoes.fluxar', password=SENHA, name=apelido.capitalize(), **campos,
    )


def criar_admin(apelido='admin', **extra):
    campos = {'role': 'ADMIN'}
    campos.update(extra)
    return criar_usuario(apelido, **campos)


class PermissoesTestCase(APITestCase):

    def setUp(self):
        cache.clear()

"""
Base dos testes das classes de despesa: usuários com o padrão do cadastro
(Essencial e Dispensável, CLASSE-01) e atalhos para as classes e categorias.
"""
from rest_framework.test import APITestCase

from api.models import User
from core.texto import normalizar
from transactions.models import Category, ClasseDeDespesa

SENHA = 'senha-de-teste-123'
ROTA = '/api/expense-classes/'

# Os erros sem campo levam o `code` do formato único da API (AD-024)
LIMITE_ATINGIDO = {'detail': 'Limite de 5 classes atingido.', 'code': 'invalid'}
NOME_REPETIDO = {'name': ['Já existe uma classe com esse nome.']}
CLASSE_PADRAO_FIXA = {'detail': 'As classes padrão não podem ser excluídas nem renomeadas.', 'code': 'invalid'}


def criar_usuario(email='ana@teste.fluxar', **extras):
    extras.setdefault('email_verified', True)
    return User.objects.create_user(email=email, password=SENHA, name='Pessoa de Teste', **extras)


def criar_classe(usuario, nome, cor='#123456'):
    return ClasseDeDespesa.objects.create(user=usuario, nome=nome, nome_normalizado=normalizar(nome), cor=cor)


def classe(usuario, nome):
    return ClasseDeDespesa.objects.get(user=usuario, nome=nome)


def categoria(usuario, nome, tipo='EXPENSE', **extras):
    return Category.objects.create(user=usuario, name=nome, type=tipo, **extras)


def detalhe(classe_):
    return f'{ROTA}{classe_.pk}/'


class ClassesTestCase(APITestCase):

    def setUp(self):
        self.ana = criar_usuario()
        self.client.force_authenticate(user=self.ana)

    def essencial(self, usuario=None):
        return classe(usuario or self.ana, 'Essencial')

    def dispensavel(self, usuario=None):
        return classe(usuario or self.ana, 'Dispensável')

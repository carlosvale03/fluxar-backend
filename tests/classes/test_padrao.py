"""
Classes no padrão do cadastro (CLASSE-01, CLASSE-24) e na limpeza dos dados
pelo administrador, que recria o padrão (AD-050).
"""
from unittest import mock

from django.test import TestCase

from api.limpeza import limpar_dados
from api.models import User
from transactions.models import Category, ClasseDeDespesa

SENHA = 'senha-de-teste-123'

ESSENCIAIS = {'Casa', 'Comida', 'Transporte', 'Educação'}
DISPENSAVEIS = {'Lazer', 'Eletrônicos', 'Doces', 'Doação', 'Presente'}


def criar_usuario(email='novo@teste.fluxar', **extras):
    return User.objects.create_user(email=email, password=SENHA, name='Pessoa Nova', **extras)


def classes(usuario):
    return sorted((c.nome, c.cor, c.padrao) for c in ClasseDeDespesa.objects.filter(user=usuario))


def classe_propria(usuario, nome, tipo='EXPENSE'):
    categoria = Category.objects.select_related('classe').get(user=usuario, name=nome, type=tipo)
    return categoria.classe.nome if categoria.classe_id else None


class PadraoDoCadastroTests(TestCase):

    def test_usuario_novo_tem_essencial_e_dispensavel(self):
        usuario = criar_usuario()

        self.assertEqual(classes(usuario), [('Dispensável', '#F97316', True), ('Essencial', '#16A34A', True)])

    def test_categorias_padrao_recebem_a_classe_inicial(self):
        usuario = criar_usuario()

        for nome in ESSENCIAIS:
            self.assertEqual(classe_propria(usuario, nome), 'Essencial', nome)
        for nome in DISPENSAVEIS:
            self.assertEqual(classe_propria(usuario, nome), 'Dispensável', nome)
        # A classe é do próprio usuário
        comida = Category.objects.get(user=usuario, name='Comida')
        self.assertEqual(comida.classe.user_id, usuario.pk)

    def test_subcategorias_de_casa_e_receitas_ficam_sem_classe_propria(self):
        usuario = criar_usuario()

        self.assertIsNone(classe_propria(usuario, 'Aluguel'))
        self.assertIsNone(classe_propria(usuario, 'Energia'))
        self.assertEqual(Category.objects.get(user=usuario, name='Aluguel').parent.name, 'Casa')
        for nome in ('Salário', 'Investimento', 'Pagamentos', 'Prêmio', 'Presente', 'Outros'):
            self.assertIsNone(classe_propria(usuario, nome, 'INCOME'), nome)

    def test_cada_usuario_recebe_as_proprias_classes(self):
        ana = criar_usuario('ana@teste.fluxar')
        bia = criar_usuario('bia@teste.fluxar')

        self.assertEqual(ClasseDeDespesa.objects.filter(user=ana).count(), 2)
        self.assertEqual(ClasseDeDespesa.objects.filter(user=bia).count(), 2)
        self.assertEqual(Category.objects.get(user=bia, name='Doces').classe.user_id, bia.pk)


@mock.patch('cloudinary.uploader.destroy', return_value={'result': 'ok'})
class LimpezaDasClassesTests(TestCase):

    def test_a_limpeza_termina_com_as_duas_classes_padrao_sem_duplicar(self, destruir):
        admin = criar_usuario('admin@teste.fluxar', role='ADMIN')
        usuario = criar_usuario()
        ClasseDeDespesa.objects.create(user=usuario, nome='Dívidas', nome_normalizado='dividas', cor='#111111')
        ClasseDeDespesa.objects.filter(user=usuario, nome='Essencial').update(cor='#000000')

        limpar_dados(usuario, admin)

        self.assertEqual(classes(usuario), [('Dispensável', '#F97316', True), ('Essencial', '#16A34A', True)])
        self.assertEqual(classe_propria(usuario, 'Comida'), 'Essencial')
        self.assertEqual(classe_propria(usuario, 'Doces'), 'Dispensável')

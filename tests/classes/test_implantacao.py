"""
Modelo das classes de despesa e implantação para quem já usa o app
(CLASSE-14, CLASSE-25).

A migração é chamada importando o módulo, com o registro de modelos atual.
Antes de cada teste, as classes são apagadas, como estava o banco antes das
classes existirem: as categorias perdem a classe própria junto.
"""
import importlib
from unittest import mock

from django.apps import apps
from django.test import TestCase

from api.exclusao import excluir_definitivamente
from api.models import RegistroDeExclusao, User
from core.texto import normalizar
from data_exchange.importacao import texto as texto_da_importacao
from transactions.models import Category, ClasseDeDespesa

# O nome do módulo começa com dígito, por isso o import_module
migracao = importlib.import_module('transactions.migrations.0013_classes_de_despesa')

SENHA = 'senha-de-teste-123'


def criar_usuario(email):
    return User.objects.create_user(email=email, password=SENHA, name='Pessoa de Teste')


def classes(usuario):
    """As classes do usuário como {nome: (cor, padrão)}."""
    return {c.nome: (c.cor, c.padrao) for c in ClasseDeDespesa.objects.filter(user=usuario)}


def classe_de(categoria):
    categoria.refresh_from_db()
    return categoria.classe.nome if categoria.classe_id else None


class ImplantacaoTests(TestCase):

    def setUp(self):
        self.ana = criar_usuario('ana@teste.fluxar')
        self.bia = criar_usuario('bia@teste.fluxar')
        # O banco como estava antes das classes
        ClasseDeDespesa.objects.all().delete()
        Category.objects.filter(user__in=[self.ana, self.bia]).delete()

    def implantar(self):
        migracao.implantar(apps, None)

    def test_cria_essencial_e_dispensavel_para_cada_usuario_existente(self):
        self.implantar()

        esperado = {'Essencial': ('#16A34A', True), 'Dispensável': ('#F97316', True)}
        self.assertEqual(classes(self.ana), esperado)
        self.assertEqual(classes(self.bia), esperado)

    def test_categoria_principal_de_despesa_com_nome_padrao_recebe_a_classe_inicial(self):
        comida = Category.objects.create(user=self.ana, name='comida', type='EXPENSE')
        eletronicos = Category.objects.create(user=self.ana, name='  ELETRONICOS ', type='EXPENSE')
        educacao = Category.objects.create(user=self.ana, name='Educação', type='EXPENSE')
        presente = Category.objects.create(user=self.ana, name='Presente', type='EXPENSE')
        mercado = Category.objects.create(user=self.ana, name='Mercado', type='EXPENSE')

        self.implantar()

        self.assertEqual(classe_de(comida), 'Essencial')
        self.assertEqual(classe_de(eletronicos), 'Dispensável')
        self.assertEqual(classe_de(educacao), 'Essencial')
        self.assertEqual(classe_de(presente), 'Dispensável')
        # Nome que não é de categoria padrão fica sem classe
        self.assertIsNone(classe_de(mercado))
        # A classe é a do próprio usuário
        comida.refresh_from_db()
        self.assertEqual(comida.classe.user_id, self.ana.pk)

    def test_subcategorias_e_categorias_de_receita_ficam_sem_classe_propria(self):
        mercado = Category.objects.create(user=self.ana, name='Mercado', type='EXPENSE')
        sub_comida = Category.objects.create(user=self.ana, name='Comida', type='EXPENSE', parent=mercado)
        casa = Category.objects.create(user=self.ana, name='Casa', type='EXPENSE')
        aluguel = Category.objects.create(user=self.ana, name='Aluguel', type='EXPENSE', parent=casa)
        presente_receita = Category.objects.create(user=self.ana, name='Presente', type='INCOME')

        self.implantar()

        self.assertIsNone(classe_de(sub_comida))
        self.assertIsNone(classe_de(aluguel))
        self.assertIsNone(classe_de(presente_receita))
        self.assertEqual(classe_de(casa), 'Essencial')

    def test_a_classe_inicial_vem_das_classes_do_proprio_usuario(self):
        doces_ana = Category.objects.create(user=self.ana, name='Doces', type='EXPENSE')
        doces_bia = Category.objects.create(user=self.bia, name='Doces', type='EXPENSE')

        self.implantar()

        doces_ana.refresh_from_db()
        doces_bia.refresh_from_db()
        self.assertEqual(doces_ana.classe.user_id, self.ana.pk)
        self.assertEqual(doces_bia.classe.user_id, self.bia.pk)
        self.assertEqual(ClasseDeDespesa.objects.filter(nome='Dispensável').count(), 2)


class ModeloDasClassesTests(TestCase):

    def test_a_normalizacao_da_importacao_e_a_de_core(self):
        self.assertIs(texto_da_importacao.normalizar, normalizar)
        self.assertEqual(normalizar(' Dívidas '), 'dividas')

    def test_excluir_a_classe_tira_a_classe_propria_das_categorias(self):
        usuario = criar_usuario('ana@teste.fluxar')
        classe = ClasseDeDespesa.objects.create(user=usuario, nome='Dívidas', nome_normalizado='dividas', cor='#000000')
        categoria = Category.objects.create(user=usuario, name='Empréstimo', type='EXPENSE', classe=classe)

        classe.delete()

        categoria.refresh_from_db()
        self.assertIsNone(categoria.classe_id)


@mock.patch('cloudinary.uploader.destroy', return_value={'result': 'ok'})
class ExclusaoDefinitivaDasClassesTests(TestCase):

    def test_a_exclusao_definitiva_apaga_as_classes_do_usuario(self, destruir):
        ana = criar_usuario('ana@teste.fluxar')
        bia = criar_usuario('bia@teste.fluxar')
        for usuario in (ana, bia):
            ClasseDeDespesa.objects.create(user=usuario, nome='Dívidas', nome_normalizado='dividas', cor='#000000')
        ana_id = ana.pk
        antes_da_bia = ClasseDeDespesa.objects.filter(user=bia).count()

        excluir_definitivamente(ana, RegistroDeExclusao.ADMIN)

        self.assertFalse(ClasseDeDespesa.objects.filter(user_id=ana_id).exists())
        self.assertEqual(ClasseDeDespesa.objects.filter(user=bia).count(), antes_da_bia)
        self.assertGreater(antes_da_bia, 0)

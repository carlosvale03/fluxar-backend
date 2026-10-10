"""
O padrão de um cadastro novo numa função (ADMIN-22, AD-050).
"""
from django.test import TestCase

from accounts.models import Account
from api.models import User
from transactions.models import Category
from transactions.padrao import criar_padrao_do_cadastro

# As categorias de um cadastro novo, como (nome, tipo, categoria pai)
CATEGORIAS_PADRAO = {
    ('Salário', 'INCOME', None),
    ('Investimento', 'INCOME', None),
    ('Pagamentos', 'INCOME', None),
    ('Prêmio', 'INCOME', None),
    ('Presente', 'INCOME', None),
    ('Outros', 'INCOME', None),
    ('Casa', 'EXPENSE', None),
    ('Aluguel', 'EXPENSE', 'Casa'),
    ('Energia', 'EXPENSE', 'Casa'),
    ('Comida', 'EXPENSE', None),
    ('Transporte', 'EXPENSE', None),
    ('Lazer', 'EXPENSE', None),
    ('Educação', 'EXPENSE', None),
    ('Eletrônicos', 'EXPENSE', None),
    ('Doces', 'EXPENSE', None),
    ('Doação', 'EXPENSE', None),
    ('Presente', 'EXPENSE', None),
}


def categorias(usuario):
    return [
        (c.name, c.type, c.parent.name if c.parent_id else None)
        for c in Category.objects.filter(user=usuario).select_related('parent')
    ]


def contas(usuario):
    return [(c.name, c.type, c.initial_balance, c.is_active) for c in Account.objects.filter(user=usuario)]


class PadraoDoCadastroTests(TestCase):

    def assert_padrao(self, usuario):
        encontradas = categorias(usuario)
        self.assertEqual(len(encontradas), len(CATEGORIAS_PADRAO))
        self.assertEqual(set(encontradas), CATEGORIAS_PADRAO)
        self.assertTrue(all(c.is_active for c in Category.objects.filter(user=usuario)))
        self.assertEqual(contas(usuario), [('Carteira', 'WALLET', 0, True)])

    def test_cadastro_novo_recebe_as_categorias_as_subcategorias_e_a_carteira(self):
        usuario = User.objects.create_user(email='novo@teste.fluxar', password='senha-de-teste-123', name='Novo')

        self.assert_padrao(usuario)

    def test_subcategorias_herdam_tipo_e_cor_da_categoria_pai(self):
        usuario = User.objects.create_user(email='novo@teste.fluxar', password='senha-de-teste-123', name='Novo')

        casa = Category.objects.get(user=usuario, name='Casa')
        for sub in Category.objects.filter(user=usuario, parent=casa):
            self.assertEqual((sub.type, sub.color), (casa.type, casa.color))

    def test_a_funcao_num_usuario_sem_dados_cria_o_mesmo_padrao(self):
        usuario = User.objects.create_user(email='novo@teste.fluxar', password='senha-de-teste-123', name='Novo')
        Category.objects.filter(user=usuario).delete()
        Account.objects.filter(user=usuario).delete()

        criar_padrao_do_cadastro(usuario)

        self.assert_padrao(usuario)

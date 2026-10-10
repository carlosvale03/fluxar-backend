"""
Classe das categorias de despesa (CLASSE-16 a CLASSE-18, CLASSE-21 a
CLASSE-23, CLASSE-26, CLASSE-27).
"""
import json
from datetime import date

from accounts.models import Account
from tests.importacao.base import MAPEAMENTO, URL_PLANILHA, arquivo_xlsx
from transactions.classes import categorias_das_classes, mapa_de_classes
from transactions.models import Category

from .base import ClassesTestCase, categoria, criar_classe, criar_usuario

ROTA = '/api/categories/'
RECEITA_SEM_CLASSE = {'expense_class': ['Categorias de receita não têm classe.']}
CLASSE_NAO_ENCONTRADA = {'expense_class': ['Classe não encontrada.']}


def resumo(classe):
    return {'id': str(classe.pk), 'name': classe.nome, 'color': classe.cor}


class ClasseDasCategoriasTests(ClassesTestCase):

    def setUp(self):
        super().setUp()
        self.comida = Category.objects.get(user=self.ana, name='Comida')

    def classe_da_api(self, categoria_):
        dados = self.client.get(f'{ROTA}{categoria_.pk}/').json()
        return dados['expense_class'], dados['effective_class'], dados['class_inherited']

    def test_subcategoria_nova_herda_a_classe_da_mae(self):
        resposta = self.client.post(
            ROTA, {'name': 'Delivery', 'type': 'EXPENSE', 'parent': str(self.comida.pk)}, format='json',
        )

        self.assertEqual(resposta.status_code, 201, resposta.data)
        dados = resposta.json()
        self.assertEqual(
            (dados['expense_class'], dados['effective_class'], dados['class_inherited']),
            (None, resumo(self.essencial()), True),
        )
        # Na lista, a subcategoria aninhada mostra o mesmo
        lista = self.client.get(ROTA, {'type': 'EXPENSE'}).json()
        [comida] = [c for c in lista if c['name'] == 'Comida']
        self.assertEqual(
            (comida['expense_class'], comida['effective_class'], comida['class_inherited']),
            (str(self.essencial().pk), resumo(self.essencial()), False),
        )
        [delivery] = comida['subcategories']
        self.assertEqual((delivery['effective_class'], delivery['class_inherited']), (resumo(self.essencial()), True))

    def test_classe_propria_da_subcategoria_muda_so_ela_e_sem_ela_volta_a_herdar(self):
        delivery = categoria(self.ana, 'Delivery', parent=self.comida)
        dispensavel = self.dispensavel()

        trocada = self.client.patch(
            f'{ROTA}{delivery.pk}/', {'expense_class': str(dispensavel.pk)}, format='json',
        )

        self.assertEqual(trocada.status_code, 200, trocada.data)
        self.assertEqual(self.classe_da_api(delivery), (str(dispensavel.pk), resumo(dispensavel), False))
        self.assertEqual(self.classe_da_api(self.comida)[1:], (resumo(self.essencial()), False))

        sem_propria = self.client.patch(f'{ROTA}{delivery.pk}/', {'expense_class': None}, format='json')

        self.assertEqual(sem_propria.status_code, 200, sem_propria.data)
        self.assertEqual(self.classe_da_api(delivery), (None, resumo(self.essencial()), True))

    def test_mae_sem_classe_com_subcategoria_classificada(self):
        mercado = categoria(self.ana, 'Mercado')
        feira = categoria(self.ana, 'Feira', parent=mercado, classe=self.essencial())

        self.assertEqual(self.classe_da_api(mercado), (None, None, False))
        self.assertEqual(self.classe_da_api(feira), (str(self.essencial().pk), resumo(self.essencial()), False))

    def test_criar_categoria_de_despesa_com_classe_ou_sem_classe(self):
        dividas = criar_classe(self.ana, 'Dívidas')

        com_classe = self.client.post(
            ROTA, {'name': 'Empréstimo', 'type': 'EXPENSE', 'expense_class': str(dividas.pk)}, format='json',
        )
        sem_classe = self.client.post(ROTA, {'name': 'Mercado', 'type': 'EXPENSE'}, format='json')

        self.assertEqual(com_classe.status_code, 201, com_classe.data)
        self.assertEqual(
            (com_classe.json()['expense_class'], com_classe.json()['effective_class']),
            (str(dividas.pk), resumo(dividas)),
        )
        self.assertEqual(Category.objects.get(pk=com_classe.data['id']).classe_id, dividas.pk)
        self.assertEqual(sem_classe.status_code, 201, sem_classe.data)
        self.assertEqual((sem_classe.json()['expense_class'], sem_classe.json()['effective_class']), (None, None))

    def test_classe_em_categoria_de_receita_e_recusada(self):
        salario = Category.objects.get(user=self.ana, name='Salário')

        editada = self.client.patch(
            f'{ROTA}{salario.pk}/', {'expense_class': str(self.essencial().pk)}, format='json',
        )
        criada = self.client.post(
            ROTA, {'name': 'Bônus', 'type': 'INCOME', 'expense_class': str(self.essencial().pk)}, format='json',
        )

        self.assertEqual((editada.status_code, editada.data), (400, RECEITA_SEM_CLASSE))
        self.assertEqual((criada.status_code, criada.data), (400, RECEITA_SEM_CLASSE))
        salario.refresh_from_db()
        self.assertIsNone(salario.classe_id)
        self.assertFalse(Category.objects.filter(user=self.ana, name='Bônus').exists())
        self.assertEqual(self.classe_da_api(salario), (None, None, False))

    def test_despesa_que_vira_receita_perde_a_classe_propria(self):
        doces = Category.objects.get(user=self.ana, name='Doces')

        resposta = self.client.patch(f'{ROTA}{doces.pk}/', {'type': 'INCOME'}, format='json')

        self.assertEqual(resposta.status_code, 200, resposta.data)
        doces.refresh_from_db()
        self.assertEqual((doces.type, doces.classe_id), ('INCOME', None))
        self.assertEqual(
            (resposta.json()['expense_class'], resposta.json()['effective_class'], resposta.json()['class_inherited']),
            (None, None, False),
        )

    def test_classe_de_outro_usuario_e_id_inexistente_recebem_a_mesma_resposta(self):
        da_bia = criar_classe(criar_usuario('bia@teste.fluxar'), 'Da Bia')
        doces = Category.objects.get(user=self.ana, name='Doces')
        antes = doces.classe_id

        for valor in (str(da_bia.pk), '00000000-0000-0000-0000-000000000000', 'nao-e-um-id'):
            with self.subTest(valor=valor):
                editada = self.client.patch(f'{ROTA}{doces.pk}/', {'expense_class': valor}, format='json')
                criada = self.client.post(
                    ROTA, {'name': 'Nova', 'type': 'EXPENSE', 'expense_class': valor}, format='json',
                )
                self.assertEqual((editada.status_code, editada.data), (400, CLASSE_NAO_ENCONTRADA))
                self.assertEqual((criada.status_code, criada.data), (400, CLASSE_NAO_ENCONTRADA))
        doces.refresh_from_db()
        self.assertEqual(doces.classe_id, antes)

    def test_subcategoria_movida_para_outra_mae_herda_a_classe_da_nova_mae(self):
        delivery = categoria(self.ana, 'Delivery', parent=self.comida)
        lazer = Category.objects.get(user=self.ana, name='Lazer')

        resposta = self.client.patch(f'{ROTA}{delivery.pk}/', {'parent': str(lazer.pk)}, format='json')

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(self.classe_da_api(delivery), (None, resumo(self.dispensavel()), True))


class MapaDeClassesTests(ClassesTestCase):

    def test_categoria_excluida_mantem_a_classe_no_mapa(self):
        doces = Category.objects.get(user=self.ana, name='Doces')
        bombom = categoria(self.ana, 'Bombom', parent=doces)

        self.assertEqual(self.client.delete(f'{ROTA}{doces.pk}/').status_code, 204)

        doces.refresh_from_db()
        self.assertFalse(doces.is_active)
        mapa = mapa_de_classes(self.ana)
        self.assertEqual(mapa[doces.pk], self.dispensavel())
        self.assertEqual(mapa[bombom.pk], self.dispensavel())

    def test_mapa_resolve_heranca_receitas_e_ciclos(self):
        casa = Category.objects.get(user=self.ana, name='Casa')
        aluguel = Category.objects.get(user=self.ana, name='Aluguel')
        neta = categoria(self.ana, 'Condomínio', parent=aluguel)
        salario = Category.objects.get(user=self.ana, name='Salário')
        a = categoria(self.ana, 'Ciclo A')
        b = categoria(self.ana, 'Ciclo B', parent=a)
        Category.objects.filter(pk=a.pk).update(parent=b)

        mapa = mapa_de_classes(self.ana)

        self.assertEqual(mapa[casa.pk], self.essencial())
        self.assertEqual(mapa[aluguel.pk], self.essencial())
        self.assertEqual(mapa[neta.pk], self.essencial())
        self.assertIsNone(mapa[salario.pk])
        self.assertIsNone(mapa[a.pk])
        self.assertIsNone(mapa[b.pk])
        # Só as categorias do usuário
        outra = Category.objects.get(user=criar_usuario('bia@teste.fluxar'), name='Comida')
        self.assertNotIn(outra.pk, mapa)

    def test_categorias_das_classes_com_e_sem_classe(self):
        mercado = categoria(self.ana, 'Mercado')
        doces = Category.objects.get(user=self.ana, name='Doces')
        aluguel = Category.objects.get(user=self.ana, name='Aluguel')

        so_dispensavel = categorias_das_classes(self.ana, [self.dispensavel().pk])
        com_sem_classe = categorias_das_classes(self.ana, [self.essencial().pk], sem_classe=True)

        self.assertIn(doces.pk, so_dispensavel)
        self.assertNotIn(mercado.pk, so_dispensavel)
        self.assertIn(aluguel.pk, com_sem_classe)
        self.assertIn(mercado.pk, com_sem_classe)
        self.assertNotIn(doces.pk, com_sem_classe)


class ImportacaoSemClasseTests(ClassesTestCase):

    def test_a_importacao_cria_categorias_sem_classe_propria(self):
        carteira = Account.objects.get(user=self.ana, name='Carteira')
        arquivo = arquivo_xlsx([
            ['Data', 'Descrição', 'Valor', 'Categoria', 'Sub'],
            [date(2026, 9, 10), 'Feira do sábado', -30, 'Comida', 'Feira'],
            [date(2026, 9, 11), 'Passagem', -200, 'Viagem', None],
        ])

        resposta = self.client.post(URL_PLANILHA, {
            'file': arquivo, 'import_type': 'INCOME_EXPENSE', 'account_id': str(carteira.pk),
            'mapping': json.dumps({**MAPEAMENTO, 'category_column': 'Categoria', 'subcategory_column': 'Sub'}),
        }, format='multipart')

        self.assertEqual(resposta.status_code, 200, resposta.data)
        feira = Category.objects.get(user=self.ana, name='Feira')
        viagem = Category.objects.get(user=self.ana, name='Viagem')
        self.assertEqual((feira.classe_id, viagem.classe_id), (None, None))
        mapa = mapa_de_classes(self.ana)
        # A subcategoria criada dentro de Comida herda a classe dela
        self.assertEqual(mapa[feira.pk], self.essencial())
        self.assertIsNone(mapa[viagem.pk])

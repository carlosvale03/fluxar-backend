"""
API das classes de despesa (CLASSE-02, CLASSE-04 a CLASSE-08, CLASSE-10,
CLASSE-11, CLASSE-13, CLASSE-15).
"""
from unittest import mock

from api.models import SystemLog
from tests.lgpd.test_logs import capturar_logs_e_saida
from tests.permissoes.base import LIMITES, RECURSOS, fechar, liberacao_de_testes
from transactions.models import Category, ClasseDeDespesa

from .base import (
    CLASSE_PADRAO_FIXA, LIMITE_ATINGIDO, NOME_REPETIDO, ROTA, ClassesTestCase,
    categoria, criar_classe, criar_usuario, detalhe,
)


def nomes(usuario):
    return sorted(ClasseDeDespesa.objects.filter(user=usuario).values_list('nome', flat=True))


class ListaDeClassesTests(ClassesTestCase):

    def test_lista_completa_sem_paginacao_com_padrao_e_contagem(self):
        for numero in range(3):
            criar_classe(self.ana, f'Extra {numero}')
        essencial = self.essencial()
        criar_classe(criar_usuario('bia@teste.fluxar'), 'Da Bia')
        # Categorias ativas com a classe própria Essencial: as quatro do padrão
        # e mais uma; a excluída não conta
        categoria(self.ana, 'Mercado', classe=essencial)
        categoria(self.ana, 'Antiga', classe=essencial, is_active=False)

        resposta = self.client.get(ROTA)

        self.assertEqual(resposta.status_code, 200)
        self.assertIsInstance(resposta.data, list)
        self.assertEqual(len(resposta.data), 5)
        por_nome = {item['name']: item for item in resposta.data}
        self.assertEqual(set(por_nome), {'Essencial', 'Dispensável', 'Extra 0', 'Extra 1', 'Extra 2'})
        self.assertEqual(por_nome['Essencial'], {
            'id': str(essencial.pk), 'name': 'Essencial', 'color': '#16A34A',
            'is_default': True, 'categories_count': 5,
        })
        self.assertEqual(por_nome['Dispensável']['categories_count'], 5)
        self.assertEqual((por_nome['Extra 0']['is_default'], por_nome['Extra 0']['categories_count']), (False, 0))


class CriacaoDeClassesTests(ClassesTestCase):

    def criar(self, nome, cor='#DC2626'):
        return self.client.post(ROTA, {'name': nome, 'color': cor}, format='json')

    def test_cria_a_classe_com_o_nome_e_a_cor_escolhidos(self):
        resposta = self.criar('Dívidas', '#DC2626')

        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual(
            {k: resposta.data[k] for k in ('name', 'color', 'is_default', 'categories_count')},
            {'name': 'Dívidas', 'color': '#DC2626', 'is_default': False, 'categories_count': 0},
        )
        criada = ClasseDeDespesa.objects.get(pk=resposta.data['id'])
        self.assertEqual((criada.user_id, criada.nome, criada.cor), (self.ana.pk, 'Dívidas', '#DC2626'))

    def test_a_sexta_classe_e_recusada_com_a_mensagem_do_limite(self):
        for nome in ('Dívidas', 'Impostos e taxas', 'Profissional'):
            self.assertEqual(self.criar(nome).status_code, 201)

        resposta = self.criar('Viagens')

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data, LIMITE_ATINGIDO)
        self.assertEqual(ClasseDeDespesa.objects.filter(user=self.ana).count(), 5)

    def test_o_limite_e_por_usuario(self):
        bia = criar_usuario('bia@teste.fluxar')
        for nome in ('A', 'B', 'C'):
            criar_classe(bia, nome)

        self.assertEqual(self.criar('Dívidas').status_code, 201)

    def test_nome_vazio_ou_com_31_caracteres_e_recusado_no_campo_do_nome(self):
        for nome in ('', '   ', 'x' * 31):
            with self.subTest(nome=nome):
                resposta = self.criar(nome)
                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(set(resposta.data), {'name'})
        self.assertEqual(self.criar('x' * 30).status_code, 201)
        self.assertEqual(nomes(self.ana), sorted(['Dispensável', 'Essencial', 'x' * 30]))

    def test_nome_repetido_sem_diferenca_de_maiusculas_e_acentos_e_recusado(self):
        self.assertEqual(self.criar('Dívidas').status_code, 201)

        for nome in ('dividas', 'DÍVIDAS', ' Dividas ', 'essencial', 'dispensavel'):
            with self.subTest(nome=nome):
                resposta = self.criar(nome)
                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.data, NOME_REPETIDO)
        self.assertEqual(nomes(self.ana), ['Dispensável', 'Dívidas', 'Essencial'])

    def test_o_mesmo_nome_vale_em_usuarios_diferentes(self):
        criar_classe(criar_usuario('bia@teste.fluxar'), 'Dívidas')

        self.assertEqual(self.criar('Dívidas').status_code, 201)


class EdicaoDeClassesTests(ClassesTestCase):

    def test_renomear_essencial_e_dispensavel_e_recusado(self):
        for classe_ in (self.essencial(), self.dispensavel()):
            with self.subTest(classe=classe_.nome):
                resposta = self.client.patch(detalhe(classe_), {'name': 'Básico'}, format='json')
                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.data, CLASSE_PADRAO_FIXA)
        self.assertEqual(nomes(self.ana), ['Dispensável', 'Essencial'])

    def test_mudar_a_cor_de_uma_classe_padrao_funciona(self):
        essencial = self.essencial()

        resposta = self.client.patch(detalhe(essencial), {'color': '#0EA5E9'}, format='json')

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual((resposta.data['name'], resposta.data['color']), ('Essencial', '#0EA5E9'))
        essencial.refresh_from_db()
        self.assertEqual((essencial.nome, essencial.cor), ('Essencial', '#0EA5E9'))

    def test_renomear_uma_classe_criada_pelo_usuario_funciona_e_confere_o_nome(self):
        dividas = criar_classe(self.ana, 'Dívidas')

        repetido = self.client.patch(detalhe(dividas), {'name': 'ESSENCIAL'}, format='json')
        renomeada = self.client.patch(detalhe(dividas), {'name': 'Empréstimos'}, format='json')

        self.assertEqual(repetido.status_code, 400)
        self.assertEqual(repetido.data, NOME_REPETIDO)
        self.assertEqual(renomeada.status_code, 200, renomeada.data)
        dividas.refresh_from_db()
        self.assertEqual(dividas.nome, 'Empréstimos')
        # O nome novo passa a valer na regra de repetição
        self.assertEqual(
            self.client.post(ROTA, {'name': 'emprestimos', 'color': '#000000'}, format='json').data,
            NOME_REPETIDO,
        )

    def test_classe_de_outro_usuario_responde_404(self):
        da_bia = criar_classe(criar_usuario('bia@teste.fluxar'), 'Da Bia')

        self.assertEqual(self.client.patch(detalhe(da_bia), {'color': '#000000'}, format='json').status_code, 404)
        self.assertEqual(self.client.delete(detalhe(da_bia)).status_code, 404)
        self.assertTrue(ClasseDeDespesa.objects.filter(pk=da_bia.pk).exists())


class ExclusaoDeClassesTests(ClassesTestCase):

    def test_excluir_essencial_ou_dispensavel_e_recusado(self):
        for classe_ in (self.essencial(), self.dispensavel()):
            with self.subTest(classe=classe_.nome):
                resposta = self.client.delete(detalhe(classe_))
                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.data, CLASSE_PADRAO_FIXA)
        self.assertEqual(nomes(self.ana), ['Dispensável', 'Essencial'])

    def test_excluir_uma_classe_tira_a_classe_propria_das_categorias_que_a_usavam(self):
        dividas = criar_classe(self.ana, 'Dívidas')
        emprestimo = categoria(self.ana, 'Empréstimo', classe=dividas)
        casa = Category.objects.get(user=self.ana, name='Casa')
        juros = categoria(self.ana, 'Juros', parent=casa, classe=dividas)

        resposta = self.client.delete(detalhe(dividas))

        self.assertEqual(resposta.status_code, 204)
        self.assertFalse(ClasseDeDespesa.objects.filter(pk=dividas.pk).exists())
        for categoria_ in (emprestimo, juros):
            categoria_.refresh_from_db()
            self.assertIsNone(categoria_.classe_id)
        # As demais categorias não mudam
        casa.refresh_from_db()
        self.assertEqual(casa.classe_id, self.essencial().pk)

    def test_falha_no_meio_da_exclusao_mantem_a_classe_e_as_categorias(self):
        dividas = criar_classe(self.ana, 'Dívidas')
        emprestimo = categoria(self.ana, 'Empréstimo', classe=dividas)
        juros = categoria(self.ana, 'Juros', classe=dividas)

        with mock.patch.object(ClasseDeDespesa, 'delete', side_effect=RuntimeError('falha forçada')):
            with self.assertRaises(RuntimeError):
                self.client.delete(detalhe(dividas))

        self.assertTrue(ClasseDeDespesa.objects.filter(pk=dividas.pk).exists())
        for categoria_ in (emprestimo, juros):
            categoria_.refresh_from_db()
            self.assertEqual(categoria_.classe_id, dividas.pk)


class ClassesSemTravaDePlanoTests(ClassesTestCase):

    def test_nenhum_plano_trava_as_classes(self):
        liberacao_de_testes(False)
        for chave in RECURSOS:
            fechar(chave)
        for chave in LIMITES:
            fechar(chave, limite=0)
        self.ana.plan = 'COMMON'
        self.ana.save(update_fields=['plan'])

        lista = self.client.get(ROTA)
        criada = self.client.post(ROTA, {'name': 'Dívidas', 'color': '#DC2626'}, format='json')
        editada = self.client.patch(f"{ROTA}{criada.data['id']}/", {'color': '#000000'}, format='json')
        excluida = self.client.delete(f"{ROTA}{criada.data['id']}/")

        self.assertEqual(
            [lista.status_code, criada.status_code, editada.status_code, excluida.status_code],
            [200, 201, 200, 204],
        )


class LogsSemNomeDaClasseTests(ClassesTestCase):

    def test_nenhum_log_grava_o_nome_da_classe(self):
        nome, novo_nome = 'Classe Sigilosa Qwz', 'Outra Sigilosa Kpt'

        with capturar_logs_e_saida() as (mensagens, saida):
            criada = self.client.post(ROTA, {'name': nome, 'color': '#DC2626'}, format='json')
            url = f"{ROTA}{criada.data['id']}/"
            self.client.patch(url, {'name': novo_nome}, format='json')
            self.client.post(ROTA, {'name': novo_nome, 'color': '#DC2626'}, format='json')
            self.client.delete(url)

        self.assertEqual(criada.status_code, 201)
        texto = ' '.join(mensagens) + saida.getvalue()
        registros = ' '.join(str(vars(log)) for log in SystemLog.objects.all())
        for valor in (nome, novo_nome, 'Sigilosa'):
            self.assertNotIn(valor, texto)
            self.assertNotIn(valor, registros)

from django.apps import apps

from core.isolation import find_cross_links
from transactions.models import Category
from tests.isolamento.base import DoisUsuariosTestCase
from tests.isolamento.ligacoes import gravar_ligacoes_cruzadas


def como_tuplas(links):
    return sorted(((l.tipo, l.registro_id, l.relacao, l.alheio_id) for l in links), key=str)


class VerificacaoDeLigacoesCruzadasTests(DoisUsuariosTestCase):

    def test_base_sem_ligacoes_cruzadas_devolve_lista_vazia(self):
        # Categorias-modelo sem dono, inclusive uma subcategoria-modelo, não são
        # dados de usuário e não contam como ligação cruzada
        Category.objects.create(
            user=None, name='Submodelo', type='EXPENSE', is_template=True, parent=self.categoria_modelo,
        )

        self.assertEqual(find_cross_links(apps), [])

    def test_cada_ligacao_cruzada_aparece_uma_vez_com_tipo_id_e_relacao(self):
        registros = gravar_ligacoes_cruzadas(self.a, self.b, self.categoria_modelo)

        links = find_cross_links(apps)

        # Listas ordenadas iguais: cada ligação aparece exatamente uma vez, e a
        # tag própria de A na mesma transação não aparece
        self.assertEqual(como_tuplas(links), sorted(registros.esperadas, key=str))
        self.assertEqual(len(links), 18)

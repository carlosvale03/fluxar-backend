"""
Busca de usuários no painel admin: pelo nome ou pelo e-mail, com os filtros
de plano, papel e status, na lista paginada de CONTRATO-02 (ADMIN-16).

O administrador do `setUp` (Admin Fulano de Tal) e o usuário comum (Cliente
Beltrano) não casam com nenhuma das buscas.
"""
from .base import PainelAdminTestCase, criar_usuario

URL = '/api/admin/users/'


class BuscaDeUsuariosTests(PainelAdminTestCase):

    def setUp(self):
        super().setUp()
        self.maria_premium = criar_usuario('m.silva@teste.fluxar', 'Maria Silva', plan='PREMIUM')
        self.maria_comum = criar_usuario('m.souza@teste.fluxar', 'Maria Souza', plan='COMMON')
        self.maria_plus = criar_usuario('m.lima@teste.fluxar', 'Maria Lima', plan='PREMIUM_PLUS')
        self.maria_admin = criar_usuario('m.costa@teste.fluxar', 'Maria Costa', plan='PREMIUM', role='ADMIN')
        self.maria_arquivada = criar_usuario('m.rocha@teste.fluxar', 'Maria Rocha', plan='PREMIUM', is_active=False)
        self.joao_premium = criar_usuario('joao.ferreira@teste.fluxar', 'João Ferreira', plan='PREMIUM')

    def ids(self, parametros):
        resposta = self.client.get(URL, parametros)
        self.assertEqual(resposta.status_code, 200, resposta.data)
        return {item['id'] for item in resposta.json()['results']}

    def test_maria_com_o_plano_premium_traz_so_as_marias_ativas_do_premium(self):
        self.assertEqual(
            self.ids({'search': 'maria', 'plan': 'PREMIUM'}),
            {str(self.maria_premium.pk), str(self.maria_admin.pk)},
        )

    def test_busca_pelo_email(self):
        # "ferreira" só aparece no e-mail e no nome do João; "m.souza", só no e-mail
        self.assertEqual(self.ids({'search': 'joao.ferreira@'}), {str(self.joao_premium.pk)})
        self.assertEqual(self.ids({'search': 'm.souza'}), {str(self.maria_comum.pk)})

    def test_filtro_de_papel_combina_com_a_busca_e_o_plano(self):
        self.assertEqual(self.ids({'search': 'maria', 'role': 'ADMIN'}), {str(self.maria_admin.pk)})
        self.assertEqual(
            self.ids({'search': 'maria', 'role': 'USER', 'plan': 'PREMIUM'}), {str(self.maria_premium.pk)},
        )

    def test_filtro_de_status_combina_com_a_busca(self):
        self.assertEqual(self.ids({'search': 'maria', 'show_archived': 'true'}), {str(self.maria_arquivada.pk)})
        self.assertEqual(
            self.ids({'search': 'maria', 'show_archived': 'true', 'plan': 'COMMON'}), set(),
        )
        self.assertNotIn(str(self.maria_arquivada.pk), self.ids({'search': 'maria'}))

    def test_resultado_da_busca_vem_paginado(self):
        for i in range(22):
            criar_usuario(f'helena{i}@teste.fluxar', f'Helena {i}', plan='PREMIUM')

        resposta = self.client.get(URL, {'search': 'helena', 'plan': 'PREMIUM'}).json()
        segunda = self.client.get(URL, {'search': 'helena', 'plan': 'PREMIUM', 'page': 2}).json()

        self.assertEqual((resposta['count'], resposta['total_pages'], len(resposta['results'])), (22, 2, 20))
        self.assertIsNotNone(resposta['next'])
        self.assertEqual(len(segunda['results']), 2)
        self.assertEqual(
            len({u['id'] for u in resposta['results']} | {u['id'] for u in segunda['results']}), 22,
        )

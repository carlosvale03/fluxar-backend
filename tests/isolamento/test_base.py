from types import SimpleNamespace

from tests.isolamento.base import DoisUsuariosTestCase


def resposta(status_code, data):
    return SimpleNamespace(status_code=status_code, data=data)


class BaseDoisUsuariosTests(DoisUsuariosTestCase):

    def test_cada_objeto_pertence_ao_usuario_certo(self):
        for dados in (self.a, self.b):
            usuario = dados.usuario
            self.assertEqual(dados.conta.user, usuario)
            self.assertEqual(dados.cofrinho.user, usuario)
            self.assertEqual(dados.cofrinho.type, 'PIGGY_BANK')
            self.assertEqual(dados.meta.user, usuario)
            self.assertEqual(dados.meta.account, dados.cofrinho)
            self.assertEqual(dados.cartao.user, usuario)
            self.assertEqual(dados.fatura.card, dados.cartao)
            self.assertEqual(dados.categoria.user, usuario)
            self.assertEqual(dados.subcategoria.user, usuario)
            self.assertEqual(dados.subcategoria.parent, dados.categoria)
            self.assertEqual(dados.tag.user, usuario)
            self.assertEqual(dados.orcamento.user, usuario)
            self.assertEqual(dados.orcamento.category, dados.categoria)
            self.assertEqual(dados.monitor.user, usuario)
            self.assertEqual(dados.monitor.category, dados.categoria)
        self.assertNotEqual(self.a.usuario, self.b.usuario)
        self.assertIsNone(self.categoria_modelo.user)
        self.assertTrue(self.categoria_modelo.is_template)

    def test_a_nao_enxerga_contas_de_b_na_listagem(self):
        resp = self.como(self.a.usuario).get('/api/accounts/')

        self.assertEqual(resp.status_code, 200)
        ids = {item['id'] for item in resp.data}
        self.assertIn(str(self.a.conta.id), ids)
        self.assertIn(str(self.a.cofrinho.id), ids)
        ids_de_b = {str(c.id) for c in self.b.usuario.accounts.all()}
        self.assertEqual(ids & ids_de_b, set())

    def test_assert_mesma_recusa_compara_status_chaves_e_mensagens(self):
        recusa = resposta(400, {'account': ['Conta não encontrada.']})

        # Respostas idênticas passam, inclusive conferindo a mensagem.
        self.assert_mesma_recusa(
            recusa, resposta(400, {'account': ['Conta não encontrada.']}),
            'account', 'Conta não encontrada.',
        )

        casos_que_falham = [
            # status diferente
            (resposta(404, {'account': ['Conta não encontrada.']}), recusa, 'account'),
            (recusa, resposta(404, {'account': ['Conta não encontrada.']}), 'account'),
            # erro fora do campo esperado
            (recusa, recusa, 'category'),
            # chaves de erro diferentes
            (recusa, resposta(400, {'category': ['Conta não encontrada.']}), 'account'),
            # mensagens diferentes
            (recusa, resposta(400, {'account': ['Invalid pk']}), 'account'),
        ]
        for alheio, inexistente, campo in casos_que_falham:
            with self.subTest(alheio=alheio, inexistente=inexistente, campo=campo):
                with self.assertRaises(AssertionError):
                    self.assert_mesma_recusa(alheio, inexistente, campo)

        with self.assertRaises(AssertionError):
            self.assert_mesma_recusa(recusa, recusa, 'account', 'Cartão não encontrado.')

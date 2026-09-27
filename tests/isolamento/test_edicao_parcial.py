from datetime import date
from decimal import Decimal

from transactions.models import Transaction
from tests.isolamento.base import DoisUsuariosTestCase

URL = '/api/transactions/'


class EdicaoParcialComLigacaoCruzadaTests(DoisUsuariosTestCase):
    """
    Transação de A que ainda aponta para objeto de B (ou para a
    categoria-modelo), gravada à força como antes da correção: a edição é
    recusada até a ligação ser desfeita, mesmo sem o campo no corpo.
    """

    def setUp(self):
        self.cliente = self.como(self.a.usuario)

    def transacao_de_a(self, tipo='EXPENSE'):
        if tipo == 'CREDIT_CARD':
            t = Transaction.objects.create(
                user=self.a.usuario, type='CREDIT_CARD', status='PENDING',
                description='Existente', amount=Decimal('30.00'), date=date(2026, 9, 1),
                credit_card=self.a.cartao, category=self.a.categoria,
            )
        else:
            t = Transaction.objects.create(
                user=self.a.usuario, type='EXPENSE', status='COMPLETED',
                description='Existente', amount=Decimal('30.00'), date=date(2026, 9, 1),
                account=self.a.conta, category=self.a.categoria,
            )
        t.tags.set([self.a.tag])
        return t

    def forjar(self, campo, tipo='EXPENSE'):
        """Grava à força a ligação cruzada `campo` numa transação de A."""
        t = self.transacao_de_a(tipo)
        alheios = {
            'account': self.b.conta, 'credit_card': self.b.cartao,
            'category': self.b.categoria, 'categoria_modelo': self.categoria_modelo,
        }
        if campo == 'tags':
            t.tags.add(self.b.tag)
        elif campo == 'categoria_modelo':
            Transaction.objects.filter(pk=t.pk).update(category=self.categoria_modelo)
        else:
            Transaction.objects.filter(pk=t.pk).update(**{campo: alheios[campo]})
        return t

    def estado(self, t):
        t.refresh_from_db()
        return (
            t.account_id, t.credit_card_id, t.category_id, t.description,
            t.amount, t.updated_at, set(t.tags.values_list('id', flat=True)),
        )

    def assert_patch_recusado(self, t, campo, mensagem, inexistente):
        antes = self.estado(t)
        url = f'{URL}{t.id}/'

        resp = self.cliente.patch(url, {'description': 'Nova'}, format='json')
        resp_inexistente = self.cliente.patch(url, {campo: inexistente}, format='json')

        self.assert_mesma_recusa(resp, resp_inexistente, campo, mensagem)
        self.assertEqual(resp.data, {campo: [mensagem]})
        self.assertEqual(self.estado(t), antes)

    # --- Recusa enquanto a ligação cruzada existe ---

    def test_patch_so_com_descricao_e_recusado_com_conta_de_b(self):
        t = self.forjar('account')
        self.assert_patch_recusado(t, 'account', 'Conta não encontrada.', self.ID_INEXISTENTE)

    def test_patch_so_com_descricao_e_recusado_com_cartao_de_b(self):
        t = self.forjar('credit_card', tipo='CREDIT_CARD')
        self.assert_patch_recusado(t, 'credit_card', 'Cartão não encontrado.', self.ID_INEXISTENTE)

    def test_patch_so_com_descricao_e_recusado_com_categoria_de_b(self):
        t = self.forjar('category')
        self.assert_patch_recusado(t, 'category', 'Categoria não encontrada.', self.ID_INEXISTENTE)

    def test_patch_so_com_descricao_e_recusado_com_categoria_modelo(self):
        t = self.forjar('categoria_modelo')
        self.assert_patch_recusado(t, 'category', 'Categoria não encontrada.', self.ID_INEXISTENTE)

    def test_patch_so_com_descricao_e_recusado_com_tag_de_b(self):
        t = self.forjar('tags')
        self.assert_patch_recusado(t, 'tags', 'Tag não encontrada.', [self.ID_INEXISTENTE])

    def test_patch_que_troca_uma_relacao_mas_mantem_outra_cruzada_e_recusado(self):
        t = self.forjar('account')
        Transaction.objects.filter(pk=t.pk).update(category=self.b.categoria)
        antes = self.estado(t)

        resp = self.cliente.patch(f'{URL}{t.id}/', {'account': str(self.a.conta.id)}, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {'category': ['Categoria não encontrada.']})
        self.assertEqual(self.estado(t), antes)

    # --- Aceite depois de desfazer a ligação ---

    def test_patch_que_troca_a_relacao_cruzada_por_uma_propria_e_aceito(self):
        casos = (
            ('account', 'EXPENSE', {'account': str(self.a.cofrinho.id)}, 'account_id', self.a.cofrinho.id),
            ('credit_card', 'CREDIT_CARD', {'credit_card': str(self.a.cartao.id)}, 'credit_card_id', self.a.cartao.id),
            ('category', 'EXPENSE', {'category': str(self.a.subcategoria.id)}, 'category_id', self.a.subcategoria.id),
            ('categoria_modelo', 'EXPENSE', {'category': str(self.a.subcategoria.id)}, 'category_id', self.a.subcategoria.id),
        )
        for campo, tipo, corpo, atributo, esperado in casos:
            with self.subTest(campo):
                t = self.forjar(campo, tipo)

                resp = self.cliente.patch(f'{URL}{t.id}/', {**corpo, 'description': 'Nova'}, format='json')

                self.assertEqual(resp.status_code, 200, resp.data)
                t.refresh_from_db()
                self.assertEqual(getattr(t, atributo), esperado)
                self.assertEqual(t.description, 'Nova')

        with self.subTest('tags'):
            t = self.forjar('tags')

            resp = self.cliente.patch(f'{URL}{t.id}/', {
                'tags': [str(self.a.tag.id)], 'description': 'Nova',
            }, format='json')

            self.assertEqual(resp.status_code, 200, resp.data)
            t.refresh_from_db()
            self.assertEqual(list(t.tags.all()), [self.a.tag])
            self.assertEqual(t.description, 'Nova')

    def test_patch_que_troca_a_relacao_cruzada_por_nula_e_aceito(self):
        for campo, corpo, atributo in (
            ('category', {'category': None}, 'category_id'),
            ('tags', {'tags': []}, None),
        ):
            with self.subTest(campo):
                t = self.forjar(campo)

                resp = self.cliente.patch(f'{URL}{t.id}/', {**corpo, 'description': 'Nova'}, format='json')

                self.assertEqual(resp.status_code, 200, resp.data)
                t.refresh_from_db()
                if atributo:
                    self.assertIsNone(getattr(t, atributo))
                else:
                    self.assertEqual(list(t.tags.all()), [])
                self.assertEqual(t.description, 'Nova')

    def test_patch_parcial_de_transacao_sem_ligacao_cruzada_continua_funcionando(self):
        t = self.transacao_de_a()

        resp = self.cliente.patch(f'{URL}{t.id}/', {'description': 'Nova'}, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        t.refresh_from_db()
        self.assertEqual(t.description, 'Nova')
        self.assertEqual(t.account, self.a.conta)
        self.assertEqual(t.category, self.a.categoria)
        self.assertEqual(list(t.tags.all()), [self.a.tag])

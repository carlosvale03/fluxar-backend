import uuid
from datetime import date
from decimal import Decimal

from accounts.models import Account
from accounts.services import AccountService
from transactions.models import Tag, Transaction
from tests.isolamento.base import DoisUsuariosTestCase

URL = '/api/transactions/'

# campo -> (valor com o objeto de B, valor com um ID inexistente, mensagem)
RELACOES = {
    'account': (lambda b: str(b.conta.id), lambda i: i, 'Conta não encontrada.'),
    'credit_card': (lambda b: str(b.cartao.id), lambda i: i, 'Cartão não encontrado.'),
    'category': (lambda b: str(b.categoria.id), lambda i: i, 'Categoria não encontrada.'),
    'tags': (lambda b: [str(b.tag.id)], lambda i: [i], 'Tag não encontrada.'),
    'target_account_id': (lambda b: str(b.conta.id), lambda i: i, 'Conta não encontrada.'),
}


class EscritaTransacoesTests(DoisUsuariosTestCase):

    def setUp(self):
        self.cliente = self.como(self.a.usuario)

    def payload(self, **extra):
        dados = {
            'type': 'EXPENSE', 'status': 'COMPLETED', 'description': 'Compra',
            'amount': '50.00', 'date': '2026-09-15',
            'account': str(self.a.conta.id), 'category': str(self.a.categoria.id),
            'tags': [str(self.a.tag.id)],
        }
        dados.update(extra)
        return dados

    def criar_transacao_de_a(self):
        t = Transaction.objects.create(
            user=self.a.usuario, type='EXPENSE', status='COMPLETED',
            description='Existente', amount=Decimal('30.00'), date=date(2026, 9, 1),
            account=self.a.conta, category=self.a.categoria,
        )
        t.tags.set([self.a.tag])
        return t

    def estado(self, t):
        t.refresh_from_db()
        return (
            t.account_id, t.credit_card_id, t.category_id, t.description,
            t.amount, t.updated_at, set(t.tags.values_list('id', flat=True)),
        )

    def assert_b_intacto(self):
        conta_b = Account.objects.get(pk=self.b.conta.pk)
        self.assertEqual(conta_b.balance, Decimal('1000.00'))
        self.assertEqual(AccountService.get_balance(conta_b), Decimal('1000.00'))
        self.assertFalse(Transaction.objects.filter(account__user=self.b.usuario).exists())
        self.assertFalse(Transaction.objects.filter(credit_card__user=self.b.usuario).exists())
        self.assertFalse(Transaction.objects.filter(category__user=self.b.usuario).exists())
        self.assertFalse(Transaction.objects.filter(tags__user=self.b.usuario).exists())

    # --- Criação ---

    def assert_criacao_recusada(self, campo):
        valor_b, valor_inexistente, mensagem = RELACOES[campo]
        total_antes = Transaction.objects.count()

        resp_alheio = self.cliente.post(URL, self.payload(**{campo: valor_b(self.b)}), format='json')
        resp_inexistente = self.cliente.post(
            URL, self.payload(**{campo: valor_inexistente(self.ID_INEXISTENTE)}), format='json',
        )

        self.assert_mesma_recusa(resp_alheio, resp_inexistente, campo, mensagem)
        self.assertEqual(Transaction.objects.count(), total_antes)
        self.assert_b_intacto()

    def test_criacao_com_conta_de_b_e_recusada(self):
        self.assert_criacao_recusada('account')

    def test_criacao_com_cartao_de_b_e_recusada(self):
        self.assert_criacao_recusada('credit_card')

    def test_criacao_com_categoria_de_b_e_recusada(self):
        self.assert_criacao_recusada('category')

    def test_criacao_com_tag_de_b_e_recusada(self):
        self.assert_criacao_recusada('tags')

    def test_criacao_com_conta_destino_de_b_e_recusada(self):
        self.assert_criacao_recusada('target_account_id')

    def test_criacao_com_uma_tag_de_b_entre_tags_de_a_e_recusada(self):
        tag_a2 = Tag.objects.create(user=self.a.usuario, name='Outra A')
        total_antes = Transaction.objects.count()

        resp = self.cliente.post(URL, self.payload(tags=[
            str(self.a.tag.id), str(self.b.tag.id), str(tag_a2.id),
        ]), format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {'tags': ['Tag não encontrada.']})
        self.assertEqual(Transaction.objects.count(), total_antes)
        self.assert_b_intacto()

    def test_criacao_com_objetos_de_a_continua_funcionando(self):
        resp = self.cliente.post(URL, self.payload(), format='json')

        self.assertEqual(resp.status_code, 201, resp.data)
        t = Transaction.objects.get(pk=resp.data['id'])
        self.assertEqual(t.user, self.a.usuario)
        self.assertEqual(t.account, self.a.conta)
        self.assertEqual(t.category, self.a.categoria)
        self.assertEqual(list(t.tags.all()), [self.a.tag])
        self.assertEqual(resp.data['account'], self.a.conta.id)
        self.assertEqual(resp.data['category'], self.a.categoria.id)
        self.assertEqual(resp.data['tags'], [self.a.tag.id])

        resp_cartao = self.cliente.post(URL, self.payload(
            account=None, credit_card=str(self.a.cartao.id), tags=[],
        ), format='json')
        self.assertEqual(resp_cartao.status_code, 201, resp_cartao.data)
        self.assertEqual(Transaction.objects.get(pk=resp_cartao.data['id']).credit_card, self.a.cartao)

    # --- Edição ---

    def assert_edicao_recusada(self, campo):
        valor_b, valor_inexistente, mensagem = RELACOES[campo]
        t = self.criar_transacao_de_a()
        antes = self.estado(t)

        resp_alheio = self.cliente.patch(f'{URL}{t.id}/', {campo: valor_b(self.b)}, format='json')
        resp_inexistente = self.cliente.patch(
            f'{URL}{t.id}/', {campo: valor_inexistente(self.ID_INEXISTENTE)}, format='json',
        )

        self.assert_mesma_recusa(resp_alheio, resp_inexistente, campo, mensagem)
        self.assertEqual(self.estado(t), antes)
        self.assert_b_intacto()

    def test_edicao_com_conta_de_b_e_recusada(self):
        self.assert_edicao_recusada('account')

    def test_edicao_com_cartao_de_b_e_recusada(self):
        self.assert_edicao_recusada('credit_card')

    def test_edicao_com_categoria_de_b_e_recusada(self):
        self.assert_edicao_recusada('category')

    def test_edicao_com_tag_de_b_e_recusada(self):
        self.assert_edicao_recusada('tags')

    def test_edicao_com_conta_destino_de_b_e_recusada(self):
        self.assert_edicao_recusada('target_account_id')

    def test_edicao_com_uma_tag_de_b_entre_tags_de_a_e_recusada(self):
        t = self.criar_transacao_de_a()
        tag_a2 = Tag.objects.create(user=self.a.usuario, name='Outra A')
        antes = self.estado(t)

        resp = self.cliente.patch(f'{URL}{t.id}/', {'tags': [
            str(tag_a2.id), str(self.b.tag.id),
        ]}, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {'tags': ['Tag não encontrada.']})
        self.assertEqual(self.estado(t), antes)

    def test_edicao_com_objetos_de_a_continua_funcionando(self):
        t = self.criar_transacao_de_a()
        tag_a2 = Tag.objects.create(user=self.a.usuario, name='Outra A')

        resp = self.cliente.patch(f'{URL}{t.id}/', {
            'account': str(self.a.cofrinho.id),
            'category': str(self.a.subcategoria.id),
            'tags': [str(tag_a2.id)],
        }, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        t.refresh_from_db()
        self.assertEqual(t.account, self.a.cofrinho)
        self.assertEqual(t.category, self.a.subcategoria)
        self.assertEqual(list(t.tags.all()), [tag_a2])

    def test_edicao_de_transacao_ja_ligada_a_conta_de_b_e_recusada(self):
        # Ligação cruzada gravada à força, como antes da correção.
        t = self.criar_transacao_de_a()
        Transaction.objects.filter(pk=t.pk).update(account=self.b.conta)
        dados = self.payload(account=str(self.b.conta.id), description='Nova descrição')

        resp = self.cliente.put(f'{URL}{t.id}/', dados, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {'account': ['Conta não encontrada.']})
        t.refresh_from_db()
        self.assertEqual(t.description, 'Existente')

    # --- Parceira da transferência ---

    def test_troca_de_conta_da_parceira_so_altera_transacao_do_dono(self):
        transfer_id = uuid.uuid4()
        saida_a = Transaction.objects.create(
            user=self.a.usuario, type='TRANSFER_OUT', status='COMPLETED',
            description='TR', amount=Decimal('10.00'), date=date(2026, 9, 2),
            account=self.a.conta, transfer_id=transfer_id,
        )
        # Parceira forjada: transação de B com o mesmo transfer_id.
        parceira_b = Transaction.objects.create(
            user=self.b.usuario, type='TRANSFER_IN', status='COMPLETED',
            description='TR', amount=Decimal('10.00'), date=date(2026, 9, 2),
            account=self.b.conta, transfer_id=transfer_id,
        )

        resp = self.cliente.patch(
            f'{URL}{saida_a.id}/', {'target_account_id': str(self.a.cofrinho.id)}, format='json',
        )

        self.assertEqual(resp.status_code, 200, resp.data)
        parceira_b.refresh_from_db()
        self.assertEqual(parceira_b.account, self.b.conta)

    def test_troca_de_conta_da_parceira_propria_continua_funcionando(self):
        transfer_id = uuid.uuid4()
        saida = Transaction.objects.create(
            user=self.a.usuario, type='TRANSFER_OUT', status='COMPLETED',
            description='TR', amount=Decimal('10.00'), date=date(2026, 9, 2),
            account=self.a.conta, transfer_id=transfer_id,
        )
        entrada = Transaction.objects.create(
            user=self.a.usuario, type='TRANSFER_IN', status='COMPLETED',
            description='TR', amount=Decimal('10.00'), date=date(2026, 9, 2),
            account=self.a.conta, transfer_id=transfer_id,
        )

        resp = self.cliente.patch(
            f'{URL}{saida.id}/', {'target_account_id': str(self.a.cofrinho.id)}, format='json',
        )

        self.assertEqual(resp.status_code, 200, resp.data)
        entrada.refresh_from_db()
        self.assertEqual(entrada.account, self.a.cofrinho)

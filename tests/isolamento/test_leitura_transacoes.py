import uuid
from datetime import date
from decimal import Decimal

from transactions.models import Transaction
from transactions.services import TransactionService
from tests.isolamento.base import DoisUsuariosTestCase

URL = '/api/transactions/'


class LeituraDetalhesDaTransacaoTests(DoisUsuariosTestCase):

    def setUp(self):
        self.cliente = self.como(self.a.usuario)

    def item_da_lista(self, transacao_id):
        resp = self.cliente.get(URL)
        self.assertEqual(resp.status_code, 200)
        itens = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        return next(item for item in itens if item['id'] == str(transacao_id))

    def assert_sem_dados_de_b(self, dados):
        texto = str(dados)
        for nome in ('Conta B', 'Cofrinho B', 'Mercado B', 'Viagem B'):
            self.assertNotIn(nome, texto)
        for obj in (self.b.conta, self.b.cofrinho, self.b.categoria, self.b.tag):
            self.assertNotIn(str(obj.id), texto)

    def test_transacao_de_a_com_conta_categoria_e_tag_de_b_nao_mostra_dados_de_b(self):
        # Ligações cruzadas gravadas à força, como antes da correção
        t = Transaction.objects.create(
            user=self.a.usuario, type='EXPENSE', status='PENDING', description='Forjada',
            amount=Decimal('40.00'), date=date(2026, 9, 3),
            account=self.b.conta, category=self.b.categoria,
        )
        t.tags.set([self.b.tag, self.a.tag])

        detalhe = self.cliente.get(f'{URL}{t.id}/')
        self.assertEqual(detalhe.status_code, 200)

        for dados in (detalhe.data, self.item_da_lista(t.id)):
            self.assertIsNone(dados['account'])
            self.assertIsNone(dados['account_detail'])
            self.assertIsNone(dados['category'])
            self.assertIsNone(dados['category_detail'])
            # A tag de B some da lista; a tag de A continua
            self.assertEqual([str(i) for i in dados['tags']], [str(self.a.tag.id)])
            self.assertEqual([tag['name'] for tag in dados['tags_detail']], ['Viagem A'])
            self.assert_sem_dados_de_b(dados)

    def test_transferencia_com_parceira_forjada_em_outro_usuario_nao_mostra_a_parceira(self):
        # A parceira gravada à força em B, com o mesmo transfer_id da perna de A
        transfer_id = uuid.uuid4()
        perna_de_a = Transaction.objects.create(
            user=self.a.usuario, type='TRANSFER_OUT', description='TR - Para: ?',
            amount=Decimal('25.00'), date=date(2026, 9, 4), account=self.a.conta,
            transfer_id=transfer_id,
        )
        Transaction.objects.create(
            user=self.b.usuario, type='TRANSFER_IN', description='TR - De: ?',
            amount=Decimal('999.00'), date=date(2026, 9, 4), account=self.b.conta,
            transfer_id=transfer_id,
        )

        detalhe = self.cliente.get(f'{URL}{perna_de_a.id}/')
        self.assertEqual(detalhe.status_code, 200)

        for dados in (detalhe.data, self.item_da_lista(perna_de_a.id)):
            self.assertIsNone(dados['related_transaction'])
            self.assert_sem_dados_de_b(dados)
            self.assertNotIn('999.00', str(dados))

    def test_parceira_de_a_na_conta_de_b_nao_mostra_o_nome_da_conta(self):
        transfer_id = TransactionService.create_transfer(
            user=self.a.usuario, account_from=self.a.conta, account_to=self.a.cofrinho,
            amount=Decimal('25.00'), date=date(2026, 9, 4),
        )
        saida = Transaction.objects.get(transfer_id=transfer_id, type='TRANSFER_OUT')
        entrada = Transaction.objects.get(transfer_id=transfer_id, type='TRANSFER_IN')
        # Ligação cruzada gravada à força na parceira
        Transaction.objects.filter(pk=entrada.pk).update(account=self.b.conta)

        detalhe = self.cliente.get(f'{URL}{saida.id}/')

        self.assertEqual(detalhe.status_code, 200)
        self.assertEqual(detalhe.data['related_transaction']['id'], entrada.id)
        self.assertEqual(detalhe.data['related_transaction']['account_name'], 'Desconhecida')
        self.assertNotIn('Conta B', str(detalhe.data))

    def test_formato_da_resposta_das_transacoes_normais_nao_muda(self):
        t = Transaction.objects.create(
            user=self.a.usuario, type='EXPENSE', status='PENDING', description='Normal',
            amount=Decimal('40.00'), date=date(2026, 9, 3),
            account=self.a.conta, category=self.a.categoria,
        )
        t.tags.set([self.a.tag])
        transfer_id = TransactionService.create_transfer(
            user=self.a.usuario, account_from=self.a.conta, account_to=self.a.cofrinho,
            amount=Decimal('25.00'), date=date(2026, 9, 4),
        )
        saida = Transaction.objects.get(transfer_id=transfer_id, type='TRANSFER_OUT')
        entrada = Transaction.objects.get(transfer_id=transfer_id, type='TRANSFER_IN')

        detalhe = self.cliente.get(f'{URL}{t.id}/')
        transferencia = self.cliente.get(f'{URL}{saida.id}/')

        self.assertEqual(detalhe.status_code, 200)
        self.assertEqual(detalhe.data['account'], self.a.conta.id)
        self.assertEqual(detalhe.data['account_detail'], {'id': self.a.conta.id, 'name': 'Conta A'})
        self.assertEqual(detalhe.data['category'], self.a.categoria.id)
        self.assertEqual(detalhe.data['category_detail']['id'], str(self.a.categoria.id))
        self.assertEqual(detalhe.data['category_detail']['name'], 'Mercado A')
        self.assertEqual(detalhe.data['tags'], [self.a.tag.id])
        self.assertEqual(
            [dict(tag) for tag in detalhe.data['tags_detail']],
            [{'id': str(self.a.tag.id), 'name': 'Viagem A', 'color': None}],
        )
        self.assertEqual(self.item_da_lista(t.id), detalhe.data)

        self.assertEqual(transferencia.status_code, 200)
        self.assertEqual(transferencia.data['related_transaction'], {
            'id': entrada.id, 'account_name': 'Cofrinho A',
            'amount': Decimal('25.00'), 'type': 'TRANSFER_IN',
        })

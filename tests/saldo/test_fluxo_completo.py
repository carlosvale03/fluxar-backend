"""
Sequência de operações com o saldo conferido (Success Criteria da spec).

Um único teste percorre pela API transações avulsas, transferência, série
recorrente, compra no cartão com pagamento e estorno da fatura, ajuste de
saldo e exclusão de uma conta zerada. Depois de cada passo, cada conta tem o
saldo guardado igual ao de `accounts.saldo.calcular` (SALDO-01) e ao valor
esperado calculado à mão, a lista de contas mostra esse mesmo valor
(SALDO-28) e o dashboard soma só as contas ativas (SALDO-29, SALDO-30).
"""
from decimal import Decimal

from accounts.models import Account
from accounts.saldo import calcular
from transactions.models import Transaction
from tests.saldo.base import SaldoTestCase, URL_TRANSACOES

LIQUIDAS = ('CHECKING', 'SAVINGS', 'WALLET')


def decimal(valor):
    return Decimal(str(valor)).quantize(Decimal('0.01'))


class FluxoCompletoTests(SaldoTestCase):

    def setUp(self):
        super().setUp()
        self.reserva = Account.objects.create(
            user=self.a.usuario, name='Reserva', type='CHECKING',
            initial_balance=Decimal('0.00'),
        )
        self.carteira = Account.objects.get(user=self.a.usuario, name='Carteira')
        # Valor esperado de cada conta, de todos os usuários, mantido à mão
        self.esperado = {c.pk: c.initial_balance for c in Account.objects.all()}

    # Conferência

    def conferir(self, passo):
        for conta in Account.objects.all():
            with self.subTest(passo=passo, conta=conta.name):
                self.assertEqual(conta.balance, calcular(conta))
                self.assertEqual(conta.balance, self.esperado[conta.pk])

        ativas = Account.objects.filter(user=self.a.usuario, is_active=True)
        resp = self.cliente.get('/api/accounts/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            {c['id']: Decimal(c['balance']) for c in resp.data},
            {str(c.pk): self.esperado[c.pk] for c in ativas},
            passo,
        )

        resp = self.cliente.get('/api/reports/dashboard/')
        self.assertEqual(resp.status_code, 200, resp.data)
        resumo = resp.data['summary']
        liquido = sum((self.esperado[c.pk] for c in ativas if c.type in LIQUIDAS), Decimal('0.00'))
        total = sum((self.esperado[c.pk] for c in ativas), Decimal('0.00'))
        self.assertEqual(decimal(resumo['total_liquid_balance']), liquido, passo)
        self.assertEqual(decimal(resumo['total_balance']), total, passo)

    def mover(self, conta, valor):
        self.esperado[conta.pk] += Decimal(valor)

    def soma_de_a(self):
        return sum(
            (self.esperado[c.pk] for c in Account.objects.filter(user=self.a.usuario)),
            Decimal('0.00'),
        )

    # Chamadas

    def criar(self, **corpo):
        dados = {
            'status': 'COMPLETED', 'date': '2026-09-15',
            'account': str(self.a.conta.id), 'category': str(self.a.despesa.id),
        }
        dados.update(corpo)
        resp = self.cliente.post(URL_TRANSACOES, dados, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return resp.data['id']

    def alterar(self, tx_id, **corpo):
        resp = self.cliente.patch(f'{URL_TRANSACOES}{tx_id}/', corpo, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def excluir(self, tx_id):
        resp = self.cliente.delete(f'{URL_TRANSACOES}{tx_id}/')
        self.assertEqual(resp.status_code, 204)

    def test_saldo_confere_em_toda_a_sequencia(self):
        conta, poupanca, reserva = self.a.conta, self.a.poupanca, self.reserva
        self.conferir('início')

        # 1. Transações avulsas
        self.criar(type='INCOME', amount='200.00', description='Freela', category=str(self.a.receita.id))
        self.mover(conta, '200.00')
        self.conferir('cria receita efetivada')

        despesa = self.criar(type='EXPENSE', amount='80.00', description='Mercado', status='PENDING')
        self.conferir('cria despesa pendente')

        self.alterar(despesa, status='COMPLETED')
        self.mover(conta, '-80.00')
        self.conferir('efetiva a despesa')

        self.alterar(despesa, amount='90.50')
        self.mover(conta, '-10.50')
        self.conferir('edita o valor da despesa')

        self.alterar(despesa, account=str(poupanca.id))
        self.mover(conta, '90.50')
        self.mover(poupanca, '-90.50')
        self.conferir('move a despesa para a poupança')

        self.excluir(despesa)
        self.mover(poupanca, '90.50')
        self.conferir('exclui a despesa')

        # 2. Transferência
        soma = self.soma_de_a()
        resp = self.cliente.post(f'{URL_TRANSACOES}transfer/', {
            'account_from': str(conta.id), 'account_to': str(poupanca.id),
            'amount': '100.00', 'date': '2026-09-15', 'description': 'Reserva',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        saida = Transaction.objects.get(user=self.a.usuario, type='TRANSFER_OUT')
        self.mover(conta, '-100.00')
        self.mover(poupanca, '100.00')
        self.conferir('cria a transferência')

        self.alterar(saida.id, amount='150.00')
        self.mover(conta, '-50.00')
        self.mover(poupanca, '50.00')
        self.conferir('edita o valor da transferência')

        self.alterar(saida.id, target_account_id=str(reserva.id))
        self.mover(poupanca, '-150.00')
        self.mover(reserva, '150.00')
        self.conferir('troca o destino da transferência')

        self.excluir(saida.id)
        self.mover(conta, '150.00')
        self.mover(reserva, '-150.00')
        self.assertFalse(Transaction.objects.filter(transfer_id=saida.transfer_id).exists())
        self.assertEqual(self.soma_de_a(), soma)
        self.conferir('exclui a transferência')

        # 3. Série recorrente com a primeira efetivada
        primeira = self.criar(
            type='INCOME', amount='5000.00', description='Salário', date='2026-09-05',
            category=str(self.a.receita.id), is_recurring=True, frequency='MONTHLY',
        )
        serie = Transaction.objects.get(pk=primeira).recurring_source
        ocorrencias = list(Transaction.objects.filter(recurring_source=serie).order_by('date'))
        self.assertEqual(len(ocorrencias), 12)
        self.assertEqual([t.status for t in ocorrencias[1:]], ['PENDING'] * 11)
        self.mover(conta, '5000.00')
        self.conferir('cria a série')

        self.alterar(ocorrencias[1].id, status='COMPLETED')
        self.mover(conta, '5000.00')
        self.conferir('efetiva a segunda ocorrência')

        resp = self.cliente.patch(f'{URL_TRANSACOES}bulk-update/', {
            'recurring_source': str(serie.id), 'amount': '5500.00', 'account': str(poupanca.id),
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        pendentes = Transaction.objects.filter(recurring_source=serie, status='PENDING')
        self.assertEqual(pendentes.count(), 10)
        self.assertEqual(set(pendentes.values_list('account_id', 'amount')), {(poupanca.pk, Decimal('5500.00'))})
        self.conferir('altera todas as ocorrências')

        resp = self.cliente.delete(f'{URL_TRANSACOES}bulk-delete/?recurring_source={serie.id}')
        self.assertIn(resp.status_code, (200, 204))
        self.assertEqual(
            list(Transaction.objects.filter(recurring_source=serie).values_list('status', flat=True)),
            ['COMPLETED', 'COMPLETED'],
        )
        self.conferir('exclui a série')

        # 4. Compra no cartão, pagamento, estorno e novo pagamento da fatura
        resp = self.cliente.post(f'{URL_TRANSACOES}credit-card-expense/', {
            'credit_card': str(self.a.cartao.id), 'amount': '300.00', 'date': '2026-09-05',
            'description': 'Loja', 'category': str(self.a.despesa.id),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        compra = Transaction.objects.get(pk=resp.data[0]['id'])
        self.assertEqual(compra.status, 'PENDING')
        self.conferir('compra no cartão')

        url_fatura = f'/api/invoices/{compra.invoice_id}/'
        pagamento = {'account_id': str(conta.id), 'amount': '300.00', 'date': '2026-09-20'}
        resp = self.cliente.post(f'{url_fatura}pay/', pagamento, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.mover(conta, '-300.00')
        self.conferir('paga a fatura')

        resp = self.cliente.post(f'{url_fatura}unpay/', format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.mover(conta, '300.00')
        self.conferir('estorna a fatura')

        resp = self.cliente.post(f'{url_fatura}pay/', pagamento, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.mover(conta, '-300.00')
        self.conferir('paga a fatura de novo')

        # 5. Ajuste de saldo
        resp = self.cliente.post(
            f'/api/accounts/{conta.id}/adjust-balance/', {'new_balance': '10000.10'}, format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.esperado[conta.pk] = Decimal('10000.10')
        self.conferir('ajusta o saldo')

        # 6. Exclusão de uma conta zerada
        self.assertEqual(self.esperado[reserva.pk], Decimal('0.00'))
        resp = self.cliente.delete(f'/api/accounts/{reserva.id}/')
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Account.objects.get(pk=reserva.pk).is_active)
        self.conferir('exclui a conta zerada')

        # Os números do fim, conferidos de uma vez
        self.assertEqual(self.esperado[conta.pk], Decimal('10000.10'))
        self.assertEqual(self.esperado[poupanca.pk], Decimal('0.00'))
        self.assertEqual(self.esperado[self.carteira.pk], Decimal('0.00'))

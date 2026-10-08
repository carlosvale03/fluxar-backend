from decimal import Decimal

from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from accounts.models import Account, CreditCard, CreditCardInvoice
from budgets.models import Budget
from core.isolation import find_cross_links, fix_cross_links
from goals.models import Goal, GoalDeposit
from reports.models import FocusedMonitorItem
from transactions.models import Category, RecurringTransaction, Tag, Transaction
from transactions.services import TransactionService
from tests.isolamento.base import DoisUsuariosTestCase
from tests.isolamento.ligacoes import DIA, gravar_ligacoes_cruzadas


def estado(model):
    """Todos os registros do model, campo a campo, para comparar antes e depois."""
    return sorted(model.objects.values(), key=str)


MODELOS = (
    Account, CreditCard, CreditCardInvoice, Budget, Goal, GoalDeposit,
    FocusedMonitorItem, Category, Tag, RecurringTransaction, Transaction,
)


class CorrecaoDeLigacoesCruzadasTests(DoisUsuariosTestCase):

    def setUp(self):
        self.r = gravar_ligacoes_cruzadas(self.a, self.b, self.categoria_modelo)

        # Movimentos próprios de B na conta que recebeu a receita de A
        Transaction.objects.create(
            user=self.b.usuario, type='EXPENSE', status='COMPLETED', description='Conta de luz',
            amount=Decimal('100.00'), date=DIA, account=self.b.conta,
        )
        Transaction.objects.create(
            user=self.b.usuario, type='INCOME', status='PENDING', description='A receber',
            amount=Decimal('50.00'), date=DIA, account=self.b.conta,
        )
        # Saldo guardado como o signal antigo deixava (1000 + 500 de A - 100);
        # com o recálculo do razão (AD-038), os signals não chegam mais a ele
        Account.objects.filter(pk=self.b.conta.pk).update(balance=Decimal('1400.00'))
        # Compra própria de B na fatura que recebeu a compra de A, e o total
        # guardado como o signal antigo deixava (120 de B + 70 de A)
        Transaction.objects.create(
            user=self.b.usuario, type='CREDIT_CARD', status='PENDING', description='Compra',
            amount=Decimal('120.00'), date=DIA, credit_card=self.b.cartao, invoice=self.b.fatura,
        )
        CreditCardInvoice.objects.filter(pk=self.b.fatura.pk).update(total_amount=Decimal('190.00'))
        # Aporte e resgate próprios na meta de A, que recebeu o aporte da conta de
        # B, e o valor guardado contando esse aporte (300 - 50 + 200)
        GoalDeposit.objects.create(goal=self.a.meta, account=self.a.cofrinho, amount=Decimal('300.00'), type='DEPOSIT', date=DIA)
        GoalDeposit.objects.create(goal=self.a.meta, account=self.a.cofrinho, amount=Decimal('50.00'), type='WITHDRAWAL', date=DIA)
        Goal.objects.filter(pk=self.a.meta.pk).update(current_amount=Decimal('450.00'))

    def test_cada_ligacao_e_desfeita_conforme_a_tabela(self):
        r = self.r

        relatorio = fix_cross_links(apps)

        self.assertEqual(relatorio.ligacoes, 18)
        # Transação: a relação alheia vira nula e a própria continua
        for transacao, relacao in (
            (r.t_conta, 'account'), (r.t_cartao, 'credit_card'), (r.t_fatura, 'invoice'),
            (r.t_categoria, 'category'), (r.t_modelo, 'category'),
            (r.t_parcela, 'parent_transaction'), (r.t_recorrente, 'recurring_source'),
        ):
            transacao.refresh_from_db()
            self.assertIsNone(getattr(transacao, f'{relacao}_id'), relacao)
        self.assertEqual(r.t_fatura.credit_card_id, self.a.cartao.id)
        self.assertEqual(r.t_categoria.account_id, self.a.conta.id)
        # Tag: sai só a tag de B
        self.assertEqual(list(r.t_tag.tags.all()), [self.a.tag])
        # Série recorrente
        r.serie_a.refresh_from_db()
        self.assertEqual((r.serie_a.account_id, r.serie_a.credit_card_id, r.serie_a.category_id), (None, None, None))
        # Categoria-pai, conta do cartão e conta da meta
        self.assertIsNone(Category.objects.get(pk=r.categoria_a.pk).parent_id)
        self.assertIsNone(CreditCard.objects.get(pk=self.a.cartao.pk).account_id)
        self.assertIsNone(Goal.objects.get(pk=self.a.meta.pk).account_id)
        # Orçamento, monitores e aporte ligados a objetos de B são excluídos
        self.assertFalse(Budget.objects.filter(pk=r.orcamento.pk).exists())
        self.assertFalse(FocusedMonitorItem.objects.filter(pk__in=[r.monitor_categoria.pk, r.monitor_tag.pk]).exists())
        self.assertFalse(GoalDeposit.objects.filter(pk=r.aporte.pk).exists())

        self.assertEqual(find_cross_links(apps), [])

    def test_recalcula_saldo_da_conta_total_da_fatura_e_valor_da_meta(self):
        # Antes: o saldo guardado de B conta a receita de A (1000 + 500 - 100)
        self.assertEqual(Account.objects.get(pk=self.b.conta.pk).balance, Decimal('1400.00'))

        relatorio = fix_cross_links(apps)

        self.assertEqual((relatorio.contas, relatorio.faturas, relatorio.metas), (1, 1, 1))
        # SALDO-01: inicial 1000 - despesa efetivada 100; a receita pendente fica de fora
        self.assertEqual(Account.objects.get(pk=self.b.conta.pk).balance, Decimal('900.00'))
        # Fatura de B: só a compra de B
        self.assertEqual(CreditCardInvoice.objects.get(pk=self.b.fatura.pk).total_amount, Decimal('120.00'))
        # Meta de A: aportes menos resgates restantes (AD-028)
        self.assertEqual(Goal.objects.get(pk=self.a.meta.pk).current_amount, Decimal('250.00'))

    def aportes_com_transferencia_pendente(self):
        """
        Dois aportes na meta de A com a transferência pendente: um antigo, só
        com o `transaction_id`, e um ligado às duas pernas. Pela META-01, os
        dois ficam fora do valor da meta.
        """
        for valor, ligado in (('70.00', False), ('30.00', True)):
            transfer_id = TransactionService.create_transfer(
                user=self.a.usuario, account_from=self.a.conta, account_to=self.a.cofrinho,
                amount=Decimal(valor), date=DIA, description='Aporte',
            )
            Transaction.objects.filter(transfer_id=transfer_id).update(status='PENDING')
            pernas = {}
            if ligado:
                pernas = {
                    'transacao_saida': Transaction.objects.get(transfer_id=transfer_id, type='TRANSFER_OUT'),
                    'transacao_entrada': Transaction.objects.get(transfer_id=transfer_id, type='TRANSFER_IN'),
                }
            GoalDeposit.objects.create(
                goal=self.a.meta, account=self.a.conta, amount=Decimal(valor), type='DEPOSIT', date=DIA,
                transaction_id=transfer_id, **pernas,
            )

    def test_valor_da_meta_conta_so_os_aportes_efetivados(self):
        self.aportes_com_transferencia_pendente()

        fix_cross_links(apps)

        # 300 - 50 dos registros sem transação; os aportes pendentes ficam de fora (META-01)
        self.assertEqual(Goal.objects.get(pk=self.a.meta.pk).current_amount, Decimal('250.00'))

    def test_valor_da_meta_com_o_registro_historico_da_migracao(self):
        self.aportes_com_transferencia_pendente()
        estado = MigrationExecutor(connection).loader.project_state(
            ('transactions', '0007_corrige_isolamento'),
        )

        fix_cross_links(estado.apps)

        self.assertEqual(Goal.objects.get(pk=self.a.meta.pk).current_amount, Decimal('250.00'))

    def test_subcategoria_pendurada_vira_raiz_e_volta_para_a_lista_do_dono(self):
        cliente = self.como(self.a.usuario)
        antes = cliente.get('/api/categories/')
        self.assertNotIn(str(self.r.categoria_a.id), [c['id'] for c in antes.data])

        fix_cross_links(apps)

        depois = cliente.get('/api/categories/')
        self.assertEqual(depois.status_code, 200)
        raiz = next(c for c in depois.data if c['id'] == str(self.r.categoria_a.id))
        self.assertEqual((raiz['name'], raiz['parent']), ('Pendurada A', None))

    def test_rodar_a_correcao_duas_vezes_da_o_mesmo_resultado(self):
        fix_cross_links(apps)
        depois_da_primeira = [estado(model) for model in MODELOS]

        relatorio = fix_cross_links(apps)

        self.assertEqual(relatorio, (0, 0, 0, 0))
        self.assertEqual([estado(model) for model in MODELOS], depois_da_primeira)

    def test_dados_sem_ligacao_cruzada_nao_mudam(self):
        # Saldo guardado divergente numa conta sem ligação cruzada: acertar esse
        # saldo é da spec saldo (SALDO-38), não desta correção
        Account.objects.filter(pk=self.a.conta.pk).update(balance=Decimal('12345.00'))
        corrigidos = {
            Transaction: {self.r.t_conta.pk, self.r.t_cartao.pk, self.r.t_fatura.pk, self.r.t_categoria.pk,
                          self.r.t_modelo.pk, self.r.t_parcela.pk, self.r.t_recorrente.pk, self.r.t_tag.pk},
            RecurringTransaction: {self.r.serie_a.pk},
            Category: {self.r.categoria_a.pk},
            CreditCard: {self.a.cartao.pk},
            Goal: {self.a.meta.pk},
            Budget: {self.r.orcamento.pk},
            FocusedMonitorItem: {self.r.monitor_categoria.pk, self.r.monitor_tag.pk},
            GoalDeposit: {self.r.aporte.pk},
            Account: {self.b.conta.pk},
            CreditCardInvoice: {self.b.fatura.pk},
        }

        def sem_ligacao(model):
            ids = corrigidos.get(model, set())
            return sorted(model.objects.exclude(pk__in=ids).values(), key=str)

        antes = [sem_ligacao(model) for model in MODELOS]

        fix_cross_links(apps)

        self.assertEqual([sem_ligacao(model) for model in MODELOS], antes)
        self.assertEqual(Account.objects.get(pk=self.a.conta.pk).balance, Decimal('12345.00'))
        # Nas transações corrigidas, só a relação alheia muda
        transacao = Transaction.objects.get(pk=self.r.t_conta.pk)
        self.assertEqual(
            (transacao.user, transacao.type, transacao.status, transacao.amount, transacao.date),
            (self.a.usuario, 'INCOME', 'COMPLETED', Decimal('500.00'), DIA),
        )

"""
Repetidos num envio que mistura receitas, despesas e transferências
(IMPCOMP-31, IMPCOMP-46): a regra de IMPORT-36 vale para as receitas e
despesas e a de IMPORT-37 para as transferências no mesmo lote; `marcar`
aponta as repetidas sem gravar nada.
"""
import uuid
from datetime import date
from decimal import Decimal

from data_exchange.importacao.gravacao import Gravacao
from data_exchange.importacao.interpretacao import LinhaImportada
from data_exchange.importacao.repetidos import Repetidos
from transactions.models import Transaction
from transactions.services import TransactionService

from .base import ImportacaoTestCase


class RepetidosMistosTests(ImportacaoTestCase):

    def lancar(self, tipo, valor, descricao, dia=10):
        Transaction.objects.create(
            user=self.a.usuario, account=self.a.conta, type=tipo, description=descricao,
            amount=Decimal(valor), date=date(2026, 9, dia),
        )

    def transferir(self, valor, dia=10):
        TransactionService.create_transfer(
            user=self.a.usuario, account_from=self.a.conta, account_to=self.a.poupanca,
            amount=Decimal(valor), date=date(2026, 9, dia), description='Reserva',
        )

    def linha(self, numero, tipo, valor, descricao='Reserva', dia=10, destino=None):
        return LinhaImportada(
            numero=numero, data=date(2026, 9, dia), valor=Decimal(valor), tipo=tipo,
            descricao=descricao, conta=self.a.conta, destino=destino, aba='Extrato',
        )

    def lote(self):
        return [
            self.linha(2, 'INCOME', '1500.00', 'Salário'),
            self.linha(3, 'EXPENSE', '45.00', 'Padaria'),
            self.linha(4, 'TRANSFER', '200.00', destino=self.a.poupanca),
        ]

    def test_lote_misto_ja_importado_e_todo_ignorado(self):
        """IMPCOMP-46: receita, despesa e transferência já gravadas são ignoradas no mesmo envio."""
        self.lancar('INCOME', '1500.00', 'Salário')
        self.lancar('EXPENSE', '45.00', 'Padaria')
        self.transferir('200.00')
        antes = Transaction.objects.count()

        resumo = Gravacao(self.a.usuario).importar(self.lote())

        self.assertEqual(
            (resumo['total'], resumo['imported'], resumo['ignored'], resumo['rejected']), (3, 0, 3, 0),
        )
        self.assertEqual(Transaction.objects.count(), antes)

    def test_lote_misto_novo_e_gravado_e_a_reimportacao_ignora_tudo(self):
        """IMPCOMP-46: o primeiro envio grava as três; o segundo, igual, não grava nenhuma."""
        primeiro = Gravacao(self.a.usuario).importar(self.lote())
        segundo = Gravacao(self.a.usuario).importar(self.lote())
        self.assertEqual((primeiro['imported'], primeiro['ignored']), (3, 0))
        self.assertEqual((segundo['imported'], segundo['ignored']), (0, 3))

    def test_marcar_aponta_as_repetidas_sem_gravar(self):
        """IMPCOMP-31: só a despesa e a transferência existentes são repetidas; nada é criado."""
        self.lancar('EXPENSE', '45.00', 'Padaria')
        self.transferir('200.00')
        lote = self.lote() + [self.linha(5, 'EXPENSE', '45.00', 'Padaria')]
        antes = Transaction.objects.count()

        marcadas = Repetidos(self.a.usuario, lote).marcar(lote)

        # A segunda "Padaria" passa da contagem existente: não é repetida (IMPORT-38)
        self.assertEqual(marcadas, [False, True, True, False])
        self.assertEqual(Transaction.objects.count(), antes)

    def test_marcar_com_conta_provisoria_nao_encontra_repetidas(self):
        """IMPCOMP-31: a conta a criar ainda não tem transações; as linhas dela nunca são repetidas."""
        self.lancar('EXPENSE', '45.00', 'Padaria')
        provisoria = type(self.a.conta)(pk=uuid.uuid4(), user=self.a.usuario, name='Nova')
        linha = LinhaImportada(
            numero=2, data=date(2026, 9, 10), valor=Decimal('45.00'), tipo='EXPENSE',
            descricao='Padaria', conta=provisoria,
        )
        self.assertEqual(Repetidos(self.a.usuario, [linha]).marcar([linha]), [False])

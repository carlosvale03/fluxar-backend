"""
Contas criadas pela importação completa e saldo (IMPCOMP-25 a IMPCOMP-27,
IMPCOMP-29).

As contas novas têm o nome, o tipo, a instituição e a cor do plano; depois
da gravação, o saldo de cada uma é o saldo atual informado, com
transferências e pendentes; o limite de contas vale para todas de uma vez.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.db import transaction

from accounts.models import Account
from core import travas
from core.travas import LimiteDoPlano, conferir_limite
from data_exchange.importacao.contas import acertar_saldos, criar_contas
from data_exchange.importacao.gravacao import Gravacao
from data_exchange.importacao.interpretacao import LinhaImportada
from tests.permissoes.base import fechar, liberacao_de_testes

from .base import ImportacaoTestCase


def criar(nome, tipo='CHECKING', saldo='0.00', institution=None, color=None):
    return {'acao': 'criar', 'nome': nome, 'tipo': tipo, 'saldo_atual': saldo,
            'institution': institution, 'color': color}


class ContasDaImportacaoTestCase(ImportacaoTestCase):

    def setUp(self):
        super().setUp()
        cache.clear()
        travas.invalidar()
        self.addCleanup(travas.invalidar)
        liberacao_de_testes(False)

    def contas_do_usuario(self):
        return Account.objects.filter(user=self.a.usuario).count()

    def linha(self, numero, conta, tipo, valor, status='COMPLETED', destino=None, dia=10):
        return LinhaImportada(
            numero=numero, data=date(2026, 9, dia), valor=Decimal(valor), tipo=tipo,
            descricao=f'Linha {numero}', status=status, conta=conta, destino=destino, aba='Extrato',
        )


class CriarContasTests(ContasDaImportacaoTestCase):

    def test_contas_criadas_tem_nome_tipo_instituicao_e_cor_do_plano(self):
        """IMPCOMP-25: só as contas a criar, com os dados do plano e saldo inicial zero."""
        criadas = criar_contas(self.a.usuario, {
            'Nubank': criar('Nubank PF', 'CHECKING', '10.00', 'nubank', '#820AD1'),
            'Reserva': criar('Reserva', 'SAVINGS'),
            'Corrente A': {'acao': 'vincular', 'id': str(self.a.conta.pk)},
        })

        self.assertEqual(list(criadas), ['Nubank', 'Reserva'])
        nubank = Account.objects.get(pk=criadas['Nubank'].pk)
        self.assertEqual(
            (nubank.user, nubank.name, nubank.type, nubank.institution, nubank.color, nubank.initial_balance, nubank.is_active),
            (self.a.usuario, 'Nubank PF', 'CHECKING', 'nubank', '#820AD1', Decimal('0.00'), True),
        )
        reserva = Account.objects.get(pk=criadas['Reserva'].pk)
        self.assertEqual((reserva.name, reserva.type, reserva.institution, reserva.color), ('Reserva', 'SAVINGS', None, None))


class SaldoTests(ContasDaImportacaoTestCase):

    def test_saldo_da_conta_criada_e_o_saldo_atual_informado(self):
        """IMPCOMP-26: com receita, despesa, pendente e transferências de e para uma conta vinculada."""
        criadas = criar_contas(self.a.usuario, {
            'Nova': criar('Nova', saldo='1234.56'),
            'Só pendentes': criar('Só pendentes', saldo='-50.00'),
        })
        nova, pendentes = criadas['Nova'], criadas['Só pendentes']
        Gravacao(self.a.usuario).importar([
            self.linha(2, nova, 'INCOME', '3000.00'),
            self.linha(3, nova, 'EXPENSE', '120.40'),
            self.linha(4, nova, 'EXPENSE', '999.00', status='PENDING'),
            self.linha(5, nova, 'TRANSFER', '500.00', destino=self.a.poupanca),
            self.linha(6, self.a.conta, 'TRANSFER', '80.00', destino=nova),
            self.linha(7, pendentes, 'EXPENSE', '30.00', status='PENDING'),
        ])

        acertar_saldos(criadas, {'Nova': Decimal('1234.56'), 'Só pendentes': Decimal('-50.00')})

        nova.refresh_from_db()
        pendentes.refresh_from_db()
        # Efeito das efetivadas na "Nova": 3000 - 120,40 - 500 + 80 = 2459,60
        self.assertEqual((nova.balance, nova.initial_balance), (Decimal('1234.56'), Decimal('-1225.04')))
        # Pendentes não mexem no saldo: o saldo inicial é o próprio saldo atual
        self.assertEqual((pendentes.balance, pendentes.initial_balance), (Decimal('-50.00'), Decimal('-50.00')))
        # As contas vinculadas mantêm o saldo inicial e recebem só o efeito das transferências
        self.a.poupanca.refresh_from_db()
        self.a.conta.refresh_from_db()
        self.assertEqual((self.a.poupanca.initial_balance, self.a.poupanca.balance), (Decimal('0.00'), Decimal('500.00')))
        self.assertEqual((self.a.conta.initial_balance, self.a.conta.balance), (Decimal('1000.00'), Decimal('920.00')))

    def test_saldo_atual_zero_sem_transacoes(self):
        """IMPCOMP-26: sem transações, o saldo inicial e o saldo são o informado."""
        criadas = criar_contas(self.a.usuario, {'Vazia': criar('Vazia')})
        acertar_saldos(criadas, {'Vazia': Decimal('0.00')})
        vazia = Account.objects.get(pk=criadas['Vazia'].pk)
        self.assertEqual((vazia.initial_balance, vazia.balance), (Decimal('0.00'), Decimal('0.00')))


class LimiteDeContasTests(ContasDaImportacaoTestCase):

    def test_tres_contas_com_duas_vagas_sao_recusadas_sem_gravar(self):
        """IMPCOMP-27: 403 plan_limit_reached e nenhuma conta criada."""
        usadas = travas.uso(self.a.usuario, 'limite_contas')
        fechar('limite_contas', limite=usadas + 2)
        antes = self.contas_do_usuario()

        with self.assertRaises(LimiteDoPlano) as recusa:
            criar_contas(self.a.usuario, {n: criar(n) for n in ('Uma', 'Duas', 'Três')})

        self.assertEqual((recusa.exception.status_code, recusa.exception.default_code), (403, 'plan_limit_reached'))
        self.assertEqual(recusa.exception.extras, {'feature': 'limite_contas', 'limit': usadas + 2})
        self.assertEqual(self.contas_do_usuario(), antes)

    def test_duas_contas_com_duas_vagas_passam(self):
        """IMPCOMP-27: até o limite, todas são criadas."""
        fechar('limite_contas', limite=travas.uso(self.a.usuario, 'limite_contas') + 2)
        antes = self.contas_do_usuario()
        criar_contas(self.a.usuario, {n: criar(n) for n in ('Uma', 'Duas')})
        self.assertEqual(self.contas_do_usuario(), antes + 2)

    def test_conferir_limite_sem_quantidade_continua_igual(self):
        """IMPCOMP-27 sem mudar PERM-16: um item é recusado no limite e aceito abaixo dele."""
        usadas = travas.uso(self.a.usuario, 'limite_contas')
        fechar('limite_contas', limite=usadas)
        with self.assertRaises(LimiteDoPlano):
            conferir_limite(self.a.usuario, 'limite_contas')
        fechar('limite_contas', limite=usadas + 1)
        conferir_limite(self.a.usuario, 'limite_contas')
        # Nenhuma conta a criar não esbarra no limite, mesmo já no limite
        fechar('limite_contas', limite=usadas)
        conferir_limite(self.a.usuario, 'limite_contas', quantidade=0)


class FalhaTests(ContasDaImportacaoTestCase):

    def test_falha_depois_de_criar_as_contas_desfaz_a_criacao(self):
        """IMPCOMP-29: na transação da importação, uma falha que sobe desfaz as contas e as transações."""
        antes = self.contas_do_usuario()
        with patch.object(Gravacao, 'importar', side_effect=RuntimeError('falha')):
            with self.assertRaises(RuntimeError), transaction.atomic():
                criadas = criar_contas(self.a.usuario, {'Nova': criar('Nova')})
                Gravacao(self.a.usuario).importar([self.linha(2, criadas['Nova'], 'INCOME', '10.00')])
        self.assertEqual(self.contas_do_usuario(), antes)
        self.assertFalse(Account.objects.filter(user=self.a.usuario, name='Nova').exists())

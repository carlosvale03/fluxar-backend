"""
Referências do mês e histórico (SALARIO-52, SALARIO-53, SALARIO-56).

Hoje é 10/10/2026 em Brasília: o mês atual é outubro, e os 3 últimos meses
completos são julho, agosto e setembro.
"""
from datetime import date
from decimal import Decimal

from accounts.faturas import obter_fatura
from accounts.models import CreditCard
from transactions.models import Category, ClasseDeDespesa, RecurringTransaction, Transaction

from .base import URL_REFERENCIAS, SalarioTestCase, hoje_em, receita


class ReferenciasTestCase(SalarioTestCase):

    def referencias(self):
        with hoje_em(2026, 10, 10):
            resposta = self.client.get(URL_REFERENCIAS)
        self.assertEqual(resposta.status_code, 200, resposta.data)
        return resposta.data

    def categoria(self, nome, tipo='EXPENSE'):
        return Category.objects.get(user=self.a.usuario, name=nome, type=tipo, parent__isnull=True)

    def despesa(self, valor, data, categoria, status='COMPLETED', **extra):
        return Transaction.objects.create(
            user=self.a.usuario, type='EXPENSE', status=status, account=self.a.conta, category=categoria,
            description='Despesa', amount=Decimal(valor), date=data, **extra,
        )

    def classe(self, historico, nome):
        [linha] = [c for c in historico['by_class'] if c['class_name'] == nome]
        return linha


class ComprometidoTests(ReferenciasTestCase):

    def test_aluguel_recorrente_pendente_e_fatura_do_mes_somam_o_comprometido(self):
        casa = self.categoria('Casa')
        serie = RecurringTransaction.objects.create(
            user=self.a.usuario, description='Aluguel', amount=Decimal('1200.00'), type='EXPENSE',
            account=self.a.conta, category=casa, frequency='MONTHLY', start_date=date(2026, 9, 15),
        )
        self.despesa('1200.00', date(2026, 10, 15), casa, status='PENDING', recurring_source=serie)
        # Fora do comprometido: a do mês seguinte, a já paga e a pendente avulsa
        self.despesa('1200.00', date(2026, 11, 15), casa, status='PENDING', recurring_source=serie)
        self.despesa('1200.00', date(2026, 10, 1), casa, recurring_source=serie)
        self.despesa('80.00', date(2026, 10, 20), casa, status='PENDING')
        cartao = CreditCard.objects.create(
            user=self.a.usuario, name='Cartão', limit=Decimal('5000.00'), closing_day=10, due_day=20,
            account=self.a.conta,
        )
        outubro = obter_fatura(cartao, 10, 2026)
        Transaction.objects.create(
            user=self.a.usuario, type='CREDIT_CARD', status='PENDING', account=self.a.conta, credit_card=cartao,
            invoice=outubro, description='Loja', amount=Decimal('450.00'), date=outubro.due_date,
            purchase_date=date(2026, 9, 25),
        )

        comprometido = self.referencias()['committed']

        self.assertEqual(comprometido, {'recurring_pending': '1200.00', 'invoices_due': '450.00', 'total': '1650.00'})


class HistoricoTests(ReferenciasTestCase):

    def test_medias_dos_3_ultimos_meses_completos_por_classe(self):
        comida, lazer = self.categoria('Comida'), self.categoria('Lazer')
        for mes in (7, 8, 9):
            receita(self.a, '3000.00', date(2026, mes, 5))
            self.despesa('1860.00', date(2026, mes, 10), comida)
            self.despesa('300.00', date(2026, mes, 12), lazer)
        # Fora da janela: junho e o mês atual
        receita(self.a, '9000.00', date(2026, 6, 5))
        self.despesa('999.00', date(2026, 10, 2), comida)

        historico = self.referencias()['history']

        self.assertEqual(historico['months_used'], 3)
        self.assertEqual(historico['salary_average'], '3000.00')
        self.assertEqual(historico['expense_average'], '2160.00')
        self.assertEqual(historico['difference_average'], '840.00')
        essencial = self.classe(historico, 'Essencial')
        self.assertEqual((essencial['reference'], essencial['average']), ('ESSENCIAL', '1860.00'))
        dispensavel = self.classe(historico, 'Dispensável')
        self.assertEqual((dispensavel['reference'], dispensavel['average']), ('DISPENSAVEL', '300.00'))
        self.assertEqual(
            essencial['class_id'],
            str(ClasseDeDespesa.objects.get(user=self.a.usuario, nome_normalizado='essencial').pk),
        )

    def test_com_um_mes_completo_usa_so_ele(self):
        receita(self.a, '3000.00', date(2026, 9, 5))
        self.despesa('1500.00', date(2026, 9, 10), self.categoria('Comida'))

        historico = self.referencias()['history']

        self.assertEqual(historico['months_used'], 1)
        self.assertEqual(historico['salary_average'], '3000.00')
        self.assertEqual(self.classe(historico, 'Essencial')['average'], '1500.00')
        self.assertEqual(historico['difference_average'], '1500.00')

    def test_primeira_transacao_no_meio_de_agosto_usa_dois_meses(self):
        receita(self.a, '3000.00', date(2026, 8, 20))
        receita(self.a, '3000.00', date(2026, 9, 5))

        historico = self.referencias()['history']

        self.assertEqual(historico['months_used'], 2)
        self.assertEqual(historico['salary_average'], '3000.00')

    def test_sem_historico_as_medias_ficam_zeradas(self):
        receita(self.a, '3000.00', date(2026, 10, 5))

        historico = self.referencias()['history']

        self.assertEqual(historico['months_used'], 0)
        self.assertEqual(
            (historico['salary_average'], historico['expense_average'], historico['difference_average']),
            ('0.00', '0.00', '0.00'),
        )
        self.assertEqual(
            {c['class_name']: c['average'] for c in historico['by_class']},
            {'Essencial': '0.00', 'Dispensável': '0.00'},
        )

    def test_so_salarios_efetivados_entram_e_despesa_sem_classe_aparece_a_parte(self):
        receita(self.a, '3000.00', date(2026, 9, 5))
        receita(self.a, '500.00', date(2026, 9, 6), status='PENDING')
        receita(self.a, '700.00', date(2026, 9, 7), categoria=self.categoria('Investimento', 'INCOME'))
        mercado = Category.objects.create(user=self.a.usuario, name='Mercado', type='EXPENSE')
        self.despesa('250.00', date(2026, 9, 9), mercado)
        viagens = ClasseDeDespesa.objects.create(
            user=self.a.usuario, nome='Viagens', nome_normalizado='viagens', cor='#000000',
        )
        hotel = Category.objects.create(user=self.a.usuario, name='Hotel', type='EXPENSE', classe=viagens)
        self.despesa('400.00', date(2026, 9, 11), hotel)

        historico = self.referencias()['history']

        self.assertEqual(historico['salary_average'], '3000.00')
        self.assertEqual(historico['expense_average'], '650.00')
        self.assertEqual(historico['by_class'][-1], {
            'class_id': None, 'class_name': 'Sem classe', 'reference': '', 'average': '250.00',
        })
        self.assertEqual(
            self.classe(historico, 'Viagens'),
            {'class_id': str(viagens.pk), 'class_name': 'Viagens', 'reference': '', 'average': '400.00'},
        )

"""
Travas de recurso nas rotas (PERM-15, PERM-22 e PERM-26).

Com a liberação para testes desligada, cada rota de um recurso fechado no
plano do usuário responde 403 `{detail, code: "plan_locked", feature}`; com
a trava aberta, a rota responde normalmente. `personalizar_dashboard`,
`gestao_do_salario` e `vinculos` ainda não têm rota no backend. O dinheiro já
lançado continua movimentável: o cofrinho de uma meta e o pagamento e o
estorno de faturas existentes seguem liberados (PERM-22).
"""
import json
from decimal import Decimal

from rest_framework import status

from accounts.models import Account
from api.models import TravaDePlano
from core import travas
from tests.importacao.base import MAPEAMENTO, arquivo_csv, arquivo_ofx, transacao_ofx
from tests.isolamento.base import criar_dados
from transactions.models import RecurringTransaction, Tag, Transaction

from .base import RECURSOS, PermissoesTestCase, criar_admin, fechar, liberacao_de_testes

BLOQUEADO = 'Este recurso não está disponível no seu plano.'
SEM_ROTA = {'personalizar_dashboard', 'gestao_do_salario', 'vinculos'}


class TravasTestCase(PermissoesTestCase):

    def setUp(self):
        super().setUp()
        self.d = criar_dados('A')
        self.client.force_authenticate(user=self.d.usuario)
        self.serie = self.criar_serie()
        liberacao_de_testes(False)

    def criar_serie(self):
        """Uma despesa mensal recorrente, criada pela API com a liberação ligada."""
        resposta = self.client.post('/api/transactions/', self.corpo_transacao(
            is_recurring=True, frequency='MONTHLY',
        ), format='json')
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)
        return RecurringTransaction.objects.get(user=self.d.usuario)

    def corpo_transacao(self, **extra):
        corpo = {
            'type': 'EXPENSE', 'status': 'COMPLETED', 'description': 'Mercado',
            'amount': '10.00', 'date': '2026-09-10',
            'account': str(self.d.conta.pk), 'category': str(self.d.categoria.pk),
        }
        corpo.update(extra)
        return corpo

    def corpo_compra(self, **extra):
        corpo = {
            'credit_card': str(self.d.cartao.pk), 'amount': '90.00', 'date': '2026-09-05',
            'description': 'Compra', 'category': str(self.d.categoria.pk), 'installments': 1,
        }
        corpo.update(extra)
        return corpo

    def abrir(self, chave, plano='COMMON'):
        TravaDePlano.objects.filter(chave=chave, plano=plano).delete()
        travas.invalidar()

    def assert_travada(self, resposta, chave):
        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN, getattr(resposta, 'data', None))
        self.assertEqual(resposta.data, {'detail': BLOQUEADO, 'code': 'plan_locked', 'feature': chave})

    def conferir(self, chave, chamadas):
        """
        Cada chamada, como (nome, função, status esperado com a trava aberta):
        com a trava fechada no Comum, 403 com a chave; aberta, o status normal.
        """
        fechar(chave)
        for nome, chamar, _ in chamadas:
            with self.subTest(trava='fechada', chamada=nome):
                self.assert_travada(chamar(), chave)
        self.abrir(chave)
        for nome, chamar, esperado in chamadas:
            with self.subTest(trava='aberta', chamada=nome):
                resposta = chamar()
                self.assertEqual(resposta.status_code, esperado, getattr(resposta, 'data', None))


def chamadas_do_catalogo(t):
    """As rotas de cada recurso do catálogo que tem rota, a partir de um `TravasTestCase`."""
    c = t.client
    d = t.d
    return {
        'relatorios_avancados': [
            ('gráficos avançados', lambda: c.get('/api/reports/charts/advanced/'), 200),
        ],
        'comparacao_mensal': [
            ('comparação mensal', lambda: c.get('/api/reports/charts/monthly-comparison/'), 200),
        ],
        'analise_por_tag': [
            ('análise da tag', lambda: c.get('/api/reports/charts/tag-insights/', {'tag_id': str(d.tag.pk)}), 200),
            ('distribuição por tag', lambda: c.get('/api/reports/charts/tag-distribution/'), 200),
        ],
        'monitor_de_foco': [
            ('lista', lambda: c.get('/api/focused-monitors/'), 200),
            ('detalhe', lambda: c.get(f'/api/focused-monitors/{d.monitor.pk}/'), 200),
        ],
        'calendario': [
            ('calendário', lambda: c.get('/api/reports/calendar/'), 200),
        ],
        'orcamentos': [
            ('lista', lambda: c.get('/api/budgets/'), 200),
            ('importação de outro mês', lambda: c.post('/api/budgets/bulk_import/', {
                'source_ids': [str(d.orcamento.pk)], 'month': 10, 'year': 2026,
            }, format='json'), 201),
        ],
        'metas': [
            ('lista', lambda: c.get('/api/goals/'), 200),
            ('aporte', lambda: c.post(f'/api/goals/{d.meta.pk}/deposit/', {
                'amount': '20.00', 'account_id': str(d.conta.pk),
            }, format='json'), 200),
            ('resgate', lambda: c.post(f'/api/goals/{d.meta.pk}/withdraw/', {
                'amount': '5.00', 'account_to': str(d.conta.pk),
            }, format='json'), 200),
            ('histórico', lambda: c.get(f'/api/goals/{d.meta.pk}/history/'), 200),
        ],
        'cartoes': [
            ('criar cartão', lambda: c.post('/api/credit-cards/', {
                'name': 'Novo', 'limit': '500.00', 'closing_day': 1, 'due_day': 10,
                'account_id': str(d.conta.pk),
            }, format='json'), 201),
            ('editar cartão', lambda: c.patch(f'/api/credit-cards/{d.cartao.pk}/', {'name': 'Outro'}, format='json'), 200),
            ('lista geral de faturas', lambda: c.get('/api/invoices/'), 200),
            ('compra no cartão', lambda: c.post(
                '/api/transactions/credit-card-expense/', t.corpo_compra(), format='json',
            ), 201),
        ],
        'compras_parceladas': [
            ('compra em 3x', lambda: c.post(
                '/api/transactions/credit-card-expense/', t.corpo_compra(installments=3), format='json',
            ), 201),
        ],
        'transacoes_recorrentes': [
            ('lançar recorrente', lambda: c.post('/api/transactions/', t.corpo_transacao(
                is_recurring=True, frequency='MONTHLY',
            ), format='json'), 201),
            ('editar a série', lambda: c.patch('/api/transactions/bulk-update/', {
                'recurring_source': str(t.serie.pk), 'description': 'Mercado do mês',
            }, format='json'), 200),
            ('excluir a série', lambda: c.delete(
                f'/api/transactions/bulk-delete/?recurring_source={t.serie.pk}',
            ), 200),
        ],
        'tags': [
            ('lista de tags', lambda: c.get('/api/tags/'), 200),
            ('criar tag', lambda: c.post('/api/tags/', {'name': 'Nova'}, format='json'), 201),
            ('lançar com tags', lambda: c.post('/api/transactions/', t.corpo_transacao(
                tags=[str(d.tag.pk)],
            ), format='json'), 201),
            ('compra com tags', lambda: c.post(
                '/api/transactions/credit-card-expense/', t.corpo_compra(tags=[str(d.tag.pk)]), format='json',
            ), 201),
        ],
        'importacao_ofx': [
            ('importar OFX', lambda: c.post('/api/import/ofx/', {
                'file': arquivo_ofx(transacao_ofx('F1', '20260910', '-12.34', memo='Padaria')),
                'account_id': str(d.conta.pk),
            }, format='multipart'), 200),
        ],
        'importacao_planilha': [
            ('preflight', lambda: c.post('/api/import/spreadsheet/preflight/', {
                'file': arquivo_csv([['Data', 'Descrição', 'Valor'], ['10/09/2026', 'Padaria', '-12,34']]),
                'mapping': json.dumps(MAPEAMENTO), 'import_type': 'INCOME_EXPENSE',
            }, format='multipart'), 200),
            ('importar planilha', lambda: c.post('/api/import/spreadsheet/', {
                'file': arquivo_csv([['Data', 'Descrição', 'Valor'], ['10/09/2026', 'Padaria', '-12,34']]),
                'mapping': json.dumps(MAPEAMENTO), 'import_type': 'INCOME_EXPENSE',
                'account_id': str(d.conta.pk),
            }, format='multipart'), 200),
        ],
        'exportacao_pdf': [
            ('exportar PDF', lambda: c.get('/api/export/transactions/pdf/'), 200),
        ],
        'exportacao_xlsx': [
            ('exportar XLSX', lambda: c.get('/api/export/transactions/xls/'), 200),
        ],
    }


class UmaRotaPorTravaTests(TravasTestCase):
    """Uma verificação por chave do catálogo com rota (PERM-15, PERM-26)."""

    def test_o_catalogo_com_rota_tem_15_chaves(self):
        self.assertEqual(set(chamadas_do_catalogo(self)), set(RECURSOS) - SEM_ROTA)

    def test_relatorios_avancados(self):
        self.conferir('relatorios_avancados', chamadas_do_catalogo(self)['relatorios_avancados'])

    def test_comparacao_mensal(self):
        self.conferir('comparacao_mensal', chamadas_do_catalogo(self)['comparacao_mensal'])

    def test_analise_por_tag(self):
        self.conferir('analise_por_tag', chamadas_do_catalogo(self)['analise_por_tag'])

    def test_monitor_de_foco(self):
        self.conferir('monitor_de_foco', chamadas_do_catalogo(self)['monitor_de_foco'])

    def test_calendario(self):
        self.conferir('calendario', chamadas_do_catalogo(self)['calendario'])

    def test_orcamentos(self):
        self.conferir('orcamentos', chamadas_do_catalogo(self)['orcamentos'])

    def test_metas(self):
        self.conferir('metas', chamadas_do_catalogo(self)['metas'])

    def test_cartoes(self):
        self.conferir('cartoes', chamadas_do_catalogo(self)['cartoes'])

    def test_compras_parceladas(self):
        self.conferir('compras_parceladas', chamadas_do_catalogo(self)['compras_parceladas'])

    def test_transacoes_recorrentes(self):
        self.conferir('transacoes_recorrentes', chamadas_do_catalogo(self)['transacoes_recorrentes'])

    def test_tags(self):
        self.conferir('tags', chamadas_do_catalogo(self)['tags'])

    def test_importacao_ofx(self):
        self.conferir('importacao_ofx', chamadas_do_catalogo(self)['importacao_ofx'])

    def test_importacao_planilha(self):
        self.conferir('importacao_planilha', chamadas_do_catalogo(self)['importacao_planilha'])

    def test_exportacao_pdf(self):
        self.conferir('exportacao_pdf', chamadas_do_catalogo(self)['exportacao_pdf'])

    def test_exportacao_xlsx(self):
        self.conferir('exportacao_xlsx', chamadas_do_catalogo(self)['exportacao_xlsx'])


class LiberacaoLigadaTests(TravasTestCase):

    def test_com_a_liberacao_ligada_nenhuma_rota_do_catalogo_e_travada(self):
        # PERM-23: tudo fechado no Comum, mas a liberação ligada libera tudo
        for chave in RECURSOS:
            fechar(chave)
        liberacao_de_testes(True)
        for chave, chamadas in chamadas_do_catalogo(self).items():
            for nome, chamar, esperado in chamadas:
                with self.subTest(chave=chave, chamada=nome):
                    resposta = chamar()
                    self.assertEqual(resposta.status_code, esperado, getattr(resposta, 'data', None))

    def test_admin_usa_as_rotas_com_tudo_fechado_no_plano_dele(self):
        # PERM-09
        for chave in RECURSOS:
            fechar(chave)
        admin = criar_admin()
        self.client.force_authenticate(user=admin)
        self.assertEqual(self.client.get('/api/goals/').status_code, 200)
        self.assertEqual(self.client.get('/api/export/transactions/pdf/').status_code, 200)

    def test_trava_fechada_em_outro_plano_nao_afeta_o_comum(self):
        fechar('metas', 'PREMIUM')
        self.assertEqual(self.client.get('/api/goals/').status_code, 200)


class RecursoParcialTests(TravasTestCase):
    """O que continua liberado com uma trava fechada (PERM-15, PERM-21)."""

    def test_compras_parceladas_fechada_recusa_so_acima_de_1x(self):
        fechar('compras_parceladas')
        resposta = self.client.post(
            '/api/transactions/credit-card-expense/', self.corpo_compra(installments=1), format='json',
        )
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)
        antes = Transaction.objects.filter(type='CREDIT_CARD').count()
        resposta = self.client.post(
            '/api/transactions/credit-card-expense/', self.corpo_compra(installments=2), format='json',
        )
        self.assert_travada(resposta, 'compras_parceladas')
        self.assertEqual(Transaction.objects.filter(type='CREDIT_CARD').count(), antes)

    def test_recorrentes_fechada_libera_o_lancamento_avulso_e_a_exclusao_por_transferencia(self):
        fechar('transacoes_recorrentes')
        resposta = self.client.post('/api/transactions/', self.corpo_transacao(), format='json')
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)
        resposta = self.client.post('/api/transactions/transfer/', {
            'account_from': str(self.d.conta.pk), 'account_to': str(self.d.cofrinho.pk),
            'amount': '10.00', 'date': '2026-09-10',
        }, format='json')
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)
        transferencia = Transaction.objects.filter(transfer_id__isnull=False).first().transfer_id

        resposta = self.client.delete(f'/api/transactions/bulk-delete/?transfer_id={transferencia}')

        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)
        self.assertFalse(Transaction.objects.filter(transfer_id=transferencia).exists())
        # As ocorrências já criadas da série seguem como transações comuns
        ocorrencia = Transaction.objects.filter(recurring_source=self.serie, status='PENDING').first()
        resposta = self.client.patch(f'/api/transactions/{ocorrencia.pk}/', {'status': 'COMPLETED'}, format='json')
        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)

    def test_recorrentes_fechada_nao_cria_nem_altera_a_serie(self):
        fechar('transacoes_recorrentes')
        series = RecurringTransaction.objects.count()
        transacoes = Transaction.objects.count()
        self.client.post('/api/transactions/', self.corpo_transacao(is_recurring=True, frequency='MONTHLY'), format='json')
        self.client.patch('/api/transactions/bulk-update/', {
            'recurring_source': str(self.serie.pk), 'description': 'Outra',
        }, format='json')
        self.client.delete(f'/api/transactions/bulk-delete/?recurring_source={self.serie.pk}')
        self.assertEqual(RecurringTransaction.objects.count(), series)
        self.assertEqual(Transaction.objects.count(), transacoes)
        self.serie.refresh_from_db()
        self.assertEqual((self.serie.description, self.serie.is_active), ('Mercado', True))

    def test_tags_fechada_recusa_editar_com_tags_e_aceita_sem_tags(self):
        fechar('tags')
        transacao = Transaction.objects.filter(user=self.d.usuario).first()
        rota = f'/api/transactions/{transacao.pk}/'
        self.assert_travada(self.client.patch(rota, {'tags': [str(self.d.tag.pk)]}, format='json'), 'tags')
        self.assertFalse(Transaction.objects.get(pk=transacao.pk).tags.exists())
        resposta = self.client.patch(rota, {'description': 'Sem tags'}, format='json')
        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)
        resposta = self.client.post('/api/transactions/', self.corpo_transacao(tags=[]), format='json')
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)

    def test_planilha_com_tags_fechada_ignora_as_tags_e_grava_a_linha(self):
        fechar('tags')
        tags_antes = Tag.objects.filter(user=self.d.usuario).count()
        resposta = self.client.post('/api/import/spreadsheet/', {
            'file': arquivo_csv([['Data', 'Descrição', 'Valor', 'Tags'], ['10/09/2026', 'Padaria', '-12,34', 'viagem, nova']]),
            'mapping': json.dumps({**MAPEAMENTO, 'tags_column': 'Tags'}), 'import_type': 'INCOME_EXPENSE',
            'account_id': str(self.d.conta.pk),
        }, format='multipart')
        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)
        gravada = Transaction.objects.get(user=self.d.usuario, description='Padaria')
        self.assertEqual(gravada.amount, Decimal('12.34'))
        self.assertFalse(gravada.tags.exists())
        self.assertEqual(Tag.objects.filter(user=self.d.usuario).count(), tags_antes)


class DinheiroJaLancadoTests(TravasTestCase):
    """Cofrinho e faturas existentes com as travas fechadas (PERM-22)."""

    def test_com_metas_fechada_o_cofrinho_recebe_transferencia_e_ajuste_de_saldo(self):
        fechar('metas')
        cofrinho = self.d.cofrinho
        resposta = self.client.post('/api/transactions/transfer/', {
            'account_from': str(self.d.conta.pk), 'account_to': str(cofrinho.pk),
            'amount': '100.00', 'date': '2026-09-10',
        }, format='json')
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)
        resposta = self.client.post('/api/transactions/transfer/', {
            'account_from': str(cofrinho.pk), 'account_to': str(self.d.conta.pk),
            'amount': '30.00', 'date': '2026-09-11',
        }, format='json')
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)
        resposta = self.client.post(f'/api/accounts/{cofrinho.pk}/adjust-balance/', {'new_balance': '50.00'}, format='json')
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)
        self.assertEqual(Account.objects.get(pk=cofrinho.pk).balance, Decimal('50.00'))
        self.assert_travada(self.client.get('/api/goals/'), 'metas')

    def test_com_cartoes_fechada_ler_pagar_e_estornar_faturas_seguem_liberados(self):
        compra = Transaction.objects.create(
            user=self.d.usuario, type='CREDIT_CARD', status='PENDING', account=self.d.conta,
            credit_card=self.d.cartao, invoice=self.d.fatura, description='Compra antiga',
            amount=Decimal('80.00'), date=self.d.fatura.due_date,
        )
        fechar('cartoes')
        cartao, fatura = self.d.cartao, self.d.fatura
        leituras = [
            f'/api/credit-cards/', f'/api/credit-cards/{cartao.pk}/', f'/api/credit-cards/{cartao.pk}/invoices/',
            f'/api/invoices/{fatura.pk}/', f'/api/invoices/{fatura.pk}/transactions/',
        ]
        for rota in leituras:
            with self.subTest(rota=rota):
                self.assertEqual(self.client.get(rota).status_code, status.HTTP_200_OK)

        resposta = self.client.post(f'/api/invoices/{fatura.pk}/pay/', {
            'amount': '80.00', 'account_id': str(self.d.conta.pk), 'date': '2026-09-20',
        }, format='json')
        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)
        self.assertEqual(Transaction.objects.get(pk=compra.pk).status, 'COMPLETED')

        resposta = self.client.post(f'/api/invoices/{fatura.pk}/unpay/')
        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)
        self.assertEqual(Transaction.objects.get(pk=compra.pk).status, 'PENDING')

    def test_com_cartoes_fechada_criar_editar_e_excluir_cartao_e_comprar_recebem_403(self):
        fechar('cartoes')
        cartao = self.d.cartao
        self.assert_travada(self.client.post('/api/credit-cards/', {
            'name': 'Novo', 'limit': '500.00', 'closing_day': 1, 'due_day': 10,
        }, format='json'), 'cartoes')
        self.assert_travada(self.client.patch(f'/api/credit-cards/{cartao.pk}/', {'name': 'X'}, format='json'), 'cartoes')
        self.assert_travada(self.client.delete(f'/api/credit-cards/{cartao.pk}/'), 'cartoes')
        self.assert_travada(self.client.get('/api/invoices/'), 'cartoes')
        self.assert_travada(self.client.post(
            '/api/transactions/credit-card-expense/', self.corpo_compra(), format='json',
        ), 'cartoes')
        cartao.refresh_from_db()
        self.assertEqual((cartao.name, cartao.is_active), ('Cartão A', True))
        self.assertFalse(Transaction.objects.filter(type='CREDIT_CARD').exists())

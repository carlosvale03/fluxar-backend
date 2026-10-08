"""
Registro das correções de categoria e filtros do atalho das sugeridas
(IMPORT-42, IMPORT-45, IMPORT-46, IMPORT-48, IMPORT-49).

Definir ou trocar a categoria de uma transação importada grava uma
correção do próprio usuário e desliga a marca de sugerida.
"""
import uuid
from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from api.models import User
from data_exchange.importacao.texto import normalizar_descricao
from transactions.models import Category, CorrecaoDeCategoria, Transaction

from .base import ImportacaoTestCase

URL_TRANSACOES = '/api/transactions/'
SENHA_DO_ADMIN = 'Cofre-Azul-2026'


class NormalizarDescricaoTests(SimpleTestCase):

    def test_sem_maiusculas_acentos_digitos_e_espacos_extras(self):
        """IMPORT-43: "UBER *TRIP 1234" e "UBER *TRIP 5678" são a mesma descrição."""
        self.assertEqual(normalizar_descricao('UBER *TRIP 1234'), 'uber *trip')
        self.assertEqual(normalizar_descricao('  Úber   *TRIP 5678 '), 'uber *trip')
        self.assertEqual(normalizar_descricao('Padaria São João 12 3'), 'padaria sao joao')


class CorrecoesTestCase(ImportacaoTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.transporte = Category.objects.create(user=cls.a.usuario, name='Transporte', type='EXPENSE')

    def importada(self, dono=None, lote=None, categoria=None, sugerida=False, descricao='UBER *TRIP 1234'):
        dono = dono or self.a
        return Transaction.objects.create(
            user=dono.usuario, account=dono.conta, type='EXPENSE', description=descricao,
            amount=Decimal('23.90'), date=date(2026, 9, 10), category=categoria,
            import_batch=lote or uuid.uuid4(), categoria_sugerida=sugerida,
        )

    def trocar_categoria(self, transacao, categoria):
        resp = self.client.patch(
            f'{URL_TRANSACOES}{transacao.pk}/', {'category': str(categoria.pk)}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp


class RegistroDasCorrecoesTests(CorrecoesTestCase):

    def test_trocar_a_categoria_de_uma_importada_grava_a_correcao(self):
        """IMPORT-42: descrição, conta, categoria de antes, de depois e data."""
        transacao = self.importada(categoria=self.a.despesa)

        self.trocar_categoria(transacao, self.transporte)

        correcao = CorrecaoDeCategoria.objects.get()
        self.assertEqual(
            (correcao.user, correcao.transacao, correcao.descricao, correcao.descricao_normalizada,
             correcao.conta, correcao.categoria_antes, correcao.categoria_depois),
            (self.a.usuario, transacao, 'UBER *TRIP 1234', 'uber *trip',
             self.a.conta, self.a.despesa, self.transporte),
        )
        self.assertIsNotNone(correcao.criada_em)

    def test_definir_a_categoria_de_uma_importada_sem_categoria_grava_a_correcao(self):
        """IMPORT-42: definir também conta, com a categoria de antes vazia."""
        transacao = self.importada()

        self.trocar_categoria(transacao, self.transporte)

        correcao = CorrecaoDeCategoria.objects.get()
        self.assertEqual(
            (correcao.transacao, correcao.categoria_antes, correcao.categoria_depois),
            (transacao, None, self.transporte),
        )

    def test_transacao_nao_importada_ou_categoria_igual_nao_grava(self):
        """IMPORT-42: só a mudança de categoria de uma transação importada vira correção."""
        manual = Transaction.objects.create(
            user=self.a.usuario, account=self.a.conta, type='EXPENSE', description='UBER *TRIP 1',
            amount=Decimal('10.00'), date=date(2026, 9, 10), category=self.a.despesa,
        )
        self.trocar_categoria(manual, self.transporte)

        importada = self.importada(categoria=self.transporte)
        self.trocar_categoria(importada, self.transporte)
        resp = self.client.patch(
            f'{URL_TRANSACOES}{importada.pk}/', {'description': 'Uber'}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)

        self.assertFalse(CorrecaoDeCategoria.objects.exists())
        manual.refresh_from_db()
        self.assertEqual(manual.category, self.transporte)

    def test_trocar_uma_sugerida_grava_a_correcao_e_desliga_a_marca(self):
        """IMPORT-42, IMPORT-46 e edge case: a troca de uma sugerida vira correção nova."""
        lote = uuid.uuid4()
        transacao = self.importada(lote=lote, categoria=self.a.despesa, sugerida=True)

        antes = self.client.get(f'{URL_TRANSACOES}{transacao.pk}/')
        self.assertEqual(antes.status_code, 200)
        self.assertEqual((antes.data['category_suggested'], antes.data['import_batch']), (True, str(lote)))

        resp = self.trocar_categoria(transacao, self.transporte)

        self.assertIs(resp.data['category_suggested'], False)
        transacao.refresh_from_db()
        self.assertIs(transacao.categoria_sugerida, False)
        self.assertEqual(CorrecaoDeCategoria.objects.get().categoria_antes, self.a.despesa)

    def test_lote_e_marca_de_sugerida_sao_somente_leitura(self):
        """IMPORT-46: o corpo não muda o lote nem a marca de sugerida."""
        lote = uuid.uuid4()
        transacao = self.importada(lote=lote)

        resp = self.client.patch(
            f'{URL_TRANSACOES}{transacao.pk}/',
            {'import_batch': str(uuid.uuid4()), 'category_suggested': True}, format='json',
        )

        self.assertEqual(resp.status_code, 200, resp.data)
        transacao.refresh_from_db()
        self.assertEqual((transacao.import_batch, transacao.categoria_sugerida), (lote, False))


class FiltrosDoLoteTests(CorrecoesTestCase):

    def ids(self, resp):
        self.assertEqual(resp.status_code, 200, resp.data)
        return {item['id'] for item in resp.data['results']}

    def test_lista_so_as_sugeridas_do_lote(self):
        """IMPORT-45: `?import_batch=<id>&suggested_category=true` traz só as sugeridas do lote."""
        lote, outro = uuid.uuid4(), uuid.uuid4()
        sugerida = self.importada(lote=lote, categoria=self.transporte, sugerida=True)
        sem_sugestao = self.importada(lote=lote)
        self.importada(lote=outro, categoria=self.transporte, sugerida=True)

        so_sugeridas = self.client.get(URL_TRANSACOES, {'import_batch': str(lote), 'suggested_category': 'true'})
        do_lote = self.client.get(URL_TRANSACOES, {'import_batch': str(lote)})

        self.assertEqual(self.ids(so_sugeridas), {str(sugerida.pk)})
        self.assertEqual(self.ids(do_lote), {str(sugerida.pk), str(sem_sugestao.pk)})

    def test_lote_invalido_recebe_400_no_campo(self):
        """IMPORT-45: `import_batch` que não é UUID recebe 400 no campo."""
        resp = self.client.get(URL_TRANSACOES, {'import_batch': 'abc'})

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {'import_batch': ['Lote de importação inválido.']})


class CorrecoesPorUsuarioTests(CorrecoesTestCase):

    def test_correcao_fica_com_o_dono_da_transacao(self):
        """IMPORT-49: a correção de B é de B e não entra nas de A."""
        categoria_de_b = Category.objects.create(user=self.b.usuario, name='Transporte B', type='EXPENSE')
        transacao = self.importada(dono=self.b)
        self.client.force_authenticate(user=self.b.usuario)

        self.trocar_categoria(transacao, categoria_de_b)

        self.assertEqual(CorrecaoDeCategoria.objects.get().user, self.b.usuario)
        self.assertFalse(CorrecaoDeCategoria.objects.filter(user=self.a.usuario).exists())

    def test_exclusao_definitiva_pelo_painel_apaga_as_correcoes(self):
        """IMPORT-48: as duas rotas de exclusão definitiva apagam as correções do usuário."""
        admin = User.objects.create_user(
            email='admin.importacao@teste.fluxar', password=SENHA_DO_ADMIN, name='Admin',
            is_staff=True, role='ADMIN',
        )
        mantida = CorrecaoDeCategoria.objects.create(
            user=self.a.usuario, descricao='Padaria', descricao_normalizada='padaria',
        )
        for metodo, url, dados in (
            ('delete', '/api/admin/users/{pk}/', {'admin_password': SENHA_DO_ADMIN, 'permanent': True}),
            ('delete', '/api/admin/users/{pk}/hard-delete/', {'admin_password': SENHA_DO_ADMIN}),
        ):
            with self.subTest(url=url):
                usuario = User.objects.create_user(
                    email='excluido@teste.fluxar', password='senha-de-teste-123', name='Excluído',
                )
                correcao = CorrecaoDeCategoria.objects.create(
                    user=usuario, descricao='UBER *TRIP 1234', descricao_normalizada='uber *trip',
                )
                self.client.force_authenticate(user=admin)

                resp = getattr(self.client, metodo)(url.format(pk=usuario.pk), dados, format='json')

                self.assertEqual(resp.status_code, 200, resp.data)
                self.assertFalse(CorrecaoDeCategoria.objects.filter(pk=correcao.pk).exists())
                self.assertTrue(CorrecaoDeCategoria.objects.filter(pk=mantida.pk).exists())

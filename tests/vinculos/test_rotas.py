"""
Rotas de vincular e desfazer: `POST` e `DELETE /api/transactions/{id}/link/`
(VINCULO-02, VINCULO-04, VINCULO-09 a VINCULO-12, VINCULO-20 e VINCULO-21).
"""
from django.core.cache import cache

from core import travas
from tests.permissoes.base import fechar, liberacao_de_testes
from transactions.models import Transaction

from .base import VinculosTestCase, compra, despesa, fotografia, url_do_vinculo

NAO_ENCONTRADA = 'Transação não encontrada.'
BLOQUEADO = {
    'detail': 'Este recurso não está disponível no seu plano.', 'code': 'plan_locked', 'feature': 'vinculos',
}
ID_INEXISTENTE = '00000000-0000-4000-8000-000000000000'


class RotasTestCase(VinculosTestCase):

    def setUp(self):
        super().setUp()
        cache.clear()
        travas.invalidar()
        self.addCleanup(travas.invalidar)
        self.cinema = despesa(self.a, 'Cinema', '50.00', categoria=self.a.cinema)
        self.transporte = despesa(self.a, 'Transporte', '45.00', categoria=self.a.transporte)
        self.pipoca = despesa(self.a, 'Pipoca', '20.00', categoria=self.a.alimentacao)

    def ligar(self, dependente, principal):
        return self.client.post(url_do_vinculo(dependente), {'principal': str(principal)}, format='json')

    def principal_de(self, transacao):
        return self.recarregar(transacao).principal_id


class VincularTests(RotasTestCase):

    def test_ligar_uma_transacao_existente_devolve_200_com_a_principal(self):
        resposta = self.ligar(self.pipoca, self.cinema.pk)

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(resposta.data['id'], str(self.pipoca.pk))
        self.assertEqual(str(resposta.data['principal']), str(self.cinema.pk))
        self.assertEqual(self.principal_de(self.pipoca), self.cinema.pk)

    def test_trocar_e_repetir_pela_rota(self):
        self.assertEqual(self.ligar(self.transporte, self.cinema.pk).status_code, 200)
        repetida = self.ligar(self.transporte, self.cinema.pk)
        self.assertEqual(repetida.status_code, 200, repetida.data)
        self.assertEqual(self.principal_de(self.transporte), self.cinema.pk)

        trocada = self.ligar(self.transporte, self.pipoca.pk)
        self.assertEqual(trocada.status_code, 200, trocada.data)
        self.assertEqual(str(trocada.data['principal']), str(self.pipoca.pk))
        self.assertEqual(Transaction.objects.filter(principal__isnull=False).count(), 1)

    def test_dependente_como_principal_recebe_400(self):
        self.ligar(self.transporte, self.cinema.pk)
        resposta = self.ligar(self.pipoca, self.transporte.pk)
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.data['detail'], 'Uma transação dependente não pode ser principal.')
        self.assertIsNone(self.principal_de(self.pipoca))

    def test_parcela_pela_rota_liga_a_compra_e_devolve_a_principal_da_compra(self):
        parcelas = compra(self.a, 'Jantar', '120.00', parcelas=3, categoria=self.a.alimentacao)
        resposta = self.ligar(parcelas[2], self.cinema.pk)
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(resposta.data['id'], str(parcelas[2].pk))
        self.assertEqual(str(resposta.data['principal']), str(self.cinema.pk))
        self.assertEqual(self.principal_de(parcelas[0]), self.cinema.pk)
        self.assertIsNone(self.principal_de(parcelas[2]))


class IsolamentoTests(RotasTestCase):
    """VINCULO-11 e AD-010."""

    def test_principal_de_outro_usuario_recebe_a_mesma_recusa_de_um_id_inexistente(self):
        alheia = despesa(self.b, 'Cinema B', '50.00')
        resposta_alheia = self.ligar(self.transporte, alheia.pk)
        resposta_inexistente = self.ligar(self.transporte, ID_INEXISTENTE)

        self.assertEqual(resposta_alheia.status_code, 400)
        self.assertEqual(resposta_alheia.data, {'principal': [NAO_ENCONTRADA]})
        self.assertEqual(resposta_inexistente.status_code, 400)
        self.assertEqual(resposta_inexistente.data, resposta_alheia.data)
        self.assertIsNone(self.principal_de(self.transporte))

    def test_dependente_de_outro_usuario_recebe_404(self):
        alheia = despesa(self.b, 'Transporte B', '45.00')
        resposta = self.client.post(url_do_vinculo(alheia), {'principal': str(self.cinema.pk)}, format='json')
        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(
            self.client.post(
                f'/api/transactions/{ID_INEXISTENTE}/link/', {'principal': str(self.cinema.pk)}, format='json',
            ).status_code,
            404,
        )
        self.assertEqual(self.client.delete(url_do_vinculo(alheia)).status_code, 404)
        self.assertIsNone(self.principal_de(alheia))


class DesfazerTests(RotasTestCase):
    """VINCULO-04 e VINCULO-17."""

    def test_desfazer_devolve_200_e_mantem_as_transacoes(self):
        self.ligar(self.transporte, self.cinema.pk)
        antes = fotografia(self.a)
        valores = list(Transaction.objects.filter(user=self.a.usuario).order_by('pk').values(
            'pk', 'description', 'amount', 'date', 'category_id', 'account_id',
        ))

        resposta = self.client.delete(url_do_vinculo(self.transporte))

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertIsNone(resposta.data['principal'])
        self.assertIsNone(self.principal_de(self.transporte))
        self.assertEqual(fotografia(self.a), antes)
        self.assertEqual(list(Transaction.objects.filter(user=self.a.usuario).order_by('pk').values(
            'pk', 'description', 'amount', 'date', 'category_id', 'account_id',
        )), valores)


class TravaTests(RotasTestCase):
    """VINCULO-20 e VINCULO-21."""

    def test_com_o_recurso_travado_ligar_recebe_403_e_desfazer_funciona(self):
        self.ligar(self.transporte, self.cinema.pk)
        liberacao_de_testes(False)
        fechar('vinculos')

        resposta = self.ligar(self.pipoca, self.cinema.pk)
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(resposta.data, BLOQUEADO)
        self.assertIsNone(self.principal_de(self.pipoca))
        # Trocar a principal também é travado
        resposta = self.ligar(self.transporte, self.pipoca.pk)
        self.assertEqual(resposta.data, BLOQUEADO)
        # O vínculo existente continua e pode ser desfeito
        self.assertEqual(self.principal_de(self.transporte), self.cinema.pk)
        resposta = self.client.delete(url_do_vinculo(self.transporte))
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertIsNone(self.principal_de(self.transporte))

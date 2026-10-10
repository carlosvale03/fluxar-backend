"""
Consentimento de melhoria do produto nas configurações (LGPD-34, LGPD-35).
"""
from unittest import mock

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.test import APITestCase

from api.models import DecisaoDeConsentimento, User
from api.sessoes import criar_sessao
from core import termos

ROTA = '/api/users/me/consent/'


class ConsentimentoTests(APITestCase):

    def setUp(self):
        self.ana = User.objects.create_user(email='ana@teste.fluxar', password='senha-de-teste-123', name='Ana')
        acesso, _ = criar_sessao(self.ana)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {acesso}')

    def decidir(self, consent):
        return self.client.put(ROTA, {'consent': consent}, format='json')

    # LGPD-35 ---------------------------------------------------------------

    def test_dar_e_retirar_grava_duas_decisoes_com_data_e_versao_sem_apagar_a_anterior(self):
        antes = timezone.now()

        dar = self.decidir(True)
        retirar = self.decidir(False)

        self.assertEqual(dar.status_code, 200, dar.content)
        self.assertIs(dar.data['consent'], True)
        self.assertEqual(retirar.status_code, 200, retirar.content)
        self.assertIs(retirar.data['consent'], False)
        decisoes = list(DecisaoDeConsentimento.objects.filter(user=self.ana).order_by('decidido_em'))
        self.assertEqual([d.consentiu for d in decisoes], [True, False])
        for decisao in decisoes:
            self.assertEqual(decisao.versao_da_politica, termos.VERSAO_VIGENTE)
            self.assertGreaterEqual(decisao.decidido_em, antes)
        self.ana.refresh_from_db()
        self.assertFalse(self.ana.consentimento_melhoria)

    def test_a_decisao_guarda_a_versao_vigente_no_momento(self):
        with mock.patch.object(termos, 'VERSAO_VIGENTE', '2.0'):
            self.decidir(True)
        with mock.patch.object(termos, 'VERSAO_VIGENTE', '3.0'):
            # Quem já aceitou a versão nova, para não cair no bloqueio dos termos
            User.objects.filter(pk=self.ana.pk).update(versao_dos_termos_aceita='3.0')
            self.decidir(False)

        versoes = list(
            DecisaoDeConsentimento.objects.filter(user=self.ana).order_by('decidido_em')
            .values_list('versao_da_politica', flat=True)
        )
        self.assertEqual(versoes, ['2.0', '3.0'])

    # LGPD-34 ---------------------------------------------------------------

    def test_get_devolve_o_estado_atual_e_a_data_da_ultima_decisao(self):
        inicial = self.client.get(ROTA)
        self.assertEqual(inicial.status_code, 200)
        self.assertEqual(inicial.data, {'consent': False, 'decided_at': None, 'policy_version': None})

        self.decidir(True)
        resposta = self.client.get(ROTA)

        ultima = DecisaoDeConsentimento.objects.get(user=self.ana)
        self.assertIs(resposta.data['consent'], True)
        self.assertEqual(parse_datetime(resposta.data['decided_at']), ultima.decidido_em)
        self.assertEqual(resposta.data['policy_version'], termos.VERSAO_VIGENTE)
        self.assertIs(self.client.get('/api/auth/me/').data['product_improvement_consent'], True)

    def test_valor_que_nao_e_booleano_recebe_400_no_campo(self):
        for valor in (None, 'sim', 1):
            with self.subTest(valor=valor):
                resposta = self.decidir(valor)

                self.assertEqual(resposta.status_code, 400)
                self.assertIn('consent', resposta.data)
        self.assertFalse(DecisaoDeConsentimento.objects.exists())

    def test_sem_login_recebe_401(self):
        self.client.credentials()

        self.assertEqual(self.client.get(ROTA).status_code, 401)
        self.assertEqual(self.client.put(ROTA, {'consent': True}, format='json').status_code, 401)

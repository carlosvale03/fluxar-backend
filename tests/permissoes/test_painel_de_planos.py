"""
Configuração das travas no painel (PERM-10 a PERM-13 e PERM-24).

`GET /api/admin/plans/` mostra cada trava com o valor dos três planos e a
liberação para testes. `PATCH` aceita `{testing_unlock}`, `{key, plan,
enabled}` ou `{key, plan, limit}`, grava, registra no log só quando o valor
muda e faz a mudança valer na requisição seguinte.
"""
from rest_framework import status

from api.models import GlobalSetting, SystemLog, TravaDePlano
from api.utils.email_service import _mask_email
from core import travas

from .base import (
    LIMITES, RECURSOS, PermissoesTestCase, criar_admin, criar_usuario, fechar, liberacao_de_testes,
)

ROTA = '/api/admin/plans/'
PLANOS = ['COMMON', 'PREMIUM', 'PREMIUM_PLUS']


class PainelDePlanosTestCase(PermissoesTestCase):

    def setUp(self):
        super().setUp()
        self.admin = criar_admin()
        self.client.force_authenticate(user=self.admin)

    def patch(self, corpo):
        return self.client.patch(ROTA, corpo, format='json')


class LeituraTests(PainelDePlanosTestCase):

    def test_get_mostra_as_24_travas_com_os_valores_dos_tres_planos(self):
        resposta = self.client.get(ROTA)
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertIs(resposta.data['testing_unlock'], True)
        catalogo = resposta.data['catalog']
        self.assertEqual([t['key'] for t in catalogo], RECURSOS + LIMITES)
        for item in catalogo:
            trava = travas.CATALOGO[item['key']]
            with self.subTest(chave=item['key']):
                self.assertEqual(item['name'], trava.nome)
                self.assertEqual(item['description'], trava.descricao)
                if item['key'] in LIMITES:
                    self.assertEqual(item['type'], 'limit')
                    self.assertEqual(item['values'], {p: {'limit': None} for p in PLANOS})
                else:
                    self.assertEqual(item['type'], 'feature')
                    self.assertEqual(item['values'], {p: True for p in PLANOS})

    def test_get_mostra_o_valor_configurado_de_cada_plano(self):
        fechar('metas', 'COMMON')
        fechar('limite_contas', 'PREMIUM', limite=5)
        catalogo = {t['key']: t for t in self.client.get(ROTA).data['catalog']}
        self.assertEqual(catalogo['metas']['values'], {'COMMON': False, 'PREMIUM': True, 'PREMIUM_PLUS': True})
        self.assertEqual(
            catalogo['limite_contas']['values'],
            {'COMMON': {'limit': None}, 'PREMIUM': {'limit': 5}, 'PREMIUM_PLUS': {'limit': None}},
        )

    def test_get_recusa_parametro_desconhecido(self):
        self.assertEqual(self.client.get(ROTA, {'plano': 'COMMON'}).status_code, status.HTTP_400_BAD_REQUEST)


class GravacaoTests(PainelDePlanosTestCase):

    def test_desligar_um_recurso_e_definir_um_limite_valem_na_requisicao_seguinte(self):
        liberacao_de_testes(False)
        comum = criar_usuario('comum')
        premium = criar_usuario('premium', plan='PREMIUM')
        self.assertIs(travas.acesso(comum).recurso_liberado('exportacao_pdf'), True)

        resposta = self.patch({'key': 'exportacao_pdf', 'plan': 'COMMON', 'enabled': False})
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        resposta = self.patch({'key': 'limite_contas', 'plan': 'COMMON', 'limit': 2})
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)

        catalogo = {t['key']: t for t in resposta.data['catalog']}
        self.assertIs(catalogo['exportacao_pdf']['values']['COMMON'], False)
        self.assertEqual(catalogo['limite_contas']['values']['COMMON'], {'limit': 2})
        self.assertIs(travas.acesso(comum).recurso_liberado('exportacao_pdf'), False)
        self.assertEqual(travas.acesso(comum).limite('limite_contas'), 2)
        self.assertIs(travas.acesso(premium).recurso_liberado('exportacao_pdf'), True)
        self.assertIsNone(travas.acesso(premium).limite('limite_contas'))
        linha = TravaDePlano.objects.get(chave='limite_contas', plano='COMMON')
        self.assertEqual((linha.limite, linha.atualizada_por_id), (2, self.admin.pk))

    def test_limite_nulo_volta_a_ser_sem_limite_e_zero_e_aceito(self):
        liberacao_de_testes(False)
        comum = criar_usuario('comum')
        self.assertEqual(self.patch({'key': 'limite_tags', 'plan': 'COMMON', 'limit': 0}).status_code, 200)
        self.assertEqual(travas.acesso(comum).limite('limite_tags'), 0)
        self.assertEqual(self.patch({'key': 'limite_tags', 'plan': 'COMMON', 'limit': None}).status_code, 200)
        self.assertIsNone(travas.acesso(comum).limite('limite_tags'))

    def test_limite_invalido_recebe_400_no_campo_limit(self):
        for valor in (-1, 2.5, 'abc', True, '', [2]):
            with self.subTest(limite=valor):
                resposta = self.patch({'key': 'limite_contas', 'plan': 'COMMON', 'limit': valor})
                self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn('limit', resposta.data)
        self.assertFalse(TravaDePlano.objects.exists())
        self.assertFalse(SystemLog.objects.filter(action='UPDATE_PLAN_LOCK').exists())

    def test_chave_plano_ou_campo_errado_recebem_400_no_campo(self):
        casos = [
            ({'key': 'contas', 'plan': 'COMMON', 'enabled': False}, 'key'),
            ({'plan': 'COMMON', 'enabled': False}, 'key'),
            ({'key': 'metas', 'plan': 'GOLD', 'enabled': False}, 'plan'),
            ({'key': 'metas', 'enabled': False}, 'plan'),
            ({'key': 'metas', 'plan': 'COMMON'}, 'enabled'),
            ({'key': 'metas', 'plan': 'COMMON', 'enabled': 'talvez'}, 'enabled'),
            ({'key': 'metas', 'plan': 'COMMON', 'limit': 2}, 'limit'),
            ({'key': 'limite_metas', 'plan': 'COMMON', 'enabled': False}, 'enabled'),
            ({'key': 'limite_metas', 'plan': 'COMMON'}, 'limit'),
            ({'testing_unlock': 'talvez'}, 'testing_unlock'),
            ({'testing_unlock': False, 'key': 'metas', 'plan': 'COMMON', 'enabled': False}, 'testing_unlock'),
        ]
        for corpo, campo in casos:
            with self.subTest(corpo=corpo):
                resposta = self.patch(corpo)
                self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(campo, resposta.data)
        self.assertFalse(TravaDePlano.objects.exists())
        self.assertEqual(GlobalSetting.objects.get(key='testing_unlock').value, 'true')


class LogTests(PainelDePlanosTestCase):

    def logs(self, acao):
        return list(SystemLog.objects.filter(action=acao).order_by('timestamp'))

    def test_cada_mudanca_grava_quem_quando_a_trava_o_plano_e_os_valores(self):
        self.patch({'key': 'exportacao_pdf', 'plan': 'COMMON', 'enabled': False})
        self.patch({'key': 'limite_contas', 'plan': 'PREMIUM', 'limit': 2})
        self.patch({'key': 'limite_contas', 'plan': 'PREMIUM', 'limit': None})

        logs = self.logs('UPDATE_PLAN_LOCK')
        self.assertEqual(
            [log.description for log in logs],
            [
                "Trava 'exportacao_pdf' no plano COMMON: liberado -> bloqueado.",
                "Trava 'limite_contas' no plano PREMIUM: sem limite -> 2.",
                "Trava 'limite_contas' no plano PREMIUM: 2 -> sem limite.",
            ],
        )
        for log in logs:
            # O administrador aparece pelo e-mail mascarado, sem o nome (LGPD-22)
            self.assertEqual(log.admin_name, _mask_email(self.admin.email))
            self.assertIsNotNone(log.timestamp)

    def test_gravar_o_mesmo_valor_nao_gera_log(self):
        self.assertEqual(self.patch({'key': 'metas', 'plan': 'COMMON', 'enabled': True}).status_code, 200)
        self.assertEqual(self.patch({'key': 'limite_metas', 'plan': 'COMMON', 'limit': None}).status_code, 200)
        self.assertEqual(self.patch({'testing_unlock': True}).status_code, 200)
        self.patch({'key': 'limite_metas', 'plan': 'COMMON', 'limit': 3})
        self.patch({'key': 'limite_metas', 'plan': 'COMMON', 'limit': 3})

        self.assertEqual(len(self.logs('UPDATE_PLAN_LOCK')), 1)
        self.assertEqual(self.logs('UPDATE_TESTING_UNLOCK'), [])

    def test_ligar_e_desligar_a_liberacao_grava_no_log_e_vale_na_requisicao_seguinte(self):
        comum = criar_usuario('comum')
        fechar('metas', 'COMMON')
        self.assertIs(travas.acesso(comum).recurso_liberado('metas'), True)

        resposta = self.patch({'testing_unlock': False})
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertIs(resposta.data['testing_unlock'], False)
        self.assertIs(travas.acesso(comum).recurso_liberado('metas'), False)

        self.patch({'testing_unlock': True})
        self.assertIs(travas.acesso(comum).recurso_liberado('metas'), True)

        self.assertEqual(
            [log.description for log in self.logs('UPDATE_TESTING_UNLOCK')],
            ['Liberação para testes: ligada -> desligada.', 'Liberação para testes: desligada -> ligada.'],
        )
        self.assertEqual(GlobalSetting.objects.get(key='testing_unlock').value, 'true')


class AcessoAoPainelTests(PermissoesTestCase):

    def test_quem_nao_e_admin_recebe_403_mesmo_com_is_staff(self):
        for usuario in (criar_usuario('comum'), criar_usuario('staff', is_staff=True, is_superuser=True)):
            self.client.force_authenticate(user=usuario)
            with self.subTest(usuario=usuario.email):
                self.assertEqual(self.client.get(ROTA).status_code, status.HTTP_403_FORBIDDEN)
                resposta = self.client.patch(ROTA, {'testing_unlock': False}, format='json')
                self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)
                resposta = self.client.patch(
                    ROTA, {'key': 'metas', 'plan': 'COMMON', 'enabled': False}, format='json',
                )
                self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(GlobalSetting.objects.get(key='testing_unlock').value, 'true')
        self.assertFalse(TravaDePlano.objects.exists())

    def test_rota_de_configuracoes_recusa_a_liberacao_para_testes(self):
        self.client.force_authenticate(user=criar_admin())
        for corpo in ({'testing_unlock': False}, {'key': 'testing_unlock', 'value': 'false'},
                      {'maintenance_mode': False, 'testing_unlock': False}):
            with self.subTest(corpo=corpo):
                resposta = self.client.post('/api/admin/settings/', corpo, format='json')
                self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn('testing_unlock', resposta.data)
        self.assertEqual(GlobalSetting.objects.get(key='testing_unlock').value, 'true')
        self.assertFalse(GlobalSetting.objects.filter(key='maintenance_mode').exists())

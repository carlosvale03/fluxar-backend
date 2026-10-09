"""
Versão dos termos, aceite no cadastro e consentimento opcional
(LGPD-26, LGPD-27, LGPD-30, LGPD-31, LGPD-33, LGPD-39).

O envio do e-mail de verificação é simulado. A migração de dados é testada
importando o módulo.
"""
import datetime
import importlib
from unittest import mock

import django.apps
from django.utils import timezone
from rest_framework.test import APITestCase

from api.models import AceiteDosTermos, DecisaoDeConsentimento, User
from core import termos

TERMOS = '/api/terms/'
REGISTRO = '/api/auth/register/'
SENHA = 'Cofre-Verde-2026'
TERMOS_OBRIGATORIOS = 'É preciso aceitar os termos de uso.'
AUSENTE = object()


def dados(**campos):
    corpo = {
        'name': 'Ricardo Lima', 'email': 'ricardo@teste.fluxar', 'password': SENHA,
        'password_confirm': SENHA, 'terms_accepted': True,
    }
    corpo.update(campos)
    return {chave: valor for chave, valor in corpo.items() if valor is not AUSENTE}


def rodar_migracao():
    modulo = importlib.import_module('api.migrations.0019_termos_por_versao_e_consentimento')
    modulo.sem_aceite_e_sem_consentimento(django.apps.apps, None)


class TermosVigentesTests(APITestCase):

    def test_devolve_versao_data_mudancas_e_servicos_sem_login(self):
        resposta = self.client.get(TERMOS, HTTP_AUTHORIZATION='Bearer token-vencido')

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data['version'], termos.VERSAO_VIGENTE)
        datetime.date.fromisoformat(resposta.data['effective_date'])
        self.assertEqual(resposta.data['effective_date'], termos.VIGENTE_DESDE.isoformat())
        self.assertTrue(resposta.data['changes'])
        self.assertTrue(all(isinstance(mudanca, str) and mudanca for mudanca in resposta.data['changes']))
        # Hospedagem da API e do banco, do site, e-mail e imagens (LGPD-31)
        nomes = {servico['name'] for servico in resposta.data['services']}
        self.assertTrue({'Render', 'Vercel', 'Resend', 'Brevo', 'Cloudinary'} <= nomes)
        self.assertTrue(all(servico['purpose'] for servico in resposta.data['services']))


@mock.patch('api.views.send_verification_email', return_value=True)
class AceiteNoCadastroTests(APITestCase):

    def cadastrar(self, **campos):
        return self.client.post(REGISTRO, dados(**campos), format='json')

    # LGPD-27 ---------------------------------------------------------------

    def test_sem_o_aceite_ou_com_false_recebe_400_no_campo(self, envio):
        for valor in (AUSENTE, False):
            with self.subTest(terms_accepted=valor):
                resposta = self.cadastrar(terms_accepted=valor)

                self.assertEqual(resposta.status_code, 400)
                self.assertEqual([str(m) for m in resposta.data['terms_accepted']], [TERMOS_OBRIGATORIOS])
                self.assertFalse(User.objects.filter(email='ricardo@teste.fluxar').exists())
                self.assertFalse(AceiteDosTermos.objects.exists())

    # LGPD-26, LGPD-33 ------------------------------------------------------

    def test_cadastro_aceito_grava_o_aceite_da_versao_vigente_com_data_e_hora(self, envio):
        antes = timezone.now()

        resposta = self.cadastrar()

        self.assertEqual(resposta.status_code, 201, resposta.data)
        usuario = User.objects.get(email='ricardo@teste.fluxar')
        aceite = AceiteDosTermos.objects.get(user=usuario)
        self.assertEqual(aceite.versao, termos.VERSAO_VIGENTE)
        self.assertGreaterEqual(aceite.aceito_em, antes)
        self.assertEqual(usuario.versao_dos_termos_aceita, termos.VERSAO_VIGENTE)

    def test_sem_o_campo_de_consentimento_ele_fica_desligado(self, envio):
        resposta = self.cadastrar()

        self.assertEqual(resposta.status_code, 201, resposta.data)
        usuario = User.objects.get(email='ricardo@teste.fluxar')
        self.assertFalse(usuario.consentimento_melhoria)
        self.assertFalse(DecisaoDeConsentimento.objects.filter(user=usuario, consentiu=True).exists())

    def test_consentimento_false_cadastra_e_fica_desligado(self, envio):
        resposta = self.cadastrar(product_improvement_consent=False)

        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertFalse(User.objects.get(email='ricardo@teste.fluxar').consentimento_melhoria)

    def test_com_consentimento_true_grava_a_decisao_com_a_versao_e_a_data(self, envio):
        antes = timezone.now()

        resposta = self.cadastrar(product_improvement_consent=True)

        self.assertEqual(resposta.status_code, 201, resposta.data)
        usuario = User.objects.get(email='ricardo@teste.fluxar')
        self.assertTrue(usuario.consentimento_melhoria)
        decisao = DecisaoDeConsentimento.objects.get(user=usuario)
        self.assertIs(decisao.consentiu, True)
        self.assertEqual(decisao.versao_da_politica, termos.VERSAO_VIGENTE)
        self.assertGreaterEqual(decisao.decidido_em, antes)


class UsuariosExistentesTests(APITestCase):

    # LGPD-39 ---------------------------------------------------------------

    def test_depois_da_migracao_todo_usuario_existente_fica_sem_aceite_e_sem_consentimento(self):
        antigos = []
        for indice in range(2):
            usuario = User.objects.create_user(
                email=f'antigo{indice}@teste.fluxar', password='senha-de-teste-123', name='Antigo',
                terms_accepted=True, terms_accepted_at=timezone.now(),
            )
            User.objects.filter(pk=usuario.pk).update(
                versao_dos_termos_aceita='1.0', consentimento_melhoria=True,
            )
            antigos.append(usuario)

        rodar_migracao()

        for usuario in antigos:
            usuario.refresh_from_db()
            self.assertIsNone(usuario.versao_dos_termos_aceita)
            self.assertFalse(usuario.consentimento_melhoria)
            # O aceite antigo fica só como histórico
            self.assertTrue(usuario.terms_accepted)

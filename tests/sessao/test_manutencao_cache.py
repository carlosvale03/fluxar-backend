"""
Estado da manutenção em cache (SESSAO-24 e SESSAO-25).

`manutencao_ligada()` lê a `GlobalSetting` `maintenance_mode` no máximo uma vez
a cada 30 segundos por processo. Dentro desse prazo, o valor vem da memória,
sem consulta ao banco. `invalidar()` descarta o valor guardado, e o painel
chama essa função ao salvar, para o próprio processo ver a mudança na hora.
"""
from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from api.models import GlobalSetting, User
from core import manutencao


class EstadoDaManutencaoEmCacheTests(APITestCase):

    def setUp(self):
        manutencao.invalidar()
        self.addCleanup(manutencao.invalidar)
        self.agora = 1000.0
        relogio = patch('core.manutencao.time.monotonic', side_effect=lambda: self.agora)
        relogio.start()
        self.addCleanup(relogio.stop)

    def gravar(self, valor):
        GlobalSetting.objects.update_or_create(key='maintenance_mode', defaults={'value': valor})

    # SESSAO-25 ---------------------------------------------------------

    def test_varias_chamadas_dentro_de_30_segundos_fazem_uma_unica_consulta(self):
        self.gravar('true')

        with self.assertNumQueries(1):
            resultados = [manutencao.manutencao_ligada()]
            for segundos in (1, 10, 29.9):
                self.agora = 1000.0 + segundos
                resultados.append(manutencao.manutencao_ligada())

        self.assertEqual(resultados, [True, True, True, True])

    # SESSAO-24 ---------------------------------------------------------

    def test_depois_de_30_segundos_le_o_banco_de_novo(self):
        self.gravar('true')
        self.assertIs(manutencao.manutencao_ligada(), True)
        self.gravar('false')

        self.agora = 1029.9
        self.assertIs(manutencao.manutencao_ligada(), True)

        self.agora = 1030.0
        with self.assertNumQueries(1):
            self.assertIs(manutencao.manutencao_ligada(), False)

    def test_invalidar_faz_a_proxima_chamada_ler_o_banco_na_hora(self):
        self.gravar('false')
        self.assertIs(manutencao.manutencao_ligada(), False)
        self.gravar('true')

        manutencao.invalidar()

        with self.assertNumQueries(1):
            self.assertIs(manutencao.manutencao_ligada(), True)

    def test_sem_a_configuracao_a_manutencao_fica_desligada_e_o_valor_ignora_maiusculas(self):
        self.assertIs(manutencao.manutencao_ligada(), False)

        for valor, esperado in (('TRUE', True), ('True', True), ('false', False), ('1', False)):
            with self.subTest(valor=valor):
                self.gravar(valor)
                manutencao.invalidar()
                self.assertIs(manutencao.manutencao_ligada(), esperado)

    def test_salvar_pelo_painel_vale_na_hora_no_proprio_processo(self):
        admin = User.objects.create_user(
            email='admin@fluxar.teste', password='Cofre-Azul-2026', name='Admin',
            email_verified=True, is_staff=True, role='ADMIN',
        )
        self.client.force_authenticate(admin)
        self.assertIs(manutencao.manutencao_ligada(), False)

        resposta = self.client.post('/api/admin/settings/', {'maintenance_mode': True}, format='json')

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertIs(manutencao.manutencao_ligada(), True)

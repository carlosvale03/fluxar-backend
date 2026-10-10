"""
Consulta do log de auditoria (ADMIN-12 a ADMIN-15).
"""
from datetime import datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

from api.auditoria import Acoes, registrar
from api.exclusao import excluir_definitivamente
from api.models import RegistroDeExclusao, SystemLog

from .base import DESTRUIR, OK, PainelAdminTestCase, criar_admin

BRASILIA = ZoneInfo('America/Sao_Paulo')
ROTA = '/api/admin/logs/'
DATA_INVALIDA = ['Data inválida. Use o formato AAAA-MM-DD.']


def em(dia, hora=12, minuto=0):
    """Um instante do dia em Brasília."""
    return datetime.fromisoformat(dia).replace(hour=hora, minute=minuto, tzinfo=BRASILIA)


class ConsultaDoLogTestCase(PainelAdminTestCase):

    def gravar(self, admin, acao, quando, usuario=None):
        log = registrar(admin, acao, usuario, descricao=acao)
        SystemLog.objects.filter(pk=log.pk).update(timestamp=quando)
        return log.pk

    def ids(self, resposta):
        self.assertEqual(resposta.status_code, 200, resposta.data)
        return [item['id'] for item in resposta.data['results']]


class FiltrosTests(ConsultaDoLogTestCase):

    def setUp(self):
        super().setUp()
        self.outro_admin = criar_admin('outra.admin@teste.fluxar', 'Outra Admin')
        self.plano_dia_1 = str(self.gravar(self.admin, Acoes.CHANGE_PLAN, em('2026-10-01', 0, 0), self.usuario))
        self.papel_dia_2 = str(self.gravar(self.outro_admin, Acoes.CHANGE_ROLE, em('2026-10-02', 9), self.usuario))
        self.plano_dia_3 = str(self.gravar(self.outro_admin, Acoes.CHANGE_PLAN, em('2026-10-03', 23, 59), self.usuario))
        self.manutencao_dia_4 = str(self.gravar(self.admin, Acoes.UPDATE_MAINTENANCE, em('2026-10-04')))

    def test_sem_filtro_traz_tudo_do_mais_recente_para_o_mais_antigo(self):
        self.assertEqual(
            self.ids(self.client.get(ROTA)),
            [self.manutencao_dia_4, self.plano_dia_3, self.papel_dia_2, self.plano_dia_1],
        )

    def test_cada_filtro_sozinho(self):
        casos = {
            'action=CHANGE_PLAN': [self.plano_dia_3, self.plano_dia_1],
            f'admin={self.outro_admin.pk}': [self.plano_dia_3, self.papel_dia_2],
            'inicio=2026-10-03': [self.manutencao_dia_4, self.plano_dia_3],
            'fim=2026-10-02': [self.papel_dia_2, self.plano_dia_1],
        }
        for filtro, esperado in casos.items():
            with self.subTest(filtro=filtro):
                self.assertEqual(self.ids(self.client.get(f'{ROTA}?{filtro}')), esperado)

    def test_filtros_combinados(self):
        resposta = self.client.get(f'{ROTA}?action=CHANGE_PLAN&admin={self.outro_admin.pk}&inicio=2026-10-01&fim=2026-10-03')
        self.assertEqual(self.ids(resposta), [self.plano_dia_3])

        resposta = self.client.get(f'{ROTA}?action=CHANGE_ROLE&admin={self.admin.pk}')
        self.assertEqual(self.ids(resposta), [])

    def test_periodo_inclui_os_dois_dias_inteiros_no_fuso_de_brasilia(self):
        # 00:00 do dia 1 e 23:59 do dia 3 em Brasília ficam dentro
        resposta = self.client.get(f'{ROTA}?inicio=2026-10-01&fim=2026-10-03')
        self.assertEqual(self.ids(resposta), [self.plano_dia_3, self.papel_dia_2, self.plano_dia_1])

        resposta = self.client.get(f'{ROTA}?inicio=2026-10-02&fim=2026-10-02')
        self.assertEqual(self.ids(resposta), [self.papel_dia_2])

    def test_data_ou_administrador_invalido_recebe_400_no_campo(self):
        casos = {
            'inicio=01/10/2026': ('inicio', DATA_INVALIDA),
            'fim=2026-02-30': ('fim', DATA_INVALIDA),
            'inicio=2026-10-01T10:00': ('inicio', DATA_INVALIDA),
        }
        for filtro, (campo, mensagem) in casos.items():
            with self.subTest(filtro=filtro):
                resposta = self.client.get(f'{ROTA}?{filtro}')
                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.data[campo], mensagem)

        resposta = self.client.get(f'{ROTA}?admin=nao-e-um-id')
        self.assertEqual(resposta.status_code, 400)
        self.assertIn('admin', resposta.data)

    def test_parametro_vazio_vale_como_ausente(self):
        resposta = self.client.get(f'{ROTA}?action=&admin=&inicio=&fim=')
        self.assertEqual(len(self.ids(resposta)), 4)

    def test_lista_paginada_com_20_por_pagina(self):
        agora = em('2026-10-05')
        for minuto in range(21):
            self.gravar(self.admin, Acoes.CHANGE_PLAN, agora + timedelta(minutes=minuto), self.usuario)

        primeira = self.client.get(f'{ROTA}?action=CHANGE_PLAN')
        segunda = self.client.get(f'{ROTA}?action=CHANGE_PLAN&page=2')

        self.assertEqual(primeira.data['count'], 23)
        self.assertEqual(primeira.data['total_pages'], 2)
        self.assertEqual(len(primeira.data['results']), 20)
        self.assertEqual(len(segunda.data['results']), 3)
        self.assertEqual(segunda.data['results'][-1]['id'], self.plano_dia_1)


class LogDoUsuarioTests(ConsultaDoLogTestCase):

    @mock.patch(DESTRUIR, return_value=OK)
    def test_log_de_um_usuario_excluido_continua_consultavel_pelo_id(self, destruir):
        primeiro = str(self.gravar(self.admin, Acoes.CHANGE_PLAN, em('2026-10-01'), self.usuario))
        segundo = str(self.gravar(self.admin, Acoes.CHANGE_ROLE, em('2026-10-02'), self.usuario))
        self.gravar(self.admin, Acoes.UPDATE_MAINTENANCE, em('2026-10-03'))
        usuario_id = self.usuario.pk

        excluir_definitivamente(self.usuario, RegistroDeExclusao.ADMIN)

        resposta = self.client.get(f'/api/admin/users/{usuario_id}/logs/')
        self.assertEqual(self.ids(resposta), [segundo, primeiro])
        self.assertEqual(resposta.data['count'], 2)
        for item in resposta.data['results']:
            self.assertEqual(item['user_id'], str(usuario_id))
            self.assertEqual(item['user_email'], '')


class LogSomenteLeituraTests(ConsultaDoLogTestCase):

    def test_escrita_nas_rotas_do_log_recebe_405(self):
        log_id = self.gravar(self.admin, Acoes.CHANGE_PLAN, em('2026-10-01'), self.usuario)
        corpo = {'action': 'FALSO', 'description': 'inventado'}
        for rota in (ROTA, f'/api/admin/users/{self.usuario.pk}/logs/'):
            for metodo in ('post', 'put', 'patch', 'delete'):
                with self.subTest(rota=rota, metodo=metodo):
                    resposta = getattr(self.client, metodo)(rota, corpo, format='json')
                    self.assertEqual(resposta.status_code, 405)

        log = SystemLog.objects.get()
        self.assertEqual((log.pk, log.action), (log_id, 'CHANGE_PLAN'))

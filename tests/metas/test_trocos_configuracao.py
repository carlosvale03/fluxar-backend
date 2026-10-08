"""
Configuração do cofrinho de trocos (META-35, META-44, META-45).

`GET /api/goals/spare-change/` devolve a configuração e os trocos pendentes;
`PUT` ativa, escolhe a meta e desativa.
"""
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.core.cache import cache

from api.models import User
from core import travas
from goals.models import ConfiguracaoDeTrocos, Goal, Troco
from tests.metas.base import MetasTestCase
from tests.permissoes.base import fechar, liberacao_de_testes

URL = '/api/goals/spare-change/'
AGORA = datetime(2026, 10, 8, 15, 30, tzinfo=dt_timezone.utc)


def troco(dados, valor, status='PENDENTE'):
    return Troco.objects.create(user=dados.usuario, conta=dados.conta, valor=Decimal(valor), status=status)


class ConfiguracaoDosTrocosTests(MetasTestCase):

    def ativar(self, meta=None):
        with mock.patch('django.utils.timezone.now', return_value=AGORA):
            return self.client.put(URL, {'active': True, 'goal': (meta or self.a.meta).pk}, format='json')

    def test_sem_configuracao_os_trocos_estao_desativados_e_zerados(self):
        resp = self.client.get(URL)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, {
            'active': False, 'goal': None, 'paused': False, 'pending_total': '0.00', 'pending_count': 0,
        })

    def test_ativar_grava_a_meta_e_a_hora_da_ativacao(self):
        resp = self.ativar()

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data, {
            'active': True, 'goal': self.a.meta.pk, 'paused': False, 'pending_total': '0.00', 'pending_count': 0,
        })
        config = ConfiguracaoDeTrocos.objects.get(user=self.a.usuario)
        self.assertEqual((config.ativo, config.meta_id, config.ativado_em), (True, self.a.meta.pk, AGORA))
        self.assertEqual(self.client.get(URL).data, resp.data)

    def test_ativar_exige_uma_meta_ativa_do_usuario(self):
        sem_meta = self.client.put(URL, {'active': True}, format='json')
        alheia = self.client.put(URL, {'active': True, 'goal': self.b.meta.pk}, format='json')
        Goal.objects.filter(pk=self.a.meta.pk).update(is_active=False)
        arquivada = self.client.put(URL, {'active': True, 'goal': self.a.meta.pk}, format='json')

        self.assertEqual(sem_meta.status_code, 400)
        self.assertEqual(sem_meta.data['goal'], ['Este campo é obrigatório.'])
        self.assertEqual(alheia.status_code, 400)
        self.assertEqual(alheia.data['goal'], ['Meta não encontrada.'])
        self.assertEqual(arquivada.status_code, 400)
        self.assertEqual(arquivada.data['goal'], ['Metas arquivadas não recebem aportes.'])
        self.assertFalse(ConfiguracaoDeTrocos.objects.filter(user=self.a.usuario, ativo=True).exists())

    def test_meta_arquivada_ou_excluida_pausa_ate_escolher_outra(self):
        self.ativar()
        Goal.objects.filter(pk=self.a.meta.pk).update(is_active=False)

        arquivada = self.client.get(URL)

        self.assertEqual((arquivada.data['active'], arquivada.data['paused']), (True, True))

        outra = Goal.objects.create(user=self.a.usuario, name='Reserva', target_amount=Decimal('100.00'), account=self.a.cofrinho)
        escolhida = self.ativar(outra)
        self.assertEqual((escolhida.data['goal'], escolhida.data['paused']), (outra.pk, False))

        outra.delete()
        excluida = self.client.get(URL)
        self.assertEqual(
            (excluida.data['active'], excluida.data['goal'], excluida.data['paused']), (True, None, True),
        )

    def test_desativar_mantem_os_trocos_pendentes_no_total(self):
        self.ativar()
        troco(self.a, '0.70')
        troco(self.a, '0.40')
        troco(self.a, '0.50', status='DEPOSITADO')
        troco(self.a, '0.20', status='DESCARTADO')
        troco(self.b, '0.90')

        resp = self.client.put(URL, {'active': False}, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data, {
            'active': False, 'goal': self.a.meta.pk, 'paused': False, 'pending_total': '1.10', 'pending_count': 2,
        })
        self.assertEqual(Troco.objects.filter(user=self.a.usuario, status='PENDENTE').count(), 2)

    def test_exclusao_do_usuario_apaga_a_configuracao_e_os_trocos(self):
        self.ativar()
        troco(self.a, '0.70')
        troco(self.b, '0.90')

        User.objects.get(pk=self.a.usuario.pk).delete()

        self.assertFalse(ConfiguracaoDeTrocos.objects.filter(user_id=self.a.usuario.pk).exists())
        self.assertFalse(Troco.objects.filter(user_id=self.a.usuario.pk).exists())
        self.assertEqual(Troco.objects.filter(user=self.b.usuario).count(), 1)


class TravaDosTrocosTests(MetasTestCase):

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(travas.invalidar)
        liberacao_de_testes(False)
        fechar('metas')

    def test_configuracao_dos_trocos_recebe_403_com_metas_fechada(self):
        for metodo in ('get', 'put'):
            resp = getattr(self.client, metodo)(URL, {'active': True, 'goal': self.a.meta.pk}, format='json')
            self.assertEqual(resp.status_code, 403, metodo)
            self.assertEqual((resp.data['code'], resp.data['feature']), ('plan_locked', 'metas'), metodo)
        self.assertFalse(ConfiguracaoDeTrocos.objects.exists())

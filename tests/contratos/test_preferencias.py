"""Preferências no formato da tela: o objeto `preferences` (CONTRATO-26, CONTRATO-28)."""
from api.models import User

from .base import ContratosTestCase

URL_PERFIL = '/api/users/me/'


class PreferenciasTests(ContratosTestCase):

    def setUp(self):
        super().setUp()
        User.objects.filter(pk=self.a.usuario.pk).update(
            theme_preference='light', currency='BRL', language='pt-BR',
            notification_settings={'email': True, 'push': True, 'budget_alerts': True},
        )
        # Como numa requisição real, o usuário vem do banco
        self.client.force_authenticate(user=self.usuario())

    def usuario(self):
        return User.objects.get(pk=self.a.usuario.pk)

    def test_salva_e_devolve_o_objeto_preferences(self):
        resp = self.client.patch(URL_PERFIL, {
            'preferences': {'theme': 'dark', 'notifications': {'email': False}},
        }, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['preferences']['theme'], 'dark')
        self.assertIs(resp.data['preferences']['notifications']['email'], False)
        self.assertEqual(self.usuario().theme_preference, 'dark')
        # Recarregar a página lê o mesmo valor
        self.assertEqual(self.client.get(URL_PERFIL).data['preferences']['theme'], 'dark')

    def test_demais_preferencias_continuam_como_estavam(self):
        self.client.patch(URL_PERFIL, {
            'preferences': {'theme': 'dark', 'notifications': {'email': False}},
        }, format='json')

        usuario = self.usuario()
        self.assertEqual(usuario.notification_settings, {'email': False, 'push': True, 'budget_alerts': True})
        self.assertEqual((usuario.currency, usuario.language), ('BRL', 'pt-BR'))

    def test_valor_invalido_recebe_400_no_campo(self):
        resp = self.client.patch(URL_PERFIL, {'preferences': {'theme': 'roxo'}}, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('theme', resp.data['preferences'])
        self.assertEqual(self.usuario().theme_preference, 'light')

        resp = self.client.patch(URL_PERFIL, {'preferences': {'currency': 'USD'}}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('currency', resp.data['preferences'])

        resp = self.client.patch(URL_PERFIL, {'preferences': {'notifications': {'email': 'talvez'}}}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('notifications', resp.data['preferences'])
        self.assertEqual(self.usuario().notification_settings['email'], True)

    def test_campos_planos_continuam_aceitos(self):
        resp = self.client.patch(URL_PERFIL, {'theme_preference': 'system', 'name': 'Novo nome'}, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['preferences']['theme'], 'system')
        self.assertEqual((self.usuario().theme_preference, self.usuario().name), ('system', 'Novo nome'))

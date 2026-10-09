"""
Imagens enviadas com nome aleatório (LGPD-20).

O uploader do Cloudinary é simulado: o teste confere o arquivo e as opções
que chegariam ao Cloudinary.
"""
import re
from unittest import mock

import cloudinary
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from api.models import User

SENHA = 'senha-de-teste-123'
NOME_ALEATORIO = re.compile(r'[0-9a-f]{32}\.jpg')


def resposta_do_cloudinary(pasta):
    return {
        'public_id': f'{pasta}/abc123', 'version': 1, 'type': 'upload',
        'resource_type': 'image', 'format': 'jpg',
    }


def imagem(nome):
    return SimpleUploadedFile(nome, b'\xff\xd8\xff\xe0conteudo', content_type='image/jpeg')


class NomeAleatorioTests(APITestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(email='upload@teste.fluxar', password=SENHA, name='João Silva')
        self.client.force_authenticate(user=self.usuario)
        # O link da imagem precisa de um cloud_name, que o CI não configura
        config = mock.patch.object(cloudinary.config(), 'cloud_name', 'teste', create=True)
        config.start()
        self.addCleanup(config.stop)

    def assert_enviado_sem_o_nome_original(self, upload):
        self.assertEqual(upload.call_count, 1)
        arquivo = upload.call_args.args[0]
        opcoes = upload.call_args.kwargs
        self.assertRegex(arquivo.name, NOME_ALEATORIO)
        self.assertNotIn('joao', arquivo.name.lower())
        self.assertNotIn('joao', repr(opcoes).lower())
        self.assertIs(opcoes['use_filename'], False)

    @mock.patch('cloudinary.uploader.upload', return_value=resposta_do_cloudinary('avatars'))
    def test_avatar_vai_com_nome_aleatorio(self, upload):
        resposta = self.client.post(
            '/api/users/me/avatar/', {'avatar': imagem('joao-silva.jpg')}, format='multipart',
        )

        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assert_enviado_sem_o_nome_original(upload)

    @mock.patch('cloudinary.uploader.upload', return_value=resposta_do_cloudinary('goals'))
    def test_imagem_da_meta_vai_com_nome_aleatorio(self, upload):
        resposta = self.client.post('/api/goals/', {
            'name': 'Viagem', 'target_amount': '500.00', 'image': imagem('joao-silva.jpg'),
        }, format='multipart')

        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assert_enviado_sem_o_nome_original(upload)

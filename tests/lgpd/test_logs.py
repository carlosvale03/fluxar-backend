"""
Logs sem dados pessoais nem financeiros (LGPD-21, LGPD-22, LGPD-23).
"""
import ast
import contextlib
import io
import logging
import os
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APITestCase

from accounts.models import Account
from api.models import User
from core.logs import FiltroDeDadosPessoais
from goals.models import Goal

SENHA = 'senha-de-teste-123'
# Pastas fora do código de produção
FORA_DA_PRODUCAO = {'tests', 'migrations', 'venv', 'scratch', '.git', 'node_modules', '__pycache__'}


class CapturaDeTudo(logging.Handler):
    """Guarda a mensagem de todo registro que chega ao logger raiz."""

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.mensagens = []

    def emit(self, record):
        self.mensagens.append(record.getMessage())


@contextlib.contextmanager
def capturar_logs_e_saida():
    raiz = logging.getLogger()
    captura = CapturaDeTudo()
    nivel = raiz.level
    raiz.addHandler(captura)
    raiz.setLevel(logging.DEBUG)
    saida = io.StringIO()
    try:
        with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(saida):
            yield captura.mensagens, saida
    finally:
        raiz.removeHandler(captura)
        raiz.setLevel(nivel)


class SemPrintTests(SimpleTestCase):

    def test_codigo_de_producao_nao_tem_print(self):
        com_print = []
        arquivos = []
        for pasta, subpastas, nomes in os.walk(settings.BASE_DIR):
            subpastas[:] = [nome for nome in subpastas if nome not in FORA_DA_PRODUCAO]
            arquivos += [Path(pasta, nome) for nome in nomes if nome.endswith('.py')]
        self.assertIn(Path(settings.BASE_DIR, 'transactions', 'views.py'), arquivos)
        for arquivo in arquivos:
            relativo = arquivo.relative_to(settings.BASE_DIR)
            arvore = ast.parse(arquivo.read_text(encoding='utf-8'))
            for no in ast.walk(arvore):
                if isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id == 'print':
                    com_print.append(f'{relativo}:{no.lineno}')
        self.assertEqual(com_print, [])


class CategoriaSemPayloadNoLogTests(APITestCase):

    def test_criar_categoria_nao_escreve_o_payload(self):
        usuario = User.objects.create_user(email='categoria@teste.fluxar', password=SENHA, name='Pessoa')
        self.client.force_authenticate(user=usuario)

        with capturar_logs_e_saida() as (mensagens, saida):
            criada = self.client.post(
                '/api/categories/', {'name': 'Remédio Sigiloso', 'type': 'EXPENSE'}, format='json',
            )
            recusada = self.client.post('/api/categories/', {'name': 'Outra Sigilosa', 'type': 'INVALIDO'}, format='json')

        self.assertEqual(criada.status_code, 201, criada.data)
        self.assertEqual(recusada.status_code, 400)
        registrado = '\n'.join(mensagens) + saida.getvalue()
        self.assertNotIn('Sigilos', registrado)
        self.assertNotIn('EXPENSE', registrado)


class FiltroDeDadosPessoaisTests(SimpleTestCase):

    def registrar(self, mensagem, *argumentos):
        logger = logging.getLogger('tests.lgpd.filtro')
        captura = CapturaDeTudo()
        captura.addFilter(FiltroDeDadosPessoais())
        logger.addHandler(captura)
        logger.propagate = False
        try:
            logger.warning(mensagem, *argumentos)
        finally:
            logger.removeHandler(captura)
            logger.propagate = True
        return captura.mensagens[0]

    def test_troca_email_e_cpf_pela_forma_mascarada(self):
        mensagem = self.registrar('Login de joao.silva@x.com com CPF 529.982.247-25 e 52998224725')

        self.assertEqual(
            mensagem, 'Login de jo***@x.com com CPF ***.***.***-25 e ***.***.***-25',
        )

    def test_mascara_tambem_os_argumentos(self):
        self.assertEqual(self.registrar('Envio para %s', 'ana@x.com'), 'Envio para an***@x.com')

    def test_mascara_o_traceback_do_erro(self):
        logger = logging.getLogger('tests.lgpd.filtro.traceback')
        saida = io.StringIO()
        handler = logging.StreamHandler(saida)
        handler.addFilter(FiltroDeDadosPessoais())
        logger.addHandler(handler)
        logger.propagate = False
        try:
            try:
                raise ValueError('chave duplicada: joao.silva@x.com')
            except ValueError:
                logger.exception('Erro inesperado')
        finally:
            logger.removeHandler(handler)
            logger.propagate = True

        self.assertIn('ValueError: chave duplicada: jo***@x.com', saida.getvalue())
        self.assertNotIn('joao.silva@x.com', saida.getvalue())

    def test_filtro_ligado_em_todos_os_handlers_e_no_logger_raiz(self):
        caminho = 'core.logs.FiltroDeDadosPessoais'
        filtros = settings.LOGGING['filters']
        nomes = {nome for nome, filtro in filtros.items() if filtro.get('()') == caminho}
        self.assertTrue(nomes)
        for nome, handler in settings.LOGGING['handlers'].items():
            self.assertTrue(nomes & set(handler.get('filters', [])), nome)
        self.assertTrue(settings.LOGGING['root']['handlers'])

        raiz = logging.getLogger()
        self.assertTrue(raiz.handlers)
        for logger in (raiz, logging.getLogger('api'), logging.getLogger('core')):
            for handler in logger.handlers:
                self.assertTrue(
                    any(isinstance(filtro, FiltroDeDadosPessoais) for filtro in handler.filters), handler,
                )


class ErroNoCloudinaryTests(TestCase):

    ERRO = RuntimeError('falha ao remover a imagem de joao@x.com com o token abc123')

    def assert_so_a_classe(self, logs):
        self.assertEqual(len(logs.records), 1)
        mensagem = logs.records[0].getMessage()
        self.assertIn('RuntimeError', mensagem)
        self.assertNotIn('joao', mensagem)
        self.assertNotIn('abc123', mensagem)
        self.assertIsNone(logs.records[0].exc_info)

    @mock.patch('cloudinary.uploader.destroy', side_effect=ERRO)
    def test_troca_do_avatar_loga_so_a_classe_do_erro(self, _destroy):
        usuario = User.objects.create_user(email='avatar@teste.fluxar', password=SENHA, name='Pessoa')
        User.objects.filter(pk=usuario.pk).update(avatar='image/upload/v1/avatars/antigo.jpg')
        usuario.refresh_from_db()
        usuario.avatar = 'image/upload/v1/avatars/novo.jpg'

        with self.assertLogs('api.signals', level='ERROR') as logs:
            usuario.save()

        self.assert_so_a_classe(logs)

    @mock.patch('cloudinary.uploader.destroy', side_effect=ERRO)
    def test_exclusao_da_meta_loga_so_a_classe_do_erro(self, _destroy):
        usuario = User.objects.create_user(email='meta@teste.fluxar', password=SENHA, name='Pessoa')
        cofrinho = Account.objects.create(user=usuario, name='Cofrinho', type='PIGGY_BANK')
        meta = Goal.objects.create(
            user=usuario, name='Viagem', target_amount=Decimal('100.00'), account=cofrinho,
            image='image/upload/v1/goals/foto.jpg',
        )
        meta = Goal.objects.get(pk=meta.pk)

        with self.assertLogs('goals.signals', level='ERROR') as logs:
            meta.delete()

        self.assert_so_a_classe(logs)


class ComandosSemDadosPessoaisTests(TestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(email='dono.da.conta@teste.fluxar', password=SENHA, name='Pessoa')
        self.ativa = Account.objects.create(
            user=self.usuario, name='Conta Secreta', type='CHECKING',
            initial_balance=Decimal('1234.56'), balance=Decimal('1234.56'),
        )
        self.inativa = Account.objects.create(
            user=self.usuario, name='Conta Escondida', type='CHECKING', is_active=False,
        )

    def rodar(self, comando):
        saida = io.StringIO()
        call_command(comando, stdout=saida)
        return saida.getvalue()

    def assert_sem_dados(self, texto):
        self.assertNotIn('dono.da.conta@teste.fluxar', texto)
        self.assertNotIn('Conta Secreta', texto)
        self.assertNotIn('Conta Escondida', texto)
        self.assertNotIn('1234', texto)

    def test_audit_accounts_mostra_so_id_e_email_mascarado(self):
        texto = self.rodar('audit_accounts')

        self.assert_sem_dados(texto)
        self.assertIn(str(self.ativa.pk), texto)
        self.assertIn(str(self.inativa.pk), texto)
        self.assertIn('do***@teste.fluxar', texto)

    def test_init_balances_mostra_so_o_id(self):
        texto = self.rodar('init_balances')

        self.assert_sem_dados(texto)
        self.assertIn(str(self.ativa.pk), texto)

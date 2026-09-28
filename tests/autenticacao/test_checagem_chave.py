"""
Checagem da SECRET_KEY comprometida (AUTH-42).

Os testes nunca usam uma chave real: cada caso injeta o hash de uma chave de
teste na lista de chaves comprometidas.
"""
import hashlib
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import SystemCheckError
from django.test import SimpleTestCase, override_settings

from core import checks

CHAVE_DO_HISTORICO = 'chave-de-teste-que-finge-estar-no-historico-0123456789abcdef'
CHAVE_INSEGURA = 'django-insecure-chave-de-teste-gerada-pelo-startproject-0123'
CHAVE_NOVA = 'chave-de-teste-nova-que-nunca-apareceu-no-historico-0123456789'

LISTA_DE_TESTE = frozenset({hashlib.sha256(CHAVE_DO_HISTORICO.encode()).hexdigest()})


@mock.patch.object(checks, 'CHAVES_COMPROMETIDAS', LISTA_DE_TESTE)
class ChecagemDaChaveTests(SimpleTestCase):

    def ids(self, erros):
        return [erro.id for erro in erros]

    @override_settings(DEBUG=False, SECRET_KEY=CHAVE_DO_HISTORICO)
    def test_chave_do_historico_em_producao_da_erro(self):
        erros = checks.check_secret_key(None)
        self.assertEqual(self.ids(erros), ['core.E001'])
        self.assertIn('SECRET_KEY', erros[0].msg)

    @override_settings(DEBUG=False, SECRET_KEY=CHAVE_INSEGURA)
    def test_chave_com_prefixo_django_insecure_em_producao_da_erro(self):
        self.assertEqual(self.ids(checks.check_secret_key(None)), ['core.E001'])

    @override_settings(DEBUG=False, SECRET_KEY=CHAVE_NOVA)
    def test_chave_nova_em_producao_nao_da_erro(self):
        self.assertEqual(checks.check_secret_key(None), [])

    @override_settings(DEBUG=True, SECRET_KEY=CHAVE_DO_HISTORICO)
    def test_com_debug_ligado_nao_confere_a_chave(self):
        self.assertEqual(checks.check_secret_key(None), [])

    @override_settings(DEBUG=False, SECRET_KEY=CHAVE_DO_HISTORICO)
    def test_check_deploy_falha_com_a_chave_do_historico(self):
        with self.assertRaises(SystemCheckError) as contexto:
            call_command('check', '--deploy', stdout=StringIO(), stderr=StringIO())
        self.assertIn('core.E001', str(contexto.exception))

    @override_settings(DEBUG=False, SECRET_KEY=CHAVE_NOVA)
    def test_check_deploy_passa_com_chave_nova(self):
        call_command('check', '--deploy', stdout=StringIO(), stderr=StringIO())


class InicializacaoDeProducaoTests(SimpleTestCase):
    """A inicialização em produção roda o check --deploy antes de subir o servidor."""

    def test_entrypoint_confere_a_chave_antes_de_migrar_e_subir(self):
        script = (Path(settings.BASE_DIR) / 'entrypoint.sh').read_text(encoding='utf-8')
        linhas = [linha.strip() for linha in script.splitlines()]
        self.assertIn('set -e', linhas)
        checagem = linhas.index('python manage.py check --deploy')
        self.assertLess(checagem, linhas.index('python manage.py migrate --noinput'))
        servidor = next(i for i, linha in enumerate(linhas) if linha.startswith('exec gunicorn'))
        self.assertLess(checagem, servidor)

"""
Configuração de segurança exigida em produção (AUTH-37, AUTH-38 e AUTH-39).

As settings são lidas uma única vez, na inicialização. Por isso cada caso
importa as settings num Python novo, com as variáveis de ambiente
controladas. O script desliga o `load_dotenv()` antes de importar as
settings, para que o `.env` local não preencha as variáveis que o teste
deixou de fora: uma variável `None` em `iniciar()` sai do ambiente.
"""
import json
import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase

# Valores só de teste; nenhum deles é uma chave real.
CHAVE_DE_TESTE = 'chave-de-teste-da-configuracao-0123456789abcdefghijklmnop'
FRONTEND_DE_TESTE = 'https://app.fluxar.teste'
ORIGEM_ALHEIA = 'https://site-malicioso.teste'

SEM_DOTENV = 'import dotenv\ndotenv.load_dotenv = lambda *args, **kwargs: False\n'

SCRIPT_INICIA = SEM_DOTENV + 'import django\ndjango.setup()\nprint("iniciou")\n'

SCRIPT_VALORES_DEV = SEM_DOTENV + '''
import json
import django
django.setup()
from django.conf import settings
print(json.dumps({
    'frontend_url': settings.FRONTEND_URL,
    'tem_secret_key': bool(settings.SECRET_KEY),
}))
'''

# Faz uma requisição simples e uma preflight com o cabeçalho Origin e devolve
# o Access-Control-Allow-Origin de cada uma. As duas passam só por caminhos
# que não consultam o banco.
SCRIPT_CORS = SEM_DOTENV + '''
import json, sys
import django
django.setup()
from django.test.utils import setup_test_environment
setup_test_environment()
from django.test import Client
from django.conf import settings
origem = sys.argv[1]
cliente = Client()
simples = cliente.get('/api/auth/login/', HTTP_ORIGIN=origem)
preflight = cliente.options(
    '/api/auth/login/', HTTP_ORIGIN=origem,
    HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
)
print(json.dumps({
    'simples': simples.headers.get('Access-Control-Allow-Origin'),
    'preflight': preflight.headers.get('Access-Control-Allow-Origin'),
    'allow_all': settings.CORS_ALLOW_ALL_ORIGINS,
}))
'''

PRODUCAO = {
    'DEBUG': '0',
    'SECRET_KEY': CHAVE_DE_TESTE,
    'FRONTEND_URL': FRONTEND_DE_TESTE,
    'CORS_ALLOWED_ORIGINS': None,
}


def iniciar(script, *argumentos, **variaveis):
    """
    Roda o script num Python novo, com as settings do projeto. Cada variável
    com valor recebe esse valor; cada uma com `None` sai do ambiente.
    """
    ambiente = os.environ.copy()
    ambiente['DJANGO_SETTINGS_MODULE'] = 'core.settings'
    for nome, valor in variaveis.items():
        if valor is None:
            ambiente.pop(nome, None)
        else:
            ambiente[nome] = valor
    return subprocess.run(
        [sys.executable, '-c', script, *argumentos],
        cwd=settings.BASE_DIR, env=ambiente,
        capture_output=True, text=True, timeout=120,
    )


def ultima_linha(texto):
    linhas = [linha for linha in texto.strip().splitlines() if linha.strip()]
    return linhas[-1] if linhas else ''


class ConfiguracaoDeProducaoTests(SimpleTestCase):
    """Com DEBUG desligado, a falta de uma variável obrigatória impede a inicialização."""

    def assert_falha_nomeando(self, resultado, variavel):
        self.assertNotEqual(resultado.returncode, 0, resultado.stdout)
        erro = ultima_linha(resultado.stderr)
        self.assertTrue(
            erro.startswith('django.core.exceptions.ImproperlyConfigured:'), erro,
        )
        self.assertIn(variavel, erro)

    def test_sem_secret_key_em_producao_interrompe_nomeando_a_variavel(self):
        resultado = iniciar(SCRIPT_INICIA, **{**PRODUCAO, 'SECRET_KEY': None})
        self.assert_falha_nomeando(resultado, 'SECRET_KEY')

    def test_sem_frontend_url_em_producao_interrompe_nomeando_a_variavel(self):
        resultado = iniciar(SCRIPT_INICIA, **{**PRODUCAO, 'FRONTEND_URL': None})
        self.assert_falha_nomeando(resultado, 'FRONTEND_URL')

    def test_frontend_url_vazia_conta_como_ausente(self):
        resultado = iniciar(SCRIPT_INICIA, **{**PRODUCAO, 'FRONTEND_URL': ''})
        self.assert_falha_nomeando(resultado, 'FRONTEND_URL')

    def test_com_as_duas_variaveis_em_producao_inicia(self):
        resultado = iniciar(SCRIPT_INICIA, **PRODUCAO)
        self.assertEqual(resultado.returncode, 0, ultima_linha(resultado.stderr))
        self.assertEqual(ultima_linha(resultado.stdout), 'iniciou')

    def test_com_debug_ligado_usa_os_valores_de_desenvolvimento(self):
        resultado = iniciar(
            SCRIPT_VALORES_DEV,
            **{**PRODUCAO, 'DEBUG': '1', 'SECRET_KEY': None, 'FRONTEND_URL': None},
        )
        self.assertEqual(resultado.returncode, 0, ultima_linha(resultado.stderr))
        valores = json.loads(ultima_linha(resultado.stdout))
        self.assertEqual(valores['frontend_url'], 'http://localhost:3000')
        self.assertTrue(valores['tem_secret_key'])


class CorsTests(SimpleTestCase):
    """Sem CORS_ALLOWED_ORIGINS, nenhuma origem é liberada (AUTH-39)."""

    def cors(self, origem, lista):
        resultado = iniciar(SCRIPT_CORS, origem, **{**PRODUCAO, 'CORS_ALLOWED_ORIGINS': lista})
        self.assertEqual(resultado.returncode, 0, ultima_linha(resultado.stderr))
        return json.loads(ultima_linha(resultado.stdout))

    def test_sem_a_lista_nenhuma_origem_recebe_o_cabecalho(self):
        cabecalhos = self.cors(ORIGEM_ALHEIA, None)
        self.assertIsNone(cabecalhos['simples'])
        self.assertIsNone(cabecalhos['preflight'])
        self.assertFalse(cabecalhos['allow_all'])

    def test_com_a_lista_so_a_origem_listada_recebe_o_cabecalho(self):
        lista = f'{FRONTEND_DE_TESTE},https://outro.fluxar.teste'
        liberada = self.cors(FRONTEND_DE_TESTE, lista)
        self.assertEqual(liberada['simples'], FRONTEND_DE_TESTE)
        self.assertEqual(liberada['preflight'], FRONTEND_DE_TESTE)

        alheia = self.cors(ORIGEM_ALHEIA, lista)
        self.assertIsNone(alheia['simples'])
        self.assertIsNone(alheia['preflight'])

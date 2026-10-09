"""
Campo criptografado e chave obrigatória (LGPD-15, LGPD-16, AD-047).

O valor gravado no banco é o que `get_db_prep_save` devolve, e a leitura é o
que `from_db_value` devolve; os casos conferem os dois lados sem depender de
um modelo. A obrigatoriedade da chave segue o padrão de
`tests/autenticacao/test_configuracao.py`: as settings são lidas num Python
novo, com as variáveis de ambiente controladas.
"""
import datetime
import json
from decimal import Decimal

from cryptography.fernet import Fernet
from django.db import connection
from django.test import SimpleTestCase, override_settings

from core.criptografia import (
    DataCriptografada,
    DecimalCriptografado,
    TextoCriptografado,
    descriptografar_texto,
)
from tests.autenticacao.test_configuracao import (
    PRODUCAO,
    SCRIPT_INICIA,
    SEM_DOTENV,
    iniciar,
    ultima_linha,
)

# Chaves só de teste
CHAVE_ANTIGA = Fernet.generate_key().decode()
CHAVE_NOVA = Fernet.generate_key().decode()

SCRIPT_CHAVES = SEM_DOTENV + '''
import json
import django
django.setup()
from django.conf import settings
print(json.dumps(settings.FIELD_ENCRYPTION_KEYS))
'''


def gravar(campo, valor):
    """O valor como vai para a coluna do banco."""
    return campo.get_db_prep_save(valor, connection)


def ler(campo, valor_no_banco):
    """O valor como volta do banco."""
    return campo.from_db_value(valor_no_banco, None, connection)


class CampoCriptografadoTests(SimpleTestCase):

    def test_texto_volta_igual_e_o_banco_nao_tem_o_texto_em_claro(self):
        campo = TextoCriptografado()
        no_banco = gravar(campo, '52998224725')

        self.assertNotIn('52998224725', no_banco)
        self.assertNotIn('529982', no_banco)
        self.assertEqual(ler(campo, no_banco), '52998224725')

    def test_data_volta_como_data(self):
        campo = DataCriptografada()
        nascimento = datetime.date(1990, 5, 17)
        no_banco = gravar(campo, nascimento)

        self.assertNotIn('1990', no_banco)
        self.assertNotIn('05-17', no_banco)
        self.assertEqual(ler(campo, no_banco), nascimento)
        self.assertIsInstance(ler(campo, no_banco), datetime.date)

    def test_decimal_volta_como_decimal_com_as_casas(self):
        campo = DecimalCriptografado()
        no_banco = gravar(campo, Decimal('4321.50'))

        self.assertNotIn('4321', no_banco)
        lido = ler(campo, no_banco)
        self.assertEqual(lido, Decimal('4321.50'))
        self.assertEqual(str(lido), '4321.50')

    def test_none_continua_none(self):
        for campo in (TextoCriptografado(), DataCriptografada(), DecimalCriptografado()):
            with self.subTest(campo=type(campo).__name__):
                self.assertIsNone(gravar(campo, None))
                self.assertIsNone(ler(campo, None))

    def test_com_duas_chaves_le_o_valor_gravado_com_a_segunda(self):
        campo = TextoCriptografado()
        with override_settings(FIELD_ENCRYPTION_KEYS=[CHAVE_ANTIGA]):
            gravado_com_a_antiga = gravar(campo, '11144477735')

        with override_settings(FIELD_ENCRYPTION_KEYS=[CHAVE_NOVA, CHAVE_ANTIGA]):
            self.assertEqual(ler(campo, gravado_com_a_antiga), '11144477735')
            gravado_agora = gravar(campo, '11144477735')

        # O valor novo sai com a primeira chave da lista
        self.assertEqual(descriptografar_texto(gravado_agora, chaves=[CHAVE_NOVA]), '11144477735')


class ChaveObrigatoriaTests(SimpleTestCase):

    def test_sem_a_chave_em_producao_interrompe_nomeando_a_variavel(self):
        resultado = iniciar(SCRIPT_INICIA, **{**PRODUCAO, 'FIELD_ENCRYPTION_KEY': None})

        self.assertNotEqual(resultado.returncode, 0, resultado.stdout)
        erro = ultima_linha(resultado.stderr)
        self.assertTrue(erro.startswith('django.core.exceptions.ImproperlyConfigured:'), erro)
        self.assertIn('FIELD_ENCRYPTION_KEY', erro)

    def test_lista_separada_por_virgula_vira_a_lista_de_chaves(self):
        resultado = iniciar(
            SCRIPT_CHAVES, **{**PRODUCAO, 'FIELD_ENCRYPTION_KEY': f'{CHAVE_NOVA}, {CHAVE_ANTIGA}'},
        )

        self.assertEqual(resultado.returncode, 0, ultima_linha(resultado.stderr))
        self.assertEqual(json.loads(ultima_linha(resultado.stdout)), [CHAVE_NOVA, CHAVE_ANTIGA])

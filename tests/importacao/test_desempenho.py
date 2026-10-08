"""
Tempo de importação e concorrência do servidor (IMPORT-40, IMPORT-41).

O arquivo de 10.000 linhas mede só a chamada da importação. O
`gunicorn.conf.py` é importado como módulo para conferir os valores.
"""
import importlib.util
import json
import os
import time
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase

from accounts.models import Account
from accounts.saldo import calcular
from transactions.models import Transaction

from .base import MAPEAMENTO, URL_PLANILHA, ImportacaoTestCase, arquivo_csv

LIMITE_DE_SEGUNDOS = 30


class DesempenhoTests(ImportacaoTestCase):

    def test_dez_mil_linhas_em_ate_30_segundos(self):
        """IMPORT-40: um CSV de 10.000 linhas válidas importa em até 30 segundos."""
        linhas = [['Data', 'Descrição', 'Valor', 'Categoria', 'Tags']]
        for i in range(10_000):
            dia = i % 28 + 1
            linhas.append([
                f'{dia:02d}/09/2026', f'Compra {i}', f'-{i % 100 + 1},50',
                f'Categoria {i % 10}', f'tag {i % 5}',
            ])
        mapeamento = {**MAPEAMENTO, 'category_column': 'Categoria', 'tags_column': 'Tags'}
        arquivo = arquivo_csv(linhas)
        self.assertLessEqual(arquivo.size, 5 * 1024 * 1024)

        inicio = time.monotonic()
        resp = self.client.post(URL_PLANILHA, {
            'file': arquivo, 'mapping': json.dumps(mapeamento),
            'import_type': 'INCOME_EXPENSE', 'account_id': str(self.a.conta.id),
        }, format='multipart')
        duracao = time.monotonic() - inicio

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual((resp.data['total'], resp.data['imported'], resp.data['rejected']), (10_000, 10_000, 0))
        self.assertLessEqual(duracao, LIMITE_DE_SEGUNDOS, f'{duracao:.1f} s')
        print(f'\n[IMPORT-40] 10.000 linhas em {duracao:.1f} s')  # noqa: T201 - tempo medido no relatório
        self.assertEqual(Transaction.objects.filter(import_batch=resp.data['batch_id']).count(), 10_000)
        conta = Account.objects.get(pk=self.a.conta.pk)
        # 1000 - 100 x (1,50 + 2,50 + ... + 100,50)
        self.assertEqual(conta.balance, Decimal('1000.00') - 100 * (Decimal('5050') + Decimal('50')))
        self.assertEqual(conta.balance, calcular(conta))


class ConfiguracaoDoGunicornTests(SimpleTestCase):

    def carregar(self, **ambiente):
        """Importa o `gunicorn.conf.py` da raiz com as variáveis de `ambiente`."""
        variaveis = {k: v for k, v in os.environ.items() if k not in {'WEB_CONCURRENCY', 'GUNICORN_THREADS', 'PORT'}}
        variaveis.update(ambiente)
        caminho = Path(settings.BASE_DIR) / 'gunicorn.conf.py'
        with patch.dict(os.environ, variaveis, clear=True):
            spec = importlib.util.spec_from_file_location('gunicorn_conf', caminho)
            modulo = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(modulo)
        return modulo

    def test_gthread_com_dois_workers_e_quatro_threads_por_padrao(self):
        """IMPORT-41: uma importação ocupa uma thread; as outras requisições seguem atendidas."""
        conf = self.carregar()
        self.assertEqual(
            (conf.worker_class, conf.workers, conf.threads, conf.timeout),
            ('gthread', 2, 4, 120),
        )
        self.assertFalse(hasattr(conf, 'bind'))

    def test_variaveis_de_ambiente_ajustam_workers_threads_e_porta(self):
        """IMPORT-41: WEB_CONCURRENCY, GUNICORN_THREADS e PORT mudam sem mexer no Start Command."""
        conf = self.carregar(WEB_CONCURRENCY='3', GUNICORN_THREADS='8', PORT='10000')
        self.assertEqual((conf.workers, conf.threads, conf.bind), (3, 8, '0.0.0.0:10000'))

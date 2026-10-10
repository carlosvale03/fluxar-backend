"""
Grava em CSV o conjunto anonimizado para melhorar o produto (LGPD-36 a
LGPD-38): só os dados de quem consentiu, sem identificadores.

A saída do comando traz só a contagem de linhas, sem dados (LGPD-21).
"""
import csv

from django.core.management.base import BaseCommand

from core.conjuntos import COLUNAS, dados_para_melhoria


class Command(BaseCommand):
    help = 'Grava em CSV os dados anonimizados de quem consentiu com o uso na melhoria do produto.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--saida', default='dados_de_melhoria.csv', help='Caminho do CSV gerado (padrão: dados_de_melhoria.csv).',
        )

    def handle(self, *args, **options):
        linhas = dados_para_melhoria()
        with open(options['saida'], 'w', newline='', encoding='utf-8') as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS)
            escritor.writeheader()
            escritor.writerows(linhas)
        self.stdout.write(f'Linhas gravadas: {len(linhas)}.')

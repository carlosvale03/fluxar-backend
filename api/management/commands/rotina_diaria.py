"""
Rotina diária do backend (AD-048): apaga as contas cuja exclusão definitiva
venceu (LGPD-10, LGPD-12).

O workflow agendado do GitHub chama `POST /api/rotina-diaria/`, que roda o
mesmo código; este comando serve para rodar à mão no Render Shell. A saída
traz só as contagens, sem identificar ninguém (LGPD-21).
"""
from django.core.management.base import BaseCommand

from api.exclusao import excluir_contas_vencidas


class Command(BaseCommand):
    help = 'Roda a rotina diária: apaga as contas com a exclusão definitiva vencida.'

    def handle(self, *args, **options):
        excluidas, falhas = excluir_contas_vencidas()
        self.stdout.write(f'Contas excluídas: {excluidas}. Falhas: {falhas}.')

from django.apps import apps
from django.core.management.base import BaseCommand

from core.isolation import find_cross_links, fix_cross_links


class Command(BaseCommand):
    help = 'Lista as ligações entre dados de usuários diferentes e, com --fix, desfaz cada uma'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix', action='store_true',
            help='Desfaz as ligações e recalcula saldos, faturas e metas afetados',
        )

    def handle(self, *args, **options):
        # A saída traz só tipos, relações e IDs: nada de nomes, valores ou e-mails (AD-019)
        links = find_cross_links(apps)
        for link in links:
            self.stdout.write(f'{link.tipo} {link.registro_id} {link.relacao} {link.alheio_id}')
        self.stdout.write(f'Ligações cruzadas: {len(links)}')

        if options['fix']:
            relatorio = fix_cross_links(apps)
            self.stdout.write(
                f'Ligações desfeitas: {relatorio.ligacoes}. Recalculados: contas {relatorio.contas}, '
                f'faturas {relatorio.faturas}, metas {relatorio.metas}.'
            )

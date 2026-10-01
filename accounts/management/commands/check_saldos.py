from django.core.management.base import BaseCommand

from accounts.models import Account
from accounts.saldo import calcular


class Command(BaseCommand):
    help = (
        'Confere o saldo guardado de cada conta, ativa ou excluída, com o calculado por '
        'SALDO-01 e lista "<id> <exibido> <calculado>" para cada divergência (SALDO-39). '
        'Não mostra nomes (AD-019).'
    )

    def handle(self, *args, **options):
        divergentes = 0
        for conta in Account.objects.order_by('pk'):
            calculado = calcular(conta)
            if conta.balance != calculado:
                divergentes += 1
                self.stdout.write(f'{conta.pk} {conta.balance} {calculado}')
        self.stdout.write(f'Contas com saldo divergente: {divergentes}')

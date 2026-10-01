from django.core.management.base import BaseCommand
from accounts.models import Account
from django.db import transaction

class Command(BaseCommand):
    help = (
        'Limpa o banco de dados apagando as contas inativas sem nada ligado a elas. '
        'O histórico das contas excluídas e o saldo das contas ativas não mudam (SALDO-47).'
    )

    def handle(self, *args, **options):
        self.stdout.write("--- Limpeza do Banco de Dados ---")

        with transaction.atomic():
            # Só contas inativas sem transações, aportes de meta ou séries:
            # apagar as demais levaria junto o histórico e as pernas de
            # transferência de contas ativas
            inactive_accounts = Account.objects.filter(
                is_active=False,
                transactions__isnull=True,
                goaldeposit__isnull=True,
                recurringtransaction__isnull=True,
            )
            inactive_count = inactive_accounts.count()
            if inactive_count > 0:
                self.stdout.write(f"Apagando {inactive_count} contas inativas sem movimentação...")
                Account.objects.filter(pk__in=list(inactive_accounts.values_list('pk', flat=True))).delete()
            else:
                self.stdout.write("Nenhuma conta inativa sem movimentação encontrada.")

        self.stdout.write(self.style.SUCCESS("Limpeza concluída!"))

from django.core.management.base import BaseCommand
from accounts.models import Account
from transactions.models import Transaction
from django.db import transaction

class Command(BaseCommand):
    help = 'Limpa o banco de dados apagando contas inativas e opcionalmente todas as transações.'

    def add_arguments(self, parser):
        parser.add_argument('--all-transactions', action='store_true', help='Apaga TODAS as transações do sistema')

    def handle(self, *args, **options):
        self.stdout.write("--- Limpeza do Banco de Dados ---")
        
        if options['all_transactions']:
            confirm = input("CUIDADO: Isso apagará TODAS as transações do sistema. Tem certeza? (s/N): ")
            if confirm.lower() != 's':
                self.stdout.write(self.style.WARNING("Operação cancelada."))
                return

        with transaction.atomic():
            # 1. Apagar todas as contas inativas
            inactive_accounts = Account.objects.filter(is_active=False)
            inactive_count = inactive_accounts.count()
            if inactive_count > 0:
                self.stdout.write(f"Apagando {inactive_count} contas inativas (e suas transações)...")
                inactive_accounts.delete()
            else:
                self.stdout.write("Nenhuma conta inativa encontrada.")

            # 2. Apagar transações se solicitado
            if options['all_transactions']:
                transactions = Transaction.objects.all()
                tx_count = transactions.count()
                if tx_count > 0:
                    self.stdout.write(f"Apagando {tx_count} transações existentes...")
                    transactions.delete()
                
                # Resetar saldos das contas ativas
                active_accounts = Account.objects.filter(is_active=True)
                for acc in active_accounts:
                    acc.balance = acc.initial_balance
                    acc.save(update_fields=['balance'])
                self.stdout.write(self.style.SUCCESS("Transações apagadas e saldos resetados."))

        self.stdout.write(self.style.SUCCESS("Limpeza concluída!"))

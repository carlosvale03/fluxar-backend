from django.core.management.base import BaseCommand
from accounts.models import Account
from accounts.services import AccountService
from django.db import transaction

class Command(BaseCommand):
    help = 'Inicializa o saldo calculado (balance) de todas as contas ativas com base no histórico.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Iniciando inicialização de saldos..."))
        
        accounts = Account.objects.filter(is_active=True)
        count = 0
        
        with transaction.atomic():
            for account in accounts:
                # Calcula o saldo usando a lógica dinâmica do AccountService
                current_balance = AccountService.get_balance(account)
                account.balance = current_balance
                account.save(update_fields=['balance'])
                self.stdout.write(f"Conta '{account.name}': Saldo atualizado para {current_balance}")
                count += 1
                
        self.stdout.write(self.style.SUCCESS(f"Sucesso! {count} contas atualizadas."))

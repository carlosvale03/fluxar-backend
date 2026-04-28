from django.core.management.base import BaseCommand
from accounts.models import Account
from django.db.models import Count

class Command(BaseCommand):
    help = 'Audita as contas do sistema, mostrando ativas e inativas.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("--- Auditoria de Contas ---"))
        
        inactive = Account.objects.filter(is_active=False)
        self.stdout.write(f"Contas Inativas: {inactive.count()}")
        for acc in inactive:
            self.stdout.write(f"- [INATIVA] ID: {acc.id} | Nome: {acc.name} | Usuário: {acc.user.email}")
            
        active = Account.objects.filter(is_active=True)
        self.stdout.write(f"\nContas Ativas: {active.count()}")
        for acc in active:
            self.stdout.write(f"- [ATIVA] ID: {acc.id} | Nome: {acc.name} | Usuário: {acc.user.email} | Saldo: {acc.balance}")

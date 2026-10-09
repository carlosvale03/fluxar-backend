from django.core.management.base import BaseCommand
from accounts.models import Account

from api.utils.email_service import _mask_email


class Command(BaseCommand):
    help = 'Audita as contas do sistema, mostrando ativas e inativas.'

    def handle(self, *args, **options):
        # Só o id da conta e o e-mail mascarado do dono, sem nome nem saldo
        # (LGPD-21, LGPD-22)
        self.stdout.write(self.style.SUCCESS("--- Auditoria de Contas ---"))

        inactive = Account.objects.filter(is_active=False).select_related('user')
        self.stdout.write(f"Contas Inativas: {inactive.count()}")
        for acc in inactive:
            self.stdout.write(f"- [INATIVA] ID: {acc.id} | Usuário: {_mask_email(acc.user.email)}")

        active = Account.objects.filter(is_active=True).select_related('user')
        self.stdout.write(f"\nContas Ativas: {active.count()}")
        for acc in active:
            self.stdout.write(f"- [ATIVA] ID: {acc.id} | Usuário: {_mask_email(acc.user.email)}")

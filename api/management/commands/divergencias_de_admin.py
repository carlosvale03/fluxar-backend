"""
Lista as contas em que o papel e o `is_staff` divergem (PERM-29).

O administrador do app é quem tem o papel `ADMIN` (AD-016), e o `is_staff`
serve só para o admin do Django. Depois da implantação, o comando mostra quem
tem `is_staff` sem o papel e quem tem o papel sem `is_staff`, para o
responsável decidir caso a caso. Não altera nenhuma conta. A saída traz o ID e
o e-mail mascarado, nunca o e-mail inteiro (AD-019).
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from api.models import User
from api.utils.email_service import _mask_email


class Command(BaseCommand):
    help = 'Lista as contas em que o papel ADMIN e o is_staff divergem, sem alterar nada.'

    def handle(self, *args, **options):
        divergentes = (
            User.objects
            .filter(Q(is_staff=True) & ~Q(role='ADMIN') | Q(role='ADMIN', is_staff=False))
            .order_by('created_at')
            .values_list('pk', 'email', 'is_staff')
        )
        total = 0
        for pk, email, is_staff in divergentes:
            motivo = 'is_staff sem o papel ADMIN' if is_staff else 'papel ADMIN sem is_staff'
            self.stdout.write(f'{pk} {_mask_email(email)}: {motivo}')
            total += 1
        self.stdout.write(f'Contas divergentes: {total}')

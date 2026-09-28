"""
Lista as contas cujos e-mails só diferem na caixa (AUTH-44).

Não altera nada: essas contas ficam como estão até uma resolução manual. A
saída traz o ID e o e-mail mascarado de cada conta, nunca o e-mail inteiro
(AD-019).
"""
from collections import defaultdict

from django.core.management.base import BaseCommand

from api.models import User
from api.utils.email_service import _mask_email


class Command(BaseCommand):
    help = 'Lista os grupos de contas cujos e-mails só diferem na caixa, sem alterar nada.'

    def handle(self, *args, **options):
        grupos = defaultdict(list)
        for pk, email in User.objects.order_by('created_at').values_list('pk', 'email'):
            grupos[email.lower()].append((pk, email))

        colisoes = [grupos[chave] for chave in sorted(grupos) if len(grupos[chave]) > 1]
        for contas in colisoes:
            self.stdout.write('; '.join(f'{pk} {_mask_email(email)}' for pk, email in contas))

        self.stdout.write(f'Total: {len(colisoes)} grupo(s) com e-mails que só diferem na caixa.')

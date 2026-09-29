"""
Acerta os dados das contas existentes (AUTH-43, AD-035).

- Passa o e-mail para minúsculas quando nenhuma outra conta tem o mesmo
  e-mail em minúsculas. As que colidem ficam como estão até a resolução
  manual (AUTH-44), listadas pelo comando check_email_case.
- Marca como ativas as contas pendentes do modelo antigo
  (email_verified=False e is_active=False).
"""
from collections import defaultdict

from django.db import migrations


def forward(apps, schema_editor):
    User = apps.get_model('api', 'User')

    grupos = defaultdict(list)
    for pk, email in User.objects.values_list('pk', 'email'):
        grupos[email.lower()].append((pk, email))

    for email_minusculo, contas in grupos.items():
        if len(contas) > 1:
            continue
        pk, email = contas[0]
        if email != email_minusculo:
            User.objects.filter(pk=pk).update(email=email_minusculo)

    User.objects.filter(email_verified=False, is_active=False).update(is_active=True)


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0009_nomes_dos_campos_do_usuario'),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]

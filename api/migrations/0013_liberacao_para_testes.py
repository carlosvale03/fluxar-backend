"""
Começa com a liberação para testes ligada (PERM-28).

Grava `testing_unlock = 'true'` só quando a chave não existe, para não
desfazer uma decisão já tomada no painel. Sem nenhuma `TravaDePlano`, todas
as travas ficam liberadas e sem limite nos três planos (AD-044).
"""
from django.db import migrations


def gravar_liberacao(apps, schema_editor):
    GlobalSetting = apps.get_model('api', 'GlobalSetting')
    GlobalSetting.objects.get_or_create(
        key='testing_unlock',
        defaults={
            'value': 'true',
            'description': 'Libera todos os recursos para todos os usuários durante a fase de testes.',
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0012_travadeplano'),
    ]

    operations = [
        migrations.RunPython(gravar_liberacao, migrations.RunPython.noop),
    ]

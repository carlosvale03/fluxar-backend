"""
Desfaz as ligações entre dados de usuários diferentes gravadas antes da
correção e recalcula saldos, faturas e metas afetados (ISOL-17, ISOL-18).
Roda uma vez, no `migrate` do deploy; em banco vazio não encontra nada.
"""
from django.db import migrations

from core.isolation import fix_cross_links


def corrigir(apps, schema_editor):
    fix_cross_links(apps)


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0006_transaction_payment_date'),
        ('accounts', '0004_account_balance'),
        ('budgets', '0001_initial'),
        ('goals', '0007_alter_goal_image'),
        ('reports', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(corrigir, migrations.RunPython.noop),
    ]

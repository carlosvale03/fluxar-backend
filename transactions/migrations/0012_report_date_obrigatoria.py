"""
`report_date` obrigatória e indexada, depois de preenchida pela
`0011_relatorios` (AD-046).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0011_relatorios'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transaction',
            name='report_date',
            field=models.DateField(db_index=True),
        ),
    ]

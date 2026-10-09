"""
Campos dos relatórios (AD-046, spec `relatorios`).

1. `report_date`: a data em que a transação conta nos relatórios. Compra no
   cartão com `purchase_date`: a data da compra mais N-1 meses na parcela N,
   no último dia do mês quando o dia não existe (REL-01, REL-02, AD-006).
   Compra no cartão antiga, sem `purchase_date`, e os demais tipos: a `date`.
   A regra é a mesma de `transactions.models.data_no_relatorio`, repetida
   aqui para a migração não depender do modelo atual.
2. `is_balance_adjustment`: marca os lançamentos antigos do ajuste de saldo
   pela descrição "Ajuste de saldo" (REL-03, REL-05).

Usa os modelos históricos e `dia_no_mes` de `accounts/faturas.py`, que não
importa modelos nem acessa o banco. O campo fica obrigatório na
`0012_report_date_obrigatoria`, numa transação separada da gravação dos dados.
"""
from django.db import migrations, models

from accounts.faturas import dia_no_mes

AJUSTE_DE_SALDO = 'Ajuste de saldo'


def _data_no_relatorio(tipo, data, data_da_compra, numero_da_parcela):
    if tipo != 'CREDIT_CARD' or data_da_compra is None:
        return data
    meses = data_da_compra.month - 1 + (numero_da_parcela or 1) - 1
    return dia_no_mes(data_da_compra.year + meses // 12, meses % 12 + 1, data_da_compra.day)


def preencher(apps, schema_editor):
    Transaction = apps.get_model('transactions', 'Transaction')

    Transaction.objects.exclude(type='CREDIT_CARD', purchase_date__isnull=False).update(
        report_date=models.F('date'),
    )
    compras = Transaction.objects.filter(type='CREDIT_CARD', purchase_date__isnull=False).only(
        'pk', 'type', 'date', 'purchase_date', 'installment_number',
    )
    for compra in compras.iterator():
        report_date = _data_no_relatorio(
            compra.type, compra.date, compra.purchase_date, compra.installment_number,
        )
        Transaction.objects.filter(pk=compra.pk).update(report_date=report_date)

    Transaction.objects.filter(description=AJUSTE_DE_SALDO).update(is_balance_adjustment=True)


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0010_importacao'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='report_date',
            field=models.DateField(null=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='is_balance_adjustment',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(preencher, migrations.RunPython.noop),
    ]

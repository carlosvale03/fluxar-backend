"""
Classes de despesa (AD-025, AD-052, spec `classes-de-despesa`).

Cria `ClasseDeDespesa` e `Category.classe` e implanta as classes para quem
já usa o app (CLASSE-25):

1. cria Essencial e Dispensável para cada usuário;
2. dá a classe inicial de CLASSE-24 às categorias de despesa sem mãe cujo
   nome, sem diferença de maiúsculas e acentos, é o de uma categoria padrão.
   Subcategorias e categorias de receita ficam sem classe própria.

A regra e a lista ficam copiadas aqui para a migração não depender do
código atual de `transactions/padrao.py` nem de `core/texto.py`.
"""
import unicodedata
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

ESSENCIAL = ('Essencial', 'essencial', '#16A34A')
DISPENSAVEL = ('Dispensável', 'dispensavel', '#F97316')

# Nome normalizado da categoria padrão de despesa → classe inicial (CLASSE-24)
CLASSE_INICIAL = {
    'casa': 'essencial',
    'comida': 'essencial',
    'transporte': 'essencial',
    'educacao': 'essencial',
    'lazer': 'dispensavel',
    'eletronicos': 'dispensavel',
    'doces': 'dispensavel',
    'doacao': 'dispensavel',
    'presente': 'dispensavel',
}


def _normalizar(texto):
    if texto is None:
        return ''
    return ''.join(
        c for c in unicodedata.normalize('NFKD', str(texto))
        if not unicodedata.combining(c)
    ).lower().strip()


def implantar(apps, schema_editor):
    User = apps.get_model('api', 'User')
    ClasseDeDespesa = apps.get_model('transactions', 'ClasseDeDespesa')
    Category = apps.get_model('transactions', 'Category')

    for usuario_id in User.objects.values_list('pk', flat=True).iterator():
        classes = {}
        for nome, nome_normalizado, cor in (ESSENCIAL, DISPENSAVEL):
            classe, _ = ClasseDeDespesa.objects.get_or_create(
                user_id=usuario_id, nome_normalizado=nome_normalizado,
                defaults={'nome': nome, 'cor': cor, 'padrao': True},
            )
            classes[nome_normalizado] = classe

        categorias = Category.objects.filter(
            user_id=usuario_id, type='EXPENSE', parent__isnull=True, classe__isnull=True,
        ).only('pk', 'name')
        for categoria in categorias:
            inicial = CLASSE_INICIAL.get(_normalizar(categoria.name))
            if inicial:
                Category.objects.filter(pk=categoria.pk).update(classe=classes[inicial])


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0012_report_date_obrigatoria'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ClasseDeDespesa',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('nome', models.CharField(max_length=30)),
                ('nome_normalizado', models.CharField(max_length=30)),
                ('cor', models.CharField(max_length=7)),
                ('padrao', models.BooleanField(default=False)),
                ('criada_em', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='classes_de_despesa', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='category',
            name='classe',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='categorias', to='transactions.classededespesa'),
        ),
        migrations.AddConstraint(
            model_name='classededespesa',
            constraint=models.UniqueConstraint(fields=('user', 'nome_normalizado'), name='classe_nome_unico_por_usuario'),
        ),
        migrations.RunPython(implantar, migrations.RunPython.noop),
    ]

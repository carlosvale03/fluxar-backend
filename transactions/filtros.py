"""
Filtro de transações da lista e das exportações (CONTRATO-10, CONTRATO-11,
CONTRATO-13, CONTRATO-15, AD-022).

A lista e as duas exportações chamam `filtrar_transacoes`, e os relatórios
usam `TIPOS_DE_DESPESA`: o mesmo filtro tem o mesmo significado nos três.
"""
from uuid import UUID

from rest_framework.exceptions import ValidationError

from core.datas import ler_data

from .models import Category

# "Despesas" inclui as compras no cartão (FIN-25)
TIPOS_DE_DESPESA = ('EXPENSE', 'CREDIT_CARD')
TIPOS_DE_TRANSFERENCIA = ('TRANSFER_OUT', 'TRANSFER_IN')

TIPO_INVALIDO = 'Tipo inválido. Use ALL, INCOME, EXPENSE ou TRANSFER.'
LOTE_INVALIDO = 'Lote de importação inválido.'


def categorias_com_descendentes(usuario, ids):
    """
    Os ids das categorias do usuário em `ids` e de todas as descendentes
    delas, ativas ou não: o histórico pode ter transações de categoria
    inativa. Id de outro usuário ou inexistente fica de fora (ISOL).
    """
    validos = [i for i in ids if _uuid_valido(i)]
    encontradas = set(
        Category.objects.filter(user=usuario, pk__in=validos).values_list('pk', flat=True)
    )
    fronteira = set(encontradas)
    while fronteira:
        filhas = set(
            Category.objects.filter(user=usuario, parent_id__in=fronteira).values_list('pk', flat=True)
        ) - encontradas
        encontradas |= filhas
        fronteira = filhas
    return encontradas


def _uuid_valido(valor):
    try:
        UUID(str(valor))
    except ValueError:
        return False
    return True


def filtrar_transacoes(qs, params, usuario):
    """
    Aplica os filtros de `params` (query params da requisição) sobre `qs`,
    que já vem filtrado pelo usuário.
    """
    account_id = params.get('accountId')
    if account_id and account_id != 'ALL':
        qs = qs.filter(account_id=account_id)
    if params.get('credit_card'):
        qs = qs.filter(credit_card_id=params.get('credit_card'))
    if params.get('invoice'):
        qs = qs.filter(invoice_id=params.get('invoice'))
    month, year = params.get('month'), params.get('year')
    if month and year:
        qs = qs.filter(date__month=month, date__year=year)

    # Datas sem hora (CONTRATO-22)
    if params.get('startDate'):
        qs = qs.filter(date__gte=ler_data(params.get('startDate'), 'startDate'))
    if params.get('endDate'):
        qs = qs.filter(date__lte=ler_data(params.get('endDate'), 'endDate'))

    tipo = params.get('type')
    if tipo and tipo != 'ALL':
        if tipo == 'EXPENSE':
            qs = qs.filter(type__in=TIPOS_DE_DESPESA)
        elif tipo == 'TRANSFER':
            qs = qs.filter(type__in=TIPOS_DE_TRANSFERENCIA)
        elif tipo == 'INCOME':
            qs = qs.filter(type='INCOME')
        else:
            raise ValidationError({'type': [TIPO_INVALIDO]})

    # Várias categorias, com as subcategorias de cada uma (CONTRATO-10, CONTRATO-11)
    categorias = [c for c in params.getlist('categoryId') if c and c != 'ALL']
    if categorias:
        qs = qs.filter(category_id__in=categorias_com_descendentes(usuario, categorias))

    if params.get('search'):
        qs = qs.filter(description__icontains=params.get('search'))

    # Só transações de série recorrente (CONTRATO-15)
    if params.get('is_recurring') == 'true':
        qs = qs.filter(recurring_source__isnull=False)
    if params.get('transfer_id'):
        qs = qs.filter(transfer_id=params.get('transfer_id'))

    # Atalho do resultado da importação para as sugeridas do lote (IMPORT-45)
    lote = params.get('import_batch')
    if lote:
        if not _uuid_valido(lote):
            raise ValidationError({'import_batch': [LOTE_INVALIDO]})
        qs = qs.filter(import_batch=lote)
    if params.get('suggested_category') == 'true':
        qs = qs.filter(categoria_sugerida=True)

    tag_ids = params.getlist('tagIds')
    if tag_ids:
        qs = qs.filter(tags__id__in=tag_ids).distinct()
    return qs

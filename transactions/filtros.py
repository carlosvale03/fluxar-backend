"""
Filtro de transações da lista e das exportações (CONTRATO-10, CONTRATO-11,
CONTRATO-13, CONTRATO-15, AD-022).

A lista e as duas exportações chamam `filtrar_transacoes`, e os relatórios
usam `TIPOS_DE_DESPESA`: o mesmo filtro tem o mesmo significado nos três.
"""
from uuid import UUID

from django.db.models import Q
from rest_framework.exceptions import ValidationError

from core.datas import ler_data

from .classes import SEM_CLASSE, mapa_de_classes
from .models import Category, ClasseDeDespesa

# "Despesas" inclui as compras no cartão (FIN-25)
TIPOS_DE_DESPESA = ('EXPENSE', 'CREDIT_CARD')
TIPOS_DE_TRANSFERENCIA = ('TRANSFER_OUT', 'TRANSFER_IN')

TIPO_INVALIDO = 'Tipo inválido. Use ALL, INCOME, EXPENSE ou TRANSFER.'
LOTE_INVALIDO = 'Lote de importação inválido.'
CLASSE_INVALIDA = 'Classe inválida no filtro: {valor}.'


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


def filtrar_por_classe(qs, valores, usuario):
    """
    Despesas e compras no cartão com classe efetiva entre `valores` (ids de
    classe do usuário) e, com `sem_classe`, as sem classe efetiva ou sem
    categoria (CLASSE-34 a CLASSE-36). Um valor que não é classe do usuário
    nem `sem_classe` recebe 400 (CLASSE-38).
    """
    do_usuario = {
        str(pk) for pk in ClasseDeDespesa.objects.filter(user=usuario).values_list('pk', flat=True)
    }
    pedidas = set()
    sem_classe = False
    for valor in valores:
        if valor == SEM_CLASSE:
            sem_classe = True
        elif _uuid_valido(valor) and str(UUID(str(valor))) in do_usuario:
            pedidas.add(str(UUID(str(valor))))
        else:
            raise ValidationError({'classId': [CLASSE_INVALIDA.format(valor=valor)]})

    mapa = mapa_de_classes(usuario)
    condicao = Q(category_id__in=[
        categoria_id for categoria_id, classe in mapa.items()
        if classe is not None and str(classe.pk) in pedidas
    ])
    if sem_classe:
        # Sem categoria, ou com categoria sem classe efetiva: como "Sem classe"
        # na divisão dos gráficos (CLASSE-28)
        com_classe = [categoria_id for categoria_id, classe in mapa.items() if classe is not None]
        condicao |= Q(category__isnull=True) | ~Q(category_id__in=com_classe)
    return qs.filter(condicao, type__in=TIPOS_DE_DESPESA)


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

    # Várias classes, com `sem_classe`, combinadas por "e" com a categoria (CLASSE-37)
    classes = params.getlist('classId')
    if classes:
        qs = filtrar_por_classe(qs, classes, usuario)

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

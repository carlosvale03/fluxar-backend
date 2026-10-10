"""
Filtro de transações da lista e das exportações (CONTRATO-10, CONTRATO-11,
CONTRATO-13, CONTRATO-15, AD-022).

A lista e as duas exportações chamam `filtrar_transacoes`, e os relatórios
usam `TIPOS_DE_DESPESA`: o mesmo filtro tem o mesmo significado nos três.
"""
from uuid import UUID

from django.db.models import Exists, OuterRef, Q, Sum
from django.db.models.functions import Coalesce
from rest_framework.exceptions import ValidationError

from core.datas import ler_data
from core.valores import ler_valor

from .classes import SEM_CLASSE, mapa_de_classes
from .models import Category, ClasseDeDespesa, Transaction

# "Despesas" inclui as compras no cartão (FIN-25)
TIPOS_DE_DESPESA = ('EXPENSE', 'CREDIT_CARD')
TIPOS_DE_TRANSFERENCIA = ('TRANSFER_OUT', 'TRANSFER_IN')

TIPO_INVALIDO = 'Tipo inválido. Use ALL, INCOME, EXPENSE ou TRANSFER.'
LOTE_INVALIDO = 'Lote de importação inválido.'
CLASSE_INVALIDA = 'Classe inválida no filtro: {valor}.'
TRANSACAO_INVALIDA = 'Transação inválida no filtro: {valor}.'
LIGADAS_INVALIDO = 'Use linked=true para ver só as transações com vínculo.'
VALOR_INVALIDO_NO_FILTRO = 'Valor inválido no filtro: {valor}.'


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

    if params.get('amount'):
        qs = filtrar_por_valor(qs, params.get('amount'), usuario)

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

    qs = filtrar_por_vinculo(qs, params, usuario)

    tag_ids = params.getlist('tagIds')
    if tag_ids:
        qs = qs.filter(tags__id__in=tag_ids).distinct()
    return qs


def filtrar_por_valor(qs, texto, usuario):
    """
    Filtro `amount` (VINCULO-03): o valor no formato da API ("50.00"), lido
    como o `amount` da criação (`ler_valor`); ilegível, zero, negativo ou
    com mais de duas casas recebe 400 no campo.

    Traz as transações com esse valor e as compras parceladas cujo total
    (a soma das parcelas, agrupadas pela raiz) é esse valor; nessas, vêm a
    raiz e todas as parcelas, como no `principalId`. Uma compra parcelada
    também aparece pelo valor de uma parcela.
    """
    try:
        valor = ler_valor(texto)
    except ValidationError:
        raise ValidationError({'amount': [VALOR_INVALIDO_NO_FILTRO.format(valor=texto)]})

    compras = (
        Transaction.objects.filter(user=usuario, is_installment=True)
        .annotate(compra=Coalesce('parent_transaction_id', 'pk'))
        .values('compra')
        .annotate(total=Sum('amount'))
        .filter(total=valor)
        .values('compra')
    )
    return qs.filter(
        Q(amount=valor) | Q(pk__in=compras) | Q(parent_transaction_id__in=compras)
    )


def filtrar_por_vinculo(qs, params, usuario):
    """
    Filtros do vínculo (VINCULO-29, VINCULO-30, VINCULO-32), com as parcelas
    das compras envolvidas:
    - `principalId`: a compra principal e as dependentes dela; id que não é
      de uma transação do usuário recebe 400;
    - `linked=true`: só as transações que são principais ou dependentes;
      outro valor recebe 400.
    Os dois dependem do recurso `vinculos` (VINCULO-20).
    """
    principal = params.get('principalId')
    ligadas = params.get('linked')
    if principal is None and ligadas is None:
        return qs
    from core.travas import exigir_recurso
    exigir_recurso(usuario, 'vinculos')

    if principal is not None:
        alvo = None
        if _uuid_valido(principal):
            alvo = Transaction.objects.filter(user=usuario, pk=principal).values_list(
                'pk', 'parent_transaction_id',
            ).first()
        if alvo is None:
            raise ValidationError({'principalId': [TRANSACAO_INVALIDA.format(valor=principal)]})
        raiz = alvo[1] or alvo[0]
        qs = qs.filter(
            Q(pk=raiz) | Q(parent_transaction_id=raiz)
            | Q(principal_id=raiz) | Q(parent_transaction__principal_id=raiz)
        )

    if ligadas is not None:
        if ligadas != 'true':
            raise ValidationError({'linked': [LIGADAS_INVALIDO]})
        qs = qs.filter(
            Q(principal__isnull=False) | Q(parent_transaction__principal__isnull=False)
            | Q(Exists(Transaction.objects.filter(principal_id=OuterRef('pk'))))
            | Q(Exists(Transaction.objects.filter(principal_id=OuterRef('parent_transaction_id'))))
        )
    return qs

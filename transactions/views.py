from django.db.models import Case, DecimalField, F, Q, Sum, When
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Transaction, Category, Tag, RecurringTransaction
from .serializers import (
    TransactionSerializer, CategorySerializer, TagSerializer,
    TransferSerializer, CreditCardExpenseSerializer,
    TIPOS_DO_ENDPOINT, TIPO_NAO_ALTERAVEL,
)
from .filtros import filtrar_transacoes
from .services import COMPRA_EM_FATURA_PAGA, TransactionService, em_fatura_paga, grupo_da_compra
from core.filtros import PAGINACAO, ParametrosConhecidosMixin
from core.mixins import UserQuerySetMixin
from core.travas import RecursoLiberado, conferir_limite, exigir_recurso
from rest_framework.exceptions import ValidationError
from accounts.models import Account
from accounts.saldo import recalcular
from core.fields import get_owned_or_400, CATEGORIA_NAO_ENCONTRADA, CONTA_NAO_ENCONTRADA
from core.valores import ler_valor

class CategoryViewSet(ParametrosConhecidosMixin, UserQuerySetMixin, viewsets.ModelViewSet):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None  # Remove paginação para retornar árvore completa
    # Parâmetros conhecidos da lista (CONTRATO-14)
    parametros_permitidos = frozenset({'type'})

    def get_queryset(self):
        qs = super().get_queryset()
        
        # Na listagem, retorna apenas as RAÍZES (subcategorias vêm aninhadas pelo serializer)
        if self.action == 'list':
            qs = qs.filter(parent__isnull=True)
        
        # Filtro opcional por tipo
        type_filter = self.request.query_params.get('type')
        if type_filter:
            qs = qs.filter(type=type_filter)
            
        return qs.order_by('name')

    def perform_destroy(self, instance):
        """
        Soft Delete: Apenas marca como inativa para manter histórico e liberar limite.
        """
        instance.is_active = False
        instance.save()

    def create(self, request, *args, **kwargs):
        print(f"DEBUG CREATE CATEGORY PAYLOAD: {request.data}")
        try:
            return super().create(request, *args, **kwargs)
        except Exception as e:
            print(f"DEBUG CREATE CATEGORY ERROR: {e}")
            if hasattr(e, 'detail'):
                print(f"DEBUG ERROR DETAIL: {e.detail}")
            raise e

class TagViewSet(ParametrosConhecidosMixin, UserQuerySetMixin, viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated, RecursoLiberado('tags')]
    
    # get_queryset removido pois o Mixin resolve

    def perform_create(self, serializer):
        conferir_limite(self.request.user, 'limite_tags')
        serializer.save(user=self.request.user)

from core.pagination import PaginacaoPadrao

# Histórico da conta excluída: só leitura (SALDO-36, AD-003)
DE_CONTA_EXCLUIDA = {'detail': 'Esta transação é de uma conta excluída e não pode ser alterada.'}


# Séries recorrentes (SALDO-21, SALDO-22)
SERIE_NAO_ENCONTRADA = 'Série não encontrada.'
SERIE_ENCERRADA = {'detail': 'Esta série foi encerrada e não pode ser alterada.'}


def _envolve_conta_excluida(transacoes):
    """
    Se alguma das transações, ou alguma perna de transferência delas (do mesmo
    usuário), está numa conta excluída.
    """
    filtro = Q()
    for t in transacoes:
        filtro |= Q(pk=t.pk, user_id=t.user_id)
        if t.transfer_id:
            filtro |= Q(transfer_id=t.transfer_id, user_id=t.user_id)
    if not filtro:
        return False
    return Transaction.objects.filter(filtro, account__is_active=False).exists()

# Entradas somam no total do dia; as demais transações subtraem (CONTRATO-09)
TIPOS_DE_ENTRADA = ('INCOME', 'TRANSFER_IN')


def _totais_do_dia(filtradas, datas):
    """
    Para cada data de `datas`, a soma com sinal de todas as transações do
    filtro naquele dia, e não só as da página (CONTRATO-09), como texto com
    duas casas: `{"AAAA-MM-DD": "-123.45"}`.
    """
    if not datas:
        return {}
    linhas = (
        Transaction.objects.filter(pk__in=filtradas.values('pk'), date__in=datas)
        .order_by().values('date')
        .annotate(total=Sum(Case(
            When(type__in=TIPOS_DE_ENTRADA, then=F('amount')),
            default=-F('amount'),
            output_field=DecimalField(max_digits=15, decimal_places=2),
        )))
    )
    return {linha['date'].isoformat(): f"{linha['total']:.2f}" for linha in linhas}


class TransactionViewSet(ParametrosConhecidosMixin, UserQuerySetMixin, viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = PaginacaoPadrao
    # Parâmetros conhecidos da lista (CONTRATO-14)
    parametros_permitidos = PAGINACAO | {
        'accountId', 'credit_card', 'invoice', 'month', 'year', 'startDate', 'endDate',
        'type', 'categoryId', 'tagIds', 'search', 'is_recurring', 'transfer_id',
        'import_batch', 'suggested_category',
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        # O mesmo filtro da exportação (CONTRATO-13), só na lista
        if self.action == 'list':
            queryset = filtrar_transacoes(queryset, self.request.query_params, self.request.user)
        return queryset.order_by('-date', '-created_at')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        resposta = self.get_paginated_response(self.get_serializer(page, many=True).data)
        resposta.data['day_totals'] = _totais_do_dia(queryset, {t.date for t in page})
        return resposta

    def update(self, request, *args, **kwargs):
        # Vale para PUT e PATCH, antes de validar o corpo
        if _envolve_conta_excluida([self.get_object()]):
            return Response(DE_CONTA_EXCLUIDA, status=status.HTTP_400_BAD_REQUEST)
        return super().update(request, *args, **kwargs)

    def perform_create(self, serializer):
        # Lançar como recorrente e lançar com tags dependem do plano (PERM-15)
        if serializer.validated_data.get('is_recurring'):
            exigir_recurso(self.request.user, 'transacoes_recorrentes')
        if serializer.validated_data.get('tags'):
            exigir_recurso(self.request.user, 'tags')
        serializer.save()

    def perform_update(self, serializer):
        # Editar uma ocorrência é essencial; pôr tags depende do plano (PERM-15)
        if serializer.validated_data.get('tags'):
            exigir_recurso(self.request.user, 'tags')
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        transacao = self.get_object()
        if transacao.type == 'CREDIT_CARD':
            return self._excluir_compra(transacao)
        if _envolve_conta_excluida([transacao]):
            return Response(DE_CONTA_EXCLUIDA, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    def _excluir_compra(self, parcela):
        """
        Excluir uma parcela exclui a compra inteira, com todas as parcelas
        (FATURA-20). Se alguma parte está numa fatura paga (FATURA-19) ou numa
        conta excluída (SALDO-36), nada sai. Os totais das faturas seguem os
        signals (FATURA-18).
        """
        grupo = list(grupo_da_compra(parcela))
        if em_fatura_paga(grupo):
            return Response({'detail': COMPRA_EM_FATURA_PAGA}, status=status.HTTP_400_BAD_REQUEST)
        if _envolve_conta_excluida(grupo):
            return Response(DE_CONTA_EXCLUIDA, status=status.HTTP_400_BAD_REQUEST)
        Transaction.objects.filter(pk__in=[p.pk for p in grupo]).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'])
    def transfer(self, request):
        serializer = TransferSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        TransactionService.create_transfer(
            user=request.user,
            account_from=data['account_from'],
            account_to=data['account_to'],
            amount=data['amount'],
            date=data['date'],
            description=data.get('description', 'Transferência')
        )
        return Response({'status': 'Transferência realizada'}, status=status.HTTP_201_CREATED)

    @action(
        detail=False, methods=['post'], url_path='credit-card-expense',
        permission_classes=[permissions.IsAuthenticated, RecursoLiberado('cartoes')],
    )
    def credit_card_expense(self, request):
        serializer = CreditCardExpenseSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        # Parcelar acima de 1x e lançar com tags dependem do plano (PERM-15)
        if data['installments'] > 1:
            exigir_recurso(request.user, 'compras_parceladas')
        if data.get('tags'):
            exigir_recurso(request.user, 'tags')
        
        txs = TransactionService.create_credit_card_expense(
            user=request.user,
            card=data['credit_card'],
            amount=data['amount'],
            date=data['date'],
            description=data['description'],
            category=data['category'],
            tags=data.get('tags'),
            installments=data['installments']
        )
        
        # Serializar retorno (pode ser a primeira transação ou lista)
        return Response(
            TransactionSerializer(txs, many=True).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['delete'], url_path='bulk-delete')
    def bulk_delete(self, request):
        """
        Exclui uma série (as ocorrências pendentes) ou as pernas de uma transferência.
        """
        recurring_id = request.query_params.get('recurring_source')
        transfer_id = request.query_params.get('transfer_id')
        
        if recurring_id:
            # Excluir a série inteira depende do plano; as pernas de uma
            # transferência seguem liberadas (PERM-15)
            exigir_recurso(request.user, 'transacoes_recorrentes')
            # Só as pendentes saem; as efetivadas ficam no histórico e a série
            # é encerrada (SALDO-22)
            serie = get_owned_or_400(
                RecurringTransaction.objects.all(), request.user, recurring_id,
                'recurring_source', SERIE_NAO_ENCONTRADA,
            )
            deleted_count, _ = Transaction.objects.filter(
                user=request.user, recurring_source=serie, status='PENDING',
            ).delete()
            serie.is_active = False
            serie.save(update_fields=['is_active', 'updated_at'])
            return Response({'status': f'{deleted_count} transações removidas.'})
            
        if transfer_id:
            pernas = Transaction.objects.filter(
                user=request.user, 
                transfer_id=transfer_id
            )
            if _envolve_conta_excluida(pernas):
                return Response(DE_CONTA_EXCLUIDA, status=status.HTTP_400_BAD_REQUEST)
            deleted_count, _ = pernas.delete()
            return Response({'status': f'{deleted_count} transações removidas.'})
            
        # Erro no formato do DRF, em português (CONTRATO-29)
        raise ValidationError({'detail': 'Informe recurring_source ou transfer_id.'})

    @action(
        detail=False, methods=['patch'], url_path='bulk-update',
        permission_classes=[permissions.IsAuthenticated, RecursoLiberado('transacoes_recorrentes')],
    )
    def bulk_update(self, request):
        """
        Altera todas as ocorrências de uma série (SALDO-21): descrição, valor,
        categoria, conta e tipo valem só para as pendentes e para o modelo da
        série; as efetivadas ficam como estão.
        """
        recurring_id = request.data.get('recurring_source')
        if not recurring_id:
            raise ValidationError({'recurring_source': ['Este campo é obrigatório.']})
        serie = get_owned_or_400(
            RecurringTransaction.objects.all(), request.user, recurring_id,
            'recurring_source', SERIE_NAO_ENCONTRADA,
        )
        if not serie.is_active:
            return Response(SERIE_ENCERRADA, status=status.HTTP_400_BAD_REQUEST)

        update_data = {
            k: v for k, v in request.data.items()
            if k in ['description', 'amount', 'category', 'account', 'type']
        }

        # Tudo é validado antes de alterar qualquer ocorrência
        if 'amount' in update_data:
            update_data['amount'] = ler_valor(update_data['amount'])
        if update_data.get('category') is not None:
            update_data['category'] = get_owned_or_400(
                Category.objects.all(), request.user, update_data['category'],
                'category', CATEGORIA_NAO_ENCONTRADA,
            )
        if 'account' in update_data:
            update_data['account'] = get_owned_or_400(
                Account.objects.filter(is_active=True), request.user, update_data['account'],
                'account', CONTA_NAO_ENCONTRADA,
            )
        if 'type' in update_data and (
            update_data['type'] not in TIPOS_DO_ENDPOINT or serie.type not in TIPOS_DO_ENDPOINT
        ):
            raise ValidationError({'type': [TIPO_NAO_ALTERAVEL]})

        pendentes = Transaction.objects.filter(
            user=request.user, recurring_source=serie, status='PENDING',
        )
        contas = set(pendentes.values_list('account_id', flat=True))
        updated_count = pendentes.update(**update_data)

        for campo, valor in update_data.items():
            setattr(serie, campo, valor)
        serie.save()

        # Pendentes não mudam o saldo, mas quem usa update() recalcula (AD-038)
        recalcular(*contas, serie.account_id)

        return Response({'status': f'{updated_count} transações atualizadas.'})

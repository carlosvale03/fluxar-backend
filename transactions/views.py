from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Transaction, Category, Tag
from .serializers import (
    TransactionSerializer, CategorySerializer, TagSerializer,
    TransferSerializer, CreditCardExpenseSerializer
)
from .services import TransactionService
from core.mixins import UserQuerySetMixin

class CategoryViewSet(UserQuerySetMixin, viewsets.ModelViewSet):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None  # Remove paginação para retornar árvore completa

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

class TagViewSet(UserQuerySetMixin, viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    # get_queryset removido pois o Mixin resolve

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

from core.pagination import StandardResultsSetPagination

class TransactionViewSet(UserQuerySetMixin, viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtros de Query Params
        account_id = self.request.query_params.get('accountId') or self.request.query_params.get('account')
        card_id = self.request.query_params.get('credit_card')
        month = self.request.query_params.get('month')
        year = self.request.query_params.get('year')
        invoice_id = self.request.query_params.get('invoice')
        
        start_date = self.request.query_params.get('startDate')
        end_date = self.request.query_params.get('endDate')
        transaction_type = self.request.query_params.get('type')
        category_id = self.request.query_params.get('categoryId') or self.request.query_params.get('category')
        search = self.request.query_params.get('search')
        
        if account_id and account_id != 'ALL':
            queryset = queryset.filter(account_id=account_id)
        if card_id:
            queryset = queryset.filter(credit_card_id=card_id)
        if invoice_id:
            queryset = queryset.filter(invoice_id=invoice_id)
        if month and year:
            queryset = queryset.filter(date__month=month, date__year=year)
            
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
            
        if transaction_type and transaction_type != 'ALL':
            if transaction_type == 'EXPENSE':
                queryset = queryset.filter(type__in=['EXPENSE', 'CREDIT_CARD', 'CREDIT_CARD_EXPENSE', 'INVOICE_PAYMENT'])
            elif transaction_type == 'TRANSFER':
                queryset = queryset.filter(type__in=['TRANSFER', 'TRANSFER_OUT', 'TRANSFER_IN'])
            else:
                queryset = queryset.filter(type=transaction_type)
                
        if category_id and category_id != 'ALL':
            queryset = queryset.filter(category_id=category_id)
            
        if search:
            queryset = queryset.filter(description__icontains=search)
            
        # Filtro por Tags (Etiquetas)
        tag_ids = self.request.query_params.getlist('tagIds')
        if tag_ids:
            queryset = queryset.filter(tags__id__in=tag_ids).distinct()
            
        return queryset.order_by('-date', '-created_at')

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

    @action(detail=False, methods=['post'], url_path='credit-card-expense')
    def credit_card_expense(self, request):
        serializer = CreditCardExpenseSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
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
        Deleta todas as transações vinculadas a um grupo de recorrência ou transferência.
        """
        recurring_id = request.query_params.get('recurring_source')
        transfer_id = request.query_params.get('transfer_id')
        
        if recurring_id:
            deleted_count, _ = Transaction.objects.filter(
                user=request.user, 
                recurring_source_id=recurring_id
            ).delete()
            return Response({'status': f'{deleted_count} transações removidas.'})
            
        if transfer_id:
            deleted_count, _ = Transaction.objects.filter(
                user=request.user, 
                transfer_id=transfer_id
            ).delete()
            return Response({'status': f'{deleted_count} transações removidas.'})
            
        return Response({'error': 'Informe recurring_source ou transfer_id'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['patch'], url_path='bulk-update')
    def bulk_update(self, request):
        """
        Atualiza campos (description, amount, category) de um grupo.
        """
        recurring_id = request.data.get('recurring_source')
        if not recurring_id:
            return Response({'error': 'Informe recurring_source'}, status=status.HTTP_400_BAD_REQUEST)
            
        # Filtra apenas transações futuras/pendentes do grupo se solicitado? 
        # Por enquanto faz em todas do grupo.
        update_data = {k: v for k, v in request.data.items() if k in ['description', 'amount', 'category']}
        
        updated_count = Transaction.objects.filter(
            user=request.user,
            recurring_source_id=recurring_id
        ).update(**update_data)
        
        return Response({'status': f'{updated_count} transações atualizadas.'})

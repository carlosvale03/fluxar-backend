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

    def get_queryset(self):
        qs = super().get_queryset()
        
        # Filtro opcional por tipo
        type_filter = self.request.query_params.get('type')
        if type_filter:
            qs = qs.filter(type=type_filter)
            
        return qs.order_by('name')

class TagViewSet(UserQuerySetMixin, viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    # get_queryset removido pois o Mixin resolve

class TransactionViewSet(UserQuerySetMixin, viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None # Remove o limite de 10 itens por página

    def get_queryset(self):
        queryset = super().get_queryset()
        # Filtros básicos (poderiam usar django-filter backend)
        account_id = self.request.query_params.get('account')
        card_id = self.request.query_params.get('credit_card')
        month = self.request.query_params.get('month')
        year = self.request.query_params.get('year')
        
        if account_id:
            queryset = queryset.filter(account_id=account_id)
        if card_id:
            queryset = queryset.filter(credit_card_id=card_id)
        if month and year:
            queryset = queryset.filter(date__month=month, date__year=year)
            
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

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Account, CreditCard, CreditCardInvoice
from .serializers import (
    AccountSerializer, CreditCardSerializer, 
    CreditCardInvoiceSerializer, InvoicePaymentSerializer
)
from .services import AccountService, CreditCardService
from core.mixins import UserQuerySetMixin

class AccountViewSet(UserQuerySetMixin, viewsets.ModelViewSet):
    """
    CRUD de Contas (Checking, Savings, Wallet, Investment).
    """
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_destroy(self, instance):
        # Soft delete
        instance.is_active = False
        instance.save()


class CreditCardViewSet(UserQuerySetMixin, viewsets.ModelViewSet):
    """
    CRUD de Cartões de Crédito.
    """
    queryset = CreditCard.objects.all()
    serializer_class = CreditCardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_destroy(self, instance):
        # Soft delete
        # TODO: Validar se não há faturas abertas com dívida antes de deletar
        instance.is_active = False
        instance.save()

    @action(detail=True, methods=['get'])
    def invoices(self, request, pk=None):
        """
        Lista todas as faturas de um cartão específico.
        """
        card = self.get_object()
        invoices = CreditCardInvoice.objects.filter(card=card).order_by('-year', '-month')
        serializer = CreditCardInvoiceSerializer(invoices, many=True)
        return Response(serializer.data)

class CreditCardInvoiceViewSet(UserQuerySetMixin, viewsets.ModelViewSet):
    """
    Listagem e Ações em Faturas.
    Nota: A listagem geral pode ser filtrada, ou usamos a sub-rota no CreditCardViewSet.
    Aqui servirá principalmente para actions como 'pay'.
    """
    queryset = CreditCardInvoice.objects.all()
    serializer_class = CreditCardInvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options'] # Não permitir delete/put arbitrário por enquanto

    def get_queryset(self):
        # Garante que só vê faturas dos seus cartões
        return CreditCardInvoice.objects.filter(card__user=self.request.user).order_by('-year', '-month')

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status == 'PAID':
            return Response({'error': 'Fatura já está paga.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = InvoicePaymentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        try:
            CreditCardService.pay_invoice(
                user=request.user,
                invoice=invoice,
                account=data['account_id'],
                amount=data['amount'],
                date=data['date']
            )
            return Response({'status': 'Pagamento processado com sucesso.'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def unpay(self, request, pk=None):
        invoice = self.get_object()
        # Validação extra? Se já open? Não tem problema desfazer open (noop)
        
        try:
            CreditCardService.unpay_invoice(request.user, invoice)
            return Response({'status': 'Pagamento estornado. Fatura reaberta.'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

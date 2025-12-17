from rest_framework import viewsets, permissions
from .models import Account, CreditCard
from .serializers import AccountSerializer, CreditCardSerializer

class AccountViewSet(viewsets.ModelViewSet):
    """
    CRUD de Contas (Checking, Savings, Wallet, Investment).
    """
    serializer_class = AccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Tenant Isolation: Apenas contas do próprio usuário
        return Account.objects.filter(user=self.request.user, is_active=True)

    def perform_destroy(self, instance):
        # Soft delete
        instance.is_active = False
        instance.save()


class CreditCardViewSet(viewsets.ModelViewSet):
    """
    CRUD de Cartões de Crédito.
    """
    serializer_class = CreditCardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Tenant Isolation
        return CreditCard.objects.filter(user=self.request.user, is_active=True)

    def perform_destroy(self, instance):
        # Soft delete
        # TODO: Validar se não há faturas abertas com dívida antes de deletar
        instance.is_active = False
        instance.save()

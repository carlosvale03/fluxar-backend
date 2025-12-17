from rest_framework import viewsets, permissions
from .models import Account, CreditCard
from .serializers import AccountSerializer, CreditCardSerializer
from core.mixins import UserQuerySetMixin

class AccountViewSet(UserQuerySetMixin, viewsets.ModelViewSet):
    """
    CRUD de Contas (Checking, Savings, Wallet, Investment).
    """
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    # get_queryset removido (resolvido pelo Mixin)

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

    # get_queryset removido (resolvido pelo Mixin)

    def perform_destroy(self, instance):
        # Soft delete
        # TODO: Validar se não há faturas abertas com dívida antes de deletar
        instance.is_active = False
        instance.save()

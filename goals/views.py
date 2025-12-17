from rest_framework import viewsets, permissions, status, decorators
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Goal
from .serializers import GoalSerializer, GoalDepositSerializer
from .services import GoalService
from core.permissions import IsPremiumPlus
from accounts.models import Account
from core.mixins import UserQuerySetMixin

from decimal import Decimal

class GoalViewSet(UserQuerySetMixin, viewsets.ModelViewSet):
    queryset = Goal.objects.all()
    serializer_class = GoalSerializer
    # Permissão: IsAuthenticated E IsPremiumPlus
    permission_classes = [permissions.IsAuthenticated, IsPremiumPlus]
    
    def get_queryset(self):
        # UserQuerySetMixin já filtra user=self.request.user
        return super().get_queryset()

    @decorators.action(detail=True, methods=['post'])
    def deposit(self, request, pk=None):
        goal = self.get_object()
        
        # Validar dados de entrada manualmente ou usar serializer simples
        amount = request.data.get('amount')
        account_id = request.data.get('account_id')
        date_deposit = request.data.get('date') # Opcional
        
        if not amount or not account_id:
            return Response(
                {'error': 'Campos amount e account_id são obrigatórios.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        account = get_object_or_404(Account, id=account_id, user=request.user)
        
        try:
            GoalService.deposit(goal, account, Decimal(amount), date_deposit)
            # Retornar a meta atualizada
            serializer = self.get_serializer(goal)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

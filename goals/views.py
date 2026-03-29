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
    
    def destroy(self, request, *args, **kwargs):
        """Bloqueia a exclusão se a meta ainda tiver saldo."""
        goal = self.get_object()
        if goal.current_amount != 0:
            return Response(
                {'error': 'Não é possível excluir uma meta com saldo pendente. Resgate o dinheiro primeiro para zerar a meta.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)
    
    def get_queryset(self):
        # UserQuerySetMixin já filtra user=self.request.user
        return super().get_queryset()

    @decorators.action(detail=True, methods=['post'])
    def deposit(self, request, pk=None):
        goal = self.get_object()
        
        # Validar dados de entrada manualmente ou usar serializer simples
        amount = request.data.get('amount')
        account_id = request.data.get('account_id') or request.data.get('account_from')
        date_deposit = request.data.get('date') or request.data.get('datetime') # Opcional
        
        if not amount or not account_id:
            return Response(
                {'error': 'Campos amount e account_id são obrigatórios.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        account = get_object_or_404(Account, id=account_id, user=request.user)
        
        try:
            description = request.data.get('description')
            print(f"DEBUG: Deposit start. Goal={goal.id}, Account={account_id}, Amount={amount}")
            GoalService.deposit(goal, account, Decimal(amount), date_deposit, description)
            # Retornar a meta atualizada
            serializer = self.get_serializer(goal)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"DEBUG: Deposit error: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @decorators.action(detail=True, methods=['post'])
    def withdraw(self, request, pk=None):
        goal = self.get_object()
        
        amount = request.data.get('amount')
        # account_to é para onde o dinheiro sai do cofrinho
        account_id = request.data.get('account_to') or request.data.get('account_id')
        date_withdrawal = request.data.get('date') or request.data.get('datetime')
        
        if not amount or not account_id:
            return Response(
                {'error': 'Campos amount e account_to são obrigatórios.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        account_to = get_object_or_404(Account, id=account_id, user=request.user)
        
        try:
            description = request.data.get('description')
            print(f"DEBUG: Withdraw start. Goal={goal.id}, AccountTo={account_id}, Amount={amount}")
            GoalService.withdraw(goal, account_to, Decimal(amount), date_withdrawal, description)
            
            serializer = self.get_serializer(goal)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"DEBUG: Withdraw error: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @decorators.action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        goal = self.get_object()
        deposits = goal.deposits.all().order_by('-created_at')
        serializer = GoalDepositSerializer(deposits, many=True)
        return Response(serializer.data)

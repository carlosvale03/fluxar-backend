from django.db import transaction as db_transaction
from django.core.exceptions import ValidationError
from datetime import date
from decimal import Decimal
from transactions.services import TransactionService
from .models import Goal, GoalDeposit

class GoalService:
    @staticmethod
    @db_transaction.atomic
    def deposit(goal, account, amount, date_deposit=None):
        """
        Realiza um aporte na meta:
        1. Debita da Conta (cria Transação de Saída/Transferência)
        2. Cria GoalDeposit
        3. Atualiza Goal.current_amount
        """
        if amount <= 0:
            raise ValidationError("O valor do depósito deve ser positivo.")
        
        if account.user != goal.user:
            raise ValidationError("Conta de origem não pertence ao dono da meta.")

        # Data default hoje
        if not date_deposit:
            date_deposit = date.today()

        # 1. Debitar da Conta Origem
        # Vamos criar como uma DESPESA por enquanto, mas ideally seria uma TRANSFERÊNCIA interna
        # Para fluxar v1, tratar como EXPENSE do tipo 'GOAL_DEPOSIT' se existisse o tipo. 
        # Vou usar EXPENSE com descrição clara.
        
        description = f"Aporte na Meta: {goal.name}"
        TransactionService.create_expense(
            user=goal.user,
            account=account,
            amount=amount,
            date=date_deposit,
            description=description,
            category=None # Ou criar categoria 'Investimentos/Metas' auto?
        )
        
        # 2. Criar registro de depósito na Meta
        GoalDeposit.objects.create(
            goal=goal,
            account=account,
            amount=amount,
            date=date_deposit
        )
        
        # 3. Atualizar saldo da Meta
        goal.current_amount += amount
        goal.save()
        
        return goal

    @staticmethod
    def get_progress(goal):
        """
        Retorna dicionário com dados de progresso.
        """
        progress_pct = Decimal(0)
        if goal.target_amount > 0:
            progress_pct = (goal.current_amount / goal.target_amount) * 100
        
        remaining = goal.target_amount - goal.current_amount
        if remaining < 0: remaining = Decimal(0)
        
        suggestion = Decimal(0)
        if goal.target_date and remaining > 0:
            today = date.today()
            # Diferença em meses aproximada
            months = (goal.target_date.year - today.year) * 12 + (goal.target_date.month - today.month)
            if months <= 0: months = 1
            suggestion = remaining / Decimal(months)
            
        return {
            'percentage': round(progress_pct, 1),
            'remaining': remaining,
            'monthly_suggestion': round(suggestion, 2)
        }

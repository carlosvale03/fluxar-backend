from django.db import transaction as db_transaction
from django.core.exceptions import ValidationError
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from transactions.services import TransactionService
from .models import Goal, GoalDeposit

class GoalService:
    @staticmethod
    @db_transaction.atomic
    def deposit(goal, account, amount, date_deposit=None, description=None):
        """
        Realiza um aporte na meta via Transferência:
        1. Cria Transferência entre Conta Origem e Cofrinho da Meta
        2. Cria GoalDeposit (para histórico)
        3. O saldo da meta agora é dinâmico (saldo da conta vinculada)
        """
        if not goal.account:
            raise ValidationError("Esta meta não possui um cofrinho vinculado.")

        if amount <= 0:
            raise ValidationError("O valor do depósito deve ser positivo.")
        
        # Garantir que amount é Decimal
        amount = Decimal(str(amount))

        if account.user != goal.user:
            raise ValidationError("Conta de origem não pertence ao dono da meta.")

        # Garantir que date_deposit é um objeto date
        if isinstance(date_deposit, str):
            from datetime import datetime
            try:
                date_deposit = datetime.strptime(date_deposit, '%Y-%m-%d').date()
            except ValueError:
                date_deposit = date.today()
        elif not date_deposit:
            date_deposit = date.today()

        if not description:
            description = f"Aporte na Meta: {goal.name}"
            
        # 1. Realizar Transferência Real
        # Isso afeta o saldo de ambas as contas.
        transfer_id = TransactionService.create_transfer(
            user=goal.user,
            account_from=account,
            account_to=goal.account,
            amount=amount,
            date=date_deposit,
            description=description
        )
        
        # 2. Criar registro de histórico de depósito na Meta
        GoalDeposit.objects.create(
            goal=goal,
            account=account,
            amount=amount,
            type='DEPOSIT',
            transaction_id=transfer_id,
            description=description,
            date=date_deposit
        )
        
        # O current_amount na Meta serve como um cache do saldo total alocado.
        # Ele é incrementado a cada depósito específico para esta meta.
        goal.current_amount += amount
        goal.save()
        
        return goal

    @staticmethod
    @db_transaction.atomic
    def withdraw(goal, account_to, amount, date_withdrawal=None, description=None):
        """
        Realiza o resgate de dinheiro da meta para uma conta:
        1. Cria Transferência entre Cofrinho da Meta e Conta de Destino
        2. Cria GoalDeposit (tipo WITHDRAWAL para histórico)
        3. O saldo da meta é atualizado (proporcionalmente refletirá a saída)
        """
        if not goal.account:
            raise ValidationError("Esta meta não possui um cofrinho vinculado.")

        if amount <= 0:
            raise ValidationError("O valor do resgate deve ser positivo.")
        
        # Garantir que amount é Decimal
        amount = Decimal(str(amount))

        if account_to.user != goal.user:
            raise ValidationError("Conta de destino não pertence ao dono da meta.")

        # Validar se há saldo suficiente na meta (proporcional)
        progress = GoalService.get_progress(goal)
        if amount > progress['current_amount']:
            raise ValidationError(f"Saldo insuficiente na meta. Disponível: {progress['current_amount']}")

        # Garantir que date_withdrawal é um objeto date
        if isinstance(date_withdrawal, str):
            from datetime import datetime
            try:
                date_withdrawal = datetime.strptime(date_withdrawal, '%Y-%m-%d').date()
            except ValueError:
                date_withdrawal = date.today()
        elif not date_withdrawal:
            date_withdrawal = date.today()

        if not description:
            description = f"Resgate da Meta: {goal.name}"
            
        # 1. Realizar Transferência Real (REVERSA: Cofrinho -> Conta)
        transfer_id = TransactionService.create_transfer(
            user=goal.user,
            account_from=goal.account,
            account_to=account_to,
            amount=amount,
            date=date_withdrawal,
            description=description
        )
        
        # 2. Criar registro de histórico de resgate na Meta
        GoalDeposit.objects.create(
            goal=goal,
            account=account_to,
            amount=amount,
            type='WITHDRAWAL',
            transaction_id=transfer_id,
            description=description,
            date=date_withdrawal
        )
        
        # O current_amount na Meta serve como um cache do saldo total alocado.
        # Ele é decrementado a cada resgate específico desta meta.
        goal.current_amount -= amount
        goal.save()
    @staticmethod
    def get_progress(goal):
        """
        Retorna dicionário com dados de progresso.
        No sistema de Ledger Estrito, confiamos no current_amount salvo na meta,
        que é atualizado permanentemente por cada aporte ou resgate (manual ou automático).
        """
        current_amount = goal.current_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        progress_pct = Decimal('0')
        if goal.target_amount > 0:
            progress_pct = (current_amount / goal.target_amount) * Decimal('100')
        
        remaining = goal.target_amount - current_amount
        if remaining < 0: remaining = Decimal('0')
        
        suggestion = Decimal('0')
        months = 0
        if goal.target_date:
            from datetime import date
            today = date.today()
            months = (goal.target_date.year - today.year) * 12 + (goal.target_date.month - today.month)
            if months <= 0: months = 1
            if remaining > 0:
                suggestion = remaining / Decimal(months)
            
        return {
            'percentage': min(round(progress_pct, 1), Decimal('100.0')),
            'current_amount': current_amount,
            'remaining': remaining,
            'monthly_suggestion': round(suggestion, 2),
            'months_remaining': months
        }

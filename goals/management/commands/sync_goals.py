from django.core.management.base import BaseCommand
from django.db.models import Sum
from decimal import Decimal
from goals.models import Goal, GoalDeposit

class Command(BaseCommand):
    help = 'Sincroniza o saldo total (current_amount) das metas baseado no histórico de transações'

    def handle(self, *args, **options):
        goals = Goal.objects.all()
        self.stdout.write(f'Iniciando sincronização de {goals.count()} metas...')

        for goal in goals:
            # Calcula o saldo histórico líquido: Aportes - Resgates
            deposits = GoalDeposit.objects.filter(goal=goal, type='DEPOSIT').aggregate(
                total=Sum('amount'))['total'] or Decimal('0.00')
            withdrawals = GoalDeposit.objects.filter(goal=goal, type='WITHDRAWAL').aggregate(
                total=Sum('amount'))['total'] or Decimal('0.00')
            
            calculated_balance = deposits - withdrawals
            
            # Garante 2 casas decimais e não permite saldo negativo
            if calculated_balance < 0:
                calculated_balance = Decimal('0.00')
            
            calculated_balance = calculated_balance.quantize(Decimal('0.01'))

            old_balance = goal.current_amount
            goal.current_amount = calculated_balance
            goal.save(update_fields=['current_amount'])

            if old_balance != calculated_balance:
                self.stdout.write(self.style.SUCCESS(
                    f'Meta "{goal.name}": Saldo corrigido de {old_balance} para {calculated_balance}'
                ))
            else:
                self.stdout.write(f'Meta "{goal.name}": Saldo já está correto ({calculated_balance})')

        self.stdout.write(self.style.SUCCESS('Sincronização concluída com sucesso!'))

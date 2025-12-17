from decimal import Decimal
from datetime import date, timedelta
from django.utils import timezone
from .models import Account, CreditCard, CreditCardInvoice

class AccountService:
    @staticmethod
    def get_balance(account: Account) -> Decimal:
        """
        Calcula o saldo atual da conta.
        Por enquanto considera apenas o saldo inicial.
        Futuramente irá somar receitas e subtrair despesas/transferências.
        """
        from django.db.models import Sum
        from transactions.models import Transaction

        balance = account.initial_balance

        # Receitas e Transferências Recebidas (Entradas)
        incomes = Transaction.objects.filter(
            account=account, 
            type__in=['INCOME', 'TRANSFER_IN']
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

        # Despesas, Transferências Enviadas e Pagamento de Fatura (Saídas)
        # Nota: CREDIT_CARD não sai da conta (sai do limite do cartão). Só INVOICE_PAYMENT sai da conta.
        expenses = Transaction.objects.filter(
            account=account,
            type__in=['EXPENSE', 'TRANSFER_OUT', 'INVOICE_PAYMENT']
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

        return balance + incomes - expenses

class CreditCardService:
    @staticmethod
    def get_invoice_data(card: CreditCard):
        """
        Retorna dados da fatura atual e limite disponível.
        """
        # 1. Identificar fatura aberta atual
        # Simulação simples da fatura atual baseada na data de hoje
        # TODO: Implementar lógica real de busca/criação de fatura
        
        current_invoice_total = Decimal('0.00')
        
        # Tenta pegar a fatura aberta atual
        today = timezone.localtime().date()
        current_invoice = card.invoices.filter(
            status='OPEN', 
            month=today.month, 
            year=today.year
        ).first()

        if current_invoice:
            current_invoice_total = current_invoice.total_amount

        available_limit = card.limit - current_invoice_total

        return {
            'current_invoice_total': current_invoice_total,
            'available_limit': available_limit
        }

    @staticmethod
    def get_next_due_date(card: CreditCard) -> date:
        """
        Calcula próxima data de vencimento baseada no dia atual e dia de fechamento.
        """
        today = timezone.localtime().date()
        # Se hoje for antes do fechamento, vence neste mês (se due_day > closing_day) ou no próximo?
        # Lógica simplificada:
        # Se hoje <= closing_day, a fatura desse mês está aberta.
        # Vencimento geralmente é X dias após fechamento. 
        # Aqui, vamos usar apenas o due_day do mês atual ou próximo.
        
        try:
            return date(today.year, today.month, card.due_day)
        except ValueError: # Ex: dia 31 em mês de 30 dias
             return date(today.year, today.month, 28) # Fallback simples

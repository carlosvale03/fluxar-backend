from decimal import Decimal
from django.db.models import Sum
from transactions.models import Transaction

class BudgetService:
    @staticmethod
    def get_budget_usage(budget):
        """
        Calcula o uso do orçamento somando transações de Despesa e Cartão.
        """
        # Filtrar transações
        # Consideramos data da competência (date)
        
        # Filtro de categorias: incluir a categoria do budget E subcategorias?
        # A descrição pede "por categoria de despesa". Geralmente orçamentos são na raiz ou específicos.
        # Se for na raiz, deveria somar as filhas?
        # Para simplificar BD-005 inicial, vamos somar EXATAMENTE a categoria do budget.
        # Se o usuário quiser monitorar pai+filhos, precisariamos de uma logica recursiva ou __in=[ids].
        # Vamos assumir: soma apenas transações vinculadas diretamente a essa categoria (ou vamos incluir filhos?)
        # Decisão: Incluir filhos é mais robusto (se orçamento é "Alimentação", inclui "Restaurante").
        
        relevant_categories = [budget.category.id]
        # Pegar subcategorias (1 nivel)
        relevant_categories += list(budget.category.subcategories.values_list('id', flat=True))

        from django.db.models import Q
        
        # Filtro dual:
        # 1. Para CREDIT_CARD, usamos o mês/ano da FATURA vinculada
        # 2. Para EXPENSE (Dinheiro/PIX), usamos o mês/ano da DATA da transação
        filter_q = (
            Q(type='CREDIT_CARD', invoice__year=budget.year, invoice__month=budget.month) |
            Q(type='EXPENSE', date__year=budget.year, date__month=budget.month)
        )

        queryset = Transaction.objects.filter(
            user=budget.user,
            category__id__in=relevant_categories
        ).filter(filter_q)
        
        total_spent = queryset.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        
        percentage = Decimal('0.00')
        if budget.amount_limit > 0:
            percentage = (total_spent / budget.amount_limit) * 100
            
        # Status
        status = 'OK'
        if percentage >= 100:
            status = 'OVER_LIMIT'
        elif percentage >= 90:
            status = 'NEAR_LIMIT'
            
        return {
            'total_spent': total_spent,
            'percentage_used': round(percentage, 2),
            'status': status
        }

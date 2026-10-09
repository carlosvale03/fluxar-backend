from decimal import Decimal
from reports import regras

class BudgetService:
    @staticmethod
    def get_budget_usage(budget):
        """
        Calcula o uso do orçamento com as mesmas despesas dos relatórios, no
        mês do orçamento: as efetivadas na data delas e as compras no cartão
        na data da compra, cada parcela no mês dela (REL-06, AD-029).
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
        # Pegar subcategorias (1 nivel), só as do dono do orçamento (ISOL-14)
        relevant_categories += list(
            budget.category.subcategories.filter(user_id=budget.user_id).values_list('id', flat=True)
        )

        inicio, fim = regras.limites_do_mes(budget.year, budget.month)
        total_spent = regras.total(
            regras.despesas(budget.user_id, inicio, fim).filter(category__id__in=relevant_categories)
        )
        
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

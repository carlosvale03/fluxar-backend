from decimal import Decimal
from datetime import date, datetime, timedelta
from django.db.models import Sum, Q
from django.db.models.functions import TruncDate
from accounts.models import Account
from transactions.models import Transaction, Category
from budgets.models import Budget
from budgets.services import BudgetService

class ReportService:
    @staticmethod
    def get_dashboard_summary(user):
        """
        Retorna resumo financeiro: Saldo Total, Receita/Despesa Mês, Status Orçamentos.
        """
        today = date.today()
        
        # 1. Total Balance (Soma de contas)
        total_balance = Account.objects.filter(user=user).aggregate(Sum('initial_balance'))['initial_balance__sum'] or Decimal('0.00')
        # TODO: O balance da conta em AccountService é calculado dinamicamente (initial + transactions).
        # Aqui precisamos somar o balanço CALCULADO de cada conta.
        # Iterar sobre contas pode ser lento se forem muitas, mas para um user normal é ok.
        # Alternativa melhor: Fazer query agregada de transações gerais + initial_balance.
        # Por enquanto, vou iterar usando AccountService.get_balance se possível, ou replicar a lógica.
        # Replicando lógica simplificada: Saldo = Sum(Initial) + Sum(Incomes) - Sum(Expenses)
        
        # Vamos pegar o saldo REAL calculado por conta:
        accounts = Account.objects.filter(user=user)
        from accounts.services import AccountService
        total_balance = sum(AccountService.get_balance(acc) for acc in accounts)

        # Fluxo do Mês Atual
        # Usamos a mesma lógica de orçamentos para Consistência:
        # Cartão -> Mês da Fatura | Resto -> Mês da Data
        expense_q = (
            Q(type='CREDIT_CARD', invoice__year=today.year, invoice__month=today.month) |
            Q(type='EXPENSE', date__year=today.year, date__month=today.month)
        )
        
        month_income = Transaction.objects.filter(
            user=user,
            type='INCOME',
            date__year=today.year,
            date__month=today.month
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

        month_expense = Transaction.objects.filter(
            user=user
        ).filter(expense_q).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        
        net_result = month_income - month_expense
        
        # 3. Resumo de Orçamentos
        budgets = Budget.objects.filter(user=user, month=today.month, year=today.year)
        budget_summary = {'OK': 0, 'NEAR_LIMIT': 0, 'OVER_LIMIT': 0}
        
        for b in budgets:
            status = BudgetService.get_budget_usage(b)['status']
            if status in budget_summary:
                budget_summary[status] += 1
                
        return {
            'total_balance': total_balance,
            'current_month': {
                'month': today.month,
                'year': today.year,
                'income': month_income,
                'expense': month_expense,
                'net_result': net_result
            },
            'budgets_status': budget_summary
        }

    @staticmethod
    def get_calendar_data(user, month, year):
        """
        Retorna lista diária de receitas e despesas.
        """
        qs = Transaction.objects.filter(
            user=user,
            date__year=year,
            date__month=month
        ).annotate(day=TruncDate('date')).values('day', 'type').annotate(total=Sum('amount')).order_by('day')
        
        # Transformar em dicionário { 'YYYY-MM-DD': {income: 0, expense: 0} }
        days_data = {}
        for item in qs:
            d_str = item['day'].strftime('%Y-%m-%d')
            if d_str not in days_data:
                days_data[d_str] = {'date': d_str, 'income': Decimal('0.00'), 'expense': Decimal('0.00')}
            
            if item['type'] == 'INCOME':
                days_data[d_str]['income'] += item['total']
            elif item['type'] in ['EXPENSE', 'CREDIT_CARD']:
                days_data[d_str]['expense'] += item['total']
                
        return list(days_data.values())

    @staticmethod
    def get_simple_charts(user, month, year):
        """
        Dados para gráficos: Barras (Por Dia/Semana) e Pizza (Categorias).
        """
        # 1. Pizza de Categorias
        expense_q = (
            Q(type='CREDIT_CARD', invoice__year=year, invoice__month=month) |
            Q(type='EXPENSE', date__year=year, date__month=month)
        )
        
        cat_expenses = Transaction.objects.filter(
            user=user
        ).filter(expense_q).values('category__name').annotate(total=Sum('amount')).order_by('-total')
        
        pie_data = {
            'labels': [],
            'values': []
        }
        for item in cat_expenses:
            name = item['category__name'] or 'Sem Categoria'
            pie_data['labels'].append(name)
            pie_data['values'].append(item['total'])
            
        # 2. Barras (Receita vs Despesa por dia - Reusar logica do calendar?)
        # Sim, o calendar já traz granularidade diária. Podemos retornar isso ou agrupar por semana.
        # Para MVP "Simples Charts", retornar dados diários é suficiente para o front montar barras.
        bar_data = ReportService.get_calendar_data(user, month, year)
        
        return {
            'pie_categories': pie_data,
            'bar_daily': bar_data
        }

    @staticmethod
    def get_advanced_charts(user, period_days=90):
        """
        Premium: Evolução Patrimonial e Heatmap.
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=period_days)
        
        # 1. Evolução Patrimonial (Simplificada: Saldo final do dia)
        # Isso é pesado. Precisamos calcular o saldo acumulado dia a dia.
        # Estratégia: Pegar saldo atual e ir subtraindo voltando no tempo? Ou pegar saldo inicial e somar?
        # Melhor: Pegar Saldo Atual (Total Balance) e iterar transações reversamente para reconstruir histórico.
        
        current_balance = ReportService.get_dashboard_summary(user)['total_balance']
        
        # Transações ordenadas desc (mais recente primeiro)
        transactions = Transaction.objects.filter(
            user=user,
            date__gt=start_date,
            date__lte=end_date
        ).order_by('-date', '-created_at')
        
        # Agrupar por dia
        daily_diffs = {} # dia -> diff saldo
        for t in transactions:
            d = t.date
            # Se income, adicionou ao saldo. Para voltar no tempo, subtraímos.
            if t.type == 'INCOME':
                val = -t.amount
            elif t.type in ['EXPENSE', 'CREDIT_CARD', 'INVOICE_PAYMENT']: # Invoice payment sai da conta
                val = t.amount
            elif t.type == 'TRANSFER_OUT':
                val = t.amount
            elif t.type == 'TRANSFER_IN':
                val = -t.amount
            else:
                val = 0
            
            # Nota: Lógica de cartão de crédito é tricky. Compra (CREDIT_CARD) não sai da conta HOJE, sai no vencimento (INVOICE_PAYMENT).
            # Para "Patrimônio Liquido" (Net Worth), Dívida de Cartão reduz patrimônio. Então Compra reduz patrimônio SIM.
            # E Pagamento de Fatura é Troca de Ativo (Dinheiro) por Passivo (Dívida), efeito zero no Net Worth.
            # VAMOS ASSUMIR NET WORTH para simplificar.
            # Se for Cash Flow (Saldo em Conta), ai Compra Cartão não afeta e Pagamento Fatura afeta.
            # O requisito diz "Evolução do Patrimônio Líquido". Então CREDIT_CARD afeta (-) e INVOICE_PAYMENT é neutro (anula divida com dinheiro).
            
            if t.type == 'CREDIT_CARD':
                # Compra reduz patrimônio
                 daily_diffs[d] = daily_diffs.get(d, 0) + (t.amount) # Na volta, somamos
            elif t.type == 'INVOICE_PAYMENT':
                 # Pagamento reduziu caixa mas reduziu divida. Neutro para patrimônio.
                 pass
            elif t.type == 'EXPENSE':
                 daily_diffs[d] = daily_diffs.get(d, 0) + t.amount
            elif t.type == 'INCOME':
                 daily_diffs[d] = daily_diffs.get(d, 0) - t.amount
            
            # Transferencia interna é neutra para patrimonio global usuario
        
        # Reconstruir série
        evolution = []
        simulated_balance = current_balance
        
        # Iterar de hoje para trás (range de datas)
        curr = end_date
        while curr >= start_date:
            evolution.append({'date': curr, 'balance': simulated_balance})
            diff = daily_diffs.get(curr, 0)
            simulated_balance += diff # Volta no tempo
            curr -= timedelta(days=1)
            
        evolution.reverse() # Ordenar cronológico
        
        return {
            'net_worth_evolution': evolution
        }

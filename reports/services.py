from decimal import Decimal
from datetime import date, datetime, timedelta
from django.db import models
from django.db.models import Sum, Q, Count, Avg, F, Case, When
from django.db.models.functions import TruncDate, TruncMonth, ExtractHour, ExtractWeekDay
from accounts.models import Account, CreditCard
from .models import FocusedMonitorItem
from transactions.models import Transaction, Category, Tag
from budgets.models import Budget
from budgets.services import BudgetService

class ReportService:
    @staticmethod
    def _get_date_range(period_days=None, month=None, year=None):
        """
        Helper para determinar start_date e end_date baseados em period_days ou mes/ano.
        """
        today = date.today()
        
        if period_days:
            # Normalização de strings de período vindas do frontend
            if period_days == 'year' or period_days == 'this_year':
                start_date = date(today.year, 1, 1)
                end_date = today
            elif period_days == 'this_month':
                start_date = date(today.year, today.month, 1)
                end_date = today
            elif period_days == 'last_30_days':
                start_date = today - timedelta(days=30)
                end_date = today
            elif period_days == 'last_90_days':
                start_date = today - timedelta(days=90)
                end_date = today
            elif period_days == 'last_6_months':
                start_date = today - timedelta(days=180)
                end_date = today
            else:
                try:
                    days = int(period_days)
                    start_date = today - timedelta(days=days)
                    end_date = today
                except (ValueError, TypeError):
                    # Fallback para o mês atual se der erro
                    start_date = date(today.year, today.month, 1)
                    end_date = today
            return start_date, end_date
        
        # Lógica padrão de mês/ano
        target_month = int(month) if month else today.month
        target_year = int(year) if year else today.year
        
        start_date = date(target_year, target_month, 1)
        if target_month == 12:
            end_date = date(target_year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(target_year, target_month + 1, 1) - timedelta(days=1)
            
        return start_date, end_date

    @staticmethod
    def get_dashboard_summary(user, month=None, year=None, period_days=None):
        """
        Retorna resumo financeiro sincronizado com o período se fornecido.
        """
        start_date, end_date = ReportService._get_date_range(period_days, month, year)
        today = date.today()
        
        # 1. Total Balance (Status atual, não depende do período para o card de saldo)
        accounts = Account.objects.filter(user=user)
        from accounts.services import AccountService
        total_balance = sum(AccountService.get_balance(acc) for acc in accounts)

        # Fluxo do Período/Mês Selecionado
        # Se for range de dias, usamos apenas a data da transação para simplificar (sem competência de cartão por enquanto no range livre)
        # TODO: Refinar competência de cartão em ranges livres se necessário.
        
        if period_days:
            # Filtro por range de data direto
            expense_q = Q(type__in=['EXPENSE', 'CREDIT_CARD'], date__gte=start_date, date__lte=end_date)
            income_base_q = Q(type='INCOME', date__gte=start_date, date__lte=end_date)
            # Para range livre, ignoramos a regra de 'mês da fatura' para cartões para ser mais intuitivo
        else:
            # Lógica tradicional de mês/ano com competência de fatura
            expense_q = (
                Q(type='CREDIT_CARD', invoice__year=start_date.year, invoice__month=start_date.month) |
                Q(type='EXPENSE', date__year=start_date.year, date__month=start_date.month)
            )
            income_base_q = Q(type='INCOME', date__year=start_date.year, date__month=start_date.month)

        expense_q &= ~Q(type__in=['INVOICE_PAYMENT', 'TRANSFER_OUT', 'TRANSFER_IN'])
        
        month_income = Transaction.objects.filter(
            user=user
        ).filter(income_base_q).exclude(
            account__type='INVESTMENT'
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

        month_expense = Transaction.objects.filter(
            user=user
        ).filter(expense_q).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        
        net_result = month_income - month_expense
        
        # 3. Resumo de Orçamentos (Sempre mês atual para o Dashboard padrão, ou proporcional se period)
        # Por enquanto mantemos a lógica do mês da 'start_date'
        budgets = Budget.objects.filter(user=user, month=start_date.month, year=start_date.year)
        budget_summary = {'OK': 0, 'NEAR_LIMIT': 0, 'OVER_LIMIT': 0}
        
        for b in budgets:
            status = BudgetService.get_budget_usage(b)['status']
            if status in budget_summary:
                budget_summary[status] += 1

        # 4. Resumo de Cartões de Crédito (Status atual)
        credit_cards = CreditCard.objects.filter(user=user, is_active=True)
        total_credit_limit = Decimal('0.00')
        total_current_invoices = Decimal('0.00')
        card_details = []

        for card in credit_cards:
            total_credit_limit += card.limit
            
            # 1. Dados para o KPI (Respeitam o Período)
            invoice_period = card.invoices.filter(month=end_date.month, year=end_date.year).first()
            total_current_invoices += invoice_period.total_amount if invoice_period else Decimal('0.00')

            # 2. Dados para Gestão de Crédito (Sempre Real-time/Hoje)
            invoice_now = card.invoices.filter(month=today.month, year=today.year).first()
            invoice_amount_now = invoice_now.total_amount if invoice_now else Decimal('0.00')

            card_details.append({
                'id': str(card.id),
                'name': card.name,
                'limit': card.limit,
                'current_invoice': invoice_amount_now, # Real-time
                'available_limit': card.limit - invoice_amount_now, # Real-time
                'color': card.color or '#CBD5E1',
                'institution': card.institution,
                'due_day': card.due_day
            })
                
        # 5. Métricas de Saúde Financeira (Agora sincronizadas com o range)
        health_metrics = ReportService.get_financial_health_metrics(
            user, month_income, month_expense, 
            start_date=start_date, end_date=end_date
        )

        return {
            'summary': {
                'total_balance': total_balance,
                'monthly_income': month_income,
                'monthly_expense': month_expense,
                'net_result': net_result,
                'total_credit_limit': total_credit_limit,
                'total_current_invoices': total_current_invoices,
                'net_worth': total_balance - total_current_invoices,
                'savings_rate': health_metrics['savings_rate'],
                'total_liquid_balance': health_metrics['total_liquid_balance'],
                'total_investment_balance': health_metrics['total_investment_balance'],
                'liquidity_ratio': health_metrics['liquidity_ratio'],
                'financial_score': health_metrics['financial_score'],
            },
            'budgets': {
                'ok_count': budget_summary['OK'],
                'near_limit_count': budget_summary['NEAR_LIMIT'],
                'over_limit_count': budget_summary['OVER_LIMIT']
            },
            'credit_cards': card_details,
            'goals': None
        }

    @staticmethod
    def _get_expected_income(user, target_month, target_year, end_date=None):
        """
        Retorna a renda esperada: Renda do mês atual ou média dos últimos 3 meses.
        """
        if not end_date:
            end_date = date(target_year, target_month, 1) # Simplificação para retrocompatibilidade
            # Se for o mês atual real, usamos a data de hoje para o range de média
            if target_month == date.today().month and target_year == date.today().year:
                end_date = date.today()

        current_income = Transaction.objects.filter(
            user=user, type='INCOME'
        ).exclude(
            Q(type__in=['TRANSFER_IN', 'TRANSFER_OUT']) | Q(account__type='INVESTMENT')
        ).filter(date__year=target_year, date__month=target_month).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        if current_income > 0:
            return current_income

        # Se não teve renda este mês ainda, pegamos a média dos últimos 3 meses
        income_avgs = Transaction.objects.filter(
            user=user, type='INCOME', 
            date__gt=end_date - timedelta(days=90)
        ).exclude(
            account__type='INVESTMENT'
        ).annotate(m=TruncMonth('date')).values('m').annotate(total=Sum('amount'))
        
        if income_avgs:
            return sum(m['total'] for m in income_avgs) / len(income_avgs)
        
        return Decimal('0.00')

    @staticmethod
    def get_financial_health_metrics(user, monthly_income, monthly_expense, month=None, year=None, start_date=None, end_date=None):
        """
        Calcula indicadores de saúde financeira baseados em Tipos de Conta e Período.
        """
        if not start_date or not end_date:
            today = date.today()
            target_month = month or today.month
            target_year = year or today.year
            start_date = date(target_year, target_month, 1)
            # Para o mês atual, o end_date é hoje para refletir o "até agora"
            if target_month == today.month and target_year == today.year:
                end_date = today
            else:
                if target_month == 12:
                    end_date = date(target_year + 1, 1, 1) - timedelta(days=1)
                else:
                    end_date = date(target_year, target_month + 1, 1) - timedelta(days=1)

        # 1. Separação de Balanços (Líquido vs Investimento)
        accounts = Account.objects.filter(user=user, is_active=True)
        from accounts.services import AccountService
        
        liquid_accounts = accounts.filter(type__in=['CHECKING', 'SAVINGS', 'WALLET'])
        investment_accounts = accounts.filter(type='INVESTMENT')
        
        total_liquid_balance = Decimal(str(sum(AccountService.get_balance(acc) for acc in liquid_accounts)))
        total_investment_balance = Decimal(str(sum(AccountService.get_balance(acc) for acc in investment_accounts)))

        # 2. Poder de Aporte (Savings Rate) - DINHEIRO NOVO (Capital Injection)
        # Consideramos apenas TRANSFER_IN para contas de investimento.
        # Excluímos INCOME (seriam dividendos/rendimentos, não 'aporte' de capital novo).
        # Excluímos também transferências internas entre contas de investimento (realaocação).
        
        internal_transfer_ids = Transaction.objects.filter(
            user=user, account__type='INVESTMENT', type='TRANSFER_OUT'
        ).values_list('transfer_id', flat=True)

        investment_inflows = Transaction.objects.filter(
            user=user,
            account__type='INVESTMENT',
            type='TRANSFER_IN',
            date__gte=start_date,
            date__lte=end_date
        ).exclude(
            transfer_id__in=internal_transfer_ids
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

        savings_rate = Decimal('0.00')
        # Se não há renda no período, usamos a renda esperada (média histórica mensal)
        income_for_calc = monthly_income if monthly_income and monthly_income > 0 else ReportService._get_expected_income(user, start_date.month, start_date.year, end_date=end_date)
        
        if income_for_calc > 0:
            savings_rate = (investment_inflows / income_for_calc) * 100
        
        # 3. Liquidity Ratio (Meses de reserva baseados em liquidez imediata)
        liquidity_ratio = Decimal('0.00')
        if monthly_expense > 0:
            # Para range diferente de um mês, normalizamos a despesa para base mensal (30 dias)
            days = (end_date - start_date).days or 1
            if days < 25: # Se for um mês normal ou menos
                 liquidity_ratio = total_liquid_balance / Decimal(str(monthly_expense))
            else:
                avg_monthly_expense = (monthly_expense / Decimal(str(days))) * 30
                liquidity_ratio = total_liquid_balance / avg_monthly_expense
        
        # 4. Score de Saúde (0-100)
        # Pontuação baseada em:
        # - Savings Rate (40%): >20% é ideal
        # - Meses de Reserva (40%): >6 meses é ideal
        # - Orçamentos estourados (20%): 0 é ideal
        
        score = 0
        # Savings Rate component (max 40)
        score += min(max(savings_rate * 2, Decimal('0')), Decimal('40'))
        
        # Liquidity component (max 40)
        score += min(liquidity_ratio * 6, Decimal('40')) # 6.6 meses = 40 pontos
        
        # Budget component (max 20)
        today = date.today()
        over_limit_budgets = Budget.objects.filter(
            user=user, 
            month=today.month, 
            year=today.year
        ).count() # TODO: Improve count by checking usage status
        
        score += max(Decimal('20') - (Decimal(str(over_limit_budgets)) * 5), Decimal('0'))

        return {
            'savings_rate': float(savings_rate.quantize(Decimal('0.01'))),
            'total_liquid_balance': float(total_liquid_balance),
            'total_investment_balance': float(total_investment_balance),
            'liquidity_ratio': float(liquidity_ratio.quantize(Decimal('0.01'))),
            'financial_score': int(score)
        }

    @staticmethod
    def get_calendar_data(user, month=None, year=None, period_days=None):
        """
        Retorna lista diária de receitas e despesas. Respeita o período se fornecido.
        """
        start_date, end_date = ReportService._get_date_range(period_days, month, year)
        
        qs = Transaction.objects.filter(
            user=user,
            date__gte=start_date,
            date__lte=end_date
        ).annotate(day=TruncDate('date')).values('day', 'type').annotate(total=Sum('amount')).order_by('day')
        
        # 1. Agrupar por dia e tipo
        raw_days = {}
        for item in qs:
            d_str = item['day'].strftime('%Y-%m-%d')
            if d_str not in raw_days:
                raw_days[d_str] = {'income': Decimal('0.00'), 'expense': Decimal('0.00')}
            
            if item['type'] == 'INCOME':
                raw_days[d_str]['income'] += item['total']
            elif item['type'] in ['EXPENSE', 'CREDIT_CARD']:
                raw_days[d_str]['expense'] += item['total']
        
        # 2. Transformar em formato esperado pelo Frontend
        days_list = []
        total_period_income = Decimal('0.00')
        total_period_expense = Decimal('0.00')

        for d_str, data in raw_days.items():
            income = data['income']
            expense = data['expense']
            net = income - expense
            
            days_list.append({
                'date': d_str,
                'total_incomes': income,
                'total_expenses': expense,
                'net_amount': net,
                'is_positive': net >= 0
            })
            
            total_period_income += income
            total_period_expense += expense
                
        return {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'days': days_list,
                'total_income': total_period_income,
            'total_expense': total_period_expense
        }

    @staticmethod
    def get_simple_charts(user, month=None, year=None, period_days=None):
        """
        Dados para gráficos: Barras (Por Dia/Semana/Mês) e Pizza (Categorias).
        """
        start_date, end_date = ReportService._get_date_range(period_days, month, year)
        
        # 1. Pizza de Categorias
        expense_q = Q(date__gte=start_date, date__lte=end_date)
        expense_q &= ~Q(type__in=['INVOICE_PAYMENT', 'TRANSFER_OUT', 'TRANSFER_IN'])
        # Inclui Despesas e Cartão de Crédito
        expense_q &= Q(type__in=['EXPENSE', 'CREDIT_CARD'])
        
        # 2. Barras (Receita vs Despesa) - SEMPRE DIÁRIO conforme pedido do usuário
        # Agrupamento diário padrão (via get_calendar_data) para manter o Fluxo de Caixa Diário detalhado
        bar_data = ReportService.get_calendar_data(user, month, year, period_days)
        income_vs_expense = []
        for d in bar_data['days']:
            income_vs_expense.append({
                'label': datetime.strptime(d['date'], '%Y-%m-%d').strftime('%d'),
                'full_date': d['date'], # Adicionando a data completa para facilitar o filtro mensal no frontend
                'income': float(d['total_incomes']),
                'expense': float(d['total_expenses'])
            })
            
        from django.db.models.functions import Coalesce
        from django.db.models import F

        # 1. Agregação de Despesas
        expense_by_category = []
        full_cat_expenses = Transaction.objects.filter(
            user=user
        ).filter(expense_q).annotate(
            effective_name=Coalesce(F('category__parent__name'), F('category__name')),
            effective_color=Coalesce(F('category__parent__color'), F('category__color'))
        ).values('effective_name', 'effective_color').annotate(total=Sum('amount')).order_by('-total')

        for item in full_cat_expenses:
            expense_by_category.append({
                'category_name': item['effective_name'] or 'Sem Categoria',
                'amount': float(item['total']),
                'color': item['effective_color'] or '#CBD5E1'
            })

        # 2. Agregação de Receitas
        income_q = Q(type='INCOME', date__gte=start_date, date__lte=end_date)
        
        income_by_category = []
        full_cat_incomes = Transaction.objects.filter(
            user=user
        ).filter(income_q).annotate(
            effective_name=Coalesce(F('category__parent__name'), F('category__name')),
            effective_color=Coalesce(F('category__parent__color'), F('category__color'))
        ).values('effective_name', 'effective_color').annotate(total=Sum('amount')).order_by('-total')

        for item in full_cat_incomes:
            income_by_category.append({
                'category_name': item['effective_name'] or 'Sem Categoria',
                'amount': float(item['total']),
                'color': item['effective_color'] or '#CBD5E1'
            })

        return {
            'income_vs_expense': income_vs_expense,
            'expense_by_category': expense_by_category,
            'income_by_category': income_by_category,
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d')
            }
        }

    @staticmethod
    def get_advanced_charts(user, period_days=90):
        """
        Premium: Evolução Patrimonial, Inteligência de Investimentos, Heatmap e Monitoramento.
        """
        from django.db.models.functions import ExtractHour, ExtractWeekDay
        
        end_date = date.today()
        start_date = end_date - timedelta(days=period_days)
        
        # 1. Evolução Patrimonial (Net Worth)
        summary_res = ReportService.get_dashboard_summary(user)
        current_balance = summary_res['summary']['total_balance']
        
        transactions = Transaction.objects.filter(
            user=user,
            date__gt=start_date,
            date__lte=end_date
        ).exclude(
            type__in=['INVOICE_PAYMENT', 'TRANSFER_OUT', 'TRANSFER_IN']
        ).order_by('-date', '-created_at')
        
        daily_diffs = {}
        for t in transactions:
            d = t.date
            if t.type in ['EXPENSE', 'CREDIT_CARD']:
                 daily_diffs[d] = daily_diffs.get(d, 0) + t.amount
            elif t.type == 'INCOME':
                 daily_diffs[d] = daily_diffs.get(d, 0) - t.amount
        
        evolution = []
        simulated_balance = current_balance
        curr = end_date
        while curr >= start_date:
            evolution.append({'date': curr.strftime('%Y-%m-%d'), 'balance': float(simulated_balance)})
            diff = daily_diffs.get(curr, 0)
            simulated_balance += diff
            curr -= timedelta(days=1)
        evolution.reverse()

        # 2. Frequência de Gastos (Heatmap)
        # Extraímos dia da semana (1=Dom, 2=Seg...) e hora do created_at
        frequency_qs = Transaction.objects.filter(
            user=user,
            type__in=['EXPENSE', 'CREDIT_CARD'],
            date__gt=start_date
        ).exclude(
            type__in=['INVOICE_PAYMENT', 'TRANSFER_OUT', 'TRANSFER_IN']
        ).annotate(
            hour=ExtractHour('created_at'),
            day_of_week=ExtractWeekDay('date') # Use compentency date for day of week
        ).values('day_of_week', 'hour').annotate(count=Count('id')).order_by('day_of_week', 'hour')

        spending_frequency = []
        for item in frequency_qs:
            # Recharts espera day_of_week 0-6 (Seg-Dom) ou 1-7
            # ExtractWeekDay: 1 (Sunday) to 7 (Saturday)
            # Vamos converter 1->6 (Dom), 2->0 (Seg)... para ficar intuitivo no gráfico se necessário
            # Mas vamos manter o valor puro e o front decide ou rotulamos:
            spending_frequency.append({
                'day_of_week': item['day_of_week'],
                'hour_of_day': item['hour'],
                'count': item['count']
            })

        # 3. Inteligência de Investimentos (Baseada em Tipo de Conta)
        investment_accounts = Account.objects.filter(user=user, type='INVESTMENT', is_active=True)
        has_investments = investment_accounts.exists()
        
        investment_data = {
            'has_investments_account': has_investments,
            'total_invested': 0.0,
            'monthly_history': [],
            'asset_allocation': []
        }

        if has_investments:
            # 1. Patrimônio em Investimentos
            from accounts.services import AccountService
            total_invested = sum(AccountService.get_balance(acc) for acc in investment_accounts)
            
            # 2. Histórico Mensal (Últimos 6 meses)
            monthly_history = []
            for i in range(5, -1, -1):
                target_date = end_date - timedelta(days=i*30)
                m_start = target_date.replace(day=1)
                if m_start.month == 12:
                    m_end = m_start.replace(year=m_start.year + 1, month=1, day=1) - timedelta(days=1)
                else:
                    m_end = m_start.replace(month=m_start.month + 1, day=1) - timedelta(days=1)
                
                # Aportes (Transfers IN para investimentos, excluindo rebalanceamento interno)
                internal_ids = Transaction.objects.filter(
                    user=user, account__type='INVESTMENT', type='TRANSFER_OUT'
                ).values_list('transfer_id', flat=True)

                m_aportes = Transaction.objects.filter(
                    user=user, account__type='INVESTMENT', type='TRANSFER_IN',
                    date__gte=m_start, date__lte=m_end
                ).exclude(
                    transfer_id__in=internal_ids
                ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

                # Resgates (Transfers OUT de investimentos)
                m_resgates = Transaction.objects.filter(
                    user=user, account__type='INVESTMENT', type='TRANSFER_OUT',
                    date__gte=m_start, date__lte=m_end
                ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

                monthly_history.append({
                    'month': m_start.strftime('%b/%y'),
                    'contribution': float(m_aportes),
                    'returns': float(m_resgates),
                })

            # Alocação (Saldos por Conta de Investimento)
            asset_allocation = []
            colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']
            for i, acc in enumerate(investment_accounts):
                balance = AccountService.get_balance(acc)
                if balance > 0:
                    asset_allocation.append({
                        'name': acc.name,
                        'value': float(balance),
                        'color': colors[i % len(colors)]
                    })

            investment_data.update({
                'total_invested': float(total_invested),
                'monthly_history': monthly_history,
                'asset_allocation': asset_allocation
            })

        # 4. Monitoramento Customizado (Foco Manual)
        items = FocusedMonitorItem.objects.filter(user=user)
        
        custom_monitoring = []
        for item in items:
            name = item.category.name if item.category else item.tag.name
            
            # Se for categoria, buscamos ela e todas as subcategorias recursivamente
            if item.category:
                def get_all_child_categories(cat_id):
                    all_ids = [cat_id]
                    children = Category.objects.filter(parent_id=cat_id).values_list('id', flat=True)
                    for child_id in children:
                        all_ids.extend(get_all_child_categories(child_id))
                    return all_ids
                
                category_ids = get_all_child_categories(item.category_id)
                target_filter = Q(category_id__in=category_ids)
            else:
                target_filter = Q(tags__id=item.tag_id)
            
            # Base de transações - Excluindo transações técnicas (Transferências/Pagamentos)
            base_qs = Transaction.objects.filter(user=user).filter(target_filter).exclude(
                type__in=['INVOICE_PAYMENT', 'TRANSFER_OUT', 'TRANSFER_IN']
            ).distinct()
            
            # Filtro de Consumo + Reembolsos (Income na mesma categoria)
            # Cartão -> Competência da Fatura | Resto (Despesa/Receita) -> Competência da Data
            consumption_q = (
                Q(type='CREDIT_CARD', invoice__year=end_date.year, invoice__month=end_date.month) |
                Q(type='EXPENSE', date__year=end_date.year, date__month=end_date.month) |
                Q(type='INCOME', date__year=end_date.year, date__month=end_date.month)
            )

            # Gasto mês atual (Líquido: Despesas - Receitas/Reembolsos)
            current_month_total = base_qs.filter(consumption_q).aggregate(
                total=Sum(
                    Case(
                        When(type='INCOME', then=-F('amount')),
                        default=F('amount'),
                        output_field=models.DecimalField()
                    )
                )
            )['total'] or Decimal('0.00')
            
            # Gasto total nos últimos 6 meses (Líquido)
            six_months_ago = end_date - timedelta(days=180)
            history_qs = base_qs.filter(date__gt=six_months_ago)
            
            total_6_months = history_qs.aggregate(
                total=Sum(
                    Case(
                        When(type='INCOME', then=-F('amount')),
                        default=F('amount'),
                        output_field=models.DecimalField()
                    )
                )
            )['total'] or Decimal('0.00')
            
            # Calculamos a média baseada apenas nos meses que tiveram movimentação (máx 6)
            months_count = history_qs.annotate(m=TruncMonth('date')).values('m').distinct().count()
            
            divisor = max(1, months_count)
            average = total_6_months / divisor
            
            # Ajuste de status: 'success' | 'warning' | 'error'
            status = 'success'
            if average > 0:
                if current_month_total > average * Decimal('1.2'): status = 'warning'
                if current_month_total > average * Decimal('1.5'): status = 'error'
            elif current_month_total > 0:
                # Se não tem média mas tem gasto agora, marcamos como atenção (item novo ou recorrente)
                status = 'warning'

            custom_monitoring.append({
                'id': str(item.id),
                'name': name,
                'type': 'category' if item.category else 'tag',
                'icon': item.category.icon if item.category else None,
                'color': item.category.color if item.category else item.tag.color,
                'current_month': float(current_month_total),
                'average_month': float(average),
                'status': status
            })

        # 5. Próximo Grande Gasto (Predição Inteligente)
        # A. Média Inteligente (apenas meses com movimentação)
        six_months_ago = end_date - timedelta(days=180)
        # Query de meses com gasto (agrupado por mês)
        month_totals = Transaction.objects.filter(
            user=user, type__in=['EXPENSE', 'CREDIT_CARD'],
            date__gt=six_months_ago, date__lte=end_date
        ).exclude(
            type__in=['INVOICE_PAYMENT', 'TRANSFER_OUT', 'TRANSFER_IN']
        ).annotate(m=TruncMonth('date')).values('m').annotate(total=Sum('amount'))
        
        non_zero_months = [m['total'] for m in month_totals if m['total'] > 0]
        avg_monthly_exp = sum(non_zero_months) / len(non_zero_months) if non_zero_months else Decimal('0.00')
        
        # Média por transação (para definir o que é "grande")
        avg_txn = Transaction.objects.filter(
            user=user, type__in=['EXPENSE', 'CREDIT_CARD']
        ).exclude(
            type__in=['INVOICE_PAYMENT', 'TRANSFER_OUT', 'TRANSFER_IN']
        ).aggregate(Avg('amount'))['amount__avg'] or Decimal('0.00')
        avg_txn = Decimal(str(avg_txn))

        # Pool de Candidatos (Data de Projeção -> {amount, items})
        candidates = {} # d_str -> {'amount': Decimal, 'desc': [str]}

        # B. Transações Agendadas no Futuro (Próximos 45 dias)
        future_txns = Transaction.objects.filter(
            user=user, date__gt=end_date,
            date__lte=end_date + timedelta(days=45),
            status='PENDING',
            amount__gt=avg_txn * Decimal('1.2')
        ).select_related('category')

        for t in future_txns:
            d_str = t.date.strftime('%Y-%m-%d')
            if d_str not in candidates: candidates[d_str] = {'amount': Decimal('0'), 'desc': []}
            candidates[d_str]['amount'] += t.amount
            candidates[d_str]['desc'].append(t.category.name if t.category else 'Geral')

        # C. Detecção de Padrões (Recorrência de 3 meses / Janela 5 dias)
        three_months_ago = end_date - timedelta(days=90)
        history = Transaction.objects.filter(
            user=user, type__in=['EXPENSE', 'CREDIT_CARD'],
            date__gt=three_months_ago, date__lte=end_date
        ).exclude(
            type__in=['INVOICE_PAYMENT', 'TRANSFER_OUT', 'TRANSFER_IN']
        ).select_related('category')

        # Agrupar por categoria -> { (year, month) -> [ (day, amount) ] }
        cat_months = {}
        for h in history:
            cat_id = h.category_id or "root"
            m_key = (h.date.year, h.date.month)
            if cat_id not in cat_months: cat_months[cat_id] = {}
            if m_key not in cat_months[cat_id]: cat_months[cat_id][m_key] = []
            cat_months[cat_id][m_key].append({'day': h.date.day, 'amount': h.amount})

        # Analisar padrões em cada categoria
        for cat_id, months in cat_months.items():
            if len(months) < 2: continue # Precisa de pelo menos 2 meses de dados
            
            # Pegar o dia médio e valor médio de cada mês
            month_pikes = []
            for m_key, txns in months.items():
                # Em um mês, pegamos o maior gasto dessa categoria (como "Aluguel" ou "Escola")
                peak = max(txns, key=lambda x: x['amount'])
                month_pikes.append(peak)

            days = [p['day'] for p in month_pikes]
            avg_val = sum(p['amount'] for p in month_pikes) / len(month_pikes)
            
            # Se a variação entre os dias for pequena (janela de 5 dias)
            if max(days) - min(days) <= 5 and avg_val > avg_txn * Decimal('1.2'):
                # Projetar para o próximo mês (mesma data média)
                proj_day = int(sum(days) / len(days))
                
                # Gerar data no próximo mês
                target_month = end_date.month + 1 if end_date.month < 12 else 1
                target_year = end_date.year if end_date.month < 12 else end_date.year + 1
                try:
                    proj_date = date(target_year, target_month, min(proj_day, 28)) # Seguro contra fev
                    if proj_date > end_date:
                        d_str = proj_date.strftime('%Y-%m-%d')
                        if d_str not in candidates: candidates[d_str] = {'amount': Decimal('0'), 'desc': []}
                        
                        # Evitar duplicar se já houver agendado
                        if not any(cat_id == t.category_id for t in future_txns if t.date == proj_date):
                            candidates[d_str]['amount'] += avg_val
                            cat_obj = Category.objects.filter(id=cat_id).first() if cat_id != "root" else None
                            candidates[d_str]['desc'].append(cat_obj.name if cat_obj else 'Geral')
                except ValueError: pass

        # D. Faturas de Cartão - Desativado para evitar duplicidade com transações manuais agendadas
        # logic removed as per user feedback

        # E. Selecionar o dia com Maior Pico Agregado
        next_expense_data = None
        if candidates:
            # Ordenar por maior montante e pegar o top 1
            sorted_candidates = sorted(candidates.items(), key=lambda x: x[1]['amount'], reverse=True)
            peak_date_str, peak_info = sorted_candidates[0]
            
            unique_desc = list(set(peak_info['desc']))
            desc_str = ", ".join(unique_desc[:3])
            if len(unique_desc) > 3: desc_str += "..."
            
            next_expense_data = {
                'description': f"Pico Previsto: {desc_str}" if len(unique_desc) > 1 else unique_desc[0],
                'amount': float(peak_info['amount']),
                'date': peak_date_str,
                'category': "Multiples" if len(unique_desc) > 1 else unique_desc[0]
            }

        # 6. Simulador de Liberdade Financeira (Projeção)
        avg_pmt = Decimal(str(investment_data['total_invested'] / 6)) if investment_data['total_invested'] > 0 else Decimal('0.00')
        # Tentar pegar média real dos últimos 3 meses de aportes
        recent_aportes = [h['contribution'] for h in investment_data['monthly_history'][-3:]]
        if recent_aportes:
            avg_pmt = Decimal(str(sum(recent_aportes) / len(recent_aportes)))

        annual_rate = Decimal('0.08') # 8% ao ano
        monthly_rate = (Decimal('1') + annual_rate) ** (Decimal('1') / Decimal('12')) - Decimal('1')
        
        pv = Decimal(str(investment_data['total_invested']))
        projections = []
        for years in [1, 5, 10, 20]:
            months = years * 12
            # Fórmula de Juros Compostos com Aportes Mensais: FV = PV*(1+r)^n + PMT * (((1+r)^n - 1) / r)
            if monthly_rate > 0:
                fv = pv * (1 + monthly_rate)**months + avg_pmt * (((1 + monthly_rate)**months - 1) / monthly_rate)
            else:
                fv = pv + (avg_pmt * months)
            
            projections.append({
                'years': years,
                'label': f"{years} {'Ano' if years == 1 else 'Anos'}",
                'value': float(fv.quantize(Decimal('0.01')))
            })

        # 7. Análise de Gastos Fixos vs Variáveis
        # Filtro de Período Respeitando a seleção do usuário
        period_filter = Q(date__gte=start_date, date__lte=end_date)
        
        # Palavras-chave expandidas para detecção inteligente
        fixed_keywords = [
            'aluguel', 'condomínio', 'assinatura', 'internet', 'luz', 'água', 
            'seguro', 'escola', 'faculdade', 'academia', 'telefone', 'celular',
            'netflix', 'spotify', 'saúde', 'plano', 'cursinho', 'aluguel', 'mensalidade'
        ]
        
        fixed_q = Q(recurring_source__isnull=False)
        for kw in fixed_keywords:
            fixed_q |= Q(category__name__icontains=kw) | Q(description__icontains=kw)

        fixed_expenses_qs = Transaction.objects.filter(
            user=user,
            type__in=['EXPENSE', 'CREDIT_CARD']
        ).filter(period_filter).exclude(
            type__in=['INVOICE_PAYMENT', 'TRANSFER_OUT', 'TRANSFER_IN']
        ).filter(fixed_q)
        
        fixed_expenses = fixed_expenses_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        total_period_exp = Transaction.objects.filter(
            user=user,
            type__in=['EXPENSE', 'CREDIT_CARD']
        ).filter(period_filter).exclude(
            type__in=['INVOICE_PAYMENT', 'TRANSFER_OUT', 'TRANSFER_IN']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # Se o período selecionado for pequeno e estiver vazio (ex: início do mês), buscamos média histórica
        if total_period_exp == 0 and (end_date - start_date).days <= 31:
            # Fallback histórico (últimos 90 dias)
            lookback_days = 90
            hist_start = end_date - timedelta(days=lookback_days)
            
            hist_fixed = Transaction.objects.filter(
                user=user, type__in=['EXPENSE', 'CREDIT_CARD'],
                date__gte=hist_start, date__lte=end_date
            ).filter(fixed_q).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            hist_total = Transaction.objects.filter(
                user=user, type__in=['EXPENSE', 'CREDIT_CARD'],
                date__gte=hist_start, date__lte=end_date
            ).exclude(
                type__in=['INVOICE_PAYMENT', 'TRANSFER_OUT', 'TRANSFER_IN']
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            fixed_expenses = hist_fixed / 3
            total_period_exp = hist_total / 3

        variable_expenses = max(Decimal('0.00'), total_period_exp - fixed_expenses)

        # 8. Gasto Diário Seguro
        expected_income = ReportService._get_expected_income(user, end_date.month, end_date.year, end_date=end_date)

        future_committed = Decimal('0.00')
        if next_expense_data:
            future_committed = Decimal(str(next_expense_data['amount']))

        available_for_month = max(Decimal('0.00'), expected_income - total_period_exp - future_committed)
        
        import calendar
        _, last_day = calendar.monthrange(end_date.year, end_date.month)
        remaining_days = max(1, last_day - end_date.day)
        
        safe_daily_spend = available_for_month / Decimal(str(remaining_days))

        # 9. Análise de Risco (Perfil de Volatilidade)
        # Buscamos os gastos dos últimos 6 meses para calcular desvio padrão
        six_months_data = Transaction.objects.filter(
            user=user, type__in=['EXPENSE', 'CREDIT_CARD'],
            date__gt=end_date - timedelta(days=180)
        ).exclude(
            type__in=['INVOICE_PAYMENT', 'TRANSFER_OUT', 'TRANSFER_IN']
        ).annotate(m=TruncMonth('date')).values('m').annotate(total=Sum('amount'))

        expense_history = [float(m['total']) for m in six_months_data]
        
        risk_level = 'Baixa'
        volatility_score = 0
        recommendation = "Sua reserva de 6 meses é adequada para seu perfil estável."
        sensitive_category = None

        if len(expense_history) >= 2:
            import statistics
            mean_exp = statistics.mean(expense_history)
            stdev_exp = statistics.stdev(expense_history)
            volatility_score = (stdev_exp / mean_exp) if mean_exp > 0 else 0
            
            if volatility_score > 0.25:
                risk_level = 'Alta'
                recommendation = "Devido à alta volatilidade nos seus gastos, recomendamos elevar sua reserva para 10-12 meses."
            elif volatility_score > 0.15:
                risk_level = 'Média'
                recommendation = "Seu perfil apresenta oscilações moderadas. Uma reserva de 8 meses traria mais segurança."
            
            # Detecção de Sazonalidade (Categoriacom maior desvio)
            cat_variance = Transaction.objects.filter(
                user=user, type__in=['EXPENSE', 'CREDIT_CARD'],
                date__gt=end_date - timedelta(days=180)
            ).exclude(
                type__in=['INVOICE_PAYMENT', 'TRANSFER_OUT', 'TRANSFER_IN']
            ).values('category__name').annotate(
                avg=Avg('amount'),
                count=Count('id')
            ).filter(count__gt=2)
            
            if cat_variance:
                # Simplificação: pegar a categoria com maior volume que não seja fixa
                sensitive_category = cat_variance.order_by('-avg').first()['category__name']

        # 10. Gastos por Dia da Semana (Migrado para Premium)
        spend_by_weekday_qs = Transaction.objects.filter(
            user=user,
            date__gte=start_date,
            date__lte=end_date,
            type__in=['EXPENSE', 'CREDIT_CARD']
        ).exclude(
            type__in=['INVOICE_PAYMENT', 'TRANSFER_OUT', 'TRANSFER_IN']
        ).annotate(weekday=ExtractWeekDay('date')).values('weekday').annotate(total=Sum('amount')).order_by('weekday')
        
        weekday_map = {
            1: 'Dom', 2: 'Seg', 3: 'Ter', 4: 'Qua', 5: 'Qui', 6: 'Sex', 7: 'Sáb'
        }
        spend_by_weekday = []
        data_by_weekday = {i: 0.0 for i in range(1, 8)}
        for item in spend_by_weekday_qs:
            data_by_weekday[item['weekday']] = float(item['total'])
            
        for i in range(1, 8):
            spend_by_weekday.append({
                'label': weekday_map[i],
                'amount': data_by_weekday[i]
            })

        risk_analysis = {
            'level': risk_level,
            'volatility_score': round(volatility_score * 100, 1),
            'recommendation': recommendation,
            'sensitive_category': sensitive_category
        }

        return {
            'net_worth_evolution': evolution,
            'spending_frequency': spending_frequency,
            'investment_analysis': investment_data,
            'custom_monitoring': custom_monitoring,
            'next_big_expense': next_expense_data,
            'financial_freedom_projection': projections,
            'fixed_vs_variable': {
                'fixed': float(fixed_expenses),
                'variable': float(variable_expenses),
                'total': float(total_period_exp)
            },
            'daily_spending_report': {
                'safe_daily_spend': float(safe_daily_spend),
                'remaining_days': remaining_days,
                'available_for_month': float(available_for_month)
            },
            'risk_analysis': risk_analysis,
            'spend_by_weekday': spend_by_weekday
        }

    @staticmethod
    def get_monthly_comparison(user, months=6, month=None, year=None):
        """
        Retorna comparação de receitas vs despesas agrupadas por mês.
        Ideal para gráficos de barras históricas e linhas de saldo.
        """
        today = date.today()
        
        # Determinar a data final (pode ser o mês selecionado no dashboard)
        if month and year:
            # Último dia do mês/ano fornecido
            if int(month) == 12:
                target_end = date(int(year) + 1, 1, 1) - timedelta(days=1)
            else:
                target_end = date(int(year), int(month) + 1, 1) - timedelta(days=1)
        else:
            target_end = today

        # Primeiro dia do mês da data final
        base_start = target_end.replace(day=1)
        
        # Vamos calcular X meses atrás
        start_date = base_start
        for _ in range(months - 1):
            start_date = (start_date - timedelta(days=1)).replace(day=1)
        
        # 1. Agregação de Receitas
        income_qs = Transaction.objects.filter(
            user=user,
            type='INCOME',
            date__gte=start_date,
            date__lte=target_end
        ).annotate(month=TruncMonth('date')).values('month').annotate(total=Sum('amount')).order_by('month')

        # 2. Agregação de Despesas
        expense_qs = Transaction.objects.filter(
            user=user,
            type__in=['EXPENSE', 'CREDIT_CARD'],
            date__gte=start_date,
            date__lte=target_end
        ).exclude(
            type__in=['INVOICE_PAYMENT', 'TRANSFER_OUT', 'TRANSFER_IN']
        ).annotate(month=TruncMonth('date')).values('month').annotate(total=Sum('amount')).order_by('month')

        # Mapear resultados
        data_map = {}
        
        # Gerar os meses no range
        curr = start_date
        while curr <= target_end:
            m_key = curr.strftime('%Y-%m')
            data_map[m_key] = {
                'month': curr.strftime('%b/%y'),
                'income': Decimal('0.00'),
                'expense': Decimal('0.00'),
                'balance': Decimal('0.00')
            }
            # Avançar para o próximo mês
            if curr.month == 12:
                curr = curr.replace(year=curr.year + 1, month=1)
            else:
                curr = curr.replace(month=curr.month + 1)

        for item in income_qs:
            m_key = item['month'].strftime('%Y-%m')
            if m_key in data_map:
                data_map[m_key]['income'] = item['total']

        for item in expense_qs:
            m_key = item['month'].strftime('%Y-%m')
            if m_key in data_map:
                data_map[m_key]['expense'] = item['total']

        # Calcular saldo
        comparison_list = []
        for key in sorted(data_map.keys()):
            val = data_map[key]
            val['balance'] = val['income'] - val['expense']
            comparison_list.append(val)

        return comparison_list
    @staticmethod
    def get_user_financial_stats(user):
        """
        Retorna métricas financeiras detalhadas para um usuário específico (Admin focus).
        Calcula saldo total, médias diárias de valor e contagem de transações.
        """
        today = date.today()
        # Período de análise: últimos 30 dias para as médias
        start_date = today - timedelta(days=30)
        
        # 1. Total Balance (Status atual de todas as contas)
        from accounts.models import Account
        from accounts.services import AccountService
        accounts = Account.objects.filter(user=user)
        total_balance = sum(AccountService.get_balance(acc) for acc in accounts)

        # 2. Daily Averages (Baseado nos últimos 30 dias)
        # Receitas
        income_txs = Transaction.objects.filter(
            user=user, 
            type='INCOME', 
            date__gte=start_date, 
            date__lte=today
        )
        total_income_val = income_txs.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        income_count = income_txs.count()
        
        # Despesas (Inclui Credit Card)
        expense_txs = Transaction.objects.filter(
            user=user, 
            type__in=['EXPENSE', 'CREDIT_CARD'], 
            date__gte=start_date, 
            date__lte=today
        )
        total_expense_val = expense_txs.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        expense_count = expense_txs.count()
        
        # Divisor (dias que tiveram transações ou 30?)
        # O usuário pediu "média baseada na contagem individual".
        # Vamos usar 30 dias como base de tempo para médias diárias.
        avg_income_value = total_income_val / Decimal('30')
        avg_expense_value = total_expense_val / Decimal('30')
        income_count_per_day = income_count / 30.0
        expense_count_per_day = expense_count / 30.0

        # Last transaction
        last_tx = Transaction.objects.filter(user=user).order_by('-date').first()
        last_transaction_date = last_tx.date.strftime('%Y-%m-%d') if last_tx else None

        return {
            "total_balance": float(total_balance),
            "avg_income_value": float(avg_income_value),
            "avg_expense_value": float(avg_expense_value),
            "income_count_per_day": float(income_count_per_day),
            "expense_count_per_day": float(expense_count_per_day),
            "last_transaction_date": last_transaction_date
        }

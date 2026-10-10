from decimal import Decimal
from datetime import date, datetime, timedelta
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from django.db.models import Sum, Q, Count, Avg, F, Case, When
from django.db.models.functions import Coalesce, TruncMonth, ExtractWeekDay
from accounts.faturas import dia_no_mes, fatura_da_compra, limite_disponivel
from accounts.models import Account, CreditCard
from core.datas import hoje
from core.valores import dinheiro
from . import regras
from .models import FocusedMonitorItem
from transactions.classes import mapa_de_classes
from transactions.filtros import TIPOS_DE_DESPESA
from transactions.models import Transaction, Category, Tag
from budgets.models import Budget
from budgets.services import BudgetService


def _categoria_do_usuario(user, campo):
    """
    `campo` da categoria-pai da transação, ou da própria categoria, só quando
    são do `user`. Categoria de outro usuário conta como ausente, e a
    transação cai em "Sem Categoria"; categoria-pai de outro usuário também
    (ISOL-15).
    """
    return Case(
        When(category__user=user, then=Coalesce(
            Case(When(category__parent__user=user, then=F(f'category__parent__{campo}'))),
            F(f'category__{campo}'),
        )),
        output_field=models.CharField(),
    )

# "Sem classe" na divisão por classe (CLASSE-28)
SEM_CLASSE_NOME = 'Sem classe'
SEM_CLASSE_COR = '#94A3B8'


def despesas_por_classe(user, start_date, end_date):
    """
    `[{class_id, class_name, color, amount}]`: as despesas do período por
    classe efetiva atual da categoria (CLASSE-28, CLASSE-30), do maior valor
    para o menor. Soma as mesmas transações da divisão por categoria, por
    `regras.despesas` (CLASSE-29). Sem classe efetiva ou sem categoria do
    usuário, a despesa vai para "Sem classe", com `class_id` nulo.
    """
    mapa = mapa_de_classes(user)
    somas = {}
    por_categoria = (
        regras.despesas(user, start_date, end_date)
        .order_by().values('category_id').annotate(total=Sum('amount'))
    )
    for item in por_categoria:
        classe = mapa.get(item['category_id'])
        chave = classe.pk if classe is not None else None
        atual = somas.setdefault(chave, {'classe': classe, 'total': Decimal('0.00')})
        atual['total'] += item['total']
    linhas = sorted(
        somas.values(),
        key=lambda s: (-s['total'], s['classe'] is None, s['classe'].nome if s['classe'] else ''),
    )
    return [
        {
            'class_id': str(s['classe'].pk) if s['classe'] else None,
            'class_name': s['classe'].nome if s['classe'] else SEM_CLASSE_NOME,
            'color': s['classe'].cor if s['classe'] else SEM_CLASSE_COR,
            'amount': dinheiro(s['total']),
        }
        for s in linhas
    ]


# Gastos puxados: dependente ou principal sem categoria do usuário (VINCULO-34)
SEM_CATEGORIA_NOME = 'Sem categoria'
SEM_CATEGORIA_COR = '#CBD5E1'


def _raizes_das_categorias(user):
    """
    `{id da categoria: categoria raiz}` das categorias do usuário, subindo a
    árvore inteira. Categoria de outro usuário fica de fora e conta como sem
    categoria (ISOL-15).
    """
    categorias = {c.pk: c for c in Category.objects.filter(user=user).only('pk', 'parent_id', 'name', 'color')}
    raizes = {}
    for pk, categoria in categorias.items():
        atual, vistas = categoria, {pk}
        while atual.parent_id in categorias and atual.parent_id not in vistas:
            vistas.add(atual.parent_id)
            atual = categorias[atual.parent_id]
        raizes[pk] = atual
    return raizes


def gastos_puxados(user, start_date, end_date):
    """
    Quanto cada categoria raiz das principais puxa de gastos em cada
    categoria raiz das dependentes (VINCULO-34). As dependentes entram pelas
    regras das despesas, cada uma pela própria `report_date` (VINCULO-35);
    uma parcela entra quando a raiz da compra dela tem principal. Do maior
    total para o menor, com os valores em texto de duas casas.
    """
    dependentes = (
        regras.despesas(user, start_date, end_date)
        .filter(Q(principal__isnull=False) | Q(parent_transaction__principal__isnull=False))
        .annotate(da_principal=Coalesce('principal', 'parent_transaction__principal'))
        .order_by().values('da_principal', 'category_id').annotate(total=Sum('amount'))
    )
    linhas = list(dependentes)
    categoria_da_principal = dict(
        Transaction.objects.filter(user=user, pk__in={linha['da_principal'] for linha in linhas})
        .values_list('pk', 'category_id')
    )
    raizes = _raizes_das_categorias(user)

    grupos = {}
    for linha in linhas:
        de = raizes.get(categoria_da_principal.get(linha['da_principal']))
        para = raizes.get(linha['category_id'])
        grupo = grupos.setdefault(de.pk if de else None, {'categoria': de, 'total': Decimal('0.00'), 'puxados': {}})
        grupo['total'] += linha['total']
        puxado = grupo['puxados'].setdefault(para.pk if para else None, {'categoria': para, 'total': Decimal('0.00')})
        puxado['total'] += linha['total']

    def ordem(item):
        return (-item['total'], item['categoria'] is None, item['categoria'].name if item['categoria'] else '')

    def campos(categoria):
        if categoria is None:
            return {'category_id': None, 'category_name': SEM_CATEGORIA_NOME, 'color': SEM_CATEGORIA_COR}
        return {
            'category_id': str(categoria.pk), 'category_name': categoria.name,
            'color': categoria.color or SEM_CATEGORIA_COR,
        }

    return [
        {
            **campos(grupo['categoria']),
            'total': dinheiro(grupo['total']),
            'pulled': [
                {**campos(puxado['categoria']), 'amount': dinheiro(puxado['total'])}
                for puxado in sorted(grupo['puxados'].values(), key=ordem)
            ],
        }
        for grupo in sorted(grupos.values(), key=ordem)
    ]


class ReportService:
    @staticmethod
    def _get_date_range(period_days=None, month=None, year=None):
        """
        Helper para determinar start_date e end_date baseados em period_days ou mes/ano.
        Hoje e o mês atual são os do calendário de Brasília (REL-08).
        """
        today = hoje()
        
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
        
        # 1. Total Balance (Status atual, não depende do período para o card de saldo)
        # Soma o saldo guardado das contas ativas, o mesmo da lista de contas (SALDO-28, SALDO-30, SALDO-31)
        accounts = Account.objects.filter(user=user, is_active=True)
        total_balance = sum((acc.balance for acc in accounts), Decimal('0.00'))

        # Fluxo do período pelas regras comuns, no mês ou no intervalo de dias:
        # despesas efetivadas e compras no cartão na data da compra, receitas
        # efetivadas e as despesas pendentes à parte (REL-01 a REL-05)
        month_income = regras.total(regras.receitas(user, start_date, end_date))
        month_expense = regras.total(regras.despesas(user, start_date, end_date))
        payable = regras.total(regras.a_pagar(user, start_date, end_date))

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
        # Em aberto nas faturas que vencem no mês atual de Brasília (REL-18)
        total_current_invoices = regras.faturas_do_mes(user)
        card_details = []

        from accounts.services import AccountService

        for card in credit_cards:
            total_credit_limit += card.limit

            # Dados para Gestão de Crédito (Sempre Real-time/Hoje)
            # Encontramos a fatura onde um gasto feito HOJE seria alocado, sem
            # criá-la e sem quebrar em meses curtos (FIN-05, FATURA-01)
            mes_now, ano_now = fatura_da_compra(card, hoje())
            invoice_now = card.invoices.filter(month=mes_now, year=ano_now).first()
            invoice_amount_now = invoice_now.total_amount if invoice_now else Decimal('0.00')

            # O mesmo limite disponível da tela do cartão (FATURA-42)
            available_limit = limite_disponivel(card)

            card_details.append({
                'id': str(card.id),
                'name': card.name,
                'limit': dinheiro(card.limit),
                'current_invoice': dinheiro(invoice_amount_now), # Fatura "ativa" para gastos hoje
                'available_limit': dinheiro(available_limit), # Real-time consolidado
                'color': card.color or '#CBD5E1',
                'institution': card.institution,
                'due_day': card.due_day
            })

                
        patrimonio = regras.patrimonio(user)

        # 5. Métricas de Saúde Financeira (Agora sincronizadas com o range)
        health_metrics = ReportService.get_financial_health_metrics(
            user, month_income, month_expense, 
            start_date=start_date, end_date=end_date
        )

        return {
            # Dinheiro como texto; percentuais e razões continuam números (CONTRATO-16)
            'summary': {
                'total_balance': dinheiro(total_balance),
                'monthly_income': dinheiro(month_income),
                'monthly_expense': dinheiro(month_expense),
                'net_result': dinheiro(net_result),
                'total_credit_limit': dinheiro(total_credit_limit),
                'total_current_invoices': dinheiro(total_current_invoices),
                'payable': dinheiro(payable),
                # Contas ativas menos as compras não pagas dos cartões (REL-13, REL-15)
                'net_worth': dinheiro(patrimonio['total']),
                'net_worth_breakdown': {
                    'available': dinheiro(patrimonio['disponivel']),
                    'reserves': dinheiro(patrimonio['reservas']),
                    'investments': dinheiro(patrimonio['investimentos']),
                    'open_invoices': dinheiro(patrimonio['faturas_em_aberto']),
                },
                'savings_rate': health_metrics['savings_rate'],
                'saved_this_month': health_metrics['saved_this_month'],
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
        Retorna a renda esperada: as receitas do mês (REL-05) ou, sem elas, a
        média dos meses com receita entre os 3 meses do calendário anteriores.
        """
        inicio, fim = regras.limites_do_mes(target_year, target_month)
        current_income = regras.total(regras.receitas(user, inicio, fim))
        if current_income > 0:
            return current_income

        # Se não teve renda este mês ainda, pegamos a média dos 3 meses anteriores
        meses = regras.meses_do_calendario(inicio - timedelta(days=1), 3)
        income_avgs = regras.receitas(
            user, regras.limites_do_mes(*meses[0])[0], inicio - timedelta(days=1),
        ).annotate(m=TruncMonth('date')).values('m').annotate(total=Sum('amount'))
        totais = [m['total'] for m in income_avgs]
        if totais:
            return sum(totais, Decimal('0.00')) / len(totais)
        
        return Decimal('0.00')

    @staticmethod
    def get_financial_health_metrics(user, monthly_income, monthly_expense, month=None, year=None, start_date=None, end_date=None):
        """
        Calcula indicadores de saúde financeira baseados em Tipos de Conta e Período.
        """
        if not start_date or not end_date:
            today = hoje()
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

        # 1. Separação de Balanços: a liquidez soma só o disponível (contas
        # correntes, poupanças e carteiras ativas), sem cofrinhos nem
        # investimentos (REL-14, SALDO-28, SALDO-29, SALDO-31)
        partes = regras.patrimonio(user)
        total_liquid_balance = partes['disponivel']
        total_investment_balance = partes['investimentos']

        # 2. Taxa de poupança: o dinheiro guardado no período (aportes em
        # cofrinhos e investimentos menos resgates) sobre as receitas dele;
        # sem receitas, indisponível (REL-20 a REL-22)
        saved_this_month = regras.dinheiro_guardado(user, start_date, end_date)
        savings_rate = None
        if monthly_income and monthly_income > 0:
            savings_rate = (saved_this_month / monthly_income) * 100

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
        # Savings Rate component (max 40); taxa indisponível vale zero
        if savings_rate is not None:
            score += min(max(savings_rate * 2, Decimal('0')), Decimal('40'))
        
        # Liquidity component (max 40)
        score += min(liquidity_ratio * 6, Decimal('40')) # 6.6 meses = 40 pontos
        
        # Budget component (max 20): menos 5 pontos por orçamento do mês do
        # período que passou do limite, pela mesma regra do resumo de
        # orçamentos do dashboard (REL-19, FIN-26)
        over_limit_budgets = sum(
            1 for budget in Budget.objects.filter(user=user, month=start_date.month, year=start_date.year)
            if BudgetService.get_budget_usage(budget)['status'] == 'OVER_LIMIT'
        )
        
        score += max(Decimal('20') - (Decimal(str(over_limit_budgets)) * 5), Decimal('0'))

        return {
            'savings_rate': float(savings_rate.quantize(Decimal('0.01'))) if savings_rate is not None else None,
            'saved_this_month': dinheiro(saved_this_month),
            'total_liquid_balance': dinheiro(total_liquid_balance),
            'total_investment_balance': dinheiro(total_investment_balance),
            'liquidity_ratio': float(liquidity_ratio.quantize(Decimal('0.01'))),
            'financial_score': int(score)
        }

    @staticmethod
    def get_calendar_data(user, month=None, year=None, period_days=None):
        """
        Retorna lista diária de receitas e despesas. Respeita o período se fornecido.
        """
        start_date, end_date = ReportService._get_date_range(period_days, month, year)

        # 1. Receitas e despesas de cada dia pelas regras comuns: a compra no
        # cartão no dia da compra, sem pendentes, transferências e ajustes
        # (REL-01 a REL-05)
        raw_days = {}

        def dia(d):
            return raw_days.setdefault(d.strftime('%Y-%m-%d'), {'income': Decimal('0.00'), 'expense': Decimal('0.00')})

        for item in regras.receitas(user, start_date, end_date).values('date').annotate(total=Sum('amount')):
            dia(item['date'])['income'] += item['total']
        for item in regras.despesas(user, start_date, end_date).values('report_date').annotate(total=Sum('amount')):
            dia(item['report_date'])['expense'] += item['total']

        # 2. Transformar em formato esperado pelo Frontend
        days_list = []
        total_period_income = Decimal('0.00')
        total_period_expense = Decimal('0.00')

        for d_str, data in sorted(raw_days.items()):
            income = data['income']
            expense = data['expense']
            net = income - expense
            
            days_list.append({
                'date': d_str,
                'total_incomes': dinheiro(income),
                'total_expenses': dinheiro(expense),
                'net_amount': dinheiro(net),
                'is_positive': net >= 0
            })
            
            total_period_income += income
            total_period_expense += expense
                
        return {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'days': days_list,
            'total_income': dinheiro(total_period_income),
            'total_expense': dinheiro(total_period_expense)
        }

    @staticmethod
    def get_simple_charts(user, month=None, year=None, period_days=None):
        """
        Dados para gráficos: Barras (Por Dia/Semana/Mês) e Pizza (Categorias).
        """
        start_date, end_date = ReportService._get_date_range(period_days, month, year)
        
        # 2. Barras (Receita vs Despesa) - SEMPRE DIÁRIO conforme pedido do usuário
        # Agrupamento diário padrão (via get_calendar_data) para manter o Fluxo de Caixa Diário detalhado
        bar_data = ReportService.get_calendar_data(user, month, year, period_days)
        income_vs_expense = []
        for d in bar_data['days']:
            income_vs_expense.append({
                'label': datetime.strptime(d['date'], '%Y-%m-%d').strftime('%d'),
                'full_date': d['date'], # Adicionando a data completa para facilitar o filtro mensal no frontend
                'income': d['total_incomes'],
                'expense': d['total_expenses']
            })
            
        # 1. Agregação de Despesas, pelas regras comuns (REL-01 a REL-03)
        expense_by_category = []
        full_cat_expenses = regras.despesas(user, start_date, end_date).annotate(
            effective_name=_categoria_do_usuario(user, 'name'),
            effective_color=_categoria_do_usuario(user, 'color')
        ).values('effective_name', 'effective_color').annotate(total=Sum('amount')).order_by('-total')

        for item in full_cat_expenses:
            expense_by_category.append({
                'category_name': item['effective_name'] or 'Sem Categoria',
                'amount': dinheiro(item['total']),
                'color': item['effective_color'] or '#CBD5E1'
            })

        # 2. Agregação de Receitas, só as efetivadas (REL-05)
        income_by_category = []
        full_cat_incomes = regras.receitas(user, start_date, end_date).annotate(
            effective_name=_categoria_do_usuario(user, 'name'),
            effective_color=_categoria_do_usuario(user, 'color')
        ).values('effective_name', 'effective_color').annotate(total=Sum('amount')).order_by('-total')

        for item in full_cat_incomes:
            income_by_category.append({
                'category_name': item['effective_name'] or 'Sem Categoria',
                'amount': dinheiro(item['total']),
                'color': item['effective_color'] or '#CBD5E1'
            })

        return {
            'income_vs_expense': income_vs_expense,
            'expense_by_category': expense_by_category,
            # Divisão por classe, pelas mesmas transações (CLASSE-28, CLASSE-29)
            'expense_by_class': despesas_por_classe(user, start_date, end_date),
            'income_by_category': income_by_category,
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d')
            }
        }

    @staticmethod
    def get_linked_expenses(user, month=None, year=None, period_days=None):
        """
        Relatório de gastos puxados, com o período dos gráficos simples
        (VINCULO-34, VINCULO-35).
        """
        start_date, end_date = ReportService._get_date_range(period_days, month, year)
        return {
            'groups': gastos_puxados(user, start_date, end_date),
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
            },
        }

    @staticmethod
    def get_advanced_charts(user, period_days=None):
        """
        Premium: Evolução Patrimonial, Inteligência de Investimentos, Heatmap e Monitoramento.

        Todos os blocos usam as despesas e as receitas de `reports/regras.py`,
        os meses do calendário e os valores em `Decimal`; o dinheiro sai como
        texto só no fim (REL-10, AD-041).
        """
        start_date, end_date = ReportService._get_date_range(period_days)
        todas_as_datas = (date.min, date.max)

        # 1. Evolução Patrimonial (Net Worth): o patrimônio no fim de cada mês
        # do calendário, pelas regras de REL-13, com a dívida do cartão ainda
        # não paga naquele dia (REL-16, REL-17). Pelo menos 6 meses, no máximo 24.
        meses_no_periodo = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month + 1
        evolution = []
        for ano, mes in regras.meses_do_calendario(end_date, min(max(6, meses_no_periodo), 24)):
            fim_do_mes = min(regras.limites_do_mes(ano, mes)[1], end_date)
            evolution.append({
                'date': fim_do_mes.strftime('%Y-%m-%d'),
                'balance': dinheiro(regras.patrimonio(user, em=fim_do_mes)['total']),
            })

        # 2. Frequência de Gastos (Heatmap): dia da semana (1=Dom ... 7=Sáb) e
        # hora em que a despesa foi lançada, no fuso de Brasília (REL-09)
        frequency_qs = regras.despesas(user, start_date, end_date).annotate(
            hour=regras.hora_em_brasilia('created_at'),
            day_of_week=regras.dia_da_semana_em_brasilia('created_at'),
        ).values('day_of_week', 'hour').annotate(count=Count('id')).order_by('day_of_week', 'hour')

        spending_frequency = [
            {'day_of_week': item['day_of_week'], 'hour_of_day': item['hour'], 'count': item['count']}
            for item in frequency_qs
        ]

        # 3. Inteligência de Investimentos (Baseada em Tipo de Conta)
        investment_accounts = Account.objects.filter(user=user, type='INVESTMENT', is_active=True)
        has_investments = investment_accounts.exists()
        total_invested = sum((acc.balance for acc in investment_accounts), Decimal('0.00'))
        monthly_history = []
        asset_allocation = []

        if has_investments:
            # Histórico dos últimos 6 meses do calendário, um item por mês
            # (REL-17): aportes vindos das outras contas e resgates para
            # elas, sem as transferências entre contas de investimento
            meses = regras.meses_do_calendario(end_date, 6)
            inicio_do_historico = regras.limites_do_mes(*meses[0])[0]
            fim_do_historico = regras.limites_do_mes(*meses[-1])[1]
            movimentos = {}
            for item in regras.transferencias_de_fora(
                user, regras.INVESTIMENTOS, inicio_do_historico, fim_do_historico,
            ).annotate(m=TruncMonth('date')).values('m', 'type').annotate(total=Sum('amount')):
                movimentos[(item['m'].year, item['m'].month, item['type'])] = item['total']

            for ano, mes in meses:
                monthly_history.append({
                    'month': date(ano, mes, 1).strftime('%b/%y'),
                    'contribution': movimentos.get((ano, mes, 'TRANSFER_IN'), Decimal('0.00')),
                    'returns': movimentos.get((ano, mes, 'TRANSFER_OUT'), Decimal('0.00')),
                })

            # Alocação (Saldos por Conta de Investimento)
            colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']
            for i, acc in enumerate(investment_accounts):
                if acc.balance > 0:
                    asset_allocation.append({
                        'name': acc.name,
                        'value': dinheiro(acc.balance),
                        'color': colors[i % len(colors)]
                    })

        # 4. Monitoramento Customizado (Foco Manual): o mês de `end_date` contra
        # a média dos 6 meses do calendário anteriores que tiveram movimento
        inicio_do_mes, fim_do_mes = regras.limites_do_mes(end_date.year, end_date.month)
        meses_anteriores = regras.meses_do_calendario(inicio_do_mes - timedelta(days=1), 6)
        inicio_da_media = regras.limites_do_mes(*meses_anteriores[0])[0]
        fim_da_media = inicio_do_mes - timedelta(days=1)

        items = FocusedMonitorItem.objects.filter(user=user)
        custom_monitoring = []
        for item in items:
            # Monitor ligado a categoria ou tag de outro usuário fica de fora (ISOL-15)
            alvo = item.category or item.tag
            if alvo.user_id != user.id:
                continue
            name = item.category.name if item.category else item.tag.name

            # Se for categoria, buscamos ela e todas as subcategorias recursivamente
            if item.category:
                def get_all_child_categories(cat_id):
                    all_ids = [cat_id]
                    # Só subcategorias do usuário (ISOL-14)
                    children = Category.objects.filter(parent_id=cat_id, user=user).values_list('id', flat=True)
                    for child_id in children:
                        all_ids.extend(get_all_child_categories(child_id))
                    return all_ids

                category_ids = get_all_child_categories(item.category_id)
                target_filter = Q(category_id__in=category_ids)
            else:
                target_filter = Q(tags__id=item.tag_id)

            # Consumo líquido pelas regras comuns: despesas menos as receitas
            # (reembolsos) do alvo
            def consumo(inicio, fim):
                return (
                    regras.total(regras.despesas(user, inicio, fim).filter(target_filter))
                    - regras.total(regras.receitas(user, inicio, fim).filter(target_filter))
                )

            current_month_total = consumo(inicio_do_mes, fim_do_mes)

            # Média só dos meses anteriores que tiveram movimentação (máx 6)
            meses_com_movimento = set()
            for qs, campo in (
                (regras.despesas(user, inicio_da_media, fim_da_media), 'report_date'),
                (regras.receitas(user, inicio_da_media, fim_da_media), 'date'),
            ):
                meses_com_movimento |= {
                    (m.year, m.month) for m in qs.filter(target_filter).annotate(m=TruncMonth(campo)).values_list('m', flat=True)
                }
            average = consumo(inicio_da_media, fim_da_media) / max(1, len(meses_com_movimento))

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
                'current_month': dinheiro(current_month_total),
                'average_month': dinheiro(average),
                'status': status
            })

        # 5. Próximo Grande Gasto (Predição Inteligente)
        # Média por transação (para definir o que é "grande")
        avg_txn = regras.despesas(user, *todas_as_datas).aggregate(Avg('amount'))['amount__avg'] or Decimal('0.00')

        # Pool de Candidatos (Data de Projeção -> {amount, items})
        candidates = {} # d_str -> {'amount': Decimal, 'desc': [str]}

        # B. Despesas pendentes agendadas nos próximos 45 dias ("A pagar", REL-04)
        future_txns = regras.a_pagar(
            user, end_date + timedelta(days=1), end_date + timedelta(days=45),
        ).filter(amount__gt=avg_txn * Decimal('1.2')).select_related('category')

        for t in future_txns:
            d_str = t.date.strftime('%Y-%m-%d')
            if d_str not in candidates: candidates[d_str] = {'amount': Decimal('0'), 'desc': []}
            candidates[d_str]['amount'] += t.amount
            # Categoria de outro usuário conta como ausente (ISOL-15)
            proprio = t.category and t.category.user_id == user.id
            candidates[d_str]['desc'].append(t.category.name if proprio else 'Geral')

        # C. Detecção de Padrões (Recorrência nos 3 meses do calendário até
        # `end_date`, janela de 5 dias), pela data das despesas no relatório
        inicio_do_padrao = regras.limites_do_mes(*regras.meses_do_calendario(end_date, 3)[0])[0]
        history = regras.despesas(user, inicio_do_padrao, end_date).select_related('category')

        # Agrupar por categoria -> { (year, month) -> [ (day, amount) ] }
        cat_months = {}
        for h in history:
            cat_id = h.category_id or "root"
            m_key = (h.report_date.year, h.report_date.month)
            if cat_id not in cat_months: cat_months[cat_id] = {}
            if m_key not in cat_months[cat_id]: cat_months[cat_id][m_key] = []
            cat_months[cat_id][m_key].append({'day': h.report_date.day, 'amount': h.amount})

        # Mês seguinte ao de `end_date`, para a projeção
        target_month = end_date.month + 1 if end_date.month < 12 else 1
        target_year = end_date.year if end_date.month < 12 else end_date.year + 1

        # Analisar padrões em cada categoria
        for cat_id, months in cat_months.items():
            if len(months) < 2: continue # Precisa de pelo menos 2 meses de dados

            # Em cada mês, o maior gasto dessa categoria (como "Aluguel" ou "Escola")
            month_pikes = [max(txns, key=lambda x: x['amount']) for txns in months.values()]

            days = [p['day'] for p in month_pikes]
            avg_val = sum((p['amount'] for p in month_pikes), Decimal('0.00')) / len(month_pikes)

            # Se a variação entre os dias for pequena (janela de 5 dias)
            if max(days) - min(days) <= 5 and avg_val > avg_txn * Decimal('1.2'):
                # Projeta no próximo mês, no dia médio, ou no último dia do mês
                # quando ele não existe (REL-11, AD-006)
                proj_date = dia_no_mes(target_year, target_month, sum(days) // len(days))
                if proj_date > end_date:
                    d_str = proj_date.strftime('%Y-%m-%d')
                    if d_str not in candidates: candidates[d_str] = {'amount': Decimal('0'), 'desc': []}

                    # Evitar duplicar se já houver agendado
                    if not any(cat_id == t.category_id for t in future_txns if t.date == proj_date):
                        candidates[d_str]['amount'] += avg_val
                        # Só categoria do usuário (ISOL-15)
                        cat_obj = Category.objects.filter(id=cat_id, user=user).first() if cat_id != "root" else None
                        candidates[d_str]['desc'].append(cat_obj.name if cat_obj else 'Geral')

        # D. Faturas de Cartão - Desativado para evitar duplicidade com transações manuais agendadas
        # logic removed as per user feedback

        # E. Selecionar o dia com Maior Pico Agregado
        next_expense_data = None
        future_committed = Decimal('0.00')
        if candidates:
            # Ordenar por maior montante e pegar o top 1
            sorted_candidates = sorted(candidates.items(), key=lambda x: x[1]['amount'], reverse=True)
            peak_date_str, peak_info = sorted_candidates[0]

            unique_desc = list(set(peak_info['desc']))
            desc_str = ", ".join(unique_desc[:3])
            if len(unique_desc) > 3: desc_str += "..."

            future_committed = peak_info['amount']
            next_expense_data = {
                'description': f"Pico Previsto: {desc_str}" if len(unique_desc) > 1 else unique_desc[0],
                'amount': dinheiro(peak_info['amount']),
                'date': peak_date_str,
                'category': "Multiples" if len(unique_desc) > 1 else unique_desc[0]
            }

        # 6. Simulador de Liberdade Financeira (Projeção): aporte mensal médio
        # dos últimos 3 meses do histórico de investimentos
        recent_aportes = [h['contribution'] for h in monthly_history[-3:]]
        avg_pmt = sum(recent_aportes, Decimal('0.00')) / len(recent_aportes) if recent_aportes else Decimal('0.00')

        annual_rate = Decimal('0.08') # 8% ao ano
        monthly_rate = (Decimal('1') + annual_rate) ** (Decimal('1') / Decimal('12')) - Decimal('1')

        pv = total_invested
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
                'value': dinheiro(fv)
            })

        # 7. Análise de Gastos Fixos vs Variáveis
        # Palavras-chave expandidas para detecção inteligente
        fixed_keywords = [
            'aluguel', 'condomínio', 'assinatura', 'internet', 'luz', 'água',
            'seguro', 'escola', 'faculdade', 'academia', 'telefone', 'celular',
            'netflix', 'spotify', 'saúde', 'plano', 'cursinho', 'aluguel', 'mensalidade'
        ]

        fixed_q = Q(recurring_source__isnull=False)
        for kw in fixed_keywords:
            # Nome de categoria de outro usuário não classifica o gasto (ISOL-15)
            fixed_q |= Q(category__user=user, category__name__icontains=kw) | Q(description__icontains=kw)

        # Despesas do período escolhido pelo usuário, pelas regras comuns
        period_expenses = regras.despesas(user, start_date, end_date)
        fixed_expenses = regras.total(period_expenses.filter(fixed_q))
        total_period_exp = regras.total(period_expenses)

        # Se o período selecionado for pequeno e estiver vazio (ex: início do mês), buscamos média histórica
        if total_period_exp == 0 and (end_date - start_date).days <= 31:
            # Fallback histórico (últimos 90 dias)
            hist_expenses = regras.despesas(user, end_date - timedelta(days=90), end_date)
            fixed_expenses = regras.total(hist_expenses.filter(fixed_q)) / 3
            total_period_exp = regras.total(hist_expenses) / 3

        variable_expenses = max(Decimal('0.00'), total_period_exp - fixed_expenses)

        # 8. Gasto Diário Seguro
        expected_income = ReportService._get_expected_income(user, end_date.month, end_date.year, end_date=end_date)

        available_for_month = max(Decimal('0.00'), expected_income - total_period_exp - future_committed)

        import calendar
        _, last_day = calendar.monthrange(end_date.year, end_date.month)
        remaining_days = max(1, last_day - end_date.day)

        safe_daily_spend = available_for_month / remaining_days

        # 9. Análise de Risco (Perfil de Volatilidade)
        # Gastos dos 6 meses do calendário até `end_date`, para o desvio padrão
        inicio_do_risco = regras.limites_do_mes(*regras.meses_do_calendario(end_date, 6)[0])[0]
        despesas_do_risco = regras.despesas(user, inicio_do_risco, end_date)
        expense_history = [
            m['total'] for m in despesas_do_risco.annotate(m=TruncMonth('report_date')).values('m').annotate(total=Sum('amount'))
        ]

        risk_level = 'Baixa'
        volatility_score = Decimal('0')
        recommendation = "Sua reserva de 6 meses é adequada para seu perfil estável."
        sensitive_category = None

        if len(expense_history) >= 2:
            import statistics
            mean_exp = statistics.mean(expense_history)
            stdev_exp = statistics.stdev(expense_history)
            volatility_score = (stdev_exp / mean_exp) if mean_exp > 0 else Decimal('0')

            if volatility_score > Decimal('0.25'):
                risk_level = 'Alta'
                recommendation = "Devido à alta volatilidade nos seus gastos, recomendamos elevar sua reserva para 10-12 meses."
            elif volatility_score > Decimal('0.15'):
                risk_level = 'Média'
                recommendation = "Seu perfil apresenta oscilações moderadas. Uma reserva de 8 meses traria mais segurança."

            # Detecção de Sazonalidade (Categoriacom maior desvio)
            cat_variance = despesas_do_risco.annotate(
                # Categoria de outro usuário conta como ausente (ISOL-15)
                category_name=Case(When(category__user=user, then=F('category__name')))
            ).values('category_name').annotate(
                avg=Avg('amount'),
                count=Count('id')
            ).filter(count__gt=2)

            if cat_variance:
                # Simplificação: pegar a categoria com maior volume que não seja fixa
                sensitive_category = cat_variance.order_by('-avg').first()['category_name']

        # 10. Gastos por Dia da Semana (Migrado para Premium) - Agora como Média
        # Buscamos a data da primeira despesa para ajustar o período de média se necessário
        first_txn_date = regras.despesas(user, *todas_as_datas).aggregate(models.Min('report_date'))['report_date__min']

        # O período de cálculo da média começa no máximo entre a start_date e a primeira transação
        calculation_start_date = start_date
        if first_txn_date and first_txn_date > start_date:
            calculation_start_date = first_txn_date

        # Contamos quantas vezes cada dia da semana aparece no período efetivo de dados
        weekday_counts = {i: 0 for i in range(1, 8)}
        curr = calculation_start_date
        while curr <= end_date:
            # ExtractWeekDay: 1 (Sun) to 7 (Sat)
            # curr.weekday(): 0 (Mon) to 6 (Sun)
            django_wd = (curr.weekday() + 1) % 7 + 1
            weekday_counts[django_wd] += 1
            curr += timedelta(days=1)

        spend_by_weekday_qs = period_expenses.annotate(
            weekday=ExtractWeekDay('report_date'),
        ).values('weekday').annotate(total=Sum('amount')).order_by('weekday')

        weekday_map = {
            1: 'Dom', 2: 'Seg', 3: 'Ter', 4: 'Qua', 5: 'Qui', 6: 'Sex', 7: 'Sáb'
        }
        data_by_weekday = {i: Decimal('0.00') for i in range(1, 8)}
        for item in spend_by_weekday_qs:
            wd = item['weekday']
            count = weekday_counts.get(wd, 1)
            data_by_weekday[wd] = item['total'] / count if count > 0 else item['total']

        spend_by_weekday = [
            {'label': weekday_map[i], 'amount': dinheiro(data_by_weekday[i])}
            for i in range(1, 8)
        ]

        # Dinheiro como texto na saída (CONTRATO-16)
        investment_data = {
            'has_investments_account': has_investments,
            'total_invested': dinheiro(total_invested),
            'monthly_history': [
                {**mes, 'contribution': dinheiro(mes['contribution']), 'returns': dinheiro(mes['returns'])}
                for mes in monthly_history
            ],
            'asset_allocation': asset_allocation,
        }

        risk_analysis = {
            'level': risk_level,
            # Percentual, número com uma casa (CONTRATO-16)
            'volatility_score': float(round(volatility_score * 100, 1)),
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
                'fixed': dinheiro(fixed_expenses),
                'variable': dinheiro(variable_expenses),
                'total': dinheiro(total_period_exp)
            },
            'daily_spending_report': {
                'safe_daily_spend': dinheiro(safe_daily_spend),
                'remaining_days': remaining_days,
                'available_for_month': dinheiro(available_for_month)
            },
            'risk_analysis': risk_analysis,
            'spend_by_weekday': spend_by_weekday,
            'period': {
                'start_date': calculation_start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'requested_start_date': start_date.strftime('%Y-%m-%d')
            }
        }

    @staticmethod
    def get_monthly_comparison(user, months=6, month=None, year=None):
        """
        Retorna comparação de receitas vs despesas agrupadas por mês.
        Ideal para gráficos de barras históricas e linhas de saldo.

        Os `months` meses do calendário que terminam no mês escolhido (ou no
        mês atual de Brasília), cada um uma vez só (REL-17), com as receitas
        e as despesas das regras comuns (REL-01 a REL-05).
        """
        fim_do_periodo = date(int(year), int(month), 1) if month and year else hoje()
        meses = regras.meses_do_calendario(fim_do_periodo, months)
        start_date = regras.limites_do_mes(*meses[0])[0]
        target_end = regras.limites_do_mes(*meses[-1])[1]

        # 1. Agregação de Receitas
        income_qs = regras.receitas(user, start_date, target_end).annotate(
            month=TruncMonth('date'),
        ).values('month').annotate(total=Sum('amount'))

        # 2. Agregação de Despesas, pela data no relatório
        expense_qs = regras.despesas(user, start_date, target_end).annotate(
            month=TruncMonth('report_date'),
        ).values('month').annotate(total=Sum('amount'))

        # Mapear resultados, um item por mês do calendário
        data_map = {
            (ano, mes): {
                'month': date(ano, mes, 1).strftime('%b/%y'),
                'income': Decimal('0.00'),
                'expense': Decimal('0.00'),
                'balance': Decimal('0.00')
            }
            for ano, mes in meses
        }

        for item in income_qs:
            data_map[(item['month'].year, item['month'].month)]['income'] = item['total']

        for item in expense_qs:
            data_map[(item['month'].year, item['month'].month)]['expense'] = item['total']

        # Calcular saldo
        comparison_list = []
        for key in meses:
            val = data_map[key]
            val['balance'] = val['income'] - val['expense']
            # Dinheiro como texto (CONTRATO-16)
            for campo in ('income', 'expense', 'balance'):
                val[campo] = dinheiro(val[campo])
            comparison_list.append(val)

        return comparison_list
    @staticmethod
    def get_user_financial_stats(user):
        """
        Métricas financeiras de um usuário para o painel admin, pelas mesmas
        regras dos relatórios dele (ADMIN-29, AD-029, AD-046):
        - receitas e despesas dos últimos 30 dias de Brasília, o mesmo período
          do dashboard com `days=30`, pela `report_date` e por `regras`;
        - sem ajustes de saldo nem transações de contas excluídas (SALDO-31);
        - saldo como a soma das contas ativas, o da lista de contas (SALDO-28).
        As médias diárias dividem o total do período por 30.
        """
        # De hoje menos 30 dias até hoje, em Brasília (REL-08)
        inicio, fim = ReportService._get_date_range(period_days=30)

        # Saldo guardado das contas ativas, o mesmo da lista de contas (SALDO-28, SALDO-31)
        accounts = Account.objects.filter(user=user, is_active=True)
        total_balance = sum((acc.balance for acc in accounts), Decimal('0.00'))

        def sem_contas_excluidas(queryset):
            return queryset.exclude(account__is_active=False)

        receitas = sem_contas_excluidas(regras.receitas(user, inicio, fim))
        despesas = sem_contas_excluidas(regras.despesas(user, inicio, fim))
        dias = Decimal('30')

        ultima = sem_contas_excluidas(
            Transaction.objects.filter(user=user, is_balance_adjustment=False)
        ).order_by('-date').first()

        return {
            # Dinheiro como texto; contagens como números (CONTRATO-16)
            "total_balance": dinheiro(total_balance),
            "avg_income_value": dinheiro(regras.total(receitas) / dias),
            "avg_expense_value": dinheiro(regras.total(despesas) / dias),
            "income_count_per_day": receitas.count() / 30.0,
            "expense_count_per_day": despesas.count() / 30.0,
            "last_transaction_date": ultima.date.strftime('%Y-%m-%d') if ultima else None,
        }

    @staticmethod
    def get_tag_insights(user, tag_id, months=6):
        """
        Retorna Monitor de Foco e Gráfico de Histórico para uma tag específica.
        """
        try:
            tag = Tag.objects.filter(user=user, id=tag_id).first()
        except (ValueError, DjangoValidationError):
            # tag_id malformado vale como tag inexistente (ISOL-12)
            tag = None
        if not tag:
            return None

        # Mês atual e meses do histórico pelo calendário de Brasília, cada mês
        # uma vez só (REL-08, REL-17)
        meses = regras.meses_do_calendario(hoje(), months)
        inicio_do_historico = regras.limites_do_mes(*meses[0])[0]
        inicio_do_mes, fim_do_mes = regras.limites_do_mes(*meses[-1])

        # 1. Despesas e receitas da tag pelas regras comuns (REL-01 a REL-05)
        def despesas_da_tag(inicio, fim):
            return regras.despesas(user, inicio, fim).filter(tags__id=tag.id)

        def receitas_da_tag(inicio, fim):
            return regras.receitas(user, inicio, fim).filter(tags__id=tag.id)

        # 2. Monitor de Foco (Mês Atual), líquido: despesas menos reembolsos
        current_total = (
            regras.total(despesas_da_tag(inicio_do_mes, fim_do_mes))
            - regras.total(receitas_da_tag(inicio_do_mes, fim_do_mes))
        )

        # 3. Média Histórica dos meses do período que tiveram movimentação
        despesas_por_mes = {
            (item['m'].year, item['m'].month): item['total']
            for item in despesas_da_tag(inicio_do_historico, fim_do_mes)
            .annotate(m=TruncMonth('report_date')).values('m').annotate(total=Sum('amount'))
        }
        receitas_por_mes = {
            (item['m'].year, item['m'].month): item['total']
            for item in receitas_da_tag(inicio_do_historico, fim_do_mes)
            .annotate(m=TruncMonth('date')).values('m').annotate(total=Sum('amount'))
        }
        total_historical = sum(despesas_por_mes.values(), Decimal('0.00')) - sum(receitas_por_mes.values(), Decimal('0.00'))
        months_count = len(set(despesas_por_mes) | set(receitas_por_mes))
        average = total_historical / max(1, months_count)

        status = 'success'
        if average > 0:
            if current_total > average * Decimal('1.2'): status = 'warning'
            if current_total > average * Decimal('1.5'): status = 'error'
        elif current_total > 0:
            status = 'warning'

        # 4. Gráfico de Histórico, um item por mês do calendário
        history_chart = [
            {
                'month': date(ano, mes, 1).strftime('%b/%y'),
                'income': dinheiro(receitas_por_mes.get((ano, mes))),
                'expense': dinheiro(despesas_por_mes.get((ano, mes))),
            }
            for ano, mes in meses
        ]

        return {
            'tag_name': tag.name,
            'color': tag.color,
            'focus_monitor': {
                'current_month': dinheiro(current_total),
                'average_month': dinheiro(average),
                'status': status
            },
            'history_chart': history_chart
        }

    @staticmethod
    def get_tag_distribution(user, month=None, year=None, period_days=None):
        """
        Distribuição de Gastos e Ganhos por Tags. Inclui 'Outros' para transações sem tags.
        """
        start_date, end_date = ReportService._get_date_range(period_days, month, year)

        # 1. Gastos pelas regras comuns (REL-01 a REL-03)
        expenses = regras.despesas(user, start_date, end_date)
        
        # Sem tags (tag de outro usuário conta como ausente, ISOL-15)
        others_expenses = expenses.exclude(tags__user=user).aggregate(total=Sum('amount'))['total'] or 0
        
        # Por Tag, só as do usuário
        tag_expenses = expenses.filter(tags__user=user).values('tags__id', 'tags__name', 'tags__color').annotate(total=Sum('amount')).order_by('-total')
        
        expense_by_tag = []
        for item in tag_expenses:
            expense_by_tag.append({
                'id': str(item['tags__id']),
                'name': item['tags__name'],
                'amount': dinheiro(item['total']),
                'color': item['tags__color'] or '#CBD5E1'
            })
            
        if others_expenses > 0:
            expense_by_tag.append({
                'id': 'others',
                'name': 'Outros',
                'amount': dinheiro(others_expenses),
                'color': '#94a3b8'
            })

        # 2. Ganhos, só os efetivados (REL-05)
        incomes = regras.receitas(user, start_date, end_date)
        
        # Sem tags (tag de outro usuário conta como ausente, ISOL-15)
        others_incomes = incomes.exclude(tags__user=user).aggregate(total=Sum('amount'))['total'] or 0
        
        # Por Tag, só as do usuário
        tag_incomes = incomes.filter(tags__user=user).values('tags__id', 'tags__name', 'tags__color').annotate(total=Sum('amount')).order_by('-total')
        
        income_by_tag = []
        for item in tag_incomes:
            income_by_tag.append({
                'id': str(item['tags__id']),
                'name': item['tags__name'],
                'amount': dinheiro(item['total']),
                'color': item['tags__color'] or '#CBD5E1'
            })
            
        if others_incomes > 0:
            income_by_tag.append({
                'id': 'others',
                'name': 'Outros',
                'amount': dinheiro(others_incomes),
                'color': '#94a3b8'
            })
            
        return {
            'expense_by_tag': expense_by_tag,
            'income_by_tag': income_by_tag,
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d')
            }
        }



from datetime import date
from decimal import Decimal
from dateutil.relativedelta import relativedelta

class MockCard:
    def __init__(self, name, closing_day, due_day):
        self.name = name
        self.closing_day = closing_day
        self.due_day = due_day

def calculate_due_date(card, purchase_date):
    if purchase_date.day >= card.closing_day:
        closing_month_date = purchase_date + relativedelta(months=1)
    else:
        closing_month_date = purchase_date
        
    closing_month = closing_month_date.month
    closing_year = closing_month_date.year
    
    if card.due_day <= card.closing_day:
        due_date = date(closing_year, closing_month, 1) + relativedelta(months=1, day=card.due_day)
    else:
        due_date = date(closing_year, closing_month, card.due_day)
        
    return due_date

def get_invoice_details(card, month, year):
    try:
        d_date = date(year, month, card.due_day)
    except ValueError:
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        d_date = date(year, month, last_day)

    if card.due_day <= card.closing_day:
        closing_ref = d_date - relativedelta(months=1)
    else:
        closing_ref = d_date
        
    try:
        c_date = date(closing_ref.year, closing_ref.month, card.closing_day)
    except ValueError:
        import calendar
        last_day = calendar.monthrange(closing_ref.year, closing_ref.month)[1]
        c_date = date(closing_ref.year, closing_ref.month, last_day)

    return c_date, d_date

card = MockCard("Cartão Teste", 28, 4)

# Testes solicitados pelo usuário
tests = [
    date(2026, 4, 27), # Antes do fechamento (deve cair em Maio)
    date(2026, 4, 28), # No fechamento (deve cair em Junho)
    date(2026, 4, 30), # Entre fechamento e vencimento (deve cair em Junho)
    date(2026, 5, 2),  # Entre fechamento e vencimento (deve cair em Junho)
    date(2026, 5, 4),  # No dia do vencimento (deve cair em Junho)
    date(2026, 5, 5),  # Após o vencimento (deve cair em Junho)
    date(2026, 5, 28), # Fechamento do próximo mês (deve cair em Julho)
]

print(f"{'Data Compra':<15} | {'Vencimento':<15} | {'Fatura Mês':<10} | {'Fechamento':<15}")
print("-" * 65)

for d in tests:
    due = calculate_due_date(card, d)
    c_date, d_date = get_invoice_details(card, due.month, due.year)
    print(f"{str(d):<15} | {str(due):<15} | {due.month:<10} | {str(c_date):<15}")

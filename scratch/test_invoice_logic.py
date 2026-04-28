from datetime import date
from dateutil.relativedelta import relativedelta

class MockCard:
    def __init__(self, closing_day, due_day):
        self.closing_day = closing_day
        self.due_day = due_day

def calculate_due_date(card, purchase_date):
    if purchase_date.day < card.closing_day:
        closing_month = purchase_date.month
        closing_year = purchase_date.year
    else:
        closing_month = purchase_date.month + 1
        closing_year = purchase_date.year
        if closing_month > 12:
            closing_month = 1
            closing_year += 1
    
    due_month = closing_month
    due_year = closing_year
    
    if card.due_day <= card.closing_day:
        due_month += 1
        if due_month > 12:
            due_month = 1
            due_year += 1
    
    return date(due_year, due_month, card.due_day)

card = MockCard(28, 4)

tests = [
    date(2026, 4, 27),
    date(2026, 4, 28),
    date(2026, 4, 29),
    date(2026, 5, 2),
    date(2026, 5, 4),
    date(2026, 5, 27),
    date(2026, 5, 28),
]

for d in tests:
    due = calculate_due_date(card, d)
    print(f"Compra: {d} -> Vencimento: {due}")

import os
import django
import sys
from decimal import Decimal
from datetime import date

# Configuração
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
os.environ['ALLOWED_HOSTS'] = 'localhost,testserver'
os.environ['DB_ENGINE'] = 'django.db.backends.postgresql'
os.environ['DB_NAME'] = 'fluxar_db'
os.environ['DB_USER'] = 'postgres'
os.environ['DB_PASSWORD'] = 'postgres'
os.environ['DB_HOST'] = 'localhost'
os.environ['DB_PORT'] = '5433'
django.setup()

from api.models import User
from accounts.models import Account, CreditCard, CreditCardInvoice
from transactions.models import Transaction
from transactions.services import TransactionService
from accounts.services import CreditCardService

def run_test():
    print("=== Testando Refatoração de Cartão ===")
    
    # Setup
    email = f"refactor_{date.today()}@example.com"
    user, _ = User.objects.get_or_create(email=email, defaults={'name': 'Refactor User', 'is_active': True})
    acc, _ = Account.objects.get_or_create(user=user, name="Conta Refactor", defaults={'initial_balance': 2000})
    card, _ = CreditCard.objects.get_or_create(
        user=user, name="Card Refactor", 
        defaults={'limit': 2000, 'closing_day': 10, 'due_day': 15, 'account': acc}
    )
    
    # Limpar
    Transaction.objects.filter(user=user).delete()
    CreditCardInvoice.objects.filter(card=card).delete()
    
    # 1. Criação de Despesa (Parcelada 2x)
    print("\n[Teste 1] Criando despesa R$ 200 (2x) em 05/02/2026...")
    # Fatura Fev (Open) e Mar (Open)
    txs = TransactionService.create_credit_card_expense(
        user=user, card=card, amount=Decimal('200.00'), 
        date=date(2026, 2, 5), description="Compra Teste", category=None, installments=2
    )
    
    t1 = txs[0]
    print(f"Parcela 1: {t1.description} - Status: {t1.status} - Account: {t1.account.name if t1.account else 'None'}")
    assert t1.status == 'PENDING'
    assert t1.account == card.account # Deve estar vinculado à conta do cartão
    
    # Validar Fatura Fev
    inv_feb = CreditCardInvoice.objects.get(card=card, month=2, year=2026)
    print(f"Invoice Fev Total: {inv_feb.total_amount} (Esperado: 100.00)")
    assert inv_feb.total_amount == Decimal('100.00')
    
    # 2. Pagamento de Fatura (TOTAL)
    print("\n[Teste 2] Pagando Fatura Fev TOTAL (R$ 100)...")
    payment_date = date(2026, 2, 14)
    CreditCardService.pay_invoice(user, inv_feb, acc, Decimal('100.00'), payment_date)
    
    t1.refresh_from_db()
    inv_feb.refresh_from_db()
    
    print(f"Pós Pagamento - Status Transação: {t1.status}")
    print(f"Pós Pagamento - Account Transação: {t1.account.name}")
    print(f"Pós Pagamento - Date Transação: {t1.date}")
    print(f"Pós Pagamento - Invoice Status: {inv_feb.status}")
    
    assert t1.status == 'COMPLETED'
    assert t1.account == acc # Mudou para conta pagadora
    assert t1.date == payment_date # Mudou data
    assert inv_feb.status == 'PAID'
    
    # 3. Pagamento Parcial (Cenário mais complexo)
    # Criar nova despesa para Março de R$ 300
    print("\n[Teste 3] Criando R$ 300 em Março...")
    t3 = TransactionService.create_credit_card_expense(
        user=user, card=card, amount=Decimal('300.00'),
        date=date(2026, 3, 5), description="Compra Março", category=None
    )
    
    inv_mar = CreditCardInvoice.objects.get(card=card, month=3, year=2026)
    # Total deve ser 100 (parcela 2 da compra 1) + 300 = 400
    print(f"Invoice Mar Total: {inv_mar.total_amount} (Esperado: 400.00)")
    assert inv_mar.total_amount == Decimal('400.00')
    
    # Pagar apenas R$ 150 (Paga os 100 da parcela + 50 da Compra Março)
    print("\nPagando R$ 150 na Fatura Março...")
    CreditCardService.pay_invoice(user, inv_mar, acc, Decimal('150.00'), date(2026, 3, 15))
    
    inv_mar.refresh_from_db()
    print(f"Invoice Mar Status: {inv_mar.status}")
    print(f"Invoice Mar Total Final: {inv_mar.total_amount} (Esperado: 150.00 - só o que foi pago)")
    assert inv_mar.status == 'PAID'
    assert inv_mar.total_amount == Decimal('150.00')
    
    # Verificar Rollover
    inv_apr = CreditCardInvoice.objects.filter(card=card, month=4, year=2026).first()
    print(f"Invoice Abr: {inv_apr}")
    assert inv_apr is not None
    print(f"Invoice Abr Total: {inv_apr.total_amount} (Esperado: 250.00 -> 400 original - 150 pago)")
    assert inv_apr.total_amount == Decimal('250.00')
    
    # Verificar transações em Abril
    txs_apr = inv_apr.transactions.all()
    for t in txs_apr:
        print(f"  Tx em Abril: {t.description} - R$ {t.amount} - Status: {t.status}")
        assert t.status == 'PENDING'
        
    print("\n=== SUCESSO! Refatoração Aprovada. ===")

if __name__ == '__main__':
    run_test()

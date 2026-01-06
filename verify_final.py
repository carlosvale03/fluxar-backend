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
from accounts.services import CreditCardService, AccountService

def run_test():
    print("=== Testando Estorno (Unpay) e Balance ===")
    
    # Setup
    email = f"unpay_{date.today()}@example.com"
    user, _ = User.objects.get_or_create(email=email, defaults={'name': 'Unpay User', 'is_active': True})
    acc, _ = Account.objects.get_or_create(user=user, name="Conta Unpay", defaults={'initial_balance': 1000})
    card, _ = CreditCard.objects.get_or_create(
        user=user, name="Card Unpay", 
        defaults={'limit': 1000, 'closing_day': 10, 'due_day': 15, 'account': acc}
    )
    
    # Limpar
    Transaction.objects.filter(user=user).delete()
    CreditCardInvoice.objects.filter(card=card).delete()
    
    # 0. Check Saldo Inicial
    bal = AccountService.get_balance(acc)
    print(f"Saldo Inicial: {bal} (Esperado: 1000.00)")
    assert bal == Decimal('1000.00')
    
    # 1. Cria Compra de R$ 200 (Status PENDING) em Fev
    print("\n1. Criando compra R$ 200 (Fev)...")
    txs = TransactionService.create_credit_card_expense(
        user=user, card=card, amount=Decimal('200.00'), 
        date=date(2026, 2, 5), description="Teste Unpay", category=None
    )
    t = txs[0]
    
    # Saldo não deve mudar (PENDING)
    bal = AccountService.get_balance(acc)
    print(f"Saldo pós compra (PENDING): {bal} (Esperado: 1000.00)")
    assert bal == Decimal('1000.00')
    
    inv = CreditCardInvoice.objects.get(card=card, month=2, year=2026)
    
    # 2. Pagar Fatura (Status -> COMPLETED)
    print("\n2. Pagando Fatura...")
    CreditCardService.pay_invoice(user, inv, acc, Decimal('200.00'), date(2026, 2, 15))
    
    inv.refresh_from_db()
    t.refresh_from_db()
    
    print(f"Status Invoice: {inv.status}")
    print(f"Status Transação: {t.status}")
    assert inv.status == 'PAID'
    assert t.status == 'COMPLETED'
    
    # Saldo deve cair (COMPLETED)
    bal = AccountService.get_balance(acc)
    print(f"Saldo pós pagamento: {bal} (Esperado: 800.00)")
    assert bal == Decimal('800.00')
    
    # 3. Estornar Fatura (Unpay)
    print("\n3. Estornando Fatura...")
    CreditCardService.unpay_invoice(user, inv)
    
    inv.refresh_from_db()
    t.refresh_from_db()
    
    print(f"Status Invoice: {inv.status}")
    print(f"Status Transação: {t.status}")
    assert inv.status == 'OPEN'
    assert t.status == 'PENDING'
    
    # Saldo deve voltar (PENDING é ignorado no get_balance)
    bal = AccountService.get_balance(acc)
    print(f"Saldo pós estorno: {bal} (Esperado: 1000.00)")
    assert bal == Decimal('1000.00')
    
    print("\n=== SUCESSO! Estorno e Saldo OK. ===")

if __name__ == '__main__':
    run_test()

import os
import django
import uuid

os.environ['DB_HOST'] = 'localhost'
os.environ['DB_PORT'] = '5433'
os.environ['DB_NAME'] = 'fluxar_db'
os.environ['DB_USER'] = 'postgres'
os.environ['DB_PASSWORD'] = 'postgres'
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from api.models import User
from accounts.models import Account, CreditCard
from accounts.serializers import CreditCardSerializer
from rest_framework.test import APIRequestFactory

def debug():
    print("Iniciando Debug de Serializer...")
    
    # 1. Setup
    email = "debug_serial@example.com"
    User.objects.filter(email=email).delete()
    user = User.objects.create_user(email=email, password="password", name="Debug Tester")
    
    account = Account.objects.create(
        user=user, 
        name="Conta Debug", 
        type="CHECKING"
    )
    
    print(f"Conta criada: {account.id}")

    # 2. Mock Request
    factory = APIRequestFactory()
    request = factory.post('/api/credit_cards/')
    request.user = user

    # 3. Teste Serializer - Create
    payload = {
        "name": "Cartão Debug",
        "limit": 1000.00,
        "closing_day": 10,
        "due_day": 15,
        "institution": "nubank",
        "account_id": str(account.id)
    }
    
    print(f"Payload: {payload}")
    
    # Context com request é CRUCIAL pois o __init__ e validate usam request.user
    serializer = CreditCardSerializer(data=payload, context={'request': request})
    
    if serializer.is_valid():
        print("Serializer Válido!")
        instance = serializer.save()
        print(f"Instância Salva: {instance} (Account: {instance.account})")
        
        # Teste Representation (que é onde eu suspeito que quebra)
        print("Tentando serializar output...")
        output = serializer.data
        if 'account_id' in output:
            print(f"SUCESSO: account_id encontrado: {output['account_id']}")
        else:
            print("FALHA: account_id NÃO encontrado no output")
            print(f"Keys: {output.keys()}")
        print(output)
    else:
        print("Serializer Inválido!")
        print(serializer.errors)

if __name__ == '__main__':
    debug()

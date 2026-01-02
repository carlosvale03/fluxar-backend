import os
import django
import uuid

os.environ['DB_HOST'] = 'localhost'
os.environ['DB_PORT'] = '5433'
os.environ['DB_NAME'] = 'fluxar_db'
os.environ['DB_USER'] = 'postgres'
os.environ['DB_PASSWORD'] = 'postgres'
os.environ['ALLOWED_HOSTS'] = 'localhost,testserver'
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from rest_framework.test import APIClient
from api.models import User
from accounts.models import Account, CreditCard

def run_verification():
    print("Iniciando verificação de Vínculo Cartão-Conta...")
    
    # 1. Setup Usuário
    email = "link_test@example.com"
    User.objects.filter(email=email).delete()
    user = User.objects.create_user(email=email, password="password", name="Link Tester")
    
    # 2. Setup Conta
    account = Account.objects.create(
        user=user, 
        name="Conta Nubank", 
        type="CHECKING",
        institution="nubank"
    )
    print(f"Conta criada: {account.name} ({account.id})")
    
    # 3. Setup Outro Usuário (para teste de isolamento)
    hacker_email = "hacker@example.com"
    User.objects.filter(email=hacker_email).delete() # Limpeza
    other_user = User.objects.create_user(email=hacker_email, password="password", name="Hacker")
    other_account = Account.objects.create(user=other_user, name="Conta Hacker")
    
    client = APIClient()
    client.force_authenticate(user=user)
    
    # 4. Teste: Criar Cartão Vinculado (Sucesso)
    print("\n[Teste 1] Criar Cartão com conta válida...")
    payload = {
        "name": "Cartão Nubank",
        "limit": 1000.00,
        "closing_day": 10,
        "due_day": 15,
        "institution": "nubank",
        "account_id": str(account.id)
    }
    
    resp = client.post('/api/credit-cards/', payload, format='json')
    if resp.status_code != 201:
        # Fallback para debug
        print(f"Erro Status: {resp.status_code}")
        with open('last_error.html', 'wb') as f:
            f.write(resp.content)
        print("Erro salvo em last_error.html")
    assert resp.status_code == 201
    
    card_id = resp.data['id']
    print(f"Sucesso. Cartão criado: {card_id}")
    
    # Verificar Resposta (Nested)
    if 'account' not in resp.data or resp.data['account']['id'] != str(account.id):
        print("FALHA: Objeto 'account' não retornado ou incorreto.")
        print(resp.data)
    else:
        print("Sucesso: Objeto 'account' retornado corretamente na resposta.")
        
    # Verificar Banco
    card = CreditCard.objects.get(id=card_id)
    assert card.account == account
    print("Sucesso: Vínculo salvo no banco.")

    # 5. Teste: Tentar vincular conta de outro usuário (Deve falhar no validador ou não encontrar FK)
    print("\n[Teste 2] Tentar vincular conta de outro usuário...")
    payload_hack = {
        "name": "Cartão Hacker",
        "limit": 5000,
        "closing_day": 1,
        "due_day": 10,
        "account_id": str(other_account.id)
    }
    resp_hack = client.post('/api/credit-cards/', payload_hack, format='json')
    
    # O serializer com PrimaryKeyRelatedField filtered deve retornar erro de campo inválido ('Objeto não existe' para o usuário)
    if resp_hack.status_code == 400 and 'account_id' in resp_hack.data:
        print(f"Sucesso: Bloqueado como esperado. Erro: {resp_hack.data['account_id']}")
    else:
        print(f"FALHA: Deveria ter bloqueado. Status: {resp_hack.status_code}")
        print(resp_hack.data)

if __name__ == '__main__':
    run_verification()

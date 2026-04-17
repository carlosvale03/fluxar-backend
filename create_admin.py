import os
import django
from django.contrib.auth import get_user_model

# Configura o ambiente Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

def create_admin():
    User = get_user_model()
    
    username = os.getenv('DJANGO_SUPERUSER_NAME', 'Admin')
    email = os.getenv('DJANGO_SUPERUSER_EMAIL')
    password = os.getenv('DJANGO_SUPERUSER_PASSWORD')

    if not email or not password:
        print("Pulei a criação de admin: DJANGO_SUPERUSER_EMAIL ou DJANGO_SUPERUSER_PASSWORD não configurados.")
        return

    # Tenta obter o usuário existente
    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            'name': username,
            'is_staff': True,
            'is_superuser': True,
            'role': 'ADMIN',
            'plan': 'PREMIUM_PLUS',
            'email_verified': True,
        }
    )

    if created:
        user.set_password(password)
        user.save()
        print(f"Superusuário criado com sucesso: {email}")
    else:
        # Garante que o usuário existente tenha permissões de admin
        updated = False
        if not user.is_superuser:
            user.is_superuser = True
            updated = True
        if not user.is_staff:
            user.is_staff = True
            updated = True
        if user.role != 'ADMIN':
            user.role = 'ADMIN'
            updated = True
        if user.plan != 'PREMIUM_PLUS':
            user.plan = 'PREMIUM_PLUS'
            updated = True
        if not user.email_verified:
            user.email_verified = True
            updated = True
            
        if updated:
            user.save()
            print(f"Permissões do usuário {email} atualizadas para ADMIN.")
        else:
            print(f"Usuário admin {email} já existe e está configurado corretamente.")

if __name__ == "__main__":
    create_admin()

import logging
import os
import django
from django.contrib.auth import get_user_model

# Configura o ambiente Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

# Mensagens só pelo log com nível (LGPD-23); o logger "core" vai ao console
logger = logging.getLogger('core.create_admin')

def create_admin():
    """
    Cria o primeiro administrador só quando não há nenhum administrador ativo
    e nunca altera contas existentes (PERM-07). Antes, o script repromovia o
    e-mail configurado a cada boot e desfazia os rebaixamentos do painel.
    """
    User = get_user_model()
    
    username = os.getenv('DJANGO_SUPERUSER_NAME', 'Admin')
    email = os.getenv('DJANGO_SUPERUSER_EMAIL')
    password = os.getenv('DJANGO_SUPERUSER_PASSWORD')

    if not email or not password:
        logger.info("Pulei a criação de admin: DJANGO_SUPERUSER_EMAIL ou DJANGO_SUPERUSER_PASSWORD não configurados.")
        return

    if User.objects.filter(role='ADMIN', is_active=True).exists():
        logger.info("Já existe um administrador ativo; nenhuma conta foi criada ou alterada.")
        return

    if User.objects.filter(email__iexact=email).exists():
        logger.warning(
            "Não há administrador ativo, e o e-mail configurado já pertence a uma conta. "
            "Nenhuma conta foi alterada: promova um administrador manualmente."
        )
        return

    # O primeiro administrador também entra no admin do Django
    User.objects.create_superuser(email=email, password=password, name=username)
    logger.info("Administrador criado com sucesso.")

if __name__ == "__main__":
    create_admin()

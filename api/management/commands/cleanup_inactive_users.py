from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from api.models import SystemLog

User = get_user_model()

class Command(BaseCommand):
    help = 'Remove usuários que não verificaram o e-mail em até 7 dias após o cadastro'

    def handle(self, *args, **options):
        self.stdout.write("Iniciando limpeza de usuários inativos...")
        
        # Data de corte: 7 dias atrás
        cutoff_date = timezone.now() - timedelta(days=7)
        
        # Filtro: não verificados, inativos e criados antes da data de corte
        inactive_users = User.objects.filter(
            email_verified=False,
            is_active=False,
            created_at__lt=cutoff_date
        )
        
        count = inactive_users.count()
        
        if count > 0:
            emails = [u.email for u in inactive_users]
            inactive_users.delete()
            
            # Registrar no log do sistema
            SystemLog.objects.create(
                action="CLEANUP_INACTIVE_USERS",
                description=f"Limpeza semanal automática: {count} usuários removidos por falta de verificação. Emails: {', '.join(emails[:10])}{'...' if count > 10 else ''}",
                admin_name="Sistema (Tarefa Agendada)"
            )
            
            self.stdout.write(self.style.SUCCESS(f"Sucesso: {count} usuários removidos."))
        else:
            self.stdout.write("Nenhum usuário inativo encontrado para remoção.")

from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse

def send_verification_email(user, token):
    """
    Envia email de verificação para o usuário.
    """
    # Em produção, usaria um domínio configurado no settings
    # Como não temos o front ainda, vamos montar uma URL que bata na API para teste ou apenas exibir o token
    verification_url = f"http://localhost:8000/api/auth/verify-email/?token={token.token}"
    
    subject = "Verifique seu e-mail no Fluxar"
    message = f"""
    Olá, {user.name}!
    
    Obrigado por se cadastrar no Fluxar.
    Para ativar sua conta, use o token abaixo ou o link (se estivesse no front):
    
    Token: {token.token}
    Link: {verification_url}
    
    Este link expira em breve.
    """
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@fluxar.com',
        [user.email],
        fail_silently=False,
    )

def send_password_reset_email(user, token):
    """
    Envia email de redefinição de senha.
    """
    # Em produção, apontaria para o frontend: http://fluxar.com/reset-password?token=...
    reset_url = f"http://localhost:8000/api/auth/reset-password-frontend-stub/?token={token.token}"
    
    subject = "Redefinição de senha no Fluxar"
    message = f"""
    Olá, {user.name}.
    
    Recebemos uma solicitação para redefinir sua senha.
    Use o token abaixo para prosseguir:
    
    Token: {token.token}
    
    Se você não solicitou isso, ignore este e-mail.
    """
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@fluxar.com',
        [user.email],
        fail_silently=False,
    )

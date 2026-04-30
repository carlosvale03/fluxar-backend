import os
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_verification_email(user, token):
    """
    Envia email de verificação premium via Django SMTP (Gmail).
    """
    # Usa variável de ambiente ou fallback para localhost
    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
    verification_url = f"{frontend_url}/auth/verify-email?token={token.token}"
    
    subject = "Ative sua conta no Fluxar"
    
    html_content = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #1a1a1a;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #7c3aed; font-size: 28px; font-weight: 800;">Fluxar</h1>
        </div>
        
        <h2 style="font-size: 20px; font-weight: 700; margin-bottom: 16px;">Olá, {user.name}!</h2>
        
        <p style="font-size: 16px; line-height: 1.6; margin-bottom: 24px;">
            Obrigado por se cadastrar no Fluxar! Estamos felizes em ter você conosco. 
            Para começar a organizar sua vida financeira, precisamos apenas que confirme seu e-mail.
        </p>
        
        <div style="text-align: center; margin: 40px 0;">
            <a href="{verification_url}" 
               style="background-color: #7c3aed; color: white; padding: 16px 32px; border-radius: 12px; text-decoration: none; font-weight: 700; font-size: 16px; display: inline-block; box-shadow: 0 4px 6px -1px rgba(124, 58, 237, 0.2);">
                Confirmar meu E-mail
            </a>
        </div>
        
        <p style="font-size: 14px; color: #666; margin-top: 40px; text-align: center;">
            Se o botão acima não funcionar, copie e cole o link abaixo no seu navegador:<br>
            <span style="color: #7c3aed;">{verification_url}</span>
        </p>
        
        <hr style="border: 0; border-top: 1px solid #eee; margin: 40px 0;">
        
        <p style="font-size: 12px; color: #999; text-align: center;">
            Este e-mail foi enviado automaticamente pelo Fluxar.<br>
            Se você não criou esta conta, pode ignorar este e-mail com segurança.
        </p>
    </div>
    """
    
    try:
        send_mail(
            subject=subject,
            message=f"Olá {user.name}, verifique seu e-mail em: {verification_url}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_content,
            fail_silently=False,
        )
    except Exception as e:
        logger.error(f"Erro ao enviar email de verificação: {str(e)}")
        print(f"DEBUG: Falha no SMTP. Link de verificação: {verification_url}")

def send_password_reset_email(user, token):
    """
    Envia email de redefinição de senha premium via Django SMTP (Gmail).
    """
    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
    reset_url = f"{frontend_url}/auth/reset-password?token={token.token}"
    
    subject = "Redefinição de senha - Fluxar"
    
    html_content = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #1a1a1a;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #7c3aed; font-size: 28px; font-weight: 800;">Fluxar</h1>
        </div>
        
        <h2 style="font-size: 20px; font-weight: 700; margin-bottom: 16px;">Olá, {user.name}.</h2>
        
        <p style="font-size: 16px; line-height: 1.6; margin-bottom: 24px;">
            Recebemos uma solicitação para redefinir a senha da sua conta no Fluxar.
            Clique no botão abaixo para escolher uma nova senha:
        </p>
        
        <div style="text-align: center; margin: 40px 0;">
            <a href="{reset_url}" 
               style="background-color: #1a1a1a; color: white; padding: 16px 32px; border-radius: 12px; text-decoration: none; font-weight: 700; font-size: 16px; display: inline-block;">
                Redefinir Minha Senha
            </a>
        </div>
        
        <p style="font-size: 14px; color: #666; margin-top: 40px; text-align: center;">
            Este link é válido por 1 hora. Se você não solicitou isso, pode ignorar este e-mail.
        </p>
        
        <hr style="border: 0; border-top: 1px solid #eee; margin: 40px 0;">
        
        <p style="font-size: 12px; color: #999; text-align: center;">
            Equipe Fluxar
        </p>
    </div>
    """
    
    try:
        send_mail(
            subject=subject,
            message=f"Olá {user.name}, redefina sua senha em: {reset_url}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_content,
            fail_silently=False,
        )
    except Exception as e:
        logger.error(f"Erro ao enviar email de reset de senha: {str(e)}")
        print(f"DEBUG: Falha no SMTP. Link de reset: {reset_url}")

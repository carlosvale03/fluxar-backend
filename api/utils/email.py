import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)

def send_welcome_email(user_email: str, user_name: str) -> None:
    """
    Envia um e-mail de boas-vindas para o novo usuário, mencionando o recurso Plus Goals.
    """
    subject = "Bem-vindo(a) ao Fluxar! Assuma o controle da sua vida financeira 🚀"
    
    message_text = f"""Olá {user_name},

Seja muito bem-vindo(a) ao Fluxar! Estamos muito felizes em ter você conosco.

O Fluxar foi desenhado para te ajudar a ter total clareza e controle sobre suas finanças. Comece agora mesmo registrando suas receitas e despesas.

Sabia que você pode ir além? 
Com o nosso recurso premium "Plus Goals" (Metas e Projeções), você pode criar objetivos financeiros claros, projetar o seu futuro e tomar decisões com muito mais segurança.

Acesse a plataforma e descubra tudo o que preparamos para você!

Um abraço,
Equipe Fluxar
"""

    html_content = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #1a1a1a;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #7c3aed; font-size: 28px; font-weight: 800;">Fluxar</h1>
        </div>
        
        <h2 style="font-size: 20px; font-weight: 700; margin-bottom: 16px;">Olá, {user_name}!</h2>
        
        <p style="font-size: 16px; line-height: 1.6; margin-bottom: 24px;">
            Seja muito bem-vindo(a) ao Fluxar! Estamos muito felizes em ter você conosco.
        </p>
        
        <p style="font-size: 16px; line-height: 1.6; margin-bottom: 24px;">
            O Fluxar foi desenhado para te ajudar a ter total clareza e controle sobre suas finanças. Comece agora mesmo registrando suas primeiras receitas e despesas.
        </p>
        
        <div style="background-color: #f3f4f6; padding: 20px; border-radius: 8px; margin: 30px 0;">
            <h3 style="color: #7c3aed; margin-top: 0;">🚀 Desbloqueie o Plus Goals</h3>
            <p style="font-size: 15px; margin-bottom: 0;">
                Sabia que você pode ir além? Com o nosso recurso premium <strong>Plus Goals</strong> (Metas e Projeções), você pode criar objetivos financeiros claros, projetar o seu futuro e tomar decisões com muito mais segurança. Assuma o controle total da sua vida financeira!
            </p>
        </div>
        
        <p style="font-size: 16px; line-height: 1.6; margin-bottom: 24px;">
            Acesse a plataforma e descubra tudo o que preparamos para você!
        </p>
        
        <hr style="border: 0; border-top: 1px solid #eee; margin: 40px 0;">
        
        <p style="font-size: 14px; color: #999; text-align: center;">
            Um abraço,<br>
            <strong>Equipe Fluxar</strong>
        </p>
    </div>
    """

    try:
        send_mail(
            subject=subject,
            message=message_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            html_message=html_content,
            fail_silently=False,
        )
        logger.info(f"E-mail de boas-vindas enviado com sucesso para {user_email}.")
    except Exception as e:
        logger.error(f"Falha ao enviar e-mail de boas-vindas para {user_email}: {str(e)}")

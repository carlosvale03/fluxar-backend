import logging
import os

import requests
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)
EMAILJS_API_URL = "https://api.emailjs.com/api/v1.0/email/send"


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _mask_email(email):
    if not email or "@" not in email:
        return "<invalid-email>"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[:2] + "***"
    return f"{masked_local}@{domain}"


def _debug_log(message):
    if _env_bool("EMAIL_DEBUG_LOGS", False):
        logger.warning("[EMAIL DEBUG] %s", message)


def _get_frontend_url():
    frontend_url = os.getenv('FRONTEND_URL') or getattr(settings, 'FRONTEND_URL', None)
    if frontend_url:
        return frontend_url.rstrip('/')

    fallback_url = 'http://localhost:3000'
    if not settings.DEBUG:
        logger.warning(
            "FRONTEND_URL nao configurada em producao. Usando fallback %s",
            fallback_url,
        )
    return fallback_url


def _send_via_resend(subject, html_content, to_email):
    api_key = os.getenv('RESEND_API_KEY')
    if not api_key:
        raise ValueError("RESEND_API_KEY nao configurada")

    import resend

    _debug_log(
        f"Tentando Resend para {_mask_email(to_email)} com from={settings.DEFAULT_FROM_EMAIL}"
    )

    resend.api_key = api_key
    resend.Emails.send({
        "from": settings.DEFAULT_FROM_EMAIL,
        "to": [to_email],
        "subject": subject,
        "html": html_content,
    })
    logger.info("Email enviado via Resend para %s", to_email)


def _send_via_smtp(subject, plain_text, html_content, to_email):
    _debug_log(
        f"Tentando SMTP para {_mask_email(to_email)} host={settings.EMAIL_HOST} port={settings.EMAIL_PORT}"
    )
    send_mail(
        subject=subject,
        message=plain_text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[to_email],
        html_message=html_content,
        fail_silently=False,
    )
    logger.info("Email enviado via SMTP fallback para %s", to_email)


def _send_via_emailjs(subject, plain_text, html_content, to_email, to_name):
    service_id = os.getenv('EMAILJS_SERVICE_ID')
    template_id = os.getenv('EMAILJS_TEMPLATE_ID')
    public_key = os.getenv('EMAILJS_PUBLIC_KEY')
    private_key = os.getenv('EMAILJS_PRIVATE_KEY')

    missing = [
        env_name
        for env_name, value in (
            ('EMAILJS_SERVICE_ID', service_id),
            ('EMAILJS_TEMPLATE_ID', template_id),
            ('EMAILJS_PUBLIC_KEY', public_key),
            ('EMAILJS_PRIVATE_KEY', private_key),
        )
        if not value
    ]
    if missing:
        raise ValueError(f"Variaveis do EmailJS ausentes: {', '.join(missing)}")

    _debug_log(
        "Tentando EmailJS com service_id=%s template_id=%s public_key_set=%s private_key_set=%s para %s"
        % (
            service_id,
            template_id,
            bool(public_key),
            bool(private_key),
            _mask_email(to_email),
        )
    )

    payload = {
        "service_id": service_id,
        "template_id": template_id,
        "user_id": public_key,
        "accessToken": private_key,
        "template_params": {
            "to_email": to_email,
            "to_name": to_name,
            "subject": subject,
            "message": plain_text,
            "html_message": html_content,
        },
    }

    response = requests.post(EMAILJS_API_URL, json=payload, timeout=15)
    _debug_log(
        f"EmailJS respondeu status={response.status_code} body={response.text[:200]}"
    )
    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"EmailJS retornou {response.status_code}: {response.text[:300]}"
        )

    logger.info("Email enviado via EmailJS fallback para %s", to_email)


def _send_with_fallback_chain(
    subject,
    plain_text,
    html_content,
    to_email,
    to_name,
    emailjs_plain_text=None,
    emailjs_html_content=None,
):
    resend_enabled = _env_bool('ENABLE_RESEND_PROVIDER', True)
    smtp_enabled = _env_bool('ENABLE_SMTP_FALLBACK', True)
    emailjs_enabled = _env_bool('USE_EMAILJS_TESTING_FALLBACK', False)

    errors = []
    _debug_log(
        "Inicio cadeia de envio para %s | resend=%s smtp=%s emailjs=%s"
        % (_mask_email(to_email), resend_enabled, smtp_enabled, emailjs_enabled)
    )

    if resend_enabled:
        try:
            _send_via_resend(subject, html_content, to_email)
            return
        except Exception as exc:
            errors.append(f"Resend: {exc}")
            logger.warning("Falha no Resend. Tentando proximo fallback. erro=%s", exc)
    else:
        logger.info("Resend ignorado por ENABLE_RESEND_PROVIDER=False")

    if smtp_enabled:
        try:
            _send_via_smtp(subject, plain_text, html_content, to_email)
            return
        except Exception as exc:
            errors.append(f"SMTP: {exc}")
            logger.warning("Falha no SMTP fallback. Avaliando EmailJS. erro=%s", exc)
    else:
        logger.info("SMTP fallback ignorado por ENABLE_SMTP_FALLBACK=False")

    if emailjs_enabled:
        try:
            _send_via_emailjs(
                subject,
                emailjs_plain_text if emailjs_plain_text is not None else plain_text,
                emailjs_html_content if emailjs_html_content is not None else html_content,
                to_email,
                to_name,
            )
            return
        except Exception as exc:
            errors.append(f"EmailJS: {exc}")
            logger.error("Falha no EmailJS fallback: %s", exc)
    else:
        logger.info("EmailJS ignorado por USE_EMAILJS_TESTING_FALLBACK=False")

    raise RuntimeError("Falha no envio de email. " + " | ".join(errors))

def send_verification_email(user, token):
    """
    Envia email de verificação premium via Django SMTP (Gmail).
    """
    frontend_url = _get_frontend_url()
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

    emailjs_plain_text = "Confirme seu e-mail para ativar sua conta no Fluxar."
    emailjs_html_content = f"""
    <p style="font-size: 16px; line-height: 1.6; margin: 0 0 24px; color: #374151;">
        Obrigado por se cadastrar no Fluxar! Para comecar a organizar sua vida financeira,
        confirme seu e-mail no botao abaixo.
    </p>

    <div style="text-align: center; margin: 30px 0;">
        <a href="{verification_url}"
           style="background-color: #7c3aed; color: #ffffff; padding: 14px 28px; border-radius: 10px; text-decoration: none; font-weight: 700; font-size: 15px; display: inline-block;">
            Confirmar meu e-mail
        </a>
    </div>

    <p style="font-size: 13px; color: #6b7280; margin: 18px 0 0;">
        Se o botao nao funcionar, copie e cole este link no navegador:<br>
        <a href="{verification_url}" style="color:#6d28d9;">{verification_url}</a>
    </p>
    """
    
    try:
        _debug_log(
            f"Disparando email de verificacao para {_mask_email(user.email)}"
        )
        _send_with_fallback_chain(
            subject=subject,
            plain_text=f"Ola {user.name}, verifique seu email em: {verification_url}",
            html_content=html_content,
            to_email=user.email,
            to_name=user.name,
            emailjs_plain_text=emailjs_plain_text,
            emailjs_html_content=emailjs_html_content,
        )
    except Exception as exc:
        logger.exception("Erro ao enviar email de verificacao para %s: %s", user.email, exc)

def send_password_reset_email(user, token):
    """
    Envia email de redefinição de senha premium via Django SMTP (Gmail).
    """
    frontend_url = _get_frontend_url()
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

    emailjs_plain_text = "Recebemos uma solicitacao para redefinir sua senha no Fluxar."
    emailjs_html_content = f"""
    <p style="font-size: 16px; line-height: 1.6; margin: 0 0 24px; color: #374151;">
        Recebemos uma solicitacao para redefinir a senha da sua conta no Fluxar.
        Clique no botao abaixo para escolher uma nova senha:
    </p>

    <div style="text-align: center; margin: 30px 0;">
        <a href="{reset_url}"
           style="background-color: #111827; color: #ffffff; padding: 14px 28px; border-radius: 10px; text-decoration: none; font-weight: 700; font-size: 15px; display: inline-block;">
            Redefinir minha senha
        </a>
    </div>

    <p style="font-size: 13px; color: #6b7280; margin: 18px 0 0;">
        Este link e valido por 1 hora. Se o botao nao funcionar, use este link:<br>
        <a href="{reset_url}" style="color:#2563eb;">{reset_url}</a>
    </p>
    """
    
    try:
        _debug_log(
            f"Disparando email de reset para {_mask_email(user.email)}"
        )
        _send_with_fallback_chain(
            subject=subject,
            plain_text=f"Ola {user.name}, redefina sua senha em: {reset_url}",
            html_content=html_content,
            to_email=user.email,
            to_name=user.name,
            emailjs_plain_text=emailjs_plain_text,
            emailjs_html_content=emailjs_html_content,
        )
    except Exception as exc:
        logger.exception("Erro ao enviar email de reset para %s: %s", user.email, exc)

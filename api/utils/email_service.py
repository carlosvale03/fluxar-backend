"""
E-mails transacionais do Fluxar (AD-011).

O envio acontece na própria requisição: tenta o Resend e depois o SMTP, com
no máximo 10 segundos somando os dois. O EmailJS só entra em
desenvolvimento, com DEBUG ligado e a flag de teste. Todo texto do usuário é
escapado antes de entrar no e-mail, e os logs trazem só o endereço mascarado
(AD-019).
"""
import logging
import os
import time

import requests
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.utils.html import escape

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
EMAILJS_API_URL = "https://api.emailjs.com/api/v1.0/email/send"
PRAZO_TOTAL_SEGUNDOS = 10


def _mask_email(email):
    if not email or "@" not in email:
        return "<invalid-email>"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[:2] + "***"
    return f"{masked_local}@{domain}"


def _get_frontend_url():
    return settings.FRONTEND_URL.rstrip('/')


def _send_via_resend(subject, plain_text, html_content, to_email, timeout):
    api_key = os.getenv('RESEND_API_KEY')
    if not api_key:
        raise ValueError("RESEND_API_KEY nao configurada")

    response = requests.post(
        RESEND_API_URL,
        headers={'Authorization': f'Bearer {api_key}'},
        json={
            "from": settings.DEFAULT_FROM_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html_content,
            "text": plain_text,
        },
        timeout=timeout,
    )
    if not 200 <= response.status_code < 300:
        raise RuntimeError(f"Resend retornou {response.status_code}")


def _send_via_smtp(subject, plain_text, html_content, to_email, timeout):
    connection = get_connection(timeout=timeout)
    message = EmailMultiAlternatives(
        subject=subject,
        body=plain_text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
        connection=connection,
    )
    message.attach_alternative(html_content, "text/html")
    message.send(fail_silently=False)


def _send_via_emailjs(subject, plain_text, html_content, to_email, to_name, timeout):
    credenciais = {
        'EMAILJS_SERVICE_ID': settings.EMAILJS_SERVICE_ID,
        'EMAILJS_TEMPLATE_ID': settings.EMAILJS_TEMPLATE_ID,
        'EMAILJS_PUBLIC_KEY': settings.EMAILJS_PUBLIC_KEY,
        'EMAILJS_PRIVATE_KEY': settings.EMAILJS_PRIVATE_KEY,
    }
    missing = [nome for nome, valor in credenciais.items() if not valor]
    if missing:
        raise ValueError(f"Variaveis do EmailJS ausentes: {', '.join(missing)}")

    payload = {
        "service_id": credenciais['EMAILJS_SERVICE_ID'],
        "template_id": credenciais['EMAILJS_TEMPLATE_ID'],
        "user_id": credenciais['EMAILJS_PUBLIC_KEY'],
        "accessToken": credenciais['EMAILJS_PRIVATE_KEY'],
        "template_params": {
            "to_email": to_email,
            "to_name": to_name,
            "subject": subject,
            "message": plain_text,
            "html_message": html_content,
        },
    }
    response = requests.post(EMAILJS_API_URL, json=payload, timeout=timeout)
    if response.status_code not in (200, 201):
        raise RuntimeError(f"EmailJS retornou {response.status_code}")


def _send_with_fallback_chain(
    tipo,
    subject,
    plain_text,
    html_content,
    to_email,
    to_name,
    emailjs_plain_text=None,
    emailjs_html_content=None,
):
    """
    Tenta cada provedor em ordem dentro do prazo total e devolve True se
    algum enviou. `to_name` já chega escapado.
    """
    provedores = []
    if settings.ENABLE_RESEND_PROVIDER:
        provedores.append((
            'resend',
            lambda prazo: _send_via_resend(subject, plain_text, html_content, to_email, prazo),
        ))
    if settings.ENABLE_SMTP_FALLBACK:
        provedores.append((
            'smtp',
            lambda prazo: _send_via_smtp(subject, plain_text, html_content, to_email, prazo),
        ))
    # AUTH-29: o EmailJS é só para testes e nunca roda em produção
    if settings.DEBUG and settings.USE_EMAILJS_TESTING_FALLBACK:
        provedores.append((
            'emailjs',
            lambda prazo: _send_via_emailjs(
                subject,
                emailjs_plain_text if emailjs_plain_text is not None else plain_text,
                emailjs_html_content if emailjs_html_content is not None else html_content,
                to_email,
                to_name,
                prazo,
            ),
        ))

    destinatario = _mask_email(to_email)
    inicio = time.monotonic()
    for provedor, enviar in provedores:
        restante = PRAZO_TOTAL_SEGUNDOS - (time.monotonic() - inicio)
        if restante <= 0:
            logger.warning(
                "E-mail tipo=%s provedor=%s resultado=sem_tempo destinatario=%s",
                tipo, provedor, destinatario,
            )
            continue
        try:
            enviar(restante)
        except Exception as exc:
            # Só a classe do erro: a mensagem pode trazer o endereço inteiro
            logger.warning(
                "E-mail tipo=%s provedor=%s resultado=falha erro=%s destinatario=%s",
                tipo, provedor, type(exc).__name__, destinatario,
            )
            continue
        logger.info(
            "E-mail tipo=%s provedor=%s resultado=enviado destinatario=%s",
            tipo, provedor, destinatario,
        )
        return True

    logger.error(
        "E-mail tipo=%s resultado=nao_enviado destinatario=%s",
        tipo, destinatario,
    )
    return False


def send_verification_email(user, token):
    """
    Envia o e-mail de verificação. Devolve True se algum provedor enviou.
    """
    frontend_url = _get_frontend_url()
    verification_url = f"{frontend_url}/auth/verify-email?token={token.token}"
    nome = escape(user.name)

    subject = "Ative sua conta no Fluxar"

    html_content = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #1a1a1a;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #7c3aed; font-size: 28px; font-weight: 800;">Fluxar</h1>
        </div>

        <h2 style="font-size: 20px; font-weight: 700; margin-bottom: 16px;">Olá, {nome}!</h2>

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

    return _send_with_fallback_chain(
        tipo='verificacao',
        subject=subject,
        plain_text=f"Ola {nome}, verifique seu email em: {verification_url}",
        html_content=html_content,
        to_email=user.email,
        to_name=nome,
        emailjs_plain_text=emailjs_plain_text,
        emailjs_html_content=emailjs_html_content,
    )


def send_password_reset_email(user, token):
    """
    Envia o e-mail de redefinição de senha. Devolve True se algum provedor enviou.
    """
    frontend_url = _get_frontend_url()
    reset_url = f"{frontend_url}/auth/reset-password?token={token.token}"
    nome = escape(user.name)

    subject = "Redefinição de senha - Fluxar"

    html_content = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #1a1a1a;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #7c3aed; font-size: 28px; font-weight: 800;">Fluxar</h1>
        </div>

        <h2 style="font-size: 20px; font-weight: 700; margin-bottom: 16px;">Olá, {nome}.</h2>

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

    return _send_with_fallback_chain(
        tipo='redefinicao',
        subject=subject,
        plain_text=f"Ola {nome}, redefina sua senha em: {reset_url}",
        html_content=html_content,
        to_email=user.email,
        to_name=nome,
        emailjs_plain_text=emailjs_plain_text,
        emailjs_html_content=emailjs_html_content,
    )

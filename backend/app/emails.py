"""Envio de e-mails.

Sem SMTP configurado, o e-mail é apenas registrado no log (útil enquanto
o projeto não tem um serviço de e-mail). No desenvolvimento, o Docker Compose
usa o Mailpit, que captura os e-mails e mostra em http://localhost:8025.
"""

import logging
import smtplib
from email.message import EmailMessage

from app.config import get_settings

log = logging.getLogger("dbeeas.emails")


def enviar_email(para: str, assunto: str, texto: str) -> None:
    s = get_settings()
    if not s.smtp_host:
        log.warning("SMTP não configurado. E-mail para %s: %s\n%s", para, assunto, texto)
        return

    msg = EmailMessage()
    msg["From"] = s.email_remetente
    msg["To"] = para
    msg["Subject"] = assunto
    msg.set_content(texto)

    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_porta, timeout=15) as smtp:
            if s.smtp_tls:
                smtp.starttls()
            if s.smtp_usuario:
                smtp.login(s.smtp_usuario, s.smtp_senha or "")
            smtp.send_message(msg)
    except (OSError, smtplib.SMTPException):
        # Falha no e-mail não deve derrubar a requisição do usuário
        log.exception("Falha ao enviar e-mail para %s", para)


def email_redefinir_senha(para: str, nome: str, link: str, minutos: int) -> None:
    enviar_email(
        para,
        "DBeeAS – Redefinição de senha",
        f"Olá, {nome}.\n\n"
        "Recebemos um pedido para redefinir a senha da sua conta no DBeeAS.\n"
        f"Para criar uma nova senha, acesse o link abaixo (válido por {minutos} minutos):\n\n"
        f"{link}\n\n"
        "Se você não fez esse pedido, ignore este e-mail. Sua senha continua a mesma.\n\n"
        "Equipe DBeeAS",
    )

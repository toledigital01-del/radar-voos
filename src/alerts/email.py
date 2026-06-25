import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import EMAIL_FROM
from src.logger import get_logger

log = get_logger()

GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")


def enviar_email(destinatario: str, assunto: str, corpo: str) -> bool:
    if not EMAIL_FROM or not GMAIL_APP_PASSWORD:
        log.warning("Email não configurado (EMAIL_FROM ou GMAIL_APP_PASSWORD ausente)")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"] = EMAIL_FROM
        msg["To"] = destinatario
        msg.attach(MIMEText(corpo, "plain", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_FROM, GMAIL_APP_PASSWORD)
            smtp.sendmail(EMAIL_FROM, destinatario, msg.as_string())

        log.info("Email enviado para %s", destinatario)
        return True
    except Exception as e:
        log.error("Email erro [%s]: %s", destinatario, e)
        return False

import truststore
truststore.inject_into_ssl()

import sendgrid
from sendgrid.helpers.mail import Mail
from config import SENDGRID_API_KEY, EMAIL_FROM
from src.logger import get_logger

log = get_logger()


def enviar_email(destinatario: str, assunto: str, corpo: str) -> bool:
    if not SENDGRID_API_KEY:
        log.warning("Email (SendGrid) não configurado")
        return False

    try:
        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
        message = Mail(
            from_email=EMAIL_FROM,
            to_emails=destinatario,
            subject=assunto,
            plain_text_content=corpo,
        )
        r = sg.send(message)
        log.info("Email enviado para %s: HTTP %s", destinatario, r.status_code)
        return True
    except Exception as e:
        log.error("Email erro [%s]: %s", destinatario, e)
        return False

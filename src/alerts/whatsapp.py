import truststore
truststore.inject_into_ssl()

from twilio.rest import Client
from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM
from src.logger import get_logger

log = get_logger()


def enviar_whatsapp(telefone: str, mensagem: str) -> bool:
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        log.warning("WhatsApp (Twilio) não configurado")
        return False

    numero = telefone.replace("whatsapp:", "").strip()
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            body=mensagem,
            to=f"whatsapp:{numero}",
        )
        log.info("WhatsApp enviado para %s: %s", numero, msg.sid)
        return True
    except Exception as e:
        log.error("WhatsApp erro [%s]: %s", numero, e)
        return False

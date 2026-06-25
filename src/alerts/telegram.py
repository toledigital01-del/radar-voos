import truststore
truststore.inject_into_ssl()

import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
from src.logger import get_logger

log = get_logger()


def enviar_telegram(mensagem: str, chat_id: str = None) -> bool:
    alvo = chat_id or TELEGRAM_CHANNEL_ID
    if not TELEGRAM_BOT_TOKEN or not alvo:
        log.warning("Telegram não configurado (TOKEN ou CHANNEL_ID ausente)")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": alvo,
        "text": mensagem,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            log.info("Telegram enviado para %s", alvo)
            return True
        log.error("Telegram falhou [%s]: HTTP %s — %s", alvo, r.status_code, r.text[:200])
        return False
    except Exception as e:
        log.error("Telegram erro [%s]: %s", alvo, e)
        return False

import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

BRASILIA = ZoneInfo("America/Sao_Paulo")


def now_brasilia() -> datetime:
    return datetime.now(BRASILIA)

# SerpApi — Google Flights (cadastro em serpapi.com)
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

# Banco de dados
_raw_db_url = os.getenv("DATABASE_URL", "sqlite:///voos.db")
# Railway fornece "postgres://..." (formato antigo) — SQLAlchemy 2.x exige "postgresql://"
DATABASE_URL = _raw_db_url.replace("postgres://", "postgresql://", 1) if _raw_db_url.startswith("postgres://") else _raw_db_url

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

# Twilio / WhatsApp
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")

# SendGrid / Email
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM")

# Moeda
MOEDA = "BRL"

# Padrões — sobrescritos pelo user_config.json se existir
_DEFAULTS = {
    "rotas": [
        {"origem": "GRU", "destino": "CDG"},
        {"origem": "GIG", "destino": "LIS"},
        {"origem": "GRU", "destino": "MIA"},
        {"origem": "POA", "destino": "EZE"},
        {"origem": "GRU", "destino": "JFK"},
        {"origem": "FOR", "destino": "LIS"},
        {"origem": "GRU", "destino": "ORD"},
        {"origem": "GRU", "destino": "MAD"},
    ],
    "dias_antecedencia": [30, 60, 90, 120],
    "threshold_desconto": 0.30,
    "intervalo_horas": 1,
}

USER_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_config.json")


def _load():
    if os.path.exists(USER_CONFIG_PATH):
        with open(USER_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


_uc = _load()

ROTAS_MONITORADAS = _uc.get("rotas", _DEFAULTS["rotas"])
DIAS_ANTECEDENCIA = _uc.get("dias_antecedencia", _DEFAULTS["dias_antecedencia"])
THRESHOLD_DESCONTO = _uc.get("threshold_desconto", _DEFAULTS["threshold_desconto"])
INTERVALO_HORAS = _uc.get("intervalo_horas", _DEFAULTS["intervalo_horas"])

# Códigos de cidade IATA que agrupam múltiplos aeroportos
CITY_GROUPS = {
    # Brasil
    "SAO": {"nome": "São Paulo",      "aeroportos": ["GRU", "CGH", "VCP"]},
    "RIO": {"nome": "Rio de Janeiro", "aeroportos": ["GIG", "SDU"]},
    "BHZ": {"nome": "Belo Horizonte", "aeroportos": ["CNF", "PLU"]},
    "BSB": {"nome": "Brasília",       "aeroportos": ["BSB"]},
    # América do Norte
    "NYC": {"nome": "Nova York",      "aeroportos": ["JFK", "EWR", "LGA"]},
    "CHI": {"nome": "Chicago",        "aeroportos": ["ORD", "MDW"]},
    "WAS": {"nome": "Washington",     "aeroportos": ["DCA", "IAD", "BWI"]},
    "LAX": {"nome": "Los Angeles",    "aeroportos": ["LAX", "BUR", "LGB"]},
    "MIA": {"nome": "Miami",          "aeroportos": ["MIA", "FLL"]},
    # Europa
    "PAR": {"nome": "Paris",          "aeroportos": ["CDG", "ORY"]},
    "LON": {"nome": "Londres",        "aeroportos": ["LHR", "LGW", "STN", "LCY"]},
    "MIL": {"nome": "Milão",          "aeroportos": ["MXP", "LIN"]},
    "ROM": {"nome": "Roma",           "aeroportos": ["FCO", "CIA"]},
    "MAD": {"nome": "Madri",          "aeroportos": ["MAD"]},
    "LIS": {"nome": "Lisboa",         "aeroportos": ["LIS"]},
    # América do Sul
    "BUE": {"nome": "Buenos Aires",   "aeroportos": ["EZE", "AEP"]},
    "SCL": {"nome": "Santiago",       "aeroportos": ["SCL"]},
    # Ásia
    "TYO": {"nome": "Tóquio",         "aeroportos": ["NRT", "HND"]},
    "SHA": {"nome": "Shanghai",       "aeroportos": ["PVG", "SHA"]},
}

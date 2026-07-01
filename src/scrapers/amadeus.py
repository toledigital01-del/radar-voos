"""
Scraper usando SerpApi — Google Flights
Documentação: https://serpapi.com/google-flights-api
250 buscas/mês grátis no plano free.
"""

import requests
from config import SERPAPI_KEY
from src.logger import get_logger
from datetime import datetime, timedelta

log = get_logger()

SERPAPI_URL = "https://serpapi.com/search"


def buscar_voos(origem: str, destino: str, data: str, data_volta: str = None) -> list:
    tipo = "1" if data_volta else "2"
    params = {
        "engine": "google_flights",
        "departure_id": origem,
        "arrival_id": destino,
        "outbound_date": data,
        "currency": "BRL",
        "hl": "pt",
        "type": tipo,
        "api_key": SERPAPI_KEY,
    }
    if data_volta:
        params["return_date"] = data_volta

    try:
        r = requests.get(SERPAPI_URL, params=params, timeout=20)
        r.raise_for_status()
        dados = r.json()

        if "error" in dados:
            log.error("SerpAPI [%s→%s %s]: %s", origem, destino, data, dados["error"])
            return []

        resultados = []
        for secao in ("best_flights", "other_flights"):
            for item in dados.get(secao, []):
                voos_item = item.get("flights", [])
                preco = float(item.get("price", 0))
                if preco == 0:
                    continue
                companhia = voos_item[0].get("airline", "?") if voos_item else "?"
                paradas = len(voos_item) - 1 if voos_item else 0
                resultados.append({
                    "origem": origem,
                    "destino": destino,
                    "preco": preco,
                    "companhia": companhia[:10],
                    "paradas": max(paradas, 0),
                    "data_voo": data,
                    "data_volta": data_volta or "",
                    "tipo_viagem": "ida_volta" if data_volta else "ida",
                })

        log.info("%s→%s %s: %d oferta(s)", origem, destino, data, len(resultados))
        return resultados

    except requests.exceptions.HTTPError as e:
        log.error("SerpAPI HTTP [%s→%s %s]: %s", origem, destino, data, e)
        return []
    except Exception as e:
        log.error("SerpAPI erro [%s→%s %s]: %s", origem, destino, data, e)
        return []


def gerar_datas_monitoramento(dias_lista: list) -> list:
    hoje = datetime.now()
    return [(hoje + timedelta(days=d)).strftime("%Y-%m-%d") for d in dias_lista]

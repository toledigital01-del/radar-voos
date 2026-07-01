from datetime import datetime

from config import CITY_GROUPS
from src.scrapers.amadeus import buscar_voos, gerar_datas_monitoramento
from src.database.queries import (
    salvar_preco, media_preco, alerta_recente, salvar_alerta, listar_assinantes,
)
from src.alerts.telegram import enviar_telegram
from src.alerts.whatsapp import enviar_whatsapp
from src.alerts.email import enviar_email
from src.logger import get_logger

log = get_logger()


def _cfg():
    """Lê configuração do banco de dados — persiste entre redeploys."""
    from src.database.queries import get_config_db
    from config import _DEFAULTS
    db_cfg = get_config_db()
    return {
        "rotas": db_cfg.get("rotas", _DEFAULTS["rotas"]),
        "dias_antecedencia": db_cfg.get("dias_antecedencia", _DEFAULTS["dias_antecedencia"]),
        "threshold_desconto": db_cfg.get("threshold_desconto", _DEFAULTS["threshold_desconto"]),
    }


def expandir_rotas(rotas: list) -> list:
    """Expande códigos de cidade (ex: RIO) para aeroportos individuais (GIG, SDU)."""
    resultado = []
    for r in rotas:
        origens = CITY_GROUPS.get(r["origem"], {}).get("aeroportos", [r["origem"]])
        destinos = CITY_GROUPS.get(r["destino"], {}).get("aeroportos", [r["destino"]])
        for o in origens:
            for d in destinos:
                if o != d:
                    resultado.append({"origem": o, "destino": d})
    return resultado


def _link_compra(origem: str, destino: str, data_voo: str) -> str:
    return (
        f"https://www.google.com/travel/flights"
        f"?q=voos+de+{origem}+para+{destino}+em+{data_voo}"
        f"&hl=pt-BR&curr=BRL"
    )


def formatar_alerta(voo: dict, preco_medio: float, desconto_pct: float) -> str:
    link = _link_compra(voo['origem'], voo['destino'], voo['data_voo'])
    return (
        f"✈️ *PROMOÇÃO DETECTADA!*\n\n"
        f"🗺️ Rota: *{voo['origem']} → {voo['destino']}*\n"
        f"💰 Preço: *R$ {voo['preco']:.0f}*\n"
        f"📅 Data do voo: {voo['data_voo']}\n"
        f"🏷️ Companhia: {voo['companhia']}\n"
        f"🛑 Paradas: {voo['paradas']}\n"
        f"📉 *{desconto_pct:.0f}% abaixo da média* (média: R$ {preco_medio:.0f})\n\n"
        f"⚡ Promoções assim somem em horas!\n"
        f"🔗 [Comprar passagem]({link})"
    )


def disparar_alertas(voo: dict, preco_medio: float, desconto_pct: float):
    mensagem = formatar_alerta(voo, preco_medio, desconto_pct)
    log.warning(
        "ALERTA: %s→%s R$%.0f (%.0f%% off | %s)",
        voo["origem"], voo["destino"], voo["preco"], desconto_pct, voo["data_voo"],
    )

    enviar_telegram(mensagem)
    for a in listar_assinantes("telegram"):
        enviar_telegram(mensagem, a.contato)
    for a in listar_assinantes("whatsapp"):
        enviar_whatsapp(a.contato, mensagem)
    for a in listar_assinantes("email"):
        assunto = f"✈️ Promoção {voo['origem']}→{voo['destino']}: R${voo['preco']:.0f}"
        enviar_email(a.contato, assunto, mensagem)

    salvar_alerta({
        "origem": voo["origem"],
        "destino": voo["destino"],
        "preco_alerta": voo["preco"],
        "preco_medio": preco_medio,
        "desconto_pct": desconto_pct,
        "companhia": voo["companhia"],
        "data_voo": voo["data_voo"],
        "link_compra": _link_compra(voo["origem"], voo["destino"], voo["data_voo"]),
    })


def ciclo_monitoramento():
    log.info("═" * 50)
    log.info("Iniciando ciclo de monitoramento")
    log.info("═" * 50)

    cfg = _cfg()
    rotas_monitoradas = cfg["rotas"]
    dias_antecedencia = cfg["dias_antecedencia"]
    threshold_desconto = cfg["threshold_desconto"]

    datas = gerar_datas_monitoramento(dias_antecedencia)
    rotas_expandidas = expandir_rotas(rotas_monitoradas)
    total_alertas = 0

    log.info(
        "%d rota(s) base → %d par(es) de aeroportos × %d data(s) = %d chamadas",
        len(rotas_monitoradas), len(rotas_expandidas), len(datas),
        len(rotas_expandidas) * len(datas),
    )

    for rota in rotas_expandidas:
        origem, destino = rota["origem"], rota["destino"]
        log.info("Monitorando %s → %s", origem, destino)

        for data in datas:
            voos = buscar_voos(origem, destino, data)

            for voo in voos:
                salvar_preco(voo)
                media = media_preco(origem, destino, dias=30)

                if media is None:
                    continue

                queda = (media - voo["preco"]) / media
                if queda >= threshold_desconto:
                    if alerta_recente(origem, destino, horas=6):
                        log.info("Alerta recente para %s→%s, pulando (anti-spam)", origem, destino)
                        continue
                    disparar_alertas(voo, media, queda * 100)
                    total_alertas += 1

    log.info("Ciclo concluído — %d alerta(s) disparado(s)", total_alertas)
    return total_alertas

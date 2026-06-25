"""
radar-voos — Sistema de Monitoramento de Passagens Aéreas
=========================================================
Monitora rotas configuradas via Amadeus API e dispara alertas
via Telegram, WhatsApp e Email quando detecta quedas de preço.

Como usar:
    1. Copie .env.example para .env e preencha as chaves
    2. pip install -r requirements.txt
    3. python main.py

Deploy no Railway:
    railway up
"""

import schedule
import time
import sys
import io
import truststore

truststore.inject_into_ssl()
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.database.models import criar_tabelas
from src.scheduler.jobs import ciclo_monitoramento
from config import INTERVALO_HORAS


def main():
    print(
        "\n"
        "  ██████╗  █████╗ ██████╗  █████╗ ██████╗       ██╗   ██╗ ██████╗  ██████╗ ███████╗\n"
        "  ██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔══██╗      ██║   ██║██╔═══██╗██╔═══██╗██╔════╝\n"
        "  ██████╔╝███████║██║  ██║███████║██████╔╝      ██║   ██║██║   ██║██║   ██║███████╗\n"
        "  ██╔══██╗██╔══██║██║  ██║██╔══██║██╔══██╗      ╚██╗ ██╔╝██║   ██║██║   ██║╚════██║\n"
        "  ██║  ██║██║  ██║██████╔╝██║  ██║██║  ██║       ╚████╔╝ ╚██████╔╝╚██████╔╝███████║\n"
        "  ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝        ╚═══╝   ╚═════╝  ╚═════╝ ╚══════╝\n"
        "\n"
        "  🛫  Monitor de Passagens Aéreas  |  v1.0.0\n"
    )

    # Cria tabelas no banco se ainda não existirem
    criar_tabelas()

    # Primeira execução imediata
    ciclo_monitoramento()

    # Agenda ciclo recorrente
    schedule.every(INTERVALO_HORAS).hours.do(ciclo_monitoramento)
    print(
        f"📡 Próximo ciclo em {INTERVALO_HORAS}h. "
        f"Pressione Ctrl+C para parar.\n"
    )

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        print("\n\n🛑 Monitor encerrado pelo usuário. Até logo!\n")
        sys.exit(0)


if __name__ == "__main__":
    main()

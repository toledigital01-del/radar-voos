"""
Script de configuração inicial — adiciona assinantes e verifica o ambiente.

Uso:
    python setup.py
"""

from src.database.models import criar_tabelas
from src.database.queries import adicionar_assinante, listar_assinantes


def main():
    print("\n🔧 Configuração inicial do Radar Voos\n")

    # Cria tabelas
    criar_tabelas()

    # Exemplo: adicionar assinante Telegram
    # adicionar_assinante("Meu Canal", "telegram", "@meu_canal")

    # Exemplo: adicionar assinante WhatsApp
    # adicionar_assinante("João Silva", "whatsapp", "+5511999998888")

    # Exemplo: adicionar assinante Email
    # adicionar_assinante("Maria", "email", "maria@email.com")

    # Lista assinantes cadastrados
    print("\n📋 Assinantes cadastrados:")
    assinantes = listar_assinantes()
    if assinantes:
        for a in assinantes:
            print(f"  • [{a.canal}] {a.nome}: {a.contato}")
    else:
        print("  (nenhum assinante cadastrado ainda)")
        print(
            "\n  Para adicionar, descomente as linhas de exemplo em setup.py\n"
            "  ou use diretamente:\n\n"
            "    from src.database.queries import adicionar_assinante\n"
            "    adicionar_assinante('Nome', 'telegram', '@canal')\n"
        )


if __name__ == "__main__":
    main()

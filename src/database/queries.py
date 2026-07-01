import json
from sqlalchemy import func
from datetime import datetime, timedelta
from src.database.models import Session, HistoricoPreco, Alerta, Assinante, Configuracao


def salvar_preco(dados: dict):
    """Salva um preço coletado no histórico."""
    session = Session()
    try:
        registro = HistoricoPreco(**dados)
        session.add(registro)
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"❌ Erro ao salvar preço: {e}")
    finally:
        session.close()


def media_preco(origem: str, destino: str, dias: int = 30) -> float | None:
    """Retorna a média de preço dos últimos N dias para uma rota."""
    session = Session()
    try:
        corte = datetime.utcnow() - timedelta(days=dias)
        resultado = (
            session.query(func.avg(HistoricoPreco.preco))
            .filter(
                HistoricoPreco.origem == origem,
                HistoricoPreco.destino == destino,
                HistoricoPreco.capturado_em >= corte,
            )
            .scalar()
        )
        return float(resultado) if resultado else None
    finally:
        session.close()


def alerta_recente(origem: str, destino: str, horas: int = 6) -> bool:
    """Verifica se já foi disparado um alerta recente para evitar spam."""
    session = Session()
    try:
        corte = datetime.utcnow() - timedelta(hours=horas)
        count = (
            session.query(Alerta)
            .filter(
                Alerta.origem == origem,
                Alerta.destino == destino,
                Alerta.enviado_em >= corte,
            )
            .count()
        )
        return count > 0
    finally:
        session.close()


def salvar_alerta(dados: dict):
    """Salva um alerta disparado no banco."""
    session = Session()
    try:
        alerta = Alerta(**dados)
        session.add(alerta)
        session.commit()
        return alerta.id
    except Exception as e:
        session.rollback()
        print(f"❌ Erro ao salvar alerta: {e}")
    finally:
        session.close()


def listar_assinantes(canal: str = None) -> list:
    """Retorna assinantes ativos, filtrando por canal se informado."""
    session = Session()
    try:
        query = session.query(Assinante).filter(Assinante.ativo == True)
        if canal:
            query = query.filter(Assinante.canal == canal)
        # expunge para usar fora da sessão
        resultados = query.all()
        session.expunge_all()
        return resultados
    finally:
        session.close()


def get_config_db() -> dict:
    """Lê configuração persistida no banco de dados."""
    session = Session()
    try:
        rows = session.query(Configuracao).all()
        return {row.chave: json.loads(row.valor) for row in rows}
    except Exception:
        return {}
    finally:
        session.close()


def set_config_db(cfg: dict):
    """Salva (upsert) configuração no banco de dados."""
    session = Session()
    try:
        for chave, valor in cfg.items():
            row = session.query(Configuracao).filter_by(chave=chave).first()
            encoded = json.dumps(valor, ensure_ascii=False)
            if row:
                row.valor = encoded
            else:
                session.add(Configuracao(chave=chave, valor=encoded))
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"❌ Erro ao salvar config no DB: {e}")
    finally:
        session.close()


def adicionar_assinante(nome: str, canal: str, contato: str):
    """Adiciona um novo assinante."""
    session = Session()
    try:
        assinante = Assinante(nome=nome, canal=canal, contato=contato)
        session.add(assinante)
        session.commit()
        print(f"✅ Assinante '{nome}' adicionado ({canal}: {contato})")
    except Exception as e:
        session.rollback()
        print(f"❌ Erro ao adicionar assinante: {e}")
    finally:
        session.close()

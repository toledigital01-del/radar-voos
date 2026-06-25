from sqlalchemy import (
    create_engine, Column, Integer, String,
    Float, DateTime, Boolean, Text
)
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from config import DATABASE_URL

Base = declarative_base()
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


class HistoricoPreco(Base):
    """Registra cada preço coletado para formar o histórico de comparação."""
    __tablename__ = "historico_precos"

    id = Column(Integer, primary_key=True)
    origem = Column(String(3), nullable=False)
    destino = Column(String(3), nullable=False)
    preco = Column(Float, nullable=False)
    moeda = Column(String(3), default="BRL")
    companhia = Column(String(10))
    paradas = Column(Integer, default=0)
    data_voo = Column(String(10))
    capturado_em = Column(DateTime, default=datetime.utcnow)


class Alerta(Base):
    """Registra cada alerta disparado (para evitar spam e auditoria)."""
    __tablename__ = "alertas"

    id = Column(Integer, primary_key=True)
    origem = Column(String(3))
    destino = Column(String(3))
    preco_alerta = Column(Float)
    preco_medio = Column(Float)
    desconto_pct = Column(Float)
    companhia = Column(String(10))
    data_voo = Column(String(10))
    link_compra = Column(Text)
    enviado_em = Column(DateTime, default=datetime.utcnow)


class Assinante(Base):
    """Guarda quem recebe os alertas e por qual canal."""
    __tablename__ = "assinantes"

    id = Column(Integer, primary_key=True)
    nome = Column(String(100))
    canal = Column(String(20))       # telegram | whatsapp | email
    contato = Column(String(200))    # @usuario | +5511... | email@
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)


def criar_tabelas():
    Base.metadata.create_all(engine)
    print("✅ Tabelas criadas com sucesso!")


if __name__ == "__main__":
    criar_tabelas()

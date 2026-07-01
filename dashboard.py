"""
Dashboard web do Radar Voos — FastAPI + HTML embutido.
Rodar: python dashboard.py
Acessar: http://localhost:8000
"""

import io, sys, json, os
import truststore
truststore.inject_into_ssl()
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exception_handlers import http_exception_handler
from pydantic import BaseModel
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import List
import uvicorn

from src.database.models import Session, HistoricoPreco, Alerta, Assinante
from config import USER_CONFIG_PATH, _DEFAULTS, CITY_GROUPS

app = FastAPI(title="Radar Voos Dashboard")

_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": str(exc)})

@app.get("/health")
def health():
    return {"status": "ok"}

@app.on_event("startup")
def startup():
    from src.database.models import criar_tabelas
    try:
        criar_tabelas()
    except Exception as e:
        print(f"DB startup warning: {e}")

    # Inicia scheduler em background thread (substitui main.py no Railway)
    import threading, schedule as _sched, time as _time
    from src.scheduler.jobs import ciclo_monitoramento
    from config import INTERVALO_HORAS

    def _scheduler_loop():
        try:
            print(f"[Scheduler] Iniciando — ciclo a cada {INTERVALO_HORAS}h")
            ciclo_monitoramento()
        except Exception as e:
            print(f"[Scheduler] Erro no ciclo inicial: {e}")
        _sched.every(INTERVALO_HORAS).hours.do(ciclo_monitoramento)
        while True:
            try:
                _sched.run_pending()
            except Exception as e:
                print(f"[Scheduler] Erro: {e}")
            _time.sleep(60)

    threading.Thread(target=_scheduler_loop, daemon=True).start()

# ══════════════════════════════════════════════════════════════════════════════
# Banco de aeroportos — fonte única de verdade para HTML e JS
# ══════════════════════════════════════════════════════════════════════════════

ALL_GROUPS = {
    # Brasil
    "SAO": {"nome": "São Paulo",         "aeroportos": ["GRU", "CGH", "VCP"]},
    "RIO": {"nome": "Rio de Janeiro",    "aeroportos": ["GIG", "SDU"]},
    "BHZ": {"nome": "Belo Horizonte",    "aeroportos": ["CNF", "PLU"]},
    # América do Norte
    "NYC": {"nome": "Nova York",         "aeroportos": ["JFK", "EWR", "LGA"]},
    "CHI": {"nome": "Chicago",           "aeroportos": ["ORD", "MDW"]},
    "WAS": {"nome": "Washington",        "aeroportos": ["DCA", "IAD", "BWI"]},
    "MIA": {"nome": "Miami",             "aeroportos": ["MIA", "FLL"]},
    # Europa
    "PAR": {"nome": "Paris",             "aeroportos": ["CDG", "ORY"]},
    "LON": {"nome": "Londres",           "aeroportos": ["LHR", "LGW", "STN", "LCY"]},
    "MIL": {"nome": "Milão",             "aeroportos": ["MXP", "LIN"]},
    "ROM": {"nome": "Roma",              "aeroportos": ["FCO", "CIA"]},
    # Ásia
    "TYO": {"nome": "Tóquio",            "aeroportos": ["NRT", "HND"]},
    "SHA": {"nome": "Shanghai",          "aeroportos": ["PVG", "SHA"]},
    # América do Sul
    "BUE": {"nome": "Buenos Aires",      "aeroportos": ["EZE", "AEP"]},
}

AIRPORTS_BY_REGION = {
    "Brasil — Sudeste": {
        "GRU": "São Paulo / Guarulhos",
        "CGH": "São Paulo / Congonhas",
        "VCP": "Campinas / Viracopos",
        "GIG": "Rio de Janeiro / Galeão",
        "SDU": "Rio de Janeiro / Santos Dumont",
        "CNF": "Belo Horizonte / Confins",
        "PLU": "Belo Horizonte / Pampulha",
        "VIX": "Vitória / Eurico Salles",
        "UDI": "Uberlândia",
        "RAO": "Ribeirão Preto",
        "SJP": "São José do Rio Preto",
        "IZA": "Juiz de Fora / Zona da Mata",
        "MOC": "Montes Claros",
        "GVR": "Governador Valadares",
        "IPN": "Ipatinga / Usiminas",
        "PPB": "Presidente Prudente",
        "CAW": "Campos dos Goytacazes",
        "BAU": "Bauru / Arealva",
        "POO": "Poços de Caldas",
    },
    "Brasil — Sul": {
        "CWB": "Curitiba / Afonso Pena",
        "FLN": "Florianópolis / Hercílio Luz",
        "POA": "Porto Alegre / Salgado Filho",
        "IGU": "Foz do Iguaçu / Cataratas",
        "LDB": "Londrina",
        "JOI": "Joinville",
        "NVT": "Navegantes",
        "XAP": "Chapecó",
        "CXJ": "Caxias do Sul",
        "CAC": "Cascavel",
        "PFB": "Passo Fundo",
        "PGZ": "Ponta Grossa",
    },
    "Brasil — Nordeste": {
        "SSA": "Salvador",
        "REC": "Recife / Guararapes",
        "FOR": "Fortaleza / Pinto Martins",
        "NAT": "Natal / São Gonçalo do Amarante",
        "MCZ": "Maceió / Zumbi dos Palmares",
        "AJU": "Aracaju / Santa Maria",
        "THE": "Teresina",
        "SLZ": "São Luís / Marechal Cunha Machado",
        "JPA": "João Pessoa / Castro Pinto",
        "JDO": "Juazeiro do Norte",
        "CPV": "Campina Grande",
        "IOS": "Ilhéus / Jorge Amado",
        "BPS": "Porto Seguro",
        "PNZ": "Petrolina / Senador Nilo Coelho",
        "VDC": "Vitória da Conquista",
        "FEN": "Fernando de Noronha",
        "IMP": "Imperatriz",
        "MAB": "Marabá",
        "PAV": "Paulo Afonso",
    },
    "Brasil — Norte": {
        "BEL": "Belém / Val de Cans",
        "MAO": "Manaus / Eduardo Gomes",
        "PVH": "Porto Velho",
        "BVB": "Boa Vista",
        "RBR": "Rio Branco / Plácido de Castro",
        "MCP": "Macapá / Alberto Alcolumbre",
        "STM": "Santarém",
        "TBT": "Tabatinga",
        "PMW": "Palmas",
        "ATM": "Altamira",
        "OPS": "Sinop",
        "BVH": "Vilhena",
        "TFF": "Tefé",
    },
    "Brasil — Centro-Oeste": {
        "BSB": "Brasília / JK",
        "GYN": "Goiânia / Santa Genoveva",
        "CGB": "Cuiabá / Marechal Rondon",
        "CGR": "Campo Grande",
    },
    "América do Norte": {
        "JFK": "Nova York / JFK",
        "EWR": "Nova York / Newark",
        "LGA": "Nova York / LaGuardia",
        "MIA": "Miami",
        "FLL": "Fort Lauderdale",
        "MCO": "Orlando",
        "LAX": "Los Angeles",
        "ORD": "Chicago / O'Hare",
        "MDW": "Chicago / Midway",
        "DCA": "Washington / Reagan",
        "IAD": "Washington / Dulles",
        "BWI": "Baltimore / Washington",
        "ATL": "Atlanta",
        "BOS": "Boston",
        "SFO": "São Francisco",
        "LAS": "Las Vegas",
        "DFW": "Dallas / Fort Worth",
        "SEA": "Seattle",
        "YYZ": "Toronto / Pearson",
        "YUL": "Montreal / Trudeau",
        "MEX": "Cidade do México",
        "CUN": "Cancún",
    },
    "América do Sul": {
        "EZE": "Buenos Aires / Ezeiza",
        "AEP": "Buenos Aires / Aeroparque",
        "SCL": "Santiago",
        "BOG": "Bogotá",
        "LIM": "Lima",
        "UIO": "Quito",
        "GYE": "Guayaquil",
        "ASU": "Assunção",
        "MVD": "Montevidéu",
        "CCS": "Caracas",
    },
    "Europa": {
        "CDG": "Paris / Charles de Gaulle",
        "ORY": "Paris / Orly",
        "LHR": "Londres / Heathrow",
        "LGW": "Londres / Gatwick",
        "STN": "Londres / Stansted",
        "LCY": "Londres / City",
        "LIS": "Lisboa",
        "OPO": "Porto",
        "MAD": "Madri / Barajas",
        "BCN": "Barcelona",
        "FCO": "Roma / Fiumicino",
        "CIA": "Roma / Ciampino",
        "MXP": "Milão / Malpensa",
        "LIN": "Milão / Linate",
        "AMS": "Amsterdam / Schiphol",
        "FRA": "Frankfurt",
        "MUC": "Munique",
        "ZRH": "Zurique",
        "GVA": "Genebra",
        "VIE": "Viena",
        "BRU": "Bruxelas",
        "CPH": "Copenhague",
        "OSL": "Oslo",
        "ARN": "Estocolmo",
        "HEL": "Helsinque",
        "ATH": "Atenas",
        "IST": "Istambul",
        "DUB": "Dublin",
        "WAW": "Varsóvia",
        "PRG": "Praga",
        "BUD": "Budapeste",
        "OTP": "Bucareste",
    },
    "Ásia / Oriente Médio / África": {
        "DXB": "Dubai",
        "DOH": "Doha / Qatar",
        "AUH": "Abu Dhabi",
        "NRT": "Tóquio / Narita",
        "HND": "Tóquio / Haneda",
        "PVG": "Shanghai / Pudong",
        "SHA": "Shanghai / Hongqiao",
        "PEK": "Pequim / Capital",
        "PKX": "Pequim / Daxing",
        "HKG": "Hong Kong",
        "SIN": "Singapura",
        "BKK": "Bangkok / Suvarnabhumi",
        "KUL": "Kuala Lumpur",
        "ICN": "Seul / Incheon",
        "DEL": "Nova Délhi",
        "BOM": "Mumbai",
        "SYD": "Sydney",
        "MEL": "Melbourne",
        "JNB": "Joanesburgo",
        "CAI": "Cairo",
        "CMN": "Casablanca",
    },
}

# Mapa plano código→nome para o JS
_ALL_AIRPORTS_FLAT = {
    code: name
    for region_airports in AIRPORTS_BY_REGION.values()
    for code, name in region_airports.items()
}

# ── Geradores de HTML/JS ───────────────────────────────────────────────────────

def _gen_datalist() -> str:
    lines = ['<optgroup label="── 🏙️ Cidades — todos os aeroportos ──">']
    for code, info in ALL_GROUPS.items():
        apts = " + ".join(info["aeroportos"])
        lines.append(f'<option value="{code}">🏙️ {code} — {info["nome"]} ({apts})</option>')
    lines.append("</optgroup>")
    for region, airports in AIRPORTS_BY_REGION.items():
        flag = "🇧🇷" if "Brasil" in region else ("🌎" if "América" in region else ("🌍" if "Europa" in region else "🌏"))
        lines.append(f'<optgroup label="── {flag} {region} ──">')
        for code, name in airports.items():
            lines.append(f'<option value="{code}">{code} — {name}</option>')
        lines.append("</optgroup>")
    return "\n      ".join(lines)


def _gen_js_airports() -> str:
    entries = [f'"{k}":"{v}"' for k, v in _ALL_AIRPORTS_FLAT.items()]
    return "{" + ",".join(entries) + "}"


def _gen_js_groups() -> str:
    parts = []
    for code, info in ALL_GROUPS.items():
        apts = "[" + ",".join(f'"{a}"' for a in info["aeroportos"]) + "]"
        parts.append(f'"{code}":{{"nome":"{info["nome"]}","aeroportos":{apts}}}')
    return "{" + ",".join(parts) + "}"


# ── helpers de config ─────────────────────────────────────────────────────────

def _read_config() -> dict:
    if os.path.exists(USER_CONFIG_PATH):
        with open(USER_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return dict(_DEFAULTS)

def _write_config(cfg: dict):
    with open(USER_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ── modelos Pydantic ──────────────────────────────────────────────────────────

class Rota(BaseModel):
    origem: str
    destino: str

class Settings(BaseModel):
    dias_antecedencia: List[int]
    threshold_desconto: float
    intervalo_horas: int

class NovoAssinante(BaseModel):
    nome: str
    canal: str
    contato: str

# ══════════════════════════════════════════════════════════════════════════════
# HTML
# ══════════════════════════════════════════════════════════════════════════════

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Radar Voos — Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Segoe UI',sans-serif; background:#0f172a; color:#e2e8f0; min-height:100vh; }

header { background:#1e293b; border-bottom:1px solid #334155; padding:16px 32px; display:flex; align-items:center; gap:12px; }
header h1 { font-size:1.3rem; font-weight:700; color:#f8fafc; }
.badge { background:#0ea5e9; color:#fff; font-size:.7rem; padding:2px 8px; border-radius:99px; font-weight:600; }
.last-update { margin-left:auto; font-size:.8rem; color:#64748b; }

.tabs { display:flex; gap:2px; padding:0 32px; background:#1e293b; border-bottom:1px solid #334155; }
.tab { padding:12px 20px; font-size:.85rem; font-weight:500; color:#64748b; cursor:pointer; border-bottom:2px solid transparent; transition:.15s; user-select:none; }
.tab:hover { color:#cbd5e1; }
.tab.active { color:#38bdf8; border-bottom-color:#38bdf8; }

.page { display:none; padding:28px 32px; max-width:1400px; margin:0 auto; }
.page.active { display:block; }

.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:16px; margin-bottom:32px; }
.card { background:#1e293b; border:1px solid #334155; border-radius:12px; padding:20px 24px; }
.card .label { font-size:.75rem; color:#64748b; text-transform:uppercase; letter-spacing:.05em; margin-bottom:8px; }
.card .value { font-size:2rem; font-weight:700; color:#f8fafc; }
.card .sub { font-size:.75rem; color:#64748b; margin-top:4px; }
.card.blue .value { color:#38bdf8; }
.card.green .value { color:#4ade80; }
.card.amber .value { color:#fbbf24; }

.section-title { font-size:1rem; font-weight:600; color:#cbd5e1; margin-bottom:14px; display:flex; align-items:center; gap:8px; }
.section-title::after { content:''; flex:1; height:1px; background:#334155; }

.table-wrap { background:#1e293b; border:1px solid #334155; border-radius:12px; overflow:hidden; margin-bottom:32px; }
table { width:100%; border-collapse:collapse; }
thead tr { background:#0f172a; }
th { padding:11px 16px; text-align:left; font-size:.75rem; color:#64748b; text-transform:uppercase; letter-spacing:.05em; }
td { padding:12px 16px; font-size:.875rem; border-top:1px solid #0f172a; }
tbody tr { background:#1e293b; transition:background .15s; }
tbody tr:hover { background:#263045; }
.rota { font-weight:600; color:#f8fafc; }
.preco { font-weight:700; }
.preco.barato { color:#4ade80; }
.preco.caro { color:#fb7185; }
.pill { display:inline-block; padding:2px 8px; border-radius:99px; font-size:.7rem; font-weight:600; }
.pill.direto { background:#14532d; color:#4ade80; }
.pill.escala { background:#451a03; color:#fbbf24; }
.pill.alerta { background:#4c0519; color:#fb7185; }
.empty { text-align:center; padding:40px; color:#475569; font-size:.875rem; }

.chart-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:32px; }
.chart-box { background:#1e293b; border:1px solid #334155; border-radius:12px; padding:20px; }
.chart-box h3 { font-size:.85rem; color:#94a3b8; margin-bottom:16px; }

/* ── CONFIG ── */
.config-grid { display:grid; grid-template-columns:1fr 1fr; gap:24px; }
.config-box { background:#1e293b; border:1px solid #334155; border-radius:12px; padding:24px; }
.config-box h2 { font-size:.95rem; font-weight:600; color:#f1f5f9; margin-bottom:20px; }

.form-row { display:flex; gap:10px; margin-bottom:8px; align-items:flex-end; flex-wrap:wrap; }
.field { display:flex; flex-direction:column; gap:6px; flex:1; min-width:100px; }
.field label { font-size:.75rem; color:#64748b; text-transform:uppercase; letter-spacing:.04em; }
.field input, .field select { background:#0f172a; border:1px solid #334155; border-radius:8px; padding:9px 12px; color:#f1f5f9; font-size:.875rem; outline:none; transition:.15s; font-family:inherit; width:100%; }
.field input:focus, .field select:focus { border-color:#38bdf8; box-shadow:0 0 0 2px #38bdf820; }
.field input::placeholder { color:#475569; }
.hint { font-size:.72rem; color:#38bdf8; margin-top:2px; min-height:16px; }

.btn { padding:9px 18px; border-radius:8px; font-size:.875rem; font-weight:600; cursor:pointer; border:none; transition:.15s; font-family:inherit; }
.btn-primary { background:#0ea5e9; color:#fff; }
.btn-primary:hover { background:#0284c7; }
.btn-danger { background:#dc2626; color:#fff; padding:6px 12px; font-size:.78rem; }
.btn-danger:hover { background:#b91c1c; }
.btn-save { background:#16a34a; color:#fff; width:100%; margin-top:8px; }
.btn-save:hover { background:#15803d; }

.rota-list { display:flex; flex-direction:column; gap:8px; max-height:460px; overflow-y:auto; margin-top:12px; }
.rota-item { display:flex; align-items:center; justify-content:space-between; background:#0f172a; border:1px solid #334155; border-radius:8px; padding:10px 14px; gap:8px; }
.rota-label { display:flex; flex-direction:column; gap:2px; flex:1; min-width:0; }
.rota-main { font-size:.9rem; font-weight:600; color:#f1f5f9; display:flex; align-items:center; gap:6px; flex-wrap:wrap; }
.rota-sub { font-size:.72rem; color:#64748b; }
.group-tag { background:#1d4ed820; color:#60a5fa; border:1px solid #1d4ed850; border-radius:5px; padding:1px 7px; font-size:.78rem; white-space:nowrap; }

.settings-group { margin-bottom:22px; }
.settings-group > label { display:block; font-size:.8rem; color:#94a3b8; margin-bottom:10px; font-weight:500; }
.dias-check { display:flex; flex-wrap:wrap; gap:8px; }
.dias-check label { display:flex; align-items:center; gap:6px; font-size:.85rem; color:#cbd5e1; cursor:pointer; background:#0f172a; border:1px solid #334155; border-radius:6px; padding:5px 10px; transition:.15s; }
.dias-check label:hover { border-color:#38bdf8; }
.dias-check input[type=checkbox] { accent-color:#38bdf8; width:14px; height:14px; }
.range-row { display:flex; align-items:center; gap:12px; }
.range-row input[type=range] { flex:1; accent-color:#38bdf8; }
.range-val { font-size:1rem; font-weight:700; color:#38bdf8; min-width:44px; text-align:right; }
.note { font-size:.72rem; color:#475569; margin-top:6px; }

.sub-list { display:flex; flex-direction:column; gap:8px; margin-top:4px; max-height:500px; overflow-y:auto; }
.sub-item { display:flex; align-items:center; gap:12px; background:#0f172a; border:1px solid #334155; border-radius:8px; padding:12px 14px; transition:.2s; }
.sub-item.inativo { opacity:.45; }
.sub-icon { font-size:1.3rem; flex-shrink:0; }
.sub-info { flex:1; min-width:0; }
.sub-nome { font-weight:600; font-size:.9rem; color:#f1f5f9; display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.sub-contato { font-size:.78rem; color:#64748b; margin-top:3px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.canal-badge { display:inline-block; padding:2px 8px; border-radius:99px; font-size:.68rem; font-weight:600; }
.canal-badge.telegram { background:#0c4a6e40; color:#38bdf8; border:1px solid #0c4a6e80; }
.canal-badge.whatsapp { background:#14532d40; color:#4ade80; border:1px solid #14532d80; }
.canal-badge.email { background:#78350f40; color:#fbbf24; border:1px solid #78350f80; }
.sub-actions { display:flex; gap:6px; flex-shrink:0; }
.btn-sm { padding:5px 10px; font-size:.75rem; border-radius:6px; border:1px solid #334155; background:transparent; color:#94a3b8; cursor:pointer; font-family:inherit; transition:.15s; white-space:nowrap; }
.btn-sm:hover { border-color:#38bdf8; color:#38bdf8; }
.btn-sm.ativo { border-color:#4ade80; color:#4ade80; }
.canal-info { background:#0f172a; border:1px solid #334155; border-radius:8px; padding:14px 16px; margin-top:20px; font-size:.8rem; line-height:1.9; color:#94a3b8; }
.canal-info strong { color:#f1f5f9; }

#toast { position:fixed; bottom:24px; right:24px; background:#1e293b; border:1px solid #334155; border-radius:10px; padding:12px 20px; font-size:.875rem; color:#f1f5f9; box-shadow:0 8px 24px #00000060; transform:translateY(80px); opacity:0; transition:.3s; z-index:999; }
#toast.show { transform:translateY(0); opacity:1; }
#toast.ok { border-color:#4ade80; }
#toast.err { border-color:#fb7185; }

@keyframes spin { to { transform:rotate(360deg); } }
.spin { display:inline-block; width:14px; height:14px; border:2px solid #334155; border-top-color:#38bdf8; border-radius:50%; animation:spin .7s linear infinite; vertical-align:middle; margin-right:6px; }

@media(max-width:900px) {
  .chart-grid, .config-grid { grid-template-columns:1fr; }
  .page { padding:16px; }
  header, .tabs { padding-left:16px; padding-right:16px; }
}
</style>
</head>
<body>

<header>
  <span>✈️</span>
  <h1>Radar Voos <span class="badge">LIVE</span></h1>
  <span class="last-update" id="last-update">carregando...</span>
</header>

<div class="tabs">
  <div class="tab active" onclick="showPage('dashboard',this)">📊 Dashboard</div>
  <div class="tab" onclick="showPage('config',this)">⚙️ Configurações</div>
  <div class="tab" onclick="showPage('assinantes',this)">👥 Assinantes</div>
</div>

<!-- ══ DASHBOARD ══ -->
<div class="page active" id="page-dashboard">
  <div class="cards">
    <div class="card blue"><div class="label">Preços Coletados</div><div class="value" id="c-total">—</div></div>
    <div class="card"><div class="label">Rotas Monitoradas</div><div class="value" id="c-rotas">—</div></div>
    <div class="card amber"><div class="label">Alertas Disparados</div><div class="value" id="c-alertas">—</div></div>
    <div class="card green"><div class="label">Menor Preço Hoje</div><div class="value" id="c-menor">—</div><div class="sub" id="c-menor-rota"></div></div>
  </div>

  <div class="section-title">Últimos Preços por Rota</div>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Rota</th><th>Preço</th><th>vs Média</th><th>Companhia</th><th>Paradas</th><th>Data do Voo</th><th>Capturado em</th></tr></thead>
      <tbody id="tbody-precos"><tr><td colspan="7" class="empty"><span class="spin"></span> carregando...</td></tr></tbody>
    </table>
  </div>

  <div class="chart-grid">
    <div class="chart-box">
      <h3>Preço Médio por Rota</h3>
      <canvas id="chart-barras" height="200"></canvas>
    </div>
    <div class="chart-box">
      <h3>Alertas Recentes</h3>
      <table style="width:100%">
        <thead><tr><th>Rota</th><th>Preço</th><th>Desconto</th><th>Quando</th><th></th></tr></thead>
        <tbody id="tbody-alertas"><tr><td colspan="5" class="empty" style="padding:24px">sem alertas ainda</td></tr></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ══ CONFIGURAÇÕES ══ -->
<div class="page" id="page-config">
  <div class="config-grid">

    <div class="config-box">
      <h2>🗺️ Rotas Monitoradas</h2>

      <div class="form-row">
        <div class="field">
          <label>Origem</label>
          <input id="inp-origem" list="airports" placeholder="Ex: SAO ou GRU" autocomplete="off"
            oninput="this.value=this.value.toUpperCase();updateHint('origem',this.value)">
          <div class="hint" id="hint-origem"></div>
        </div>
        <div style="display:flex;align-items:center;padding-bottom:22px;color:#475569;font-size:1.2rem">→</div>
        <div class="field">
          <label>Destino</label>
          <input id="inp-destino" list="airports" placeholder="Ex: PAR ou CDG" autocomplete="off"
            oninput="this.value=this.value.toUpperCase();updateHint('destino',this.value)">
          <div class="hint" id="hint-destino"></div>
        </div>
        <div style="padding-bottom:22px">
          <button class="btn btn-primary" onclick="addRota()">+ Adicionar</button>
        </div>
      </div>

      <datalist id="airports">
        __DATALIST__
      </datalist>

      <div id="rota-list" class="rota-list">
        <div class="empty"><span class="spin"></span> carregando...</div>
      </div>
    </div>

    <div class="config-box">
      <h2>🎛️ Parâmetros de Busca</h2>

      <div class="settings-group">
        <label>Dias de antecedência monitorados</label>
        <div class="dias-check" id="dias-check">
          <label><input type="checkbox" value="7"> 7 dias</label>
          <label><input type="checkbox" value="14"> 14 dias</label>
          <label><input type="checkbox" value="30"> 30 dias</label>
          <label><input type="checkbox" value="60"> 60 dias</label>
          <label><input type="checkbox" value="90"> 90 dias</label>
          <label><input type="checkbox" value="120"> 120 dias</label>
          <label><input type="checkbox" value="180"> 180 dias</label>
        </div>
      </div>

      <div class="settings-group">
        <label>Desconto mínimo para alerta</label>
        <div class="range-row">
          <input type="range" id="range-threshold" min="5" max="60" step="5"
            oninput="document.getElementById('val-threshold').textContent=this.value+'%'">
          <span class="range-val" id="val-threshold">30%</span>
        </div>
        <div class="note">Ex: 30% = alerta quando o preço cair 30% abaixo da média histórica</div>
      </div>

      <div class="settings-group">
        <label>Intervalo entre ciclos de busca</label>
        <div class="field">
          <select id="sel-intervalo">
            <option value="1">A cada 1 hora</option>
            <option value="2">A cada 2 horas</option>
            <option value="4">A cada 4 horas</option>
            <option value="6">A cada 6 horas</option>
            <option value="12">A cada 12 horas</option>
            <option value="24">Uma vez por dia</option>
          </select>
        </div>
      </div>

      <button class="btn btn-save" onclick="saveSettings()">💾 Salvar Configurações</button>
      <div class="note" style="text-align:center;margin-top:10px">Alterações entram em vigor no próximo reinício do main.py</div>
    </div>
  </div>
</div>

<!-- ══ ASSINANTES ══ -->
<div class="page" id="page-assinantes">
  <div class="config-grid">

    <div class="config-box">
      <h2>➕ Novo Assinante</h2>
      <div class="field" style="margin-bottom:14px">
        <label>Nome / Identificação</label>
        <input id="a-nome" placeholder="Ex: Canal de Promoções de Voos">
      </div>
      <div class="field" style="margin-bottom:14px">
        <label>Canal de envio</label>
        <select id="a-canal" onchange="updateContatoHint()">
          <option value="telegram">📱 Telegram</option>
          <option value="whatsapp">💬 WhatsApp</option>
          <option value="email">📧 Email</option>
        </select>
      </div>
      <div class="field" style="margin-bottom:16px">
        <label>Contato</label>
        <input id="a-contato" placeholder="@canal_telegram">
        <div class="hint" id="a-hint">Chat ID numérico (-1001234...) ou @nome_do_canal</div>
      </div>
      <button class="btn btn-primary" style="width:100%" onclick="addAssinante()">+ Adicionar Assinante</button>

      <div class="canal-info">
        <strong>📱 Telegram:</strong> Crie o bot em @BotFather → TOKEN no .env. Contato: @canal ou chat_id numérico.<br>
        <strong>💬 WhatsApp:</strong> Configure o Twilio Sandbox → credenciais no .env. Contato: +5511999998888.<br>
        <strong>📧 Email:</strong> Configure SendGrid → API key no .env. Contato: email@dominio.com.
      </div>
    </div>

    <div class="config-box">
      <h2>👥 Assinantes Cadastrados</h2>
      <div id="assinantes-list">
        <div class="empty"><span class="spin"></span> carregando...</div>
      </div>
    </div>

  </div>
</div>

<div id="toast"></div>

<script>
const AIRPORTS = __JS_AIRPORTS__;
const GROUPS   = __JS_GROUPS__;

function airportName(code) {
  const c = code.toUpperCase();
  if (GROUPS[c]) return '🏙️ ' + GROUPS[c].nome + ' — todos os aeroportos (' + GROUPS[c].aeroportos.join(', ') + ')';
  return AIRPORTS[c] || '';
}

function rotaLabel(code) {
  const c = code.toUpperCase();
  if (GROUPS[c]) {
    return '<span class="group-tag">🏙️ ' + c + '</span>' +
           '<span style="color:#94a3b8;font-size:.82rem">' + GROUPS[c].nome + '</span>' +
           '<span class="rota-sub">' + GROUPS[c].aeroportos.join(' + ') + '</span>';
  }
  return '<span>' + c + '</span>' +
         '<span class="rota-sub">' + (AIRPORTS[c] || '') + '</span>';
}

function updateHint(field, val) {
  const name = airportName(val);
  document.getElementById('hint-' + field).textContent = name ? '→ ' + name : (val.length === 3 ? 'Código não encontrado' : '');
}

// ── tabs ──────────────────────────────────────────────────────────────────────
function showPage(name, el) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  el.classList.add('active');
  if (name === 'config') loadConfig();
  if (name === 'assinantes') loadAssinantes();
}

// ── toast ─────────────────────────────────────────────────────────────────────
function toast(msg, ok=true) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'show ' + (ok ? 'ok' : 'err');
  setTimeout(() => t.className = '', 2800);
}

// ── DASHBOARD ─────────────────────────────────────────────────────────────────
const fmt = v => 'R$ ' + Number(v).toLocaleString('pt-BR', {minimumFractionDigits:0, maximumFractionDigits:0});
const fmtDate = s => s ? new Date(s).toLocaleString('pt-BR') : '—';
let barChart = null;

async function loadDashboard() {
  try {
    const [stats, precos, alertas] = await Promise.all([
      fetch('/api/stats').then(r => r.json()),
      fetch('/api/precos').then(r => r.json()),
      fetch('/api/alertas').then(r => r.json()),
    ]);

    document.getElementById('c-total').textContent = stats.total_precos.toLocaleString('pt-BR');
    document.getElementById('c-rotas').textContent = stats.rotas;
    document.getElementById('c-alertas').textContent = stats.alertas;
    if (stats.menor_preco) {
      document.getElementById('c-menor').textContent = fmt(stats.menor_preco.preco);
      document.getElementById('c-menor-rota').textContent = stats.menor_preco.origem + ' → ' + stats.menor_preco.destino;
    }
    document.getElementById('last-update').textContent = 'atualizado ' + new Date().toLocaleTimeString('pt-BR');

    const tbody = document.getElementById('tbody-precos');
    if (!precos.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty">nenhum preço coletado ainda — aguarde o próximo ciclo</td></tr>';
    } else {
      tbody.innerHTML = precos.map(p => {
        const diff = p.media ? ((p.preco - p.media) / p.media * 100) : null;
        const cls = diff === null ? '' : diff <= -10 ? 'barato' : diff >= 10 ? 'caro' : '';
        const vsMedia = diff === null ? '—' : (diff > 0 ? '+' : '') + diff.toFixed(1) + '%';
        const cor = diff === null ? '#64748b' : diff < 0 ? '#4ade80' : '#fb7185';
        const aOrigem = AIRPORTS[p.origem] ? ' <span style="font-weight:400;color:#64748b;font-size:.78rem">(' + AIRPORTS[p.origem] + ')</span>' : '';
        const aDestino = AIRPORTS[p.destino] ? ' <span style="font-weight:400;color:#64748b;font-size:.78rem">(' + AIRPORTS[p.destino] + ')</span>' : '';
        const paradas = p.paradas === 0
          ? '<span class="pill direto">Direto</span>'
          : '<span class="pill escala">' + p.paradas + ' escala(s)</span>';
        return '<tr>' +
          '<td class="rota">' + p.origem + ' → ' + p.destino + aOrigem.replace('(','').replace(')','') + '</td>' +
          '<td class="preco ' + cls + '">' + fmt(p.preco) + '</td>' +
          '<td style="color:' + cor + '">' + vsMedia + '</td>' +
          '<td>' + (p.companhia || '—') + '</td>' +
          '<td>' + paradas + '</td>' +
          '<td>' + (p.data_voo || '—') + '</td>' +
          '<td style="color:#64748b;font-size:.8rem">' + fmtDate(p.capturado_em) + '</td>' +
          '</tr>';
      }).join('');
    }

    const rotas = [...new Set(precos.map(p => p.origem + '→' + p.destino))];
    const medias = rotas.map(r => {
      const [o, d] = r.split('→');
      const items = precos.filter(p => p.origem === o && p.destino === d);
      return items.reduce((s, p) => s + p.preco, 0) / items.length;
    });
    if (barChart) barChart.destroy();
    barChart = new Chart(document.getElementById('chart-barras'), {
      type: 'bar',
      data: { labels: rotas, datasets: [{ label: 'Preço médio', data: medias,
          backgroundColor:'#38bdf888', borderColor:'#38bdf8', borderWidth:1, borderRadius:4 }] },
      options: { responsive:true, plugins:{ legend:{ display:false } },
        scales: {
          x: { ticks:{ color:'#94a3b8', font:{ size:9 } }, grid:{ color:'#1e293b' } },
          y: { ticks:{ color:'#94a3b8', callback: v => 'R$'+v.toLocaleString('pt-BR') }, grid:{ color:'#334155' } },
        }
      }
    });

    const tbA = document.getElementById('tbody-alertas');
    if (!alertas.length) {
      tbA.innerHTML = '<tr><td colspan="5" class="empty" style="padding:24px">sem alertas ainda</td></tr>';
    } else {
      tbA.innerHTML = alertas.slice(0,10).map(a =>
        '<tr><td class="rota">' + a.origem + '→' + a.destino + '</td>' +
        '<td class="preco barato">' + fmt(a.preco_alerta) + '</td>' +
        '<td><span class="pill alerta">-' + (a.desconto_pct*100).toFixed(0) + '%</span></td>' +
        '<td style="color:#64748b;font-size:.75rem">' + fmtDate(a.enviado_em) + '</td>' +
        '<td>' + (a.link_compra ? '<a href="' + a.link_compra + '" target="_blank" style="background:#0ea5e9;color:#fff;padding:4px 10px;border-radius:6px;font-size:.75rem;font-weight:600;text-decoration:none;white-space:nowrap">🛒 Comprar</a>' : '') + '</td></tr>'
      ).join('');
    }
  } catch(e) { console.error(e); }
}

// ── CONFIGURAÇÕES ─────────────────────────────────────────────────────────────
async function loadConfig() {
  const cfg = await fetch('/api/config').then(r => r.json());
  renderRotas(cfg.rotas || []);
  document.querySelectorAll('#dias-check input').forEach(cb => {
    cb.checked = (cfg.dias_antecedencia || []).includes(parseInt(cb.value));
  });
  const th = Math.round((cfg.threshold_desconto || 0.3) * 100);
  document.getElementById('range-threshold').value = th;
  document.getElementById('val-threshold').textContent = th + '%';
  document.getElementById('sel-intervalo').value = cfg.intervalo_horas || 1;
}

function renderRotas(rotas) {
  const el = document.getElementById('rota-list');
  if (!rotas.length) {
    el.innerHTML = '<div class="empty">Nenhuma rota cadastrada</div>';
    return;
  }
  el.innerHTML = rotas.map((r, i) => {
    const oLabel = rotaLabel(r.origem);
    const dLabel = rotaLabel(r.destino);
    return '<div class="rota-item">' +
      '<div class="rota-label"><div class="rota-main">' +
        oLabel + '<span style="color:#475569;margin:0 4px">→</span>' + dLabel +
      '</div></div>' +
      '<button class="btn btn-danger" onclick="removeRota(' + i + ')">✕</button>' +
    '</div>';
  }).join('');
}

async function addRota() {
  const o = document.getElementById('inp-origem').value.trim().toUpperCase();
  const d = document.getElementById('inp-destino').value.trim().toUpperCase();
  if (o.length < 3 || d.length < 3) { toast('Insira códigos IATA válidos (3 letras)', false); return; }
  if (o === d) { toast('Origem e destino não podem ser iguais', false); return; }
  const res = await fetch('/api/config/rotas', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({origem:o, destino:d}),
  });
  if (res.ok) {
    const cfg = await res.json();
    renderRotas(cfg.rotas);
    document.getElementById('inp-origem').value = '';
    document.getElementById('inp-destino').value = '';
    document.getElementById('hint-origem').textContent = '';
    document.getElementById('hint-destino').textContent = '';
    toast('Rota ' + o + ' → ' + d + ' adicionada!');
  } else {
    const err = await res.json();
    toast(err.detail || 'Erro ao adicionar', false);
  }
}

async function removeRota(index) {
  const res = await fetch('/api/config/rotas/' + index, { method:'DELETE' });
  if (res.ok) { renderRotas((await res.json()).rotas); toast('Rota removida'); }
  else toast('Erro ao remover', false);
}

async function saveSettings() {
  const dias = Array.from(document.querySelectorAll('#dias-check input:checked'))
    .map(cb => parseInt(cb.value)).sort((a,b) => a-b);
  if (!dias.length) { toast('Selecione ao menos um período', false); return; }
  const res = await fetch('/api/config/settings', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      dias_antecedencia: dias,
      threshold_desconto: parseInt(document.getElementById('range-threshold').value) / 100,
      intervalo_horas: parseInt(document.getElementById('sel-intervalo').value),
    }),
  });
  if (res.ok) toast('Salvo! Reinicie o main.py para aplicar.');
  else toast('Erro ao salvar', false);
}

// ── ASSINANTES ───────────────────────────────────────────────────────────────
const CANAL_ICONS = {telegram:'📱', whatsapp:'💬', email:'📧'};
const CANAL_HINTS = {
  telegram:'Chat ID numérico (-1001234...) ou @nome_do_canal',
  whatsapp:'Número com DDI: +5511999998888',
  email:'Endereço de email: usuario@dominio.com',
};
const CANAL_PLACEHOLDERS = {
  telegram:'@canal_telegram ou -1001234567890',
  whatsapp:'+5511999998888',
  email:'usuario@dominio.com',
};

function updateContatoHint() {
  const canal = document.getElementById('a-canal').value;
  document.getElementById('a-contato').placeholder = CANAL_PLACEHOLDERS[canal];
  document.getElementById('a-hint').textContent = CANAL_HINTS[canal];
}

async function loadAssinantes() {
  const list = await fetch('/api/assinantes').then(r => r.json());
  renderAssinantes(list);
}

function renderAssinantes(list) {
  const el = document.getElementById('assinantes-list');
  if (!list.length) {
    el.innerHTML = '<div class="empty">Nenhum assinante cadastrado.<br>Adicione alguém para receber os alertas de promoção.</div>';
    return;
  }
  el.innerHTML = '<div class="sub-list">' + list.map(a =>
    '<div class="sub-item ' + (a.ativo ? '' : 'inativo') + '">' +
      '<span class="sub-icon">' + (CANAL_ICONS[a.canal] || '📩') + '</span>' +
      '<div class="sub-info">' +
        '<div class="sub-nome">' + a.nome + ' <span class="canal-badge ' + a.canal + '">' + a.canal + '</span></div>' +
        '<div class="sub-contato">' + a.contato + '</div>' +
      '</div>' +
      '<div class="sub-actions">' +
        '<button class="btn-sm ' + (a.ativo ? 'ativo' : '') + '" onclick="toggleAssinante(' + a.id + ')">' +
          (a.ativo ? '✅ Ativo' : '⏸ Pausado') + '</button>' +
        '<button class="btn btn-danger" onclick="removeAssinante(' + a.id + ')">✕</button>' +
      '</div>' +
    '</div>'
  ).join('') + '</div>';
}

async function addAssinante() {
  const nome = document.getElementById('a-nome').value.trim();
  const canal = document.getElementById('a-canal').value;
  const contato = document.getElementById('a-contato').value.trim();
  if (!nome || !contato) { toast('Preencha nome e contato', false); return; }
  const res = await fetch('/api/assinantes', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({nome, canal, contato}),
  });
  if (res.ok) {
    document.getElementById('a-nome').value = '';
    document.getElementById('a-contato').value = '';
    loadAssinantes();
    toast(CANAL_ICONS[canal] + ' ' + nome + ' adicionado!');
  } else {
    const err = await res.json();
    toast(err.detail || 'Erro ao adicionar', false);
  }
}

async function toggleAssinante(id) {
  const res = await fetch('/api/assinantes/' + id + '/toggle', {method:'PATCH'});
  if (res.ok) { loadAssinantes(); toast('Status atualizado'); }
  else toast('Erro ao atualizar', false);
}

async function removeAssinante(id) {
  if (!confirm('Remover este assinante?')) return;
  const res = await fetch('/api/assinantes/' + id, {method:'DELETE'});
  if (res.ok) { loadAssinantes(); toast('Assinante removido'); }
  else toast('Erro ao remover', false);
}


loadDashboard();
setInterval(loadDashboard, 30000);
</script>
</body>
</html>"""

def _build_html() -> str:
    import os as _os
    _p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "static", "index.html")
    if _os.path.exists(_p):
        with open(_p, encoding="utf-8") as _fh:
            return _fh.read()
    return (
        _HTML_TEMPLATE
        .replace("__DATALIST__", _gen_datalist())
        .replace("__JS_AIRPORTS__", _gen_js_airports())
        .replace("__JS_GROUPS__", _gen_js_groups())
    )

HTML = _build_html()

# ══════════════════════════════════════════════════════════════════════════════
# API — Dashboard
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
def index():
    static_path = os.path.join(_STATIC_DIR, "index.html")
    if os.path.exists(static_path):
        with open(static_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content=HTML)


@app.get("/api/stats")
def stats():
    session = Session()
    try:
        total_precos = session.query(HistoricoPreco).count()
        rotas = session.query(HistoricoPreco.origem, HistoricoPreco.destino).distinct().count()
        alertas = session.query(Alerta).count()
        menor = (
            session.query(HistoricoPreco)
            .filter(HistoricoPreco.capturado_em >= datetime.utcnow() - timedelta(hours=24))
            .order_by(HistoricoPreco.preco).first()
        )
        return {
            "total_precos": total_precos, "rotas": rotas, "alertas": alertas,
            "menor_preco": {"preco": menor.preco, "origem": menor.origem, "destino": menor.destino} if menor else None,
        }
    finally:
        session.close()


@app.get("/api/precos")
def precos():
    session = Session()
    try:
        sub = (
            session.query(
                HistoricoPreco.origem, HistoricoPreco.destino, HistoricoPreco.data_voo,
                func.max(HistoricoPreco.capturado_em).label("ultimo"),
            )
            .group_by(HistoricoPreco.origem, HistoricoPreco.destino, HistoricoPreco.data_voo)
            .subquery()
        )
        rows = (
            session.query(HistoricoPreco)
            .join(sub, (HistoricoPreco.origem == sub.c.origem)
                & (HistoricoPreco.destino == sub.c.destino)
                & (HistoricoPreco.data_voo == sub.c.data_voo)
                & (HistoricoPreco.capturado_em == sub.c.ultimo))
            .order_by(HistoricoPreco.origem, HistoricoPreco.destino, HistoricoPreco.data_voo)
            .all()
        )
        medias = {}
        for o, d in session.query(HistoricoPreco.origem, HistoricoPreco.destino).distinct():
            avg = session.query(func.avg(HistoricoPreco.preco)).filter(
                HistoricoPreco.origem == o, HistoricoPreco.destino == d).scalar()
            medias[(o, d)] = float(avg) if avg else None
        return JSONResponse([{
            "origem": r.origem, "destino": r.destino, "preco": r.preco,
            "companhia": r.companhia, "paradas": r.paradas, "data_voo": r.data_voo,
            "capturado_em": r.capturado_em.isoformat() if r.capturado_em else None,
            "media": medias.get((r.origem, r.destino)),
        } for r in rows])
    finally:
        session.close()


@app.get("/api/alertas")
def alertas():
    session = Session()
    try:
        rows = session.query(Alerta).order_by(desc(Alerta.enviado_em)).limit(20).all()
        return JSONResponse([{
            "origem": a.origem, "destino": a.destino, "preco_alerta": a.preco_alerta,
            "preco_medio": a.preco_medio, "desconto_pct": a.desconto_pct,
            "companhia": a.companhia, "data_voo": a.data_voo,
            "link_compra": a.link_compra,
            "enviado_em": a.enviado_em.isoformat() if a.enviado_em else None,
        } for a in rows])
    finally:
        session.close()


# ══════════════════════════════════════════════════════════════════════════════
# API — Configurações
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/config/groups")
def get_groups():
    return ALL_GROUPS


@app.get("/api/config/airports")
def get_airports():
    return _ALL_AIRPORTS_FLAT


@app.get("/api/config")
def get_config():
    return _read_config()


@app.post("/api/config/rotas")
def add_rota(rota: Rota):
    cfg = _read_config()
    rotas = cfg.get("rotas", list(_DEFAULTS["rotas"]))
    o, d = rota.origem.upper().strip(), rota.destino.upper().strip()
    if any(r["origem"] == o and r["destino"] == d for r in rotas):
        raise HTTPException(status_code=400, detail=f"Rota {o} → {d} já existe")
    rotas.append({"origem": o, "destino": d})
    cfg["rotas"] = rotas
    _write_config(cfg)
    return cfg


@app.delete("/api/config/rotas/{index}")
def remove_rota(index: int):
    cfg = _read_config()
    rotas = cfg.get("rotas", list(_DEFAULTS["rotas"]))
    if index < 0 or index >= len(rotas):
        raise HTTPException(status_code=404, detail="Rota não encontrada")
    rotas.pop(index)
    cfg["rotas"] = rotas
    _write_config(cfg)
    return cfg


@app.post("/api/config/settings")
def save_settings(s: Settings):
    cfg = _read_config()
    cfg["dias_antecedencia"] = sorted(s.dias_antecedencia)
    cfg["threshold_desconto"] = round(s.threshold_desconto, 2)
    cfg["intervalo_horas"] = s.intervalo_horas
    _write_config(cfg)
    return cfg


# ══════════════════════════════════════════════════════════════════════════════
# API — Assinantes
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/assinantes")
def get_assinantes():
    session = Session()
    try:
        rows = session.query(Assinante).order_by(Assinante.canal, Assinante.nome).all()
        return JSONResponse([{
            "id": a.id, "nome": a.nome, "canal": a.canal,
            "contato": a.contato, "ativo": a.ativo,
            "criado_em": a.criado_em.isoformat() if a.criado_em else None,
        } for a in rows])
    finally:
        session.close()


@app.post("/api/assinantes", status_code=201)
def add_assinante(a: NovoAssinante):
    canal = a.canal.lower().strip()
    if canal not in ("telegram", "whatsapp", "email"):
        raise HTTPException(status_code=400, detail="Canal inválido. Use: telegram, whatsapp ou email")
    session = Session()
    try:
        novo = Assinante(nome=a.nome.strip(), canal=canal, contato=a.contato.strip())
        session.add(novo)
        session.commit()
        return {"id": novo.id, "nome": novo.nome, "canal": novo.canal, "contato": novo.contato, "ativo": novo.ativo}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.delete("/api/assinantes/{id}")
def del_assinante(id: int):
    session = Session()
    try:
        a = session.query(Assinante).filter(Assinante.id == id).first()
        if not a:
            raise HTTPException(status_code=404, detail="Assinante não encontrado")
        session.delete(a)
        session.commit()
        return {"ok": True}
    finally:
        session.close()


@app.patch("/api/assinantes/{id}/toggle")
def toggle_assinante(id: int):
    session = Session()
    try:
        a = session.query(Assinante).filter(Assinante.id == id).first()
        if not a:
            raise HTTPException(status_code=404, detail="Assinante não encontrado")
        a.ativo = not a.ativo
        session.commit()
        return {"id": a.id, "ativo": a.ativo}
    finally:
        session.close()


# ══════════════════════════════════════════════════════════════════════════════
# API — Ações / Testes
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/config/channels")
def get_channels_config():
    from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM, EMAIL_FROM
    return {
        "telegram": {
            "token": TELEGRAM_BOT_TOKEN or "",
            "channel_id": TELEGRAM_CHANNEL_ID or "",
            "configured": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID),
        },
        "whatsapp": {
            "sid": TWILIO_ACCOUNT_SID or "",
            "auth_token": TWILIO_AUTH_TOKEN or "",
            "from_number": TWILIO_WHATSAPP_FROM or "",
            "to_number": os.getenv("TWILIO_WHATSAPP_TO", ""),
            "configured": bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN),
        },
        "email": {
            "from_addr": EMAIL_FROM or "",
            "configured": bool(EMAIL_FROM),
        },
    }


@app.post("/api/testar-telegram")
def testar_telegram():
    import requests as _req
    from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID, now_brasilia

    if not TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN não configurado no .env")
    if not TELEGRAM_CHANNEL_ID:
        raise HTTPException(status_code=400, detail="TELEGRAM_CHANNEL_ID não configurado no .env")

    hora = now_brasilia().strftime("%d/%m/%Y %H:%M")
    msg = (
        "✅ *Radar Voos — Teste de Conexão*\n\n"
        f"🕐 Horário: {hora} (Brasília)\n"
        "📡 Bot conectado e funcionando!\n"
        "🔔 Você receberá alertas de promoções aqui."
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = _req.post(url, json={
            "chat_id": TELEGRAM_CHANNEL_ID,
            "text": msg,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }, timeout=10)
        data = r.json()
        if data.get("ok"):
            return {"ok": True, "msg": "Mensagem de teste enviada com sucesso!"}
        raise HTTPException(status_code=400, detail=data.get("description", f"Erro Telegram HTTP {r.status_code}"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de conexão: {e}")


@app.post("/api/testar-alerta")
def testar_alerta():
    import requests as _req
    from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
    from src.scheduler.jobs import formatar_alerta, _link_compra
    from config import now_brasilia

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN ou TELEGRAM_CHANNEL_ID não configurados no .env")

    voo_simulado = {
        "origem": "POA",
        "destino": "GIG",
        "preco": 287.0,
        "companhia": "LATAM",
        "paradas": 0,
        "data_voo": (datetime.utcnow() + timedelta(days=45)).strftime("%Y-%m-%d"),
    }
    preco_medio = 890.0
    desconto_pct = round((preco_medio - voo_simulado["preco"]) / preco_medio * 100)

    msg = formatar_alerta(voo_simulado, preco_medio, desconto_pct)
    msg += f"\n\n_⚠️ Esta é uma mensagem de teste — {now_brasilia().strftime('%d/%m/%Y %H:%M')}_"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = _req.post(url, json={
            "chat_id": TELEGRAM_CHANNEL_ID,
            "text": msg,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }, timeout=10)
        data = r.json()
        if data.get("ok"):
            return {"ok": True, "msg": f"Alerta simulado enviado! POA→GIG R$287 ({desconto_pct}% off)"}
        raise HTTPException(status_code=400, detail=data.get("description", f"Erro Telegram HTTP {r.status_code}"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de conexão: {e}")


class BuscarParams(BaseModel):
    origem: str
    destino: str
    data: str = ""

@app.post("/api/buscar")
def buscar_rota(p: BuscarParams):
    """Busca voos para uma rota/data específica e salva no histórico."""
    from datetime import date as _date
    from src.scrapers.amadeus import buscar_voos
    from src.scheduler.jobs import expandir_rotas
    from src.database.queries import salvar_preco

    origem = p.origem.upper().strip()
    destino = p.destino.upper().strip()
    if not origem or not destino:
        raise HTTPException(status_code=400, detail="Origem e destino são obrigatórios")

    data = p.data or _date.today().isoformat()
    rotas = expandir_rotas([{"origem": origem, "destino": destino}])

    resultados = []
    for rota in rotas:
        try:
            voos = buscar_voos(rota["origem"], rota["destino"], data)
            for v in voos:
                salvar_preco(v)
            resultados.extend(voos)
        except Exception as e:
            print(f"Erro ao buscar {rota['origem']}→{rota['destino']}: {e}")

    return {
        "ok": True,
        "rotas_buscadas": [f"{r['origem']}→{r['destino']}" for r in rotas],
        "total": len(resultados),
        "resultados": resultados,
    }


@app.post("/api/verificar")
def verificar_rotas():
    import threading
    from src.scheduler.jobs import ciclo_monitoramento
    def _run():
        try:
            ciclo_monitoramento()
        except Exception as e:
            print(f"Erro no ciclo: {e}")
    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "msg": "Verificação iniciada em background. Alertas serão enviados se houver promoções."}


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    total = sum(len(v) for v in AIRPORTS_BY_REGION.values())
    print(f"Aeroportos cadastrados: {total} | Grupos: {len(ALL_GROUPS)}")
    print(f"Dashboard disponível em http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)

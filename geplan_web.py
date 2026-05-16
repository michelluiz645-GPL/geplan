import streamlit as st
import json, os, sqlite3, datetime, zipfile, hashlib, time
import urllib.request, urllib.error

st.set_page_config(page_title="GEPLAN", page_icon="⚙", layout="wide", initial_sidebar_state="expanded")

# ══════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════
KOBO_TOKEN        = "421a638b833d5066715177f3b42f6e691f556601"
KOBO_UID_SUPRIM   = "aVYWQiABCjpd5Rvr7NodwY"
KOBO_UID_COMPRAS  = "aHsL6id4azYfCKa8HY978g"
KOBO_URL_SUPRIM   = f"https://kf.kobotoolbox.org/api/v2/assets/{KOBO_UID_SUPRIM}/data/?format=json&limit=100"
KOBO_URL_COMPRAS  = f"https://kf.kobotoolbox.org/api/v2/assets/{KOBO_UID_COMPRAS}/data/?format=json&limit=100"

CATEGORIAS    = ["FILTROS","ÓLEOS","GRAXAS","LUBRIFICANTES","COMBUSTÍVEL","PEÇAS MOTOR",
                 "PEÇAS HIDRÁULICAS","ELÉTRICA","ILUMINAÇÃO","FREIOS","SUSPENSÃO","ROLAMENTOS",
                 "CORREIAS","MANGUEIRAS","PARAFUSOS","FERRAMENTAS","EPI","MATERIAL DE LIMPEZA",
                 "SOLDA","PNEUS","BATERIAS","TINTAS","MATERIAL DE ESCRITÓRIO","INFORMÁTICA",
                 "OUTROS","PEÇA LEVE","PEÇA PESADA","ROÇADA","CONSUMO ADM"]
UNIDADES          = ["UNID","METROS","LITROS","KG"]
TIPOS_EQUIP       = ["ROÇADEIRA","SOPRADOR","OUTRO"]
ALMOXARIFADOS     = ["ALMOX 01","ALMOX 02"]
TIPOS_COMBUSTIVEL = ["DIESEL S500","DIESEL S10","GASOLINA"]
MENUS_ADMIN    = ["Dashboard","Consultar","Entrada","Saída","Devolução","Entregas Pend.",
                  "Combustíveis","Produtos","Estoque","Equipamentos","Funcionários","Equipes",
                  "Veículos","Relatórios","Suprimentos Kobo","Compras Kobo","EPI","Engenharia",
                  "Backup","Usuários"]
MENUS_OPERADOR = ["Dashboard","Consultar","Entrada","Saída","Devolução","Entregas Pend.",
                  "Estoque","Suprimentos Kobo","Compras Kobo","EPI","Engenharia"]

PASTA       = os.path.join(os.path.expanduser("~"), "Documentos", "Geplan")
PASTA_ALMOX = os.path.join(PASTA, "ALMOXARIFADO")
PASTA_ENG   = os.path.join(PASTA, "ENGENHARIA")
PASTA_BACK  = os.path.join(PASTA, "BACKUPS")
DB_PATH     = os.path.join(PASTA_ALMOX, "geplan.db")
for _p in [PASTA_ALMOX, PASTA_ENG, PASTA_BACK]:
    os.makedirs(_p, exist_ok=True)

# ══════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════
st.markdown("""<style>
.stApp{background:#F5F6FA !important}
.block-container{background:#F5F6FA !important;padding:1.5rem 2rem !important}
[data-testid="stSidebar"]{background:#1E2A3A !important;border-right:1px solid #2C3E52 !important}
[data-testid="stSidebar"] *{color:#CBD5E1 !important}
[data-testid="stSidebar"] .stButton>button{background:transparent !important;color:#CBD5E1 !important;border:none !important;text-align:left !important;font-size:13px !important;padding:7px 14px !important;border-radius:6px !important;width:100% !important;margin:1px 0 !important}
[data-testid="stSidebar"] .stButton>button:hover{background:#2C3E52 !important;color:#fff !important}
[data-testid="stSidebar"] .stButton>button[kind="primary"]{background:#2563EB !important;color:#fff !important}
.gcard{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:12px;padding:18px 20px;margin-bottom:14px;box-shadow:0 1px 3px rgba(0,0,0,0.06)}
.page-header h1{font-size:24px;font-weight:700;color:#1E293B;margin:0}
.page-header p{color:#64748B;font-size:13px;margin:4px 0 0}
.stButton>button{border-radius:8px !important;font-weight:600 !important}
.stButton>button[kind="primary"]{background:#2563EB !important;color:#fff !important;border:none !important}
.stButton>button[kind="primary"]:hover{background:#1D4ED8 !important}
[data-testid="metric-container"]{background:#fff;border:1px solid #E2E8F0;border-radius:12px;padding:14px;box-shadow:0 1px 3px rgba(0,0,0,0.05)}
.stDataFrame{background:#FFFFFF !important;border-radius:10px}
div[data-testid="stExpander"]{background:#fff;border:1px solid #E2E8F0;border-radius:10px}
</style>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# DB
# ══════════════════════════════════════════════
def _db_conn():
    conn = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn

def _db_init():
    conn = _db_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS dados(chave TEXT PRIMARY KEY,valor TEXT NOT NULL,updated TEXT DEFAULT(datetime('now','localtime')));
        CREATE TABLE IF NOT EXISTS obras(id TEXT PRIMARY KEY,setor TEXT,nome TEXT,descricao TEXT DEFAULT'',responsavel TEXT DEFAULT'',data_inicio TEXT DEFAULT'',data_prev TEXT DEFAULT'',status TEXT DEFAULT'ATIVA',criado_em TEXT DEFAULT(datetime('now','localtime')),criado_por TEXT DEFAULT'');
        CREATE TABLE IF NOT EXISTS mov_obras(id INTEGER PRIMARY KEY AUTOINCREMENT,obra_id TEXT,tipo TEXT,descricao TEXT DEFAULT'',valor REAL DEFAULT 0,data TEXT DEFAULT'',usuario TEXT DEFAULT'',criado_em TEXT DEFAULT(datetime('now','localtime')));
    """)
    conn.commit(); conn.close()

_db_init()

def ler(chave):
    try:
        conn = _db_conn()
        row = conn.execute("SELECT valor FROM dados WHERE chave=?",(chave,)).fetchone()
        conn.close()
        if row: return json.loads(row[0])
    except: pass
    _arqs = {"funcionarios":"funcionarios.json","equipes":"equipes.json","produtos":"produtos.json",
             "veiculos":"veiculos.json","movimentos":"movimentos.json","usuarios":"usuarios.json",
             "numeracao":"numeracao.json","entregas":"entregas_pendentes.json",
             "equipamentos":"equipamentos.json","combustiveis":"combustiveis.json",
             "mov_combustiveis":"mov_combustiveis.json","precos_combustiveis":"precos_combustiveis.json",
             "kobo_pedidos":"kobo_pedidos.json","kobo_compras":"kobo_compras.json",
             "epi_validades":"epi_validades.json","mov_equipamentos":"mov_equipamentos.json"}
    for pasta in [PASTA_ALMOX, PASTA]:
        if chave in _arqs:
            p = os.path.join(pasta, _arqs[chave])
            if os.path.exists(p):
                with open(p,"r",encoding="utf-8") as f: dados=json.load(f)
                gravar(chave,dados); return dados
    return {}

def gravar(chave, dados):
    try:
        conn = _db_conn()
        conn.execute("INSERT INTO dados(chave,valor,updated) VALUES(?,?,datetime('now','localtime')) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor,updated=excluded.updated",
                     (chave, json.dumps(dados,ensure_ascii=False)))
        conn.commit(); conn.close(); return True
    except Exception as e:
        st.error(f"Erro DB: {e}"); return False

def hash_senha(s): return hashlib.sha256(s.encode()).hexdigest()

def verificar_login(login, senha):
    usuarios = ler("usuarios")
    if not usuarios:
        admin = {"nome":"Administrador","login":"admin","nivel":"ADMIN","senha":hash_senha("admin123")}
        gravar("usuarios",{"admin":admin})
        usuarios = {"admin":admin}
    h = hash_senha(senha)
    for uid,u in usuarios.items():
        if u.get("login","").lower()==login.lower() and u.get("senha","")==h:
            return u
    return None

def agora(): return datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
def data_hoje(): return datetime.datetime.now().strftime("%d/%m/%Y")
def fmt_preco(v):
    try: return f"R$ {float(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")
    except: return str(v)

def proximo_numero_saida():
    nd=ler("numeracao"); n=int(nd.get("saida",0))+1
    nd["saida"]=n; gravar("numeracao",nd)
    return f"S-{n:06d}"

def grupos_criticos(produtos):
    grp={}
    for cb,p in produtos.items():
        cp=p.get("codigo_produto","").strip(); ch=cp if cp else cb
        em=float(p.get("estoque_min",0) or 0); es=float(p.get("estoque",0))
        if ch not in grp:
            grp[ch]={"total":0.0,"min":em,"nome":p["nome"],"unid":p.get("unid","UNID"),"itens":[]}
        grp[ch]["total"]+=es
        if em>grp[ch]["min"]: grp[ch]["min"]=em
        grp[ch]["itens"].append((cb,p))
    return [(ch,g) for ch,g in grp.items() if g["min"]>0 and g["total"]<=g["min"]]

def funcs_ativos():
    return {k:v for k,v in ler("funcionarios").items() if not v.get("demitido") and v.get("status","ATIVO")=="ATIVO"}

def dias_para_vencer(data_str):
    try:
        d = datetime.datetime.strptime(data_str,"%d/%m/%Y").date()
        return (d - datetime.date.today()).days
    except: return None

def fazer_backup():
    ts=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nome=os.path.join(PASTA_BACK,f"geplan_backup_{ts}.zip")
    with zipfile.ZipFile(nome,"w",zipfile.ZIP_DEFLATED) as z:
        if os.path.exists(DB_PATH): z.write(DB_PATH,"geplan.db")
    backups=sorted([os.path.join(PASTA_BACK,f) for f in os.listdir(PASTA_BACK) if f.startswith("geplan_backup_")])
    for v in backups[:-30]:
        try: os.remove(v)
        except: pass
    return nome

def kobo_buscar(url):
    try:
        req=urllib.request.Request(url,headers={"Authorization":f"Token {KOBO_TOKEN}","Accept":"application/json"})
        with urllib.request.urlopen(req,timeout=15) as r:
            return json.loads(r.read().decode()).get("results",[]),None
    except Exception as e: return [],str(e)

def kobo_extrair_itens(sub):
    itens=[]; CNOME=["DESCRI_O_DO_ITEM","DESCRICAO_DO_ITEM","material","produto","item","nome","MATERIAIS"]
    CQTD=["QUAL_A_QUANTIDADE","quantidade","qtd","qty"]; CMOT=["QUAL_O_MOTIVO_DA_CO","QUAL_O_MOTIVO_DA_COMPRA","motivo"]
    grupos={}
    for k,v in sub.items():
        if "/" in k:
            pref,campo=k.rsplit("/",1)
            grupos.setdefault(pref,{})[campo.strip()]=v
    for pref,campos in sorted(grupos.items()):
        nome=qtd=motivo=""
        for cv,vv in campos.items():
            cu=cv.upper()
            if not nome and any(x.upper() in cu for x in CNOME if len(x)>3): nome=str(vv) if vv else ""
            if not qtd  and any(x.upper() in cu for x in CQTD  if len(x)>2): qtd =str(vv) if vv else ""
            if not motivo and any(x.upper() in cu for x in CMOT if len(x)>4): motivo=str(vv) if vv else ""
        if nome: itens.append({"nome":nome,"qtd":qtd,"motivo":motivo})
    return itens

# ══════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════
for k,v in [("usuario",None),("setor",None),("pagina","Dashboard")]:
    if k not in st.session_state: st.session_state[k]=v

# ══════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════
def tela_login():
    import streamlit.components.v1 as components

    ano_atual   = datetime.datetime.now().year
    setor_sel   = st.session_state.get("_setor_sel", "ALMOXARIFADO")
    almox_act   = "active" if setor_sel == "ALMOXARIFADO" else ""
    eng_act     = "active" if setor_sel == "ENGENHARIA"   else ""
    teal_cl     = "teal"   if setor_sel == "ENGENHARIA"   else ""

    # Visual HTML decorativo
    components.html(f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>
*{{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',sans-serif}}
body{{background:#0F172A;height:100vh;display:flex;overflow:hidden}}
.left{{flex:1;background:#0F172A;display:flex;flex-direction:column;
  justify-content:center;padding:60px 56px;border-right:1px solid #1E2D40}}
.logo{{font-size:44px;font-weight:900;letter-spacing:-1px}}
.ge{{color:#F97316}}.pl{{color:#2563EB}}
.sub{{font-size:13px;color:#64748B;margin-top:8px}}
.line{{width:50px;height:4px;background:#2563EB;border-radius:2px;margin:28px 0}}
.item{{display:flex;align-items:center;gap:10px;padding:8px 0;color:#475569;font-size:13px}}
.ver{{margin-top:auto;padding-top:40px;font-size:11px;color:#1E2D40}}
.right{{width:400px;flex-shrink:0;background:#111827;display:flex;
  flex-direction:column;justify-content:center;padding:52px 44px}}
.title{{font-size:22px;font-weight:700;color:#F1F5F9;margin-bottom:4px}}
.sub2{{font-size:12px;color:#4B5563;margin-bottom:28px}}
</style></head><body>
<div class="left">
  <div class="logo"><span class="ge">GE</span><span class="pl">PLAN</span></div>
  <div class="sub">Sistema de Gestao Operacional</div>
  <div class="line"></div>
  <div class="item">&#128659; Terraplanagem</div>
  <div class="item">&#127959; Obras Publicas e Privadas</div>
  <div class="item">&#128739; Conservacao</div>
  <div class="ver">GEPLAN v5 &middot; {ano_atual}</div>
</div>
<div class="right">
  <div class="title">Acesso ao Sistema</div>
  <div class="sub2">Use o formulario abaixo para entrar</div>
</div>
</body></html>""", height=480, scrolling=False)

    # Esconde elementos do Streamlit
    st.markdown("""<style>
    [data-testid="stHeader"]{display:none !important}
    footer{display:none !important}
    .block-container{padding-top:4px !important}
    </style>""", unsafe_allow_html=True)

    # ── FORMULÁRIO PRINCIPAL ─────────────────────────────
    # Tudo dentro de um único form — sem rerun entre setor e login
    with st.form("login_form", clear_on_submit=False):
        st.markdown("### Entrar no Sistema")

        col1, col2 = st.columns(2)
        with col1:
            setor_input = st.radio(
                "Setor",
                ["📦 Almoxarifado", "🏗️ Engenharia"],
                index=0 if setor_sel == "ALMOXARIFADO" else 1,
                horizontal=False
            )
        with col2:
            usuario_input = st.text_input("Usuário", placeholder="admin")
            senha_input   = st.text_input("Senha", type="password", placeholder="admin123")

        entrar = st.form_submit_button(
            "Entrar →",
            use_container_width=True,
            type="primary"
        )

        if entrar:
            if not usuario_input or not senha_input:
                st.error("⚠️ Preencha usuário e senha!")
            else:
                setor_final = "ENGENHARIA" if "Engenharia" in setor_input else "ALMOXARIFADO"
                usuario_obj = verificar_login(usuario_input.strip(), senha_input)
                if usuario_obj:
                    st.session_state.usuario = usuario_obj
                    st.session_state.setor   = setor_final
                    st.session_state.pagina  = "Engenharia" if setor_final == "ENGENHARIA" else "Dashboard"
                    # Limpa estados temporários
                    for k in ["_setor_sel", "_login_erro"]:
                        if k in st.session_state:
                            del st.session_state[k]
                    st.rerun()
                else:
                    st.error("❌ Usuário ou senha incorretos. Tente: admin / admin123")


def sidebar_app():
    u=st.session_state.usuario; nivel=u.get("nivel","OPERADOR"); setor=st.session_state.setor
    with st.sidebar:
        st.markdown(f"""<div style='padding:8px 0 14px;display:flex;align-items:center;gap:10px'>
          <span style='font-size:20px'>⚙️</span>
          <div><div style='font-size:15px;font-weight:900;color:#fff'>GEPLAN</div>
          <div style='font-size:10px;letter-spacing:1.5px;text-transform:uppercase;color:#64748B'>
          {'📦 Almoxarifado' if setor=='ALMOXARIFADO' else '🏗️ Engenharia'}</div></div></div>""",unsafe_allow_html=True)
        st.divider()
        menus=MENUS_ADMIN if nivel=="ADMIN" else MENUS_OPERADOR
        if setor=="ENGENHARIA": menus=["Engenharia","Dashboard","Backup"]
        icons={"Dashboard":"🏠","Consultar":"🔍","Entrada":"📥","Saída":"📤","Devolução":"↩️",
               "Entregas Pend.":"🚚","Combustíveis":"⛽","Produtos":"📦","Estoque":"📊",
               "Equipamentos":"🔧","Funcionários":"👤","Equipes":"👥","Veículos":"🚗",
               "Relatórios":"📈","Suprimentos Kobo":"📋","Compras Kobo":"🛒",
               "EPI":"🧾","Engenharia":"🏗️","Backup":"💾","Usuários":"👑"}
        for m in menus:
            ativo=st.session_state.pagina==m
            if st.sidebar.button(f"{icons.get(m,'•')}  {m}",key=f"nav_{m}",
                                  use_container_width=True,type="primary" if ativo else "secondary"):
                st.session_state.pagina=m; st.rerun()
        st.divider()
        nome=u.get("nome","").split()[0]
        st.markdown(f"""<div style='font-size:12px;color:#94A3B8'>
          👤 <b style='color:#E8EDF5'>{nome}</b><br>
          <span style='font-size:10px;color:#475569;text-transform:uppercase'>{nivel}</span></div>""",unsafe_allow_html=True)
        if st.button("🚪 Sair",use_container_width=True):
            st.session_state.usuario=None; st.session_state.setor=None; st.rerun()

# ══════════════════════════════════════════════
# HELPER
# ══════════════════════════════════════════════
def pg_header(titulo,subtitulo=""):
    c1,c2=st.columns([4,1])
    with c1: st.markdown(f"<div class='page-header'><h1>{titulo}</h1><p>{subtitulo}</p></div>",unsafe_allow_html=True)
    with c2: st.markdown(f"<p style='text-align:right;color:#64748B;font-size:12px;margin-top:20px'>{datetime.datetime.now().strftime('%d/%m/%Y  %H:%M:%S')}</p>",unsafe_allow_html=True)

# ══════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════
def pg_dashboard():
    pg_header("Dashboard","Visão geral do almoxarifado")
    prods=ler("produtos"); movs=ler("movimentos"); funcs=ler("funcionarios"); equips=ler("equipamentos")
    ativos=sum(1 for f in funcs.values() if not f.get("demitido") and f.get("status","ATIVO")=="ATIVO")
    entradas=sum(1 for m in movs.values() if m.get("tipo")=="ENTRADA")
    saidas=sum(1 for m in movs.values() if m.get("tipo")=="SAÍDA")
    devolucoes=sum(1 for m in movs.values() if m.get("tipo")=="DEVOLUÇÃO")
    valor=sum(float(p.get("preco",0))*float(p.get("estoque",0)) for p in prods.values())
    crit=grupos_criticos(prods)
    entregas=ler("entregas")
    n_pend=sum(1 for v in entregas.values() if v.get("status")=="PENDENTE")

    # KPIs linha 1
    st.markdown("""<style>
    [data-testid="metric-container"]{
        background:#FFFFFF;border:1px solid #E2E8F0;border-radius:12px;
        padding:16px 20px;box-shadow:0 1px 3px rgba(0,0,0,0.06)}
    [data-testid="metric-container"] [data-testid="stMetricLabel"]{
        font-size:12px;color:#64748B;font-weight:500}
    [data-testid="metric-container"] [data-testid="stMetricValue"]{
        font-size:28px;font-weight:700;color:#1E293B}
    </style>""", unsafe_allow_html=True)

    c1,c2,c3,c4,c5=st.columns(5)
    with c1: st.metric("📦 Produtos",len(prods))
    with c2: st.metric("👤 Funcionários",ativos)
    with c3: st.metric("📥 Entradas",entradas)
    with c4: st.metric("📤 Saídas",saidas)
    with c5: st.metric("↩️ Devoluções",devolucoes)

    c6,c7,c8=st.columns(3)
    with c6: st.metric("💰 Valor Estoque",fmt_preco(valor))
    with c7: st.metric("⚠️ Críticos",len(crit),delta=f"-{len(crit)}" if crit else None,delta_color="inverse")
    with c8: st.metric("🔧 Equipamentos",len(equips))

    if crit:
        txt=" · ".join(f"[{ch}] {g['nome']} — Total:{g['total']:.0f} Mín:{g['min']:.0f}" for ch,g in crit[:3])
        st.warning(f"⚠️ {len(crit)} código(s) abaixo do mínimo: {txt}")

    if n_pend>0:
        if st.button(f"🚚 {n_pend} entrega(s) pendente(s) — clique para ver"):
            st.session_state.pagina="Entregas Pend."; st.rerun()

    # Ações rápidas
    st.markdown("### Ações Rápidas")
    b1,b2,b3,b4,b5=st.columns(5)
    with b1:
        if st.button("🔍 Consultar",use_container_width=True): st.session_state.pagina="Consultar"; st.rerun()
    with b2:
        if st.button("📥 Entrada",use_container_width=True,type="primary"): st.session_state.pagina="Entrada"; st.rerun()
    with b3:
        if st.button("📤 Saída",use_container_width=True): st.session_state.pagina="Saída"; st.rerun()
    with b4:
        if st.button("↩️ Devolução",use_container_width=True): st.session_state.pagina="Devolução"; st.rerun()
    with b5:
        if st.button("⛽ Combustível",use_container_width=True): st.session_state.pagina="Combustíveis"; st.rerun()

    # Últimos movimentos
    st.markdown("### Últimos Movimentos")
    ultimas=sorted(movs.items(),key=lambda x:x[1].get("data",""),reverse=True)[:15]
    if ultimas:
        rows=[{"Data":m.get("data","─"),"Nº Pedido":m.get("numero_pedido","─"),
               "Tipo":m.get("tipo","─"),"Produto":m.get("nome","─"),
               "Qtd":f"{m.get('qtd',0)} {m.get('unid','')}".strip(),
               "Equipe":m.get("equipe","─"),"Almox":m.get("almoxarifado","─")} for _,m in ultimas]
        st.dataframe(rows,use_container_width=True,hide_index=True)
    else:
        st.info("Nenhuma movimentação registrada ainda.")

# ══════════════════════════════════════════════
# CONSULTAR
# ══════════════════════════════════════════════
def pg_consultar():
    pg_header("Consultar Produto","Busca por código interno ou código de barras")
    cod=st.text_input("🔍 Código do produto",placeholder="Digite o código interno ou de barras e pressione Enter")
    if not cod: return
    prods=ler("produtos"); p=None; cb_real=cod
    matches=[(k,v) for k,v in prods.items() if v.get("codigo_produto","").upper()==cod.upper()]
    if len(matches)>=1: cb_real,p=matches[0]
    elif cod in prods: p=prods[cod]; cb_real=cod
    if not p: st.warning(f"Produto '{cod}' não encontrado."); return

    # Agrupa marcas
    grp={}
    for k,v in prods.items():
        ch=v.get("codigo_produto","").strip() or k
        grp.setdefault(ch,[]).append((k,v))
    ch_grp=p.get("codigo_produto","").strip() or cb_real
    marcas=grp.get(ch_grp,[])
    total_grp=sum(float(v.get("estoque",0)) for _,v in marcas)
    emin_grp=max((float(v.get("estoque_min",0)) for _,v in marcas),default=0)
    cor="🔴" if total_grp<=emin_grp and emin_grp>0 else "🟢"

    c1,c2=st.columns(2)
    with c1:
        st.markdown(f"""<div class='gcard' style='border-top:3px solid #2563EB'>
        <b style='font-size:16px'>{p['nome']}</b><br><br>
        <b>Cód. Interno:</b> {p.get('codigo_produto','─')}<br>
        <b>Cód. Barras:</b> {cb_real}<br>
        <b>Categoria:</b> {p.get('categoria','─')}<br>
        <b>Unidade:</b> {p.get('unid','─')}<br>
        <b>Preço Unit.:</b> {fmt_preco(p.get('preco',0))}<br>
        <b>Estoque:</b> {p.get('estoque',0)} {p.get('unid','')}<br>
        <b>Estoque Mín.:</b> {p.get('estoque_min',0)}
        </div>""",unsafe_allow_html=True)
    with c2:
        if len(marcas)>1:
            st.markdown(f"""<div class='gcard' style='border-top:3px solid #0D9488'>
            <b>Grupo — Cód. Interno: {ch_grp}</b><br><br>
            {cor} <b>Estoque total:</b> {total_grp:.0f} {p.get('unid','')}<br>
            <b>Mínimo do grupo:</b> {emin_grp:.0f}<br><br>
            <b>Marcas:</b><br>
            {'<br>'.join(f"• {v['nome']} — {v.get('estoque',0)} {v.get('unid','')}" for _,v in marcas)}
            </div>""",unsafe_allow_html=True)
        else:
            st.markdown(f"""<div class='gcard'>
            <b>Estoque</b><br><br>
            {cor} <b>Estoque atual:</b> {p.get('estoque',0)} {p.get('unid','')}<br>
            <b>Mínimo:</b> {emin_grp:.0f}
            </div>""",unsafe_allow_html=True)

    # Histórico de movimentações do produto
    movs=ler("movimentos")
    hist=[m for m in movs.values() if m.get("codigo")==cb_real or
          (p.get("codigo_produto") and any(k==m.get("codigo") for k,_ in marcas))]
    hist=sorted(hist,key=lambda x:x.get("data",""),reverse=True)[:20]
    if hist:
        st.markdown("**Últimas movimentações deste produto:**")
        st.dataframe([{"Data":m.get("data","─"),"Tipo":m.get("tipo","─"),
                       "Qtd":m.get("qtd","─"),"Equipe":m.get("equipe","─"),
                       "Nº Pedido":m.get("numero_pedido","─")} for m in hist],
                     use_container_width=True,hide_index=True)

# ══════════════════════════════════════════════
# ENTRADA
# ══════════════════════════════════════════════
def pg_entrada():
    pg_header("Entrada de Material","Registrar recebimento de materiais no estoque")
    funcs=funcs_ativos()
    with st.form("form_entrada",clear_on_submit=True):
        c1,c2=st.columns(2)
        with c1:
            almox=st.selectbox("Almoxarifado *",ALMOXARIFADOS)
            data_e=st.text_input("Data da Entrada",value=data_hoje())
            nf=st.text_input("Nota Fiscal / Orçamento")
        with c2:
            fornecedor=st.text_input("Fornecedor")
            resp_opts=[f"{n} — {f['nome']}" for n,f in funcs.items()]
            resp=st.selectbox("Responsável Almoxarifado",resp_opts if resp_opts else ["─"])
            obs=st.text_input("Observação")

        st.divider()
        st.markdown("**Item a registrar:**")
        c3,c4,c5=st.columns(3)
        with c3: cod=st.text_input("Código do Produto *",placeholder="Cód. interno ou barras")
        with c4: qtd=st.number_input("Quantidade *",min_value=0.0,step=1.0,format="%.2f")
        with c5: val=st.number_input("Valor Unitário R$",min_value=0.0,step=0.01,format="%.2f")

        if st.form_submit_button("✅ Registrar Entrada",use_container_width=True,type="primary"):
            if not cod or qtd<=0:
                st.error("⚠️ Preencha o código e a quantidade!")
            else:
                prods=ler("produtos"); p=None; cb_real=cod
                for k,v in prods.items():
                    if v.get("codigo_produto","").upper()==cod.upper(): p=v; cb_real=k; break
                if not p: p=prods.get(cod); cb_real=cod
                if not p:
                    st.error(f"❌ Produto '{cod}' não encontrado no cadastro!")
                else:
                    prods[cb_real]["estoque"]=float(prods[cb_real].get("estoque",0))+qtd
                    if val>0: prods[cb_real]["preco"]=val
                    movs=ler("movimentos")
                    movs[str(datetime.datetime.now().timestamp())]={"tipo":"ENTRADA","codigo":cb_real,
                        "nome":p["nome"],"unid":p.get("unid","UNID"),"qtd":qtd,"preco":val,
                        "fornecedor":fornecedor,"nf":nf,"obs":obs,"almoxarifado":almox,
                        "responsavel":resp.split(" — ",1)[1] if " — " in resp else resp,
                        "data":data_e or agora(),"usuario":st.session_state.usuario.get("nome","")}
                    gravar("produtos",prods); gravar("movimentos",movs)
                    st.success(f"✅ Entrada registrada! **{p['nome']}** +{qtd:.0f} {p.get('unid','UNID')} | Novo estoque: **{prods[cb_real]['estoque']:.0f}**")

# ══════════════════════════════════════════════
# SAÍDA
# ══════════════════════════════════════════════
def pg_saida():
    pg_header("Saída de Material","Registrar retirada ou entrega de materiais")
    funcs=funcs_ativos(); equipes=ler("equipes")
    with st.form("form_saida",clear_on_submit=True):
        c1,c2=st.columns(2)
        with c1:
            almox=st.selectbox("Almoxarifado *",ALMOXARIFADOS)
            tipo_saida=st.selectbox("Tipo de Saída",["🏪 Retirada","🚚 Entrega"])
            data_s=st.text_input("Data da Saída",value=data_hoje())
        with c2:
            num_eq=st.text_input("Nº da Equipe",placeholder="Ex: 01")
            resp_opts=[f"{n} — {f['nome']}" for n,f in funcs.items()]
            resp_almox=st.selectbox("Responsável Almoxarifado",resp_opts if resp_opts else ["─"])
            col_opts=[f"{n} — {f['nome']}" for n,f in funcs.items()]
            colaborador=st.selectbox("Colaborador Responsável",col_opts if col_opts else ["─"])

        entregador=""
        if "Entrega" in tipo_saida:
            entregador=st.text_input("Entregador (quem vai levar)")

        st.divider()
        c3,c4=st.columns(2)
        with c3: cod=st.text_input("Código do Produto *",placeholder="Cód. interno ou barras")
        with c4: qtd=st.number_input("Quantidade *",min_value=0.0,step=1.0,format="%.2f")

        b1,b2=st.columns(2)
        with b1: salvar=st.form_submit_button("💾 Finalizar e Salvar",use_container_width=True,type="primary")
        with b2: imprimir=st.form_submit_button("🖨️ Finalizar e Imprimir",use_container_width=True)

        if salvar or imprimir:
            if not cod or qtd<=0: st.error("⚠️ Preencha o código e a quantidade!"); st.stop()
            prods=ler("produtos"); p=None; cb_real=cod
            matches=[(k,v) for k,v in prods.items() if v.get("codigo_produto","").upper()==cod.upper()]
            if len(matches)==1: cb_real,p=matches[0]
            elif len(matches)>1:
                st.warning(f"Código interno '{cod}' tem {len(matches)} marcas. Usando a com mais estoque.")
                cb_real,p=max(matches,key=lambda x:float(x[1].get("estoque",0)))
            else: p=prods.get(cod); cb_real=cod
            if not p: st.error(f"❌ Produto '{cod}' não encontrado!"); st.stop()
            estq=float(p.get("estoque",0))
            if estq<qtd: st.error(f"❌ Estoque insuficiente! Disponível: {estq:.0f} {p.get('unid','')}"); st.stop()

            num_pedido=proximo_numero_saida()
            prods[cb_real]["estoque"]=estq-qtd
            nome_resp=resp_almox.split(" — ",1)[1] if " — " in resp_almox else resp_almox
            nome_col=colaborador.split(" — ",1)[1] if " — " in colaborador else colaborador
            mov={"tipo":"SAÍDA","numero_pedido":num_pedido,"codigo":cb_real,"nome":p["nome"],
                 "unid":p.get("unid","UNID"),"qtd":qtd,"preco":float(p.get("preco",0)),
                 "equipe":num_eq,"colaborador":nome_col,"resp_almox":nome_resp,
                 "tipo_saida":"ENTREGA" if "Entrega" in tipo_saida else "RETIRADA",
                 "entregador":entregador,"almoxarifado":almox,"data":data_s or agora(),
                 "registrado_por":st.session_state.usuario.get("nome","")}
            movs=ler("movimentos"); movs[str(datetime.datetime.now().timestamp())]=mov
            gravar("produtos",prods); gravar("movimentos",movs)

            if "Entrega" in tipo_saida:
                pend=ler("entregas")
                pend[f"{num_pedido}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"]={"numero_pedido":num_pedido,
                    "equipe":num_eq,"colaborador":nome_col,"entregador":entregador,"resp_almox":nome_resp,
                    "registrado_por":mov["registrado_por"],"data_saida":agora(),"almoxarifado":almox,
                    "itens":[{"nome":p["nome"],"qtd":qtd,"unid":p.get("unid","UNID"),"preco":float(p.get("preco",0))}],
                    "status":"PENDENTE","data_confirmacao":""}
                gravar("entregas",pend)

            total=qtd*float(p.get("preco",0))
            st.success(f"✅ Saída registrada! Pedido: **{num_pedido}**")
            st.markdown(f"""<div class='gcard' style='font-family:Courier New,monospace;font-size:13px;line-height:1.9'>
            <b>{'='*42}</b><br>
            &nbsp;&nbsp;&nbsp;ALMOXARIFADO GEPLAN — {almox}<br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;COMPROVANTE DE SAÍDA<br>
            <b>{'='*42}</b><br>
            Nº Pedido&nbsp;: {num_pedido}<br>
            Data/Hora&nbsp;: {agora()}<br>
            Equipe&nbsp;&nbsp;&nbsp;&nbsp;: {num_eq}<br>
            Colaborad.: {nome_col}<br>
            Resp.Almox: {nome_resp}<br>
            Registrado: {mov['registrado_por']}<br>
            Tipo&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;: {'ENTREGA' if 'Entrega' in tipo_saida else 'RETIRADA'}<br>
            {'─'*42}<br>
            {p['nome'][:22]:<22} {qtd:>5.0f} {p.get('unid',''):<5} {fmt_preco(p.get('preco',0)):>10}<br>
            {'─'*42}<br>
            TOTAL&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;: {fmt_preco(total):>10}<br>
            {'─'*42}<br>
            Assinatura: ______________________________<br>
            <b>{'='*42}</b>
            </div>""",unsafe_allow_html=True)

# ══════════════════════════════════════════════
# DEVOLUÇÃO
# ══════════════════════════════════════════════
def pg_devolucao():
    pg_header("Devolução","Devolver material ao estoque")
    with st.form("form_dev",clear_on_submit=True):
        c1,c2=st.columns(2)
        with c1:
            cod=st.text_input("Código do Produto *")
            qtd=st.number_input("Quantidade *",min_value=0.0,step=1.0)
        with c2:
            motivo=st.text_input("Motivo da devolução")
            resp_opts=[f"{n} — {f['nome']}" for n,f in funcs_ativos().items()]
            resp=st.selectbox("Responsável",resp_opts if resp_opts else ["─"])
        if st.form_submit_button("↩️ Registrar Devolução",use_container_width=True,type="primary"):
            if not cod or qtd<=0: st.error("Preencha o código e a quantidade!")
            else:
                prods=ler("produtos"); p=prods.get(cod)
                if not p: st.error("Produto não encontrado!")
                else:
                    prods[cod]["estoque"]=float(prods[cod].get("estoque",0))+qtd
                    movs=ler("movimentos")
                    movs[str(datetime.datetime.now().timestamp())]={"tipo":"DEVOLUÇÃO","codigo":cod,
                        "nome":p["nome"],"unid":p.get("unid","UNID"),"qtd":qtd,"motivo":motivo,
                        "responsavel":resp.split(" — ",1)[1] if " — " in resp else resp,
                        "data":agora(),"usuario":st.session_state.usuario.get("nome","")}
                    gravar("produtos",prods); gravar("movimentos",movs)
                    st.success(f"✅ Devolução registrada! +{qtd:.0f} em '{p['nome']}' | Novo estoque: {prods[cod]['estoque']:.0f}")

# ══════════════════════════════════════════════
# ENTREGAS PENDENTES
# ══════════════════════════════════════════════
def pg_entregas():
    pg_header("Entregas Pendentes","Controle de confirmação de entregas")
    aba=st.radio("",["⏳ Pendentes","✅ Confirmadas","📄 Todas"],horizontal=True)
    entregas=ler("entregas")
    filtro="PENDENTE" if "Pendentes" in aba else "ENTREGUE" if "Confirmadas" in aba else None
    lista=sorted([(k,v) for k,v in entregas.items() if filtro is None or v.get("status")==filtro],
                 key=lambda x:x[1].get("data_saida",""),reverse=True)
    if not lista:
        st.success("✅ Nenhuma entrega pendente!" if filtro=="PENDENTE" else "Nenhum registro."); return
    for chave,v in lista:
        status=v.get("status","PENDENTE")
        with st.container():
            st.markdown(f"---")
            c1,c2=st.columns([3,1])
            with c1:
                badge="⏳ PENDENTE" if status=="PENDENTE" else f"✅ ENTREGUE — {v.get('data_confirmacao','')}"
                st.markdown(f"**🚚 {v.get('numero_pedido','─')}** — {v.get('data_saida','')} | {badge}")
                st.caption(f"👥 Equipe: {v.get('equipe','─')} | 👤 {v.get('colaborador','─')} | 🚗 Entregador: {v.get('entregador','─')} | Almox: {v.get('almoxarifado','─')}")
                st.caption(f"Registrado por: {v.get('registrado_por','─')}")
                for it in v.get("itens",[]):
                    st.caption(f"  📦 {it.get('nome','')} × {it.get('qtd','')} {it.get('unid','')} — {fmt_preco(it.get('preco',0))}")
            with c2:
                if status=="PENDENTE":
                    if st.button("✅ Confirmar Entrega",key=f"conf_{chave}",type="primary"):
                        dados=ler("entregas")
                        dados[chave]["status"]="ENTREGUE"; dados[chave]["data_confirmacao"]=agora()
                        dados[chave]["confirmado_por"]=st.session_state.usuario.get("nome","─")
                        gravar("entregas",dados); st.success("✅ Confirmado!"); st.rerun()
                else:
                    st.caption(f"✅ Por: {v.get('confirmado_por','─')}")

# ══════════════════════════════════════════════
# COMBUSTÍVEIS
# ══════════════════════════════════════════════
def pg_combustiveis():
    pg_header("Combustíveis","Gestão de combustíveis — entrada, saída e abastecimento")
    precos=ler("precos_combustiveis"); comb=ler("combustiveis")

    # Preços e estoque atual
    c_cols=st.columns(len(TIPOS_COMBUSTIVEL))
    for i,tc in enumerate(TIPOS_COMBUSTIVEL):
        with c_cols[i]:
            qtd=float(comb.get(tc,0)); preco=float(precos.get(tc,0))
            st.metric(f"⛽ {tc}",f"{qtd:.1f} L",f"R$ {preco:.2f}/L")

    aba=st.radio("",["📥 Entrada","📤 Saída","🔄 Abastecimento Externo","📊 Movimentações","💰 Atualizar Preços"],horizontal=True)

    if "Entrada" in aba:
        with st.form("f_comb_e",clear_on_submit=True):
            c1,c2,c3=st.columns(3)
            with c1: tipo_c=st.selectbox("Combustível",TIPOS_COMBUSTIVEL)
            with c2: qtd_c=st.number_input("Quantidade (L)",min_value=0.0,step=1.0,format="%.2f")
            with c3: val_c=st.number_input("Valor Total R$",min_value=0.0,step=0.01,format="%.2f")
            c4,c5=st.columns(2)
            with c4: forn_c=st.text_input("Fornecedor")
            with c5: resp_c=st.selectbox("Responsável",[f"{n} — {f['nome']}" for n,f in funcs_ativos().items()] or ["─"])
            if st.form_submit_button("✅ Registrar Entrada",type="primary"):
                if qtd_c<=0: st.error("Informe a quantidade!")
                else:
                    comb2=ler("combustiveis"); comb2[tipo_c]=float(comb2.get(tipo_c,0))+qtd_c
                    if val_c>0 and qtd_c>0: prcos2=ler("precos_combustiveis"); prcos2[tipo_c]=val_c/qtd_c; gravar("precos_combustiveis",prcos2)
                    mov_c=ler("mov_combustiveis")
                    mov_c[str(datetime.datetime.now().timestamp())]={"tipo":"ENTRADA","combustivel":tipo_c,
                        "quantidade":qtd_c,"valor":val_c,"fornecedor":forn_c,
                        "responsavel":resp_c.split(" — ",1)[1] if " — " in resp_c else resp_c,
                        "data":agora(),"usuario":st.session_state.usuario.get("nome","")}
                    gravar("combustiveis",comb2); gravar("mov_combustiveis",mov_c)
                    st.success(f"✅ {qtd_c:.1f}L de {tipo_c} adicionados!"); st.rerun()

    elif "Saída" in aba:
        with st.form("f_comb_s",clear_on_submit=True):
            c1,c2=st.columns(2)
            with c1:
                tipo_c=st.selectbox("Combustível",TIPOS_COMBUSTIVEL)
                qtd_c=st.number_input("Quantidade (L)",min_value=0.0,step=1.0,format="%.2f")
            with c2:
                frota_c=st.text_input("Frota / Veículo")
                eq_c=st.text_input("Equipe")
                km_c=st.text_input("KM / Horímetro")
            resp_c=st.selectbox("Responsável",[f"{n} — {f['nome']}" for n,f in funcs_ativos().items()] or ["─"])
            if st.form_submit_button("✅ Registrar Saída",type="primary"):
                if qtd_c<=0: st.error("Informe a quantidade!")
                else:
                    comb2=ler("combustiveis"); estq=float(comb2.get(tipo_c,0))
                    if estq<qtd_c: st.error(f"Estoque insuficiente! Disponível: {estq:.1f}L")
                    else:
                        comb2[tipo_c]=estq-qtd_c
                        mov_c=ler("mov_combustiveis")
                        preco_u=float(ler("precos_combustiveis").get(tipo_c,0))
                        mov_c[str(datetime.datetime.now().timestamp())]={"tipo":"SAÍDA","combustivel":tipo_c,
                            "quantidade":qtd_c,"valor":qtd_c*preco_u,"frota":frota_c,"equipe":eq_c,
                            "km_ho":km_c,"responsavel":resp_c.split(" — ",1)[1] if " — " in resp_c else resp_c,
                            "data":agora(),"usuario":st.session_state.usuario.get("nome","")}
                        gravar("combustiveis",comb2); gravar("mov_combustiveis",mov_c)
                        st.success(f"✅ {qtd_c:.1f}L de {tipo_c} baixados!"); st.rerun()

    elif "Externo" in aba:
        with st.form("f_comb_ext",clear_on_submit=True):
            c1,c2=st.columns(2)
            with c1:
                tipo_c=st.selectbox("Combustível",TIPOS_COMBUSTIVEL)
                qtd_c=st.number_input("Quantidade (L)",min_value=0.0,step=1.0,format="%.2f")
                val_c=st.number_input("Valor Total R$",min_value=0.0,step=0.01,format="%.2f")
            with c2:
                frota_c=st.text_input("Frota / Veículo")
                eq_c=st.text_input("Equipe"); km_c=st.text_input("KM / Horímetro")
                posto_c=st.text_input("Posto / Fornecedor")
            if st.form_submit_button("✅ Registrar Abastecimento",type="primary"):
                mov_c=ler("mov_combustiveis")
                mov_c[str(datetime.datetime.now().timestamp())]={"tipo":"ABASTECIMENTO EXTERNO",
                    "combustivel":tipo_c,"quantidade":qtd_c,"valor":val_c,"frota":frota_c,
                    "equipe":eq_c,"km_ho":km_c,"fornecedor":posto_c,"data":agora(),
                    "usuario":st.session_state.usuario.get("nome","")}
                gravar("mov_combustiveis",mov_c)
                st.success(f"✅ Abastecimento externo registrado! {qtd_c:.1f}L — {tipo_c}")

    elif "Movimentações" in aba:
        mov_c=ler("mov_combustiveis")
        movs_l=sorted(mov_c.values(),key=lambda m:m.get("data",""),reverse=True)[:30]
        if movs_l:
            st.dataframe([{"Data":m.get("data","─"),"Tipo":m.get("tipo","─"),
                           "Combustível":m.get("combustivel","─"),"Qtd(L)":f"{m.get('quantidade',0):.1f}",
                           "Valor":fmt_preco(m.get("valor",0)),"Frota":m.get("frota","─") or m.get("fornecedor","─"),
                           "Equipe":m.get("equipe","─"),"KM/Ho":m.get("km_ho","─"),
                           "Responsável":m.get("responsavel","─")} for m in movs_l],
                         use_container_width=True,hide_index=True)
        else: st.info("Nenhuma movimentação.")

    elif "Preços" in aba:
        with st.form("f_precos",clear_on_submit=False):
            st.markdown("**Atualizar preços por litro:**")
            novos={}
            cols=st.columns(len(TIPOS_COMBUSTIVEL))
            for i,tc in enumerate(TIPOS_COMBUSTIVEL):
                with cols[i]: novos[tc]=st.number_input(tc,value=float(precos.get(tc,0)),min_value=0.0,step=0.01,format="%.2f")
            if st.form_submit_button("💾 Salvar Preços",type="primary"):
                gravar("precos_combustiveis",novos); st.success("✅ Preços atualizados!"); st.rerun()

# ══════════════════════════════════════════════
# PRODUTOS
# ══════════════════════════════════════════════
def pg_produtos():
    pg_header("Produtos","Cadastro e gestão de produtos")
    aba=st.radio("",["📋 Lista","➕ Novo Produto","✏️ Editar Produto"],horizontal=True)
    prods=ler("produtos")
    if aba=="📋 Lista":
        if not prods: st.info("Nenhum produto cadastrado."); return
        busca=st.text_input("🔍 Buscar",placeholder="Nome, código ou categoria")
        rows=[]
        for cb,p in prods.items():
            if busca and busca.upper() not in cb.upper() and busca.upper() not in p.get("nome","").upper() and busca.upper() not in p.get("categoria","").upper(): continue
            rows.append({"Código":cb,"Cód. Interno":p.get("codigo_produto","─"),"Produto":p["nome"],
                         "Categoria":p.get("categoria","─"),"Unid":p.get("unid","─"),
                         "Estoque":float(p.get("estoque",0)),"Mínimo":float(p.get("estoque_min",0)),
                         "Preço":fmt_preco(p.get("preco",0))})
        st.dataframe(rows,use_container_width=True,hide_index=True)
        st.caption(f"{len(rows)} produto(s) encontrado(s)")

    elif aba=="➕ Novo Produto":
        with st.form("form_prod",clear_on_submit=True):
            c1,c2=st.columns(2)
            with c1:
                cod=st.text_input("Código de Barras *")
                nome=st.text_input("Nome do Produto *")
                cat=st.selectbox("Categoria",CATEGORIAS)
                unid=st.selectbox("Unidade",UNIDADES)
            with c2:
                cod_int=st.text_input("Código Interno (agrupa marcas equiv.)")
                preco=st.number_input("Preço R$",min_value=0.0,step=0.01,format="%.2f")
                emin=st.number_input("Estoque Mínimo",min_value=0.0,step=1.0)
                estq_ini=st.number_input("Estoque Inicial",min_value=0.0,step=1.0)
            if st.form_submit_button("💾 Cadastrar Produto",type="primary"):
                if not cod or not nome: st.error("Preencha código e nome!")
                elif cod in prods: st.error("Código já cadastrado!")
                else:
                    if cod_int:
                        for k,v in prods.items():
                            if v.get("codigo_produto","")==cod_int:
                                st.info(f"ℹ️ Código interno '{cod_int}' já usado em: {v['nome']}")
                    prods[cod]={"nome":nome,"categoria":cat,"unid":unid,"preco":preco,
                                "estoque":estq_ini,"estoque_min":emin,"codigo_produto":cod_int}
                    gravar("produtos",prods); st.success(f"✅ '{nome}' cadastrado com sucesso!")

    else:
        cod_ed=st.selectbox("Selecione o produto",[""] + list(prods.keys()),
                             format_func=lambda x: f"{x} — {prods[x]['nome']}" if x else "Escolha...")
        if cod_ed and cod_ed in prods:
            p=prods[cod_ed]
            with st.form("form_ed",clear_on_submit=False):
                c1,c2=st.columns(2)
                with c1:
                    nome_e=st.text_input("Nome",value=p.get("nome",""))
                    cat_e=st.selectbox("Categoria",CATEGORIAS,index=CATEGORIAS.index(p.get("categoria",CATEGORIAS[0])) if p.get("categoria") in CATEGORIAS else 0)
                    unid_e=st.selectbox("Unidade",UNIDADES,index=UNIDADES.index(p.get("unid",UNIDADES[0])) if p.get("unid") in UNIDADES else 0)
                with c2:
                    cod_int_e=st.text_input("Código Interno",value=p.get("codigo_produto",""))
                    preco_e=st.number_input("Preço R$",value=float(p.get("preco",0)),min_value=0.0,step=0.01,format="%.2f")
                    emin_e=st.number_input("Estoque Mínimo",value=float(p.get("estoque_min",0)),min_value=0.0)
                    estq_e=st.number_input("Estoque Atual",value=float(p.get("estoque",0)),min_value=0.0)
                if st.form_submit_button("💾 Salvar Alterações",type="primary"):
                    prods[cod_ed].update({"nome":nome_e,"categoria":cat_e,"unid":unid_e,
                                          "codigo_produto":cod_int_e,"preco":preco_e,
                                          "estoque_min":emin_e,"estoque":estq_e})
                    gravar("produtos",prods); st.success(f"✅ '{nome_e}' atualizado!")

# ══════════════════════════════════════════════
# ESTOQUE
# ══════════════════════════════════════════════
def pg_estoque():
    pg_header("Estoque","Situação atual dos produtos com alertas de mínimo")
    prods=ler("produtos")
    if not prods: st.info("Nenhum produto cadastrado."); return
    crit=grupos_criticos(prods)
    if crit:
        msgs="\n".join(f"• [{ch}] {g['nome']} ({len(g['itens'])} marca(s)) — Estoque: {g['total']:.0f} | Mínimo: {g['min']:.0f}" for ch,g in crit)
        st.warning(f"⚠️ **{len(crit)} código(s) interno(s) abaixo do mínimo:**\n{msgs}")

    # Filtros
    c1,c2,c3=st.columns(3)
    with c1: busca=st.text_input("🔍 Buscar produto",placeholder="Nome ou código")
    with c2: cat_f=st.selectbox("Categoria",["TODAS"]+CATEGORIAS)
    with c3: alerta_f=st.checkbox("Mostrar apenas críticos")

    # Monta grupos
    grp_all={}
    for cb,p in prods.items():
        ch=p.get("codigo_produto","").strip() or cb
        grp_all.setdefault(ch,{"total":0.0,"min":0.0,"nome":p["nome"],"cat":p.get("categoria","─"),
                                "unid":p.get("unid","UNID"),"valor":0.0,"itens":[]})
        es=float(p.get("estoque",0)); em=float(p.get("estoque_min",0)); pr=float(p.get("preco",0))
        grp_all[ch]["total"]+=es; grp_all[ch]["valor"]+=es*pr
        if em>grp_all[ch]["min"]: grp_all[ch]["min"]=em
        grp_all[ch]["itens"].append((cb,p))

    rows=[]
    for ch,g in grp_all.items():
        if busca and busca.upper() not in g["nome"].upper() and busca.upper() not in ch.upper(): continue
        if cat_f!="TODAS" and g["cat"]!=cat_f: continue
        alerta=g["min"]>0 and g["total"]<=g["min"]
        if alerta_f and not alerta: continue
        rows.append({"":"⚠️" if alerta else "✅","Cód.Interno":ch,
                     "Produto":g["nome"],"Categoria":g["cat"],
                     "Marcas":len(g["itens"]),"Estoque":g["total"],"Mínimo":g["min"],
                     "Unid":g["unid"],"Valor Total":fmt_preco(g["valor"])})

    rows=sorted(rows,key=lambda x:(x[""]=="✅",x["Estoque"]))
    st.dataframe(rows,use_container_width=True,hide_index=True)
    total_val=sum(float(p.get("preco",0))*float(p.get("estoque",0)) for p in prods.values())
    st.caption(f"**{len(rows)} código(s)** | Valor total em estoque: **{fmt_preco(total_val)}**")

# ══════════════════════════════════════════════
# EQUIPAMENTOS
# ══════════════════════════════════════════════
def pg_equipamentos():
    pg_header("Equipamentos","Controle de equipamentos e roçadeiras")
    aba=st.radio("",["📋 Lista","➕ Novo","📋 Movimentações"],horizontal=True)
    equips=ler("equipamentos")

    if aba=="📋 Lista":
        if not equips: st.info("Nenhum equipamento cadastrado."); return
        rows=[{"ID":k,"Nome":v.get("nome","─"),"Tipo":v.get("tipo","─"),
               "Série":v.get("serie","─"),"Status":v.get("status","ATIVO"),
               "Equipe":v.get("equipe","─")} for k,v in equips.items()]
        st.dataframe(rows,use_container_width=True,hide_index=True)

    elif aba=="➕ Novo":
        with st.form("f_eq",clear_on_submit=True):
            c1,c2=st.columns(2)
            with c1:
                eid=st.text_input("ID / Código *")
                nome=st.text_input("Nome *")
                tipo=st.selectbox("Tipo",TIPOS_EQUIP)
            with c2:
                serie=st.text_input("Nº de Série")
                eq=st.text_input("Equipe responsável")
                obs=st.text_input("Observação")
            if st.form_submit_button("💾 Cadastrar",type="primary"):
                if not eid or not nome: st.error("Preencha ID e nome!")
                else:
                    equips[eid]={"nome":nome,"tipo":tipo,"serie":serie,"equipe":eq,"obs":obs,"status":"ATIVO"}
                    gravar("equipamentos",equips); st.success(f"✅ '{nome}' cadastrado!")

    else:
        mov_e=ler("mov_equipamentos")
        rows=[{"Data":m.get("data","─"),"Equipamento":m.get("equipamento","─"),
               "Tipo":m.get("tipo","─"),"Responsável":m.get("responsavel","─"),
               "Obs":m.get("obs","─")} for m in sorted(mov_e.values(),key=lambda x:x.get("data",""),reverse=True)[:30]]
        if rows: st.dataframe(rows,use_container_width=True,hide_index=True)
        else: st.info("Sem movimentações.")

# ══════════════════════════════════════════════
# FUNCIONÁRIOS
# ══════════════════════════════════════════════
def pg_funcionarios():
    pg_header("Funcionários","Cadastro de colaboradores")
    aba=st.radio("",["📋 Lista","➕ Novo","✏️ Editar / Desligar"],horizontal=True)
    funcs=ler("funcionarios"); equipes=ler("equipes")

    if aba=="📋 Lista":
        if not funcs: st.info("Nenhum funcionário."); return
        busca=st.text_input("🔍 Buscar")
        rows=[]
        for k,v in funcs.items():
            if busca and busca.upper() not in v.get("nome","").upper() and busca.upper() not in k.upper(): continue
            status="❌ Desligado" if v.get("demitido") else "✅ Ativo"
            rows.append({"Código":k,"Nome":v.get("nome","─"),"Função":v.get("funcao","─"),
                          "Equipe":v.get("equipe_num","─"),"Status":status})
        st.dataframe(rows,use_container_width=True,hide_index=True)

    elif aba=="➕ Novo":
        with st.form("f_func",clear_on_submit=True):
            c1,c2=st.columns(2)
            with c1:
                cod=st.text_input("Código *"); nome=st.text_input("Nome *")
                funcao=st.text_input("Função / Cargo")
            with c2:
                eq_num=st.text_input("Nº da Equipe")
                cpf=st.text_input("CPF (opcional)")
                tel=st.text_input("Telefone")
            if st.form_submit_button("💾 Cadastrar",type="primary"):
                if not cod or not nome: st.error("Preencha código e nome!")
                elif cod in funcs: st.error("Código já cadastrado!")
                else:
                    funcs[cod]={"nome":nome,"funcao":funcao,"equipe_num":eq_num,"cpf":cpf,"tel":tel,"status":"ATIVO","demitido":False}
                    gravar("funcionarios",funcs); st.success(f"✅ '{nome}' cadastrado!")

    else:
        cod_ed=st.selectbox("Selecione",[""] + list(funcs.keys()),
                             format_func=lambda x: f"{x} — {funcs[x]['nome']}" if x else "Escolha...")
        if cod_ed and cod_ed in funcs:
            v=funcs[cod_ed]
            with st.form("f_func_ed"):
                c1,c2=st.columns(2)
                with c1:
                    nome_e=st.text_input("Nome",value=v.get("nome",""))
                    funcao_e=st.text_input("Função",value=v.get("funcao",""))
                with c2:
                    eq_e=st.text_input("Equipe",value=v.get("equipe_num",""))
                    status_e=st.selectbox("Status",["ATIVO","INATIVO"],index=0 if v.get("status","ATIVO")=="ATIVO" else 1)
                c1b,c2b=st.columns(2)
                with c1b:
                    if st.form_submit_button("💾 Salvar",type="primary"):
                        funcs[cod_ed].update({"nome":nome_e,"funcao":funcao_e,"equipe_num":eq_e,"status":status_e})
                        gravar("funcionarios",funcs); st.success("✅ Atualizado!")
                with c2b:
                    if st.form_submit_button("❌ Desligar funcionário"):
                        funcs[cod_ed]["demitido"]=True; funcs[cod_ed]["status"]="INATIVO"
                        gravar("funcionarios",funcs); st.success(f"'{v['nome']}' desligado.")

# ══════════════════════════════════════════════
# EPI
# ══════════════════════════════════════════════
def pg_epi():
    pg_header("EPI — Validades","Controle de validade e entrega de EPIs")
    aba=st.radio("",["📋 Listar / Buscar","➕ Registrar Entrega","⚠️ Vencidos / Próximos"],horizontal=True)
    epi_vals=ler("epi_validades"); funcs=ler("funcionarios")

    if aba=="📋 Listar / Buscar":
        busca=st.text_input("🔍 Buscar por funcionário")
        itens=[v for v in epi_vals.values() if not busca or busca.upper() in v.get("funcionario","").upper()]
        if not itens: st.info("Nenhum registro encontrado."); return
        hoje=datetime.date.today()
        rows=[]
        for v in sorted(itens,key=lambda x:dias_para_vencer(x.get("proxima_troca","")) or 9999):
            d=dias_para_vencer(v.get("proxima_troca",""))
            if d is None: status="─"
            elif d<0: status=f"🔴 Vencido há {abs(d)}d"
            elif d<=30: status=f"🟡 Vence em {d}d"
            else: status=f"🟢 {d}d"
            rows.append({"Funcionário":v.get("funcionario","─"),"EPI":v.get("epi","─"),
                          "Entregue em":v.get("data_entrega","─"),"Próx. Troca":v.get("proxima_troca","─"),
                          "Status":status,"Responsável":v.get("responsavel","─")})
        st.dataframe(rows,use_container_width=True,hide_index=True)

    elif aba=="➕ Registrar Entrega":
        with st.form("f_epi",clear_on_submit=True):
            c1,c2=st.columns(2)
            with c1:
                func_opts=[f"{k} — {v['nome']}" for k,v in funcs.items() if not v.get("demitido")]
                func_sel=st.selectbox("Funcionário *",func_opts if func_opts else ["─"])
                epi_nome=st.text_input("EPI *",placeholder="Ex: Botina, Capacete, Luva...")
                data_e=st.text_input("Data de Entrega",value=data_hoje())
            with c2:
                prox_troca=st.text_input("Próxima Troca (dd/mm/aaaa)")
                resp_opts=[f"{k} — {v['nome']}" for k,v in funcs_ativos().items()]
                resp=st.selectbox("Responsável Almoxarifado",resp_opts if resp_opts else ["─"])
                obs=st.text_input("Observação")
            if st.form_submit_button("💾 Registrar",type="primary"):
                if not func_sel or not epi_nome: st.error("Selecione o funcionário e informe o EPI!")
                else:
                    nome_func=func_sel.split(" — ",1)[1] if " — " in func_sel else func_sel
                    key=f"{func_sel.split(' — ')[0]}_{epi_nome}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
                    epi_vals[key]={"funcionario":nome_func,"epi":epi_nome,"data_entrega":data_e,
                                   "proxima_troca":prox_troca,"responsavel":resp.split(" — ",1)[1] if " — " in resp else resp,
                                   "obs":obs,"registrado_por":st.session_state.usuario.get("nome","")}
                    gravar("epi_validades",epi_vals); st.success(f"✅ EPI '{epi_nome}' registrado para {nome_func}!")

    else:
        hoje=datetime.date.today()
        vencidos=[v for v in epi_vals.values() if (dias_para_vencer(v.get("proxima_troca","")) or 999)<0]
        proximos=[v for v in epi_vals.values() if 0<=(dias_para_vencer(v.get("proxima_troca","")) or 999)<=30]
        if vencidos:
            st.error(f"🔴 {len(vencidos)} EPI(s) VENCIDO(S):")
            for v in vencidos:
                d=dias_para_vencer(v.get("proxima_troca",""))
                st.write(f"• **{v.get('funcionario','─')}** — {v.get('epi','─')} — Venceu há {abs(d)} dias ({v.get('proxima_troca','─')})")
        if proximos:
            st.warning(f"🟡 {len(proximos)} EPI(s) vencendo em até 30 dias:")
            for v in proximos:
                d=dias_para_vencer(v.get("proxima_troca",""))
                st.write(f"• **{v.get('funcionario','─')}** — {v.get('epi','─')} — Vence em {d} dias ({v.get('proxima_troca','─')})")
        if not vencidos and not proximos:
            st.success("✅ Nenhum EPI vencido ou próximo do vencimento!")

# ══════════════════════════════════════════════
# EQUIPES
# ══════════════════════════════════════════════
def pg_equipes():
    pg_header("Equipes","Cadastro de equipes")
    aba=st.radio("",["📋 Lista","➕ Nova"],horizontal=True)
    equipes=ler("equipes"); funcs=ler("funcionarios")
    if aba=="📋 Lista":
        if not equipes: st.info("Nenhuma equipe."); return
        for num,eq in sorted(equipes.items()):
            membros=[f"{k} — {v['nome']}" for k,v in funcs.items() if v.get("equipe_num")==num and not v.get("demitido")]
            with st.expander(f"👥 Equipe {num} — {eq.get('nome','─')} ({len(membros)} membro(s))"):
                if membros:
                    for m in membros: st.write(f"• {m}")
                else: st.caption("Nenhum funcionário nesta equipe.")
    else:
        with st.form("f_eq_new",clear_on_submit=True):
            c1,c2=st.columns(2)
            with c1: num=st.text_input("Número *"); nome=st.text_input("Nome da Equipe *")
            with c2: resp=st.text_input("Responsável"); veic=st.text_input("Veículo principal")
            if st.form_submit_button("💾 Criar Equipe",type="primary"):
                if not num or not nome: st.error("Preencha número e nome!")
                else:
                    equipes[num]={"nome":nome,"responsavel":resp,"veiculo":veic}
                    gravar("equipes",equipes); st.success(f"✅ Equipe {num} — {nome} criada!")

# ══════════════════════════════════════════════
# VEÍCULOS
# ══════════════════════════════════════════════
def pg_veiculos():
    pg_header("Veículos","Frota de veículos e equipamentos")
    aba=st.radio("",["📋 Lista","➕ Novo"],horizontal=True)
    veics=ler("veiculos")
    if aba=="📋 Lista":
        if not veics: st.info("Nenhum veículo."); return
        rows=[{"Frota":k,"Placa":v.get("placa","─"),"Modelo":v.get("modelo","─"),
               "Tipo":v.get("tipo","─"),"Equipe":v.get("equipe","─"),
               "Status":v.get("status","ATIVO")} for k,v in veics.items()]
        st.dataframe(rows,use_container_width=True,hide_index=True)
    else:
        with st.form("f_veic",clear_on_submit=True):
            c1,c2=st.columns(2)
            with c1: frota=st.text_input("Frota *"); placa=st.text_input("Placa *"); modelo=st.text_input("Modelo")
            with c2:
                tipo=st.selectbox("Tipo",["CAMINHÃO","PICKUP","VAN","MOTO","EQUIPAMENTO","OUTRO"])
                eq=st.text_input("Equipe"); ano=st.text_input("Ano")
            if st.form_submit_button("💾 Cadastrar",type="primary"):
                if not frota or not placa: st.error("Preencha frota e placa!")
                else:
                    veics[frota]={"placa":placa,"modelo":modelo,"tipo":tipo,"equipe":eq,"ano":ano,"status":"ATIVO"}
                    gravar("veiculos",veics); st.success(f"✅ Veículo {placa} cadastrado!")

# ══════════════════════════════════════════════
# RELATÓRIOS
# ══════════════════════════════════════════════
def pg_relatorios():
    pg_header("Relatórios","Análises e exportações")
    aba=st.radio("",["⚠️ Abaixo do Mínimo","📋 Movimentações","💰 Valor por Categoria",
                     "👥 Por Equipe","📊 Resumo Mensal"],horizontal=True)
    prods=ler("produtos"); movs=ler("movimentos")

    if "Mínimo" in aba:
        crit=grupos_criticos(prods)
        if not crit: st.success("✅ Todos os produtos acima do mínimo!"); return
        rows=[{"Cód.Interno":ch,"Produto":g["nome"],"Marcas":len(g["itens"]),
               "Estoque Total":g["total"],"Mínimo":g["min"],"Diferença":g["total"]-g["min"]} for ch,g in crit]
        st.dataframe(rows,use_container_width=True,hide_index=True)

    elif "Movimentações" in aba:
        c1,c2=st.columns(2)
        with c1: tipo_f=st.selectbox("Tipo",["TODOS","ENTRADA","SAÍDA","DEVOLUÇÃO"])
        with c2: busca_f=st.text_input("Buscar produto")
        rows=[]
        for m in sorted(movs.values(),key=lambda x:x.get("data",""),reverse=True):
            if tipo_f!="TODOS" and m.get("tipo")!=tipo_f: continue
            if busca_f and busca_f.upper() not in m.get("nome","").upper(): continue
            rows.append({"Data":m.get("data","─"),"Nº Pedido":m.get("numero_pedido","─"),
                          "Tipo":m.get("tipo","─"),"Produto":m.get("nome","─"),
                          "Qtd":m.get("qtd","─"),"Equipe":m.get("equipe","─"),
                          "Responsável":m.get("responsavel") or m.get("resp_almox","─")})
        st.dataframe(rows,use_container_width=True,hide_index=True)
        st.caption(f"{len(rows)} movimentação(ões)")

    elif "Categoria" in aba:
        por_cat={}
        for p in prods.values():
            cat=p.get("categoria","OUTROS"); val=float(p.get("preco",0))*float(p.get("estoque",0))
            por_cat[cat]=por_cat.get(cat,0)+val
        rows=[{"Categoria":k,"Qtd Produtos":sum(1 for p in prods.values() if p.get("categoria")==k),
               "Valor Total":fmt_preco(v)} for k,v in sorted(por_cat.items(),key=lambda x:-x[1])]
        st.dataframe(rows,use_container_width=True,hide_index=True)

    elif "Equipe" in aba:
        por_eq={}
        for m in movs.values():
            if m.get("tipo")!="SAÍDA": continue
            eq=m.get("equipe","─") or "─"
            por_eq.setdefault(eq,{"qtd":0,"valor":0.0,"movs":0})
            por_eq[eq]["qtd"]+=float(m.get("qtd",0)); por_eq[eq]["movs"]+=1
            por_eq[eq]["valor"]+=float(m.get("qtd",0))*float(m.get("preco",0))
        rows=[{"Equipe":eq,"Saídas":v["movs"],"Qtd Total":f"{v['qtd']:.0f}","Valor Total":fmt_preco(v["valor"])} for eq,v in sorted(por_eq.items())]
        st.dataframe(rows,use_container_width=True,hide_index=True)

    else:
        mes_atual=datetime.datetime.now().month; ano_atual=datetime.datetime.now().year
        rows=[]
        for m in movs.values():
            try:
                d=datetime.datetime.strptime(m.get("data","")[:10],"%d/%m/%Y")
                if d.month==mes_atual and d.year==ano_atual:
                    rows.append({"Data":m.get("data","─"),"Tipo":m.get("tipo","─"),
                                  "Produto":m.get("nome","─"),"Qtd":m.get("qtd","─")})
            except: pass
        st.markdown(f"**Movimentações do mês {mes_atual}/{ano_atual}: {len(rows)}**")
        st.dataframe(rows,use_container_width=True,hide_index=True)

# ══════════════════════════════════════════════
# KOBO SUPRIMENTOS
# ══════════════════════════════════════════════
def pg_kobo_suprim():
    pg_header("Suprimentos Kobo","Pedidos de suprimentos das equipes")
    c1,c2=st.columns([3,1])
    with c2:
        if st.button("🔄 Atualizar",type="primary"):
            with st.spinner("Buscando..."):
                subs,erro=kobo_buscar(KOBO_URL_SUPRIM)
            if erro: st.error(f"❌ {erro}")
            else:
                gravar("kobo_cache_suprim",{"ultima":agora(),"subs":subs})
                st.success(f"✅ {len(subs)} pedido(s)!"); st.rerun()

    cache=ler("kobo_cache_suprim"); subs=cache.get("subs",[]) if cache else []
    hist=ler("kobo_pedidos") or {}
    if cache: st.caption(f"Última atualização: {cache.get('ultima','─')}")
    if not subs: st.info("Clique em 🔄 Atualizar para carregar pedidos."); return

    aba=st.radio("",["⏳ Pendentes","✅ Aprovados","❌ Rejeitados","📄 Todos"],horizontal=True)
    for sub in subs:
        sid=str(sub.get("_id",""))
        proc=hist.get(sid,{}); status_atual=proc.get("status","PENDENTE")
        if aba=="⏳ Pendentes" and status_atual!="PENDENTE": continue
        if aba=="✅ Aprovados" and status_atual!="APROVADO": continue
        if aba=="❌ Rejeitados" and status_atual!="REJEITADO": continue

        itens=kobo_extrair_itens(sub)
        data_sub=sub.get("_submission_time","")[:16].replace("T"," ")
        equipe=sub.get("equipe","") or sub.get("EQUIPE","") or sub.get("_submitted_by","")
        badge_status = "⏳ PENDENTE" if status_atual=="PENDENTE" else ("✅ APROVADO" if status_atual=="APROVADO" else "❌ REJEITADO")
        n_itens = len(itens)

        with st.expander(f"🔍 Pedido #{sid} — {data_sub} — Equipe: {equipe or '─'} — {badge_status} — {n_itens} item(ns)", expanded=status_atual=="PENDENTE"):
            # Mostra todos os campos do pedido
            st.markdown("**📋 Itens solicitados:**")
            if itens:
                for i,it in enumerate(itens,1):
                    nome_it = it.get('nome','─')
                    qtd_it  = it.get('qtd','─')
                    mot_it  = it.get('motivo','─')
                    st.markdown(f"""<div style='background:#F8FAFF;border:1px solid #E2E8F0;border-radius:8px;
                        padding:10px 14px;margin-bottom:8px;font-size:13px'>
                        <b>{i}. {nome_it}</b><br>
                        Quantidade: <b>{qtd_it}</b> &nbsp;|&nbsp; Motivo: {mot_it}
                    </div>""", unsafe_allow_html=True)
            else:
                # Mostra campos brutos se não conseguiu extrair itens
                st.markdown("**Campos do pedido:**")
                campos_uteis = {k:v for k,v in sub.items() if not k.startswith("_") and v and str(v).strip()}
                for k,v in list(campos_uteis.items())[:20]:
                    st.caption(f"**{k}:** {v}")

            st.divider()
            if status_atual=="PENDENTE":
                # Tipo de aprovação
                tipo_aprov = st.radio(
                    "Tipo de aprovação:",
                    ["✅ Aprovar tudo", "⚡ Aprovação parcial"],
                    key=f"tipo_{sid}",
                    horizontal=True
                )

                if "parcial" in tipo_aprov:
                    st.markdown("**Selecione os itens APROVADOS** (desmarcados ficam pendentes):")
                    itens_aprov = []
                    itens_pend  = []
                    for i,it in enumerate(itens):
                        nome_it = it.get("nome","─")
                        qtd_it  = it.get("qtd","─")
                        checked = st.checkbox(
                            f"{nome_it} — Qtd: {qtd_it}",
                            value=True,
                            key=f"chk_{sid}_{i}"
                        )
                        if checked:
                            itens_aprov.append(it)
                        else:
                            itens_pend.append(it)

                    if itens_pend:
                        st.markdown(f"""<div style='background:#FEF3C7;border:1px solid #FCD34D;
                            border-radius:8px;padding:10px 14px;font-size:12px;color:#92400E'>
                            ⚠️ <b>{len(itens_pend)} item(ns) ficarão pendentes:</b>
                            {', '.join(it.get('nome','─') for it in itens_pend)}
                        </div>""", unsafe_allow_html=True)

                    col1,col2=st.columns(2)
                    with col1:
                        if st.button("⚡ Confirmar Parcial", key=f"ap_parc_{sid}", type="primary"):
                            if not itens_aprov:
                                st.error("Selecione pelo menos 1 item para aprovar!")
                            else:
                                prods=ler("produtos"); baixados=[]
                                for it in itens_aprov:
                                    nome_it=it.get("nome","").strip()
                                    for k,p in prods.items():
                                        if nome_it.upper() in p.get("nome","").upper():
                                            try:
                                                qtd_b=float(it.get("qtd",0) or 0)
                                                prods[k]["estoque"]=float(prods[k].get("estoque",0))-qtd_b
                                                baixados.append(f"{p['nome']} -{qtd_b:.0f}")
                                            except: pass
                                            break
                                gravar("produtos",prods)
                                hist[sid]={
                                    "status":"PARCIAL",
                                    "data":agora(),
                                    "usuario":st.session_state.usuario.get("nome",""),
                                    "itens_aprovados":[it.get("nome","") for it in itens_aprov],
                                    "itens_pendentes":[it.get("nome","") for it in itens_pend],
                                }
                                gravar("kobo_pedidos",hist)
                                msg=f"⚡ Aprovação parcial! Aprovados: {len(itens_aprov)} | Pendentes: {len(itens_pend)}"
                                if baixados: msg+=f" | Estoque: {', '.join(baixados)}"
                                st.success(msg); st.rerun()
                    with col2:
                        if st.button("❌ Rejeitar tudo",key=f"rej_parc_{sid}"):
                            hist[sid]={"status":"REJEITADO","data":agora(),"usuario":st.session_state.usuario.get("nome","")}
                            gravar("kobo_pedidos",hist); st.rerun()
                else:
                    # Aprovação integral
                    col1,col2,col3=st.columns([1,1,2])
                    with col1:
                        if st.button("✅ Aprovar Tudo",key=f"ap_{sid}",type="primary"):
                            prods=ler("produtos"); baixados=[]
                            for it in itens:
                                nome_it=it.get("nome","").strip()
                                for k,p in prods.items():
                                    if nome_it.upper() in p.get("nome","").upper():
                                        try:
                                            qtd_b=float(it.get("qtd",0) or 0)
                                            prods[k]["estoque"]=float(prods[k].get("estoque",0))-qtd_b
                                            baixados.append(f"{p['nome']} -{qtd_b:.0f}")
                                        except: pass
                                        break
                            gravar("produtos",prods)
                            hist[sid]={
                                "status":"APROVADO","data":agora(),
                                "usuario":st.session_state.usuario.get("nome",""),
                                "itens_aprovados":[it.get("nome","") for it in itens],
                                "itens_pendentes":[],
                            }
                            gravar("kobo_pedidos",hist)
                            msg="✅ Aprovado!" + (f" Estoque: {', '.join(baixados)}" if baixados else "")
                            st.success(msg); st.rerun()
                    with col2:
                        if st.button("❌ Rejeitar",key=f"rej_{sid}"):
                            hist[sid]={"status":"REJEITADO","data":agora(),"usuario":st.session_state.usuario.get("nome","")}
                            gravar("kobo_pedidos",hist); st.rerun()
                    with col3:
                        st.caption(f"ID: {sid}")

            else:
                cor={"APROVADO":"#DCFCE7","PARCIAL":"#FEF3C7","REJEITADO":"#FEE2E2"}.get(status_atual,"#F1F5F9")
                brd={"APROVADO":"#86EFAC","PARCIAL":"#FCD34D","REJEITADO":"#FCA5A5"}.get(status_atual,"#E2E8F0")
                icn={"APROVADO":"✅","PARCIAL":"⚡","REJEITADO":"❌"}.get(status_atual,"📋")
                st.markdown(f"""<div style='background:{cor};border:1px solid {brd};
                    border-radius:8px;padding:10px 14px;font-size:13px;margin-bottom:8px'>
                    {icn} <b>{status_atual}</b> em {proc.get("data","─")} por {proc.get("usuario","─")}
                </div>""", unsafe_allow_html=True)

                # Mostra itens aprovados e pendentes se parcial
                if status_atual=="PARCIAL":
                    ap=proc.get("itens_aprovados",[])
                    pend=proc.get("itens_pendentes",[])
                    if ap:
                        st.markdown(f"✅ **Aprovados:** {', '.join(ap)}")
                    if pend:
                        st.markdown(f"⏳ **Pendentes:** {', '.join(pend)}")
                        # Botão para reabrir os pendentes
                        if st.button(f"🔄 Reprocessar itens pendentes",key=f"repro_{sid}"):
                            # Cria novo registro só com os itens pendentes
                            hist[sid]["status"]="PARCIAL_REABERTO"
                            gravar("kobo_pedidos",hist)
                            st.info("Itens pendentes marcados para reprocessamento."); st.rerun()

                with st.expander("🔎 Ver todos os campos do pedido"):
                    for k,v in sub.items():
                        if not k.startswith("_") and v:
                            st.caption(f"**{k}:** {v}")

# ══════════════════════════════════════════════
# KOBO COMPRAS
# ══════════════════════════════════════════════
def pg_kobo_compras():
    pg_header("Compras Kobo","Pedidos de compra das equipes")

    c1,c2=st.columns([3,1])
    with c2:
        if st.button("🔄 Atualizar Pedidos",type="primary",use_container_width=True):
            with st.spinner("Buscando pedidos no Kobo..."):
                subs,erro=kobo_buscar(KOBO_URL_COMPRAS)
            if erro:
                st.error(f"❌ Erro ao conectar: {erro}")
            else:
                gravar("kobo_compras_cache",{"ultima":agora(),"subs":subs})
                st.success(f"✅ {len(subs)} pedido(s) carregado(s)!")
                st.rerun()

    cache=ler("kobo_compras_cache")
    subs=cache.get("subs",[]) if cache else []
    hist=ler("kobo_hist_compras") or {}

    if cache:
        st.caption(f"Última atualização: {cache.get('ultima','─')} | {len(subs)} pedido(s) no cache")
    if not subs:
        st.info("Clique em 🔄 Atualizar Pedidos para carregar.")
        return

    # Contadores
    n_pend=sum(1 for s in subs if hist.get(str(s.get("_id","")),{}).get("status","PENDENTE")=="PENDENTE")
    n_aprov=sum(1 for s in subs if hist.get(str(s.get("_id","")),{}).get("status","")=="APROVADO")
    n_rej=sum(1 for s in subs if hist.get(str(s.get("_id","")),{}).get("status","")=="REJEITADO")

    m1,m2,m3,m4=st.columns(4)
    with m1: st.metric("📄 Total",len(subs))
    with m2: st.metric("⏳ Pendentes",n_pend)
    with m3: st.metric("✅ Aprovados",n_aprov)
    with m4: st.metric("❌ Rejeitados",n_rej)

    aba=st.radio("",["⏳ Pendentes","✅ Aprovados","❌ Rejeitados","📄 Todos"],
                 horizontal=True,key="aba_kc")

    for sub in subs:
        sid=str(sub.get("_id",""))
        proc=hist.get(sid,{}); status_atual=proc.get("status","PENDENTE")
        if aba=="⏳ Pendentes" and status_atual!="PENDENTE": continue
        if aba=="✅ Aprovados" and status_atual!="APROVADO": continue
        if aba=="❌ Rejeitados" and status_atual!="REJEITADO": continue

        itens=kobo_extrair_itens(sub)
        data_sub=sub.get("_submission_time","")[:16].replace("T"," ")
        equipe=sub.get("equipe","") or sub.get("EQUIPE","") or sub.get("_submitted_by","") or "─"
        n_itens=len(itens)
        badge_s="⏳ PENDENTE" if status_atual=="PENDENTE" else ("✅ APROVADO" if status_atual=="APROVADO" else "❌ REJEITADO")

        with st.expander(
            f"🔍 Pedido #{sid} — {data_sub} — Equipe: {equipe} — {badge_s} — {n_itens} item(ns)",
            expanded=status_atual=="PENDENTE"
        ):
            # Itens do pedido
            st.markdown("**🛒 Itens solicitados para compra:**")
            if itens:
                for i,it in enumerate(itens,1):
                    nome_it=it.get("nome","─")
                    qtd_it=it.get("qtd","─")
                    mot_it=it.get("motivo","─")
                    st.markdown(f"""<div style='background:#F0FDF4;border:1px solid #BBF7D0;
                        border-radius:8px;padding:10px 14px;margin-bottom:8px;font-size:13px'>
                        <b>{i}. {nome_it}</b><br>
                        Quantidade: <b>{qtd_it}</b> &nbsp;|&nbsp; Motivo: {mot_it}
                    </div>""", unsafe_allow_html=True)
            else:
                st.markdown("**Campos do pedido:**")
                campos={k:v for k,v in sub.items() if not k.startswith("_") and v and str(v).strip()}
                for k,v in list(campos.items())[:20]:
                    st.caption(f"**{k}:** {v}")

            st.divider()
            if status_atual=="PENDENTE":
                c1,c2,c3=st.columns([1,1,2])
                with c1:
                    if st.button("✅ Aprovar",key=f"cap_{sid}",type="primary"):
                        hist[sid]={"status":"APROVADO","data":agora(),
                                   "usuario":st.session_state.usuario.get("nome","")}
                        gravar("kobo_hist_compras",hist)
                        st.success("✅ Pedido de compra aprovado!"); st.rerun()
                with c2:
                    if st.button("❌ Rejeitar",key=f"crej_{sid}"):
                        hist[sid]={"status":"REJEITADO","data":agora(),
                                   "usuario":st.session_state.usuario.get("nome","")}
                        gravar("kobo_hist_compras",hist); st.rerun()
                with c3:
                    st.caption(f"ID Kobo: {sid}")
            else:
                badge="✅ APROVADO" if status_atual=="APROVADO" else "❌ REJEITADO"
                st.info(f"{badge} em {proc.get('data','─')} por {proc.get('usuario','─')}")
                with st.expander("🔎 Ver todos os campos"):
                    for k,v in sub.items():
                        if not k.startswith("_") and v:
                            st.caption(f"**{k}:** {v}")

# ══════════════════════════════════════════════
# USUÁRIOS
# ══════════════════════════════════════════════
def pg_usuarios():
    pg_header("Usuários","Gestão de acesso ao sistema")
    usuarios=ler("usuarios")
    aba=st.radio("",["📋 Lista","➕ Novo Usuário"],horizontal=True)
    if aba=="📋 Lista":
        rows=[{"Login":v.get("login","─"),"Nome":v.get("nome","─"),"Nível":v.get("nivel","─")} for v in usuarios.values()]
        st.dataframe(rows,use_container_width=True,hide_index=True)
        st.caption(f"{len(rows)} usuário(s) cadastrado(s)")
    else:
        with st.form("f_usr",clear_on_submit=True):
            c1,c2=st.columns(2)
            with c1:
                nome=st.text_input("Nome completo *")
                login=st.text_input("Login *",placeholder="sem espaços, minúsculo")
            with c2:
                nivel=st.selectbox("Nível de acesso",["OPERADOR","ADMIN"])
                senha=st.text_input("Senha *",type="password")
                conf=st.text_input("Confirmar senha",type="password")
            if st.form_submit_button("💾 Criar usuário",type="primary"):
                if not nome or not login or not senha: st.error("Preencha todos os campos!")
                elif senha!=conf: st.error("Senhas não coincidem!")
                elif any(v.get("login","").lower()==login.lower() for v in usuarios.values()): st.error("Login já existe!")
                else:
                    uid=login.lower().replace(" ","_")
                    usuarios[uid]={"nome":nome,"login":login.lower(),"nivel":nivel,"senha":hash_senha(senha)}
                    gravar("usuarios",usuarios); st.success(f"✅ Usuário '{login}' criado com nível {nivel}!")

# ══════════════════════════════════════════════
# ENGENHARIA
# ══════════════════════════════════════════════
def listar_obras(setor=None,status=None):
    conn=_db_conn(); q="SELECT * FROM obras WHERE 1=1"; params=[]
    if setor: q+=" AND setor=?"; params.append(setor)
    if status: q+=" AND status=?"; params.append(status)
    q+=" ORDER BY criado_em DESC"
    rows=conn.execute(q,params).fetchall(); conn.close()
    return [dict(r) for r in rows]

def criar_obra(setor,nome,descricao="",responsavel="",data_inicio="",data_prev="",criado_por=""):
    oid=f"{setor[:3]}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    setor_path=os.path.join(PASTA_ENG,setor)
    obra_slug="".join(c for c in nome.upper().replace(" ","_") if c.isalnum() or c in "_-")[:40]
    obra_path=os.path.join(setor_path,f"{oid}_{obra_slug}")
    os.makedirs(obra_path,exist_ok=True)
    for sub in ["DOCUMENTOS","MEDICOES","FOTOS","CONTRATOS","RELATORIOS"]:
        os.makedirs(os.path.join(obra_path,sub),exist_ok=True)
    conn=_db_conn()
    conn.execute("INSERT INTO obras(id,setor,nome,descricao,responsavel,data_inicio,data_prev,status,criado_por) VALUES(?,?,?,?,?,?,?,'ATIVA',?)",
                 (oid,setor,nome,descricao,responsavel,data_inicio,data_prev,criado_por))
    conn.commit(); conn.close()
    return oid,obra_path

def pg_engenharia():
    pg_header("Engenharia","Gestão de obras e projetos")
    c1,c2,c3=st.columns([2,1,1])
    with c1:
        setores_disp=["TODOS","ENGENHARIA"]+sorted(set(o["setor"] for o in listar_obras() if o["setor"] not in ["TODOS","ENGENHARIA"]))
        setor_f=st.selectbox("Setor",setores_disp)
    with c2: status_f=st.selectbox("Status",["TODOS","ATIVA","CONCLUÍDA","SUSPENSA"])
    with c3:
        st.markdown("<br>",unsafe_allow_html=True)
        if st.button("➕ Nova Obra",type="primary",use_container_width=True):
            st.session_state._nova_obra=True

    if getattr(st.session_state,"_nova_obra",False):
        with st.expander("➕ Nova Obra",expanded=True):
            with st.form("f_obra"):
                c1,c2=st.columns(2)
                with c1:
                    setor_n=st.text_input("Setor *",value="ENGENHARIA")
                    nome_o=st.text_input("Nome da Obra *")
                    resp_o=st.text_input("Responsável Técnico")
                with c2:
                    desc_o=st.text_area("Descrição",height=80)
                    data_i=st.text_input("Data de Início",value=data_hoje())
                    data_p=st.text_input("Previsão de Conclusão")
                if st.form_submit_button("💾 Criar Obra",type="primary"):
                    if not nome_o: st.error("Informe o nome da obra!")
                    else:
                        oid,path=criar_obra(setor_n.upper(),nome_o,desc_o,resp_o,data_i,data_p,st.session_state.usuario.get("nome",""))
                        st.success(f"✅ Obra criada! ID: {oid}\nPasta: {path}\nSub-pastas: DOCUMENTOS, MEDICOES, FOTOS, CONTRATOS, RELATORIOS")
                        st.session_state._nova_obra=False; st.rerun()

    obras=listar_obras(None if setor_f=="TODOS" else setor_f, None if status_f=="TODOS" else status_f)
    if not obras: st.info("Nenhuma obra encontrada. Clique em ➕ Nova Obra para começar."); return

    por_setor={}
    for o in obras: por_setor.setdefault(o["setor"],[]).append(o)
    for sn,lista_o in sorted(por_setor.items()):
        st.markdown(f"### 🏢 {sn} — {len(lista_o)} obra(s)")
        for obra in lista_o:
            cor={"ATIVA":"🟢","CONCLUÍDA":"🔵","SUSPENSA":"🔴"}.get(obra["status"],"⚪")
            with st.container():
                c1,c2=st.columns([4,1])
                with c1:
                    st.markdown(f"**🏗️ {obra['nome']}** {cor} {obra['status']}")
                    st.caption(f"ID: {obra['id']} | Resp: {obra['responsavel'] or '─'} | Início: {obra['data_inicio'] or '─'} | Prev: {obra['data_prev'] or '─'}")
                    if obra["descricao"]: st.caption(obra["descricao"])
                with c2:
                    # Status update
                    novo_st=st.selectbox("",["ATIVA","CONCLUÍDA","SUSPENSA"],
                                          index=["ATIVA","CONCLUÍDA","SUSPENSA"].index(obra["status"]),
                                          key=f"st_{obra['id']}")
                    if novo_st!=obra["status"]:
                        conn=_db_conn(); conn.execute("UPDATE obras SET status=? WHERE id=?",(novo_st,obra["id"]))
                        conn.commit(); conn.close(); st.rerun()
            st.divider()

# ══════════════════════════════════════════════
# BACKUP
# ══════════════════════════════════════════════
def pg_backup():
    pg_header("Backup","Gerenciamento de backups do sistema")
    c1,c2=st.columns(2)
    with c1:
        sz=f"{os.path.getsize(DB_PATH)/1024:.1f} KB" if os.path.exists(DB_PATH) else "não encontrado"
        st.markdown(f"""<div class='gcard' style='border-top:3px solid #2563EB'>
        <b>Banco de Dados SQLite</b><br><br>
        📁 <code>{DB_PATH}</code><br>Tamanho: {sz}</div>""",unsafe_allow_html=True)
    with c2:
        backups=sorted([f for f in os.listdir(PASTA_BACK) if f.startswith("geplan_backup_")],reverse=True) if os.path.exists(PASTA_BACK) else []
        ultimo=backups[0] if backups else "nenhum"
        st.markdown(f"""<div class='gcard' style='border-top:3px solid #0D9488'>
        <b>Backups: {len(backups)}</b><br><br>
        Último: {ultimo}<br>📁 <code>{PASTA_BACK}</code></div>""",unsafe_allow_html=True)

    if st.button("💾 Fazer Backup Agora",type="primary"):
        with st.spinner("Criando backup..."):
            arq=fazer_backup()
        st.success(f"✅ Backup salvo: {os.path.basename(arq)}")

    if backups:
        st.markdown("**Últimos backups:**")
        for b in backups[:10]:
            sz_b=os.path.getsize(os.path.join(PASTA_BACK,b))/1024
            st.caption(f"• {b} ({sz_b:.0f} KB)")

    st.markdown("""<div class='gcard'>
    <b>ℹ️ Backup Automático</b><br>
    ✅ Roda automaticamente ao abrir o sistema<br>
    ✅ Mantém os últimos 30 backups<br>
    ✅ Inclui banco de dados completo
    </div>""",unsafe_allow_html=True)

# ══════════════════════════════════════════════
# ROTEADOR
# ══════════════════════════════════════════════
def main():
    if not st.session_state.usuario:
        tela_login(); return
    sidebar_app()
    rotas={"Dashboard":pg_dashboard,"Consultar":pg_consultar,"Entrada":pg_entrada,
           "Saída":pg_saida,"Devolução":pg_devolucao,"Entregas Pend.":pg_entregas,
           "Combustíveis":pg_combustiveis,"Produtos":pg_produtos,"Estoque":pg_estoque,
           "Equipamentos":pg_equipamentos,"Funcionários":pg_funcionarios,"Equipes":pg_equipes,
           "Veículos":pg_veiculos,"Relatórios":pg_relatorios,"Suprimentos Kobo":pg_kobo_suprim,
           "Compras Kobo":pg_kobo_compras,"EPI":pg_epi,"Engenharia":pg_engenharia,
           "Backup":pg_backup,"Usuários":pg_usuarios}
    fn=rotas.get(st.session_state.pagina)
    if fn: fn()
    else: pg_dashboard()

main()

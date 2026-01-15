import streamlit as st
import pandas as pd
import json, base64, os, re, requests, io, sqlite3, glob
import gspread
from google.oauth2.service_account import Credentials
from google import genai
import yfinance as yf
import datetime
import time
import PIL.Image
import plotly.express as px

# ===== Configuração da página =====
st.set_page_config(page_title="PlasPrint IA", page_icon="favicon.ico", layout="wide")

def init_db():
    try:
        conn = sqlite3.connect('fichas_tecnicas.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS custos_tintas (
                cor TEXT PRIMARY KEY,
                preco_litro REAL,
                preco_litro_usd REAL,
                data_atualizacao TEXT
            )
        ''')
        # Populate initial data if empty
        cursor.execute("SELECT count(*) FROM custos_tintas")
        if cursor.fetchone()[0] == 0:
            initial_data = [
                ('cyan', 250.0, 45.0), ('magenta', 250.0, 45.0), ('yellow', 250.0, 45.0),
                ('black', 250.0, 45.0), ('white', 300.0, 55.0), ('varnish', 180.0, 35.0)
            ]
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for cor, brl, usd in initial_data:
                cursor.execute("INSERT INTO custos_tintas VALUES (?, ?, ?, ?)", (cor, brl, usd, now))
            conn.commit()
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fichas_referencia ON fichas(referencia)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fichas_produto ON fichas(produto)")
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Erro ao inicializar banco de dados: {e}")

init_db()

# ===== Funções auxiliares =====
def get_usd_brl_rate():
    if "usd_brl_cache" in st.session_state:
        cached = st.session_state.usd_brl_cache
        if (datetime.datetime.now() - cached["timestamp"]).seconds < 600:
            return cached["rate"]

    rate = None
    url = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
    max_retries = 3
    for attempt in range(max_retries):
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            data = res.json()
            if "USDBRL" in data and "ask" in data["USDBRL"]:
                rate = float(data["USDBRL"]["ask"])
                break
        except:
            pass

    if rate is None:
        try:
            ticker = yf.Ticker("USDBRL=X")
            hist = ticker.history(period="1d")
            if not hist.empty:
                rate = float(hist["Close"].iloc[-1])
        except:
            pass

    st.session_state.usd_brl_cache = {
        "rate": rate,
        "timestamp": datetime.datetime.now()
    }

    return rate

def parse_money_str(s):
    """Parse string de dinheiro, lidando com formato americano e europeu"""
    s = s.strip()
    if s.startswith('$'):
        s = s[1:]
    
    # Remove espaços
    s = s.replace(" ", "")
    
    # Detectar formato: se tem vírgula antes de ponto, é formato europeu
    # Se tem ponto antes de vírgula (ou só ponto com 3 dígitos antes), é formato americano
    
    # Contar ocorrências
    dot_count = s.count('.')
    comma_count = s.count(',')
    
    if comma_count > 0 and dot_count > 0:
        # Ambos presentes - determinar qual é decimal
        last_comma = s.rfind(',')
        last_dot = s.rfind('.')
        
        if last_comma > last_dot:
            # Formato europeu: 1.234.567,89
            s = s.replace('.', '').replace(',', '.')
        else:
            # Formato americano: 1,234,567.89
            s = s.replace(',', '')
    elif comma_count > 0:
        # Só vírgula - pode ser decimal ou separador de milhares
        if comma_count == 1 and len(s.split(',')[1]) <= 2:
            # Provavelmente decimal europeu: 1234,56
            s = s.replace(',', '.')
        else:
            # Separador de milhares: 1,234,567
            s = s.replace(',', '')
    elif dot_count == 1:
        # Um único ponto - pode ser decimal ou milhar
        parts = s.split('.')
        if len(parts[1]) == 3:
            # Se tem 3 dígitos após o ponto e nenhuma vírgula, 
            # em contexto PT-BR/Industrial costuma ser milhar (ex: 250.000)
            s = s.replace('.', '')
        # Se for != 3, deixamos o ponto para o float() tratar como decimal (ex: 1.50 ou 1.2345)
    elif dot_count > 1:
        # Múltiplos pontos = separador de milhares europeu: 1.234.567
        s = s.replace('.', '')
    # else: formato já está correto
    
    try:
        return float(s)
    except:
        return None

def to_brazilian(n):
    if 0 < n < 0.01:
        n = 0.01
    return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def format_dollar_values(text, rate):
    # Regex que ignora R$ (Reais) e captura apenas $ (Dólares)
    # Usa negative lookbehind (?<!R) para garantir que não haja um 'R' antes do '$'
    money_regex = re.compile(r'(?<!R)\$\s?([\d.,]+)')
    found = False

    def repl(m):
        nonlocal found
        found = True
        orig = m.group(0)
        val = parse_money_str(orig)
        if val is None or rate is None:
            return orig
        converted = val * float(rate)
        brl = to_brazilian(converted)
        # Escapamos o $ com \ para evitar que o Streamlit interprete como LaTeX (que muda a fonte e esconde o $)
        return f"{orig.replace('$', r'\$')} (R\\$ {brl})"

    formatted = money_regex.sub(repl, text)

    if found:
        if not formatted.endswith("\n"):
            formatted += "\n"
        formatted += "(valores sem impostos)"

    return formatted

def process_response(texto):
    # Detecta apenas $ (Dólares), ignorando R$ (Reais)
    padrao_dolar = r"(?<!R)\$\s?[\d.,]+"
    if re.search(padrao_dolar, texto):
        rate = get_usd_brl_rate()
        if rate:
            return format_dollar_values(texto, rate)
        else:
            return texto
    return texto

@st.cache_data(ttl=600)
def get_ink_data():
    try:
        conn = sqlite3.connect('fichas_tecnicas.db')
        # Tenta pegar coluna usd também, se não existir (v1 do banco) retorna só brl
        try:
            df = pd.read_sql_query("SELECT cor, preco_litro, preco_litro_usd FROM custos_tintas", conn)
        except:
            df = pd.read_sql_query("SELECT cor, preco_litro FROM custos_tintas", conn)
            df['preco_litro_usd'] = 0.0
            
        conn.close()
        return df.set_index('cor').to_dict('index')
    except:
        return {
            'cyan': {'preco_litro': 250.0, 'preco_litro_usd': 45.0}, 
            'magenta': {'preco_litro': 250.0, 'preco_litro_usd': 45.0}, 
            'yellow': {'preco_litro': 250.0, 'preco_litro_usd': 45.0}, 
            'black': {'preco_litro': 250.0, 'preco_litro_usd': 45.0}, 
            'white': {'preco_litro': 300.0, 'preco_litro_usd': 55.0}, 
            'varnish': {'preco_litro': 180.0, 'preco_litro_usd': 35.0}
        }
        
def get_ink_prices():
    # Helper antigo para compatibilidade
    data = get_ink_data()
    return {k: v['preco_litro'] for k, v in data.items()}

def inject_favicon():
    try:
        with open("favicon.ico", "rb") as f:
            data = base64.b64encode(f.read()).decode()
        st.markdown(f'<link rel="icon" href="data:image/x-icon;base64,{data}" type="image/x-icon" />', unsafe_allow_html=True)
    except:
        pass
inject_favicon()

def get_base64_of_jpg(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

def get_base64_font(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

# ===== Carregar imagens, backgrounds e fontes =====
background_image = "background.jpg"
logo_image = "logo.png"

def get_base64_file(path):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except:
        return ""

img_base64 = get_base64_file(background_image)
img_base64_logo = get_base64_file(logo_image)
font_base64 = get_base64_file("font.ttf")
img_base64_config = get_base64_file("config.png")

st.markdown(f"""
<style>
@font-face {{
    font-family: 'SamsungSharpSans';
    src: url(data:font/ttf;base64,{font_base64}) format('truetype');
}}

/* Aplicar fonte ABSOLUTAMENTE em tudo */
* {{
    font-family: 'SamsungSharpSans', sans-serif !important;
}}

[data-testid="stMetricValue"], 
[data-testid="stTable"], 
[data-testid="stDataFrame"],
.stMarkdown, 
div {{
    font-family: 'SamsungSharpSans', sans-serif !important;
}}

/* RESTAURAR ÍCONES */
[data-testid="stIconMaterial"], 
.material-icons,
.material-symbols-outlined,
i {{
    font-family: 'Material Symbols Outlined', 'Material Icons', 'serif' !important;
}}

/* Correção para o texto no cabeçalho */
header[data-testid="stHeader"] button {{
    font-size: 0 !important;
    color: transparent !important;
    overflow: hidden !important;
}}

header[data-testid="stHeader"] button * {{
    font-size: 0 !important;
    color: transparent !important;
    display: none !important;
    visibility: hidden !important;
}}

/* Recriar o ícone da sidebar */
[data-testid="stSidebarCollapseButton"]::after {{
    content: "〉" !important;
    visibility: visible !important;
    font-size: 22px !important;
    color: white !important;
    display: block !important;
    position: absolute !important;
    left: 50% !important;
    top: 50% !important;
    transform: translate(-50%, -50%) !important;
    font-family: sans-serif !important;
    pointer-events: none !important;
}}

[data-testid="stSidebarCollapseButton"] {{
    background-color: transparent !important;
    border: none !important;
    width: 40px !important;
    height: 40px !important;
    position: relative !important;
}}

header[data-testid="stHeader"] [data-testid="stHeaderActionElements"] button {{
    font-size: 14px !important;
    color: white !important;
}}

h1.custom-font {{
    text-align: center;
    font-size: 380%;
    margin-bottom: 0px;
}}
p.custom-font {{
    font-weight: bold;
    text-align: left;
}}
.stApp {{
    background-image: url("data:image/jpg;base64,{img_base64}");
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    background-attachment: fixed;
}}

    /* Efeito Glassmorphism */
    .glass-card {{
        background: rgba(25, 25, 25, 0.6) !important;
        backdrop-filter: blur(15px) !important;
        -webkit-backdrop-filter: blur(15px) !important;
        border-radius: 15px !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        padding: 20px !important;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.8) !important;
        margin-bottom: 25px !important;
    }}

/* Estilização do chat */
.stChatMessage {{
    background-color: rgba(255, 255, 255, 0.05) !important;
    border-radius: 15px !important;
    padding: 10px !important;
    margin-bottom: 10px !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
}}

.stChatInputContainer {{
    padding-bottom: 20px !important;
}}

/* Remover ícones do chat */
[data-testid="stChatMessageAvatarUser"], 
[data-testid="stChatMessageAvatarAssistant"],
.stChatMessageAvatar {{
    display: none !important;
}}

/* Estilizar o botão para largura total e texto 'Enviar Imagem' */
div[data-testid="stFileUploader"] section,
div[data-testid="stFileUploader"] label {{
    width: 100% !important;
    max-width: 100% !important;
    min-width: 100% !important;
    display: block !important;
    padding: 0 !important;
    margin: 0 !important;
}}

div[data-testid="stFileUploader"] label {{
    display: none !important;
}}

div[data-testid="stFileUploader"] section {{
    background-color: transparent !important;
    border: none !important;
    min-height: 0 !important;
    pointer-events: none !important;
}}

div[data-testid="stFileUploader"] svg,
div[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzoneInstructions"] {{
    display: none !important;
}}

div[data-testid="stFileUploader"] section button {{
    font-family: 'SamsungSharpSans', sans-serif !important;
    width: 100% !important;
    min-width: 100% !important;
    margin: 10px 0 0 0 !important;
    height: 48px !important;
    background-color: rgba(255, 255, 255, 0.1) !important;
    border: 1px solid rgba(255, 255, 255, 0.2) !important;
    border-radius: 8px !important;
    color: transparent !important;
    position: relative !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    pointer-events: auto !important;
    cursor: pointer !important;
}}

div[data-testid="stFileUploader"] section button::before {{
    display: flex !important;
    content: "Enviar Imagem" !important;
    position: absolute !important;
    width: 100% !important;
    height: 100% !important;
    left: 0 !important;
    top: 0 !important;
    align-items: center !important;
    justify-content: center !important;
    color: white !important;
    font-size: 0.95rem !important;
    font-weight: bold !important;
    pointer-events: none !important;
}}

/* MATAR QUALQUER RASTRO EM OUTROS BOTÕES */
div[data-testid="stFileUploader"] button:not(section button),
div[data-testid="stFileUploaderDeleteBtn"],
div[data-testid="stFileUploaderFileData"] button,
button[aria-label="Remove image"] {{
    width: auto !important;
    min-width: 0 !important;
    background-color: transparent !important;
    border: none !important;
}}

div[data-testid="stFileUploader"] button:not(section button)::before,
div[data-testid="stFileUploader"] button:not(section button)::after,
div[data-testid="stFileUploaderDeleteBtn"]::before,
div[data-testid="stFileUploaderFileData"] button::before {{
    content: none !important;
    display: none !important;
}}

/* Botão de Configurações - ALTA PRIORIDADE */
div[data-testid="stPopover"] > button,
div.stPopover > button,
.stPopover > button {{
    position: fixed !important;
    top: 20px !important;
    right: 20px !important;
    z-index: 99999999 !important;
    background-color: transparent !important;
    background-image: url("data:image/png;base64,{img_base64_config}") !important;
    background-size: 28px !important;
    background-repeat: no-repeat !important;
    background-position: center !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 10px !important;
    width: 44px !important;
    height: 44px !important;
    min-width: 44px !important;
    min-height: 44px !important;
    color: transparent !important;
    font-size: 0 !important;
    cursor: pointer !important;
    opacity: 1.0 !important;
    transition: all 0.2s ease !important;
}}

div[data-testid="stPopover"] > button *,
div.stPopover > button *,
.stPopover > button * {{
    display: none !important;
    visibility: hidden !important;
    width: 0 !important;
    height: 0 !important;
    opacity: 0 !important;
}}

div[data-testid="stPopover"] > button:hover,
div.stPopover > button:hover {{
    transform: scale(1.05) !important;
    background-color: rgba(255, 255, 255, 0.05) !important;
    border-color: rgba(255, 255, 255, 0.3) !important;
}}

div[data-testid="stPopover"], div.stPopover {{
    border: none !important;
    background: transparent !important;
}}

/* Estilo para as abas (Tabs) */
[data-testid="stTab"] p {{
    font-size: 1.1rem !important;
    font-weight: bold !important;
    color: rgba(255, 255, 255, 0.6) !important;
    transition: all 0.3s ease !important;
}}

[data-testid="stTab"][aria-selected="true"] {{
    background-color: rgba(0, 210, 255, 0.08) !important;
    border-bottom: 3px solid #00d2ff !important;
}}

[data-testid="stTab"][aria-selected="true"] p {{
    color: #00d2ff !important;
}}

[data-testid="stTab"]:hover p {{
    color: white !important;
}}

/* Remover a linha vermelha padrão do Streamlit */
[data-testid="stTabList"] div[data-baseweb="tab-highlight"] {{
    background-color: transparent !important;
    display: none !important;
}}
</style>
""", unsafe_allow_html=True)
# Estilos customizados para progress bars e feedback visual
st.markdown("""
<style>
/* Progress bars customizadas - Azul Claro para Azul Royal */
.stProgress > div > div > div > div {
    background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%);
    animation: progressPulse 1.5s ease-in-out infinite;
}

@keyframes progressPulse {
    0%, 100% {
        opacity: 1;
    }
    50% {
        opacity: 0.8;
    }
}

/* Spinner customizado (sem rotação no container) - Azul Claro */
.stSpinner > div {
    border-top-color: #00d2ff !important;
}

/* Alertas mais bonitos com borda azul */
.stAlert {
    border-radius: 10px !important;
    border-left: 4px solid #00d2ff !important;
    animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
    from {
        opacity: 0;
        transform: translateY(-10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

/* Success message */
.stSuccess {
    background-color: rgba(40, 167, 69, 0.1) !important;
    border-left-color: #28a745 !important;
}

/* Error message */
.stError {
    background-color: rgba(220, 53, 69, 0.1) !important;
    border-left-color: #dc3545 !important;
}

/* Warning message */
.stWarning {
    background-color: rgba(255, 193, 7, 0.1) !important;
    border-left-color: #ffc107 !important;
}

/* Info message */
.stInfo {
    background-color: rgba(102, 126, 234, 0.1) !important;
    border-left-color: #667eea !important;
}

/* nuclear fix for ghosting/blur/fade during processing */
[data-testid="stAppViewBlockContainer"],
[data-testid="stAppViewBlockContainer"] > div:first-child,
.main .block-container,
.stApp {
    filter: none !important;
    opacity: 1 !important;
    backdrop-filter: none !important;
}

/* also target any element that Streamlit might be dynamically adding filters to */
div[style*="filter"], div[style*="opacity"], div[style*="backdrop-filter"] {
    filter: none !important;
    opacity: 1 !important;
    backdrop-filter: none !important;
}

/* ensure my custom progress bar Pulse still works (it uses opacity) 
   we will scope it specifically so it's not neutralized by the above rule */
.stProgress > div > div > div > div {
    animation: progressPulse 1.5s ease-in-out infinite !important;
}

/* Desativar o overlay de loading que o Streamlit às vezes coloca sobre elementos individuais */
[data-testid="stSkeleton"] {
    display: none !important;
}

/* Aplicar transições apenas a elementos específicos se necessário */
.stButton, .stTextInput, .stFileUploader, .stChatMessage {
    transition: background-color 0.2s ease, transform 0.2s ease !important;
}
</style>
""", unsafe_allow_html=True)


# ===== Segredos =====
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SHEET_ID = st.secrets["SHEET_ID"]
    SERVICE_ACCOUNT_B64 = st.secrets["SERVICE_ACCOUNT_B64"]
except:
    st.error("Configure os segredos GEMINI_API_KEY, SHEET_ID e SERVICE_ACCOUNT_B64.")
    st.stop()

sa_json = json.loads(base64.b64decode(SERVICE_ACCOUNT_B64).decode())
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(sa_json, scopes=scopes)
gc = gspread.authorize(creds)

try:
    sh = gc.open_by_key(SHEET_ID)
except Exception as e:
    st.error(f"Não consegui abrir a planilha: {e}")
    st.stop()

@st.cache_data
def read_ws(name):
    try:
        ws = sh.worksheet(name)
        return pd.DataFrame(ws.get_all_records())
    except Exception as e:
        st.warning(f"Aba '{name}' não pôde ser carregada: {e}")
        return pd.DataFrame()

@st.cache_data
def read_sqlite(table_name):
    try:
        conn = sqlite3.connect('fichas_tecnicas.db')
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Erro ao ler banco de dados local ({table_name}): {e}")
        return pd.DataFrame()

# @st.cache_data -- Desativado temporariamente para garantir refresh dos filtros de hora
def load_oee_data():
    try:
        # Pular as primeiras duas linhas (cabeçalhos originais e tags de índices)
        df = pd.read_excel('oee teep.xlsx', skiprows=1)
        
        # Mapeamento fornecido pelo usuário:
        # B (1): Máquina
        # C (2): Data
        # D (3): Turno
        # E (4): Hora
        # K (10): Teep
        # L (11): OEE
        
        # O pandas lê as colunas B-L (índices 1-11 se usarmos iloc ou nomes se existirem)
        # Vamos usar iloc para garantir os índices
        new_df = pd.DataFrame()
        new_df['maquina'] = df.iloc[:, 1]
        new_df['data'] = df.iloc[:, 2]
        new_df['turno'] = df.iloc[:, 3]
        new_df['hora'] = df.iloc[:, 4]
        new_df['disponibilidade'] = df.iloc[:, 7]
        new_df['performance'] = df.iloc[:, 8]
        new_df['qualidade'] = df.iloc[:, 9]
        new_df['teep'] = df.iloc[:, 10]
        new_df['oee'] = df.iloc[:, 11]
        
        # Filtrar apenas o que tem máquina e data válida
        new_df = new_df[new_df['maquina'].notna()]
        new_df = new_df[~new_df['maquina'].astype(str).str.contains('Turno', na=False)]
        new_df = new_df[new_df['data'].notna()]
        
        # Converter colunas de porcentagem para float
        pct_cols = ['disponibilidade', 'performance', 'qualidade', 'teep', 'oee']
        for col in pct_cols:
            new_df[col] = new_df[col].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
            new_df[col] = pd.to_numeric(new_df[col], errors='coerce').fillna(0) / 100.0
            
        # Converter data para datetime (forçar formato brasileiro Dia/Mês/Ano)
        new_df['data'] = pd.to_datetime(new_df['data'], dayfirst=True, errors='coerce')
        new_df = new_df.dropna(subset=['data'])
        
        # Filtrar apenas o horário produtivo (06:00 às 21:59)
        # Conforme solicitado: média do dia apenas valores de 6 a 21 (Coluna E)
        new_df = new_df[(new_df['hora'] >= 6) & (new_df['hora'] <= 21)]
        
        # Renomear Turnos: 1 -> Turno A, 2 -> Turno B
        def rename_shift(val):
            val_str = str(val).split('.')[0] # Lida com 1.0 ou "1"
            if val_str == '1': return 'Turno A'
            if val_str == '2': return 'Turno B'
            return val
            
        new_df['turno'] = new_df['turno'].apply(rename_shift)
        
        return new_df
    except Exception as e:
        st.error(f"Erro ao carregar oee teep.xlsx: {e}")
        return pd.DataFrame()

def refresh_data():
    """Atualiza todos os dados com feedback visual de progresso"""
    progress_bar = st.sidebar.progress(0)
    status_text = st.sidebar.empty()
    
    status_text.text('Carregando dados de erros...')
    progress_bar.progress(0.15)
    st.session_state.erros_df = read_ws("erros")
    
    status_text.text('Carregando fichas técnicas...')
    progress_bar.progress(0.30)
    st.session_state.trabalhos_df = read_sqlite("fichas")
    
    status_text.text('Carregando dados DACEN...')
    progress_bar.progress(0.45)
    st.session_state.dacen_df = read_ws("dacen")
    
    status_text.text('Carregando dados PSI...')
    progress_bar.progress(0.60)
    st.session_state.psi_df = read_ws("psi")
    
    status_text.text('Carregando dados gerais...')
    progress_bar.progress(0.75)
    st.session_state.gerais_df = read_ws("gerais")

    status_text.text('Carregando dados OEE/TEEP...')
    progress_bar.progress(0.85)
    st.session_state.oee_df = load_oee_data()

    status_text.text('Calculando custos financeiros...')
    progress_bar.progress(0.95)
    st.session_state.precos_tintas = get_ink_prices()
    
    if not st.session_state.trabalhos_df.empty:
        df = st.session_state.trabalhos_df.copy()
        for cor in ['cyan', 'magenta', 'yellow', 'black', 'white', 'varnish']:
            if cor in df.columns:
                preco = st.session_state.precos_tintas.get(cor, 0)
                # Garante que os valores são numéricos
                df[cor] = pd.to_numeric(df[cor], errors='coerce').fillna(0)
                df[f'custo_{cor}'] = df[cor] * preco
        
        # Custo total de tinta (dividido por 1000 para obter custo por unidade, já que o consumo é por 1000un)
        cost_cols = [f'custo_{cor}' for cor in ['cyan', 'magenta', 'yellow', 'black', 'white', 'varnish'] if f'custo_{cor}' in df.columns]
        df['custo_total_tinta_mil'] = df[cost_cols].sum(axis=1)
        df['custo_total_tinta'] = df['custo_total_tinta_mil'] / 1000
        st.session_state.trabalhos_df = df

    progress_bar.progress(1.0)
    status_text.text('Dados carregados com sucesso!')
    time.sleep(0.5)
    progress_bar.empty()
    status_text.empty()

def paginate_dataframe(df, page_size=20, key_prefix="page"):
    """Helper to paginate a dataframe in the UI"""
    if len(df) <= page_size:
        return df
    
    total_pages = (len(df) - 1) // page_size + 1
    page_num = st.number_input(f"Página (de {total_pages})", min_value=1, max_value=total_pages, step=1, key=f"{key_prefix}_num")
    
    start_idx = (page_num - 1) * page_size
    end_idx = start_idx + page_size
    
    st.write(f"Mostrando {start_idx + 1} a {min(end_idx, len(df))} de {len(df)} registros")
    return df.iloc[start_idx:end_idx]

def process_chat_request(prompt, dfs, image=None):
    progress_container = st.empty()
    status_container = st.empty()
    
    try:
        with progress_container:
            progress_bar = st.progress(0)
        
        with status_container:
            st.info('Preparando contexto dos dados...')
        progress_bar.progress(0.20)
        
        with status_container:
            st.info('Processando dados das planilhas...')
        progress_bar.progress(0.40)
        context = build_context(dfs)
        
        # Instruções de sistema para o modelo
        system_instruction = f'''
        Você é o Assistente Técnico PlasPrint IA especializado em flexografia e impressão industrial.
        Responda em português brasileiro de forma estritamente técnica e direta.
        **NUNCA use saudações, introduções ou frases de cortesia.**
        Vá direto ao ponto e forneça a solução ou análise técnica imediatamente.
        Baseie-se nos dados das planilhas fornecidas e nos dados de produção (Excel).

        FORMATO DE RESPOSTA:
        - Use **Tabelas Markdown** para apresentar custos, consumos e parâmetros numéricos.
        - Use **Títulos (##)** ou **Negrito** para separar seções (ex: Tempo de Processo, Custos).
        - Use **Listas (bullet points)** para parâmetros técnicos.
        - Mantenha um espaçamento claro entre parágrafos.
        - **PROIBIDO**: Nunca mostre nomes técnicos de colunas do banco de dados (ex: `config_white`, `id`, `referencia`) entre parênteses ou em qualquer lugar da resposta. Use apenas o nome amigável.

        UNIDADES DE MEDIDA - CONSUMO DE TINTA:
        - **IMPORTANTE**: Os valores brutos nas planilhas (ex: 0.057) representam **ml (mililitros) por unidade (garrafa)**.
        - **DIFERENCIAÇÃO VISUAL OBRIGATÓRIA**: Para evitar confusão, nunca mostre o mesmo número para unidade e milheiro.
        - **Consumo Unitário**: Use o valor bruto (ex: 0.057) e a unidade **ml/garrafa**.
        - **Consumo por Milheiro (1.000 un)**: Multiplique o valor bruto por 1.000 e use a unidade **ml/milheiro** (ex: 57 ml).

        ANÁLISE FINANCEIRA E CUSTOS:
        - **Moeda Brasileira**: Use SEMPRE o prefixo **R$** para custos calculados pelo sistema.
        - **Moeda Americana**: Use o prefixo **$** APENAS se encontrar valores originalmente em dólar.
        - Os preços base por litro são: {st.session_state.precos_tintas} (Valores em R$/L).
        - Considere a margem de {st.session_state.get('margem_lucro', 40)}% sobre o custo unitário.

        TRATAMENTO DE LINKS E MÍDIA:
        - **ESTRUTURA OBRIGATÓRIA**: Para links de imagem, use exatamente: Link de Imagem: [URL].
        - **REGRAS DE RESPOSTA**: Ao citar uma **referência**, você DEVE mostrar também a **decoração** correspondente.
        - **LOCALIZAÇÃO**: Coloque o link imediatamente APÓS descrever o item.
        - **REGRA DE OURO**: Sempre inclua os links das colunas IMAGEM e informações.

        Se a pergunta for sobre OEE ou Eficiência:
        - Analise os dados de Disponibilidade, Performance e Qualidade.
        - Identifique gargalos e motivos de rejeição.

        CONTEXTO DOS DADOS:
        {context}
        '''
        
        full_prompt = [prompt]
        if image:
            full_prompt.append(image)
            with status_container:
                st.info('Analisando imagem enviada...')
        
        # Sistema de retry para lidar com 429 RESOURCE_EXHAUSTED
        max_retries = 5
        retry_delay = 10 # segundos iniciais
        resp = None
        
        for attempt in range(max_retries):
            try:
                # Tenta usar o modelo Flash mais recente disponível
                resp = client.models.generate_content(
                    model="gemini-flash-latest", 
                    contents=full_prompt,
                    config={"system_instruction": system_instruction}
                )
                break # Sucesso, sai do loop
            except Exception as e:
                err_str = str(e).upper()
                if "429" in err_str and attempt < max_retries - 1:
                    # Se atingir o limite, esperamos o tempo de backoff
                    with status_container:
                        st.warning(f"Limite de uso temporário atingido. Aguardando {retry_delay}s para liberar... (Tentativa {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2 # Espera progressivamente mais
                else:
                    raise e # Erro fatal ou última tentativa falhou
        
        with status_container:
            st.info('Formatando resposta...')
        progress_bar.progress(0.90)

        # Limpeza mínima: apenas links de imagem redundantes se houver
        clean_text = re.sub(r'Links de imagens:?', '', resp.text, flags=re.IGNORECASE)
        
        # Limpar indicadores de progresso
        progress_bar.progress(1.0)
        time.sleep(0.3)
        progress_container.empty()
        status_container.empty()
        
        # Renderização Inteligente: Texto + Mídia intercalados
        render_smart_response(clean_text)

    except Exception as e:
        if "progress_container" in locals() and progress_container: progress_container.empty()
        if "status_container" in locals() and status_container: status_container.empty()
        st.error(f"Erro ao processar: {e}")
        st.warning('Dica: Tente reformular sua pergunta ou verifique sua conexão.')

if any(k not in st.session_state for k in ["erros_df", "trabalhos_df", "dacen_df", "psi_df", "gerais_df"]):
    with st.spinner('Carregando dados iniciais do sistema...'):
        refresh_data()

st.sidebar.header("Dados carregados")
st.sidebar.write("erros:", len(st.session_state.get("erros_df", [])))
st.sidebar.write("trabalhos:", len(st.session_state.get("trabalhos_df", [])))
st.sidebar.write("dacen:", len(st.session_state.get("dacen_df", [])))
st.sidebar.write("psi:", len(st.session_state.get("psi_df", [])))
st.sidebar.write("gerais:", len(st.session_state.get("gerais_df", [])))
st.sidebar.write("oee/teep:", len(st.session_state.get("oee_df", [])))

if st.sidebar.button("Atualizar Dados"):
    with st.spinner('Atualizando dados...'):
        refresh_data()
    st.success('Dados atualizados!')
    time.sleep(0.5)
    st.rerun()


os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
client = genai.Client()

def build_context(dfs, max_chars=30000):
    parts = []
    for name, df in dfs.items():
        if df.empty:
            continue
        parts.append(f"--- {name} ---")
        for r in df.to_dict(orient="records"):
            row_items = [f"{k}: {v}" for k,v in r.items() if v is not None and str(v).strip() != '']
            parts.append(" | ".join(row_items))
    context = "\n".join(parts)
    if len(context) > max_chars:
        context = context[:max_chars] + "\n...[CONTEXTO TRUNCADO]"
    return context

@st.cache_data
def load_drive_media(url):
    """Baixa os bytes da mídia do Drive para garantir exibição correta"""
    try:
        file_id = ""
        if "/file/d/" in url: file_id = url.split("/file/d/")[1].split("/")[0]
        elif "id=" in url: file_id = url.split("id=")[1].split("&")[0]
        
        if not file_id: return None
        
        direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        res = requests.get(direct_url, timeout=10)
        if res.status_code == 200:
            return res.content
    except:
        pass
    return None

def get_media_type(url):
    """Identifica mídia por extensão ou padrão de URL, com suporte especial ao Drive"""
    url_lower = url.lower()
    
    # Check by extension first
    if any(ext in url_lower for ext in ['.mp4', '.mov', '.avi', '.m4v', '.webm', '.mkv']):
        return 'video'
    if any(ext in url_lower for ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp']):
        return 'image'
        
    # Special keywords in URL or common Drive sharing patterns
    if "drive.google.com" in url:
        # If it doesn't have an extension, we'll rely on the AI tag or a later request
        return 'drive'
        
    return 'unknown'

def render_smart_response(text):
    """Renderiza texto e mídia de forma intercalada, detectando links de forma robusta"""
    # Procura por "Link de X: URL" ou apenas URLs de mídia soltas
    pattern = r'((?:Link de [A-Za-zãõí\s]+:?\s*)?https?://[^\s\)\n]+)'
    
    parts = re.split(pattern, text, flags=re.IGNORECASE)
    
    for part in parts:
        if not part: continue
        
        match = re.match(r'(?:Link de ([A-Za-zãõí\s]+):?\s*)?(https?://[^\s\)\n]+)', part, re.IGNORECASE)
        
        if match:
            tag = (match.group(1) or "").lower().strip()
            url = match.group(2).strip().replace('`', '')
            
            # Limpa URL de possíveis resíduos de Markdown ou pontuação final
            url = re.sub(r'[.\)\]\s]+$', '', url)
            
            mtype = get_media_type(url)
            
            try:
                # Decidir se é vídeo ou imagem baseado na tag da IA ou tipo detectado
                is_video = 'vídeo' in tag or 'video' in tag or mtype == 'video'
                is_image = 'imagem' in tag or 'foto' in tag or mtype == 'image'
                
                # Para links do Drive, tentamos inferir se é mídia se a tag for genérica
                if mtype == 'drive' and not is_video and not is_image:
                    if any(x in tag for x in ['máquina', 'foto', 'equipamento', 'mídia', 'apresentação']):
                        is_image = True 

                if is_video:
                    if "drive.google.com" in url:
                        file_id = ""
                        if "/file/d/" in url: file_id = url.split("/file/d/")[1].split("/")[0]
                        elif "id=" in url: file_id = url.split("id=")[1].split("&")[0]
                        st.video(f"https://drive.google.com/uc?id={file_id}")
                    else:
                        st.video(url)
                    st.markdown(f"<div style='text-align:center;'><a href='{url}' target='_blank' style='color: #00d2ff;'>Abrir vídeo em nova aba</a></div>", unsafe_allow_html=True)
                elif is_image or mtype == 'image':
                    if "drive.google.com" in url:
                        img_bytes = load_drive_media(url)
                        if img_bytes:
                            st.image(img_bytes, use_container_width=True)
                        else:
                            st.markdown(f"<div style='text-align:center;'><a href='{url}' target='_blank' style='color: #00d2ff;'>Ver Foto (Clique aqui)</a></div>", unsafe_allow_html=True)
                    else:
                        st.image(url, use_container_width=True)
                else:
                    # Se não for mídia clara, mostra botão azul
                    st.markdown(f"<div style='text-align:center; margin: 10px 0;'><a href='{url}' target='_blank' style='background-color: #3a7bd5; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;'>Abrir Conteúdo ({tag or 'Link'})</a></div>", unsafe_allow_html=True)
            except Exception:
                st.markdown(f"🔗 [Acesse o conteúdo aqui]({url})")
        else:
            clean_part = part.strip()
            if clean_part:
                clean_part = re.sub(r'^[\s\n]*[\*\-]\s*', '', clean_part)
                if clean_part:
                    st.markdown(process_response(clean_part))


def remove_drive_links(text):
    return re.sub(r'https?://drive\.google\.com/file/d/[a-zA-Z0-9_-]+/view\?usp=drive_link', '', text)

col_esq, col_meio, col_dir = st.columns([1,3,1])
with col_meio:
    st.markdown("<h1 class='custom-font'>PlasPrint IA</h1><br>", unsafe_allow_html=True)

with col_dir:
    pass  # Coluna direita vazia


with col_meio:

    tab_chat, tab_financeiro, tab_analitico, tab_oee, tab_config = st.tabs([
        "Assistente IA", "Custo", "Analítico", "Oee e Teep", "Configurações"
    ])

    with tab_config:
        st.markdown("### Custos de Tintas (USD)")
        
        
        rate = get_usd_brl_rate()
        if rate:
            st.success(f"💵 Dólar Hoje: R$ {rate:.4f}")
        else:
            st.warning("Não foi possível obter a cotação do dólar.")
            rate = st.number_input("Taxa de Conversão Manual (R$)", value=5.50, min_value=1.0)

        ink_data = get_ink_data()
        
        st.markdown("#### Preços por Litro (em Dólares)")
        with st.form("settings_form"):
            col1, col2 = st.columns(2)
            updates = {}
            
            cores = ['cyan', 'magenta', 'yellow', 'black', 'white', 'varnish']
            for idx, cor in enumerate(cores):
                current_usd = ink_data.get(cor, {}).get('preco_litro_usd', 0.0)
                # Fallback se usd for 0 mas tiver brl
                if current_usd == 0 and ink_data.get(cor, {}).get('preco_litro', 0) > 0:
                     current_usd = ink_data[cor]['preco_litro'] / rate
                
                # Alternar entre colunas
                with col1 if idx % 2 == 0 else col2:
                    updates[cor] = st.number_input(
                        f"{cor.capitalize()} ($/L)", 
                        value=float(current_usd), 
                        step=1.0, 
                        format="%.2f",
                        key=f"ink_{cor}"
                    )
            
            st.markdown("---")
            if st.form_submit_button("💾 Salvar Configurações", use_container_width=True):
                try:
                    conn = sqlite3.connect('fichas_tecnicas.db')
                    cursor = conn.cursor()
                    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    for cor, usd_price in updates.items():
                        brl_price = usd_price * rate
                        # Upsert logical equivalent
                        cursor.execute("""
                            INSERT INTO custos_tintas (cor, preco_litro, preco_litro_usd, data_atualizacao) 
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(cor) DO UPDATE SET 
                                preco_litro=excluded.preco_litro,
                                preco_litro_usd=excluded.preco_litro_usd,
                                data_atualizacao=excluded.data_atualizacao
                        """, (cor, brl_price, usd_price, now))
                        
                    conn.commit()
                    conn.close()
                    st.session_state.precos_tintas = get_ink_prices() # Refresh session
                    st.success("✅ Valores atualizados e convertidos com sucesso!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao salvar: {e}")

    with tab_oee:
        st.subheader("Indicadores de Eficiência (OEE/TEEP)")
        
        if not st.session_state.get("oee_df", pd.DataFrame()).empty:
            df_oee = st.session_state.oee_df.copy()
            
            # Filtros na aba OEE
            st.markdown("#### Filtros")
            c1, c2 = st.columns(2)
            with c1:
                maquinas = ["Todas"] + sorted(df_oee['maquina'].unique().tolist())
                sel_maquina = st.selectbox("Máquina", maquinas)
            with c2:
                min_date = df_oee['data'].min()
                max_date = df_oee['data'].max()
                sel_dates = st.date_input("Período", value=(min_date, max_date), min_value=min_date, max_value=max_date)
            
            # Aplicação dos filtros
            if sel_maquina != "Todas":
                df_oee = df_oee[df_oee['maquina'] == sel_maquina]
            
            if len(sel_dates) == 2:
                df_oee = df_oee[(df_oee['data'] >= pd.Timestamp(sel_dates[0])) & (df_oee['data'] <= pd.Timestamp(sel_dates[1]))]
            
            if not df_oee.empty:
                # Métricas principais
                m1, m2 = st.columns(2)
                with m1:
                    st.metric("OEE Médio", f"{df_oee['oee'].mean()*100:.1f}%")
                with m2:
                    st.metric("TEEP Médio", f"{df_oee['teep'].mean()*100:.1f}%")
                
                # Gráfico de linha temporal com efeito Glass
                st.write("#### Evolução Temporal OEE e TEEP")
                df_daily = df_oee.groupby('data')[['oee', 'teep']].mean().reset_index()
                
                # Criar rótulo com dia da semana em português
                dias_semana = {0: 'Seg', 1: 'Ter', 2: 'Qua', 3: 'Qui', 4: 'Sex', 5: 'Sáb', 6: 'Dom'}
                df_daily['data_label'] = df_daily['data'].dt.strftime('%d/%m') + " (" + df_daily['data'].dt.dayofweek.map(dias_semana) + ")"
                
                fig_line = px.line(df_daily, x='data_label', y=['oee', 'teep'], 
                                  labels={'value': '', 'data_label': '', 'variable': ''},
                                  color_discrete_sequence=['#3a7bd5', '#00d2ff'])
                fig_line.update_traces(hovertemplate='%{y:.1%}')
                fig_line.update_layout(
                    yaxis_tickformat='.1%', 
                    height=400,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(t=20, b=80, l=60, r=40),
                    legend_title_text='',
                    legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5)
                )
                
                st.plotly_chart(fig_line, use_container_width=True)
                
                # Gráfico por hora
                df_hourly = df_oee.groupby('hora')[['oee', 'teep']].mean().reset_index()
                df_hourly_melted = df_hourly.melt(id_vars='hora', var_name='Métrica', value_name='Valor')
                
                fig_hourly = px.bar(df_hourly_melted, x='hora', y='Valor', color='Métrica', 
                                   barmode='group',
                                   text='Valor',
                                   labels={'Valor': '', 'hora': 'Hora', 'Métrica': ''},
                                   color_discrete_sequence=['#3a7bd5', '#00d2ff'])
                
                fig_hourly.update_traces(texttemplate='%{text:.1%}', textposition='outside', hovertemplate='%{y:.1%}')
                fig_hourly.update_layout(
                    yaxis_visible=False,
                    height=450,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(t=50, b=50, l=0, r=0),
                    legend_title_text='',
                    legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5)
                )
                
                st.plotly_chart(fig_hourly, use_container_width=True)
                
                # Gráfico de barras por máquina (se "Todas" selecionado)
                if sel_maquina == "Todas":
                    st.write("#### OEE por Máquina")
                    df_mac = df_oee.groupby('maquina')['oee'].mean().sort_values(ascending=False).reset_index()
                    fig_mac = px.bar(df_mac, x='maquina', y='oee', color='oee', 
                                    text='oee',
                                    color_continuous_scale=['#0a1929', '#00d2ff', '#3a7bd5'],
                                    labels={'oee': 'OEE Médio', 'maquina': 'Máquina'})
                    fig_mac.update_traces(texttemplate='%{text:.1%}', textposition='outside', hovertemplate='%{y:.1%}')
                    fig_mac.update_layout(
                        yaxis_visible=False, 
                        coloraxis_showscale=False,
                        height=450,
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        margin=dict(t=50, b=50, l=0, r=0)
                    )
                    st.plotly_chart(fig_mac, use_container_width=True)
                
                # Novos Gráficos Solicitados
                col_a, col_b = st.columns(2)
                
                with col_a:
                    st.write("#### 1. Comparativo por Turno")
                    df_shift = df_oee.groupby('turno')[['oee', 'teep']].mean().reset_index()
                    fig_shift = px.bar(df_shift, x='turno', y=['oee', 'teep'], barmode='group',
                                      text_auto='.1%',
                                      labels={'value': '', 'variable': '', 'turno': ''},
                                      color_discrete_sequence=['#3a7bd5', '#00d2ff'])
                    fig_shift.update_traces(hovertemplate='%{y:.1%}')
                    fig_shift.update_layout(
                        yaxis_visible=False, height=350,
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        margin=dict(t=30, b=30, l=0, r=0),
                        legend_title_text='',
                        legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5)
                    )
                    st.plotly_chart(fig_shift, use_container_width=True)
                
                with col_b:
                    st.write("#### 2. OEE vs TEEP (Correlação)")
                    fig_scat = px.scatter(df_oee, x='teep', y='oee', color='turno',
                                         hover_data=['maquina', 'hora'],
                                         labels={'teep': 'TEEP', 'oee': 'OEE'},
                                         color_discrete_sequence=['#3a7bd5', '#00d2ff'])
                    fig_scat.update_traces(hovertemplate='TEEP: %{x:.1%}<br>OEE: %{y:.1%}')
                    fig_scat.update_layout(
                        height=350,
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        margin=dict(t=30, b=30, l=40, r=20),
                        legend_title_text=''
                    )
                    st.plotly_chart(fig_scat, use_container_width=True)
                
                col_c, col_d = st.columns(2)
                
                with col_c:
                    st.write("#### 3. Fatores de Perda (Componentes)")
                    # Média dos componentes
                    df_comp = df_oee[['disponibilidade', 'performance', 'qualidade']].mean().reset_index()
                    df_comp.columns = ['Fator', 'Valor']
                    fig_loss = px.bar(df_comp, x='Fator', y='Valor', color='Fator',
                                     text_auto='.1%',
                                     color_discrete_sequence=['#3a7bd5', '#00d2ff', '#4facfe'])
                    fig_loss.update_traces(hovertemplate='%{y:.1%}')
                    fig_loss.update_layout(
                        yaxis_visible=False, showlegend=False, height=350,
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        margin=dict(t=30, b=30, l=0, r=0)
                    )
                    st.plotly_chart(fig_loss, use_container_width=True)
                
                with col_d:
                    st.write("#### 5. Distribuição de Performance")
                    def get_bucket(val):
                        if val < 0.5: return "Baixa (<50%)"
                        if val < 0.8: return "Normal (50-80%)"
                        return "Alta (>80%)"
                    df_oee['faixa'] = df_oee['oee'].apply(get_bucket)
                    df_buckets = df_oee['faixa'].value_counts().reset_index()
                    df_buckets.columns = ['Faixa', 'Quantidade']
                    fig_buckets = px.pie(df_buckets, values='Quantidade', names='Faixa',
                                        hole=0.4, color_discrete_sequence=['#00d2ff', '#3a7bd5', '#4facfe'])
                    fig_buckets.update_layout(
                        height=350,
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        margin=dict(t=30, b=30, l=0, r=0),
                        legend_title_text='',
                        legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5)
                    )
                    st.plotly_chart(fig_buckets, use_container_width=True)
                
                st.write("#### 4. Mapa de Calor: Consistência de OEE (Hora x Dia)")
                # Criar matriz para Heatmap
                df_heat = df_oee.groupby(['data', 'hora'])['oee'].mean().reset_index()
                
                # Converter data para string formatada com dia da semana
                dias_semana = {0: 'Seg', 1: 'Ter', 2: 'Qua', 3: 'Qui', 4: 'Sex', 5: 'Sáb', 6: 'Dom'}
                df_heat['data_str'] = df_heat['data'].dt.strftime('%d/%m') + "<br>(" + df_heat['data'].dt.dayofweek.map(dias_semana) + ")"
                df_pivot = df_heat.pivot(index='hora', columns='data_str', values='oee').fillna(0) * 100
                
                fig_heat = px.imshow(df_pivot, 
                                    labels=dict(x="", y="Hora", color="OEE %"),
                                    color_continuous_scale=['#0a1929', '#3a7bd5', '#00d2ff'],
                                    zmin=0, zmax=100,
                                    aspect="auto")
                fig_heat.update_traces(hovertemplate='Dia: %{x}<br>Hora: %{y}<br>OEE: %{z:.1f}%')
                fig_heat.update_layout(
                    height=450,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(t=30, b=30, l=40, r=40)
                )
                st.plotly_chart(fig_heat, use_container_width=True)
            else:
                st.warning("Nenhum dado encontrado para os filtros selecionados.")
        else:
            st.info("Carregue o arquivo 'oee teep.xlsx' para visualizar as métricas de eficiência.")

    with tab_chat:
        # Input do chat
        prompt = st.chat_input("Qual a sua dúvida?")

        # Upload de imagem
        uploaded_file = st.file_uploader("Enviar Imagem", type=["jpg", "jpeg", "png"], label_visibility="collapsed")

        if prompt:
            # Mostrar mensagem do usuário
            with st.chat_message("user"):
                st.markdown(prompt)
                image_to_send = None
                if uploaded_file:
                    image_to_send = PIL.Image.open(uploaded_file)
                    st.image(image_to_send, caption="Imagem enviada", use_container_width=True)

            # Processar resposta
            with st.chat_message("assistant"):
                dfs = {
                    "erros": st.session_state.erros_df,
                    "trabalhos": st.session_state.trabalhos_df,
                    "dacen": st.session_state.dacen_df,
                    "psi": st.session_state.psi_df,
                    "gerais": st.session_state.gerais_df
                }
                

                process_chat_request(prompt, dfs, image_to_send)



    with tab_financeiro:
        st.subheader("Visão de Custos por Produto")
        
        if not st.session_state.trabalhos_df.empty:
            df_fin = st.session_state.trabalhos_df.copy()
            
            # Filtro de busca no dashboard
            search_fin = st.text_input("Filtrar por Referência ou Produto (Dashboard)", "")
            if search_fin:
                df_fin = df_fin[df_fin['produto'].str.contains(search_fin, case=False, na=False) | 
                                df_fin['referencia'].str.contains(search_fin, case=False, na=False)]
            
            # Métricas rápidas
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Custo Médio (por Garrafa)", f"R$ {df_fin['custo_total_tinta'].mean():.4f}")
            with c2:
                st.metric("Produto Mais Caro (Unidade)", f"R$ {df_fin['custo_total_tinta'].max():.4f}")
            with c3:
                st.metric("Produto Mais Barato (Unidade)", f"R$ {df_fin['custo_total_tinta'].min():.4f}")
            
            st.write("---")
            
            # 1. Top 10 High-Cost Products (Full Width)
            st.write("#### Top 10: Produtos com Maior Custo (1000 un.)")
            df_top10 = df_fin.nlargest(10, 'custo_total_tinta_mil')[['referencia', 'produto', 'decoracao', 'custo_total_tinta_mil']].copy()
            df_top10['label'] = df_top10['referencia'] + " - " + df_top10['produto'] + " (" + df_top10['decoracao'] + ")"
            
            # Ordenar do MAIOR para o MENOR para que o maior fique no TOPO no gráfico horizontal
            df_top10 = df_top10.sort_values('custo_total_tinta_mil', ascending=True)
            
            fig_top10 = px.bar(df_top10, x='custo_total_tinta_mil', y='label', orientation='h',
                              text='custo_total_tinta_mil', color='produto', 
                              labels={'custo_total_tinta_mil': 'Custo (R$)', 'label': 'Produto (Decoração)'},
                              color_discrete_sequence=px.colors.qualitative.Plotly,
                              category_orders={"label": df_top10['label'].tolist()}) # Forçar a ordem exata do DF
            
            fig_top10.update_traces(
                texttemplate='R$ %{text:.2f}', 
                textposition='inside',
                insidetextanchor='start'
            )
            
            fig_top10.update_layout(
                margin=dict(t=20, b=0, l=0, r=0), 
                height=500, 
                showlegend=False,
                xaxis_visible=False,
                coloraxis_showscale=False,
                yaxis={'categoryorder':'array', 'categoryarray': df_top10['label'].tolist()}
            )
            st.plotly_chart(fig_top10, use_container_width=True)

            st.write("---")
            st.write("#### Detalhamento Financeiro (Custo por Unidade)")
            df_disp = df_fin[['referencia', 'decoracao', 'produto', 'custo_total_tinta', 'custo_total_tinta_mil']].copy()
            df_disp.columns = ['Referência', 'Decoração', 'Produto', 'Custo Unitário (R$)', 'Custo 1.000 un (R$)']
            
            st.dataframe(
                df_disp.style.format(precision=4, decimal=',', thousands='.'),
                use_container_width=True
            )
            
            # (Removido sugestão de formação de preço conforme solicitado)
    with tab_analitico:
        st.subheader("Análise de Performance e Consumo")
        
        if not st.session_state.trabalhos_df.empty:
            df_ana = st.session_state.trabalhos_df.copy()
            cores = ['cyan', 'magenta', 'yellow', 'black', 'white', 'varnish']
            df_ana['total_ml'] = df_ana[cores].sum(axis=1)
            
            # --- Métricas Gerais ---
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Total de Fichas", len(df_ana))
            with m2:
                total_vol = df_ana[cores].sum().sum()
                st.metric("Volume Total (ml/1k)", f"{total_vol:.1f}")
            with m3:
                avg_time = df_ana['tempo_s'].mean()
                st.metric("Tempo Médio (s)", f"{avg_time:.1f}")
            with m4:
                most_used_color = df_ana[cores].sum().idxmax()
                st.metric("Cor Mais Usada", most_used_color.capitalize())

            st.write("---")

            # 1. Gráficos de Pizza (lado a lado)
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                st.write("#### Distribuição de Tintas por Cor (%)")
                cons_cor = df_ana[cores].sum().reset_index()
                cons_cor.columns = ['Cor', 'Volume']
                fig_pie = px.pie(cons_cor, values='Volume', names='Cor', color='Cor',
                               color_discrete_map={
                                   'cyan': '#00BFFF', 'magenta': '#FF00FF', 
                                   'yellow': '#FFFF00', 'black': '#444444',
                                   'white': '#FFFFFF', 'varnish': '#C0C0C0'
                               }, hole=0.4)
                fig_pie.update_layout(
                    margin=dict(t=20, b=80, l=0, r=0), 
                    height=450,
                    legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5)
                )
                st.plotly_chart(fig_pie, use_container_width=True)

            with col_chart2:
                st.write("#### Mix de Produtos (Qtd de Fichas)")
                prod_counts = df_ana['produto'].value_counts().reset_index()
                prod_counts.columns = ['produto', 'quantidade']
                fig_prod = px.pie(prod_counts, values='quantidade', names='produto', hole=0.4)
                fig_prod.update_traces(textinfo='percent')
                fig_prod.update_layout(
                    margin=dict(t=20, b=80, l=0, r=0), 
                    height=450,
                    legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5)
                )
                st.plotly_chart(fig_prod, use_container_width=True)

            st.write("---")

            # 2. Gráfico de Barras (Média de Consumo por Cor)
            st.write("#### Média de Consumo por Cor (ml/1k)")
            avg_cons = df_ana[cores].mean().reset_index()
            avg_cons.columns = ['Cor', 'Média de Consumo']
            fig_bar = px.bar(avg_cons, x='Cor', y='Média de Consumo', color='Cor',
                            color_discrete_map={
                                'cyan': '#00BFFF', 'magenta': '#FF00FF', 
                                'yellow': '#FFFF00', 'black': '#444444',
                                'white': '#FFFFFF', 'varnish': '#C0C0C0'
                            })
            fig_bar.update_layout(showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)

            st.write("---")

            # 3. TreeMap (Hierarquia de Consumo)
            st.write("#### Hierarquia de Consumo (Decoração > Produto)")
            fig_tree = px.treemap(df_ana, path=['decoracao', 'produto'], values='total_ml',
                                 color='total_ml', color_continuous_scale='Viridis',
                                 labels={'total_ml': '', 'decoracao': 'Decoração', 'produto': 'Produto'})
            fig_tree.update_layout(coloraxis_showscale=False)
            st.plotly_chart(fig_tree, use_container_width=True)

            st.write("---")
            
            # 4. Explorador de Performance Geral
            st.write("#### Explorador de Performance e Consumo Técnico")
            
            df_tec = df_ana.copy()
            media_total = df_ana['total_ml'].mean()
            alto_consumo_count = len(df_ana[df_ana['total_ml'] > media_total * 1.5])
            
            st.info(f"Média Geral de Consumo: {media_total:.2f} ml | Itens com consumo elevado (>50% da média): {alto_consumo_count}")
            
            df_tec_disp = df_tec[['referencia', 'decoracao', 'produto', 'total_ml', 'tempo_s']].copy()
            df_tec_disp.columns = ['Referência', 'Decoração', 'Produto', 'Consumo Total (ml)', 'Tempo (s)']
            
            st.dataframe(df_tec_disp, use_container_width=True, hide_index=True)

            # --- 5. Relatório Analítico Gerado por IA (ao final) ---
            st.write("---")
            st.markdown("### Relatório Analítico (PlasPrint IA)")
            
            @st.cache_data(ttl=3600)
            def generate_analytical_report(stats_json):
                try:
                    stats = json.loads(stats_json)
                    prompt = f"""
                    Como Assistente Técnico de Impressão Digital PlasPrint IA, analise os seguintes dados de produção e consumo (nosso processo é de IMPRESSÃO DIGITAL):
                    - Total de Fichas: {stats['total_fichas']}
                    - Consumo Médio Total: {stats['media_ml']:.2f} ml/1k
                    - Tempo Médio de Produção: {stats['media_tempo']:.1f} segundos
                    - Cor Predominante: {stats['cor_lider']}
                    - Volume Total de Tintas: {stats['volume_total']:.1f} ml
                    - Itens com Consumo Elevado: {stats['itens_criticos']}
                    - Distribuição por Produto: {stats['prod_dist']}
                    
                    Gere um resumo executivo muito simples e direto (máximo de 3 parágrafos) focado nos pontos críticos e oportunidades de economia. Evite termos de flexografia ou processos analógicos. Vá direto ao ponto.
                    """
                    response = client.models.generate_content(
                        model="gemini-flash-latest",
                        contents=[prompt],
                        config={"system_instruction": "Você é um especialista em análise de dados industriais e impressão digital industrial."}
                    )
                    return response.text
                except Exception as e:
                    return f"Não foi possível gerar o relatório no momento: {e}"

            prod_cons_data = df_ana.groupby('produto')['total_ml'].sum().sort_values(ascending=False)
            prod_dist_str = ", ".join([f"{k}: {v:.1f}ml" for k, v in prod_cons_data.head(5).to_dict().items()])
            
            stats_data = {
                "total_fichas": len(df_ana),
                "media_ml": df_ana['total_ml'].mean(),
                "media_tempo": df_ana['tempo_s'].mean(),
                "cor_lider": df_ana[cores].sum().idxmax().capitalize(),
                "volume_total": df_ana[cores].sum().sum(),
                "itens_criticos": len(df_ana[df_ana['total_ml'] > df_ana['total_ml'].mean() * 1.5]),
                "prod_dist": prod_dist_str
            }
            
            with st.spinner("IA analisando dados..."):
                report = generate_analytical_report(json.dumps(stats_data))
                st.markdown(f"""
                <div style="background-color: rgba(0, 210, 255, 0.05); padding: 20px; border-radius: 10px; border-left: 5px solid #00d2ff; margin-bottom: 25px;">
                    {report}
                </div>
                """, unsafe_allow_html=True)

        else:
            st.info("Nenhum dado disponível para análise analítica.")


# Footer
footer_css = """
<style>
.footer-container { width: 100%; text-align: center; margin-top: 50px; padding-bottom: 20px; }
.logo-footer { width: 120px; opacity: 0.6; transition: opacity 0.3s ease; margin-bottom: 10px; }
.logo-footer:hover { opacity: 1.0; }
.version-tag { font-size: 12px; color: white; opacity: 0.5; }
[data-testid="stAppViewBlockContainer"] { padding-bottom: 150px !important; }
</style>
"""

footer_html = f"""
<div class='footer-container'>
    <img src="data:image/png;base64,{img_base64_logo}" class="logo-footer"><br>
    <div class='version-tag'>V2.0</div>
</div>
"""

st.markdown(footer_css + footer_html, unsafe_allow_html=True)











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

st.markdown(f"""
<style>
@font-face {{
    font-family: 'SamsungSharpSans';
    src: url(data:font/ttf;base64,{font_base64}) format('truetype');
}}

/* Aplicar fonte ABSOLUTAMENTE em tudo: textos, números, métricas e tabelas */
* {{
    font-family: 'SamsungSharpSans', sans-serif !important;
}}

/* Garantir que métricas e dataframes (tabelas) herdem corretamente */
[data-testid="stMetricValue"], 
[data-testid="stTable"], 
[data-testid="stDataFrame"],
.stMarkdown, 
div {{
    font-family: 'SamsungSharpSans', sans-serif !important;
}}

/* RESTAURAR ÍCONES: Impedir que a fonte customizada sobrescreva os glifos/ligaduras */
[data-testid="stIconMaterial"], 
.material-icons,
.material-symbols-outlined,
i {{
    font-family: 'Material Symbols Outlined', 'Material Icons', 'serif' !important;
}}

/* Correção RADICAL para o texto 'keyboard_double_arrow_right' no cabeçalho */
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

/* Recriar o ícone da sidebar (seta/menu) de forma limpa */
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

/* Estilo do botão em si */
[data-testid="stSidebarCollapseButton"] {{
    background-color: transparent !important;
    border: none !important;
    width: 40px !important;
    height: 40px !important;
    position: relative !important;
}}

/* Garante que o botão de Deploy e Menu (direita) não sumam texto se necessário, 
   mas como o 'Deploy' costuma ser um span específico, vamos isolá-los */
header[data-testid="stHeader"] [data-testid="stHeaderActionElements"] button {{
    font-size: 14px !important; /* Restaura tamanho para botões da direita */
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
    display: none !important; /* Esconde o rótulo redundante */
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
/* APENAS o botão principal de upload (dentro da section) deve ter largura total e estilo customizado */
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

/* Texto do botão principal */
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

/* MATAR QUALQUER RASTRO EM OUTROS BOTÕES (Excluir, etc) */
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

/* Posicionamento e Estilo do Botão de Configurações (Engrenagem) */
.fixed-settings {{
    position: fixed !important;
    top: 15px !important;
    right: 15px !important;
    z-index: 999999 !important;
}}

/* Alvo direto em qualquer botão dentro do container fixo */
.fixed-settings button {{
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
    min-height: 0 !important;
    min-width: 0 !important;
    width: auto !important;
    height: auto !important;
    color: transparent !important; /* Esconde o emoji original */
}}

/* Esconder a seta e qualquer SVG */
.fixed-settings button svg {{
    display: none !important;
}}

/* Reinjetar a engrenagem pequena e discreta */
.fixed-settings button::before {{
    content: "⚙️";
    position: absolute;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    color: white !important;
    opacity: 0.3;
    font-size: 14px !important; /* Tamanho reduzido */
    visibility: visible !important;
    pointer-events: none;
}}

.fixed-settings button:hover::before {{
    opacity: 1.0;
}}

/* Garantir que o container do popover não tenha bordas no estado fechado */
div[data-testid="stPopover"] {{
    border: none !important;
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

/* Desativar o efeito de 'ghosting'/'blur' do Streamlit durante a execução */
[data-testid="stAppViewBlockContainer"] {
    filter: none !important;
}

/* Desativar transições globais que interferem com o re-render do Streamlit */
* {
    transition: none !important;
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

@st.cache_data(ttl=600)
def read_xlsx():
    try:
        # Busca por qualquer arquivo .xlsx na pasta raiz (ou pasta 'producao' se preferir)
        xlsx_files = glob.glob("*.xlsx")
        if not xlsx_files:
            return pd.DataFrame()
        # Pega o mais recente
        latest_file = max(xlsx_files, key=os.path.getmtime)
        df = pd.read_excel(latest_file)
        return df
    except Exception as e:
        # Se falhar por falta de openpyxl, pandas avisará
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def read_oee():
    try:
        if not os.path.exists("oee teep.xlsx"):
            return pd.DataFrame()
        
        # Leitura inicial
        df = pd.read_excel("oee teep.xlsx")
        
        # Mapeamento de colunas baseado na inspeção
        rename_map = {
            'Unnamed: 1': 'Maquina',
            'Unnamed: 2': 'Data',
            'Unnamed: 7': 'Disponibilidade',
            'Unnamed: 8': 'Performance',
            'Unnamed: 9': 'Qualidade',
            'Unnamed: 11': 'OEE'
        }
        df = df.rename(columns=rename_map)
        
        # Selecionar apenas colunas úteis
        cols = list(rename_map.values())
        df = df[cols]
        
        # Limpeza
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce', dayfirst=True)
        df = df.dropna(subset=['Data', 'Maquina'])
        
        # Converter métricas de percentual para float
        def clean_pct(x):
            if isinstance(x, str):
                return float(x.replace('%', '').replace(',', '.').strip()) / 100
            return x
            
        for col in ['OEE', 'Disponibilidade', 'Performance', 'Qualidade']:
            df[col] = df[col].apply(clean_pct)
            
        return df
    except Exception as e:
        st.error(f"Erro ao ler OEE: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def read_rejeito():
    try:
        if not os.path.exists("rejeito.xlsx"):
            return pd.DataFrame()
            
        df = pd.read_excel("rejeito.xlsx")
        
        # Mapeamento
        rename_map = {
            'Unnamed: 1': 'Maquina',
            'Unnamed: 2': 'Data',
            'Registro': 'Motivo',
            'Unnamed: 9': 'Produto',
            'Unnamed: 13': 'QtdRejeitada'
        }
        df = df.rename(columns=rename_map)
        
        # Selecionar colunas, garantindo que elas existem
        existing_cols = [c for c in rename_map.values() if c in df.columns]
        df = df[existing_cols]
        
        # Limpeza
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce', dayfirst=True)
        df = df.dropna(subset=['Data', 'Produto'])
        
        # Converter qtd
        df['QtdRejeitada'] = pd.to_numeric(df['QtdRejeitada'], errors='coerce').fillna(0)
        
        return df
    except Exception as e:
        st.error(f"Erro ao ler Rejeito: {e}")
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

    status_text.text('Carregando dados de produção...')
    progress_bar.progress(0.85)
    st.session_state.producao_df = read_xlsx()

    status_text.text('Carregando indicadores OEE/TEEP...')
    progress_bar.progress(0.90)
    st.session_state.oee_df = read_oee()
    st.session_state.rejeito_df = read_rejeito()
    
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

if any(k not in st.session_state for k in ["erros_df", "producao_df", "oee_df", "rejeito_df"]):
    with st.spinner('Carregando dados iniciais do sistema...'):
        refresh_data()

st.sidebar.header("Dados carregados")
st.sidebar.write("erros:", len(st.session_state.get("erros_df", [])))
st.sidebar.write("trabalhos:", len(st.session_state.get("trabalhos_df", [])))
st.sidebar.write("dacen:", len(st.session_state.get("dacen_df", [])))
st.sidebar.write("psi:", len(st.session_state.get("psi_df", [])))
st.sidebar.write("gerais:", len(st.session_state.get("gerais_df", [])))
st.sidebar.write("produção (Excel):", len(st.session_state.get("producao_df", [])))
st.sidebar.write("OEE (Registros):", len(st.session_state.get("oee_df", [])))
st.sidebar.write("Rejeitos (Registros):", len(st.session_state.get("rejeito_df", [])))

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
    # Configurações com Popover e Ícone de Engrenagem
    st.markdown('<div class="fixed-settings">', unsafe_allow_html=True)
    with st.popover("⚙️", help="Configurações de Custos (USD)"):

        st.markdown("### 🛠️ Custos de Tintas (USD)")
        
        rate = get_usd_brl_rate()
        if rate:
            st.success(f"Dólar Hoje: R$ {rate:.4f}")
        else:
            st.warning("Não foi possível obter a cotação do dólar.")
            rate = st.number_input("Taxa de Conversão Manual (R$)", value=5.50, min_value=1.0)

        ink_data = get_ink_data()
        
        with st.form("settings_form"):
            updates = {}
            for cor in ['cyan', 'magenta', 'yellow', 'black', 'white', 'varnish']:
                current_usd = ink_data.get(cor, {}).get('preco_litro_usd', 0.0)
                # Fallback se usd for 0 mas tiver brl
                if current_usd == 0 and ink_data.get(cor, {}).get('preco_litro', 0) > 0:
                     current_usd = ink_data[cor]['preco_litro'] / rate
                
                updates[cor] = st.number_input(f"{cor.capitalize()} ($/L)", value=float(current_usd), step=1.0, format="%.2f")
            
            st.markdown("---")
            st.markdown("### 📈 Margem")
            current_margin = st.session_state.get('margem_lucro', 40)
            margem = st.slider("Margem de Lucro (%)", 10, 200, current_margin)

            st.markdown("---")
            if st.form_submit_button("Salvar Configurações"):
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
                    st.session_state.margem_lucro = margem
                    st.success("Valores atualizados e convertidos!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

with col_meio:

    tab_chat, tab_financeiro, tab_analitico, tab_eficiencia = st.tabs(["Assistente IA", "Custo", "Analítico", "Eficiência"])

    with tab_eficiencia:
        st.markdown("### Indicadores de Eficiência (OEE)")
        
        if "oee_df" in st.session_state and not st.session_state.oee_df.empty:
            oee_df = st.session_state.oee_df
            
            # Filtros de data
            min_date = oee_df['Data'].min()
            max_date = oee_df['Data'].max()
            
            c1, c2 = st.columns(2)
            with c1:
                date_range = st.date_input("Período", [min_date, max_date])
            
            # Aplicar filtro
            if len(date_range) == 2:
                mask = (oee_df['Data'].dt.date >= date_range[0]) & (oee_df['Data'].dt.date <= date_range[1])
                filtered_oee = oee_df[mask]
            else:
                filtered_oee = oee_df
            
            # KPIs Gerais
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("OEE Médio", f"{filtered_oee['OEE'].mean():.1%}")
            k2.metric("Disponibilidade", f"{filtered_oee['Disponibilidade'].mean():.1%}")
            k3.metric("Performance", f"{filtered_oee['Performance'].mean():.1%}")
            k4.metric("Qualidade", f"{filtered_oee['Qualidade'].mean():.1%}")
            
            # Gráfico de tendência
            st.markdown("#### Evolução do OEE")
            daily_oee = filtered_oee.groupby('Data')[['OEE', 'Disponibilidade', 'Performance', 'Qualidade']].mean().reset_index()
            fig_oee = px.line(daily_oee, x='Data', y=['OEE', 'Disponibilidade', 'Performance', 'Qualidade'], 
                              title="Evolução Diária dos Indicadores", markers=True)
            st.plotly_chart(fig_oee, width="stretch")
            
            # Análise de Rejeito
            st.markdown("---")
            st.markdown("### Análise de Rejeitos")
            
            if "rejeito_df" in st.session_state and not st.session_state.rejeito_df.empty:
                rej_df = st.session_state.rejeito_df
                # Filtro de data também para rejeitos
                if len(date_range) == 2:
                    mask_rej = (rej_df['Data'].dt.date >= date_range[0]) & (rej_df['Data'].dt.date <= date_range[1])
                    filtered_rej = rej_df[mask_rej]
                else:
                    filtered_rej = rej_df
                    
                col_rej1, col_rej2 = st.columns(2)
                
                with col_rej1:
                    st.markdown("#### Top Motivos de Rejeição")
                    top_rejeitos = filtered_rej.groupby('Motivo')['QtdRejeitada'].sum().sort_values(ascending=False).head(10).reset_index()
                    fig_rej = px.bar(top_rejeitos, x='QtdRejeitada', y='Motivo', orientation='h', title="Top 10 Motivos (Qtd)", text_auto=True)
                    fig_rej.update_layout(yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig_rej, width="stretch")
                    
                with col_rej2:
                    st.markdown("#### Rejeição por Máquina")
                    mach_rej = filtered_rej.groupby('Maquina')['QtdRejeitada'].sum().reset_index()
                    fig_mach = px.pie(mach_rej, values='QtdRejeitada', names='Maquina', title="Distribuição por Máquina", hole=0.4)
                    st.plotly_chart(fig_mach, width="stretch")
                    
            else:
                st.info("Dados de rejeição não disponíveis.")
        
        st.markdown("---")
        st.markdown("### Assistente de Eficiência")
        prompt_oee = st.chat_input("Pergunte sobre OEE, máquinas ou rejeitos...")
        
        if prompt_oee:
            with st.chat_message("user"):
                st.markdown(prompt_oee)
            
            with st.chat_message("assistant"):
                dfs = {
                    "erros": st.session_state.erros_df,
                    "trabalhos": st.session_state.trabalhos_df,
                    "dacen": st.session_state.dacen_df,
                    "psi": st.session_state.psi_df,
                    "gerais": st.session_state.gerais_df,
                    "producao": st.session_state.producao_df,
                    "oee": st.session_state.get("oee_df", pd.DataFrame()),
                    "rejeito": st.session_state.get("rejeito_df", pd.DataFrame())
                }
                process_chat_request(prompt_oee, dfs)
                
        else:
            if not "oee_df" in st.session_state and st.button("Tentar Recarregar Dados"):
                refresh_data()
                st.rerun()

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
                    "gerais": st.session_state.gerais_df,
                    "producao": st.session_state.producao_df
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
            
            
            # Tabela Detalhada
            st.write("#### Detalhamento Financeiro (Custo por Unidade)")
            df_disp = df_fin[['referencia', 'decoracao', 'produto', 'custo_total_tinta', 'custo_total_tinta_mil']].copy()
            df_disp.columns = ['Referência', 'Decoração', 'Produto', 'Custo Unitário (R$)', 'Custo 1.000 un (R$)']
            
            # Paginação
            df_paged = paginate_dataframe(df_disp, page_size=20, key_prefix="fin_det")
            
            st.dataframe(
                df_paged.style.format(precision=4, decimal=',', thousands='.'),
                use_container_width=True
            )
            
            # Sugestão de Preço com Margem
            st.write("#### Sugestão de Formação de Preço (por Unidade)")
            margem = st.session_state.get('margem_lucro', 40) / 100
            df_fin['preco_venda_sugerido'] = df_fin['custo_total_tinta'] * (1 + margem)
            st.dataframe(
                df_fin[['referencia', 'decoracao', 'produto', 'custo_total_tinta', 'preco_venda_sugerido']]
                .rename(columns={'referencia': 'Referência', 'decoracao': 'Decoração', 'produto': 'Produto', 'custo_total_tinta': 'Custo Tinta (R$)', 'preco_venda_sugerido': f'Preço Sugerido (+{margem*100:.0f}%)'})
                .head(20),
                use_container_width=True
            )
    with tab_analitico:
        st.subheader("Análise de Performance e Consumo")
        
        if not st.session_state.trabalhos_df.empty:
            df_ana = st.session_state.trabalhos_df.copy()
            cores = ['cyan', 'magenta', 'yellow', 'black', 'white', 'varnish']
            df_ana['total_ml'] = df_ana[cores].sum(axis=1)
            
            # Métricas Gerais
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
            
            # Distribuição de Consumo por Cor
            st.write("#### Distribuição de Tintas (Total)")
            cons_cor = df_ana[cores].sum().reset_index()
            cons_cor.columns = ['Cor', 'Volume']
            fig_pie = px.pie(cons_cor, values='Volume', names='Cor', color='Cor',
                           color_discrete_map={
                               'cyan': '#00BFFF', 'magenta': '#FF00FF', 
                               'yellow': '#FFFF00', 'black': '#000000',
                               'white': '#FFFFFF', 'varnish': '#C0C0C0'
                           }, hole=0.4)
            fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=350)
            st.plotly_chart(fig_pie, width="stretch")

            st.write("---")
            
            # 3. Scatter: Tempo vs Consumo
            st.write("#### Relação: Tempo de Produção vs Consumo de Tinta")
            fig_scatter = px.scatter(df_ana, x='tempo_s', y='total_ml', hover_name='produto',
                                   color='total_ml', size='total_ml',
                                   labels={'tempo_s': 'Tempo (segundos)', 'total_ml': 'Consumo (ml/1k)'},
                                   color_continuous_scale='Viridis')
            st.plotly_chart(fig_scatter, width="stretch")
            
            
            # 4. Explorador de Performance Geral
            st.write("#### Explorador de Performance e Consumo Técnico")
            
            df_tec = df_ana.copy()

            media_total = df_ana['total_ml'].mean()
            alto_consumo_count = len(df_ana[df_ana['total_ml'] > media_total * 1.5])
            
            st.info(f"Média Geral de Consumo: {media_total:.2f} ml | Itens com consumo elevado (>50% da média): {alto_consumo_count}")
            
            # Tabela completa com todas as fichas
            df_tec_disp = df_tec[['referencia', 'decoracao', 'produto', 'total_ml', 'tempo_s']].copy()
            df_tec_disp.columns = ['Referência', 'Decoração', 'Produto', 'Consumo Total (ml)', 'Tempo (s)']
            
            # Paginação
            df_tec_paged = paginate_dataframe(df_tec_disp, page_size=20, key_prefix="ana_det")
            
            st.dataframe(
                df_tec_paged,
                use_container_width=True,
                hide_index=True
            )

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




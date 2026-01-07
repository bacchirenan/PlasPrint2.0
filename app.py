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
        return f"{orig.replace('$', r'\$')} (R\$ {brl})"

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

def get_ink_prices():
    try:
        conn = sqlite3.connect('fichas_tecnicas.db')
        df = pd.read_sql_query("SELECT cor, preco_litro FROM custos_tintas", conn)
        conn.close()
        return dict(zip(df['cor'], df['preco_litro']))
    except:
        return {
            'cyan': 250.0, 'magenta': 250.0, 'yellow': 250.0, 
            'black': 250.0, 'white': 300.0, 'varnish': 180.0
        }

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
* {{
    font-family: 'SamsungSharpSans', sans-serif !important;
}}
/* Esconder botão de colapso da sidebar e ícones de sistema que vazam como texto */
[data-testid="stSidebarCollapseButton"], 
.st-emotion-cache-1it3434, 
span[data-testid="stIconMaterial"] {{
    display: none !important;
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

@st.cache_data
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

if "erros_df" not in st.session_state:
    with st.spinner('Carregando dados iniciais do sistema...'):
        refresh_data()

st.sidebar.header("Dados carregados")
st.sidebar.write("erros:", len(st.session_state.erros_df))
st.sidebar.write("trabalhos:", len(st.session_state.trabalhos_df))
st.sidebar.write("dacen:", len(st.session_state.dacen_df))
st.sidebar.write("psi:", len(st.session_state.psi_df))
st.sidebar.write("gerais:", len(st.session_state.gerais_df))
st.sidebar.write("produção (Excel):", len(st.session_state.producao_df))

if st.sidebar.button("Atualizar Dados"):
    with st.spinner('Atualizando dados...'):
        refresh_data()
    st.success('Dados atualizados!')
    time.sleep(0.5)
    st.rerun()

# Sidebar: Gestão de Custos
with st.sidebar.expander("💰 Gestão de Custos (R$/L)"):
    if "precos_tintas" not in st.session_state:
        st.session_state.precos_tintas = get_ink_prices()
    
    with st.form("form_custos"):
        novos_precos = {}
        for cor, preco in st.session_state.precos_tintas.items():
            novos_precos[cor] = st.number_input(f"Preço {cor.capitalize()}", value=float(preco), step=5.0)
        
        margem_sugerida = st.slider("Margem de Lucro Sugerida (%)", 10, 200, 40)
        
        if st.form_submit_button("Salvar Preços"):
            try:
                conn = sqlite3.connect('fichas_tecnicas.db')
                cursor = conn.cursor()
                for cor, preco in novos_precos.items():
                    cursor.execute("UPDATE custos_tintas SET preco_litro = ?, data_atualizacao = ? WHERE cor = ?", 
                                   (preco, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), cor))
                conn.commit()
                conn.close()
                st.session_state.precos_tintas = novos_precos
                st.session_state.margem_lucro = margem_sugerida
                st.success("Preços e margem salvos!")
                refresh_data()
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
client = genai.Client()

def build_context(dfs, max_chars=50000):
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

    tab_chat, tab_financeiro, tab_analitico = st.tabs(["Assistente IA", "Custo", "Analítico"])

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
                # Indicador de progresso do processamento
                progress_container = st.empty()
                status_container = st.empty()
                
                with progress_container:
                    progress_bar = st.progress(0)
                
                with status_container:
                    st.info('Preparando contexto dos dados...')
                progress_bar.progress(0.20)
                
                dfs = {
                    "erros": st.session_state.erros_df,
                    "trabalhos": st.session_state.trabalhos_df,
                    "dacen": st.session_state.dacen_df,
                    "psi": st.session_state.psi_df,
                    "gerais": st.session_state.gerais_df,
                    "producao": st.session_state.producao_df
                }
                
                with status_container:
                    st.info('Processando dados das planilhas...')
                progress_bar.progress(0.40)
                context = build_context(dfs)
                
                # Instruções de sistema para o modelo
                system_instruction = f"""
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
                - **PROIBIDO**: Nunca mostre nomes técnicos de colunas do banco de dados (ex: `config_white`, `id`, `referencia`) entre parênteses ou em qualquer lugar da resposta. Use apenas o nome amigável/descritivo do parâmetro.
                
                UNIDADES DE MEDIDA - CONSUMO DE TINTA:
                - **IMPORTANTE**: Os valores brutos nas planilhas (ex: 0.057, 0.015) representam **ml (mililitros) por unidade (garrafa)**.
                - **DIFERENCIAÇÃO VISUAL OBRIGATÓRIA**: Para evitar confusão, nunca mostre o mesmo número para unidade e milheiro.
                - **Consumo Unitário**: Use o valor bruto (ex: 0.057) e a unidade **ml/garrafa**.
                - **Consumo por Milheiro (1.000 un)**: Multiplique o valor bruto por 1.000 e use a unidade **ml/milheiro** (ex: 57 ml).
                - Exemplo: Se o valor é 0.055, exiba "0.055 ml/garrafa" e "55 ml/1.000 unidades".
                
                ANÁLISE FINANCEIRA E CUSTOS:
                - **Moeda Brasileira**: Use SEMPRE o prefixo **R$** para custos calculados pelo sistema (colunas `custo_total_tinta`, `custo_total_tinta_mil`).
                - **Moeda Americana**: Use o prefixo **$** APENAS se encontrar valores originalmente em dólar nas planilhas de insumos/peças.
                - A coluna `custo_total_tinta` contém o **Custo Unitário (por garrafa)** em Reais (R$).
                - A coluna `custo_total_tinta_mil` contém o **Custo por Milheiro (1.000 garrafas)** em Reais (R$).
                - Os preços base por litro são: {st.session_state.precos_tintas} (Valores em R$/L).
                - Se solicitado análise de preço ou lucro, considere a margem de {st.session_state.get('margem_lucro', 40)}% sobre o custo unitário.

                TRATAMENTO DE LINKS E MÍDIA:
                - **ESTRUTURA OBRIGATÓRIA**: Para links de imagem, use exatamente: Link de Imagem: [URL].
                - Para links de vídeo, use exatamente: Link de Vídeo: [URL].
                - Para outros links, use exatamente: Link de Informação: [URL].
                - **REGRAS DE RESPOSTA**: Ao citar uma **referência**, você DEVE mostrar também a **decoração** correspondente. Exemplo: "Referência 123 (Decoração: Nome)".
                - **LOCALIZAÇÃO**: Coloque o link imediatamente APÓS descrever o item.
                - **REGRA DE OURO**: Sempre inclua os links das colunas IMAGEM e informações. O sistema transformará os links de imagem em fotos e os de vídeo em players automaticamente.
                """
                
                full_prompt = [f"Contexto das Planilhas:\n{context}\n\nPergunta do Usuário: {prompt}"]
                if uploaded_file:
                    with status_container:
                        st.info('Processando imagem enviada...')
                    progress_bar.progress(0.50)
                    full_prompt.append(image_to_send)

                try:
                    with status_container:
                        st.info('Processando consulta...')
                    progress_bar.progress(0.70)
                    
                    # Sistema de retry para lidar com 429 RESOURCE_EXHAUSTED
                    max_retries = 3
                    retry_delay = 5 # segundos iniciais
                    resp = None
                    
                    for attempt in range(max_retries):
                        try:
                            resp = client.models.generate_content(
                                model="gemini-flash-latest", 
                                contents=full_prompt,
                                config={"system_instruction": system_instruction}
                            )
                            break # Sucesso, sai do loop
                        except Exception as e:
                            if "429" in str(e) and attempt < max_retries - 1:
                                with status_container:
                                    st.warning(f"Limite de quota atingido. Tentando novamente em {retry_delay}s... (Tentativa {attempt + 1}/{max_retries})")
                                time.sleep(retry_delay)
                                retry_delay *= 2 # Backoff exponencial
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
            st.dataframe(
                df_fin[['referencia', 'decoracao', 'produto', 'custo_total_tinta', 'custo_total_tinta_mil']]
                .rename(columns={'referencia': 'Referência', 'decoracao': 'Decoração', 'produto': 'Produto', 'custo_total_tinta': 'Custo Unitário (R$)', 'custo_total_tinta_mil': 'Custo 1.000 un (R$)'})
                .style.format(precision=4, decimal=',', thousands='.')
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
            st.plotly_chart(fig_pie, use_container_width=True)

            st.write("---")
            
            # 3. Scatter: Tempo vs Consumo
            st.write("#### Relação: Tempo de Produção vs Consumo de Tinta")
            fig_scatter = px.scatter(df_ana, x='tempo_s', y='total_ml', hover_name='produto',
                                   color='total_ml', size='total_ml',
                                   labels={'tempo_s': 'Tempo (segundos)', 'total_ml': 'Consumo (ml/1k)'},
                                   color_continuous_scale='Viridis')
            st.plotly_chart(fig_scatter, use_container_width=True)
            
            
            # 4. Explorador de Performance Geral
            st.write("#### Explorador de Performance e Consumo Técnico")
            
            df_tec = df_ana.copy()

            media_total = df_ana['total_ml'].mean()
            alto_consumo_count = len(df_ana[df_ana['total_ml'] > media_total * 1.5])
            
            st.info(f"Média Geral de Consumo: {media_total:.2f} ml | Itens com consumo elevado (>50% da média): {alto_consumo_count}")
            
            # Tabela completa com todas as fichas
            st.dataframe(
                df_tec[['referencia', 'decoracao', 'produto', 'total_ml', 'tempo_s']]
                .rename(columns={
                    'referencia': 'Referência', 
                    'decoracao': 'Decoração', 
                    'produto': 'Produto', 
                    'total_ml': 'Consumo Total (ml)', 
                    'tempo_s': 'Tempo (s)'
                }),
                use_container_width=True,
                hide_index=True
            )

        else:
            st.info("Nenhum dado disponível para análise analítica.")

st.markdown(f"""
<style>
/* Ajuste do Logo e Rodapé para não sobrepor conteúdo */
.footer-container {{
    width: 100%;
    text-align: center;
    margin-top: 50px;
    padding-bottom: 20px;
}}
.logo-footer {{ 
    display: inline-block;
    width: 120px;
    opacity: 0.6;
    transition: opacity 0.3s ease;
    margin-bottom: 10px;
}}
.logo-footer:hover {{
    opacity: 1.0;
}}
.version-tag {{ 
    font-size: 12px; 
    color: white; 
    opacity: 0.5;
}}
/* Adicionar espaço no fim da página para garantir que nada fique colado */
[data-testid="stAppViewBlockContainer"] {{
    padding-bottom: 150px !important;
}}
</style>
<div class="footer-container">
    <img src="data:image/png;base64,{img_base64_logo}" class="logo-footer" /><br>
    <div class="version-tag">V2.0</div>
</div>
""", unsafe_allow_html=True)




import streamlit as st
import pandas as pd
import json, base64, os, re, requests, io
import gspread
from google.oauth2.service_account import Credentials
from google import genai
import yfinance as yf
import datetime
import time
import PIL.Image

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
    s = s.strip()
    if s.startswith('$'):
        s = s[1:]
    s = s.replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except:
        return None

def to_brazilian(n):
    if 0 < n < 0.01:
        n = 0.01
    return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def format_dollar_values(text, rate):
    money_regex = re.compile(r'\$\s?\d+(?:[.,]\d+)?')
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
        return f"{orig} (R$ {brl})"

    formatted = money_regex.sub(repl, text)

    if found:
        if not formatted.endswith("\n"):
            formatted += "\n"
        formatted += "(valores sem impostos)"

    return formatted

def process_response(texto):
    padrao_dolar = r"\$\s?\d+(?:[.,]\d+)?"
    if re.search(padrao_dolar, texto):
        rate = get_usd_brl_rate()
        if rate:
            return format_dollar_values(texto, rate)
        else:
            return texto
    return texto

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

# ===== Carregar background e fonte =====
background_image = "background.jpg"
img_base64 = get_base64_of_jpg(background_image)
font_base64 = get_base64_font("font.ttf")

st.markdown(f"""
<style>
@font-face {{
    font-family: 'CustomFont';
    src: url(data:font/ttf;base64,{font_base64}) format('truetype');
}}
h1.custom-font {{
    font-family: 'CustomFont', sans-serif !important;
    text-align: center;
    font-size: 380%;
    margin-bottom: 0px;
}}
p.custom-font {{
    font-family: 'CustomFont', sans-serif !important;
    font-weight: bold;
    text-align: left;
}}
div.stButton > button {{
    font-family: 'CustomFont', sans-serif !important;
}}
div.stTextInput > div > input {{
    font-family: 'CustomFont', sans-serif !important;
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
div[data-testid="stFileUploader"] button {{
    font-family: 'CustomFont', sans-serif !important;
    width: 100% !important;
    min-width: 100% !important;
    margin: 10px 0 0 0 !important; /* Pequeno espaçamento do chat_input */
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
div[data-testid="stFileUploader"] button::before {{
    content: "Enviar Imagem" !important;
    position: absolute !important;
    width: 100% !important;
    height: 100% !important;
    left: 0 !important;
    top: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    color: white !important;
    font-size: 0.95rem !important;
    font-weight: bold !important;
    font-family: 'CustomFont', sans-serif !important;
    pointer-events: none !important;
    text-align: center !important;
}}
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

def refresh_data():
    st.session_state.erros_df = read_ws("erros")
    st.session_state.trabalhos_df = read_ws("trabalhos")
    st.session_state.dacen_df = read_ws("dacen")
    st.session_state.psi_df = read_ws("psi")
    st.session_state.gerais_df = read_ws("gerais")

if "erros_df" not in st.session_state:
    refresh_data()

st.sidebar.header("Dados carregados")
st.sidebar.write("erros:", len(st.session_state.erros_df))
st.sidebar.write("trabalhos:", len(st.session_state.trabalhos_df))
st.sidebar.write("dacen:", len(st.session_state.dacen_df))
st.sidebar.write("psi:", len(st.session_state.psi_df))
st.sidebar.write("gerais:", len(st.session_state.gerais_df))

if st.sidebar.button("Atualizar planilha"):
    refresh_data()
    st.rerun()

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
def load_drive_image(file_id):
    url = f"https://drive.google.com/uc?export=view&id={file_id}"
    res = requests.get(url)
    res.raise_for_status()
    return res.content

def show_drive_images_from_text(text):
    drive_links = re.findall(
        r'https?://drive\.google\.com/file/d/([a-zA-Z0-9_-]+)',
        text
    )
    for file_id in drive_links:
        try:
            img_bytes = io.BytesIO(load_drive_image(file_id))
            st.image(img_bytes, use_container_width=True)
        except:
            pass  # silencia o erro sem exibir nada


def show_clickable_links_from_informacoes(text):
    links = re.findall(r'(https?://[^\s]+)', text)
    if not links:
        return
    for link in links:
        st.markdown(f"<div style='text-align:center;'><a href='{link}' target='_blank'>Abrir Link</a></div>", unsafe_allow_html=True)


def remove_drive_links(text):
    return re.sub(r'https?://drive\.google\.com/file/d/[a-zA-Z0-9_-]+/view\?usp=drive_link', '', text)

col_esq, col_meio, col_dir = st.columns([1,3,1])
with col_meio:
    st.markdown("<h1 class='custom-font'>PlasPrint IA</h1><br>", unsafe_allow_html=True)

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
            with st.spinner("Analisando..."):
                dfs = {
                    "erros": st.session_state.erros_df,
                    "trabalhos": st.session_state.trabalhos_df,
                    "dacen": st.session_state.dacen_df,
                    "psi": st.session_state.psi_df,
                    "gerais": st.session_state.gerais_df
                }
                context = build_context(dfs)
                
                # Instruções de sistema para o modelo
                system_instruction = """
                Você é o Assistente Técnico PlasPrint IA especializado em flexografia e impressão industrial.
                Responda em português brasileiro de forma estritamente técnica e direta.
                **NUNCA use saudações, introduções ou frases como "Olá", "Como assistente técnico", ou "posso confirmar que".**
                Vá direto ao ponto e forneça a solução ou análise técnica imediatamente.
                Baseie-se principalmente nos dados das planilhas fornecidas.
                Se uma imagem for enviada, analise-a em busca de defeitos de impressão ou painéis de máquina e cruze com os dados.
                Se não souber a resposta baseada nos dados, sugira procurar o suporte técnico sênior.
                Regras:
                - Proibido introduções, saudações ou frases de cortesia.
                - Nunca cite o nome da aba ou linha da planilha.
                - Use negrito para termos técnicos importantes.
                - Respostas ultra-objetivas e diretas.
                """
                
                full_prompt = [f"Contexto das Planilhas:\n{context}\n\nPergunta do Usuário: {prompt}"]
                if uploaded_file:
                    full_prompt.append(image_to_send)

                try:
                    # Usando gemini-flash-latest para garantir compatibilidade com a cota gratuita
                    resp = client.models.generate_content(
                        model="gemini-flash-latest", 
                        contents=full_prompt,
                        config={"system_instruction": system_instruction}
                    )

                    clean_text = re.sub(r'Links de imagens:?', '', resp.text, flags=re.IGNORECASE)
                    clean_text = re.sub(r'https?://\S+', '', clean_text)
                    clean_text = re.sub(r'\s{2,}', ' ', clean_text).strip()

                    output_fmt = process_response(clean_text)
                    # Formatar com HTML para centralizar e quebras de linha
                    formatted_response = f"<div style='text-align:left;'>{output_fmt.replace(chr(10),'<br/>')}</div>"
                    st.markdown(formatted_response, unsafe_allow_html=True)
                    
                    # Exibir links e imagens de drive que venham no texto bruto do contexto
                    show_clickable_links_from_informacoes(resp.text)
                    show_drive_images_from_text(resp.text)

                except Exception as e:
                    st.error(f"Erro ao processar: {e}")

st.markdown("""
<style>
.version-tag { position: fixed; bottom: 50px; right: 25px; font-size: 12px; color: white; opacity: 0.7; z-index: 100; }
.logo-footer { position: fixed; bottom: 5px; left: 50%; transform: translateX(-50%); width: 120px; z-index: 100; }
</style>
<div class="version-tag">V2.0</div>
""", unsafe_allow_html=True)

def get_base64_img(path):
    with open(path, "rb") as f:  # <— correção aplicada
        return base64.b64encode(f.read()).decode()

img_base64_logo = get_base64_img("logo.png")
st.markdown(f'<img src="data:image/png;base64,{img_base64_logo}" class="logo-footer" />', unsafe_allow_html=True)




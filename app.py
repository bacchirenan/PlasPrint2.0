import streamlit as st
if "run_count" not in st.session_state: st.session_state.run_count = 0
st.session_state.run_count += 1
print(f"\n--- EXECUÇÃO #{st.session_state.run_count} ---")
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
import plotly.io as pio
import kaleido
from fpdf import FPDF
import warnings
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

# Suprimir avisos de depreciação do Kaleido para não poluir o log
warnings.simplefilter("ignore", category=DeprecationWarning)

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

class PDFReport(FPDF):
    def header(self):
        if os.path.exists("logo.png"):
            self.image("logo.png", 10, 8, 25)
        self.set_font('Arial', 'B', 15)
        self.cell(80)
        self.cell(30, 10, 'Relatório Técnico PlasPrint IA', 0, 0, 'C')
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()} | Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 0, 'C')

def create_pdf_report(selected_elements, data_sources):
    print(f">>> [PDF] Iniciando criação do relatório com {len(selected_elements)} elementos")
    pdf = PDFReport()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Função auxiliar para exportar gráfico com timeout
    def export_chart_with_timeout(fig):
        """Exporta o gráfico usando Kaleido"""
        # Configurações para exportação clara
        fig.update_layout(
            paper_bgcolor='white',
            plot_bgcolor='white',
            font=dict(color='black')
        )
        
        # Exportar usando pio.to_image
        img_bytes = pio.to_image(fig, format="png", width=800, height=450, scale=2)
        return img_bytes
    
    # Função auxiliar para adicionar gráfico ao PDF com timeout
    def add_plotly_chart(fig, title):
        print(f">>> [PDF] Gerando imagem para o gráfico: {title}")
        try:
            # Usar ThreadPoolExecutor com timeout de 15 segundos
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(export_chart_with_timeout, fig)
                try:
                    # Aguardar até 15 segundos pelo resultado
                    img_bytes = future.result(timeout=15)
                    
                    # Sucesso - adicionar imagem ao PDF
                    pdf.add_page()
                    pdf.set_font('Arial', 'B', 12)
                    pdf.cell(0, 10, title, 0, 1)
                    
                    img_path = f"temp_chart_{datetime.now().timestamp()}.png"
                    with open(img_path, "wb") as f:
                        f.write(img_bytes)
                    pdf.image(img_path, x=10, y=None, w=190)
                    os.remove(img_path)
                    print(f">>> [PDF] Gráfico '{title}' adicionado com sucesso")
                    
                except FutureTimeoutError:
                    # Timeout - processo travou
                    print(f">>> [KALEIDO] TIMEOUT ao exportar gráfico '{title}' - processo travou após 15 segundos")
                    
                    # Adicionar página de erro
                    pdf.add_page()
                    pdf.set_font('Arial', 'B', 12)
                    pdf.cell(0, 10, title, 0, 1)
                    pdf.ln(5)
                    pdf.set_font('Arial', 'I', 9)
                    pdf.multi_cell(0, 5, f"Erro: Timeout ao gerar gráfico (processo travou após 15 segundos)")
                    pdf.ln(5)
                    pdf.set_font('Arial', '', 9)
                    pdf.multi_cell(0, 5, "Possíveis soluções:\n1. Tente gerar o PDF novamente\n2. Reduza a quantidade de gráficos selecionados\n3. Reinstale o Kaleido: pip uninstall kaleido && pip install kaleido==0.2.1\n4. Verifique se há processos Kaleido travados no Gerenciador de Tarefas\n5. Reinicie o aplicativo Streamlit")
                    
                except Exception as e:
                    # Erro durante exportação
                    error_msg = str(e)
                    print(f">>> [PDF] ERRO ao gerar gráfico '{title}': {error_msg}")
                    pdf.add_page()
                    pdf.set_font('Arial', 'B', 12)
                    pdf.cell(0, 10, title, 0, 1)
                    pdf.ln(5)
                    pdf.set_font('Arial', 'I', 9)
                    pdf.multi_cell(0, 5, f"Erro ao gerar gráfico: {error_msg[:200]}")
                    pdf.ln(5)
                    pdf.set_font('Arial', '', 9)
                    pdf.multi_cell(0, 5, "Possíveis soluções:\n1. Reinstale o Kaleido: pip uninstall kaleido && pip install kaleido==0.2.1\n2. Verifique se há processos Kaleido travados no Gerenciador de Tarefas\n3. Reinicie o aplicativo Streamlit")
            
        except Exception as e:
            error_msg = str(e)
            print(f">>> [PDF] ERRO CRÍTICO ao processar gráfico '{title}': {error_msg}")
            pdf.add_page()
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, title, 0, 1)
            pdf.ln(5)
            pdf.set_font('Arial', 'I', 9)
            pdf.multi_cell(0, 5, f"Erro crítico: {error_msg[:200]}")
            pdf.ln(5)
            pdf.set_font('Arial', '', 9)
            pdf.multi_cell(0, 5, "Tente gerar o PDF novamente ou contate o suporte técnico.")

    if "Resumo de Produção (Métricas)" in selected_elements:
        pdf.add_page()
        df = data_sources.get('df_rep')
        if df is not None and not df.empty:
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, 'Resumo Geral de Produção', 0, 1)
            pdf.set_font('Arial', '', 10)
            
            total_pecas = df['producao_total'].sum()
            total_boas = df['pecas_boas'].sum()
            total_rejeito = df['rejeito'].sum()
            perc_rejeito = (total_rejeito / total_pecas * 100) if total_pecas > 0 else 0
            
            pdf.cell(0, 10, f'Total Produzido: {total_pecas:,.0f}'.replace(',', '.'), 0, 1)
            pdf.cell(0, 10, f'Peças Boas: {total_boas:,.0f}'.replace(',', '.'), 0, 1)
            pdf.cell(0, 10, f'Total Rejeito: {total_rejeito:,.0f}'.replace(',', '.'), 0, 1)
            pdf.cell(0, 10, f'Percentual de Perda: {perc_rejeito:.1f}%', 0, 1)
            pdf.ln(10)

    if "Tabela: Detalhamento por Máquina" in selected_elements:
        df = data_sources.get('df_rep')
        if df is not None and not df.empty:
            pdf.add_page()
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, 'Detalhamento por Máquina', 0, 1)
            pdf.ln(5)
            
            pdf.set_font('Arial', 'B', 9)
            pdf.cell(50, 8, 'Máquina', 1)
            pdf.cell(35, 8, 'Produção', 1)
            pdf.cell(35, 8, 'Boas', 1)
            pdf.cell(30, 8, 'Rejeito', 1)
            pdf.cell(30, 8, '% Perda', 1)
            pdf.ln()
            
            pdf.set_font('Arial', '', 8)
            df_sum = df.groupby('maquina')[['producao_total', 'pecas_boas', 'rejeito']].sum().reset_index()
            for _, row in df_sum.iterrows():
                p_loss = (row['rejeito'] / row['producao_total'] * 100) if row['producao_total'] > 0 else 0
                pdf.cell(50, 8, str(row['maquina'])[:25], 1)
                pdf.cell(35, 8, f"{row['producao_total']:,.0f}".replace(',', '.'), 1)
                pdf.cell(35, 8, f"{row['pecas_boas']:,.0f}".replace(',', '.'), 1)
                pdf.cell(30, 8, f"{row['rejeito']:,.0f}".replace(',', '.'), 1)
                pdf.cell(30, 8, f"{p_loss:.1f}%", 1)
                pdf.ln()

    # Adicionar gráficos via loop se forem figs
    for element in selected_elements:
        if element.startswith("Gráfico:") and element in data_sources:
            fig = data_sources[element]
            if fig:
                add_plotly_chart(fig, element.replace("Gráfico: ", ""))

    return pdf.output()

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

/* RESTAURAR ÍCONES E ESCONDER TEXTO VAZADO */
[data-testid="stIconMaterial"], 
.material-icons,
.material-symbols-outlined {{
    font-family: 'Material Symbols Outlined', 'Material Icons' !important;
    display: inline-block !important;
    width: 24px !important;
    height: 24px !important;
    overflow: hidden !important;
    color: inherit !important;
    vertical-align: middle !important;
    font-size: 24px !important;
}}

/* Fix para expanders: esconde o "texto" do ícone mas mantém o label visível */
[data-testid="stExpander"] summary [data-testid="stIconMaterial"] {{
    color: transparent !important; /* Esconde o texto que forma o ícone se o glifo falhar */
    position: relative;
    font-size: 0 !important;
}}

/* Tenta forçar o ícone de volta como SVG ou via renderização do Streamlit */
[data-testid="stExpander"] summary svg {{
    display: block !important;
    color: white !important;
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

/* Custom MultiSelect Styling */
div[data-baseweb="select"] > div {
    background-color: rgba(255, 255, 255, 0.05) !important;
    border-radius: 8px !important;
    border: 1px solid rgba(0, 210, 255, 0.2) !important;
}
div[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    background-color: #1a335f !important;
    color: white !important;
    border-radius: 4px !important;
    border: 1px solid rgba(0, 210, 255, 0.3) !important;
}

/* CSS simplify - removed nuclear fix to test loading */

/* ensure my custom progress bar Pulse still works (it uses opacity) 
   we will scope it specifically so it's not neutralized by the above rule */
.stProgress > div > div > div > div {
    animation: progressPulse 1.5s ease-in-out infinite !important;
}

/* Skeleton visibility restored to avoid blank screen during load */
[data-testid="stSkeleton"] {
    display: block !important;
}

/* Aplicar transições apenas a elementos específicos se necessário */
.stButton, .stTextInput, .stFileUploader, .stChatMessage {
    transition: background-color 0.2s ease, transform 0.2s ease !important;
}

/* --- TRANSFORMAR RADIO EM ABAS (RESTAURANDO O VISUAL) --- */
[data-testid="stRadio"] > div[role="radiogroup"] {
    display: flex;
    flex-direction: row;
    justify-content: flex-start;
    align-items: center;
    gap: 0px !important;
    width: 100% !important;
    max-width: 100vw !important;
    flex-wrap: nowrap;
    background-color: transparent !important;
    padding: 0 !important;
    overflow: visible !important;
}

[data-testid="stRadio"] > div[role="radiogroup"] > label {
    background: transparent !important;
    padding: 8px 3px !important;
    cursor: pointer !important;
    border-radius: 5px 5px 0 0 !important;
    transition: all 0.3s !important;
    flex: 1 1 auto;
    min-width: 0;
    text-align: center !important;
    justify-content: center !important;
    margin: 0 !important;
    border: none !important;
    white-space: nowrap;
    overflow: visible !important;
}

/* Esconder bolinha do radio (Removendo o que o usuário não pediu) */
[data-testid="stRadio"] > div[role="radiogroup"] > label > div:first-child {
    display: none !important;
}

/* Texto do item - Escala adaptativa para 7 abas */
[data-testid="stRadio"] > div[role="radiogroup"] > label > div[data-testid="stMarkdownContainer"] p {
    font-size: clamp(0.45rem, 0.9vw, 0.85rem) !important;
    font-weight: bold !important;
    color: rgba(255, 255, 255, 0.6) !important;
    margin: 0 !important;
    padding: 0 !important;
}

/* --- RESPONSIVIDADE EXTREMA --- */
@media (max-width: 768px) {
    [data-testid="stRadio"] > div[role="radiogroup"] > label {
        padding: 5px 1px !important;
    }
}

/* Hover */
[data-testid="stRadio"] > div[role="radiogroup"] > label:hover {
    background-color: rgba(255, 255, 255, 0.05) !important;
}
[data-testid="stRadio"] > div[role="radiogroup"] > label:hover > div[data-testid="stMarkdownContainer"] p {
    color: white !important;
}

/* Ítem Selecionado (Simulando a aba ativa) */
[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) {
    border-bottom: 3px solid #00d2ff !important;
    background-color: rgba(0, 210, 255, 0.08) !important;
}

[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) > div[data-testid="stMarkdownContainer"] p {
    color: #00d2ff !important;
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
            
        # Converter data para datetime
        new_df['data'] = pd.to_datetime(new_df['data'], dayfirst=True, format='mixed', errors='coerce')
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

def load_producao_data():
    try:
        # Pular as primeiras 3 linhas (cabeçalhos na linha 3, dados começam na 4)
        # header=None porque a linha 4 é DADO e não cabeçalho
        df = pd.read_excel('producao.xlsx', skiprows=3, header=None)
        
        # Mapeamento Solicitado (Revisado):
        # B (1): Máquina
        # C (2): Data
        # F (5): Hora
        # G (6): Turno
        # H (7): Registro
        # I (8): OS
        # J (9): Produto (Implícito/Contexto)
        # K (10): Operador
        # O (14): Produção Total
        # P (15): Rejeito
        # Q (16): Peças Boas
        
        new_df = pd.DataFrame()
        new_df['maquina'] = df.iloc[:, 1]
        new_df['data'] = df.iloc[:, 2]
        new_df['hora'] = df.iloc[:, 5]
        new_df['turno_cod'] = df.iloc[:, 6]
        new_df['registro'] = df.iloc[:, 7]
        new_df['os'] = df.iloc[:, 8]
        new_df['produto'] = df.iloc[:, 9]
        new_df['operador'] = df.iloc[:, 10]
        # Ignore L(11), M(12), N(13)
        new_df['producao_total'] = df.iloc[:, 14]
        new_df['rejeito'] = df.iloc[:, 15]
        new_df['pecas_boas'] = df.iloc[:, 16]
        
        # Limpezas básicas
        new_df = new_df[new_df['maquina'].notna()]
        new_df = new_df[~new_df['maquina'].astype(str).str.contains('Turno', na=False, case=False)]
        new_df = new_df[new_df['data'].notna()]
        
        # Converter data
        new_df['data'] = pd.to_datetime(new_df['data'], dayfirst=True, format='mixed', errors='coerce')
        new_df = new_df.dropna(subset=['data'])
        
        # Mapear turno
        def map_shift(val):
            try:
                v = int(float(val))
                if v == 1: return 'Turno A'
                if v == 2: return 'Turno B'
                if v == 3: return 'Turno C'
            except:
                pass
            return str(val)
            
        new_df['turno'] = new_df['turno_cod'].apply(map_shift)
        
        # Converter numéricos
        cols_num = ['producao_total', 'rejeito', 'pecas_boas']
        for c in cols_num:
            new_df[c] = pd.to_numeric(new_df[c], errors='coerce').fillna(0)
            
        return new_df
    except Exception as e:
        st.warning(f"Erro ao carregar producao.xlsx: {e}")
        return pd.DataFrame()


def load_canudos_data():
    """Carrega dados de Canudos.xlsx"""
    try:
        # A=0 (Data), B=1 (Turno), C=2 (OS), D=3 (Op), E=4 (Boas), F=5 (Perdas)
        df = pd.read_excel("Canudos.xlsx", header=None, usecols="A:F")
        df.columns = ['data', 'turno', 'os', 'operador', 'pecas_boas', 'perdas']
        new_df = df.copy()
        
        # Limpeza e Conversão
        new_df['data'] = pd.to_datetime(new_df['data'], dayfirst=True, format='mixed', errors='coerce')
        new_df = new_df.dropna(subset=['data']) # Remove linhas sem data (cabeçalho se houver)
        
        # Extrair Hora (se houver informação de tempo)
        new_df['hora'] = new_df['data'].dt.hour.fillna(0).astype(int)

        # Mapeamento de Operadores
        map_op = {8502: 'Pedro', 8524: 'Leonardo'}
        # Converter para numérico primeiro para garantir match no dict
        new_df['operador_cod'] = pd.to_numeric(new_df['operador'], errors='coerce')
        new_df['operador_nome'] = new_df['operador_cod'].map(map_op).fillna(new_df['operador'])
        
        # Converter métricas
        cols_num = ['pecas_boas', 'perdas']
        for c in cols_num:
            new_df[c] = pd.to_numeric(new_df[c], errors='coerce').fillna(0)
            
        return new_df
    except Exception as e:
        # st.warning(f"Aviso: Canudos.xlsx não encontrado ou erro de leitura: {e}") # Silencioso no startup
        return pd.DataFrame()

def refresh_data():
    """Atualiza todos os dados com feedback visual de progresso"""
    print(">>> Iniciando carregamento de dados...")
    progress_bar = st.sidebar.progress(0)
    status_text = st.sidebar.empty()
    
    status_text.text('Carregando dados de erros...')
    progress_bar.progress(0.15)
    st.session_state.erros_df = read_ws("erros")
    print(f"    - Erros: {len(st.session_state.erros_df)} registros")
    
    status_text.text('Carregando fichas técnicas...')
    progress_bar.progress(0.30)
    st.session_state.trabalhos_df = read_sqlite("fichas")
    print(f"    - Fichas: {len(st.session_state.trabalhos_df)} registros")
    
    status_text.text('Carregando dados DACEN...')
    progress_bar.progress(0.45)
    st.session_state.dacen_df = read_ws("dacen")
    print(f"    - DACEN: {len(st.session_state.dacen_df)} registros")
    
    status_text.text('Carregando dados PSI...')
    progress_bar.progress(0.60)
    st.session_state.psi_df = read_ws("psi")
    print(f"    - PSI: {len(st.session_state.psi_df)} registros")
    
    status_text.text('Carregando dados gerais...')
    progress_bar.progress(0.75)
    st.session_state.gerais_df = read_ws("gerais")
    print(f"    - Gerais: {len(st.session_state.gerais_df)} registros")

    status_text.text('Carregando dados OEE/TEEP...')
    progress_bar.progress(0.85)
    st.session_state.oee_df = load_oee_data()
    print(f"    - OEE: {len(st.session_state.oee_df)} registros")
    
    status_text.text('Carregando dados de Produção...')
    progress_bar.progress(0.90)
    st.session_state.producao_df = load_producao_data()
    print(f"    - Produção: {len(st.session_state.producao_df)} registros")

    status_text.text('Carregando dados de Canudos...')
    progress_bar.progress(0.92)
    st.session_state.canudos_df = load_canudos_data()
    print(f"    - Canudos: {len(st.session_state.canudos_df)} registros")

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
    print(">>> Carregamento de dados concluído.")
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
            st.info('Processando...')
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
st.sidebar.write("produção:", len(st.session_state.get("producao_df", [])))
st.sidebar.write("canudos:", len(st.session_state.get("canudos_df", [])))

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

    # --- Navegação Persistente (Substituindo st.tabs para corrigir reset) ---
    tabs_labels = ["Assistente IA", "Fichas", "Produção", "Oee e Teep", "Canudos", "Relatórios", "Configurações"]
    
    # Inicializar estado se não existir
    if "nav_tab" not in st.session_state:
        st.session_state.nav_tab = tabs_labels[0]

    # Menu de navegação (estilo botões/abas)
    print(f">>> [UI] Renderizando rádio de navegação. Aba atual: {st.session_state.get('nav_tab', 'desconhecida')}")
    selected_tab = st.radio(
        "Navegação", 
        tabs_labels, 
        horizontal=True, 
        label_visibility="collapsed",
        key="nav_tab"
    )
    st.markdown("---")

    if selected_tab == "Relatórios":
        st.subheader("Relatórios de Produção")
        df_rep = st.session_state.get("producao_df", pd.DataFrame()).copy()
        
        if not df_rep.empty:
            st.markdown("#### Filtros de Relatório")
            c1, c2 = st.columns(2)
            
            with c1:
                original_maquinas = sorted(df_rep['maquina'].unique().tolist())
                # Mapeamento para nomes limpos: "180" -> "180- CX-360G"
                maq_map = {name.split('-')[0].strip() if '-' in name else name: name for name in original_maquinas}
                clean_maquinas = list(maq_map.keys())
                sel_clean = st.multiselect("Filtrar Máquina(s)", options=clean_maquinas, default=clean_maquinas, key="rep_maq_multi")
                
            with c2:
                if not df_rep['data'].empty:
                    min_date = df_rep['data'].min()
                    max_date = df_rep['data'].max()
                    yesterday = pd.Timestamp.today().date() - pd.Timedelta(days=1)
                    default_val = (yesterday, yesterday)
                    
                    visual_min = min(min_date.date(), yesterday) if pd.notnull(min_date) else yesterday
                    sel_dates = st.date_input("Período", value=default_val, min_value=visual_min, max_value=max_date, key="rep_date")
                else:
                    sel_dates = []

            # Aplicação dos filtros
            if sel_clean:
                sel_originals = [maq_map[name] for name in sel_clean]
                df_rep = df_rep[df_rep['maquina'].isin(sel_originals)]
            else:
                st.warning("Selecione ao menos uma máquina.")
                st.stop()
            
            if isinstance(sel_dates, (list, tuple)) and len(sel_dates) == 2:
                df_rep = df_rep[(df_rep['data'] >= pd.Timestamp(sel_dates[0])) & (df_rep['data'] <= pd.Timestamp(sel_dates[1]))]
            elif isinstance(sel_dates, (list, tuple)) and len(sel_dates) == 1:
                df_rep = df_rep[df_rep['data'] >= pd.Timestamp(sel_dates[0])]

            if not df_rep.empty:
                st.markdown("#### 📄 Gerador de Relatório PDF")
                st.write("Selecione os elementos abaixo para compor seu relatório baseado nos filtros aplicados:")
                
                re_options = [
                    "Resumo de Produção (Métricas)",
                    "Tabela: Detalhamento por Máquina",
                    "Gráfico: Peças por Hora (Produção)",
                    "Gráfico: Distribuição de OEE (Buckets)",
                    "Gráfico: Heatmap de OEE",
                    "Gráfico: Produção Diária (Canudos)",
                    "Gráfico: Peças por Hora (Canudos)",
                    "Gráfico: Top 10 Custos (Fichas Técnica)",
                    "Gráfico: Mix de Produtos (Tintas)"
                ]
                selected_reports = st.multiselect("Elementos do PDF:", options=re_options, default=["Resumo de Produção (Métricas)", "Tabela: Detalhamento por Máquina"], key="rep_sel_multi")
                
                print(f">>> [UI] Renderizando elementos de relatório. Selecionados: {selected_reports}")
                if st.button("Gerar PDF"):
                    print(">>> [UI] Botão 'Gerar PDF' clicado!")
                    with st.spinner("Gerando relatório... Isso pode levar alguns segundos dependendo da quantidade de gráficos."):
                        data_sources = {'df_rep': df_rep}
                        
                        # Preparar dados OEE
                        df_oee_base = st.session_state.get("oee_df", pd.DataFrame()).copy()
                        if not df_oee_base.empty:
                            # Aplicar mesmos filtros de máquina e data
                            sel_originals = [maq_map[name] for name in sel_clean]
                            df_oee_filtered = df_oee_base[df_oee_base['maquina'].isin(sel_originals)]
                            if isinstance(sel_dates, (list, tuple)) and len(sel_dates) == 2:
                                df_oee_filtered = df_oee_filtered[(df_oee_filtered['data'] >= pd.Timestamp(sel_dates[0])) & (df_oee_filtered['data'] <= pd.Timestamp(sel_dates[1]))]
                            data_sources['df_oee'] = df_oee_filtered

                        # Preparar dados Canudos
                        df_can_base = st.session_state.get("canudos_df", pd.DataFrame()).copy()
                        if not df_can_base.empty:
                            if isinstance(sel_dates, (list, tuple)) and len(sel_dates) == 2:
                                df_can_filtered = df_can_base[(df_can_base['data'] >= pd.Timestamp(sel_dates[0])) & (df_can_base['data'] <= pd.Timestamp(sel_dates[1]))]
                                data_sources['df_can'] = df_can_filtered

                        # Preparar dados Fichas
                        df_fichas = st.session_state.get("trabalhos_df", pd.DataFrame())
                        data_sources['df_fichas'] = df_fichas

                        # --- GERAR GRÁFICOS ---
                        if "Gráfico: Peças por Hora (Produção)" in selected_reports:
                            df_hora = df_rep.groupby('hora')['producao_total'].sum().reset_index()
                            fig = px.bar(df_hora, x='hora', y='producao_total', title="Produção por Hora", color_discrete_sequence=['#00adef'])
                            data_sources["Gráfico: Peças por Hora (Produção)"] = fig
                        
                        if "Gráfico: Distribuição de OEE (Buckets)" in selected_reports and 'df_oee' in data_sources:
                            df_oee = data_sources['df_oee']
                            if not df_oee.empty:
                                def get_bucket(val):
                                    if val < 0.5: return "Baixa (<50%)"
                                    if val < 0.8: return "Normal (50-80%)"
                                    return "Alta (>80%)"
                                df_oee['Faixa'] = df_oee['oee'].apply(get_bucket)
                                df_b = df_oee['Faixa'].value_counts().reset_index()
                                df_b.columns = ['Faixa', 'Qtd']
                                fig = px.pie(df_b, names='Faixa', values='Qtd', title="Distribuição de OEE", color_discrete_map={"Baixa (<50%)": "#1a335f", "Normal (50-80%)": "#4466b1", "Alta (>80%)": "#89c153"})
                                data_sources["Gráfico: Distribuição de OEE (Buckets)"] = fig

                        if "Gráfico: Heatmap de OEE" in selected_reports and 'df_oee' in data_sources:
                            df_oee = data_sources['df_oee']
                            if not df_oee.empty:
                                df_heat = df_oee.groupby(['data', 'hora'])['oee'].mean().reset_index()
                                df_heat['data_str'] = df_heat['data'].dt.strftime('%d/%m')
                                df_pivot = df_heat.pivot(index='hora', columns='data_str', values='oee').fillna(0) * 100
                                fig = px.imshow(df_pivot, labels=dict(x="", y="Hora", color="OEE %"), color_continuous_scale=['#0a1929', '#89c153'], title="Mapa de Calor: OEE por Hora/Dia")
                                data_sources["Gráfico: Heatmap de OEE"] = fig

                        if "Gráfico: Produção Diária (Canudos)" in selected_reports and 'df_can' in data_sources:
                            df_can = data_sources['df_can']
                            if not df_can.empty:
                                df_g = df_can.groupby('data')[['pecas_boas', 'perdas']].sum().reset_index()
                                df_m = df_g.melt(id_vars='data', value_vars=['pecas_boas', 'perdas'], var_name='Tipo', value_name='Qtd')
                                fig = px.bar(df_m, x='data', y='Qtd', color='Tipo', barmode='group', title="Canudos: Boas vs Perdas Diárias", color_discrete_map={'pecas_boas': '#00adef', 'perdas': '#1a335f'})
                                data_sources["Gráfico: Produção Diária (Canudos)"] = fig

                        if "Gráfico: Peças por Hora (Canudos)" in selected_reports and 'df_can' in data_sources:
                            df_can = data_sources['df_can']
                            if not df_can.empty:
                                df_h = df_can.groupby(['data', 'turno'])['pecas_boas'].sum().reset_index()
                                df_h['pecas_por_hora'] = df_h['pecas_boas'] / 8
                                df_avg = df_h.groupby('turno')['pecas_por_hora'].mean().reset_index()
                                fig = px.bar(df_avg, x='turno', y='pecas_por_hora', title="Canudos: Peças por Hora (Média)", color='turno', color_discrete_map={'Turno A': '#00adef', 'Turno B': '#1a335f', 'Turno C': '#89c153'})
                                data_sources["Gráfico: Peças por Hora (Canudos)"] = fig

                        if "Gráfico: Top 10 Custos (Fichas Técnica)" in selected_reports:
                            df_f = data_sources['df_fichas']
                            if not df_f.empty:
                                df_t10 = df_f.nlargest(10, 'custo_total_tinta_mil')
                                fig = px.bar(df_t10, x='custo_total_tinta_mil', y='produto', orientation='h', title="Top 10 Custos (R$ / 1.000 un)", color_discrete_sequence=['#4466b1'])
                                data_sources["Gráfico: Top 10 Custos (Fichas Técnica)"] = fig

                        if "Gráfico: Mix de Produtos (Tintas)" in selected_reports:
                            df_f = data_sources['df_fichas']
                            if not df_f.empty:
                                counts = df_f['produto'].value_counts().reset_index()
                                counts.columns = ['produto', 'quantidade']
                                fig = px.pie(counts, values='quantidade', names='produto', title="Mix de Produtos", color_discrete_sequence=['#1a335f', '#00adef'])
                                data_sources["Gráfico: Mix de Produtos (Tintas)"] = fig

                        # --- GERAR PDF ---
                        pdf_bytes = create_pdf_report(selected_reports, data_sources)
                        st.download_button(
                            label="📥 Baixar Relatório PDF",
                            data=bytes(pdf_bytes),
                            file_name=f"Relatorio_Producao_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                            mime="application/pdf"
                        )
            else:
                st.warning("Nenhum dado encontrado para o período/máquinas selecionados.")
        else:
            st.info("Carregue os dados de produção para visualizar os relatórios.")

    if selected_tab == "Configurações":
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

    if selected_tab == "Oee e Teep":
        st.subheader("Indicadores de Eficiência (OEE/TEEP)")
        
        if not st.session_state.get("oee_df", pd.DataFrame()).empty:
            df_oee = st.session_state.oee_df.copy()
            
            # Filtros na aba OEE
            st.markdown("#### Filtros")
            c1, c2 = st.columns(2)
            with c1:
                original_maquinas = sorted(df_oee['maquina'].unique().tolist())
                # Mapeamento: "180" -> "180- CX-360G"
                maq_map = {name.split('-')[0].strip() if '-' in name else name: name for name in original_maquinas}
                clean_maquinas = list(maq_map.keys())
                sel_clean_maquinas = st.multiselect("Filtrar Máquina(s)", options=clean_maquinas, default=clean_maquinas, key="oee_maq")
            with c2:
                min_date = df_oee['data'].min()
                max_date = df_oee['data'].max()
                
                # Default para Ontem
                yesterday = pd.Timestamp.today().date() - pd.Timedelta(days=1)
                default_val = (yesterday, yesterday)
                
                # Ajustar min visual para evitar erro se base for pós-ontem
                if pd.notnull(min_date):
                    visual_min = min(min_date.date(), yesterday)
                else:
                    visual_min = yesterday

                sel_dates = st.date_input("Período", value=default_val, min_value=visual_min, max_value=max_date, key="oee_date")
            
            # Aplicação dos filtros
            if sel_clean_maquinas:
                sel_originals = [maq_map[name] for name in sel_clean_maquinas]
                df_oee = df_oee[df_oee['maquina'].isin(sel_originals)]
            else:
                st.warning("Selecione ao menos uma máquina para visualizar os dados.")
                st.stop()
            
            if len(sel_dates) == 2:
                df_oee = df_oee[(df_oee['data'] >= pd.Timestamp(sel_dates[0])) & (df_oee['data'] <= pd.Timestamp(sel_dates[1]))]
            
            st.markdown("### Pergunte sobre os indicadores OEE e TEEP")
            prompt_oee = st.chat_input("Ex: Qual máquina teve a melhor performance?", key="chat_oee")
            if prompt_oee:
                with st.chat_message("user"): st.markdown(prompt_oee)
                with st.chat_message("assistant"):
                    process_chat_request(prompt_oee, {"oee_teep": df_oee})
            
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
                                  color_discrete_sequence=['#4466b1', '#00adef'])
                fig_line.update_traces(hovertemplate='%{y:.1%}')
                fig_line.update_layout(
                    yaxis_tickformat='.1%', 
                    height=400,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(t=20, b=100, l=60, r=40),
                    legend_title_text='',
                    legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5)
                )
                
                st.plotly_chart(fig_line, use_container_width=True)
                
                # Gráfico por hora
                df_hourly = df_oee.groupby('hora')[['oee', 'teep']].mean().reset_index()
                df_hourly_melted = df_hourly.melt(id_vars='hora', var_name='Métrica', value_name='Valor')
                
                fig_hourly = px.bar(df_hourly_melted, x='hora', y='Valor', color='Métrica', 
                                   barmode='group',
                                   text='Valor',
                                   labels={'Valor': '', 'hora': 'Hora', 'Métrica': ''},
                                   color_discrete_sequence=['#4466b1', '#00adef'])
                
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
                
                # Gráfico de barras por máquina (se mais de uma selecionada)
                if len(sel_clean_maquinas) > 1:
                    st.write("#### OEE por Máquina")
                    df_mac = df_oee.groupby('maquina')['oee'].mean().sort_values(ascending=False).reset_index()
                    fig_mac = px.bar(df_mac, x='maquina', y='oee', color='oee', 
                                    text='oee',
                                    color_continuous_scale=['#0a1929', '#1a335f', '#4466b1', '#00adef', '#09a38c', '#89c153'],
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
                st.write("#### Comparativo por Turno")
                df_shift = df_oee.groupby('turno')[['oee', 'teep']].mean().reset_index().sort_values('turno')
                fig_shift = px.bar(df_shift, x='turno', y=['oee', 'teep'], barmode='group',
                                  text_auto='.1%',
                                  labels={'value': '', 'variable': '', 'turno': ''},
                                  color_discrete_sequence=['#4466b1', '#00adef'],
                                  category_orders={"turno": sorted(df_shift['turno'].unique())})
                fig_shift.update_traces(hovertemplate='%{y:.1%}')
                fig_shift.update_layout(
                    yaxis_visible=False, height=400,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(t=30, b=100, l=0, r=0),
                    legend_title_text='',
                    legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5)
                )
                st.plotly_chart(fig_shift, use_container_width=True)
                
                # OEE por Operador (Precisa cruzar com Produção pois OEE não tem Operador)
                st.write("#### OEE Médio por Operador")
                
                # Tentar cruzar com Produção se disponível
                if not st.session_state.get("producao_df", pd.DataFrame()).empty:
                    df_p_temp = st.session_state.producao_df[['data', 'maquina', 'hora', 'operador']].copy()
                    # Normalizar tipos para o merge
                    df_p_temp['data'] = pd.to_datetime(df_p_temp['data'])
                    df_p_temp['hora'] = pd.to_numeric(df_p_temp['hora'], errors='coerce')
                    
                    df_oee_merged = df_oee.copy()
                    df_oee_merged['data'] = pd.to_datetime(df_oee_merged['data'])
                    df_oee_merged['hora'] = pd.to_numeric(df_oee_merged['hora'], errors='coerce')
                    
                    # Merge para trazer o operador
                    df_oee_merged = pd.merge(df_oee_merged, df_p_temp, on=['data', 'maquina', 'hora'], how='left')
                    
                    # Remover NAs de operador e agrupar
                    df_op_oee = df_oee_merged[df_oee_merged['operador'].notna()]
                    
                    # Filtrar operadores específicos (Fábio e Sem Operador)
                    exclude_ops = ["6462 - fabio", "0 - sem operador"]
                    df_op_oee = df_op_oee[~df_op_oee['operador'].astype(str).str.contains("6462|0 - sem", case=False, na=False)]
                    
                    if not df_op_oee.empty:
                        df_op_oee = df_op_oee.groupby('operador')['oee'].mean().reset_index().sort_values('oee', ascending=True)
                        fig_op_oee = px.bar(df_op_oee, x='oee', y='operador', orientation='h',
                                           text='oee',
                                           color='oee',
                                           labels={'oee': 'OEE Médio', 'operador': ''},
                                           color_continuous_scale=['#1a335f', '#4466b1', '#00adef', '#09a38c', '#89c153'])
                        
                        fig_op_oee.update_traces(texttemplate='%{text:.1%}', textposition='inside', textfont_color='white')
                        
                        # (Mediana removida conforme solicitação)

                        fig_op_oee.update_layout(
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            height=400,
                            xaxis_visible=False,
                            coloraxis_showscale=False,
                            margin=dict(t=30, b=0, l=0, r=0)
                        )
                        st.plotly_chart(fig_op_oee, use_container_width=True)
                    else:
                        st.info("Não foi possível correlacionar operadores com os dados de OEE no período selecionado.")
                else:
                    st.info("Dados de produção não disponíveis para cruzar operadores com OEE.")
                
                # 5. Distribuição de Performance
                st.write("#### Distribuição de Performance (Faixas de OEE)")
                def get_bucket(val):
                    if val < 0.5: return "Baixa (<50%)"
                    if val < 0.8: return "Normal (50-80%)"
                    return "Alta (>80%)"
                df_oee['faixa'] = df_oee['oee'].apply(get_bucket)
                df_buckets = df_oee['faixa'].value_counts().reset_index()
                df_buckets.columns = ['Faixa', 'Quantidade']
                fig_buckets = px.pie(df_buckets, values='Quantidade', names='Faixa',
                                    hole=0.4, 
                                    color='Faixa',
                                    color_discrete_map={
                                        "Baixa (<50%)": "#1a335f",
                                        "Normal (50-80%)": "#00adef",
                                        "Alta (>80%)": "#89c153"
                                    },
                                    category_orders={"Faixa": ["Baixa (<50%)", "Normal (50-80%)", "Alta (>80%)"]})
                fig_buckets.update_layout(
                    height=350,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(t=30, b=80, l=0, r=0),
                    legend_title_text='',
                    legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5)
                )
                st.plotly_chart(fig_buckets, use_container_width=True)
                
                st.write("#### Mapa de Calor: Consistência de OEE (Hora x Dia)")
                # Criar matriz para Heatmap
                df_heat = df_oee.groupby(['data', 'hora'])['oee'].mean().reset_index()
                
                # Converter data para string formatada com dia da semana
                dias_semana = {0: 'Seg', 1: 'Ter', 2: 'Qua', 3: 'Qui', 4: 'Sex', 5: 'Sáb', 6: 'Dom'}
                df_heat['data_str'] = df_heat['data'].dt.strftime('%d/%m') + " (" + df_heat['data'].dt.dayofweek.map(dias_semana) + ")"
                df_pivot = df_heat.pivot(index='hora', columns='data_str', values='oee').fillna(0) * 100
                
                fig_heat = px.imshow(df_pivot, 
                                    labels=dict(x="", y="Hora", color="OEE %"),
                                    color_continuous_scale=['#0a1929', '#1a335f', '#4466b1', '#09a38c', '#89c153'],
                                    zmin=0, zmax=100,
                                    aspect="auto")
                fig_heat.update_traces(hovertemplate='Dia: %{x}<br>Hora: %{y}<br>OEE: %{z:.1f}%')
                fig_heat.update_layout(
                    height=450,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(t=30, b=30, l=40, r=40),
                    xaxis_tickangle=-45
                )
                st.plotly_chart(fig_heat, use_container_width=True)

            else:
                st.warning("Nenhum dado encontrado para os filtros selecionados.")
        else:
            st.info("Carregue o arquivo 'oee teep.xlsx' para visualizar as métricas de eficiência.")
    if selected_tab == "Canudos":
        st.subheader("Gestão de Canudos: Produção vs Perdas")
        
        if not st.session_state.get("canudos_df", pd.DataFrame()).empty:
             df_can = st.session_state.canudos_df.copy()
             
             # Filtros (Estilo OEE, mas apenas Data)
             st.markdown("#### Filtros")
             min_date = df_can['data'].min()
             max_date = df_can['data'].max()
             
             # Proteção para datas nulas
             if pd.isnull(min_date): min_date = pd.Timestamp.today()
             if pd.isnull(max_date): max_date = pd.Timestamp.today()
             
             # Default para Ontem (conforme solicitado)
             yesterday = pd.Timestamp.today().date() - pd.Timedelta(days=1)
             default_val = (yesterday, yesterday)
             
             # Garantir que min_value abrange ontem se necessário, ou apenas deixar livre
             # st.date_input min_value trava a seleção. Se os dados começam HOJE, ontem daria erro se travado.
             # Vamos ajustar o min_date visual para incluir ontem se a base for muito recente
             visual_min = min(min_date.date(), yesterday)

             sel_dates = st.date_input("Período", value=default_val, min_value=visual_min, max_value=max_date, key="dates_canudos")
             
             # Aplicação do Filtro
             if isinstance(sel_dates, tuple): # Garante que é tupla
                 if len(sel_dates) == 2:
                    df_can = df_can[(df_can['data'] >= pd.Timestamp(sel_dates[0])) & (df_can['data'] <= pd.Timestamp(sel_dates[1]))]
                 elif len(sel_dates) == 1: # Caso selecione apenas uma data início
                    df_can = df_can[df_can['data'] >= pd.Timestamp(sel_dates[0])]
             
             st.markdown("### Pergunte sobre os dados de Canudos")
             prompt_can = st.chat_input("Ex: Qual turno produziu mais peças boas?", key="chat_canudos")
             if prompt_can:
                with st.chat_message("user"): st.markdown(prompt_can)
                with st.chat_message("assistant"):
                    process_chat_request(prompt_can, {"canudos": df_can})
             
             st.write("---")

             # Métricas Gerais
             c1, c2, c3, c4 = st.columns(4)
             with c1:
                 st.metric("Total Peças Boas", f"{df_can['pecas_boas'].sum():,.0f}".replace(",", "."))
             with c2:
                 st.metric("Total Perdas", f"{df_can['perdas'].sum():,.0f}".replace(",", "."))
             with c3:
                 eff = 0
                 total_geral = df_can['pecas_boas'].sum() + df_can['perdas'].sum()
                 if total_geral > 0:
                     eff = (df_can['pecas_boas'].sum() / total_geral) * 100
                 st.metric("Eficiência Global", f"{eff:.1f}%")
             with c4:
                 loss_pct = 0
                 if total_geral > 0:
                     loss_pct = (df_can['perdas'].sum() / total_geral) * 100
                 st.metric("% Perdas", f"{loss_pct:.1f}%")

             st.write("---")
             
             # Gráfico Comparativo: Peças Boas vs Perdas (Agrupado por Data)
             st.write("#### Produção Diária: Peças Boas vs Perdas")
             
             # Agrupar por data para o gráfico
             df_grouped = df_can.groupby('data')[['pecas_boas', 'perdas']].sum().reset_index()
             
             # Format: DD/MM (Dia)
             dias_semana = {0: 'Seg', 1: 'Ter', 2: 'Qua', 3: 'Qui', 4: 'Sex', 5: 'Sáb', 6: 'Dom'}
             df_grouped['data_label'] = df_grouped['data'].dt.strftime('%d/%m') + " (" + df_grouped['data'].dt.dayofweek.map(dias_semana) + ")"
             
             # Melt para formato do Plotly (Barras Agrupadas)
             df_melted = df_grouped.melt(id_vars='data_label', value_vars=['pecas_boas', 'perdas'], 
                                        var_name='Tipo', value_name='Quantidade')
             
             # Mapeamento de nomes para legenda
             df_melted['Tipo'] = df_melted['Tipo'].map({'pecas_boas': 'Peças Boas', 'perdas': 'Perdas'})
             
             fig_can = px.bar(df_melted, x='data_label', y='Quantidade', color='Tipo',
                             barmode='group',
                             text='Quantidade',
                             labels={'Quantidade': 'Qtd. Peças', 'data_label': '', 'Tipo': ''},
                             # Cores: Cyan para Boas, Vermelho/Laranja ou Azul Escuro para Perdas?
                             # Vamos usar Cyan (#00adef) para Boas e Magenta/Roxo (#e91e63 ou da paleta #1a335f) para contrastar
                             # Usando Paleta do App: Cyan vs Dark Blue
                             color_discrete_map={'Peças Boas': '#00adef', 'Perdas': '#1a335f'})
                             
             fig_can.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
             
             # Linha Mediana (Peças Boas)
             median_boas = df_grouped['pecas_boas'].median()
             fig_can.add_hline(y=median_boas, line_dash="dash", line_color="#89c153", 
                               annotation_text=f"Mediana: {median_boas:,.0f}", 
                               annotation_position="top right",
                               annotation_font_color="#89c153")
             
             fig_can.update_layout(
                 paper_bgcolor='rgba(0,0,0,0)',
                 plot_bgcolor='rgba(0,0,0,0)',
                 height=450,
                 margin=dict(t=30, b=100, l=0, r=0),
                 legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5)
             )
             st.plotly_chart(fig_can, use_container_width=True)
             
             st.write("---")
             
             # Novo Gráfico: Peças por Hora, por Turno (Baseado em 8h de turno)
             st.write("#### Peças por Hora")
             if not df_can.empty:
                 # Agrupar por data e turno para somar a produção do período de 8h
                 df_hourly = df_can.groupby(['data', 'turno'])['pecas_boas'].sum().reset_index()
                 # Dividir por 8 para ter a média horária daquele shift
                 df_hourly['pecas_por_hora'] = df_hourly['pecas_boas'] / 8
                 
                 # Média das médias horárias por turno no período selecionado
                 df_avg_hourly = df_hourly.groupby('turno')['pecas_por_hora'].mean().reset_index()
                 
                 # Mapeamento de Cores (Paleta do App)
                 palette_map = {
                     'Turno A': '#00adef', 'Turno B': '#1a335f', 'Turno C': '#89c153',
                     'A': '#00adef', 'B': '#1a335f', 'C': '#89c153',
                     '1': '#00adef', '2': '#1a335f', '3': '#89c153'
                 }
                 
                 fig_hourly = px.bar(df_avg_hourly, x='turno', y='pecas_por_hora',
                                    color='turno',
                                    text='pecas_por_hora',
                                    labels={'pecas_por_hora': 'Peças/Hora', 'turno': 'Turno'},
                                    color_discrete_map=palette_map)
                 
                 # Adicionar linha de mediana
                 median_val = df_avg_hourly['pecas_por_hora'].median()
                 fig_hourly.add_hline(y=median_val, line_dash="dash", line_color="#89c153", 
                                    annotation_text=f"Mediana: {median_val:,.1f}", 
                                    annotation_position="top right",
                                    annotation_font_color="#89c153")
                 
                 fig_hourly.update_traces(texttemplate='%{text:,.1f}', textposition='outside')
                 fig_hourly.update_layout(
                     paper_bgcolor='rgba(0,0,0,0)',
                     plot_bgcolor='rgba(0,0,0,0)',
                     height=400,
                     margin=dict(t=30, b=50, l=0, r=0),
                     showlegend=False
                 )
                 st.plotly_chart(fig_hourly, use_container_width=True)

             st.write("---")
             st.write("#### Análise por Turno")

             # Lógica de Turnos Customizados (Solicitado: A das 6 as 14, B das 14 as 22)
             def get_custom_shift(h):
                 if 6 <= h < 14: return "Turno A (06-14h)"
                 if 14 <= h < 22: return "Turno B (14-22h)"
                 return "Outros"

             df_can['turno_custom'] = df_can['hora'].apply(get_custom_shift)
             
             # Filtrar apenas turnos A e B para o gráfico comparativo solicitado
             df_shifts_can = df_can[df_can['turno_custom'].isin(["Turno A (06-14h)", "Turno B (14-22h)"])]
             
             if not df_shifts_can.empty:
                 df_shift_sum = df_shifts_can.groupby('turno_custom')['pecas_boas'].sum().reset_index()
                 fig_custom_shift = px.bar(df_shift_sum, x='turno_custom', y='pecas_boas',
                                          color='turno_custom',
                                          text='pecas_boas',
                                          labels={'pecas_boas': 'Peças Boas', 'turno_custom': 'Turno'},
                                          color_discrete_map={"Turno A (06-14h)": "#00adef", "Turno B (14-22h)": "#1a335f"})
                 
                 fig_custom_shift.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
                 fig_custom_shift.update_layout(
                     paper_bgcolor='rgba(0,0,0,0)',
                     plot_bgcolor='rgba(0,0,0,0)',
                     height=400,
                     margin=dict(t=30, b=50, l=0, r=0),
                     showlegend=False
                 )
                 st.plotly_chart(fig_custom_shift, use_container_width=True)
             
             # 1. Peças por Hora, por Turno
             # Se houver dados de HORA (>0), usamos hourly agregation. Se não, mostramos aviso ou agrupamos só por Turno.
             # O usuário pediu "peças por hora, por turno". Vamos assumir X=Hora, Y=Peças, Color=Turno
             if df_can['hora'].sum() > 0:
                 df_hora_turno = df_can.groupby(['turno', 'hora'])['pecas_boas'].sum().reset_index()
                 fig_hora = px.bar(df_hora_turno, x='hora', y='pecas_boas', color='turno',
                                  title="Peças por Hora (Detalhado por Turno)",
                                  labels={'hora': 'Hora do Dia', 'pecas_boas': 'Qtd. Peças', 'turno': 'Turno'},
                                  color_discrete_sequence=['#00adef', '#1a335f', '#89c153']) # Cyan, Blue, Green
                 
                 # Linha Mediana (Hora)
                 median_hora = df_hora_turno['pecas_boas'].median()
                 fig_hora.add_hline(y=median_hora, line_dash="dash", line_color="#89c153",
                                   annotation_text=f"Mediana: {median_hora:,.0f}",
                                   annotation_position="top right",
                                   annotation_font_color="#89c153")
                                   
                 fig_hora.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                 st.plotly_chart(fig_hora, use_container_width=True)
             else:
                 # Se não tiver hora, não dá pra fazer "por hora".
                 pass 
                 # st.warning("Dados não contêm informação de hora para detalhamento horário.")

             # Layout para Produção e Perdas por Turno
             c_t1, c_t2 = st.columns(2)
             
             with c_t1:
                 # Produção por Turno
                 df_prod_turno = df_can.groupby('turno')['pecas_boas'].sum().reset_index().sort_values('turno')
                 fig_pt = px.pie(df_prod_turno, names='turno', values='pecas_boas',
                                title="Produção Total por Turno",
                                color_discrete_sequence=['#00adef', '#1a335f', '#89c153'],
                                category_orders={"turno": sorted(df_prod_turno['turno'].unique())})
                 fig_pt.update_traces(textposition='inside', textinfo='percent+label')
                 fig_pt.update_layout(
                     paper_bgcolor='rgba(0,0,0,0)', 
                     plot_bgcolor='rgba(0,0,0,0)', 
                     height=350
                 )
                 st.plotly_chart(fig_pt, use_container_width=True)
                 
             with c_t2:
                 # Perdas por Turno
                 df_loss_turno = df_can.groupby('turno')['perdas'].sum().reset_index().sort_values('turno')
                 fig_lt = px.pie(df_loss_turno, names='turno', values='perdas',
                                title="Perdas Totais por Turno",
                                color_discrete_sequence=['#1a335f', '#00adef', '#89c153'],
                                category_orders={"turno": sorted(df_loss_turno['turno'].unique())}) # Dark Blue first for losses logic (optional variation)
                 fig_lt.update_traces(textposition='inside', textinfo='percent+label')
                 fig_lt.update_layout(
                     paper_bgcolor='rgba(0,0,0,0)',
                     plot_bgcolor='rgba(0,0,0,0)', 
                     height=350
                 )
                 st.plotly_chart(fig_lt, use_container_width=True)
                
        else:
            st.info("Arquivo 'Canudos.xlsx' não carregado ou vazio. Verifique se o arquivo está na pasta.")

    if selected_tab == "Assistente IA":
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



    if selected_tab == "Fichas":
        if not st.session_state.trabalhos_df.empty:
            df_fichas = st.session_state.trabalhos_df.copy()
            
            # --- SEÇÃO FINANCEIRA ---
            st.write("### Análise Financeira")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Custo Médio (por Garrafa)", f"R$ {df_fichas['custo_total_tinta'].mean():.4f}")
            with c2:
                st.metric("Produto Maior Custo (Unidade)", f"R$ {df_fichas['custo_total_tinta'].max():.4f}")
            with c3:
                st.metric("Produto Menor Custo (Unidade)", f"R$ {df_fichas['custo_total_tinta'].min():.4f}")
            
            st.write("#### Top 10: Produtos com Maior Custo (1.000 un.)")
            df_top10 = df_fichas.nlargest(10, 'custo_total_tinta_mil')[['referencia', 'produto', 'decoracao', 'custo_total_tinta_mil']].copy()
            
            def clean_name_fichas(name):
                if not isinstance(name, str): return str(name)
                name = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', name)
                name = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', name)
                name = name.lower().replace('garrafa', '').replace('corpo', '').title()
                return re.sub(r'\b[mM][lL]\b', 'ml', name).strip()

            df_top10['produto_clean'] = df_top10['produto'].apply(clean_name_fichas)
            df_top10['label'] = df_top10['referencia'] + " - " + df_top10['produto_clean'] + " (" + df_top10['decoracao'] + ")"
            df_top10 = df_top10.sort_values('custo_total_tinta_mil', ascending=True)
            
            fig_top10 = px.bar(df_top10, x='custo_total_tinta_mil', y='label', orientation='h',
                              text='custo_total_tinta_mil', color='produto', 
                              labels={'custo_total_tinta_mil': 'Custo (R$)', 'label': 'Produto'},
                              color_discrete_sequence=['#4466b1', '#00adef', '#09a38c', '#89c153'])
            
            fig_top10.update_traces(texttemplate='R$ %{text:.2f}', textposition='inside', insidetextanchor='start')
            fig_top10.update_layout(
                margin=dict(t=20, b=0, l=0, r=0), height=450, showlegend=False, xaxis_visible=False,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                yaxis={'categoryorder':'array', 'categoryarray': df_top10['label'].tolist()}
            )
            st.plotly_chart(fig_top10, use_container_width=True)

            with st.expander("Ver Detalhamento Financeiro Completo"):
                df_disp = df_fichas[['referencia', 'decoracao', 'produto', 'custo_total_tinta', 'custo_total_tinta_mil']].copy()
                df_disp.columns = ['Referência', 'Decoração', 'Produto', 'Custo Unitário (R$)', 'Custo 1.000 un (R$)']
                st.dataframe(df_disp.style.format(precision=4, decimal=',', thousands='.'), use_container_width=True)

            st.write("---")
            
            # --- SEÇÃO TÉCNICA ---
            st.write("### Análise de Performance e Consumo")
            cores = ['cyan', 'magenta', 'yellow', 'black', 'white', 'varnish']
            df_fichas['total_ml'] = df_fichas[cores].sum(axis=1)
            
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Total de Fichas", len(df_fichas))
            with m2:
                total_vol = df_fichas[cores].sum().sum()
                st.metric("Volume Total (ml/1k)", f"{total_vol:.1f}")
            with m3:
                avg_time = df_fichas['tempo_s'].mean()
                st.metric("Tempo Médio (s)", f"{avg_time:.1f}")
            with m4:
                most_used_color = df_fichas[cores].sum().idxmax()
                st.metric("Cor Mais Usada", most_used_color.capitalize())

            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                st.write("#### Distribuição de Tintas por Cor (%)")
                cons_cor = df_fichas[cores].sum().reset_index()
                cons_cor.columns = ['Cor', 'Volume']
                fig_pie = px.pie(cons_cor, values='Volume', names='Cor', hole=0.4,
                               color_discrete_map={'cyan': '#00adef', 'varnish': '#1a335f', 'magenta': '#4466b1', 
                                                 'yellow': '#89c153', 'black': '#09a38c', 'white': '#d3d3d3'})
                fig_pie.update_layout(margin=dict(t=20, b=80, l=0, r=0), height=400,
                                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                    legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5))
                st.plotly_chart(fig_pie, use_container_width=True)

            with col_chart2:
                st.write("#### Mix de Produtos (Qtd de Fichas)")
                prod_counts = df_fichas['produto'].value_counts().reset_index()
                prod_counts.columns = ['produto', 'quantidade']
                fig_prod = px.pie(prod_counts, values='quantidade', names='produto', hole=0.4,
                                 color_discrete_sequence=['#1a335f', '#4466b1', '#00adef', '#09a38c', '#89c153'])
                fig_prod.update_traces(textinfo='percent')
                fig_prod.update_layout(margin=dict(t=20, b=80, l=0, r=0), height=400,
                                     paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                     legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5))
                st.plotly_chart(fig_prod, use_container_width=True)

            st.write("#### Hierarquia de Consumo (Decoração > Produto)")
            fig_tree = px.treemap(df_fichas, path=['decoracao', 'produto'], values='total_ml',
                                 color='total_ml', color_continuous_scale=['#1a335f', '#4466b1', '#00adef', '#09a38c', '#89c153'])
            fig_tree.update_layout(coloraxis_showscale=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=450)
            st.plotly_chart(fig_tree, use_container_width=True)

            with st.expander("Ver Explorador de Performance Geral"):
                df_tec_disp = df_fichas[['referencia', 'decoracao', 'produto', 'total_ml', 'tempo_s']].copy()
                df_tec_disp.columns = ['Referência', 'Decoração', 'Produto', 'Consumo Total (ml/1k)', 'Tempo (s)']
                st.dataframe(df_tec_disp, use_container_width=True, hide_index=True)

        else:
            st.info("Nenhum dado disponível para análise de fichas.")

    if selected_tab == "Produção":
        st.subheader("Controle de Produção")
        
        if not st.session_state.get("producao_df", pd.DataFrame()).empty:
            df_prod = st.session_state.producao_df.copy()
            
            # --- Filtros (Igual OEE) ---
            st.markdown("#### Filtros")
            c1, c2 = st.columns(2)
            with c1:
                original_maquinas_prod = sorted(df_prod['maquina'].unique().tolist())
                # Mapeamento: "180" -> "180- CX-360G"
                maq_map_prod = {name.split('-')[0].strip() if '-' in name else name: name for name in original_maquinas_prod}
                clean_maquinas_prod = list(maq_map_prod.keys())
                sel_clean_prod = st.multiselect("Filtrar Máquina(s)", options=clean_maquinas_prod, default=clean_maquinas_prod, key="prod_maq_multi")
            with c2:
                if not df_prod['data'].empty:
                    min_date_prod = df_prod['data'].min()
                    max_date_prod = df_prod['data'].max()
                    
                    # Default para Ontem
                    yesterday_prod = pd.Timestamp.today().date() - pd.Timedelta(days=1)
                    default_val_prod = (yesterday_prod, yesterday_prod)
                    
                    if pd.notnull(min_date_prod):
                        visual_min_prod = min(min_date_prod.date(), yesterday_prod)
                    else:
                        visual_min_prod = yesterday_prod

                    sel_dates_prod = st.date_input("Período", value=default_val_prod, min_value=visual_min_prod, max_value=max_date_prod, key="prod_date")
                else:
                    sel_dates_prod = []

            # Aplicação dos filtros
            if sel_clean_prod:
                sel_originals_prod = [maq_map_prod[name] for name in sel_clean_prod]
                df_prod = df_prod[df_prod['maquina'].isin(sel_originals_prod)]
            else:
                st.warning("Selecione ao menos uma máquina para visualizar os dados.")
                st.stop()
            
            if len(sel_dates_prod) == 2:
                df_prod = df_prod[(df_prod['data'] >= pd.Timestamp(sel_dates_prod[0])) & (df_prod['data'] <= pd.Timestamp(sel_dates_prod[1]))]

            st.markdown("### Pergunte sobre os dados de Produção")
            prompt_prod = st.chat_input("Ex: Quem foi o operador mais produtivo hoje?", key="chat_producao")
            if prompt_prod:
               with st.chat_message("user"): st.markdown(prompt_prod)
               with st.chat_message("assistant"):
                   process_chat_request(prompt_prod, {"producao": df_prod})

            if not df_prod.empty:
                # --- Métricas Gerais ---
                total_pecas = df_prod['producao_total'].sum()
                total_boas = df_prod['pecas_boas'].sum()
                total_rejeito = df_prod['rejeito'].sum()
                
                # Evitar divisão por zero
                perc_boas = (total_boas / total_pecas) if total_pecas > 0 else 0
                perc_rejeito = (total_rejeito / total_pecas) if total_pecas > 0 else 0

                # Linha 1: Contagens Absolutas
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Total de Peças", f"{total_pecas:,.0f}".replace(",", "."))
                with c2:
                    st.metric("Peças Boas", f"{total_boas:,.0f}".replace(",", "."))
                with c3:
                    st.metric("Rejeitos", f"{total_rejeito:,.0f}".replace(",", "."))
                
                # Linha 2: Porcentagens
                c4, c5, c6 = st.columns(3)
                with c4:
                    st.metric("% Peças Boas", f"{perc_boas:.1%}")
                with c5:
                    st.metric("% Rejeitos", f"{perc_rejeito:.1%}")
                with c6:
                    st.empty() # Espaço vazio para manter alinhamento
                    
                st.write("---")
                
                # 1. Gráfico de Peças Produzidas por Máquina
                st.write("#### Peças Produzidas Por Máquina")
                
                # Agrupar por máquina
                df_maq_prod = df_prod.groupby('maquina')['pecas_boas'].sum().reset_index().sort_values('pecas_boas', ascending=False)
                
                fig_prod_maq = px.bar(df_maq_prod, x='maquina', y='pecas_boas', color='maquina',
                                     text='pecas_boas',
                                     labels={'pecas_boas': 'Peças Boas', 'maquina': 'Máquina'},
                                     # Usando a paleta de 5 cores
                                     color_discrete_sequence=['#1a335f', '#4466b1', '#00adef', '#09a38c', '#89c153'])
                                     
                fig_prod_maq.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
                fig_prod_maq.update_layout(
                    yaxis_visible=False,
                    showlegend=False,
                    height=500,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(t=30, b=50, l=0, r=0)
                )
                st.plotly_chart(fig_prod_maq, use_container_width=True)
                
                st.write("---")
                
                # --- NOVOS GRÁFICOS ---
                
                # 1. Evolução Diária (Barras)
                st.write("#### Produção Diária (Peças Boas)")
                df_daily_prod = df_prod.groupby('data')['pecas_boas'].sum().reset_index()
                # Formatar data para DD/MM
                df_daily_prod['data_label'] = df_daily_prod['data'].dt.strftime('%d/%m')
                
                fig_daily_prod = px.bar(df_daily_prod, x='data_label', y='pecas_boas',
                                         labels={'pecas_boas': 'Peças Boas', 'data_label': 'Data'},
                                         text='pecas_boas',
                                         color_discrete_sequence=['#00adef']) # Cyan
                fig_daily_prod.update_traces(texttemplate='%{text:,.0f}', textposition='inside', textfont_color='white')
                # Mediana Produção Diária
                median_daily_prod = df_daily_prod['pecas_boas'].median()
                fig_daily_prod.add_hline(y=median_daily_prod, line_dash="dash", line_color="#89c153",
                                        annotation_text=f"Mediana: {median_daily_prod:,.0f}",
                                        annotation_position="top right",
                                        annotation_font_color="#89c153")

                fig_daily_prod.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    height=350,
                    margin=dict(t=20, b=60, l=0, r=0)
                )
                st.plotly_chart(fig_daily_prod, use_container_width=True)
                
                st.write("---")

                # 2. Evolução Horária (Linha) -> Agora Barra
                st.write("#### Evolução Horária da Produção")
                df_hourly_prod = df_prod.groupby('hora')['pecas_boas'].sum().reset_index()
                # Filtrar apenas das 06 às 22
                df_hourly_prod = df_hourly_prod[(df_hourly_prod['hora'] >= 6) & (df_hourly_prod['hora'] <= 22)]
                
                fig_hourly_prod = px.bar(df_hourly_prod, x='hora', y='pecas_boas',
                                         labels={'pecas_boas': 'Peças Boas', 'hora': 'Hora'},
                                         color_discrete_sequence=['#00adef']) # Usando Cyan para destaque
                # Mediana Evolução Horária
                median_hourly_prod = df_hourly_prod['pecas_boas'].median()
                fig_hourly_prod.add_hline(y=median_hourly_prod, line_dash="dash", line_color="#89c153",
                                        annotation_text=f"Mediana: {median_hourly_prod:,.0f}",
                                        annotation_position="top right",
                                        annotation_font_color="#89c153")

                fig_hourly_prod.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    height=350,
                    margin=dict(t=20, b=40, l=0, r=0)
                )
                st.plotly_chart(fig_hourly_prod, use_container_width=True)
                
                # 3. Ranking de Operadores (Filtrado)
                st.write("#### Peças Produzidas por Operador")
                target_ops = ["Marcus Vinicius", "Yuri Franco", "Diego Matheus", "Matheus Anzolin"]
                # Filtrar apenas os operadores solicitados. Normalizar para evitar problemas de case se necessário
                df_op_prod = df_prod[df_prod['operador'].astype(str).str.strip().isin(target_ops)]
                
                if df_op_prod.empty:
                     # Fallback caso os nomes não batam exatamente, tenta busca parcial ou mostra todos
                     df_op_prod = df_prod[df_prod['operador'].astype(str).str.contains('|'.join(target_ops), case=False, na=False)]
                
                # Agrupar e ordenar
                df_op_prod_grouped = df_op_prod.groupby('operador')['pecas_boas'].sum().reset_index().sort_values('pecas_boas', ascending=True)

                fig_op = px.bar(df_op_prod_grouped, x='pecas_boas', y='operador', orientation='h',
                               text='pecas_boas',
                               color='operador', # Adicionar cor por operador
                               labels={'pecas_boas': '', 'operador': ''},
                               color_discrete_sequence=['#1a335f', '#4466b1', '#00adef', '#09a38c', '#89c153']) # Paleta para diferenciar
                
                fig_op.update_traces(texttemplate='%{text:,.0f}', textposition='inside', textfont_color='white')
                fig_op.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    height=400,
                    xaxis_visible=False,
                    yaxis={'categoryorder':'total ascending'}, # Garante maior no TOPO
                    showlegend=False, # Esconder legenda pois nomes já estão no eixo Y
                    margin=dict(t=30, b=0, l=0, r=0)
                )
                st.plotly_chart(fig_op, use_container_width=True)
                    
                
                # 4. Comparativo de Turnos (Nova Linha)
                st.write("#### Comparativo de Turnos")
                df_shift_prod = df_prod.groupby('turno')['pecas_boas'].sum().reset_index().sort_values('turno') # Ordenar alfabeticamente (A, B, C)
                
                fig_shift_prod = px.pie(df_shift_prod, values='pecas_boas', names='turno',
                                       color='turno',
                                       color_discrete_sequence=['#4466b1', '#00adef', '#09a38c'], # Blue/Cyan mix
                                       hole=0.5,
                                       category_orders={"turno": sorted(df_shift_prod['turno'].unique())})
                fig_shift_prod.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    height=400,
                    margin=dict(t=30, b=20, l=0, r=0),
                    legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5)
                )
                st.plotly_chart(fig_shift_prod, use_container_width=True)
                    
                st.write("---")
                
                # 5. Top Produtos
                st.write("#### Top Produtos Mais Fabricados")
                
                # Função de limpeza de nome
                def clean_prod_name(name):
                    if not isinstance(name, str): return str(name)
                    # 1. Remover código antes do primeiro " - "
                    if ' - ' in name:
                        name = name.split(' - ', 1)[1]
                    
                    # 2. Separar letras de números (ex: Facil530 -> Facil 530)
                    name = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', name)
                    # 2b. Separar números de unidades/letras (ex: 530ML -> 530 ML)
                    name = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', name)
                    
                    # 3. Remover palavras desnecessárias (Inicio e fim)
                    name = name.lower()
                    name = name.replace('corpo ', '').replace('garrafa ', '')
                    name = name.replace(' 2023', '').replace(' 2024', '')
                    
                    # 4. Formatação Title Case
                    name = name.title()
                    
                    # 5. Ajustes finos de unidade e pontuação
                    # Forçar 'ml' e 'mm' minúsculos ignorando o Title Case anterior
                    name = re.sub(r'\b[mM][lL]\b', 'ml', name)
                    name = re.sub(r'\b[mM][mM]\b', 'mm', name)
                    
                    name = name.replace(' - ', ' ') # Remover hifens restantes
                    
                    return name.strip()

                df_top_prod = df_prod.groupby('produto')['pecas_boas'].sum().reset_index().sort_values('pecas_boas', ascending=False).head(10)
                df_top_prod['produto_label'] = df_top_prod['produto'].apply(clean_prod_name)
                
                fig_top_prod = px.bar(df_top_prod, x='pecas_boas', y='produto_label', orientation='h',
                                     text='pecas_boas',
                                     color='pecas_boas',
                                     color_continuous_scale=['#1a335f', '#4466b1', '#00adef', '#09a38c', '#89c153'],
                                     labels={'pecas_boas': '', 'produto_label': ''})
                                     
                fig_top_prod.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    yaxis={'categoryorder':'total ascending'}, # Garante maior em cima
                    height=500,
                    coloraxis_showscale=False,
                    xaxis_visible=True, # Mostrar eixo X para referência de volume
                    margin=dict(t=30, b=0, l=0, r=0)
                )
                fig_top_prod.update_traces(texttemplate='%{text:,.0f}', textposition='inside', textfont_color='white')
                
                st.plotly_chart(fig_top_prod, use_container_width=True)

                
            else:
                 st.warning("Nenhum dado encontrado para os filtros selecionados.")
            
        else:
            st.info("Carregue o arquivo 'producao.xlsx' para visualizar os dados.")


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
print(">>> Script finalizado e pronto para exibir na tela.")











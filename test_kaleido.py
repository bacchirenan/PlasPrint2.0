import plotly.express as px
import plotly.io as pio
import sys
import time

print("--- Iniciando teste simples de Kaleido ---")
try:
    fig = px.scatter(x=[1, 2, 3], y=[4, 5, 6], title="Teste Simples")
    print("Tentando pio.to_image...")
    start_time = time.time()
    img_bytes = pio.to_image(fig, format="png")
    end_time = time.time()
    print(f"Sucesso! Exportado em {end_time - start_time:.2f} segundos.")
    with open("test_simple.png", "wb") as f:
        f.write(img_bytes)
except Exception as e:
    print(f"ERRO: {e}")
    sys.exit(1)

"""
Script de teste para verificar se o Kaleido funciona com timeout
"""
import plotly.express as px
import plotly.io as pio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import time

def export_chart_with_timeout(fig):
    """Exporta o gráfico usando Kaleido"""
    fig.update_layout(
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(color='black')
    )
    
    img_bytes = pio.to_image(fig, format="png", width=800, height=450, scale=2)
    return img_bytes

print("=== Teste de Exportação de Gráfico com Timeout ===\n")

# Criar um gráfico simples
fig = px.bar(x=['A', 'B', 'C'], y=[1, 3, 2], title="Teste de Gráfico")

print("1. Tentando exportar gráfico com timeout de 15 segundos...")
start_time = time.time()

try:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(export_chart_with_timeout, fig)
        try:
            img_bytes = future.result(timeout=15)
            elapsed = time.time() - start_time
            print(f"✓ Sucesso! Gráfico exportado em {elapsed:.2f} segundos")
            print(f"  Tamanho da imagem: {len(img_bytes)} bytes")
            
            # Salvar imagem para verificação
            with open("test_chart_output.png", "wb") as f:
                f.write(img_bytes)
            print(f"  Imagem salva como: test_chart_output.png")
            
        except FutureTimeoutError:
            elapsed = time.time() - start_time
            print(f"✗ TIMEOUT após {elapsed:.2f} segundos")
            print("  O Kaleido travou durante a exportação")
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"✗ ERRO após {elapsed:.2f} segundos: {str(e)}")
            
except Exception as e:
    print(f"✗ ERRO CRÍTICO: {str(e)}")

print("\n=== Teste Concluído ===")

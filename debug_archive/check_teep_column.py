import pandas as pd
import numpy as np

try:
    # Carregar dados
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    
    print("Colunas do arquivo:")
    for i, col in enumerate(df.columns):
        print(f"  {i}: {col}")
    
    print("\n" + "=" * 80)
    print("Primeiras 10 linhas do arquivo (colunas relevantes):")
    print("=" * 80)
    
    # Mostrar as primeiras linhas
    cols_to_show = [1, 2, 3, 4, 7, 8, 9, 10, 11]  # Máquina, Data, Turno, Hora, Disp, Perf, Qual, TEEP, OEE
    print(df.iloc[:10, cols_to_show])
    
    print("\n" + "=" * 80)
    print("Verificando se estamos lendo a coluna TEEP correta:")
    print("=" * 80)
    print(f"Coluna 10 (K): {df.columns[10] if len(df.columns) > 10 else 'N/A'}")
    print(f"Coluna 11 (L): {df.columns[11] if len(df.columns) > 11 else 'N/A'}")
    
    # Mostrar algumas linhas de fevereiro
    new_df = pd.DataFrame()
    new_df['maquina'] = df.iloc[:, 1]
    new_df['data'] = df.iloc[:, 2]
    new_df['turno'] = df.iloc[:, 3]
    new_df['hora'] = df.iloc[:, 4]
    new_df['col_10'] = df.iloc[:, 10]  # Suposta TEEP
    new_df['col_11'] = df.iloc[:, 11]  # Suposta OEE
    
    # Converter data
    new_df['data'] = pd.to_datetime(new_df['data'], dayfirst=True, format='mixed', errors='coerce')
    
    # Filtrar fevereiro
    mask_feb = (new_df['data'] >= '2026-02-01') & (new_df['data'] <= '2026-02-11')
    feb_data = new_df[mask_feb]
    
    print("\n" + "=" * 80)
    print("Amostra de dados de fevereiro (01/02 a 11/02):")
    print("=" * 80)
    print(feb_data.head(20))
    
    print("\n" + "=" * 80)
    print("Valores únicos na coluna 10 (TEEP?):")
    print("=" * 80)
    print(feb_data['col_10'].value_counts().head(10))
    
    print("\n" + "=" * 80)
    print("Valores únicos na coluna 11 (OEE?):")
    print("=" * 80)
    print(feb_data['col_11'].value_counts().head(10))
    
except Exception as e:
    print(f"Erro: {e}")
    import traceback
    traceback.print_exc()

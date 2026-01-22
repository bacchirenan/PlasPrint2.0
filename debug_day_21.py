import pandas as pd
import numpy as np

def inspect_day_21():
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    
    # Col 1: Máquina, Col 2: Data, Col 3: Turno, Col 4: Hora, Col 7: Disp, Col 8: Perf, Col 9: Qual
    data = pd.DataFrame()
    data['maquina'] = df.iloc[:, 1]
    data['data'] = df.iloc[:, 2]
    data['turno'] = df.iloc[:, 3]
    data['hora'] = df.iloc[:, 4]
    data['disp'] = df.iloc[:, 7]
    data['perf'] = df.iloc[:, 8]
    data['qual'] = df.iloc[:, 9]
    data['oee_sheet'] = df.iloc[:, 11]
    
    data = data[data['maquina'].notna()]
    data = data[~data['maquina'].astype(str).str.contains('Turno', na=False)]
    
    # Converter data
    data['data_dt'] = pd.to_datetime(data['data'], dayfirst=True, format='mixed', errors='coerce')
    
    # Filtrar dia 21
    target = data[data['data_dt'] == '2026-01-21'].copy()
    
    if target.empty:
        print("Nenhum dado encontrado para 2026-01-21")
        # Mostrar o que tem de data
        print("Datas encontradas:", data['data'].unique()[:10])
        return

    # Limpar floats
    for col in ['disp', 'perf', 'qual', 'oee_sheet']:
        target[col] = target[col].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
        target[col] = pd.to_numeric(target[col], errors='coerce').fillna(0) / 100.0
        
    target['oee_calc'] = (target['disp'] * target['perf'] * target['qual']).round(4)
    
    # Filtro de hora do app (6-21)
    target_filtered = target[(target['hora'] >= 6) & (target['hora'] <= 21)].copy()
    
    print(f"--- Diagnóstico Detalhado 2026-01-21 ---")
    print(f"Total de registros no dia (sem filtro hora): {len(target)}")
    print(f"Registros entre 06h e 21h: {len(target_filtered)}")
    
    # Agrupar por Turno e Máquina (usando MÉDIA, pois o usuário mencionou 80.32% que parece uma média)
    print("\n--- Resultados por Máquina (MÉDIA entre 06-21h) ---")
    mq_stats = target_filtered.groupby('maquina').agg({
        'disp': 'mean',
        'perf': 'mean',
        'qual': 'mean',
        'oee_calc': 'mean'
    })
    mq_stats *= 100
    print(mq_stats.to_string())
    
    print("\n--- Resultados por Turno (MÉDIA entre 06-21h) ---")
    # Turno 1 = A, 2 = B
    turno_stats = target_filtered.groupby('turno').agg({
        'disp': 'mean',
        'perf': 'mean',
        'qual': 'mean',
        'oee_calc': 'mean'
    })
    turno_stats *= 100
    print(turno_stats.to_string())

    print("\n--- OEE Geral (MÉDIA de todos os registros 06-21h) ---")
    print(f"OEE Geral: {target_filtered['oee_calc'].mean()*100:.2f}%")

    # Verificar se as máquinas batem com o que o usuário disse: 28, 180, 181
    # Note: O nome na planilha pode ser "28-CX-360G"
    
    print("\n--- Amostra de dados para conferência (Máquina 28) ---")
    print(target_filtered[target_filtered['maquina'].astype(str).str.contains('28')].head(10).to_string())

inspect_day_21()

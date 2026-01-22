import pandas as pd
import numpy as np

def debug_3_machines():
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    
    data = pd.DataFrame()
    data['maquina'] = df.iloc[:, 1]
    data['data'] = df.iloc[:, 2]
    data['turno'] = df.iloc[:, 3]
    data['hora'] = df.iloc[:, 4]
    data['disp'] = df.iloc[:, 7]
    data['perf'] = df.iloc[:, 8]
    data['qual'] = df.iloc[:, 9]

    data = data[data['maquina'].notna()]
    data = data[~data['maquina'].astype(str).str.contains('Turno', na=False)]
    for col in ['disp', 'perf', 'qual']:
        data[col] = data[col].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
        data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0) / 100.0

    data['data_dt'] = pd.to_datetime(data['data'], dayfirst=True, format='mixed', errors='coerce')
    day21 = data[data['data_dt'] == '2026-01-21'].copy()
    day21 = day21[(day21['hora'] >= 6) & (day21['hora'] <= 21)]
    
    # Filter 3 machines
    subset = day21[day21['maquina'].str.contains('28|180|181')]
    
    print("--- 3 Machines Analysis (Day 21) ---")
    
    for t in ['1', '2']:
        tsk = subset[subset['turno'].astype(str).str.startswith(t)]
        if tsk.empty: continue
        
        # Calc OEE Row
        oee_row = tsk['disp'] * tsk['perf'] * tsk['qual']
        
        # Method: Mean of Non-Zero OEE
        mean_nz = oee_row[oee_row > 0].mean() * 100
        
        print(f"Turno {t}: Mean NZ OEE = {mean_nz:.2f}")

debug_3_machines()

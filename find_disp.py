import pandas as pd
import numpy as np

def find_disp():
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    
    data = pd.DataFrame()
    data['maquina'] = df.iloc[:, 1]
    data['data'] = df.iloc[:, 2]
    data['hora'] = df.iloc[:, 4]
    data['disp'] = df.iloc[:, 7]

    data = data[data['maquina'].notna()]
    data = data[~data['maquina'].astype(str).str.contains('Turno', na=False)]
    data['disp'] = data['disp'].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
    data['disp'] = pd.to_numeric(data['disp'], errors='coerce').fillna(0)

    data['data_dt'] = pd.to_datetime(data['data'], dayfirst=True, format='mixed', errors='coerce')
    target = data[(data['data_dt'] == '2026-01-21') & (data['maquina'].str.contains('28'))].copy()
    
    # Try all hour windows
    for start in range(0, 24):
        for end in range(start, 24):
            subset = target[(target['hora'] >= start) & (target['hora'] <= end)]
            if subset.empty: continue
            
            mean_d = subset['disp'].mean()
            if abs(mean_d - 66.77) < 0.1:
                print(f"Found Disp 66.77 in window {start}-{end}: {mean_d}")

find_disp()

import pandas as pd
import numpy as np

def check_mixed_logic():
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    
    # Extract
    data = pd.DataFrame()
    data['maquina'] = df.iloc[:, 1]
    data['data'] = df.iloc[:, 2]
    data['hora'] = df.iloc[:, 4]
    data['disp'] = df.iloc[:, 7]
    data['perf'] = df.iloc[:, 8]
    data['qual'] = df.iloc[:, 9]

    # Clean
    data = data[data['maquina'].notna()]
    data = data[~data['maquina'].astype(str).str.contains('Turno', na=False)]
    
    for col in ['disp', 'perf', 'qual']:
        data[col] = data[col].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
        data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0) / 100.0

    # Filter Day 21, Maq 28
    data['data_dt'] = pd.to_datetime(data['data'], dayfirst=True, format='mixed', errors='coerce')
    target = data[(data['data_dt'] == '2026-01-21') & (data['maquina'].str.contains('28'))].copy()
    
    # Time Filter 6-21
    target = target[(target['hora'] >= 6) & (target['hora'] <= 21)]
    
    # Hypothesis: 
    # Disp = Mean (All)
    # Perf = Mean (Non-Zero)
    # Qual = Mean (Non-Zero)
    
    val_disp = target['disp'].mean()
    
    perf_nonzero = target[target['perf'] > 0]
    val_perf = perf_nonzero['perf'].mean()
    
    qual_nonzero = target[target['qual'] > 0]
    val_qual = qual_nonzero['qual'].mean()
    
    oee = val_disp * val_perf * val_qual
    
    print(f"Disp (Mean All): {val_disp*100:.2f} (User: 66.77)")
    print(f"Perf (Mean >0): {val_perf*100:.2f} (User: 111.84)")
    print(f"Qual (Mean >0): {val_qual*100:.2f} (User: 100.00)")
    print(f"OEE: {oee*100:.2f} (User: 74.67)")

    # Try eliminating 'Parada' from Disponibilidade if that exists? 
    # Or maybe 'Disp' is Mean of Non-Zero too?
    val_disp_nz = target[target['disp'] > 0]['disp'].mean()
    print(f"Disp (Mean >0): {val_disp_nz*100:.2f}")

check_mixed_logic()

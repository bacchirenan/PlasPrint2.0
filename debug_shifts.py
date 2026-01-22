import pandas as pd
import numpy as np

def check_shifts():
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    
    # Extract
    data = pd.DataFrame()
    data['maquina'] = df.iloc[:, 1]
    data['data'] = df.iloc[:, 2]
    data['turno'] = df.iloc[:, 3]
    data['hora'] = df.iloc[:, 4]
    data['disp'] = df.iloc[:, 7]
    data['perf'] = df.iloc[:, 8]
    data['qual'] = df.iloc[:, 9]

    # Clean
    data = data[data['maquina'].notna()]
    data = data[~data['maquina'].astype(str).str.contains('Turno', na=False)]
    
    # Convert
    for col in ['disp', 'perf', 'qual']:
        data[col] = data[col].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
        data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0) / 100.0

    # Filter Day 21
    data['data_dt'] = pd.to_datetime(data['data'], dayfirst=True, format='mixed', errors='coerce')
    day21 = data[data['data_dt'] == '2026-01-21'].copy()
    
    # Filter 6-21
    day21 = day21[(day21['hora'] >= 6) & (day21['hora'] <= 21)]
    
    print("--- Day 21 Analysis ---")
    
    for turno_lbl, prefix in [('Turno A', '1'), ('Turno B', '2')]:
        subset = day21[day21['turno'].astype(str).str.startswith(prefix)]
        if subset.empty:
            print(f"{turno_lbl}: No data")
            continue
            
        m_disp = subset['disp'].mean()
        m_perf = subset[subset['perf'] > 0]['perf'].mean()
        m_qual = subset[subset['qual'] > 0]['qual'].mean()
        
        oee = m_disp * m_perf * m_qual * 100
        print(f"{turno_lbl}: Disp={m_disp*100:.2f}, Perf={m_perf*100:.2f}, Qual={m_qual*100:.2f} -> OEE={oee:.2f}")

    print("\n--- Full File Analysis (Average of Daily Averages?) ---")
    # Maybe the user refers to the global average over all days?
    
    data_filtered = data[(data['hora'] >= 6) & (data['hora'] <= 21)]
    
    for turno_lbl, prefix in [('Turno A', '1'), ('Turno B', '2')]:
        subset = data_filtered[data_filtered['turno'].astype(str).str.startswith(prefix)]
        
        m_disp = subset['disp'].mean()
        m_perf = subset[subset['perf'] > 0]['perf'].mean()
        m_qual = subset[subset['qual'] > 0]['qual'].mean()
        oee = m_disp * m_perf * m_qual * 100
        print(f"Global {turno_lbl}: OEE={oee:.2f}")

check_shifts()

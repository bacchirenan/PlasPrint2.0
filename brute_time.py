import pandas as pd
import numpy as np

def brute_force_time():
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    
    data = pd.DataFrame()
    data['maquina'] = df.iloc[:, 1]
    data['data'] = df.iloc[:, 2]
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
    target_all = data[(data['data_dt'] == '2026-01-21') & (data['maquina'].str.contains('28'))].copy()

    # Targets
    t_disp = 66.77
    t_perf = 111.84
    
    for start in range(0, 10):
        for end in range(18, 24):
            # Try range
            subset = target_all[(target_all['hora'] >= start) & (target_all['hora'] <= end)]
            if subset.empty: continue
            
            # Metric 1: Mean All
            d_mean = subset['disp'].mean() * 100
            
            # Metric 2: Mean Non-Zero
            p_nz = subset[subset['perf'] > 0]['perf'].mean() * 100
            
            if abs(d_mean - t_disp) < 1.0 or abs(p_nz - t_perf) < 1.0:
                print(f"Window {start}-{end}: Disp={d_mean:.2f}, Perf={p_nz:.2f}")

brute_force_time()

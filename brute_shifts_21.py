import pandas as pd
import numpy as np

def brute_day21():
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
    
    # Filter 6-21?
    day21_filt = day21[(day21['hora'] >= 6) & (day21['hora'] <= 21)]
    
    # Helper
    def try_aggs(subset, label):
        if subset.empty: return
        
        # Method 1: Mean D * Mean P * Mean Q
        m1 = subset['disp'].mean() * subset['perf'].mean() * subset['qual'].mean() * 100
        
        # Method 2: Mean D * Mean P_NZ * Mean Q_NZ
        m2 = subset['disp'].mean() * subset[subset['perf']>0]['perf'].mean() * subset[subset['qual']>0]['qual'].mean() * 100
        
        # Method 3: Average of calculated OEE (row by row)
        oee_rows = subset['disp'] * subset['perf'] * subset['qual']
        m3 = oee_rows.mean() * 100
        
        # Method 4: Median of calculated OEE
        m4 = oee_rows.median() * 100
        
        # Method 5: Mean row OEE (Non-Zero)
        m5 = oee_rows[oee_rows > 0].mean() * 100
        
        print(f"--- {label} ---")
        print(f"M1 (MeanAll*): {m1:.2f}")
        print(f"M2 (MeanNZ*): {m2:.2f}")
        print(f"M3 (MeanRows): {m3:.2f}")
        print(f"M4 (MedianRows): {m4:.2f}")
        print(f"M5 (MeanRowsNZ): {m5:.2f}")

    # Turno A (1)
    tA = day21_filt[day21_filt['turno'].astype(str).str.startswith('1')]
    try_aggs(tA, "Turno A (Filtered 6-21)")

    # Turno B (2)
    tB = day21_filt[day21_filt['turno'].astype(str).str.startswith('2')]
    try_aggs(tB, "Turno B (Filtered 6-21)")
    
    # What if no time filter?
    tA_raw = day21[day21['turno'].astype(str).str.startswith('1')]
    try_aggs(tA_raw, "Turno A (Raw)")
    
    tB_raw = day21[day21['turno'].astype(str).str.startswith('2')]
    try_aggs(tB_raw, "Turno B (Raw)")

brute_day21()

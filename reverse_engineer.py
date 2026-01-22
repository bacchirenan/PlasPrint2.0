import pandas as pd
import numpy as np

def reverse_engineer():
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

    data = data[data['maquina'].notna()]
    data = data[~data['maquina'].astype(str).str.contains('Turno', na=False)]
    
    for col in ['disp', 'perf', 'qual']:
        data[col] = data[col].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
        data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0) / 100.0

    # Day 21
    data['data_dt'] = pd.to_datetime(data['data'], dayfirst=True, format='mixed', errors='coerce')
    day21 = data[data['data_dt'] == '2026-01-21'].copy()
    
    # Filter 6-21
    day21_prod = day21[(day21['hora'] >= 6) & (day21['hora'] <= 21)].copy()
    
    # Filter Disp > 0 ???
    # day21_prod = day21_prod[day21_prod['disp'] > 0]
    
    targets = {
        'M28': 74.67,
        'M180': 56.42,
        'M181': 63.51,
        'TA': 80.32,
        'TB': 51.86
    }
    
    groups = {
        'M28': day21_prod[day21_prod['maquina'].str.contains('28')],
        'M180': day21_prod[day21_prod['maquina'].str.contains('180')],
        'M181': day21_prod[day21_prod['maquina'].str.contains('181')],
        'TA': day21_prod[day21_prod['turno'].astype(str).str.startswith('1')],
        'TB': day21_prod[day21_prod['turno'].astype(str).str.startswith('2')],
    }
    
    print("Checking 'Aggregate then Multiply' logic...")
    
    for name, subset in groups.items():
        if subset.empty: continue
        
        # Method 1: Mean then Multiply
        mean_d = subset['disp'].mean()
        mean_p = subset['perf'].mean()
        mean_q = subset['qual'].mean()
        oee_mean = mean_d * mean_p * mean_q * 100
        
        # Method 2: Median then Multiply
        med_d = subset['disp'].median()
        med_p = subset['perf'].median()
        med_q = subset['qual'].median()
        oee_med = med_d * med_p * med_q * 100

        # Method 3: Mean (Capped P) then Multiply
        p_cap = subset['perf'].clip(upper=1.0)
        mean_p_cap = p_cap.mean()
        oee_mean_cap = mean_d * mean_p_cap * mean_q * 100
        
        # Method 4: Median (Capped P) then Multiply
        med_p_cap = p_cap.median()
        oee_med_cap = med_d * med_p_cap * med_q * 100
        
        print(f"--- {name} (Target: {targets[name]}) ---")
        print(f"  Mean*Mean: {oee_mean:.2f}")
        print(f"  Med*Med: {oee_med:.2f}")
        print(f"  Mean*Mean (PerfCap): {oee_mean_cap:.2f}")
        print(f"  Med*Med (PerfCap): {oee_med_cap:.2f}")

reverse_engineer()

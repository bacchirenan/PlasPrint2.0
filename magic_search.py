import pandas as pd
import numpy as np

def solve():
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    
    # Extract
    data = pd.DataFrame()
    data['maquina'] = df.iloc[:, 1]
    data['data'] = df.iloc[:, 2]
    data['turno'] = df.iloc[:, 3]
    data['hora'] = df.iloc[:, 4]
    data['oee_sheet'] = df.iloc[:, 11]
    data['disp'] = df.iloc[:, 7]
    data['perf'] = df.iloc[:, 8]
    data['qual'] = df.iloc[:, 9]

    data = data[data['maquina'].notna()]
    data = data[~data['maquina'].astype(str).str.contains('Turno', na=False)]
    
    # Clean percentages
    for col in ['oee_sheet', 'disp', 'perf', 'qual']:
        data[col] = data[col].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
        data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0) / 100.0

    # Calc OEE
    data['oee_calc'] = data['disp'] * data['perf'] * data['qual']
    
    # Calc Capped OEE
    data['oee_capped'] = data['oee_calc'].clip(upper=1.0)
    data['perf_capped'] = data['perf'].clip(upper=1.0)
    data['oee_perf_capped'] = data['disp'] * data['perf_capped'] * data['qual']

    # Day 21
    data['data_dt'] = pd.to_datetime(data['data'], dayfirst=True, format='mixed', errors='coerce')
    day21 = data[data['data_dt'] == '2026-01-21'].copy()
    
    target_magic = 80.32
    target_maq28 = 74.67
    
    print(f"Searching for {target_magic} and {target_maq28}...")
    
    # Variants of data to check
    variants = {
        'Normal': day21['oee_calc'],
        'Sheet': day21['oee_sheet'],
        'Capped': day21['oee_capped'],
        'PerfCapped': day21['oee_perf_capped']
    }
    
    # Filters
    filters = {
        'None': day21.index,
        'OEE>0': day21[day21['oee_calc'] > 0].index,
        'OEE>1%': day21[day21['oee_calc'] > 0.01].index,
        'Disp>0': day21[day21['disp'] > 0].index,
        'Turno 1': day21[day21['turno'].astype(str).str.startswith('1')].index,
        'Turno 2': day21[day21['turno'].astype(str).str.startswith('2')].index,
        'Maq 28': day21[day21['maquina'].str.contains('28')].index,
    }
    
    for vname, vdata in variants.items():
        for fname, fidx in filters.items():
            # Apply filter
            subset = vdata.loc[fidx]
            if subset.empty: continue
            
            mean_val = subset.mean() * 100
            median_val = subset.median() * 100
            
            print(f"Checking {vname} | Filter {fname}: Mean={mean_val:.2f}, Median={median_val:.2f}")

            if abs(mean_val - target_magic) < 1.0:
                print(f"!!! CLOSE TO MAGIC 80.32: {mean_val:.2f} [{vname} - {fname} - Mean]")
            if abs(median_val - target_magic) < 1.0:
                 print(f"!!! CLOSE TO MAGIC 80.32: {median_val:.2f} [{vname} - {fname} - Median]")

            if abs(mean_val - target_maq28) < 1.0:
                print(f"!!! CLOSE TO MAQ28 74.67: {mean_val:.2f} [{vname} - {fname} - Mean]")

solve()

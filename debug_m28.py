import pandas as pd
import numpy as np

def check_m28():
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
    
    # Convert
    for col in ['disp', 'perf', 'qual']:
        data[col] = data[col].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
        data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0) / 100.0

    # Filter Day 21, Maq 28
    data['data_dt'] = pd.to_datetime(data['data'], dayfirst=True, format='mixed', errors='coerce')
    target = data[(data['data_dt'] == '2026-01-21') & (data['maquina'].str.contains('28'))].copy()
    
    # Filter 6-21
    target = target[(target['hora'] >= 6) & (target['hora'] <= 21)]

    print("--- RAW VALUES (Maq 28, Day 21, 6-21h) ---")
    print(target[['hora', 'disp', 'perf', 'qual']].to_string())
    
    print("\n--- AGGREGATION (Mean) ---")
    mean_d = target['disp'].mean()
    mean_p = target['perf'].mean()
    mean_q = target['qual'].mean()
    print(f"Mean Disp: {mean_d*100:.2f}")
    print(f"Mean Perf: {mean_p*100:.2f}")
    print(f"Mean Qual: {mean_q*100:.2f}")
    print(f"Calc OEE (Mean*Mean*Mean): {mean_d * mean_p * mean_q * 100:.2f}")

    print("\n--- AGGREGATION (Median) ---")
    med_d = target['disp'].median()
    med_p = target['perf'].median()
    med_q = target['qual'].median()
    print(f"Median Disp: {med_d*100:.2f}")
    print(f"Median Perf: {med_p*100:.2f}")
    print(f"Median Qual: {med_q*100:.2f}")
    print(f"Calc OEE (Med*Med*Med): {med_d * med_p * med_q * 100:.2f}")

check_m28()

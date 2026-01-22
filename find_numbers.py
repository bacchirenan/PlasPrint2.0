import pandas as pd
import numpy as np

def find_numbers():
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    
    # Extract
    data = pd.DataFrame()
    data['maquina'] = df.iloc[:, 1]
    data['data'] = df.iloc[:, 2]
    data['oee_sheet'] = df.iloc[:, 11]
    data['disp'] = df.iloc[:, 7]
    data['perf'] = df.iloc[:, 8]
    data['qual'] = df.iloc[:, 9]

    # Convert
    for col in ['oee_sheet', 'disp', 'perf', 'qual']:
        data[col] = data[col].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
        data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)
    
    # Calculate
    data['oee_calc'] = (data['disp'] * data['perf'] * data['qual'] / 10000.0) * 100 # Adjust scale
    
    # Search targets
    targets = [74.67, 56.42, 63.51, 80.32, 51.86]
    
    print("Searching for exact matches in raw data...")
    for t in targets:
        # Check Sheet OEE
        matches = data[abs(data['oee_sheet'] - t) < 0.05]
        if not matches.empty:
            print(f"FOUND {t} in OEE_SHEET:")
            print(matches[['maquina', 'data', 'oee_sheet']].head().to_string())
            
        # Check Calc OEE
        matches_calc = data[abs(data['oee_calc'] - t) < 0.05]
        if not matches_calc.empty:
            print(f"FOUND {t} in OEE_CALC:")
            print(matches_calc[['maquina', 'data', 'oee_sheet', 'oee_calc']].head().to_string())

find_numbers()

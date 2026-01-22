import pandas as pd

def find_all():
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    
    # Extract
    data = pd.DataFrame()
    data['maquina'] = df.iloc[:, 1]
    data['data'] = df.iloc[:, 2]
    data['oee'] = df.iloc[:, 11]
    
    data = data[data['maquina'].notna()]
    data['oee'] = data['oee'].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
    data['oee'] = pd.to_numeric(data['oee'], errors='coerce').fillna(0)
    
    targets = [74.67, 56.42, 63.51, 80.32, 51.86]
    
    print("Searching entire file...")
    for t in targets:
        match = data[abs(data['oee'] - t) < 0.1]
        if not match.empty:
            print(f"--- Found {t} ---")
            print(match.head().to_string())

find_all()

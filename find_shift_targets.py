import pandas as pd

def find_targets():
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    
    data = pd.DataFrame()
    data['maquina'] = df.iloc[:, 1]
    data['data'] = df.iloc[:, 2]
    data['turno'] = df.iloc[:, 3]
    data['oee_sheet'] = df.iloc[:, 11]
    data['disp'] = df.iloc[:, 7]
    data['perf'] = df.iloc[:, 8]
    data['qual'] = df.iloc[:, 9]

    # Convert
    for col in ['oee_sheet', 'disp', 'perf', 'qual']:
        data[col] = data[col].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
        data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)
    
    data['oee_calc'] = (data['disp']/100) * (data['perf']/100) * (data['qual']/100) * 100
    
    targets = [73.08, 72.70]
    
    print("--- Searching Raw Data ---")
    for t in targets:
        # Check sheet
        match = data[abs(data['oee_sheet'] - t) < 0.1]
        if not match.empty:
            print(f"Found {t} in Sheet OEE:")
            print(match.head().to_string())
            
        # Check calc
        match_c = data[abs(data['oee_calc'] - t) < 0.1]
        if not match_c.empty:
            print(f"Found {t} in Calc OEE:")
            print(match_c.head().to_string())
            
    # Check Aggregations by Turno
    print("\n--- Checking Aggregations ---")
    # Group by Turno
    grp = data.groupby('turno')
    
    # Mean of OEE Sheet
    print("Mean of Sheet OEE:")
    print(grp['oee_sheet'].mean())
    
    # Median of Sheet OEE
    print("Median of Sheet OEE:")
    print(grp['oee_sheet'].median())
    
    # Mean of Calc OEE
    print("Mean of Calc OEE:")
    print(grp['oee_calc'].mean())

find_targets()

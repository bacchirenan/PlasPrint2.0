import pandas as pd
import numpy as np

def solve_oee_mystery():
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    
    # Extract Columns
    data = pd.DataFrame()
    data['maquina'] = df.iloc[:, 1]
    data['data'] = df.iloc[:, 2]
    data['turno'] = df.iloc[:, 3]
    data['hora'] = df.iloc[:, 4]
    data['disp'] = df.iloc[:, 7]
    data['perf'] = df.iloc[:, 8]
    data['qual'] = df.iloc[:, 9]
    
    # Cleaning
    data = data[data['maquina'].notna()]
    data = data[~data['maquina'].astype(str).str.contains('Turno', na=False)]
    
    # Convert Percentages
    for col in ['disp', 'perf', 'qual']:
        data[col] = data[col].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
        data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0) / 100.0
        
    data['oee'] = data['disp'] * data['perf'] * data['qual']
    
    # Filter Day 21
    data['data_dt'] = pd.to_datetime(data['data'], dayfirst=True, format='mixed', errors='coerce')
    day21 = data[data['data_dt'] == '2026-01-21'].copy()
    
    # Define Targets
    target_maq_28 = 74.67
    target_maq_180 = 56.42
    target_maq_181 = 63.51
    target_turno_a = 80.32
    target_turno_b = 51.86
    
    # Helper to check match
    def check(val, target, tol=1.0):
        return abs(val*100 - target) < tol

    print("--- Searching for matching logic ---")
    
    # Strategies
    # Time Filters
    times = [
        (6, 21), (6, 22), (0, 23), (6, 14), (14, 22), (7, 21)
    ]
    
    # Exclusions
    exclusions = [
        ("None", lambda x: x),
        ("OEE > 0", lambda x: x[x['oee'] > 0]),
        ("Disp > 0", lambda x: x[x['disp'] > 0]),
        ("OEE > 1%", lambda x: x[x['oee'] > 0.01]),
        ("No Machine 29", lambda x: x[~x['maquina'].str.contains('29')]),
    ]
    
    # Aggregations
    aggs = [
        ("Mean", np.mean),
        ("Median", np.median)
    ]
    
    for start, end in times:
        time_slice = day21[(day21['hora'] >= start) & (day21['hora'] <= end)]
        
        for exc_name, exc_func in exclusions:
            filtered = exc_func(time_slice)
            
            if filtered.empty: continue
            
            for agg_name, agg_func in aggs:
                # Calculate metrics
                try:
                    # Per Machine
                    m28 = agg_func(filtered[filtered['maquina'].str.contains('28')]['oee'])
                    m180 = agg_func(filtered[filtered['maquina'].str.contains('180')]['oee'])
                    m181 = agg_func(filtered[filtered['maquina'].str.contains('181')]['oee'])
                    
                    # Per Turno
                    # Map turnos
                    def map_t(v):
                        s = str(v).split('.')[0]
                        return 'A' if s=='1' else ('B' if s=='2' else 'C')
                    filtered['turno_lbl'] = filtered['turno'].apply(map_t)
                    
                    tA = agg_func(filtered[filtered['turno_lbl'] == 'A']['oee'])
                    tB = agg_func(filtered[filtered['turno_lbl'] == 'B']['oee'])
                    
                    # Check matches
                    matches = []
                    if check(m28, target_maq_28): matches.append("M28")
                    if check(m180, target_maq_180): matches.append("M180")
                    if check(m181, target_maq_181): matches.append("M181")
                    if check(tA, target_turno_a): matches.append("TurnoA")
                    if check(tB, target_turno_b): matches.append("TurnoB")
                    
                    if len(matches) > 1:
                        print(f"MATCH FOUND! [{start}-{end}] [{exc_name}] [{agg_name}]")
                        print(f"  Matches: {matches}")
                        print(f"  Vals: M28={m28*100:.2f}, M180={m180*100:.2f}, M181={m181*100:.2f}")
                        print(f"  TurnoA={tA*100:.2f}, TurnoB={tB*100:.2f}")
                        print("-" * 30)
                        
                except Exception as e:
                    pass

solve_oee_mystery()

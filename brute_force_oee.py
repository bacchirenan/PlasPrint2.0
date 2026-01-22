import pandas as pd
import itertools

def solve():
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    
    # Extract
    data = pd.DataFrame()
    data['maquina'] = df.iloc[:, 1]
    data['data'] = df.iloc[:, 2]
    data['turno'] = df.iloc[:, 3]
    data['hora'] = df.iloc[:, 4]
    data['oee_sheet'] = df.iloc[:, 11] # Use Sheet OEE first
    data['disp'] = df.iloc[:, 7]
    data['perf'] = df.iloc[:, 8]
    data['qual'] = df.iloc[:, 9]

    # Clean
    data = data[data['maquina'].notna()]
    data = data[~data['maquina'].astype(str).str.contains('Turno', na=False)]
    
    # Convert
    for col in ['oee_sheet', 'disp', 'perf', 'qual']:
        data[col] = data[col].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
        data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0) / 100.0

    data['oee_calc'] = data['disp'] * data['perf'] * data['qual']

    # Filter Day
    data['data_dt'] = pd.to_datetime(data['data'], dayfirst=True, format='mixed', errors='coerce')
    day21 = data[data['data_dt'] == '2026-01-21'].copy()
    
    targets = {
        'M28': 74.67,
        'M180': 56.42,
        'M181': 63.51,
        'TA': 80.32,
        'TB': 51.86
    }
    
    # Generate subsets of data to test aggregations on
    # Filters to try
    filters = {
        'All': lambda x: x,
        'OEE>0': lambda x: x[x['oee_calc'] > 0],
        'Disp>0': lambda x: x[x['disp'] > 0],
        'Hora 6-21': lambda x: x[(x['hora']>=6)&(x['hora']<=21)],
        'Hora 6-13': lambda x: x[(x['hora']>=6)&(x['hora']<=13)],
        'Hora 14-22': lambda x: x[(x['hora']>=14)&(x['hora']<=22)],
    }
    
    # Groups
    machines = {
        'M28': lambda x: x[x['maquina'].astype(str).str.contains('28')],
        'M180': lambda x: x[x['maquina'].astype(str).str.contains('180')],
        'M181': lambda x: x[x['maquina'].astype(str).str.contains('181')],
    }
    
    turnos = {
        'TA': lambda x: x[x['turno'].astype(str).str.startswith('1')],
        'TB': lambda x: x[x['turno'].astype(str).str.startswith('2')],
    }
    
    # Value sources
    sources = ['oee_sheet', 'oee_calc']
    
    # Aggregations
    aggs = ['mean', 'median']

    print("Starting brute force...")
    
    for fname, ffunc in filters.items():
        subset = ffunc(day21)
        if subset.empty: continue
        
        for src in sources:
            for agg in aggs:
                
                # Check Machines
                for mname, mfunc in machines.items():
                    target = targets[mname]
                    msub = mfunc(subset)
                    if msub.empty: continue
                    val = getattr(msub[src], agg)() * 100
                    if abs(val - target) < 0.1:
                        print(f"MATCH {mname}: {val:.2f} | Filter: {fname} | Source: {src} | Agg: {agg}")

                # Check Turnos
                for tname, tfunc in turnos.items():
                    target = targets[tname]
                    tsub = tfunc(subset)
                    if tsub.empty: continue
                    val = getattr(tsub[src], agg)() * 100
                    if abs(val - target) < 0.1:
                        print(f"MATCH {tname}: {val:.2f} | Filter: {fname} | Source: {src} | Agg: {agg}")

solve()

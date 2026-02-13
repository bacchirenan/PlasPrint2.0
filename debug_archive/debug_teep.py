
import pandas as pd
import numpy as np

try:
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    
    # Mapeamento
    # C (2): Data
    # D (3): Turno
    # E (4): Hora
    # H (7): Disp
    # I (8): Perf
    # J (9): Qual
    
    new_df = pd.DataFrame()
    new_df['maquina'] = df.iloc[:, 1]
    new_df['data'] = df.iloc[:, 2]
    new_df['turno'] = df.iloc[:, 3]
    new_df['hora'] = df.iloc[:, 4]
    new_df['disponibilidade'] = df.iloc[:, 7]
    new_df['performance'] = df.iloc[:, 8]
    new_df['qualidade'] = df.iloc[:, 9]
    
    # Filtrar Maquina
    new_df = new_df[new_df['maquina'].notna()]
    new_df = new_df[~new_df['maquina'].astype(str).str.contains('Turno', na=False)]
    new_df = new_df[new_df['data'].notna()]
    
    # Convert pct
    pct_cols = ['disponibilidade', 'performance', 'qualidade']
    for col in pct_cols:
        new_df[col] = new_df[col].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
        new_df[col] = pd.to_numeric(new_df[col], errors='coerce').fillna(0) / 100.0
        
    # Calc OEE
    new_df['oee'] = (new_df['disponibilidade'] * new_df['performance'] * new_df['qualidade'])
    
    # Convert Data using mixed format to handle various possibilities
    new_df['data'] = pd.to_datetime(new_df['data'], dayfirst=True, format='mixed', errors='coerce')
    
    # Filter 01/02 to 11/02 (Feb 1st to Feb 11th 2026)
    # The file likely contains 2026 data based on context
    start_date = pd.Timestamp('2026-02-01')
    end_date = pd.Timestamp('2026-02-11')
    
    mask_date = (new_df['data'] >= start_date) & (new_df['data'] <= end_date)
    filtered = new_df[mask_date].copy()
    
    print(f"Total rows filtered (All shifts): {len(filtered)}")
    
    # Current Filter Logic in App:
    # 1. Rename Shifts
    def rename_shift(val):
        val_str = str(val).split('.')[0]
        if val_str == '1': return 'Turno A'
        if val_str == '2': return 'Turno B'
        return None
    
    filtered['turno_lbl'] = filtered['turno'].apply(rename_shift)
    filtered = filtered[filtered['turno_lbl'].isin(['Turno A', 'Turno B'])]
    print(f"Rows after Shift Filter (A, B): {len(filtered)}")
    
    # 2. Filter Hour >= 6 <= 21
    filtered['hora'] = pd.to_numeric(filtered['hora'], errors='coerce')
    filtered = filtered[(filtered['hora'] >= 6) & (filtered['hora'] <= 21)]
    print(f"Rows after Hour Filter (6-21): {len(filtered)}")
    
    # 3. Global Activity Filter
    global_activity = filtered.groupby(['data', 'hora'])['oee'].sum().reset_index()
    active_slots = global_activity[global_activity['oee'] > 0][['data', 'hora']]
    final_df = filtered.merge(active_slots, on=['data', 'hora'], how='inner')
    print(f"Rows after Global Activity Filter: {len(final_df)}")
    
    # Stats
    avg_oee = final_df['oee'].mean()
    print(f"Average OEE (calculated): {avg_oee:.4f} ({avg_oee*100:.2f}%)")
    
    # TEEP Current Formula
    teep_curr = avg_oee * (16/24)
    print(f"TEEP Current (OEE * 16/24): {teep_curr:.4f} ({teep_curr*100:.2f}%)")
    
    # Check if raw OEE is higher without Global Activity Filter or Hours
    no_filter_df = new_df[mask_date].copy() # Still all shifts? No, usually TEEP is 24/7 or scheduled? 
    # User said "Tempo programado 16h / Tempo Total 24h".
    # If using ALL shifts (A, B, C) and just averaging OEE, maybe?
    
    avg_oee_all = no_filter_df['oee'].mean()
    print(f"Average OEE (All Shifts, No Filters): {avg_oee_all:.4f}")
    
    # Try Filter A+B but no hours
    ab_df = new_df[mask_date].copy()
    ab_df['turno_lbl'] = ab_df['turno'].apply(rename_shift)
    ab_df = ab_df[ab_df['turno_lbl'].isin(['Turno A', 'Turno B'])]
    avg_oee_ab = ab_df['oee'].mean()
    print(f"Average OEE (Shift A+B, No Hour Filter): {avg_oee_ab:.4f}")
    
    # Target TEEP is 41.65%
    # Target OEE implied by TEEP = OEE * 16/24 => OEE = 0.4165 * 1.5 = 0.62475
    
    print("\n--- Diagnostic ---")
    print(f"Target TEEP: 41.65%")
    print(f"Implied OEE (if Factor=0.66): 62.48%")
    print(f"My Calculated OEE: {avg_oee*100:.2f}%")
    
    # Check if we sum production or average? OEE is usually weighted by time or generic average. 
    # Here we do simple mean of rows (machines x hours).
    
except Exception as e:
    print(e)

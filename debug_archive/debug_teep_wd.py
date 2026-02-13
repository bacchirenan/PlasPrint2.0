
import pandas as pd

try:
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    
    # Columns
    new_df = pd.DataFrame()
    new_df['data'] = df.iloc[:, 2]
    new_df['turno'] = df.iloc[:, 3]
    new_df['hora'] = df.iloc[:, 4]
    new_df['maquina'] = df.iloc[:, 1]
    
    # Pct cols
    cols = ['disponibilidade', 'performance', 'qualidade']
    new_df['disponibilidade'] = df.iloc[:, 7]
    new_df['performance'] = df.iloc[:, 8]
    new_df['qualidade'] = df.iloc[:, 9]
    
    for col in cols:
        new_df[col] = new_df[col].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
        new_df[col] = pd.to_numeric(new_df[col], errors='coerce').fillna(0) / 100.0

    new_df['oee'] = new_df['disponibilidade'] * new_df['performance'] * new_df['qualidade']

    new_df['data'] = pd.to_datetime(new_df['data'], dayfirst=True, format='mixed', errors='coerce')
    
    start_date = pd.Timestamp('2026-02-01')
    end_date = pd.Timestamp('2026-02-11')
    
    mask = (new_df['data'] >= start_date) & (new_df['data'] <= end_date)
    filtered = new_df[mask].copy()
    
    # Filter Weekend
    # Dayofweek: 0=Mon, 6=Sun
    # Exclude Sat(5) and Sun(6)
    filtered['dow'] = filtered['data'].dt.dayofweek
    workdays = filtered[~filtered['dow'].isin([5, 6])]
    
    print(f"Avg OEE (All Days): {filtered['oee'].mean()*100:.2f}%")
    print(f"Avg OEE (Workdays Only): {workdays['oee'].mean()*100:.2f}%")
    
    # Check Shift Filter on Workdays
    def rename_shift(val):
        val_str = str(val).split('.')[0]
        if val_str == '1': return 'Turno A'
        if val_str == '2': return 'Turno B'
        return None
    
    workdays['tlabel'] = workdays['turno'].apply(rename_shift)
    wd_shifts = workdays[workdays['tlabel'].isin(['Turno A', 'Turno B'])]
    
    # Hour Filter
    wd_shifts['hora'] = pd.to_numeric(wd_shifts['hora'], errors='coerce')
    wd_shifts = wd_shifts[(wd_shifts['hora'] >= 6) & (wd_shifts['hora'] <= 21)]
    
    print(f"Avg OEE (Workdays + Shift A/B + Hours 6-21): {wd_shifts['oee'].mean()*100:.2f}%")
    
    # Calc TEEP with this OEE
    teep_wd = wd_shifts['oee'].mean() * (16/24)
    print(f"TEEP (Workdays OEE * 16/24): {teep_wd*100:.2f}%")

except Exception as e:
    print(e)

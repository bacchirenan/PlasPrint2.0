
import pandas as pd

try:
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    
    new_df = pd.DataFrame()
    cols = ['disponibilidade', 'performance', 'qualidade', 'teep', 'oee']
    # Indices: Disp=7, Perf=8, Qual=9, TEEP=10, OEE=11
    indices = [7, 8, 9, 10, 11]
    
    for c, i in zip(cols, indices):
        new_df[c] = df.iloc[:, i].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
        new_df[c] = pd.to_numeric(new_df[c], errors='coerce').fillna(0) / 100.0

    new_df['data'] = pd.to_datetime(df.iloc[:, 2], dayfirst=True, format='mixed', errors='coerce')
    new_df['turno'] = df.iloc[:, 3]
    new_df['hora'] = pd.to_numeric(df.iloc[:, 4], errors='coerce')
    
    start_date = pd.Timestamp('2026-02-01')
    end_date = pd.Timestamp('2026-02-11')
    
    mask = (new_df['data'] >= start_date) & (new_df['data'] <= end_date)
    filtered = new_df[mask].copy()
    
    # Filter Shift/Hour (16h window)
    def rename_shift(val):
        val_str = str(val).split('.')[0]
        if val_str == '1': return 'Turno A'
        if val_str == '2': return 'Turno B'
        return None
    
    filtered['tlbl'] = filtered['turno'].apply(rename_shift)
    
    # Filter for A and B
    f_ab = filtered[filtered['tlbl'].isin(['Turno A', 'Turno B'])]
    f_ab = f_ab[(f_ab['hora'] >= 6) & (f_ab['hora'] <= 21)]
    
    print(f"Total rows (Filtered): {len(f_ab)}")
    
    # Avg OEE (including zeros)
    print(f"Avg OEE (All): {f_ab['oee'].mean()*100:.2f}%")
    
    # Avg OEE (Excluding Zeros)
    non_zero = f_ab[f_ab['oee'] > 0]
    print(f"Avg OEE (Non-Zero): {non_zero['oee'].mean()*100:.2f}%")
    print(f"Non-Zero Count: {len(non_zero)}")
    
    # Calculate TEEP from Non-Zero OEE
    teep_nz = non_zero['oee'].mean() * (16/24)
    print(f"TEEP (Non-Zero OEE * 16/24): {teep_nz*100:.2f}%")
    
    # Try excluding rows where Availability is 0?
    non_zero_avail = f_ab[f_ab['disponibilidade'] > 0]
    print(f"Avg OEE (Avail > 0): {non_zero_avail['oee'].mean()*100:.2f}%")
    
    # Maybe filtering logic for "Utilizacao" is 16/24 = 0.666
    # If the user says TEEP is 41.65%.
    
except Exception as e:
    print(e)

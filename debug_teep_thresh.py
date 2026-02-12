
import pandas as pd
import numpy as np

try:
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    
    new_df = pd.DataFrame()
    cols = ['disponibilidade', 'performance', 'qualidade', 'teep', 'oee']
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
    f_ab = filtered[filtered['tlbl'].isin(['Turno A', 'Turno B'])]
    f_ab = f_ab[(f_ab['hora'] >= 6) & (f_ab['hora'] <= 21)]
    
    # Target OEE = 62.47% (approx) because 62.47 * (16/24) = 41.65
    target_oee = 0.6247
    
    print(f"Base OEE: {f_ab['oee'].mean()*100:.2f}%")
    
    # Iterate thresholds
    for thresh in np.arange(0, 0.5, 0.05):
        # Filter rows where Avail > thresh
        sub = f_ab[f_ab['disponibilidade'] > thresh]
        mean_oee = sub['oee'].mean()
        diff = abs(mean_oee - target_oee)
        print(f"Filter Avail > {thresh:.2f}: OEE = {mean_oee*100:.2f}%, Diff: {diff*100:.2f}%")
        
    for thresh in np.arange(0, 0.5, 0.05):
        # Filter rows where OEE > thresh
        sub = f_ab[f_ab['oee'] > thresh]
        mean_oee = sub['oee'].mean()
        diff = abs(mean_oee - target_oee)
        print(f"Filter OEE > {thresh:.2f}: OEE = {mean_oee*100:.2f}%, Diff: {diff*100:.2f}%")

except Exception as e:
    print(e)

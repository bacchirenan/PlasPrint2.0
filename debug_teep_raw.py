
import pandas as pd
import numpy as np

try:
    # Read including header row to get column names correctly if needed, but we know indices.
    # Skiprows=1.
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    
    new_df = pd.DataFrame()
    new_df['data'] = df.iloc[:, 2]
    new_df['turno'] = df.iloc[:, 3]
    new_df['hora'] = df.iloc[:, 4]
    
    # Raw columns from file
    new_df['teep_file'] = df.iloc[:, 10]
    new_df['oee_file'] = df.iloc[:, 11]
    
    # Cleaning
    cols = ['teep_file', 'oee_file']
    for col in cols:
        new_df[col] = new_df[col].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
        new_df[col] = pd.to_numeric(new_df[col], errors='coerce') # Keep as 0-100 for now or /100
        new_df[col] = new_df[col] / 100.0

    new_df['data'] = pd.to_datetime(new_df['data'], dayfirst=True, format='mixed', errors='coerce')
    
    start_date = pd.Timestamp('2026-02-01')
    end_date = pd.Timestamp('2026-02-11')
    
    mask = (new_df['data'] >= start_date) & (new_df['data'] <= end_date)
    filtered = new_df[mask].copy()
    
    print(f"Stats for period {start_date.date()} to {end_date.date()}")
    print(f"Count: {len(filtered)}")
    print(f"Avg TEEP (File): {filtered['teep_file'].mean()*100:.4f}%")
    print(f"Avg OEE (File): {filtered['oee_file'].mean()*100:.4f}%")
    
    # Check if filtering by shift/hour changes it
    # Turno 1/2
    def clean_shift(x):
        s = str(x).split('.')[0]
        if s in ['1', '2']: return True
        return False
        
    filtered['valid_shift'] = filtered['turno'].apply(clean_shift)
    f_shift = filtered[filtered['valid_shift']]
    
    print(f"Avg TEEP (File, Shift 1+2 only): {f_shift['teep_file'].mean()*100:.4f}%")
    print(f"Avg OEE (File, Shift 1+2 only): {f_shift['oee_file'].mean()*100:.4f}%")

    # Avg OEE * (16/24)
    implied_teep = f_shift['oee_file'].mean() * (16/24)
    print(f"Calc TEEP from File OEE * (16/24): {implied_teep*100:.4f}%")

except Exception as e:
    print(e)

import pandas as pd
import os
import datetime

file_path = 'oee teep.xlsx'
try:
    # Check file stats
    stats = os.stat(file_path)
    mod_time = datetime.datetime.fromtimestamp(stats.st_mtime)
    print(f"File: {file_path}")
    print(f"Last Modified: {mod_time}")
    
    # Check sheet names
    xl = pd.ExcelFile(file_path)
    print(f"Sheet names: {xl.sheet_names}")
    
    # Check machines in all sheets if multiple
    for sheet in xl.sheet_names:
        print(f"\n--- Sheet: {sheet} ---")
        df = pd.read_excel(file_path, sheet_name=sheet, skiprows=1)
        if df.shape[1] > 1:
            machines = df.iloc[:, 1].dropna().unique()
            print("Machines found:", machines)
        else:
            print("Sheet has less than 2 columns.")

except Exception as e:
    print(f"Error: {e}")

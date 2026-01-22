import pandas as pd
df = pd.read_excel('oee teep.xlsx', skiprows=1)
day21 = df[pd.to_datetime(df.iloc[:, 2], dayfirst=True, format='mixed', errors='coerce').dt.strftime('%Y-%m-%d') == '2026-01-21']
print(day21.iloc[:, [1, 2, 3, 4, 6, 7, 8, 9, 11]].head(30).to_string())

import pandas as pd
df = pd.read_excel('oee teep.xlsx', skiprows=1)
# Clean
data = pd.DataFrame()
data['maquina'] = df.iloc[:, 1]
data['data'] = df.iloc[:, 2]
data['turno'] = df.iloc[:, 3]
data['hora'] = df.iloc[:, 4]
data['disp'] = df.iloc[:, 7]
data['perf'] = df.iloc[:, 8]
data['qual'] = df.iloc[:, 9]

data = data[data['maquina'].notna()]
data = data[~data['maquina'].astype(str).str.contains('Turno', na=False)]
data['data_dt'] = pd.to_datetime(data['data'], dayfirst=True, format='mixed', errors='coerce')

# Filter Day 21 and Maq 181
day21_181 = data[(data['data_dt'] == '2026-01-21') & (data['maquina'].str.contains('181'))].copy()

# Calc OEE
for col in ['disp', 'perf', 'qual']:
    day21_181[col] = day21_181[col].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
    day21_181[col] = pd.to_numeric(day21_181[col], errors='coerce').fillna(0) / 100.0

day21_181['oee'] = day21_181['disp'] * day21_181['perf'] * day21_181['qual']

print("--- Dump 181 ---")
print(day21_181[['hora', 'disp', 'perf', 'qual', 'oee']].to_string())
print("Mean:", day21_181['oee'].mean())
print("Mean (OEE>0):", day21_181[day21_181['oee'] > 0]['oee'].mean())
print("Mean (6-21):", day21_181[(day21_181['hora'] >= 6) & (day21_181['hora'] <= 21)]['oee'].mean())

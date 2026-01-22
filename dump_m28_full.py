import pandas as pd
df = pd.read_excel('oee teep.xlsx', skiprows=1)
# Clean
data = pd.DataFrame()
data['maquina'] = df.iloc[:, 1]
data['data'] = df.iloc[:, 2]
data['hora'] = df.iloc[:, 4]
data['disp'] = df.iloc[:, 7]
data['perf'] = df.iloc[:, 8]
data['qual'] = df.iloc[:, 9]

data = data[data['maquina'].notna()]
data = data[~data['maquina'].astype(str).str.contains('Turno', na=False)]

data['data_dt'] = pd.to_datetime(data['data'], dayfirst=True, format='mixed', errors='coerce')

target = data[(data['data_dt'] == '2026-01-21') & (data['maquina'].str.contains('28'))].copy()

# Convert to float
for col in ['disp', 'perf', 'qual']:
    target[col] = target[col].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
    target[col] = pd.to_numeric(target[col], errors='coerce').fillna(0) / 100.0

print(target[['hora', 'disp', 'perf', 'qual']].sort_values('hora').to_string())

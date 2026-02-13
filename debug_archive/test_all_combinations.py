import pandas as pd
import numpy as np

df = pd.read_excel('oee teep.xlsx', skiprows=1)

new_df = pd.DataFrame()
new_df['maquina'] = df.iloc[:, 1]
new_df['data'] = df.iloc[:, 2]
new_df['turno'] = df.iloc[:, 3]
new_df['hora'] = df.iloc[:, 4]
new_df['teep'] = df.iloc[:, 10]
new_df['oee'] = df.iloc[:, 11]

new_df = new_df[new_df['maquina'].notna()]
new_df = new_df[~new_df['maquina'].astype(str).str.contains('Turno', na=False)]
new_df = new_df[new_df['data'].notna()]

for col in ['teep', 'oee']:
    new_df[col] = new_df[col].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
    new_df[col] = pd.to_numeric(new_df[col], errors='coerce').fillna(0) / 100.0

new_df['data'] = pd.to_datetime(new_df['data'], dayfirst=True, format='mixed', errors='coerce')
new_df = new_df.dropna(subset=['data'])

def rename_shift(val):
    val_str = str(val).split('.')[0]
    if val_str == '1': return 'Turno A'
    if val_str == '2': return 'Turno B'
    return None

new_df['turno'] = new_df['turno'].apply(rename_shift)
new_df = new_df[new_df['turno'].isin(['Turno A', 'Turno B'])]

new_df['hora'] = pd.to_numeric(new_df['hora'], errors='coerce')
new_df = new_df[(new_df['hora'] >= 6) & (new_df['hora'] <= 21)]

# Filtrar período
mask = (new_df['data'] >= '2026-02-01') & (new_df['data'] <= '2026-02-11')
filtered = new_df[mask]

print("=" * 80)
print("TESTANDO TODAS AS COMBINACOES POSSIVEIS")
print("=" * 80)

# Teste 1: Todos os dias + filtro de horas ativas
global_activity = filtered.groupby(['data', 'hora'])['oee'].sum().reset_index()
active_hours = global_activity[global_activity['oee'] > 0][['data', 'hora']]
test1 = filtered.merge(active_hours, on=['data', 'hora'], how='inner')
print(f"\n1. Todos os dias + filtro horas ativas:")
print(f"   TEEP: {test1['teep'].mean()*100:.2f}%")

# Teste 2: Todos os dias SEM filtro de horas ativas
test2 = filtered
print(f"\n2. Todos os dias SEM filtro horas ativas:")
print(f"   TEEP: {test2['teep'].mean()*100:.2f}%")

# Teste 3: Apenas dias úteis + filtro de horas ativas
weekdays = filtered[filtered['data'].dt.dayofweek < 5]
global_activity_wd = weekdays.groupby(['data', 'hora'])['oee'].sum().reset_index()
active_hours_wd = global_activity_wd[global_activity_wd['oee'] > 0][['data', 'hora']]
test3 = weekdays.merge(active_hours_wd, on=['data', 'hora'], how='inner')
print(f"\n3. Apenas dias uteis + filtro horas ativas:")
print(f"   TEEP: {test3['teep'].mean()*100:.2f}%")

# Teste 4: Apenas dias úteis SEM filtro de horas ativas
test4 = weekdays
print(f"\n4. Apenas dias uteis SEM filtro horas ativas:")
print(f"   TEEP: {test4['teep'].mean()*100:.2f}%")

# Teste 5: Incluindo sábado mas excluindo domingo
weekdays_sat = filtered[filtered['data'].dt.dayofweek < 6]  # 0-5 = Segunda a Sábado
global_activity_sat = weekdays_sat.groupby(['data', 'hora'])['oee'].sum().reset_index()
active_hours_sat = global_activity_sat[global_activity_sat['oee'] > 0][['data', 'hora']]
test5 = weekdays_sat.merge(active_hours_sat, on=['data', 'hora'], how='inner')
print(f"\n5. Segunda a Sabado + filtro horas ativas:")
print(f"   TEEP: {test5['teep'].mean()*100:.2f}%")

# Teste 6: Segunda a Sábado SEM filtro
test6 = weekdays_sat
print(f"\n6. Segunda a Sabado SEM filtro horas ativas:")
print(f"   TEEP: {test6['teep'].mean()*100:.2f}%")

print("\n" + "=" * 80)
print("RESUMO - QUAL ESTA MAIS PROXIMO DE 41.65%?")
print("=" * 80)

target = 41.65
tests = {
    '1. Todos + filtro ativo': test1['teep'].mean()*100,
    '2. Todos sem filtro': test2['teep'].mean()*100,
    '3. Dias uteis + filtro': test3['teep'].mean()*100,
    '4. Dias uteis sem filtro': test4['teep'].mean()*100,
    '5. Seg-Sab + filtro': test5['teep'].mean()*100,
    '6. Seg-Sab sem filtro': test6['teep'].mean()*100,
}

for name, value in tests.items():
    diff = abs(target - value)
    status = "<<<" if diff < 0.5 else ""
    print(f"{name:30} {value:6.2f}%  (diff: {diff:4.2f}) {status}")

closest = min(tests.items(), key=lambda x: abs(x[1] - target))
print(f"\nMais proximo: {closest[0]} = {closest[1]:.2f}%")
print(f"Diferenca: {abs(closest[1] - target):.2f} pontos percentuais")

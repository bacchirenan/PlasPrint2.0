import pandas as pd
import numpy as np

def load_oee_data():
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
    
    new_df = new_df[new_df['data'].dt.dayofweek < 5]
    
    return new_df

print("=" * 80)
print("INVESTIGANDO DIA 10/02 - TURNO B")
print("=" * 80)

df_oee = load_oee_data()

# Filtrar 10/02
data_10 = df_oee[df_oee['data'] == '2026-02-10']

print("\nDia 10/02 - ANTES do filtro de horas ativas:")
print(f"Total de registros: {len(data_10)}")

for turno in ['Turno A', 'Turno B']:
    turno_data = data_10[data_10['turno'] == turno]
    print(f"\n{turno}:")
    print(f"  Registros: {len(turno_data)}")
    print(f"  Maquinas: {sorted(turno_data['maquina'].unique())}")
    print(f"  Horas: {sorted(turno_data['hora'].unique())}")
    
    # Ver quais horas têm OEE = 0
    zero_hours = turno_data[turno_data['oee'] == 0]
    if len(zero_hours) > 0:
        print(f"  Horas com OEE=0: {sorted(zero_hours['hora'].unique())}")

# Aplicar filtro de horas ativas
print("\n" + "=" * 80)
print("APLICANDO FILTRO DE HORAS ATIVAS")
print("=" * 80)

global_activity = data_10.groupby(['hora'])['oee'].sum().reset_index()
print("\nAtividade global por hora (soma de OEE de todas as maquinas):")
for _, row in global_activity.iterrows():
    status = "ATIVA" if row['oee'] > 0 else "INATIVA (sera excluida)"
    print(f"  Hora {int(row['hora'])}: OEE total = {row['oee']*100:.2f}% - {status}")

active_hours = global_activity[global_activity['oee'] > 0]['hora'].values
print(f"\nHoras ativas: {sorted(active_hours)}")

# Filtrar apenas horas ativas
data_10_filtered = data_10[data_10['hora'].isin(active_hours)]

print("\nDia 10/02 - DEPOIS do filtro de horas ativas:")
for turno in ['Turno A', 'Turno B']:
    turno_data = data_10_filtered[data_10_filtered['turno'] == turno]
    print(f"\n{turno}:")
    print(f"  Registros: {len(turno_data)}")
    print(f"  Horas incluidas: {sorted(turno_data['hora'].unique())}")
    teep_avg = turno_data['teep'].mean()
    print(f"  TEEP medio: {teep_avg*100:.2f}%")

# Verificar se o problema está no filtro de horas ativas
print("\n" + "=" * 80)
print("TESTE: CALCULAR SEM FILTRO DE HORAS ATIVAS")
print("=" * 80)

mask = (df_oee['data'] >= '2026-02-01') & (df_oee['data'] <= '2026-02-11')
filtered_no_active = df_oee[mask]

print("\nSEM filtro de horas ativas:")
for turno in ['Turno A', 'Turno B']:
    turno_data = filtered_no_active[filtered_no_active['turno'] == turno]
    teep_avg = turno_data['teep'].mean()
    print(f"  {turno}: TEEP = {teep_avg*100:.2f}%")

# COM filtro de horas ativas
global_activity_all = filtered_no_active.groupby(['data', 'hora'])['oee'].sum().reset_index()
active_slots = global_activity_all[global_activity_all['oee'] > 0][['data', 'hora']]
filtered_with_active = filtered_no_active.merge(active_slots, on=['data', 'hora'], how='inner')

print("\nCOM filtro de horas ativas:")
for turno in ['Turno A', 'Turno B']:
    turno_data = filtered_with_active[filtered_with_active['turno'] == turno]
    teep_avg = turno_data['teep'].mean()
    print(f"  {turno}: TEEP = {teep_avg*100:.2f}%")

print("\n" + "=" * 80)
print("COMPARACAO")
print("=" * 80)
print("Sistema da fabrica:")
print("  Turno A: 40.23%")
print("  Turno B: 42.19%")
print("\nPrograma (COM filtro ativo):")
turno_a = filtered_with_active[filtered_with_active['turno'] == 'Turno A']['teep'].mean()
turno_b = filtered_with_active[filtered_with_active['turno'] == 'Turno B']['teep'].mean()
print(f"  Turno A: {turno_a*100:.2f}%  (diff: {abs(40.23 - turno_a*100):.2f})")
print(f"  Turno B: {turno_b*100:.2f}%  (diff: {abs(42.19 - turno_b*100):.2f})")
print("\nPrograma (SEM filtro ativo):")
turno_a_no = filtered_no_active[filtered_no_active['turno'] == 'Turno A']['teep'].mean()
turno_b_no = filtered_no_active[filtered_no_active['turno'] == 'Turno B']['teep'].mean()
print(f"  Turno A: {turno_a_no*100:.2f}%  (diff: {abs(40.23 - turno_a_no*100):.2f})")
print(f"  Turno B: {turno_b_no*100:.2f}%  (diff: {abs(42.19 - turno_b_no*100):.2f})")

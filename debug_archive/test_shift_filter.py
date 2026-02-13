import pandas as pd
import numpy as np

def load_oee_with_shift_filter():
    """Aplicar filtro de horas ativas POR TURNO em vez de globalmente"""
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
    
    # NOVO: Aplicar filtro de horas ativas POR TURNO
    if not new_df.empty:
        # Agrupar por data, turno e hora
        activity_by_shift = new_df.groupby(['data', 'turno', 'hora'])['oee'].sum().reset_index()
        active_slots = activity_by_shift[activity_by_shift['oee'] > 0][['data', 'turno', 'hora']]
        new_df = new_df.merge(active_slots, on=['data', 'turno', 'hora'], how='inner')
    
    return new_df

print("=" * 80)
print("TESTE: FILTRO DE HORAS ATIVAS POR TURNO")
print("=" * 80)

df_shift_filter = load_oee_with_shift_filter()

mask = (df_shift_filter['data'] >= '2026-02-01') & (df_shift_filter['data'] <= '2026-02-11')
filtered = df_shift_filter[mask]

print("\nResultados com filtro POR TURNO:")
for turno in ['Turno A', 'Turno B']:
    turno_data = filtered[filtered['turno'] == turno]
    teep_avg = turno_data['teep'].mean()
    print(f"  {turno}: TEEP = {teep_avg*100:.2f}%")

# Comparar com filtro global
def load_oee_with_global_filter():
    """Filtro global (como está atualmente)"""
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
    
    # Filtro GLOBAL
    if not new_df.empty:
        global_activity = new_df.groupby(['data', 'hora'])['oee'].sum().reset_index()
        active_slots = global_activity[global_activity['oee'] > 0][['data', 'hora']]
        new_df = new_df.merge(active_slots, on=['data', 'hora'], how='inner')
    
    return new_df

df_global_filter = load_oee_with_global_filter()
filtered_global = df_global_filter[mask]

print("\nResultados com filtro GLOBAL:")
for turno in ['Turno A', 'Turno B']:
    turno_data = filtered_global[filtered_global['turno'] == turno]
    teep_avg = turno_data['teep'].mean()
    print(f"  {turno}: TEEP = {teep_avg*100:.2f}%")

# Sem filtro
def load_oee_no_filter():
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

df_no_filter = load_oee_no_filter()
filtered_no = df_no_filter[mask]

print("\nResultados SEM filtro de horas ativas:")
for turno in ['Turno A', 'Turno B']:
    turno_data = filtered_no[filtered_no['turno'] == turno]
    teep_avg = turno_data['teep'].mean()
    print(f"  {turno}: TEEP = {teep_avg*100:.2f}%")

print("\n" + "=" * 80)
print("COMPARACAO FINAL")
print("=" * 80)
print("Sistema da fabrica:")
print("  Turno A: 40.23%")
print("  Turno B: 42.19%")

print("\nPrograma - Filtro POR TURNO:")
ta = filtered[filtered['turno'] == 'Turno A']['teep'].mean()
tb = filtered[filtered['turno'] == 'Turno B']['teep'].mean()
print(f"  Turno A: {ta*100:.2f}%  (diff: {abs(40.23 - ta*100):.2f})")
print(f"  Turno B: {tb*100:.2f}%  (diff: {abs(42.19 - tb*100):.2f})")

print("\nPrograma - Filtro GLOBAL:")
ta_g = filtered_global[filtered_global['turno'] == 'Turno A']['teep'].mean()
tb_g = filtered_global[filtered_global['turno'] == 'Turno B']['teep'].mean()
print(f"  Turno A: {ta_g*100:.2f}%  (diff: {abs(40.23 - ta_g*100):.2f})")
print(f"  Turno B: {tb_g*100:.2f}%  (diff: {abs(42.19 - tb_g*100):.2f})")

print("\nPrograma - SEM filtro:")
ta_n = filtered_no[filtered_no['turno'] == 'Turno A']['teep'].mean()
tb_n = filtered_no[filtered_no['turno'] == 'Turno B']['teep'].mean()
print(f"  Turno A: {ta_n*100:.2f}%  (diff: {abs(40.23 - ta_n*100):.2f})")
print(f"  Turno B: {tb_n*100:.2f}%  (diff: {abs(42.19 - tb_n*100):.2f})")

# Determinar qual é o melhor
diffs = {
    'Filtro POR TURNO': abs(40.23 - ta*100) + abs(42.19 - tb*100),
    'Filtro GLOBAL': abs(40.23 - ta_g*100) + abs(42.19 - tb_g*100),
    'SEM filtro': abs(40.23 - ta_n*100) + abs(42.19 - tb_n*100)
}

best = min(diffs.items(), key=lambda x: x[1])
print(f"\nMelhor metodo: {best[0]} (diferenca total: {best[1]:.2f})")

import pandas as pd
import numpy as np

def load_oee_data():
    try:
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
        
        # Filtrar apenas dias úteis
        new_df = new_df[new_df['data'].dt.dayofweek < 5]
        
        # Excluir horas onde TODAS as máquinas têm OEE = 0
        if not new_df.empty:
            global_activity = new_df.groupby(['data', 'hora'])['oee'].sum().reset_index()
            active_slots = global_activity[global_activity['oee'] > 0][['data', 'hora']]
            new_df = new_df.merge(active_slots, on=['data', 'hora'], how='inner')
        
        return new_df
    except Exception as e:
        print(f"Erro: {e}")
        return pd.DataFrame()

print("=" * 80)
print("ANALISE DE TEEP POR TURNO")
print("=" * 80)

df_oee = load_oee_data()

# Filtrar período
mask = (df_oee['data'] >= '2026-02-01') & (df_oee['data'] <= '2026-02-11')
filtered = df_oee[mask]

print(f"\nPeriodo: 01/02 a 11/02/2026")
print(f"Total de registros: {len(filtered)}")

# Análise por turno
print("\n" + "=" * 80)
print("METODO ATUAL DO PROGRAMA (Media simples por turno)")
print("=" * 80)

for turno in ['Turno A', 'Turno B']:
    turno_data = filtered[filtered['turno'] == turno]
    teep_avg = turno_data['teep'].mean()
    oee_avg = turno_data['oee'].mean()
    print(f"\n{turno}:")
    print(f"  Registros: {len(turno_data)}")
    print(f"  OEE medio:  {oee_avg*100:.2f}%")
    print(f"  TEEP medio: {teep_avg*100:.2f}%")

# Testar diferentes métodos de agregação
print("\n" + "=" * 80)
print("TESTANDO DIFERENTES METODOS DE AGREGACAO")
print("=" * 80)

# Método 1: Média por dia, depois por turno
print("\nMetodo 1: Media diaria primeiro, depois media por turno")
daily_shift = filtered.groupby(['data', 'turno'])[['teep', 'oee']].mean().reset_index()
for turno in ['Turno A', 'Turno B']:
    turno_data = daily_shift[daily_shift['turno'] == turno]
    teep_avg = turno_data['teep'].mean()
    print(f"  {turno}: TEEP = {teep_avg*100:.2f}%")

# Método 2: Média por máquina e turno
print("\nMetodo 2: Media por maquina e turno primeiro")
machine_shift = filtered.groupby(['maquina', 'turno'])[['teep', 'oee']].mean().reset_index()
for turno in ['Turno A', 'Turno B']:
    turno_data = machine_shift[machine_shift['turno'] == turno]
    teep_avg = turno_data['teep'].mean()
    print(f"  {turno}: TEEP = {teep_avg*100:.2f}%")

# Método 3: Excluir zeros antes de calcular
print("\nMetodo 3: Excluir TEEP = 0 antes de calcular")
filtered_nz = filtered[filtered['teep'] > 0]
for turno in ['Turno A', 'Turno B']:
    turno_data = filtered_nz[filtered_nz['turno'] == turno]
    teep_avg = turno_data['teep'].mean()
    print(f"  {turno}: TEEP = {teep_avg*100:.2f}%")

# Método 4: Média ponderada por número de horas
print("\nMetodo 4: Verificar distribuicao de horas por turno")
for turno in ['Turno A', 'Turno B']:
    turno_data = filtered[filtered['turno'] == turno]
    horas_unicas = sorted(turno_data['hora'].unique())
    print(f"  {turno}: Horas = {horas_unicas}")

# Verificar se o problema está na forma como agregamos
print("\n" + "=" * 80)
print("ANALISE DETALHADA - VALORES POR DIA E TURNO")
print("=" * 80)

daily_detail = filtered.groupby(['data', 'turno']).agg({
    'teep': 'mean',
    'oee': 'mean',
    'maquina': 'count'
}).reset_index()
daily_detail.columns = ['data', 'turno', 'teep', 'oee', 'registros']

print("\nValores diarios por turno:")
for turno in ['Turno A', 'Turno B']:
    print(f"\n{turno}:")
    turno_data = daily_detail[daily_detail['turno'] == turno]
    for _, row in turno_data.iterrows():
        print(f"  {row['data'].strftime('%d/%m')}: TEEP={row['teep']*100:.2f}%, OEE={row['oee']*100:.2f}%, Registros={row['registros']}")
    
    teep_avg = turno_data['teep'].mean()
    print(f"  --> Media: {teep_avg*100:.2f}%")

print("\n" + "=" * 80)
print("COMPARACAO COM SISTEMA DA FABRICA")
print("=" * 80)
print(f"Sistema da fabrica:")
print(f"  Turno A: 40.23%")
print(f"  Turno B: 42.19%")
print(f"\nPrograma atual:")
turno_a = filtered[filtered['turno'] == 'Turno A']['teep'].mean()
turno_b = filtered[filtered['turno'] == 'Turno B']['teep'].mean()
print(f"  Turno A: {turno_a*100:.2f}%  (diff: {abs(40.23 - turno_a*100):.2f})")
print(f"  Turno B: {turno_b*100:.2f}%  (diff: {abs(42.19 - turno_b*100):.2f})")

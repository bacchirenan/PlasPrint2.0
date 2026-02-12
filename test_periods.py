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
        
        if not new_df.empty:
            global_activity = new_df.groupby(['data', 'hora'])['oee'].sum().reset_index()
            active_slots = global_activity[global_activity['oee'] > 0][['data', 'hora']]
            new_df = new_df.merge(active_slots, on=['data', 'hora'], how='inner')
        
        return new_df
    except Exception as e:
        print(f"Erro: {e}")
        return pd.DataFrame()

df_oee = load_oee_data()

print("=" * 80)
print("TESTANDO DIFERENTES PERIODOS E FILTROS")
print("=" * 80)

# Teste 1: 02/02 a 11/02 (como está agora)
mask1 = (df_oee['data'] >= '2026-02-02') & (df_oee['data'] <= '2026-02-11')
test1 = df_oee[mask1]
print(f"\nTeste 1: 02/02 a 11/02")
print(f"  TEEP: {test1['teep'].mean()*100:.2f}%")
print(f"  Dias: {sorted(test1['data'].dt.strftime('%d/%m').unique())}")

# Teste 2: 01/02 a 11/02 (incluindo 01/02 se existir)
mask2 = (df_oee['data'] >= '2026-02-01') & (df_oee['data'] <= '2026-02-11')
test2 = df_oee[mask2]
print(f"\nTeste 2: 01/02 a 11/02")
print(f"  TEEP: {test2['teep'].mean()*100:.2f}%")
print(f"  Dias: {sorted(test2['data'].dt.strftime('%d/%m').unique())}")

# Teste 3: Incluindo 08/02 (sabado)
mask3 = (df_oee['data'] >= '2026-02-01') & (df_oee['data'] <= '2026-02-11')
test3_full = df_oee[mask3]

# Verificar se 08/02 existe nos dados RAW (antes de filtrar horas ativas)
df_raw = pd.read_excel('oee teep.xlsx', skiprows=1)
df_raw['data'] = pd.to_datetime(df_raw.iloc[:, 2], dayfirst=True, format='mixed', errors='coerce')
feb_dates = df_raw[(df_raw['data'] >= '2026-02-01') & (df_raw['data'] <= '2026-02-11')]['data'].unique()

print(f"\nDatas disponiveis no arquivo (01/02 a 11/02):")
for date in sorted(pd.to_datetime(feb_dates)):
    print(f"  {date.strftime('%d/%m/%Y (%A)')}")

# Teste 4: SEM filtro de horas ativas
print("\n" + "=" * 80)
print("TESTE SEM FILTRO DE HORAS ATIVAS")
print("=" * 80)

df_no_filter = pd.read_excel('oee teep.xlsx', skiprows=1)
new_df = pd.DataFrame()
new_df['maquina'] = df_no_filter.iloc[:, 1]
new_df['data'] = df_no_filter.iloc[:, 2]
new_df['turno'] = df_no_filter.iloc[:, 3]
new_df['hora'] = df_no_filter.iloc[:, 4]
new_df['teep'] = df_no_filter.iloc[:, 10]
new_df['oee'] = df_no_filter.iloc[:, 11]

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

# SEM filtro de horas ativas
mask_no_filter = (new_df['data'] >= '2026-02-01') & (new_df['data'] <= '2026-02-11')
test_no_filter = new_df[mask_no_filter]

print(f"\nSEM filtro de horas ativas:")
print(f"  Total registros: {len(test_no_filter)}")
print(f"  TEEP medio: {test_no_filter['teep'].mean()*100:.2f}%")
print(f"  OEE medio: {test_no_filter['oee'].mean()*100:.2f}%")

# Teste 5: Apenas dias úteis (excluir sábado e domingo)
print("\n" + "=" * 80)
print("TESTE: APENAS DIAS UTEIS")
print("=" * 80)

test_weekdays = test_no_filter[test_no_filter['data'].dt.dayofweek < 5]  # 0-4 = Segunda a Sexta
print(f"  Total registros (dias uteis): {len(test_weekdays)}")
print(f"  TEEP medio (dias uteis): {test_weekdays['teep'].mean()*100:.2f}%")
print(f"  Dias: {sorted(test_weekdays['data'].dt.strftime('%d/%m').unique())}")

print("\n" + "=" * 80)
print("RESUMO")
print("=" * 80)
print(f"Sistema da fabrica:                41,65%")
print(f"Programa atual (com filtro ativo): {test2['teep'].mean()*100:.2f}%")
print(f"Sem filtro de horas ativas:        {test_no_filter['teep'].mean()*100:.2f}%")
print(f"Apenas dias uteis:                 {test_weekdays['teep'].mean()*100:.2f}%")

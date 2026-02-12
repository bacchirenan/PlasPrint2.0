import pandas as pd
import numpy as np

def load_oee_data_weekdays_only():
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
        
        # NOVO: Filtrar apenas dias úteis (Segunda a Sexta)
        new_df = new_df[new_df['data'].dt.dayofweek < 5]
        
        # Filtro de horas ativas
        if not new_df.empty:
            global_activity = new_df.groupby(['data', 'hora'])['oee'].sum().reset_index()
            active_slots = global_activity[global_activity['oee'] > 0][['data', 'hora']]
            new_df = new_df.merge(active_slots, on=['data', 'hora'], how='inner')
        
        return new_df
    except Exception as e:
        print(f"Erro: {e}")
        return pd.DataFrame()

print("=" * 80)
print("TESTE FINAL: DIAS UTEIS + FILTRO DE HORAS ATIVAS")
print("=" * 80)

df_oee = load_oee_data_weekdays_only()

mask = (df_oee['data'] >= '2026-02-01') & (df_oee['data'] <= '2026-02-11')
filtered = df_oee[mask]

print(f"\nTotal de registros: {len(filtered)}")
print(f"Dias incluidos: {sorted(filtered['data'].dt.strftime('%d/%m (%A)').unique())}")

teep_avg = filtered['teep'].mean()
oee_avg = filtered['oee'].mean()

print("\n" + "=" * 80)
print("RESULTADO FINAL")
print("=" * 80)
print(f"OEE medio:  {oee_avg*100:.2f}%")
print(f"TEEP medio: {teep_avg*100:.2f}%")

print("\n" + "=" * 80)
print("COMPARACAO")
print("=" * 80)
print(f"Sistema da fabrica: 41,65%")
print(f"Programa corrigido: {teep_avg*100:.2f}%")
print(f"Diferenca:          {abs(41.65 - teep_avg*100):.2f} pontos percentuais")

if abs(41.65 - teep_avg*100) < 0.5:
    print("\nSTATUS: PERFEITO! Valores batem!")
elif abs(41.65 - teep_avg*100) < 1.5:
    print("\nSTATUS: MUITO BOM! Diferenca aceitavel.")
else:
    print("\nSTATUS: Ainda ha diferenca.")

import pandas as pd
import numpy as np

def load_raw_oee():
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    new_df = pd.DataFrame()
    new_df['maquina'] = df.iloc[:, 1]
    new_df['data'] = df.iloc[:, 2]
    new_df['turno_raw'] = df.iloc[:, 3]
    new_df['hora'] = df.iloc[:, 4]
    new_df['oee_raw'] = df.iloc[:, 11]
    
    # Limpar e converter
    new_df = new_df[new_df['maquina'].notna()]
    new_df = new_df[~new_df['maquina'].astype(str).str.contains('Turno', na=False)]
    new_df['data'] = pd.to_datetime(new_df['data'], dayfirst=True, format='mixed', errors='coerce')
    new_df = new_df.dropna(subset=['data'])
    
    def clean_pct(val):
        s = str(val).replace('%', '').replace(',', '.').strip()
        try:
            return float(s) / 100.0
        except:
            return 0.0

    new_df['oee'] = new_df['oee_raw'].apply(clean_pct)
    
    def map_shift(val):
        v = str(val).split('.')[0]
        if v == '1': return 'Turno A'
        if v == '2': return 'Turno B'
        return 'Outro'
        
    new_df['turno'] = new_df['turno_raw'].apply(map_shift)
    return new_df

df = load_raw_oee()

# Filtrar o dia específico
target_date = '2026-01-21'
df_target = df[df['data'] == target_date].copy()

print(f"--- Diagnóstico OEE para {target_date} ---")
print(f"Total de registros no dia: {len(df_target)}")

# Filtro de horário que o app usa (06:00 às 21:59)
df_filtered = df_target[(df_target['hora'] >= 6) & (df_target['hora'] <= 21)].copy()
print(f"Registros entre 06h e 21h: {len(df_filtered)}")

for t in ['Turno A', 'Turno B']:
    print(f"\n--- {t} ---")
    data_t = df_filtered[df_filtered['turno'] == t]
    data_raw = df_target[df_target['turno'] == t]
    
    if len(data_t) > 0:
        mean_v = data_t['oee'].mean() * 100
        median_v = data_t['oee'].median() * 100
        print(f"Com Filtro Horário (06-21h):")
        print(f"  - Média: {mean_v:.2f}%")
        print(f"  - Mediana: {median_v:.2f}%")
        print(f"  - Qtd Horas: {len(data_t)}")
        
    if len(data_raw) > 0:
        mean_raw = data_raw['oee'].mean() * 100
        print(f"Sem Filtro Horário (Dados Brutos):")
        print(f"  - Média: {mean_raw:.2f}%")
        print(f"  - Qtd Horas: {len(data_raw)}")
        
    # Mostrar os valores horários para entender
    print("Valores de OEE por hora:")
    print(data_raw[['hora', 'oee']].sort_values('hora').to_string(index=False))

# Verificar se a média de todas as máquinas agrupadas por turno bate com o esperado pelo usuário
# O usuário pode estar esperando a média das médias por máquina?
print("\n--- Verificando Agrupamento por Máquina ---")
for t in ['Turno A', 'Turno B']:
    df_t = df_filtered[df_filtered['turno'] == t]
    if not df_t.empty:
        # Média das médias das máquinas
        machine_means = df_t.groupby('maquina')['oee'].mean()
        print(f"{t} - Média das Médias por Máquina: {machine_means.mean()*100:.2f}%")
        # Mediana das medianas das máquinas
        machine_medians = df_t.groupby('maquina')['oee'].median()
        print(f"{t} - Mediana das Medianas por Máquina: {machine_medians.median()*100:.2f}%")

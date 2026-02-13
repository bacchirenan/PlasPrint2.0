import pandas as pd

# Carregar dados brutos
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

# Filtrar período
mask = (new_df['data'] >= '2026-02-01') & (new_df['data'] <= '2026-02-11')
filtered = new_df[mask]

print("=" * 80)
print("VALORES DO ARQUIVO - SEM NENHUM FILTRO DE HORAS ATIVAS")
print("=" * 80)

print("\nTEEP por turno (media simples de todos os registros):")
for turno in ['Turno A', 'Turno B']:
    turno_data = filtered[filtered['turno'] == turno]
    teep_avg = turno_data['teep'].mean()
    print(f"  {turno}: {teep_avg*100:.2f}%")

print("\n" + "=" * 80)
print("COMPARACAO")
print("=" * 80)
print("Sistema da fabrica:")
print("  Turno A: 40.23%")
print("  Turno B: 42.19%")
print("  Geral:   41.65%")

print("\nPrograma (valores do arquivo, sem filtro):")
ta = filtered[filtered['turno'] == 'Turno A']['teep'].mean()
tb = filtered[filtered['turno'] == 'Turno B']['teep'].mean()
geral = filtered['teep'].mean()
print(f"  Turno A: {ta*100:.2f}%  (diff: {abs(40.23 - ta*100):.2f})")
print(f"  Turno B: {tb*100:.2f}%  (diff: {abs(42.19 - tb*100):.2f})")
print(f"  Geral:   {geral*100:.2f}%  (diff: {abs(41.65 - geral*100):.2f})")

# Verificar se há alguma diferença nos dados por turno
print("\n" + "=" * 80)
print("DETALHES POR DIA")
print("=" * 80)

daily = filtered.groupby(['data', 'turno']).agg({
    'teep': 'mean',
    'maquina': 'count'
}).reset_index()
daily.columns = ['data', 'turno', 'teep', 'registros']

for turno in ['Turno A', 'Turno B']:
    print(f"\n{turno}:")
    turno_data = daily[daily['turno'] == turno]
    for _, row in turno_data.iterrows():
        print(f"  {row['data'].strftime('%d/%m')}: {row['teep']*100:.2f}%  ({row['registros']} registros)")

# Calcular a média ponderada
print("\n" + "=" * 80)
print("TESTE: MEDIA PONDERADA PELO NUMERO DE REGISTROS")
print("=" * 80)

for turno in ['Turno A', 'Turno B']:
    turno_data = daily[daily['turno'] == turno]
    weighted_avg = (turno_data['teep'] * turno_data['registros']).sum() / turno_data['registros'].sum()
    simple_avg = turno_data['teep'].mean()
    print(f"\n{turno}:")
    print(f"  Media simples:    {simple_avg*100:.2f}%")
    print(f"  Media ponderada:  {weighted_avg*100:.2f}%")

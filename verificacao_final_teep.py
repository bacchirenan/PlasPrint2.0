import pandas as pd
import numpy as np

print("=" * 80)
print("VERIFICACAO FINAL - TEEP CORRIGIDO COM FILTRO DE DIAS UTEIS")
print("=" * 80)

# Simular a função load_oee_data() corrigida
def load_oee_data():
    try:
        df = pd.read_excel('oee teep.xlsx', skiprows=1)
        
        new_df = pd.DataFrame()
        new_df['maquina'] = df.iloc[:, 1]
        new_df['data'] = df.iloc[:, 2]
        new_df['turno'] = df.iloc[:, 3]
        new_df['hora'] = df.iloc[:, 4]
        new_df['disponibilidade'] = df.iloc[:, 7]
        new_df['performance'] = df.iloc[:, 8]
        new_df['qualidade'] = df.iloc[:, 9]
        new_df['teep'] = df.iloc[:, 10]  # TEEP do arquivo
        new_df['oee'] = df.iloc[:, 11]   # OEE do arquivo
        
        # Filtrar dados válidos
        new_df = new_df[new_df['maquina'].notna()]
        new_df = new_df[~new_df['maquina'].astype(str).str.contains('Turno', na=False)]
        new_df = new_df[new_df['data'].notna()]
        
        # Converter porcentagens
        pct_cols = ['disponibilidade', 'performance', 'qualidade', 'teep', 'oee']
        for col in pct_cols:
            new_df[col] = new_df[col].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
            new_df[col] = pd.to_numeric(new_df[col], errors='coerce').fillna(0) / 100.0
        
        # Criar colunas auxiliares
        new_df['performance_nz'] = new_df['performance'].replace(0, np.nan)
        new_df['qualidade_nz'] = new_df['qualidade'].replace(0, np.nan)

        # Converter data
        new_df['data'] = pd.to_datetime(new_df['data'], dayfirst=True, format='mixed', errors='coerce')
        new_df = new_df.dropna(subset=['data'])
        
        # Renomear turnos
        def rename_shift(val):
            val_str = str(val).split('.')[0]
            if val_str == '1': return 'Turno A'
            if val_str == '2': return 'Turno B'
            return None
        
        new_df['turno'] = new_df['turno'].apply(rename_shift)
        new_df = new_df[new_df['turno'].isin(['Turno A', 'Turno B'])]
        
        # Filtrar horário 6h-21h
        new_df['hora'] = pd.to_numeric(new_df['hora'], errors='coerce')
        new_df = new_df[(new_df['hora'] >= 6) & (new_df['hora'] <= 21)]
        
        # NOVO: Filtrar apenas dias úteis (Segunda a Sexta)
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

# Carregar dados
df_oee = load_oee_data()

# Filtrar período: 01/02 a 11/02
mask_date = (df_oee['data'] >= '2026-02-01') & (df_oee['data'] <= '2026-02-11')
filtered = df_oee[mask_date].copy()

print(f"\nPeriodo analisado: 01/02/2026 a 11/02/2026")
print(f"Total de registros: {len(filtered)}")
print(f"\nDias incluidos (apenas dias uteis):")
for date in sorted(filtered['data'].unique()):
    day_name = date.strftime('%A')
    day_name_pt = {
        'Monday': 'Segunda-feira',
        'Tuesday': 'Terca-feira',
        'Wednesday': 'Quarta-feira',
        'Thursday': 'Quinta-feira',
        'Friday': 'Sexta-feira',
        'Saturday': 'Sabado',
        'Sunday': 'Domingo'
    }.get(day_name, day_name)
    count = len(filtered[filtered['data'] == date])
    print(f"  {date.strftime('%d/%m/%Y')} ({day_name_pt}): {count} registros")

# Calcular TEEP médio
teep_avg = filtered['teep'].mean()
oee_avg = filtered['oee'].mean()

print("\n" + "=" * 80)
print("RESULTADO FINAL")
print("=" * 80)
print(f"OEE medio:  {oee_avg*100:.2f}%")
print(f"TEEP medio: {teep_avg*100:.2f}%")

print("\n" + "=" * 80)
print("COMPARACAO COM O SISTEMA DA FABRICA")
print("=" * 80)
print(f"Sistema da fabrica: 41,65%")
print(f"Programa ANTES:     36,45%  (diferenca: 5,20 pontos)")
print(f"Programa DEPOIS:    {teep_avg*100:.2f}%  (diferenca: {abs(41.65 - teep_avg*100):.2f} pontos)")

diferenca = abs(41.65 - teep_avg*100)
if diferenca < 0.5:
    status = "PERFEITO"
    emoji = "✓✓✓"
elif diferenca < 1.0:
    status = "EXCELENTE"
    emoji = "✓✓"
elif diferenca < 2.0:
    status = "MUITO BOM"
    emoji = "✓"
else:
    status = "ACEITAVEL"
    emoji = "~"

print(f"\nSTATUS: {emoji} {status} {emoji}")
print(f"\nMelhoria: {5.20 - diferenca:.2f} pontos percentuais mais proximo do sistema!")

print("\n" + "=" * 80)
print("RESUMO DAS CORRECOES APLICADAS")
print("=" * 80)
print("1. Usar valores de TEEP e OEE diretamente do arquivo")
print("2. Nao recalcular TEEP (remover formula OEE * 16/24)")
print("3. Filtrar apenas dias uteis (Segunda a Sexta)")
print("4. Manter filtro de horas ativas (excluir horas com OEE=0 em todas maquinas)")
print("=" * 80)

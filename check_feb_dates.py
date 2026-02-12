import pandas as pd
import numpy as np

try:
    # Carregar dados
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    
    new_df = pd.DataFrame()
    new_df['maquina'] = df.iloc[:, 1]
    new_df['data'] = df.iloc[:, 2]
    new_df['turno'] = df.iloc[:, 3]
    new_df['hora'] = df.iloc[:, 4]
    new_df['teep'] = df.iloc[:, 10]
    new_df['oee'] = df.iloc[:, 11]
    
    # Filtrar dados válidos
    new_df = new_df[new_df['maquina'].notna()]
    new_df = new_df[~new_df['maquina'].astype(str).str.contains('Turno', na=False)]
    new_df = new_df[new_df['data'].notna()]
    
    # Converter porcentagens
    for col in ['teep', 'oee']:
        new_df[col] = new_df[col].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
        new_df[col] = pd.to_numeric(new_df[col], errors='coerce').fillna(0) / 100.0
    
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
    
    print("=" * 80)
    print("VERIFICANDO DATAS DISPONIVEIS EM FEVEREIRO")
    print("=" * 80)
    
    # Ver todas as datas de fevereiro
    feb_mask = (new_df['data'] >= '2026-02-01') & (new_df['data'] <= '2026-02-28')
    feb_data = new_df[feb_mask]
    
    print(f"\nDatas unicas em fevereiro:")
    for date in sorted(feb_data['data'].unique()):
        count = len(feb_data[feb_data['data'] == date])
        print(f"  {date.strftime('%d/%m/%Y')}: {count} registros")
    
    # Testar incluindo 01/02
    print("\n" + "=" * 80)
    print("TESTE COM DIA 01/02 INCLUIDO")
    print("=" * 80)
    
    mask_with_01 = (new_df['data'] >= '2026-02-01') & (new_df['data'] <= '2026-02-11')
    filtered_with_01 = new_df[mask_with_01].copy()
    
    # Excluir horas inativas
    global_activity = filtered_with_01.groupby(['data', 'hora'])['oee'].sum().reset_index()
    global_activity.columns = ['data', 'hora', 'total_oee']
    active_hours = global_activity[global_activity['total_oee'] > 0][['data', 'hora']]
    filtered_active = filtered_with_01.merge(active_hours, on=['data', 'hora'], how='inner')
    
    teep_with_01 = filtered_active['teep'].mean()
    print(f"TEEP com 01/02 incluido: {teep_with_01*100:.2f}%")
    
    # Testar SEM 01/02
    print("\n" + "=" * 80)
    print("TESTE SEM DIA 01/02")
    print("=" * 80)
    
    mask_without_01 = (new_df['data'] >= '2026-02-02') & (new_df['data'] <= '2026-02-11')
    filtered_without_01 = new_df[mask_without_01].copy()
    
    # Excluir horas inativas
    global_activity = filtered_without_01.groupby(['data', 'hora'])['oee'].sum().reset_index()
    global_activity.columns = ['data', 'hora', 'total_oee']
    active_hours = global_activity[global_activity['total_oee'] > 0][['data', 'hora']]
    filtered_active = filtered_without_01.merge(active_hours, on=['data', 'hora'], how='inner')
    
    teep_without_01 = filtered_active['teep'].mean()
    print(f"TEEP sem 01/02: {teep_without_01*100:.2f}%")
    
    # Testar com diferentes interpretações de "ate 11/02"
    print("\n" + "=" * 80)
    print("TESTE: Diferentes interpretacoes do periodo")
    print("=" * 80)
    
    # Até 11/02 inclusive
    mask1 = (new_df['data'] >= '2026-02-01') & (new_df['data'] <= '2026-02-11')
    # Até 10/02 (11/02 exclusive)
    mask2 = (new_df['data'] >= '2026-02-01') & (new_df['data'] < '2026-02-11')
    
    for i, mask in enumerate([mask1, mask2], 1):
        filtered = new_df[mask].copy()
        global_activity = filtered.groupby(['data', 'hora'])['oee'].sum().reset_index()
        global_activity.columns = ['data', 'hora', 'total_oee']
        active_hours = global_activity[global_activity['total_oee'] > 0][['data', 'hora']]
        filtered_active = filtered.merge(active_hours, on=['data', 'hora'], how='inner')
        
        teep = filtered_active['teep'].mean()
        dates = sorted(filtered['data'].unique())
        print(f"\nTeste {i}:")
        print(f"  Periodo: {dates[0].strftime('%d/%m')} ate {dates[-1].strftime('%d/%m')}")
        print(f"  TEEP: {teep*100:.2f}%")
    
    print("\n" + "=" * 80)
    print("RESUMO")
    print("=" * 80)
    print(f"Sistema da fabrica: 41,65%")
    print(f"Programa atual:     36,45%")
    print(f"Diferenca:          {41.65 - 36.45:.2f} pontos percentuais")
    
except Exception as e:
    print(f"Erro: {e}")
    import traceback
    traceback.print_exc()

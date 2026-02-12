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
    new_df['disponibilidade'] = df.iloc[:, 7]
    new_df['performance'] = df.iloc[:, 8]
    new_df['qualidade'] = df.iloc[:, 9]
    new_df['teep_file'] = df.iloc[:, 10]  # TEEP do arquivo
    
    # Filtrar dados válidos
    new_df = new_df[new_df['maquina'].notna()]
    new_df = new_df[~new_df['maquina'].astype(str).str.contains('Turno', na=False)]
    new_df = new_df[new_df['data'].notna()]
    
    # Converter porcentagens
    pct_cols = ['disponibilidade', 'performance', 'qualidade', 'teep_file']
    for col in pct_cols:
        new_df[col] = new_df[col].astype(str).str.replace('%', '').str.replace(',', '.').str.strip()
        new_df[col] = pd.to_numeric(new_df[col], errors='coerce').fillna(0) / 100.0
    
    # Calcular OEE
    new_df['oee'] = (new_df['disponibilidade'] * new_df['performance'] * new_df['qualidade']).round(4)
    
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
    
    # Filtrar período: 01/02 a 11/02
    mask_date = (new_df['data'] >= '2026-02-01') & (new_df['data'] <= '2026-02-11')
    filtered = new_df[mask_date].copy()
    
    print("=" * 80)
    print("ANÁLISE TEEP - PERÍODO 01/02 a 11/02/2026")
    print("=" * 80)
    print(f"\nTotal de registros no período: {len(filtered)}")
    print(f"Datas únicas: {sorted(filtered['data'].dt.strftime('%d/%m').unique())}")
    print(f"Máquinas: {sorted(filtered['maquina'].unique())}")
    print(f"Turnos: {sorted(filtered['turno'].unique())}")
    
    # Análise 1: TEEP do arquivo (coluna K)
    print("\n" + "=" * 80)
    print("ANÁLISE 1: TEEP do Arquivo (Coluna K)")
    print("=" * 80)
    teep_file_avg = filtered['teep_file'].mean()
    print(f"TEEP médio do arquivo: {teep_file_avg*100:.2f}%")
    
    # Análise 2: OEE médio
    print("\n" + "=" * 80)
    print("ANÁLISE 2: OEE Calculado")
    print("=" * 80)
    oee_avg = filtered['oee'].mean()
    print(f"OEE médio calculado: {oee_avg*100:.2f}%")
    
    # Análise 3: TEEP calculado ERRADO (linha por linha)
    print("\n" + "=" * 80)
    print("ANÁLISE 3: TEEP Calculado ERRADO (OEE * 16/24 por linha)")
    print("=" * 80)
    filtered['teep_wrong'] = filtered['oee'] * (16/24)
    teep_wrong_avg = filtered['teep_wrong'].mean()
    print(f"TEEP médio (método errado): {teep_wrong_avg*100:.2f}%")
    
    # Análise 4: TEEP calculado CORRETO (média do OEE * 16/24)
    print("\n" + "=" * 80)
    print("ANÁLISE 4: TEEP Calculado CORRETO (Média OEE * 16/24)")
    print("=" * 80)
    teep_correct = oee_avg * (16/24)
    print(f"TEEP correto: {teep_correct*100:.2f}%")
    
    # Análise 5: Excluir horas onde TODAS as máquinas têm OEE = 0
    print("\n" + "=" * 80)
    print("ANÁLISE 5: Excluindo horas com OEE = 0 em TODAS as máquinas")
    print("=" * 80)
    
    global_activity = filtered.groupby(['data', 'hora'])['oee'].sum().reset_index()
    global_activity.columns = ['data', 'hora', 'total_oee']
    active_hours = global_activity[global_activity['total_oee'] > 0][['data', 'hora']]
    
    filtered_active = filtered.merge(active_hours, on=['data', 'hora'], how='inner')
    print(f"Registros após excluir horas inativas: {len(filtered_active)}")
    
    oee_active_avg = filtered_active['oee'].mean()
    teep_active = oee_active_avg * (16/24)
    print(f"OEE médio (horas ativas): {oee_active_avg*100:.2f}%")
    print(f"TEEP correto (horas ativas): {teep_active*100:.2f}%")
    
    # Comparação final
    print("\n" + "=" * 80)
    print("RESUMO COMPARATIVO")
    print("=" * 80)
    print(f"Sistema da fábrica:           41,65%")
    print(f"Programa atual (errado):      {teep_wrong_avg*100:.2f}%")
    print(f"TEEP do arquivo (coluna K):   {teep_file_avg*100:.2f}%")
    print(f"TEEP correto (sem filtro):    {teep_correct*100:.2f}%")
    print(f"TEEP correto (horas ativas):  {teep_active*100:.2f}%")
    
    print("\n" + "=" * 80)
    print("CONCLUSÃO")
    print("=" * 80)
    if abs(teep_active*100 - 41.65) < 0.5:
        print("✓ O método correto com filtro de horas ativas bate com o sistema!")
    elif abs(teep_file_avg*100 - 41.65) < 0.5:
        print("✓ O TEEP do arquivo (coluna K) bate com o sistema!")
    else:
        print("✗ Nenhum método bateu exatamente. Investigação adicional necessária.")
    
except Exception as e:
    print(f"Erro: {e}")
    import traceback
    traceback.print_exc()

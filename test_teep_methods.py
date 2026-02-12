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
    new_df['teep'] = df.iloc[:, 10]  # TEEP do arquivo
    new_df['oee'] = df.iloc[:, 11]   # OEE do arquivo
    
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
    
    # Filtrar período: 01/02 a 11/02
    mask_date = (new_df['data'] >= '2026-02-01') & (new_df['data'] <= '2026-02-11')
    filtered = new_df[mask_date].copy()
    
    print("=" * 80)
    print("ANALISE TEEP - USANDO VALORES DO ARQUIVO")
    print("=" * 80)
    print(f"\nTotal de registros no periodo: {len(filtered)}")
    
    # Teste 1: Média simples
    print("\n" + "=" * 80)
    print("TESTE 1: Media simples de todos os registros")
    print("=" * 80)
    teep_avg = filtered['teep'].mean()
    oee_avg = filtered['oee'].mean()
    print(f"TEEP medio: {teep_avg*100:.2f}%")
    print(f"OEE medio: {oee_avg*100:.2f}%")
    
    # Teste 2: Excluir horas onde TODAS as máquinas têm OEE = 0
    print("\n" + "=" * 80)
    print("TESTE 2: Excluindo horas com OEE = 0 em TODAS as maquinas")
    print("=" * 80)
    
    global_activity = filtered.groupby(['data', 'hora'])['oee'].sum().reset_index()
    global_activity.columns = ['data', 'hora', 'total_oee']
    active_hours = global_activity[global_activity['total_oee'] > 0][['data', 'hora']]
    
    filtered_active = filtered.merge(active_hours, on=['data', 'hora'], how='inner')
    print(f"Registros apos excluir horas inativas: {len(filtered_active)}")
    
    teep_active = filtered_active['teep'].mean()
    oee_active = filtered_active['oee'].mean()
    print(f"TEEP medio (horas ativas): {teep_active*100:.2f}%")
    print(f"OEE medio (horas ativas): {oee_active*100:.2f}%")
    
    # Teste 3: Excluir registros com TEEP = 0
    print("\n" + "=" * 80)
    print("TESTE 3: Excluindo registros com TEEP = 0")
    print("=" * 80)
    
    filtered_nonzero = filtered[filtered['teep'] > 0]
    print(f"Registros com TEEP > 0: {len(filtered_nonzero)}")
    
    teep_nonzero = filtered_nonzero['teep'].mean()
    oee_nonzero = filtered_nonzero['oee'].mean()
    print(f"TEEP medio (TEEP > 0): {teep_nonzero*100:.2f}%")
    print(f"OEE medio (TEEP > 0): {oee_nonzero*100:.2f}%")
    
    # Teste 4: Agrupar por dia e calcular média
    print("\n" + "=" * 80)
    print("TESTE 4: Media por dia, depois media geral")
    print("=" * 80)
    
    daily_avg = filtered_active.groupby('data')[['teep', 'oee']].mean()
    print("\nMedia por dia:")
    print(daily_avg)
    
    teep_daily_avg = daily_avg['teep'].mean()
    oee_daily_avg = daily_avg['oee'].mean()
    print(f"\nTEEP medio (media das medias diarias): {teep_daily_avg*100:.2f}%")
    print(f"OEE medio (media das medias diarias): {oee_daily_avg*100:.2f}%")
    
    # Teste 5: Média ponderada por máquina
    print("\n" + "=" * 80)
    print("TESTE 5: Media por maquina, depois media geral")
    print("=" * 80)
    
    machine_avg = filtered_active.groupby('maquina')[['teep', 'oee']].mean()
    print("\nMedia por maquina:")
    print(machine_avg)
    
    teep_machine_avg = machine_avg['teep'].mean()
    oee_machine_avg = machine_avg['oee'].mean()
    print(f"\nTEEP medio (media das medias por maquina): {teep_machine_avg*100:.2f}%")
    print(f"OEE medio (media das medias por maquina): {oee_machine_avg*100:.2f}%")
    
    # Resumo
    print("\n" + "=" * 80)
    print("RESUMO COMPARATIVO")
    print("=" * 80)
    print(f"Sistema da fabrica:                     41,65%")
    print(f"Teste 1 (media simples):                {teep_avg*100:.2f}%")
    print(f"Teste 2 (horas ativas):                 {teep_active*100:.2f}%")
    print(f"Teste 3 (TEEP > 0):                     {teep_nonzero*100:.2f}%")
    print(f"Teste 4 (media das medias diarias):     {teep_daily_avg*100:.2f}%")
    print(f"Teste 5 (media das medias por maquina): {teep_machine_avg*100:.2f}%")
    
    # Verificar qual está mais próximo
    target = 41.65
    tests = {
        'Teste 1': teep_avg*100,
        'Teste 2': teep_active*100,
        'Teste 3': teep_nonzero*100,
        'Teste 4': teep_daily_avg*100,
        'Teste 5': teep_machine_avg*100
    }
    
    closest = min(tests.items(), key=lambda x: abs(x[1] - target))
    print(f"\nMais proximo do sistema: {closest[0]} ({closest[1]:.2f}%)")
    print(f"Diferenca: {abs(closest[1] - target):.2f} pontos percentuais")
    
except Exception as e:
    print(f"Erro: {e}")
    import traceback
    traceback.print_exc()

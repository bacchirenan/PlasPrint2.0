import pandas as pd

try:
    df = pd.read_excel('oee teep.xlsx', skiprows=1)
    # Check rows where the date is recent (e.g. Feb 2026)
    df['Data_dt'] = pd.to_datetime(df.iloc[:, 2], dayfirst=True, errors='coerce')
    recent = df[df['Data_dt'] >= '2026-02-01']
    print(f"Recent data counts: {len(recent)}")
    if not recent.empty:
        print("Recent machines:")
        print(recent.iloc[:, 1].unique())
        print("\nTail of recent data:")
        print(recent.iloc[-20:, :5])
except Exception as e:
    print(f"Error: {e}")

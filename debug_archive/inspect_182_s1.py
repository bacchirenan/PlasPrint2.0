import pandas as pd
df = pd.read_excel('oee teep.xlsx', skiprows=1)
mask = (df.iloc[:, 1] == '182- CX-360G') & (df.iloc[:, 2] == '03/02/2026') & (df.iloc[:, 3] == 1)
print(df[mask].iloc[:, [4, 7, 8, 9, 11]])

import sqlite3
import pandas as pd

# Conectar ao banco de dados
conn = sqlite3.connect('fichas_tecnicas.db')

# Ler dados de exemplo
df = pd.read_sql_query("SELECT referencia, produto, cyan, magenta, yellow, black, white, varnish FROM fichas LIMIT 5", conn)

print("=" * 80)
print("DADOS ATUAIS NO BANCO (valores brutos):")
print("=" * 80)
print(df.to_string(index=False))
print("\n")

print("=" * 80)
print("CONVERSÃO EXPLICADA:")
print("=" * 80)
for _, row in df.iterrows():
    print(f"\nReferência: {row['referencia']} - {row['produto']}")
    print(f"  Cyan:    {row['cyan']:.3f} (bruto) = {row['cyan']*1000:.1f} ml")
    print(f"  Magenta: {row['magenta']:.3f} (bruto) = {row['magenta']*1000:.1f} ml")
    print(f"  Yellow:  {row['yellow']:.3f} (bruto) = {row['yellow']*1000:.1f} ml")
    print(f"  Black:   {row['black']:.3f} (bruto) = {row['black']*1000:.1f} ml")
    print(f"  White:   {row['white']:.3f} (bruto) = {row['white']*1000:.1f} ml")
    print(f"  Varnish: {row['varnish']:.3f} (bruto) = {row['varnish']*1000:.1f} ml")

conn.close()

print("\n" + "=" * 80)
print("INTERPRETAÇÃO:")
print("=" * 80)
print("Se os valores brutos estão em LITROS: multiplique por 1000 para obter ml")
print("Se os valores brutos JÁ estão em ML: os valores parecem estar incorretos")
print("=" * 80)

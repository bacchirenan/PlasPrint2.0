HEAD
import sqlite3
db_path = r"d:\IMPRESSAO\SOFTWARES\PlasPrint IA v2.0\fichas_tecnicas.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT count(*) FROM fichas")
count = cursor.fetchone()[0]
print(f"Total de fichas: {count}")
conn.close()

import sqlite3
db_path = r"d:\IMPRESSAO\SOFTWARES\PlasPrint IA v2.0\fichas_tecnicas.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT count(*) FROM fichas")
count = cursor.fetchone()[0]
print(f"Total de fichas: {count}")
conn.close()
1e543fd (Salvando alterações antes do rebase)

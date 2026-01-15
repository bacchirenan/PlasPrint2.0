import sqlite3
conn = sqlite3.connect('fichas_tecnicas.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM fichas WHERE referencia='10259'")
print(cursor.fetchone())
conn.close()

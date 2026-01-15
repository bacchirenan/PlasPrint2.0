import sqlite3
conn = sqlite3.connect('fichas_tecnicas.db')
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(fichas);")
print(cursor.fetchall())
conn.close()

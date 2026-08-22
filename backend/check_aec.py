import sqlite3

conn = sqlite3.connect('aec.db')
tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
conn.close()
print("aec.db tables:", sorted(tables))
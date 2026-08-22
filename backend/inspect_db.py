import sqlite3, os
conn = sqlite3.connect('test_inspect.db')
tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
conn.close()
print('Tables:', sorted(tables))
print('Size:', os.path.getsize('test_inspect.db'))
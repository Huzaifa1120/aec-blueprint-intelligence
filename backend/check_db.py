import sqlite3, os
# Check which DB file exists
for f in ['test_via_cmd.db', 'aec.db']:
    if os.path.exists(f):
        conn = sqlite3.connect(f)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
        print(f'{f}: {len(tables)} tables - {sorted(tables)[:5]}...')
    else:
        print(f'{f}: not found')
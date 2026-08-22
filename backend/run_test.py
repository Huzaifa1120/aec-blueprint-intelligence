import sqlite3, subprocess, sys, os
from pathlib import Path

BACKEND = Path('backend').resolve()
db_file = Path('test_migration_test.db')
env = {**os.environ, 'DATABASE_URL': f'sqlite:///{db_file.as_posix()}'}
subprocess.run(
    [sys.executable, '-m', 'alembic', 'upgrade', 'head'],
    cwd=BACKEND, env=env, check=True, capture_output=True,
)
conn = sqlite3.connect(db_file.as_posix())
try:
    tables = {
        r[0] for r in conn.execute('SELECT name FROM sqlite_master WHERE type="table"')
    }
    print('Tables:', sorted(tables))
finally:
    conn.close()
db_file.unlink(missing_ok=True)
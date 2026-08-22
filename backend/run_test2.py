import sqlite3, subprocess, sys, os
from pathlib import Path

BACKEND = Path('backend').resolve()
print("BACKEND:", BACKEND)
print("CWD:", Path.cwd())

# Run alemic without DB_URL override first
result = subprocess.run(
    [sys.executable, '-m', 'alembic', 'upgrade', 'head'],
    cwd=BACKEND, capture_output=True, text=True,
)
print("Return code:", result.returncode)
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)

# Now try with DB_URL
db_file = Path('test_migration_test2.db')
env = {**os.environ, 'DATABASE_URL': f'sqlite:///{db_file.as_posix()}'}
result2 = subprocess.run(
    [sys.executable, '-m', 'alembic', 'upgrade', 'head'],
    cwd=BACKEND, env=env, capture_output=True, text=True,
)
print("With DB_URL - Return code:", result2.returncode)
print("STDOUT:", result2.stdout)
print("STDERR:", result2.stderr)

# Check tables
conn = sqlite3.connect(db_file.as_posix())
try:
    tables = {
        r[0] for r in conn.execute('SELECT name FROM sqlite_master WHERE type="table"')
    }
    print('Tables:', sorted(tables))
finally:
    conn.close()
db_file.unlink(missing_ok=True)
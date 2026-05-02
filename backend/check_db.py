import psycopg

try:
    conn = psycopg.connect('postgresql://caresync:caresync@localhost:5432/caresync')
    cur = conn.cursor()
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    tables = cur.fetchall()
    print('Database tables:')
    for t in tables:
        print(f'  - {t[0]}')
    conn.close()
    print(f'\nTotal tables: {len(tables)}')
except Exception as e:
    print(f'Error: {e}')

# Gate 1 verification — connect as application user, run SELECT 1.
# Requires: pip install pymysql

import sys
import pymysql

HOST = '127.0.0.1'
PORT = 3307
USER = 'airtrack'
PASSWORD = 'Gate1UserPass!'
DATABASE = 'airtrack'

try:
    conn = pymysql.connect(host=HOST, port=PORT, user=USER,
                           password=PASSWORD, database=DATABASE)
    cur = conn.cursor()
    cur.execute('SELECT 1')
    result = cur.fetchone()
    conn.close()
    if result == (1,):
        print('PASS: connected to airtrack on port 3307, SELECT 1 returned 1.')
        sys.exit(0)
    else:
        print(f'FAIL: unexpected result: {result}')
        sys.exit(1)
except Exception as e:
    print(f'FAIL: {e}')
    sys.exit(1)

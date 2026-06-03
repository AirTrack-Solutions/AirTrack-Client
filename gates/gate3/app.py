from flask import Flask
import pymysql

app = Flask(__name__)

DB = dict(host='127.0.0.1', port=3307, user='airtrack',
          password='Gate1UserPass!', database='airtrack')

@app.route('/')
def index():
    try:
        conn = pymysql.connect(**DB)
        cur = conn.cursor()
        cur.execute('SELECT 1')
        result = cur.fetchone()
        conn.close()
        if result == (1,):
            return 'AirTrack OK — DB connected'
        return 'AirTrack OK — unexpected DB result', 500
    except Exception as e:
        return f'AirTrack OK — DB ERROR: {e}', 500

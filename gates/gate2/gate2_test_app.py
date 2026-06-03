# Gate 2 test app — build 003 — no database code
from flask import Flask

app = Flask(__name__)

@app.route('/')
def index():
    return 'Gate2 Test App OK - build 003 - no database code'

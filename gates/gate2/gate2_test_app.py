# Gate 2 test app — build 004 — step logging to diagnose crash during import

import servicemanager
servicemanager.LogInfoMsg("[Gate2] gate2_test_app: step A — importing Flask")
from flask import Flask

servicemanager.LogInfoMsg("[Gate2] gate2_test_app: step B — calling Flask(__name__)")
app = Flask(__name__)

servicemanager.LogInfoMsg("[Gate2] gate2_test_app: step C — registering route")

@app.route('/')
def index():
    return 'Gate2 Test App OK — build 004'

servicemanager.LogInfoMsg("[Gate2] gate2_test_app: step D — module ready")

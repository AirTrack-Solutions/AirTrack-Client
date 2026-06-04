#!/usr/bin/env python3
"""
AirTrack Windows — PyInstaller build script
Run from inside gates/gate3/ on any OS.
Output: gates/gate3/dist/AirTrack/

Usage:
    python3 build.py
    python build.py
"""

import os
import subprocess
import sys
from pathlib import Path

GATE3 = Path(__file__).resolve().parent
REPO  = GATE3.parent.parent
SEP   = ';' if sys.platform == 'win32' else ':'


def run(cmd):
    print(f">>> {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(result.returncode)


run([sys.executable, '-m', 'pip', 'install', 'jaraco.text'])
run([sys.executable, '-m', 'pip', 'install', '-r', str(GATE3 / 'requirements.txt')])

run([
    sys.executable, '-m', 'PyInstaller',
    '--noconfirm',
    '--onedir',
    '--name', 'AirTrack',
    '--paths', str(REPO),
    '--paths', str(REPO / 'app'),
    '--add-data', f'{REPO / "app" / "templates"}{SEP}app/templates',
    '--add-data', f'{REPO / "app" / "static"}{SEP}app/static',
    '--add-data', f'{REPO / "app" / "migrations"}{SEP}app/migrations',
    '--add-data', f'{REPO / "app" / "scripts" / "airports.csv"}{SEP}app/scripts',
    '--add-data', f'{REPO / "app" / "core"}{SEP}app/core',
    '--hidden-import', 'win32timezone',
    '--hidden-import', 'win32service',
    '--hidden-import', 'win32serviceutil',
    '--hidden-import', 'win32event',
    '--hidden-import', 'servicemanager',
    '--hidden-import', 'pywintypes',
    '--hidden-import', 'waitress',
    '--hidden-import', 'pymysql',
    '--hidden-import', 'flask',
    '--hidden-import', 'werkzeug',
    '--hidden-import', 'sqlalchemy',
    '--hidden-import', 'flask_sqlalchemy',
    '--hidden-import', 'flask_wtf',
    '--hidden-import', 'pytz',
    '--hidden-import', 'cryptography',
    '--hidden-import', 'webauthn',
    '--hidden-import', 'apscheduler',
    '--hidden-import', 'stripe',
    '--hidden-import', 'paramiko',
    '--hidden-import', 'app.app',
    '--hidden-import', 'version',
    '--hidden-import', 'extensions',
    '--hidden-import', 'routes',
    '--collect-data', 'jaraco',
    '--distpath', str(GATE3 / 'dist'),
    '--workpath', str(GATE3 / 'build'),
    '--specpath', str(GATE3),
    str(GATE3 / 'service.py'),
])

print()
print(f"Build complete. Bundle: {GATE3 / 'dist' / 'AirTrack'}")

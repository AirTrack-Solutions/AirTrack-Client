# AirTrack Windows Service
# Reads airtrack.cfg from the install directory, sets environment, then starts
# the real AirTrack Client Flask application under Waitress.
#
# Run with admin rights:
#   AirTrack.exe install   — register service (Automatic / Delayed start)
#   AirTrack.exe start     — start the service
#   AirTrack.exe stop      — stop the service
#   AirTrack.exe remove    — unregister the service

import configparser
import os
import sys
import threading
from pathlib import Path

import servicemanager
import win32event
import win32service
import win32serviceutil


# ---------------------------------------------------------------------------
# Configuration — must happen before any app import
# ---------------------------------------------------------------------------

def _load_config():
    """Read airtrack.cfg from alongside the executable and populate os.environ."""
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent
    else:
        exe_dir = Path(__file__).parent

    cfg = configparser.ConfigParser()
    cfg.read(exe_dir / 'airtrack.cfg')

    # DATABASE_URI includes host, port, user, password, db name in one string.
    # app.py prefers DATABASE_URI over the individual DB_* vars, so we set this
    # directly to ensure port 3307 is honoured (app.py's URI builder omits port).
    os.environ.setdefault(
        'DATABASE_URI',
        cfg.get('database', 'uri',
                fallback='mysql+pymysql://airtrack:change-me@127.0.0.1:3307/airtrack?charset=utf8mb4')
    )

    # Individual vars — used by mysqldump in admin backup route (future use).
    _db_host = cfg.get('database', 'host', fallback='127.0.0.1')
    _db_port = cfg.get('database', 'port', fallback='3307')
    # Include port in DB_HOST so app.py's second URI construction gets the right port
    os.environ.setdefault('DB_HOST', f'{_db_host}:{_db_port}')
    os.environ.setdefault('DB_PORT', _db_port)
    os.environ.setdefault('DB_NAME',     cfg.get('database', 'name',     fallback='airtrack'))
    os.environ.setdefault('DB_USER',     cfg.get('database', 'user',     fallback='airtrack'))
    os.environ.setdefault('DB_PASSWORD', cfg.get('database', 'password', fallback=''))

    os.environ.setdefault('SECRET_KEY',     cfg.get('app', 'secret_key', fallback='change-me'))
    os.environ.setdefault('AIRTRACK_ROLE',  cfg.get('app', 'role',       fallback='client'))

    # Marmot (Wombat delivery agent)
    wombat_url = cfg.get('wombat', 'url', fallback='')
    customer_id = cfg.get('wombat', 'customer_id', fallback='')
    if wombat_url:
        os.environ.setdefault('WOMBAT_URL', wombat_url)
    if customer_id:
        os.environ.setdefault('AIRTRACK_CUSTOMER_ID', customer_id)

    # AIRTRACK_HOME — where Marmot stores capabilities, registries, logs
    import sys as _sys
    if _sys.platform == 'win32':
        _default_home = os.path.join(os.environ.get('ProgramData', 'C:\\ProgramData'), 'AirTrack')
    else:
        _default_home = '/airtrack_data'
    os.environ.setdefault('AIRTRACK_HOME', cfg.get('app', 'data_dir', fallback=_default_home))

    # Log dir alongside the executable so it survives reinstalls
    log_dir = exe_dir / 'logs'
    log_dir.mkdir(exist_ok=True)
    os.environ.setdefault('AIRTRACK_LOG_DIR', str(log_dir))



def _bootstrap_core():
    """Copy core files from bundle into AIRTRACK_HOME\\core\\ on first run."""
    import shutil
    airtrack_home = Path(os.environ.get(
        'AIRTRACK_HOME',
        os.path.join(os.environ.get('ProgramData', 'C:\\ProgramData'), 'AirTrack')
    ))
    core_dest = airtrack_home / 'core'
    core_dest.mkdir(parents=True, exist_ok=True)

    if getattr(sys, 'frozen', False):
        # PyInstaller --onedir: exe is in the dist root, data is in _internal/
        bundle_core = Path(sys.executable).parent / '_internal' / 'app' / 'core'
    else:
        # Running from source
        bundle_core = Path(__file__).resolve().parent.parent.parent / 'app' / 'core'

    # Write diagnostic log next to the exe — fixed location, always findable
    _diag_log = Path(sys.executable).parent / 'bootstrap_diag.txt'
    try:
        with open(_diag_log, 'w', encoding='utf-8') as _f:
            _f.write(f"exe={sys.executable}\n")
            _f.write(f"frozen={getattr(sys, 'frozen', False)}\n")
            _f.write(f"airtrack_home={airtrack_home}\n")
            _f.write(f"core_dest={core_dest}\n")
            _f.write(f"bundle_core={bundle_core}\n")
            _f.write(f"bundle_core.exists()={bundle_core.exists()}\n")
            for filename in ('airtrack_solutions.pub', 'package_installer.py'):
                dest_file = core_dest / filename
                src_file = bundle_core / filename
                _f.write(f"{filename}: src_is_file={src_file.is_file()} dest_exists={dest_file.exists()}\n")
                if not dest_file.exists() and src_file.is_file():
                    shutil.copy2(src_file, dest_file)
                    _f.write(f"  -> copied OK\n")
    except Exception as _e:
        try:
            with open(_diag_log, 'a', encoding='utf-8') as _f:
                _f.write(f"EXCEPTION: {_e}\n")
        except Exception:
            pass


_load_config()
_bootstrap_core()


# ---------------------------------------------------------------------------
# Windows service
# ---------------------------------------------------------------------------

class AirTrackService(win32serviceutil.ServiceFramework):
    _svc_name_        = 'AirTrackClient'
    _svc_display_name_ = 'AirTrack Client'
    _svc_description_ = 'AirTrack Client — planespotting logbook'

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ''),
        )
        self._start_server()
        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)

    def _start_server(self):
        import io
        # Windows service has no console — redirect stdout/stderr to UTF-8 to handle emoji in app.py
        try:
            if sys.stdout is not None and hasattr(sys.stdout, 'buffer'):
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            if sys.stderr is not None and hasattr(sys.stderr, 'buffer'):
                sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        except Exception:
            pass

        from app.app import app as flask_app
        from waitress import serve

        t = threading.Thread(
            target=serve,
            kwargs={'app': flask_app, 'host': '127.0.0.1', 'port': 5000},
            daemon=True,
        )
        t.start()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _configure_auto_start(svc_name):
    """Upgrade from DEMAND_START to Automatic (Delayed)."""
    scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
    try:
        svc = win32service.OpenService(scm, svc_name, win32service.SERVICE_CHANGE_CONFIG)
        try:
            win32service.ChangeServiceConfig(
                svc,
                win32service.SERVICE_NO_CHANGE,
                win32service.SERVICE_AUTO_START,
                win32service.SERVICE_NO_CHANGE,
                None, None, 0, None, None, None, None,
            )
            win32service.ChangeServiceConfig2(
                svc,
                win32service.SERVICE_CONFIG_DELAYED_AUTO_START_INFO,
                True,
            )
            print(f'{svc_name}: start type set to Automatic (Delayed).')
        finally:
            win32service.CloseServiceHandle(svc)
    finally:
        win32service.CloseServiceHandle(scm)


def main():
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(AirTrackService)
        servicemanager.StartServiceCtrlDispatcher()
    elif len(sys.argv) >= 2 and sys.argv[1].lower() == 'install':
        win32serviceutil.HandleCommandLine(AirTrackService)
        _configure_auto_start(AirTrackService._svc_name_)
    else:
        win32serviceutil.HandleCommandLine(AirTrackService)


if __name__ == '__main__':
    main()

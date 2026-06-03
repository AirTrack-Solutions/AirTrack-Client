# Gate 2 — build 010
# All Flask/waitress imports done at module level (main thread, before
# StartServiceCtrlDispatcher). Inside SvcDoRun these are sys.modules lookups
# only — avoids import-lock crash in the Windows service thread.

import sys
import threading

import servicemanager
import win32event
import win32service
import win32serviceutil

# --- Preload everything needed by _start_server ---
import re          # noqa: E402
import markupsafe  # noqa: E402
import jinja2      # noqa: E402
import werkzeug    # noqa: E402
import flask       # noqa: E402
from flask import Flask
import waitress    # noqa: E402
from waitress import serve as _waitress_serve
# --------------------------------------------------


class AirTrackGate2Service(win32serviceutil.ServiceFramework):
    _svc_name_ = 'AirTrackGate2'
    _svc_display_name_ = 'AirTrack Gate 2 Test'
    _svc_description_ = 'AirTrack Gate 2 proof of concept — safe to remove'

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
        sm = servicemanager

        sm.LogInfoMsg("[Gate2] build 010: creating Flask app")
        flask_app = Flask('gate2_inline')

        @flask_app.route('/')
        def index():
            return 'Gate2 Test OK — build 010 — preloaded imports'

        sm.LogInfoMsg("[Gate2] build 010: starting waitress thread")
        t = threading.Thread(
            target=_waitress_serve,
            kwargs={'app': flask_app, 'host': '127.0.0.1', 'port': 5000},
            daemon=True,
        )
        t.start()
        sm.LogInfoMsg("[Gate2] build 010: thread started")


def _configure_auto_start(svc_name):
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
        servicemanager.PrepareToHostSingle(AirTrackGate2Service)
        servicemanager.StartServiceCtrlDispatcher()
    elif len(sys.argv) >= 2 and sys.argv[1].lower() == 'install':
        win32serviceutil.HandleCommandLine(AirTrackGate2Service)
        _configure_auto_start(AirTrackGate2Service._svc_name_)
    else:
        win32serviceutil.HandleCommandLine(AirTrackGate2Service)


if __name__ == '__main__':
    main()

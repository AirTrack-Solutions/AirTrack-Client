# Gate 2 — build 009 — granular markupsafe import diagnosis

import sys
import threading

import servicemanager
import win32event
import win32service
import win32serviceutil


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

        sm.LogInfoMsg("[Gate2] 1: import re")
        import re

        sm.LogInfoMsg("[Gate2] 2: import string")
        import string

        sm.LogInfoMsg("[Gate2] 3: import typing")
        import typing

        sm.LogInfoMsg("[Gate2] 4: import functools")
        import functools

        sm.LogInfoMsg("[Gate2] 5: import markupsafe._native")
        import markupsafe._native

        sm.LogInfoMsg("[Gate2] 6: import markupsafe")
        import markupsafe

        sm.LogInfoMsg("[Gate2] 7: import jinja2")
        import jinja2

        sm.LogInfoMsg("[Gate2] 8: import werkzeug")
        import werkzeug

        sm.LogInfoMsg("[Gate2] 9: from flask import Flask")
        from flask import Flask

        sm.LogInfoMsg("[Gate2] 10: Flask('gate2_inline')")
        flask_app = Flask('gate2_inline')

        sm.LogInfoMsg("[Gate2] 11: registering route")

        @flask_app.route('/')
        def index():
            return 'Gate2 OK — build 009'

        sm.LogInfoMsg("[Gate2] 12: from waitress import serve")
        from waitress import serve

        sm.LogInfoMsg("[Gate2] 13: starting thread")
        t = threading.Thread(
            target=serve,
            kwargs={'app': flask_app, 'host': '127.0.0.1', 'port': 5000},
            daemon=True,
        )
        t.start()

        sm.LogInfoMsg("[Gate2] 14: thread started — build 009 running")


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

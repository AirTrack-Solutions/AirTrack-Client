# Gate 2 — build 014 — diagnose Flask() constructor crash step by step

import sys
import os
import threading

import servicemanager
import win32event
import win32service
import win32serviceutil

import flask
import werkzeug
import jinja2
import markupsafe
import waitress
from flask import Flask
from waitress import serve as _serve


class _DiagFlask(Flask):
    """Flask subclass that logs each constructor phase to the event log."""

    def create_jinja_environment(self):
        servicemanager.LogInfoMsg("[Gate2] Flask: create_jinja_environment()")
        result = super().create_jinja_environment()
        servicemanager.LogInfoMsg("[Gate2] Flask: create_jinja_environment() done")
        return result

    def make_config(self, instance_relative=False):
        servicemanager.LogInfoMsg("[Gate2] Flask: make_config()")
        return super().make_config(instance_relative)

    def _get_instance_path(self):
        servicemanager.LogInfoMsg("[Gate2] Flask: _get_instance_path()")
        return super()._get_instance_path()


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
        if getattr(sys, 'frozen', False):
            root = os.path.dirname(sys.executable)
        else:
            root = os.path.dirname(os.path.abspath(__file__))

        servicemanager.LogInfoMsg(f"[Gate2] build 014: root={root}")
        servicemanager.LogInfoMsg("[Gate2] build 014: constructing _DiagFlask")

        flask_app = _DiagFlask(__name__, root_path=root)

        servicemanager.LogInfoMsg("[Gate2] build 014: Flask constructed, registering route")

        @flask_app.route('/')
        def index():
            return 'Gate2 Test OK — build 014'

        servicemanager.LogInfoMsg("[Gate2] build 014: starting waitress")
        t = threading.Thread(
            target=_serve,
            kwargs={'app': flask_app, 'host': '127.0.0.1', 'port': 5000},
            daemon=True,
        )
        t.start()
        servicemanager.LogInfoMsg("[Gate2] build 014: thread started")


def _configure_auto_start(svc_name):
    scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
    try:
        svc = win32service.OpenService(scm, svc_name, win32service.SERVICE_CHANGE_CONFIG)
        try:
            win32service.ChangeServiceConfig(
                svc, win32service.SERVICE_NO_CHANGE, win32service.SERVICE_AUTO_START,
                win32service.SERVICE_NO_CHANGE, None, None, 0, None, None, None, None,
            )
            win32service.ChangeServiceConfig2(
                svc, win32service.SERVICE_CONFIG_DELAYED_AUTO_START_INFO, True,
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

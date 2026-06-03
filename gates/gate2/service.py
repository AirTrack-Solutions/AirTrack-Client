# Gate 2 -- build 016 -- narrow down thread crash + avoid lazy imports in thread

import sys
import os
import threading

import servicemanager
import win32event
import win32service
import win32serviceutil

# Preload all waitress internals so the new thread does no imports
import waitress
import waitress.server
import waitress.task
import waitress.channel
import waitress.utilities
import waitress.buffers
import waitress.adjustments
from waitress import create_server


def _simple_app(environ, start_response):
    status = '200 OK'
    headers = [('Content-Type', 'text/plain; charset=utf-8')]
    start_response(status, headers)
    return [b'Gate2 OK -- build 016']


class AirTrackGate2Service(win32serviceutil.ServiceFramework):
    _svc_name_ = 'AirTrackGate2'
    _svc_display_name_ = 'AirTrack Gate 2 Test'
    _svc_description_ = 'AirTrack Gate 2 proof of concept -- safe to remove'

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
        servicemanager.LogInfoMsg("[Gate2] build 016: creating server")
        server = create_server(_simple_app, host='127.0.0.1', port=5000)

        servicemanager.LogInfoMsg("[Gate2] build 016: creating Thread")
        t = threading.Thread(target=server.run, daemon=True)

        servicemanager.LogInfoMsg("[Gate2] build 016: calling t.start()")
        t.start()

        servicemanager.LogInfoMsg("[Gate2] build 016: thread started -- waiting")
        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)


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

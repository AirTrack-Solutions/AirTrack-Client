# Gate 2 -- build 018 -- step-by-step socket diagnosis

import sys
import os
import socket
import threading

import servicemanager
import win32event
import win32service
import win32serviceutil


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
        servicemanager.LogInfoMsg("[Gate2] build 018: step 1 -- socket.socket()")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        servicemanager.LogInfoMsg("[Gate2] build 018: step 2 -- setsockopt")
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        servicemanager.LogInfoMsg("[Gate2] build 018: step 3 -- bind")
        s.bind(('127.0.0.1', 5000))

        servicemanager.LogInfoMsg("[Gate2] build 018: step 4 -- listen")
        s.listen(5)

        servicemanager.LogInfoMsg("[Gate2] build 018: step 5 -- socket OK, closing")
        s.close()

        servicemanager.LogInfoMsg("[Gate2] build 018: step 6 -- creating Thread (no server)")
        t = threading.Thread(target=lambda: None, daemon=True)

        servicemanager.LogInfoMsg("[Gate2] build 018: step 7 -- t.start()")
        t.start()

        servicemanager.LogInfoMsg("[Gate2] build 018: all steps passed -- waiting")
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

# Gate 2 proof of concept — pywin32 Windows service wrapping Flask + Waitress
# Run with admin rights:
#   AirTrack.exe install   — register the service
#   AirTrack.exe start     — start the service
#   AirTrack.exe stop      — stop the service
#   AirTrack.exe remove    — unregister the service

import sys
import threading

import servicemanager
import win32event
import win32service
import win32serviceutil


class AirTrackService(win32serviceutil.ServiceFramework):
    _svc_name_ = 'AirTrack'
    _svc_display_name_ = 'AirTrack'
    _svc_description_ = 'AirTrack Gate 2 proof of concept'

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
        # Block until stop signal
        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)

    def _start_server(self):
        from app import app as flask_app
        from waitress import serve

        t = threading.Thread(
            target=serve,
            kwargs={'app': flask_app, 'host': '127.0.0.1', 'port': 5000},
            daemon=True,
        )
        t.start()


def main():
    if len(sys.argv) == 1:
        # Called by the Windows service dispatcher — no CLI args
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(AirTrackService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        # Called with install / start / stop / remove
        win32serviceutil.HandleCommandLine(AirTrackService)


if __name__ == '__main__':
    main()

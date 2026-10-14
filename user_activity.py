"""Local activity metadata only; no titles, screenshots, hooks or networking."""
import ctypes
import sys
from dataclasses import dataclass
from datetime import timedelta

@dataclass(frozen=True)
class ActivityState:
    idle_duration: float | None = None
    last_input_time: str | None = None
    active_window: str | None = None
    user_active: bool = False
    busy: bool = True
    available: bool = False

class WindowsActivityProvider:
    def __init__(self, active_seconds=60):
        self.active_seconds = active_seconds

    def read(self, now):
        try:
            if sys.platform != 'win32':
                return ActivityState()
            from ctypes import wintypes
            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [('cbSize', wintypes.UINT), ('dwTime', wintypes.DWORD)]
            user = ctypes.WinDLL('user32', use_last_error=True)
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            user.GetForegroundWindow.restype = wintypes.HWND
            user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
            kernel.GetTickCount.restype = wintypes.DWORD
            info = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
            if not user.GetLastInputInfo(ctypes.byref(info)):
                return ActivityState()
            idle = ((kernel.GetTickCount() - info.dwTime) & 0xffffffff) / 1000
            pid = wintypes.DWORD()
            hwnd = user.GetForegroundWindow()
            if not hwnd or not user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)):
                return ActivityState()
            # Foreground process ID avoids collecting private window titles.
            active = idle < self.active_seconds
            return ActivityState(idle, (now-timedelta(seconds=idle)).isoformat(),
                                 f'pid:{pid.value}', active, active, True)
        except Exception:
            return ActivityState()

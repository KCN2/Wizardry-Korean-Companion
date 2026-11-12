"""
wiz_hook.py - DOSBox Memory Hook Engine for Wizardry 1
Connects to DOSBox process and reads real-mode DOS conventional RAM.
"""

import ctypes
from ctypes import wintypes
import time

PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_QUERY_INFORMATION = 0x0400

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32

class RECT(ctypes.Structure):
    _fields_ = [('left', wintypes.LONG), ('top', wintypes.LONG), ('right', wintypes.LONG), ('bottom', wintypes.LONG)]

class POINT(ctypes.Structure):
    _fields_ = [('x', wintypes.LONG), ('y', wintypes.LONG)]

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", wintypes.LPVOID),
        ("AllocationBase", wintypes.LPVOID),
        ("AllocationProtect", wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD)
    ]

class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]


kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE


class DOSBoxHook:
    def __init__(self):
        self.pid = None
        self.handle = None
        self.dos_base = None
        self.hwnd = None

    def find_dosbox_pid(self):
        """PID of a running DOSBox (process name starting with "dosbox"), or None.

        Toolhelp snapshot: starting PowerShell for this took 0.8 s and froze
        the window at start and on every reconnect try while DOSBox was closed.
        """
        snap = kernel32.CreateToolhelp32Snapshot(0x2, 0)   # TH32CS_SNAPPROCESS
        if not snap or snap == ctypes.c_void_p(-1).value:   # INVALID_HANDLE_VALUE
            return None
        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(entry)
            ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
            while ok:
                if entry.szExeFile.lower().startswith("dosbox"):
                    return entry.th32ProcessID
                ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
            return None
        finally:
            kernel32.CloseHandle(snap)

    def find_dosbox_hwnd(self):
        """Visible top-level window of the DOSBox process already opened.

        A title search is not enough. Another window, such as a terminal whose
        tab name mentions DOSBox, is a different process and has no game memory.
        """
        if not self.pid:
            return None
        titled = []

        def enum_cb(hwnd, lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            window_pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
            if int(window_pid.value) != int(self.pid):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            titled.append((hwnd, buf.value))
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        for hwnd, title in titled:
            if "DOSBox" in title:
                return hwnd
        return titled[0][0] if titled else None

    def get_client_rect_on_screen(self):
        """Returns (x, y, width, height) of DOSBox game rendering client area."""
        if not self.hwnd or not user32.IsWindow(self.hwnd):
            return None
        crect = RECT()
        if not user32.GetClientRect(self.hwnd, ctypes.byref(crect)):
            return None
        pt = POINT(crect.left, crect.top)
        user32.ClientToScreen(self.hwnd, ctypes.byref(pt))
        w = crect.right - crect.left
        h = crect.bottom - crect.top
        return (pt.x, pt.y, w, h)

    def connect(self, require_signature=False):
        """Connects to DOSBox and resolves the DOS conventional memory base address.

        require_signature: only the block with the DOSBox BIOS string counts.
        Right after launch the string is not written yet, and the fallback
        (first large block) could pick the wrong one.
        """
        self.pid = self.find_dosbox_pid()
        if not self.pid:
            return False

        desired_access = PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION | PROCESS_QUERY_INFORMATION
        self.handle = kernel32.OpenProcess(desired_access, False, self.pid)
        if not self.handle:
            return False

        self.hwnd = self.find_dosbox_hwnd()
        self.dos_base = self._find_dos_base(require_signature)
        if self.dos_base is None or not self.hwnd:
            # DOSBox just started: no window or emulated RAM yet. Close the
            # handle so the next poll tries again. A handle left open counted as
            # a live connection and the overlay waited for a manual reconnect.
            self.close()
            self.pid = None
            self.hwnd = None
            self.dos_base = None
            return False
        return True

    # wiz_hook.py의 _find_dos_base 교체
    def _find_dos_base(self, require_signature=False):
        """Scans process memory for the 16MB/32MB DOSBox RAM block."""
        mbi = MEMORY_BASIC_INFORMATION()
        addr = 0
        MEM_COMMIT = 0x1000
        PAGE_READWRITE = 0x04

        candidates = []
        while kernel32.VirtualQueryEx(self.handle, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            base_val = mbi.BaseAddress or 0
            if mbi.State == MEM_COMMIT and (mbi.Protect & 0xFF) == PAGE_READWRITE and mbi.RegionSize >= 0x1000000:
                buf = (ctypes.c_char * 64)()
                bytesRead = ctypes.c_size_t()
                if kernel32.ReadProcessMemory(self.handle, ctypes.c_void_p(base_val + 0xFE054), buf, len(buf), ctypes.byref(bytesRead)):
                    if b'DOSBox' in bytes(buf):
                        return base_val
                candidates.append(base_val)
            addr = base_val + mbi.RegionSize
            if addr >= 0x7FFFFFFF0000:
                break
        
        # 서명 매칭 실패 시 첫 번째 16MB 할당 블록 반환
        if candidates and not require_signature:
            return candidates[0]
        return None
        
    def is_alive(self):
        if not self.handle:
            return False
        exit_code = wintypes.DWORD()
        if kernel32.GetExitCodeProcess(self.handle, ctypes.byref(exit_code)):
            STILL_ACTIVE = 259
            return exit_code.value == STILL_ACTIVE
        return False

    def read_bytes(self, dos_addr, size):
        if not self.handle or self.dos_base is None:
            return None
        buf = (ctypes.c_char * size)()
        bytesRead = ctypes.c_size_t()
        target = ctypes.c_void_p(self.dos_base + dos_addr)
        if kernel32.ReadProcessMemory(self.handle, target, buf, size, ctypes.byref(bytesRead)):
            return bytes(buf)
        return None

    def write_bytes(self, dos_addr, data):
        """Writes bytes to DOSBox conventional memory."""
        if not self.handle or self.dos_base is None:
            return False
        buf = (ctypes.c_char * len(data)).from_buffer_copy(data)
        bytesWritten = ctypes.c_size_t()
        target = ctypes.c_void_p(self.dos_base + dos_addr)
        return bool(kernel32.WriteProcessMemory(self.handle, target, buf, len(data), ctypes.byref(bytesWritten)))

    def close(self):
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

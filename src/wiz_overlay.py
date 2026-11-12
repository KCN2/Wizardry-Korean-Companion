"""
wiz_overlay.py - Wizardry Dual Mode Korean System
Provides both:
  1. Sidecar companion: connection, stat protection, overlay switch, game launcher, spell list, map, character-creation button.
  2. In-Game Transparent Overlay (Authentic retro screen-replacement with original hotkeys)
Switch between companion and overlay modes with the visible control button.
"""

import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, filedialog
import subprocess

from wiz_build_flags import RELEASE
import ctypes
from ctypes import wintypes
import json
import math
import os
import sys
import time
import re
from PIL import Image, ImageTk

# Enable Per-Monitor High-DPI Awareness on Windows
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Tk's after(2) stays on the 15.6ms system tick unless the process asks for 1ms.
try:
    ctypes.windll.winmm.timeBeginPeriod(1)
except Exception:
    pass

user32 = ctypes.windll.user32
GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_CAPTION = 0x00C00000
GWLP_HWNDPARENT = -8
WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
GW_HWNDPREV = 3
GA_ROOT = 2

user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindow.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetParent.restype = wintypes.HWND
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.UINT,
]
user32.SetWindowPos.restype = wintypes.BOOL
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int

class MONITORINFO(ctypes.Structure):
    _fields_ = (
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    )

user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.MonitorFromWindow.restype = ctypes.c_void_p
user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
user32.GetMonitorInfoW.restype = wintypes.BOOL
user32.RedrawWindow.argtypes = [wintypes.HWND, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
user32.RedrawWindow.restype = wintypes.BOOL
RDW_INVALIDATE = 0x0001
RDW_UPDATENOW = 0x0100
RDW_ALLCHILDREN = 0x0080
_set_owner = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
_set_owner.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
_set_owner.restype = ctypes.c_ssize_t

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_EXTENDEDKEY = 0x0001
INPUT_KEYBOARD = 1

class KEYBDINPUT(ctypes.Structure):
    _fields_ = (
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )

class MOUSEINPUT(ctypes.Structure):
    _fields_ = (
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )

class _INPUTUNION(ctypes.Union):
    _fields_ = (("mi", MOUSEINPUT), ("ki", KEYBDINPUT))

class INPUT(ctypes.Structure):
    _fields_ = (("type", wintypes.DWORD), ("u", _INPUTUNION))

user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ULONG_PTR]
user32.keybd_event.restype = None
ctypes.windll.kernel32.GetCurrentThreadId.restype = wintypes.DWORD

_LETTER_SCAN = {
    "A": 0x1E, "B": 0x30, "C": 0x2E, "D": 0x20, "E": 0x12, "F": 0x21,
    "G": 0x22, "H": 0x23, "I": 0x17, "J": 0x24, "K": 0x25, "L": 0x26,
    "M": 0x32, "N": 0x31, "O": 0x18, "P": 0x19, "Q": 0x10, "R": 0x13,
    "S": 0x1F, "T": 0x14, "U": 0x16, "V": 0x2F, "W": 0x11, "X": 0x2D,
    "Y": 0x15, "Z": 0x2C,
    "ENTER": 0x1C, "ESC": 0x01, "UP": 0x48, "+": 0x0D,
}

def _bios_key_word(key):
    """BIOS keyboard word: high byte is the scan code, low byte is the ASCII code."""
    scan = _LETTER_SCAN.get(key)
    if scan is None:
        return None
    if isinstance(key, str) and len(key) == 1 and "A" <= key <= "Z":
        return (scan << 8) | ord(key)
    if key == "ENTER":
        return (scan << 8) | 0x0D
    if key == "ESC":
        return (scan << 8) | 0x1B
    if key == "UP":
        return scan << 8
    if key == "+":
        return (scan << 8) | ord('+')
    return None

_TRAINING_STATES = {
    21048, 21782, 21122, 22178, 21154, 23166,
    21082, 21126, 21078, 21448, 20888,
}
_MAP_CELL = 18
_MAP_PAD = 8
_MAP_KIND_FILL = (
    "#1e1e2e", "#a6e3a1", "#fab387", "#cba6f7", "#f9e2af", "#45475a",
    "#89b4fa", "#f38ba8", "#94e2d5", "#11111b", "#b4befe", "#f5c2e7", "#eba0ac",
)
_MAP_KIND_KO = (
    "일반", "계단", "함정", "슈트", "회전", "암흑",
    "이동", "피해", "승강기", "바위", "주문 무효", "메시지", "조우",
)
_MAP_WALL_KO = {0: "열림", 1: "벽", 2: "문", 3: "숨은 문"}
_MAP_FLOOR_FILL = "#1e1e2e"
# Squares that take the party to another level (stairs, elevator) share a colour.
_MAP_LEVEL_COLOR = "#94e2d5"
# Kinds that cover areas keep a tint; single squares get an icon instead.
_MAP_AREA_FILL = {5: "#75618f", 9: "#585b70", 10: "#2a3540"}   # dark, rock, fizzle


def _draw_map_icon(canvas, kind, px, py, cell, stairs_dir=None):
    """Icon for a square type (Wizardry TSQUARE order)."""
    c, m = cell, cell / 2
    cx, cy = px + m, py + m
    line = dict(width=max(1, int(c / 12)), capstyle="round")
    if kind == 1:   # STAIRS: three steps; up arrow top right, down arrow bottom left
        s = c * .18
        x0 = px + c * {'up': .06, 'down': .4}.get(stairs_dir, .2)
        y0 = py + c * {'up': .9, 'down': .62}.get(stairs_dir, .8)
        canvas.create_line(x0, y0, x0 + s, y0, x0 + s, y0 - s, x0 + 2 * s, y0 - s, x0 + 2 * s, y0 - 2 * s,
                           x0 + 3 * s, y0 - 2 * s, x0 + 3 * s, y0 - 3 * s, fill=_MAP_LEVEL_COLOR, **line)
        if stairs_dir == 'up':
            canvas.create_polygon(px + c * .64, py + c * .34, px + c * .98, py + c * .34, px + c * .81, py + c * .04,
                                  fill=_MAP_LEVEL_COLOR, outline="")
        elif stairs_dir == 'down':
            canvas.create_polygon(px + c * .03, py + c * .62, px + c * .37, py + c * .62, px + c * .2, py + c * .94,
                                  fill=_MAP_LEVEL_COLOR, outline="")
    elif kind == 2:   # PIT: a hole
        canvas.create_oval(px + c * .22, py + c * .32, px + c * .78, py + c * .68,
                           fill="#000000", outline="#fab387", width=line["width"])
    elif kind == 3:   # CHUTE: arrow down into a hole
        canvas.create_oval(px + c * .25, py + c * .62, px + c * .75, py + c * .85, fill="#000000", outline="#cba6f7")
        canvas.create_line(cx, py + c * .15, cx, py + c * .6, fill="#cba6f7", arrow="last", **line)
    elif kind == 4:   # SPINNER: circular arrow
        canvas.create_arc(px + c * .2, py + c * .2, px + c * .8, py + c * .8, start=30, extent=280,
                          style="arc", outline="#f38ba8", width=line["width"])
        canvas.create_polygon(px + c * .78, py + c * .2, px + c * .88, py + c * .45, px + c * .62, py + c * .38,
                              fill="#f38ba8", outline="")
    elif kind == 6:   # TRANSFER: portal rings
        for r in (.32, .2):
            canvas.create_oval(cx - c * r, cy - c * r, cx + c * r, cy + c * r, outline="#89b4fa", width=line["width"])
    elif kind == 7:   # OUCHY: spikes
        canvas.create_line(px + c * .2, py + c * .75, px + c * .35, py + c * .3, px + c * .5, py + c * .75,
                           px + c * .65, py + c * .3, px + c * .8, py + c * .75, fill="#f38ba8", **line)
    elif kind == 8:   # BUTTONZ (elevator): up and down
        canvas.create_polygon(cx, py + c * .1, px + c * .28, py + c * .42, px + c * .72, py + c * .42, fill=_MAP_LEVEL_COLOR, outline="")
        canvas.create_polygon(cx, py + c * .9, px + c * .28, py + c * .58, px + c * .72, py + c * .58, fill=_MAP_LEVEL_COLOR, outline="")
    elif kind == 10:  # FIZZLE: circle with a slash
        canvas.create_oval(px + c * .3, py + c * .3, px + c * .7, py + c * .7, outline="#89dceb", width=1)
        canvas.create_line(px + c * .36, py + c * .64, px + c * .64, py + c * .36, fill="#89dceb", width=1)
    elif kind == 11:  # SCNMSG: message
        canvas.create_rectangle(px + c * .22, py + c * .25, px + c * .78, py + c * .65, outline="#f5e0dc", width=line["width"])
        canvas.create_line(px + c * .35, py + c * .65, px + c * .3, py + c * .8, px + c * .48, py + c * .65,
                           fill="#f5e0dc", width=line["width"])
    elif kind == 12:  # ENCOUNTE: fixed fight, crossed swords
        canvas.create_line(px + c * .22, py + c * .22, px + c * .78, py + c * .78, fill="#f38ba8", **line)
        canvas.create_line(px + c * .78, py + c * .22, px + c * .22, py + c * .78, fill="#f38ba8", **line)


def _draw_spot_icon(canvas, name, px, py, cell):
    """Icon for a named spot from WhereAreWe (keys, statues, monsters...)."""
    c = cell
    w = max(1, int(c / 12))
    if name.endswith("Key"):
        color = {"Silver Key": "#cdd6f4", "Bronze Key": "#e5a50a", "Gold Key": "#f9e2af"}.get(name, "#f9e2af")
        canvas.create_oval(px + c * .18, py + c * .35, px + c * .42, py + c * .6, outline=color, width=w)
        canvas.create_line(px + c * .42, py + c * .48, px + c * .82, py + c * .48, px + c * .82, py + c * .62,
                           fill=color, width=w)
        canvas.create_line(px + c * .68, py + c * .48, px + c * .68, py + c * .6, fill=color, width=w)
    elif name.endswith("Statue"):
        canvas.create_oval(px + c * .4, py + c * .18, px + c * .6, py + c * .38, fill="#a6adc8", outline="")
        canvas.create_rectangle(px + c * .38, py + c * .38, px + c * .62, py + c * .66, fill="#a6adc8", outline="")
        canvas.create_rectangle(px + c * .26, py + c * .66, px + c * .74, py + c * .8, fill="#7f849c", outline="")
    elif name == "Blue Ribbon":
        canvas.create_polygon(px + c * .5, py + c * .5, px + c * .3, py + c * .85, px + c * .42, py + c * .8,
                              px + c * .5, py + c * .5, px + c * .58, py + c * .8, px + c * .7, py + c * .85,
                              fill="#89b4fa", outline="")
        canvas.create_oval(px + c * .32, py + c * .15, px + c * .68, py + c * .5, fill="#89b4fa", outline="")
    elif name.endswith("Fog"):
        for k in (.35, .5, .65):
            canvas.create_line(px + c * .2, py + c * k, px + c * .8, py + c * k, fill="#bac2de", width=w, dash=(2, 2))
    elif name.endswith("Door"):   # Bear Door, Frog Door: a door that needs a statue
        color = "#e5a50a"
        canvas.create_rectangle(px + c * .3, py + c * .2, px + c * .7, py + c * .82, outline=color, width=w)
        canvas.create_oval(px + c * .56, py + c * .5, px + c * .64, py + c * .58, fill=color, outline="")
    elif name.startswith("Teleport") or name == "Chute":
        canvas.create_oval(px + c * .38, py + c * .38, px + c * .62, py + c * .62, fill="#89b4fa", outline="")
    elif name == "Item":   # a small chest
        canvas.create_rectangle(px + c * .25, py + c * .4, px + c * .75, py + c * .75, fill="#e5a50a", outline="")
        canvas.create_line(px + c * .25, py + c * .52, px + c * .75, py + c * .52, fill="#11111b", width=w)
    elif name.startswith("Stairs"):
        pass   # the square type already draws the stairs and their direction
    elif name == "소환 오행성":   # a five-pointed star
        points = []
        for k in range(10):
            r = c * (.36 if k % 2 == 0 else .15)
            angle = math.pi * (k / 5 - .5)
            points += [px + c * .5 + r * math.cos(angle), py + c * .5 + r * math.sin(angle)]
        canvas.create_polygon(points, fill="#cba6f7", outline="")
    elif "시작 지점" in name:   # where the game begins
        canvas.create_polygon(px + c * .5, py + c * .2, px + c * .8, py + c * .5, px + c * .5, py + c * .8,
                              px + c * .2, py + c * .5, fill="", outline="#f9e2af", width=w)
    elif name in ("Pool", "Fountain", "Fountain of Youth"):   # a drop of water
        canvas.create_polygon(px + c * .5, py + c * .18, px + c * .34, py + c * .52, px + c * .66, py + c * .52,
                              fill="#89dceb", outline="")
        canvas.create_oval(px + c * .32, py + c * .38, px + c * .68, py + c * .74, fill="#89dceb", outline="")
    elif name == "Altar":
        canvas.create_rectangle(px + c * .22, py + c * .4, px + c * .78, py + c * .5, fill="#f9e2af", outline="")
        canvas.create_rectangle(px + c * .32, py + c * .5, px + c * .68, py + c * .78, fill="#f9e2af", outline="")
    elif name.startswith("Orb"):
        canvas.create_oval(px + c * .3, py + c * .3, px + c * .7, py + c * .7, fill="#cba6f7", outline="#f5e0dc", width=w)
    else:   # monsters and guardians: a red mark
        canvas.create_oval(px + c * .3, py + c * .25, px + c * .7, py + c * .62, fill="#f38ba8", outline="")
        canvas.create_rectangle(px + c * .38, py + c * .55, px + c * .62, py + c * .75, fill="#f38ba8", outline="")
        canvas.create_oval(px + c * .38, py + c * .35, px + c * .47, py + c * .45, fill="#11111b", outline="")
        canvas.create_oval(px + c * .53, py + c * .35, px + c * .62, py + c * .45, fill="#11111b", outline="")
_MAP_UNSEEN_FILL = "#08080c"
# Squares the 3D view shows ahead of the party: the party's own square plus
# this many in the facing direction, stopping at the first wall or door.
# Approximation of the game's view depth, not read from the game.
_VIEW_DARK = 1
_VIEW_LIT = 3
_SIDES = ("north", "east", "south", "west")
_STEP = ((0, 1), (1, 0), (0, -1), (-1, 0))


def _app_dir():
    """Next to the exe (next to the script when run from source)."""
    return (os.path.dirname(sys.executable) if getattr(sys, 'frozen', False)
            else os.path.dirname(os.path.abspath(__file__)))


def _explored_path(game=1):
    return os.path.join(_app_dir(), f"wiz{game}_explored.json")


_SETTINGS_FILE = "wiz_overlay_settings.json"
_DOSBOX_CONF_FILE = "wiz_dosbox.conf"
# Names before 1.1 (the program once covered only Wizardry 1).
_OLD_SETTINGS_FILE, _OLD_DOSBOX_CONF_FILE = "wiz1_overlay_settings.json", "wiz1_dosbox.conf"
# Written on every launch and passed after -userconf, so these win over the
# user's own DOSBox settings. desktop: the monitor mode does not change (an
# original-size fullscreen switched the desktop to 640x480 and moved every
# window). ddraw: scales the picture and keeps a window over it visible;
# opengl fullscreen hid the whole overlay. aspect=true: the picture is 4:3,
# which _fit_game_rect assumes for a borderless fullscreen.
# autolock=false: DOSBox does not grab the mouse, so our buttons can be clicked.
_DOSBOX_CONF = """[sdl]
fullresolution=desktop
windowresolution={window}
output=ddraw
autolock=false

[render]
aspect=true

[dosbox]
machine=cga
"""


def _guess_dosbox():
    """DOSBox.exe in the usual install folders, or ''. No personal paths."""
    bases = [os.environ.get(k) for k in ("ProgramFiles(x86)", "ProgramFiles", "ProgramW6432")]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        bases.append(os.path.join(local, "Programs"))
    for base in filter(None, bases):
        try:
            names = sorted(os.listdir(base), reverse=True)   # newest version first
        except OSError:
            continue
        for name in names:
            if name.lower().startswith("dosbox"):
                exe = os.path.join(base, name, "DOSBox.exe")
                if os.path.isfile(exe):
                    return exe
    return ""


def _guess_wiz_dir():
    """A folder with WIZ1.COM next to the exe, one level up, or one level down."""
    here = _app_dir()
    for base in (here, os.path.dirname(here)):
        try:
            entries = os.listdir(base)
        except OSError:
            continue
        if any(e.upper() == "WIZ1.COM" for e in entries):
            return base
        for e in sorted(entries):
            sub = os.path.join(base, e)
            try:
                if os.path.isdir(sub) and any(n.upper() == "WIZ1.COM" for n in os.listdir(sub)):
                    return sub
            except OSError:
                continue
    return ""


# Companion choice -> share of the largest window; None is DOSBox's own size.
# DOSBox 0.74 cannot resize its window after it starts, so this is read at launch.
_WINDOW_SIZES = (("최대", 1.0), ("75%", 0.75), ("50%", 0.5), ("원본", None))


def _big_window_size(scale=1.0):
    """Largest 4:3 DOSBox window that fits the work area with its frame, times scale.

    DOSBox 0.74 grabs the mouse in fullscreen whatever autolock says, so the
    overlay buttons cannot be clicked there. A window this size works.
    """
    if scale is None:
        return "original"
    try:
        area = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(area), 0)  # SPI_GETWORKAREA
        gsm = ctypes.windll.user32.GetSystemMetrics
        frame_h = gsm(4) + 2 * (gsm(33) + gsm(92)) + 8   # caption + sizing frame + padding
        frame_w = 2 * (gsm(32) + gsm(92)) + 8
        h = (area.bottom - area.top) - frame_h
        w = (area.right - area.left) - frame_w
        if h < 400 or w < 640:
            return "original"
        if w * 3 < h * 4:
            h = w * 3 // 4
        h = max(200, int(h * scale))
        return f"{h * 4 // 3}x{h}"
    except Exception:
        return "original"


_ROSTER_CACHE = {}


def _ucsd_file(disk, wanted):
    """One file from a UCSD Pascal disk image (directory at byte 1024)."""
    u = lambda o: int.from_bytes(disk[o:o + 2], 'little')
    for i in range(1, u(1024 + 16) + 1):
        o = 1024 + i * 26
        if o + 26 > len(disk) or disk[o + 6] > 15:
            break
        if disk[o + 7:o + 7 + disk[o + 6]].decode('latin1') == wanted:
            return disk[u(o) * 512:u(o + 2) * 512]
    return None




# Wizardry 4: the start. The pentagrams are read from the disk (_wiz4_pentagrams).
_MAP_SPOTS_WIZ4 = (
    (11, 10, 9, "베르드나의 묘 (시작 지점)"),
)


def _wiz4_pentagrams(disk, levels):
    """[(level, x, y)] of the pentagrams (where Werdna summons monsters), read only.

    From the game code (SYSTEM.PASCAL, segment SPECIALS): a message square whose
    AUX2 is 200-299 runs the pentagram procedure (the one that prints "THE PENTAGRAM
    GLOWS..."). An AUX2 below -10000 is indirect: the strings numbered -AUX2 and up
    are 10-byte records (x, y, AUX2, AUX1, AUX0 as words) and the one with the
    party's x and y replaces the values. WhereAreWe 1.1.1 lists 31 of the 32 squares
    this finds; the 32nd is floor 5 (10, 10).
    """
    from tools.wiz4_krn_decode import decode_wiz4_strings
    strings = decode_wiz4_strings(disk)
    def record(number):
        text = strings.get(number)
        if text is None or len(text) < 10 or text == '**ERR**':
            return None
        raw = bytes(ord(ch) & 255 for ch in text[:10])
        return [int.from_bytes(raw[k:k + 2], 'little', signed=True) for k in range(0, 10, 2)]
    out = []
    for level in levels:
        for i, extra in enumerate(level['extra']):
            if level['types'][extra] != 11:
                continue
            x, y = i % 20, i // 20
            aux2 = level['aux2'][extra]
            number = -aux2
            while aux2 < -10000:
                rec = record(number)
                if rec is None:
                    break
                if rec[0] == x and rec[1] == y:
                    aux2 = rec[2]
                number += 1
            if 200 <= aux2 < 300:
                out.append((level['level'], x, y))
    return out


def _wiz5_specials(rec):
    """[(world x, world y, kind, Korean name, stairs direction)] of one Wizardry 5 floor.

    ``rec`` is the floor as the game builds it in memory: the first 922 bytes of
    its DRAGON.DATA zone 1 record, then its zone 8 record. 96 special squares:
    type (4 bits) at +922, y and x in the sector (3 bits, five to a word) at +970
    and +1010, sector (4 bits) at +1050, then word arrays at +1194 (B) and +1482,
    bytes at +1386 (C). Meanings from the game code (SYSTEM.PASCAL, RUNNER 64:
    the case on the type when the party steps on the square; RUNNER 68 and
    SPECIAL 1 for the cases) and the game's own words: a type 1 square says
    string 730 + 4B + C (STAIRS LEADING DOWN/UP, LADDER, ROPE, A SHIMMERING
    PORTAL...) or 750 + B - 4 (A CHUTE!, A SHAFT!, A TRAPDOOR!, A SLIDE!).
    """
    def four(o, n):
        return [v for i in range(n) for v in (rec[o + i] & 15, rec[o + i] >> 4)]
    def three(o, n):
        out = []
        for i in range(0, n - 1, 2):
            word = int.from_bytes(rec[o + i:o + i + 2], 'little')
            out += [word >> k & 7 for k in (0, 3, 6, 9, 12)]
        return out
    origins = [(rec[528 + i] - 129, rec[512 + i] - 129) for i in range(16)]
    types, ys, xs, sectors = four(922, 48), three(970, 40), three(1010, 40), four(1050, 48)
    move = {(0, 0): ("내리는 계단", 1, 'down'), (0, 1): ("오르는 계단", 1, 'up'), (0, 2): ("계단", 6, ''),
            (1, 0): ("내리는 사다리", 1, 'down'), (1, 1): ("오르는 사다리", 1, 'up'), (1, 2): ("다리", 6, ''),
            (2, 0): ("내려가는 밧줄", 1, 'down'), (2, 1): ("올라가는 밧줄", 1, 'up'), (2, 2): ("건너는 밧줄", 6, ''),
            (3, 0): ("비밀 통로", 6, ''), (3, 1): ("수상한 터널", 6, ''), (3, 2): ("빛나는 문", 6, '')}
    other = {2: ("미끄럼 바닥", 6), 3: ("이벤트", 11), 4: ("조우", 12), 6: ("이동", 6), 7: ("잠긴 문·장벽", 11),
             8: ("이벤트", 11), 9: ("함정", 2), 10: ("장치", 11), 11: ("이벤트", 11), 12: ("물건", 11),
             13: ("수수께끼", 11), 14: ("물", 11)}
    rank = {1: 0, 3: 0, 8: 0, 6: 1, 2: 2, 12: 3, 4: 4, 11: 5}   # one marker per square: the strongest
    squares = {}
    for i in range(96):
        kind_of = types[i]
        b = int.from_bytes(rec[1194 + 2 * i:1196 + 2 * i], 'little')
        c = rec[1386 + i]
        if kind_of == 0:
            continue
        if kind_of == 1:
            if b < 4:
                name, kind, direction = move.get((b, c), ("이동", 6, ''))
            elif b == 7:
                name, kind, direction = "순간이동", 6, ''
            else:
                name, kind, direction = {4: "슈트", 5: "수직 통로", 6: ("뚜껑문", "함정 문", "미끄럼틀")[min(c, 2)]}[b], 3, ''
                if b == 6 and c == 2:
                    kind = 6
        elif kind_of == 15:
            name, kind, direction = {0: ("버튼(승강기)", 8, ''), 3: ("회전", 4, '')}.get(c, ("메시지", 11, ''))
        else:
            name, kind = other.get(kind_of, ("이벤트", 11))
            direction = ''
        ox, oy = origins[sectors[i]]
        at = (ox + xs[i], oy + ys[i])
        old = squares.get(at)
        if old is None or rank.get(kind, 9) < rank.get(old[1], 9):
            squares[at] = (name, kind, direction)
    return [(x, y, kind, name, direction) for (x, y), (name, kind, direction) in squares.items()]


def _decode_wiz5_maze(rec, floor):
    """WAW Wiz5WallSet: packed east/north walls and sixteen 8x8 sectors."""
    if len(rec) != 1024:
        raise OSError('5편 지도 레코드가 잘렸습니다.')
    origins = [(rec[528 + i] - 129, rec[512 + i] - 129) for i in range(16)]
    # WAW places the disconnected eighth-floor rooms beside the main maze.
    insets = {9: (14, -11), 10: (18, -3), 11: (14, 9), 12: (22, 6),
              13: (-11, 17), 14: (-3, 22), 15: (3, 14)} if floor == 8 else {}
    cells = {}
    world_to_cell = {}
    for sector, origin in enumerate(origins):
        rx, ry = sector % 4 * 8, sector // 4 * 8
        adjacent = any(p != origin and abs(p[0] - origin[0]) <= 8
                       and abs(p[1] - origin[1]) <= 8 for p in origins)
        dest = insets.get(sector, origin if adjacent or origin == (rx, ry) else (rx - 1, ry - 1))
        for dy in range(8):
            for dx in range(8):
                x, y = rx + dx, ry + dy
                world = (origin[0] + dx, origin[1] + dy)
                display = (dest[0] + dx, dest[1] + dy)
                offset = (y // 8) * 64 + x * 2 + (y % 8) // 4
                east = (rec[offset] >> (y % 4 * 2)) & 3
                north = (rec[256 + offset] >> (y % 4 * 2)) & 3
                cells[display] = (world, east, north, (y // 8 * 32 + x) * 8 + y % 8)
                world_to_cell[world] = display
    left = min(p[0] for p in cells)
    bottom = min(p[1] for p in cells)
    width = max(p[0] for p in cells) - left + 1
    height = max(p[1] for p in cells) - bottom + 1
    block = {'level': floor, 'width': width, 'height': height, 'types': [0],
             'extra': [0] * (width * height), 'cells': set(), 'world': {}, 'world_to_cell': {},
             'sectors': bytes(rec[512:544]), 'dark_indices': {}}
    for side in ('north', 'east', 'south', 'west'):
        block[side] = [1] * (width * height)
    for (px, py), (world, east, north, dark_index) in cells.items():
        x, y = px - left, py - bottom
        i = y * width + x
        block['cells'].add((x, y))
        block['world'][(x, y)] = world
        block['world_to_cell'][world] = (x, y)
        block['dark_indices'][(x, y)] = dark_index
        # The disk leaves the edge open where no square lies beyond it (the rock
        # outside a sector); the party cannot go there, so the map draws a wall.
        if east == 0 and (world[0] + 1, world[1]) not in world_to_cell:
            east = 1
        if north == 0 and (world[0], world[1] + 1) not in world_to_cell:
            north = 1
        block['east'][i], block['north'][i] = east, north
        for side, neighbor, slot in (('west', (world[0] - 1, world[1]), 1),
                                     ('south', (world[0], world[1] - 1), 2)):
            other = world_to_cell.get(neighbor)
            if other in cells:
                block[side][i] = cells[other][slot]
    return block


def _read_maze(wiz_dir, game=1):
    """Maze levels from the game's disk image (read only).

    WIZ1.DSK (or SAVE1.DSK) -> SCENARIO.DATA -> zone 1 (ZMAZE) of the TOC:
    WIZ1 has 10 records of 894 bytes, one per 1024 bytes, from block 12.
    TMAZE: walls W, S, E, N at 0/120/240/360 (per x: 6 bytes, 2 bits per y,
    low bits first in each word), SQREXTRA at 560 (per x: 10 bytes, 4 bits
    per y), SQRETYPE at 760 (16 x 4 bits), AUX0 at 768 (16 ints).
    Checked 2026-11-02: all 10 levels equal the old wiz1_maps.json
    (walls 1600/1600 per side, squares 400/400, types and AUX0 16/16).
    Cell index is y * 20 + x, (0, 0) at the south-west.
    """
    if game not in (1, 2, 3, 4, 5):
        return None
    for disk_name in (f"WIZ{game}.DSK", f"SAVE{game}.DSK"):
        path = os.path.join(wiz_dir or "", disk_name)
        if os.path.isfile(path):
            break
    else:
        return None

    def field(rec, base, row_bytes, bits, x, y):
        per_word = 16 // bits
        o = base + x * row_bytes + 2 * (y // per_word)
        return (int.from_bytes(rec[o:o + 2], 'little') >> ((y % per_word) * bits)) & ((1 << bits) - 1)

    if game == 5:
        with open(path, 'rb') as handle:
            data = _ucsd_file(handle.read(), 'DRAGON.DATA')
        if not data or len(data) < 114:
            raise OSError('DRAGON.DATA 지도 목차를 읽지 못했습니다.')
        # Nine zones, unlike the eight-zone table in Wizardry 1–3.
        values = [int.from_bytes(data[o:o + 2], 'little') for o in (44, 62, 80, 98)]
        per_block, floors, size, start = values
        if (per_block, floors, size) != (1, 8, 1024) or start * 512 + floors * size > len(data):
            raise OSError('지원하지 않는 5편 지도 목차입니다.')
        levels = [_decode_wiz5_maze(data[start * 512 + n * size:start * 512 + (n + 1) * size], n + 1)
                  for n in range(floors)]
        values8 = [int.from_bytes(data[o:o + 2], 'little') for o in (58, 76, 94, 112)]   # zone 8
        if values8[:3] != [1, 8, 1024] or values8[3] * 512 + 8 * 1024 > len(data):
            raise OSError('지원하지 않는 5편 특수 칸 목차입니다.')
        markers = []
        for n in range(floors):
            joined = (data[start * 512 + n * size:start * 512 + n * size + 922]
                      + data[values8[3] * 512 + n * 1024:values8[3] * 512 + (n + 1) * 1024])
            markers += [(n + 1, *m) for m in _wiz5_specials(joined)]
        spots = []
        for floor, wx, wy, kind, name, direction in markers:
            block = levels[floor - 1]
            cell = block['world_to_cell'].get((wx, wy))
            if cell is None:
                continue
            x, y = cell
            block['types'] = list(range(len(_MAP_KIND_KO)))
            block['extra'][y * block['width'] + x] = kind
            if direction:
                block.setdefault('stairs', {})[cell] = direction
            spots.append({'level': floor, 'x': x, 'y': y, 'name': name})
        return {'levels': levels, 'spots': spots}

    if game == 4:
        with open(path, "rb") as f:
            dsk_bytes = f.read()
        levels = []
        for n in range(14):
            blk = 217 + (n + 1) * 2
            rec = dsk_bytes[blk * 512: blk * 512 + 1024]
            if len(rec) < 1024:
                return None
            level = {"level": n + 1}
            for side, base in (("west", 0), ("south", 120), ("east", 240), ("north", 360)):
                level[side] = [field(rec, base, 6, 2, i % 20, i // 20) for i in range(400)]
            level["extra"] = [field(rec, 560, 10, 4, i % 20, i // 20) for i in range(400)]
            level["types"] = [(int.from_bytes(rec[760 + 2 * (k // 4):762 + 2 * (k // 4)], 'little')
                               >> ((k % 4) * 4)) & 15 for k in range(16)]
            level["aux0"] = [int.from_bytes(rec[768 + 2 * k:770 + 2 * k], 'little', signed=True)
                             for k in range(16)]
            level["aux2"] = [int.from_bytes(rec[832 + 2 * k:834 + 2 * k], 'little', signed=True)
                             for k in range(16)]
            levels.append(level)
        try:
            pentagrams = _wiz4_pentagrams(path, levels)
        except Exception:
            pentagrams = []   # the map still opens without the markers
        return {
            "levels": levels,
            "spots": [{"level": lv, "x": x, "y": y, "name": name} for lv, x, y, name in
                      _MAP_SPOTS_WIZ4 + tuple((lv, x, y, "소환 오행성") for lv, x, y in pentagrams)],
        }

    floors = 10 if game == 1 else 6
    with open(path, "rb") as f:
        data = _ucsd_file(f.read(), "SCENARIO.DATA")
    if not data:
        return None
    s16 = lambda o: int.from_bytes(data[o:o + 2], 'little', signed=True)
    per_2k, slots, size, block = s16(42 + 2), s16(58 + 2), s16(74 + 2), s16(90 + 2)
    if not (1 <= per_2k <= 2 and slots >= floors and size >= 800):
        return None

    levels = []
    for n in range(floors):
        o = block * 512 + (n // per_2k) * 1024 + (n % per_2k) * size
        rec = data[o:o + size]
        if len(rec) < size:
            return None
        level = {"level": n + 1}
        for side, base in (("west", 0), ("south", 120), ("east", 240), ("north", 360)):
            level[side] = [field(rec, base, 6, 2, i % 20, i // 20) for i in range(400)]
        level["extra"] = [field(rec, 560, 10, 4, i % 20, i // 20) for i in range(400)]
        level["types"] = [(int.from_bytes(rec[760 + 2 * (k // 4):762 + 2 * (k // 4)], 'little')
                           >> ((k % 4) * 4)) & 15 for k in range(16)]
        level["aux0"] = [int.from_bytes(rec[768 + 2 * k:770 + 2 * k], 'little', signed=True)
                         for k in range(16)]
        level["aux2"] = [int.from_bytes(rec[832 + 2 * k:834 + 2 * k], 'little', signed=True)
                         for k in range(16)]
        levels.append(level)
    try:
        spots = _scenario_spots(game, path, wiz_dir, levels)
    except Exception:
        spots = []   # the map still opens without the names
    return {"levels": levels, "spots": spots}


def _scenario_spots(game, path, wiz_dir, levels):
    """Named squares of Wizardry 1-3, read from the disk (read only).

    Message squares by AUX2, as the game code runs them (SYSTEM.PASCAL, segment
    SPECIALS, the case on AUX2): 2 gives item AUX0; 4 asks to search, where AUX0
    -1000-n gives item n and a positive AUX0 is a monster to fight; 5 lets only a
    party with item AUX0 pass. An encounter square holds one fixed monster (AUX2).
    Item names are the disk's (14001 + 2n); monster names are strings 13002 + 4n
    (Wizardry 3 has no numbered strings, so its monsters stay unnamed).
    """
    items = {it['n']: it['en'] for it in _read_item_book(wiz_dir, game)}
    monsters = {}
    if game in (1, 2):
        from tools.wiz_krn_decode import decode_numbered
        with open(path, 'rb') as handle:
            krn = _ucsd_file(handle.read(), 'ASCII.KRN')
        strings = {n: t for n, t in decode_numbered(krn) if n is not None} if krn else {}
        monsters = {k: strings[13002 + 4 * k] for k in range(120) if 13002 + 4 * k in strings}
    def icon(item):
        word = item.split()
        if 'KEY' in word:
            return word[-1].title() + ' Key'
        if 'STATUE' in word:
            return word[-1].title() + ' Statue'
        return 'Blue Ribbon' if 'RIBBON' in word else 'Item'
    spots = []
    for level in levels:
        for i, extra in enumerate(level['extra']):
            kind = level['types'][extra]
            aux0, aux2 = level['aux0'][extra], level['aux2'][extra]
            spot = None
            if kind == 11 and aux2 == 2 and aux0 in items:
                spot = {'name': icon(items[aux0]), 'item': items[aux0], 'role': 'get'}
            elif kind == 11 and aux2 == 4 and -20000 < aux0 <= -1000 and -aux0 - 1000 in items:
                item = items[-aux0 - 1000]
                spot = {'name': icon(item), 'item': item, 'role': 'search'}
            elif kind == 11 and aux2 == 4 and aux0 > 0:
                spot = {'name': 'Monster', 'monster': monsters.get(aux0, ''), 'role': 'fight'}
            elif kind == 11 and aux2 == 5 and aux0 in items:
                spot = {'name': 'Door', 'item': items[aux0], 'role': 'need'}
            elif kind == 12 and aux2 > 0:
                spot = {'name': 'Monster', 'monster': monsters.get(aux2, ''), 'role': 'fight'}
            if spot:
                spot.update(level=level['level'], x=i % 20, y=i // 20)
                spots.append(spot)
    return spots


_ITEM_TYPES = {0: "무기", 1: "갑옷", 2: "방패", 3: "투구", 4: "장갑", 5: "사용 도구", 6: "기타"}
_ITEM_ALIGN = {1: "선", 2: "중립", 3: "악"}
_ITEM_CLASSES = ("전사", "마법사", "성직자", "도적", "비숍", "사무라이", "로드", "닌자")
_ITEM_CACHE = {}
# Spell numbers used by the item table (mage 1-21, priest 22-50).
_SPELL_IDS = (
    "HALITO MOGREF KATINO DUMAPIC DILTO SOPIC MAHALITO MOLITO MORLIS DALTO LAHALITO MAMORLIS "
    "MAKANITO MADALTO LAKANITO ZILWAN MASOPIC HAMAN MALOR MAHAMAN TILTOWAIT KALKI DIOS BADIOS "
    "MILWA PORFIC MATU CALFO MANIFO MONTINO LOMILWA DIALKO LATUMAPIC BAMATU DIAL BADIAL LATUMOFIS "
    "MAPORFIC DIALMA BADIALMA LITOKAN KANDI DI BADI LORTO MADI MABADI LOKTOFEIT MALIKTO KADORTO").split()
# Monster kinds of the "strong against / protects against" masks (bit 0 first).
_MONSTER_KINDS = ("전사", "마법사", "성직자", "도적", "소인", "거인", "신화", "용",
                  "동물", "늑대인간", "언데드", "악마", "곤충", "마법생물")


# Wizardry 5 spell numbers (WhereAreWe Wiz5SpellIndex): mage 1-31, priest 32-63.
_WIZ5_SPELL_IDS = (
    "KATINO HALITO DUMAPIC MOGREF PONTI MELITO DESTO MORLIS BOLATU CALIFIC MAHALITO CORTU KANTIOS TZALIK "
    "LAHALITO LITOFEIT ROKDO SOCORDI MADALTO PALIOS VASKYRE BACORTU MAMOGREF ZILWAN LOKARA LADALTO MALOR "
    "MAHAMAN TILTOWAIT ABRIEL MAWXIWTZ DIOS BADIOS MILWA KALKI PORFIC KATU CALFO MONTINO KANDI LATUMAPIC "
    "DIALKO BAMATU LOMILWA HAKANIDO DIAL BADIAL LATUMOFIS MAPORFIC BARIKO DIALMA BADI DI BAMORDI MOGATO "
    "LOKTOFEIT MADI LABADI KAKAMEN MABARIKO KADORTO IHALON BAKADI").split()


def _spell_ko(en, game):
    """Korean spell name: the spell book first, then the Wizardry 5 sentence dictionary."""
    ko = next((row[2] for row in SPELL_BOOK if row[1] == en), None)
    if ko is None and game == 5:
        try:
            with open(resource_path("wiz5_sentences.json"), encoding="utf-8") as handle:
                table = json.load(handle)
            ko = table.get(en) or str(table.get("*" + en, "")).lstrip("*") or None
        except (OSError, ValueError):
            ko = None
    return ko or en


_RESIST_KINDS = ("물리", "불", "냉기", "독", "레벨 드레인", "석화", "마법")
_STAT_EFFECTS = {1: "힘 +1", 2: "지능 +1", 3: "신앙심 +1", 4: "활력 +1", 5: "민첩 +1", 6: "행운 +1",
                 7: "힘 -1", 8: "지능 -1", 9: "신앙심 -1", 10: "활력 -1", 11: "민첩 -1", 12: "행운 -1",
                 13: "나이 -1", 14: "나이 +1"}
# Wizardry 1-3 SPECIAL word (record +6). Read from the PC game code (SYSTEM.PASCAL, segment
# UTILITIE, the procedure with the case 13..27, in Wizardry 3 13..30; Apple p-code): 1-6 add one
# to an attribute and 7-12 take one (kept only inside 3-18), 13 takes a year only above age 20.
# 28/29 compare the user's alignment with the crystal's; 30 runs the ending.
_OLD_EFFECTS = {13: "나이 -1 (20세 초과일 때만)", 15: "사무라이로 전직", 16: "로드로 전직", 17: "닌자로 전직",
                18: "골드 +50000", 19: "경험치 +50000", 20: "캐릭터 소실",
                21: "상태 회복, 체력 전부 회복, 독 해제", 22: "최대 체력 +1", 23: "파티 전원 체력 회복",
                24: "사무라이·로드·닌자 중 무작위로 전직",
                25: "전사·마법사·성직자·도적·비숍 중 무작위 직업이 되고 사망",
                26: "마법사·성직자 주문 횟수가 모든 레벨 9가 됨",
                27: "주문 횟수가 모든 레벨 9가 되지만 배운 주문을 모두 잊음",
                28: "선 성향이 쓰면 선·악 수정이 합쳐져 중립의 수정이 됨(둘 다 있을 때). "
                    "악 성향이 쓰면 파티 전원 최대 체력 감소, 사용자는 재가 되거나 소실. 중립이 쓰면 사용자 최대 체력 감소",
                29: "악 성향이 쓰면 선·악 수정이 합쳐져 중립의 수정이 됨(둘 다 있을 때). "
                    "선 성향이 쓰면 파티 전원 최대 체력 감소, 사용자는 재가 되거나 소실. 중립이 쓰면 사용자 최대 체력 감소",
                30: "릴가민의 현자들에게 오브를 바치고 결말을 봄"}
_WIZ5_EFFECTS = {15: "체력 회복", 16: "파티 전원 체력 회복", 17: "최대 체력 +1d4", 18: "나이 -1, 최대 체력 -1d4",
                 19: "주문 점수 최대", 20: "주문 점수 소진", 24: "사망", 25: "마비", 26: "석화",
                 27: "활력 -1, 나이 +1", 28: "활력 +1, 최대 체력 -1d4", 29: "재가 됨", 30: "치유", 33: "치유"}
# Byte offsets of one item record. Wizardry 1-4: 46 bytes; Wizardry 5: 54 bytes (the WhereAreWe
# layout; checked against the disk for 4 and 5: the decoded record equals it byte for byte).
_ITEM_FIELDS = {
    'old': dict(type=0, align=2, curse=4, effect=6, breaks=8, chance=10, value=12, spell=20, usable=22,
                regen=24, prot=26, resist=28, ac=30, hit=32, qty=34, faces=36, bonus=38, atk=40, crit=42, purposed=44),
    'wiz5': dict(type=0, align=2, curse=4, effect=6, breaks=10, chance=12, value=14, spell=28, usable=30,
                 regen=34, prot=36, resist=38, ac=40, hit=42, qty=44, faces=46, bonus=48, atk=50, crit=None, purposed=52),
}


def _item_effect(rec, game, names):
    """Special powers of one item record (list of Korean phrases)."""
    f = _ITEM_FIELDS['wiz5' if game == 5 else 'old']
    w = lambda key: int.from_bytes(rec[f[key]:f[key] + 2], 'little', signed=True)
    out = []
    spell, effect, chance = w('spell'), w('effect'), w('chance')
    brk = ""
    if chance:
        into = "부서진 아이템" if w('breaks') == 0 else names.get(14001 + 2 * w('breaks'), "")
        if into:
            brk = f", {chance}% 확률로 {into}(으)로 변함" if chance < 100 else f", 쓰면 {into}(으)로 변함"
        else:
            brk = f", {chance}% 확률로 변함"
    ids = _WIZ5_SPELL_IDS if game == 5 else _SPELL_IDS
    if 1 <= spell <= len(ids):
        en = ids[spell - 1]
        out.append(f"사용: {_spell_ko(en, game)}({en}){brk}")
    text = None
    if game in (4, 5):
        text = _STAT_EFFECTS.get(effect) or (_WIZ5_EFFECTS.get(effect) if game == 5 else None)
    elif effect > 0:
        text = _OLD_EFFECTS.get(effect) or _STAT_EFFECTS.get(effect) or f"특수 능력 #{effect} (미해독)"
    if text:
        out.append(f"효과: {text}{'' if spell else brk}")
    if w('hit'):
        out.append(f"명중 {w('hit'):+d}")
    if w('regen'):
        out.append(f"재생 {'+' if w('regen') > 0 else ''}{w('regen')}")
    kinds = lambda mask: ", ".join(k for b, k in enumerate(_MONSTER_KINDS) if mask >> b & 1)
    if w('prot') & 0x3FFF:
        out.append("보호: " + kinds(w('prot')))
    if w('resist') & 0x7F:
        out.append("저항: " + ", ".join(k for b, k in enumerate(_RESIST_KINDS) if w('resist') >> b & 1))
    if w('type') == 0 and w('purposed') & 0x3FFF:
        out.append("특효: " + kinds(w('purposed')))
    crit = (w('curse') & 2) if game == 5 else (w('crit') == -1)
    if crit:
        out.append("치명타")
    if game == 5 and w('curse') & 4:
        out.append("특수")
    return out


def _wiz3_item_places(data, names):
    """{item number: [Korean notes]} from the special squares of the Wizardry 3 maze.

    Read from the game code (SYSTEM.PASCAL, segment SPECIALS, the case on AUX2 of a
    SCNMSG square): 2 gives item AUX0; 4 asks to search, where AUX0 -1000-n gives item n
    and -20000-100a-b turns item a into item b; 5 lets only a party with item AUX0 pass;
    14 moves a party without item AUX1 to AUX0 (x*100+y); 15 / 16 are the fights for the
    two crystals (which crystal is which is inferred from the level). Read only.
    """
    s16 = lambda o: int.from_bytes(data[o:o + 2], 'little', signed=True)
    per, slots, size, block = s16(44), s16(60), s16(76), s16(92)
    notes = {}
    name = lambda n: names.get(14001 + 2 * n, f"#{n}")
    for level in range(min(slots, 6)):
        o = block * 512 + (level // per) * 1024 + (level % per) * size
        rec = data[o:o + size]
        if len(rec) < 864:
            continue
        aux = lambda base, k: int.from_bytes(rec[base + 2 * k:base + 2 * k + 2], 'little', signed=True)
        for k in range(16):
            kind = (int.from_bytes(rec[760 + 2 * (k // 4):762 + 2 * (k // 4)], 'little') >> ((k % 4) * 4)) & 15
            if kind != 11:
                continue
            cells = [(x, y) for y in range(20) for x in range(20)
                     if (int.from_bytes(rec[560 + x * 10 + (y // 4) * 2:562 + x * 10 + (y // 4) * 2], 'little')
                         >> ((y % 4) * 4)) & 15 == k]
            if not cells:
                continue
            where = f"{level + 1}층 ({cells[0][0]}, {cells[0][1]})" + (f" 등 {len(cells)}칸" if len(cells) > 1 else "")
            a0, a1, a2 = aux(768, k), aux(800, k), aux(832, k)
            add = lambda n, text: notes.setdefault(n, []).append(text)
            if a2 == 2 and a0 > 0:
                add(a0, f"{where}에서 얻음")
            elif a2 == 4 and -20000 < a0 <= -1000:
                add(-a0 - 1000, f"{where}을 조사해 얻음")
            elif a2 == 4 and a0 <= -20000:
                need, give = divmod(-a0 - 20000, 100)
                add(give, f"{where}에서 {name(need)}(이)가 이것으로 바뀜")
                add(need, f"{where}에서 {name(give)}(으)로 바뀜")
            elif a2 == 5 and a0 > 0:
                add(a0, f"{where}: 가진 파티만 지나갈 수 있음")
            elif a2 == 14 and a1 > 0:
                add(a1, f"{where}: 없으면 ({a0 // 100}, {a0 % 100})(으)로 옮겨짐")
            elif a2 in (15, 16):
                add(3 if a2 == 15 else 4, f"{where}에서 싸워 얻음")
    return notes


def _item_ko(ko, en):
    """Korean item name. The dictionaries key " OF " as the ligature ~ (and POTION/SCROLL as the
    icons Ⓟ/Ⓢ or x/y), the disk name spells it out."""
    forms = [en, en.replace(' OF ', '~'), en.replace(' OF ', 'w'),
             en.replace('POTION OF ', 'Ⓟ~').replace('SCROLL OF ', 'Ⓢ~'),
             en.replace('POTION OF ', 'xw').replace('SCROLL OF ', 'yw'), en.rstrip('!'),
             en.replace('POTION OF ', 'X~').replace('SCROLL OF ', 'Y~'),      # Wizardry 5 screen keys
             en.replace(' OF ', 'w') + '', re.sub(r'^OF ', '~', en)]   # padded / picture-letter names
    return next((ko[f] for f in forms if ko.get(f)), '')


def _read_item_book(wiz_dir, game):
    """Item table (TOC zone 4) of the scenario disk plus the item names. Read only.

    Wizardry 1-3: 46-byte records, 22 per 1024 bytes, names from ASCII.KRN
    (strings 14000 + 2n unknown, + 2n + 1 identified; Wizardry 3 has no string
    numbers, so its pairs follow BROKEN ITEM). Wizardry 4 and 5: records are
    contiguous and Huffman-coded with ASCII.HUFF (Wizardry 4: 46 bytes, Wizardry 5:
    58 decoded, the first 54 are the record), names 14001 + 2n of the Huffman
    strings. Fields: see _ITEM_FIELDS. Returns [dict] or raises OSError.
    """
    if game not in (1, 2, 3, 4, 5):
        raise OSError("지원하지 않는 편입니다.")
    for disk_name in (f"WIZ{game}.DSK", f"SAVE{game}.DSK"):
        path = os.path.join(wiz_dir or "", disk_name)
        if os.path.isfile(path):
            break
    else:
        raise OSError("위저드리 폴더에서 WIZ%d.DSK를 찾지 못했습니다." % game)
    stamp = (path, os.path.getmtime(path))
    if stamp in _ITEM_CACHE:
        return _ITEM_CACHE[stamp]
    with open(path, "rb") as handle:
        disk = handle.read()
    data = _ucsd_file(disk, "DRAGON.DATA" if game == 5 else "SCENARIO.DATA")
    if not data:
        raise OSError("시나리오 데이터를 읽지 못했습니다.")
    s16 = lambda o: int.from_bytes(data[o:o + 2], 'little', signed=True)
    stride = 18 if game == 5 else 16
    per, slots, size, block = (s16(42 + 8 + stride * k) for k in range(4))
    if not (1 <= per <= 100 and 1 <= slots <= 200 and 20 <= size <= 64):
        raise OSError("지원하지 않는 아이템 목차입니다.")
    # The game stores POTION / SCROLL / " OF " as the picture letters x, y, w.
    fix = lambda t: re.sub(r"[^\x20-\x7e]", "", t.replace('x', 'POTION').replace('y', 'SCROLL')
                           .replace('w', ' OF ')).replace('  ', ' ').strip()
    records = []
    if game in (4, 5):
        from tools.wiz4_krn_decode import decode_wiz4_strings, decode_pascal_string
        names = {n: fix(t) for n, t in decode_wiz4_strings(path).items()}
        huff = _ucsd_file(disk, "ASCII.HUFF")
        if not huff:
            raise OSError("ASCII.HUFF를 읽지 못했습니다.")
        want = 54 if game == 5 else 46
        for n in range(slots):
            o = block * 512 + n * size
            rec = decode_pascal_string(data[o:o + size], 0, huff[0:256], huff[256:512], huff[512:768]).encode('latin1')
            records.append(rec if len(rec) >= want else b'')
    else:
        krn = _ucsd_file(disk, "ASCII.KRN")
        if not krn:
            raise OSError("ASCII.KRN을 읽지 못했습니다.")
        from tools.wiz_krn_decode import decode_numbered
        decoded = decode_numbered(krn)
        names = {n: fix(t) for n, t in decoded if n is not None}
        if not names:
            texts = [t for _, t in decoded]
            if 'BROKEN ITEM' not in texts:
                raise OSError("아이템 이름을 찾지 못했습니다.")
            start = texts.index('BROKEN ITEM')
            names = {14000 + k: fix(t) for k, t in enumerate(texts[start:start + 2 * 200])}
            # Potion / scroll names read as junk (their unknown name is one letter, so the key
            # guess fails): try every key and take the one that reads "<x|y|z> of NAME".
            from tools.wiz_krn_decode import decrypt, find_offset_table
            offsets = find_offset_table(krn)
            for k in range(2 * 200):
                if start + k >= len(texts) or re.fullmatch(r"[A-Z0-9 +\-'().!]*", names.get(14000 + k, '')):
                    continue
                o = offsets[start + k]
                raw = krn[2 * o + 1:2 * o + 1 + krn[2 * o]]
                for key in range(51):
                    if re.fullmatch(r"[xyz]w[A-Z]+", decrypt(raw, key)):
                        names[14000 + k] = fix(decrypt(raw, key))
                        break
        for n in range(slots):
            o = block * 512 + (n // per) * 1024 + (n % per) * size
            records.append(data[o:o + 46] if size == 46 and o + 46 <= len(data) else b'')
    f = _ITEM_FIELDS['wiz5' if game == 5 else 'old']
    places = _wiz3_item_places(data, names) if game == 3 else {}
    items = []
    for n, rec in enumerate(records):
        if n == 0 or not rec or 14001 + 2 * n not in names:
            continue
        w = lambda key: int.from_bytes(rec[f[key]:f[key] + 2], 'little', signed=True)
        def long_at(vo):
            return sum(int.from_bytes(rec[vo + 2 * k:vo + 2 * k + 2], 'little') * m
                       for k, m in enumerate((1, 10000, 100000000)))
        # Wizardry 5 keeps a second long at +20 (shops: the Dagger has 25 there, nothing at +14).
        price = long_at(f['value']) or (long_at(20) if game == 5 else 0)
        qty, faces, bonus = w('qty'), w('faces'), w('bonus')
        dice = ""
        if qty and faces:
            dice = f"{qty}d{faces}" + (f"{bonus:+d}" if bonus else "") + (f" x{w('atk') + 1}" if w('atk') > 0 else "")
        mask = w('usable') & 0xFF
        items.append({
            'n': n, 'en': names[14001 + 2 * n], 'unknown': names.get(14000 + 2 * n, ''),
            'type': _ITEM_TYPES.get(w('type'), "기타"), 'align': _ITEM_ALIGN.get(w('align'), ""),
            'cursed': (w('curse') & 1) == 1 if game == 5 else w('curse') == -1, 'price': price,
            'classes': [c for b, c in enumerate(_ITEM_CLASSES) if mask >> b & 1],
            'ac': w('ac'), 'dice': dice, 'effect': _item_effect(rec, game, names) + places.get(n, []),
        })
    _ITEM_CACHE[stamp] = items
    return items


def _lost_bodies(wiz_dir, game=1):
    """Dead characters left in the maze, read from the scenario disk image.

    Read only. SAVE1.DSK (the scenario disk the game made) or WIZ1.DSK.
    SCENARIO.DATA starts with the TOC: record size, records per 1024 bytes,
    slot count and first block per zone; ZCHAR is zone 5 (WIZ1: 208 bytes,
    4 per 1024, 20 slots, block 2). Record: name +0x00, STATUS +0x28,
    +0xCA = x*100 + y and +0xCC = level of the place the character was last
    in the maze (a wiped party on level 3 at (16, 4): 1604 and 3, from the
    user's SAVE1.DSK). INMAZE (+0x20) is 0 for those bodies, so it is not used.
    Returns [(name, level, x, y, status)].
    """
    for disk_name in (f"SAVE{game}.DSK", f"WIZ{game}.DSK"):
        path = os.path.join(wiz_dir or "", disk_name)
        if os.path.isfile(path):
            break
    else:
        return []
    try:
        stamp = (path, os.path.getmtime(path))
        if stamp in _ROSTER_CACHE:
            return _ROSTER_CACHE[stamp]
        with open(path, "rb") as f:
            disk = f.read()
        data = _ucsd_file(disk, "SCENARIO.DATA")
        bodies = []
        if data:
            s16 = lambda o: int.from_bytes(data[o:o + 2], 'little', signed=True)
            per_2k, slots, size, block = s16(42 + 10), s16(58 + 10), s16(74 + 10), s16(90 + 10)
            if size == 208 and 1 <= per_2k <= 4 and 1 <= slots <= 40:
                for n in range(slots):
                    o = block * 512 + (n // per_2k) * 1024 + (n % per_2k) * size
                    rec = data[o:o + size]
                    if len(rec) < size or not 1 <= rec[0] <= 15:
                        continue
                    name = rec[1:1 + rec[0]].decode('latin1', 'replace')
                    status = int.from_bytes(rec[0x28:0x2A], 'little')
                    place = int.from_bytes(rec[0xCA:0xCC], 'little', signed=True)
                    level = int.from_bytes(rec[0xCC:0xCE], 'little', signed=True)
                    x, y = divmod(place, 100)
                    # A living character with a maze place is "OUT" (left there by
                    # a party that quit). +0x20 is 0 for them too: the user's
                    # restart list showed LILITH, RESCUE, AMEN, C, BETA, all alive
                    # with 913 / level 3; ELMER (never out) has 0.
                    out = status <= 4
                    if ((status in (5, 6) or out) and 1 <= level <= 10
                            and 0 <= place and 0 <= x <= 19 and 0 <= y <= 19):
                        bodies.append((name, level, x, y, status))
        _ROSTER_CACHE.clear()
        _ROSTER_CACHE[stamp] = bodies
        return bodies
    except Exception:
        return []


def _load_settings():
    old, new = (os.path.join(_app_dir(), n) for n in (_OLD_SETTINGS_FILE, _SETTINGS_FILE))
    if os.path.exists(old) and not os.path.exists(new):
        try:
            os.replace(old, new)   # keep the user's paths and window places
        except OSError:
            pass
    try:
        with open(os.path.join(_app_dir(), _SETTINGS_FILE), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_settings(data):
    try:
        with open(os.path.join(_app_dir(), _SETTINGS_FILE), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _remember(**values):
    """Store these choices in the settings file; write only when one changed."""
    data = _load_settings()
    if any(data.get(k) != v for k, v in values.items()):
        data.update(values)
        _save_settings(data)


def _parse_geometry(text):
    """Tk "WxH+X+Y" -> (w, h, x, y), or None. Tk writes a negative X as "+-30"."""
    m = re.fullmatch(r'(\d+)x(\d+)\+(-?\d+)\+(-?\d+)', str(text))
    return tuple(int(g) for g in m.groups()) if m else None


def _on_a_monitor(x, y):
    """True when this screen point is on some monitor (a title bar the user can grab)."""
    return bool(ctypes.windll.user32.MonitorFromPoint(wintypes.POINT(x, y), 0))


def _visible_cells(block, x, y, facing, depth):
    """Cells the 3D view shows: at each distance the square ahead and the
    squares to its left and right, up to depth ahead, until a wall or door.
    A side square shows only when the edge to it is open."""
    width, height = block.get('width', 20), block.get('height', 20)
    def neighbor(x, y, side):
        dx, dy = _STEP[side]
        if 'world' in block:
            wx, wy = block['world'][(x, y)]
            return block['world_to_cell'].get((wx + dx, wy + dy))
        # The maze wraps: past the east edge is the west edge (the 3D view shows it).
        return ((x + dx) % width, (y + dy) % height)
    seen = [(x, y)]
    if facing is None:
        return seen
    sides = ((facing + 3) % 4, (facing + 1) % 4)
    for step in range(depth + 1):
        if step:
            if block[_SIDES[facing]][y * width + x] != 0:
                break
            next_cell = neighbor(x, y, facing)
            if next_cell is None:
                break
            x, y = next_cell
            seen.append((x, y))
        for side in sides:
            if block[_SIDES[side]][y * width + x] == 0:
                next_cell = neighbor(x, y, side)
                if next_cell is not None:
                    seen.append(next_cell)
    return seen
def _entered_cells(block, x, y, facing, steps=4):
    """Squares straight ahead (through doors, not walls) up to and including the first
    one that moves the party at once (stairs, chute, teleporter, elevator),
    or nothing. The party leaves such a square before the next poll reads it."""
    width, height = block.get('width', 20), block.get('height', 20)
    out = []
    for _ in range(steps):
        # Only a solid wall (1) stops the party: these squares sit behind doors.
        if block[_SIDES[facing]][y * width + x] == 1:
            break
        dx, dy = _STEP[facing]
        if 'world' in block:
            wx, wy = block['world'][(x, y)]
            nxt = block['world_to_cell'].get((wx + dx, wy + dy))
        else:
            nxt = ((x + dx) % width, (y + dy) % height)   # the maze wraps
        if nxt is None:
            break
        x, y = nxt
        out.append(nxt)
        extra = block['extra'][y * width + x]
        types = block['types']
        if (types[extra] if 0 <= extra < len(types) else 0) in (1, 3, 6, 8):
            return out
    return []   # no such square ahead: the jump was not a teleporter, mark nothing


_MAP_SPOT_KO = {
    "Silver Key": "은열쇠", "Bronze Key": "청동열쇠", "Murphy's Ghost": "머피의 유령",
    "Gold Key": "금열쇠", "Bear Door": "곰 문", "Frog Door": "개구리 문",
    "Silver Fog": "은 안개", "Bronze Fog": "청동 안개", "Frog Statue": "개구리 석상",
    "Bear Statue": "곰 석상", "Blue Ribbon": "파란 리본", "Fire Dragon": "화염 드래곤",
    "Chute": "슈트", "Werdna": "베르드나",
    "Stairs Up": "오르는 계단", "Stairs Down": "내리는 계단", "Pool": "웅덩이", "Fountain": "샘",
    "Fountain of Youth": "젊음의 샘", "Altar": "제단", "Garian Guard": "가리안 경비병",
    "High Priest": "대사제", "L'Kbreth": "르케브레스", "Moat Monster": "해자 괴물",
    "Orb of Earithin": "에아리틴의 오브",
}


def _spot_ko(name):
    if name in _MAP_SPOT_KO:
        return _MAP_SPOT_KO[name]
    if name.startswith("Guardian "):
        return "수호자 " + name[9:]
    if name.startswith("Teleport "):
        return "순간이동 " + name[9:]
    return name


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def load_custom_fonts():
    font_file = resource_path("neodgm.ttf")
    if os.path.exists(font_file):
        try:
            ctypes.windll.gdi32.AddFontResourceExW(font_file, 0x10, 0)
        except Exception:
            pass

load_custom_fonts()

from wiz_hook import DOSBoxHook
from wiz1_state import Wizardry1State, _LEVELUP_LOST
from wiz_screen import read_trade_stage, read_stairs_prompt, relock_cga_video
from cga_text_extractor import (
    CGATextExtractor, FONT_GLYPHS, FRAME_CHAR, ITEM_KEYS, MONSTER_KEYS, battle_line_mark, combat_emphasis, load_unified_translations, project_dir, dev_path, screen_item_keys,
)

_CGA_PIXELS = tuple(bytes(((b >> 6) & 3, (b >> 4) & 3, (b >> 2) & 3, b & 3)) for b in range(256))
# shortcut: fixed title-screen palette; read the active palette if the game changes it.
_CGA_PALETTE = bytes((0, 0, 0, 85, 255, 255, 255, 85, 85, 255, 255, 255)) + bytes(756)

def _cga_image(video, width, height):
    pixels = b''.join(_CGA_PIXELS[b] for y in range(200)
                      for b in video[(y // 2) * 80 + (y % 2) * 8192:][:80])
    frame = Image.frombytes('P', (320, 200), pixels)
    frame.putpalette(_CGA_PALETTE)
    return frame.resize((width, height), Image.Resampling.NEAREST).convert('RGB')

def _layout_translated_rows(chunks, rows, measure, align='left'):
    """Wrap translated words within the measured bounds of existing screen rows."""
    words = [(word, color) for text, color in chunks for word in text.split()]
    line_words = []
    row = 0
    cur_row_words = []
    x = rows[0][1]
    for word, color in words:
        word_width = measure(word)
        gap = measure(' ') if cur_row_words else 0
        if x + gap + word_width > rows[row][2]:
            if cur_row_words:
                line_words.append((row, cur_row_words))
                cur_row_words = []
            row += 1
            if row >= len(rows):
                return None
            x = rows[row][1]
            gap = 0
        if x + gap + word_width > rows[row][2]:
            return None
        cur_row_words.append((word, color, word_width, gap))
        x += gap + word_width
    if cur_row_words:
        line_words.append((row, cur_row_words))

    placed = []
    for r_idx, r_words in line_words:
        r_y = rows[r_idx][0]
        lo = rows[r_idx][1]
        hi = rows[r_idx][2]
        total_w = sum(w + g for _, _, w, g in r_words)
        if align == 'center':
            start_x = lo + max(0.0, (hi - lo - total_w)) / 2.0
        else:
            start_x = lo
        cur_x = start_x
        for word, color, word_width, gap in r_words:
            cur_x += gap
            placed.append((cur_x, r_y, word, color))
            cur_x += word_width
    return placed


# A fight row that goes on with the sentence of the row above it.
_COMBAT_CONTINUES = re.compile(r'[│ ]*(?:AND |HITS |TIMES |FOR \d|ONCE |\d+ TIMES|MISSES|DAMAGE|BUT |COMES|APPEARS|'
                               r'HELP |NO HELP|ONE MONSTER|CANNOT |SPEAK!|NOTHING HAPPENS!|HAPPENS!)')


def _combat_message_positions(matches, lines, context, measure, scale_x, joined=None):
    """Left-packed x of each match on a fight row.

    ``joined`` (a dict), when given, gets the CGA row to draw on for matches of a
    row that continues the sentence above it: Korean is narrower than the
    English, so the whole sentence is drawn on its first row when it fits.
    """
    positions = {}
    battle_rows = {m['y'] for m in matches if not m.get('paragraph') and battle_line_mark(m['original'])}
    previous = None   # (row, row it is drawn on, x after its last word, right edge, last word was covered only)
    for row in sorted({m['y'] for m in matches}):
        if row not in battle_rows and not (context == 'combat' and 48 <= row < 88):
            previous = None
            continue
        items = sorted((m for m in matches if m['y'] == row), key=lambda m: m['x'])
        line = next((line for line in lines or () if line['y'] == row), None)
        if not items or not line or '?' in line['text']:
            previous = None
            continue
        # A joined piece (a wrapped name, the hit result) carries no window bounds:
        # take them from the row, or it starts on the window edge.
        text = line['text']
        edge_l = text.rfind(FRAME_CHAR, 0, items[0]['x'] // 8)
        edge_r = text.find(FRAME_CHAR, (items[-1]['x'] + items[-1].get('w', 0)) // 8)
        row_lo, row_hi = (edge_l + 1) * 8, (edge_r * 8 if edge_r >= 0 else 320)
        right = min(m.get('max_bound_x', row_hi) for m in items) * scale_x

        def pack(x_pos, items=None):
            row_positions = {}
            for m in (items_all if items is None else items):
                row_positions[id(m)] = x_pos
                if m['korean']:
                    x_pos += measure(m['korean']) + measure(' ')
            return row_positions, x_pos

        items_all = items
        left = max(m.get('min_bound_x', row_lo) for m in items) * scale_x
        if (joined is not None and previous and previous[0] == row - 8
                and (previous[4] or _COMBAT_CONTINUES.match(line['text']))):
            # The hit result ("3회 명중: 7 피해") always starts the second row, so
            # every attack reads the same: who and whom above, the result below.
            cut = next((k for k, m in enumerate(items)
                        if '회 명중' in m['korean'] or re.match(r'(?:AND )?HITS(?![A-Z])', m['original'])), len(items))
            if 0 < cut < len(items) and items[cut - 1]['original'] == 'AND':
                items[cut - 1]['korean'] = ''   # the "AND" of "AND HITS": the result says it
            row_positions, x_pos = pack(previous[2], items[:cut])
            rest_positions, rest_x = pack(left, items[cut:])
            if x_pos <= min(right, previous[3]) and rest_x <= right:
                positions.update(row_positions)
                positions.update(rest_positions)
                joined.update((key, previous[1]) for key in row_positions)
                previous = ((row, previous[1], x_pos, previous[3], not items[-1]['korean']) if cut == len(items)
                            else (row, row, rest_x, right, False))
                continue
        row_positions, x_pos = pack(left)
        # shortcut: an overflowing row keeps its original layout until multiline combat is supported.
        if x_pos <= right:
            positions.update(row_positions)
            previous = (row, row, x_pos, right, not items[-1]['korean'])
        else:
            previous = None
    return positions


def _paragraph_row_bounds(line, match):
    """CGA x range a paragraph row may use: inside its window edges, else the screen."""
    text = line['text'] if line else ''
    lo, hi = match['x'], match['x'] + match['w']
    left = text.rfind(FRAME_CHAR, 0, lo // 8)
    right = text.find(FRAME_CHAR, hi // 8)
    return (match['y'], (left + 1) * 8 if left >= 0 else 0, right * 8 if right >= 0 else 320)


def _blank_rows_below(video, line_by_y, y, lo, hi, limit=2):
    """Empty text rows right under a paragraph, inside the same x range.

    Only rows whose pixels are all zero there. A window edge or picture stops it.
    """
    out = []
    if not video or len(video) < 16384:
        return out
    c0, c1 = lo // 4, (hi + 3) // 4
    for k in range(1, limit + 1):
        row = y + 8 * k
        if row + 8 > 200 or row in line_by_y:
            break
        if any(video[(py % 2) * 8192 + (py // 2) * 80 + c0:(py % 2) * 8192 + (py // 2) * 80 + c1].strip(b'\0')
               for py in range(row, row + 8)):
            break
        out.append((row, lo, hi))
    return out

# WAE Wiz1MemoryHacker.GetMainState states outside the maze: edge of town,
# castle, tavern, inn, temple, shop, training, utilities, roster, creation.
_TOWN_STATE1 = frozenset((
    21518, 21638, 21678, 22234, 22580, 22310, 21780, 22602, 22704, 23692, 22696,
    21068, 21114, 21842, 21076, 21850, 21048, 21782, 21122, 22178, 21154, 23166,
    21082, 21126, 21078, 20888,
))

# Wizardry 5 castle / edge-of-town map: boxes in 0-100 units, and the state1
# word (WAW GetMainState, anchor+77458) that puts the party in each box.
_TOWN_PANELS = (('릴가민 성', 1, 49), ('마을 외곽', 51, 99))
_TOWN_NODES = {
    'castle': (6, 9, 44, 19, '성 광장'),
    'tavern': (6, 24, 44, 34, '길가메시 선술집'),
    'tavern_add': (6, 36.5, 17.5, 44.5, '영입'),
    'tavern_remove': (19.25, 36.5, 30.75, 44.5, '제외'),
    'tavern_inspect': (32.5, 36.5, 44, 44.5, '점검'),
    'inn': (6, 50, 44, 60, '모험가의 여관'),
    'shop': (6, 66, 44, 76, '볼탁 상점'),
    'temple': (6, 82, 44, 92, '칸트 사원'),
    'edge': (56, 9, 94, 19, '마을 외곽 입구'),
    'training': (56, 24, 94, 34, '훈련장'),
    'create': (56, 36.5, 67.3, 44.5, '만들기'),
    'train_inspect': (69.3, 36.5, 80.6, 44.5, '점검'),
    'roster': (82.6, 36.5, 94, 44.5, '명부'),
    'utilities': (56, 50, 94, 60, '유틸리티'),
    'maze': (56, 66, 94, 76, '미궁 출발'),
}
_TOWN_STATE_NODES = {
    5: {
        34002: 'castle', 33706: 'tavern', 34196: 'tavern_add', 34296: 'tavern_remove',
        34632: 'tavern_inspect', 35104: 'tavern_inspect',
        34208: 'inn', 34212: 'inn', 34246: 'inn', 34248: 'inn',
        35516: 'shop', 36178: 'shop', 35720: 'temple',
        36298: 'edge', 36228: 'utilities',
        33312: 'create', 33756: 'create', 33738: 'create',
        33740: 'train_inspect', 33528: 'train_inspect', 33828: 'train_inspect', 33998: 'roster',
    },
    # WAE Wiz1MemoryHacker.GetMainState
    1: {
        21638: 'castle', 21678: 'tavern', 22602: 'tavern_add', 21780: 'tavern_remove',
        22704: 'tavern_inspect', 23692: 'tavern_inspect', 22696: 'tavern_inspect',
        22234: 'inn', 22310: 'shop', 22580: 'temple', 21518: 'edge',
        21068: 'utilities', 21114: 'utilities', 21842: 'utilities', 21076: 'utilities', 21850: 'utilities',
        21048: 'training', 21082: 'create', 21126: 'create', 21078: 'create',
        21782: 'train_inspect', 21122: 'train_inspect', 22178: 'train_inspect',
        21154: 'train_inspect', 23166: 'train_inspect', 20888: 'roster',
    },
}
# Wizardry 2 and 3 share these screen texts; their state values are not mapped.
_TOWN_TEXT_NODES = (
    ('WIZARDRY UTILITIES', 'utilities'), ('C)REATE A CHARACTER', 'training'),
    ('T)RAINING/M)AZE', 'edge'), ("BOLTAC'S TRADING POST", 'shop'),
    ('TEMPLE OF CANT', 'temple'), ("ADVENTURER'S INN", 'inn'),
    ('REMOVE WHO', 'tavern_remove'), ("GILGAMESH'S TAVERN", 'tavern'),
    ('E)DGE OF TOWN', 'castle'),
)

# "1 DUKE            N-FIG  3   29   41": number, name, class, AC, HITS, max.
_PARTY_HP_RE = re.compile(r'^[ \u2502]*[1-6] .*?[GNE]-[A-Z]{3} +-?\d+ +(\d+) +(\d+) *[ \u2502]*$')
_LOW_HP_COLOR = '#ffff55'
# Party row: number, name..., class, AC, HITS, STATUS (a number, or DEAD...).
_PARTY_ROW_RE = re.compile(r'^[ │]*([1-6]) +\S.*?(?:[GNE]-[A-Z]{3}|[A-Z]{3}) +(-?\d+) +(-?\d+) +([A-Z]+|\d+)[ │]*$')


def _row_start_col(text, left_edge, right_edge):
    """First text column of a row between the given window edges, or None."""
    if not text:
        return None
    hi = right_edge if right_edge >= 0 else len(text)
    # A picture row (logo, monster) reads as unknown '?' shapes and stray
    # letters. It is not a paragraph row, so it must not block centering.
    if not re.search(r'[A-Z]{2}', text[left_edge + 1:hi]):
        return None
    for col in range(left_edge + 1, min(hi, len(text))):
        if text[col] not in (' ', FRAME_CHAR):
            return None if text[col] == '?' else col
    return None

# Spell list colours by what the spell does (key: English name).
_SPELL_KINDS = (
    ('공격', '#f38ba8', 'HALITO MAHALITO MOLITO DALTO LAHALITO MADALTO LAKANITO MAKANITO ZILWAN TILTOWAIT '
                       'BADIOS BADIAL BADIALMA LITOKAN BADI LORTO MABADI MALIKTO'),
    ('회복', '#a6e3a1', 'DIOS DIAL DIALMA MADI DI KADORTO DIALKO LATUMOFIS'),
    ('버프', '#89b4fa', 'MOGREF SOPIC MASOPIC KALKI MATU BAMATU MAPORFIC PORFIC'),
    ('디버프', '#cba6f7', 'KATINO DILTO MORLIS MAMORLIS MANIFO MONTINO'),
)
_SPELL_OTHER = ('기타', '#fab387')
_SPELL_KIND_OF = {name: (kind, color) for kind, color, names in _SPELL_KINDS for name in names.split()}


SHORT_CLASS = {
    "전사": "전사", "마법사": "마법", "사제": "사제", "도적": "도적",
    "비숍": "비숍", "사무라이": "사무", "로드": "로드", "닌자": "닌자"
}

# Wizardry 1 spell book. WhereAreWe returns this set from Wiz123.Spells.
# Effects follow that book's name, level, when, target, and result.
# Spell list: effects in our own words, numbers from the game (dice, levels, targets).
# Group damage dice read from the game code (WIZ1 SYSTEM.PASCAL, CASTASPE 30: MAHALITO 4d6,
# MOLITO 3d6, DALTO 6d6, LAHALITO 6d6, MADALTO 8d8, TILTOWAIT 10d15; CASTASPE 29: LITOKAN 3d8,
# LORTO 6d6, MALIKTO 12d6).
SPELL_BOOK = (
    ("마법사 1", "HALITO", "할리토", "전투", "적 1체", "적 하나에게 화염 1d8."),
    ("마법사 1", "MOGREF", "모그레프", "전투", "자신", "시전자 AC 2 개선(전투 동안)."),
    ("마법사 1", "KATINO", "카티노", "전투", "적 1그룹", "한 그룹을 잠재운다. 강한 적일수록 짧게 잔다. 자는 적은 명중이 쉽고 피해 2배."),
    ("마법사 1", "DUMAPIC", "두마픽", "캠프", "파티", "현재 층, 좌표, 방향 표시(1층 계단 기준)."),
    ("마법사 2", "DILTO", "딜토", "전투", "적 1그룹", "한 그룹의 AC 2 악화."),
    ("마법사 2", "SOPIC", "소픽", "전투", "자신", "시전자 AC 4 개선(전투 동안)."),
    ("마법사 3", "MAHALITO", "마할리토", "전투", "적 1그룹", "한 그룹에 화염 4d6."),
    ("마법사 3", "MOLITO", "몰리토", "전투", "적 1그룹", "한 그룹 절반가량에 3d6."),
    ("마법사 4", "MORLIS", "몰리스", "전투", "적 1그룹", "한 그룹의 AC 4 악화."),
    ("마법사 4", "DALTO", "달토", "전투", "적 1그룹", "한 그룹에 냉기 6d6."),
    ("마법사 4", "LAHALITO", "라할리토", "전투", "적 1그룹", "한 그룹에 화염 6d6."),
    ("마법사 5", "MAMORLIS", "마몰리스", "전투", "모든 적", "모든 그룹의 AC 4 악화."),
    ("마법사 5", "MAKANITO", "마카니토", "전투", "모든 적", "8레벨 미만의 적을 모두 즉사."),
    ("마법사 5", "MADALTO", "마달토", "전투", "적 1그룹", "한 그룹에 냉기 8d8."),
    ("마법사 6", "LAKANITO", "라카니토", "전투", "적 1그룹", "한 그룹을 질식사. 레벨이 높을수록 버틴다."),
    ("마법사 6", "ZILWAN", "질완", "전투", "언데드 1체", "언데드 하나를 소멸."),
    ("마법사 6", "MASOPIC", "마소픽", "전투", "파티", "파티 전원 AC 4 개선(전투 동안)."),
    ("마법사 6", "HAMAN", "하만", "전투", "무작위", "13레벨 이상. 레벨 1을 잃고 무작위 효과 하나."),
    ("마법사 7", "MALOR", "말로르", "전투/캠프", "파티", "전투: 무작위 순간이동. 캠프: 좌표 지정 이동. 바위 속이면 파티 소실."),
    ("마법사 7", "MAHAMAN", "마하만", "전투", "파티", "13레벨 이상. 레벨 1을 잃고 하만보다 강한 무작위 효과."),
    ("마법사 7", "TILTOWAIT", "틸토웨이트", "전투", "모든 적", "모든 적에게 10d15."),
    ("사제 1", "KALKI", "칼키", "전투", "파티", "파티 전원 AC 1 개선(전투 동안)."),
    ("사제 1", "DIOS", "디오스", "언제나", "아군 1인", "아군 하나 체력 1d8 회복."),
    ("사제 1", "BADIOS", "바디오스", "전투", "적 1체", "적 하나에게 1d8."),
    ("사제 1", "MILWA", "밀와", "언제나", "파티", "잠시 빛을 밝힌다. 시야가 넓어지고 숨은 문이 보인다."),
    ("사제 1", "PORFIC", "포르픽", "전투", "자신", "시전자 AC 4 개선(전투 동안)."),
    ("사제 2", "MATU", "마투", "전투", "파티", "파티 전원 AC 2 개선(전투 동안)."),
    ("사제 2", "CALFO", "칼포", "상자", "자신", "상자 함정 이름을 알아낸다(대부분 맞음)."),
    ("사제 2", "MANIFO", "마니포", "전투", "적 1그룹", "한 그룹을 몇 라운드 굳힌다."),
    ("사제 2", "MONTINO", "몬티노", "전투", "적 1그룹", "한 그룹의 주문을 막는다."),
    ("사제 3", "LOMILWA", "로밀와", "언제나", "파티", "미궁을 나갈 때까지 빛. 숨은 문이 보인다."),
    ("사제 3", "DIALKO", "디알코", "언제나", "아군 1인", "아군 하나의 마비·수면 해제."),
    ("사제 3", "LATUMAPIC", "라투마픽", "전투", "파티", "적의 정체(진짜 이름)를 보인다."),
    ("사제 3", "BAMATU", "바마투", "전투", "파티", "파티 전원 AC 4 개선(전투 동안)."),
    ("사제 4", "DIAL", "디알", "언제나", "아군 1인", "아군 하나 체력 2d8 회복."),
    ("사제 4", "BADIAL", "바디알", "전투", "적 1체", "적 하나에게 2d8."),
    ("사제 4", "LATUMOFIS", "라투모피스", "언제나", "아군 1인", "아군 하나의 독 해제."),
    ("사제 4", "MAPORFIC", "마포르픽", "언제나", "파티", "미궁을 나갈 때까지 파티 전원 AC 2 개선."),
    ("사제 5", "DIALMA", "디알마", "언제나", "아군 1인", "아군 하나 체력 3d8 회복."),
    ("사제 5", "BADIALMA", "바디알마", "전투", "적 1체", "적 하나에게 3d8."),
    ("사제 5", "LITOKAN", "리토칸", "전투", "적 1그룹", "한 그룹에 화염 3d8."),
    ("사제 5", "KANDI", "칸디", "캠프", "사망자", "죽은 동료가 남은 위치를 알려 준다."),
    ("사제 5", "DI", "디", "캠프", "사망자 1인", "죽은 동료 하나를 체력 1로 되살린다. 실패하면 재가 된다."),
    ("사제 5", "BADI", "바디", "전투", "적 1체", "적 하나를 즉사시킬 수 있다."),
    ("사제 6", "LORTO", "로르토", "전투", "적 1그룹", "한 그룹에 6d6."),
    ("사제 6", "MADI", "마디", "언제나", "아군 1인", "아군 하나 체력 전부 회복, 사망 외 상태 해제."),
    ("사제 6", "MABADI", "마바디", "전투", "적 1체", "적 하나의 체력을 1d8만 남긴다."),
    ("사제 6", "LOKTOFEIT", "로크토페이트", "전투", "파티", "파티를 성으로 보낸다. 장비와 골드를 잃는다."),
    ("사제 7", "MALIKTO", "말릭토", "전투", "모든 적", "모든 적에게 12d6."),
    ("사제 7", "KADORTO", "카도르토", "언제나", "사망/재 1인", "죽음·재에서 체력 전부로 되살린다. 실패하면 소실."),
)

def roll_screen_kind(text):
    """Which character-creation screen is on the CGA text, or ''."""
    upper = text.upper()
    if "CREATE THIS CHARACTER" in upper:
        return "create"
    if "ENTER AGAIN TO BE SURE" in upper:
        return "password_confirm"
    if "KEEP THIS CHARACTER" in upper:
        return "keep"
    if "DON'T QUALIFY" in upper or "DONT QUALIFY" in upper:
        return "noqualify"
    if "SELECT CLASS" in upper:
        return "class"
    if re.search(r"BONUS\s+\d+", upper) and (
        "WHEN FINISHED" in upper or "STRENGTH" in upper or "ALTER SCORES" in upper
    ):
        return "stats"
    if "CHOOSE ALIGNMENT" in upper:
        return "align"
    if "CHOOSE RACE" in upper:
        return "race"
    if "ENTER PASSWORD" in upper and "NEW PASSWORD" not in upper and "ALTER" not in upper:
        return "password"
    if "ENTER A NAME FOR YOUR CHARACTER" in upper:
        return "name"
    if "REATE A CHARACTER" in upper and "NSPECT A CHARACTER" in upper:
        return "menu"
    return ""


def roll_bonus(text):
    match = re.search(r"BONUS\s+(\d+)", text.upper())
    return int(match.group(1)) if match else None


def roll_name_echo(text, typed):
    """True when the name field itself shows typed. The prompt's own letters do not count."""
    if not typed:
        return True
    want = typed.upper()
    kept = []
    for line in text.upper().splitlines():
        if "ENTER A NAME FOR YOUR CHARACTER" in line:
            line = line.split("ENTER A NAME FOR YOUR CHARACTER", 1)[1]
        elif "ENTER A NAME" in line or "YOUR CHARACTER" in line:
            line = ""
        kept.append(line)
    body = "\n".join(kept)
    return re.search(rf"(?<![A-Z]){re.escape(want)}(?![A-Z])", body) is not None


def roll_norm(text):
    return "".join(ch for ch in text.upper() if ch.isalnum() or ch == " ")


_RACE_TOOLTIPS = {
    "A": (
        "인간 (Human)\n"
        "• 기본 능력치: 힘 8  지혜 8  신앙 5  생명 8  민첩 8  운 9 (합계 46)\n"
        "• 종족 특성: 독 내성 굴림 -1 보너스\n"
        "• 특징: 모든 능력치가 균형 잡힌 만능형 (다양한 직업 적합)"
    ),
    "B": (
        "엘프 (Elf)\n"
        "• 기본 능력치: 힘 7  지혜 10  신앙 10  생명 6  민첩 9  운 6 (합계 48)\n"
        "• 종족 특성: 마법도구(완드) 내성 굴림 -2 보너스\n"
        "• 특징: 지혜·신앙심 특화 (마법사·사제·비숍 최적, 생명력 낮음)"
    ),
    "C": (
        "드워프 (Dwarf)\n"
        "• 기본 능력치: 힘 10  지혜 7  신앙 10  생명 10  민첩 5  운 6 (합계 48)\n"
        "• 종족 특성: 숨결(브레스) 내성 굴림 -4 보너스\n"
        "• 특징: 강인한 체력과 힘, 높은 신앙 (전사·사제·군주 유리, 민첩 낮음)"
    ),
    "D": (
        "노움 (Gnome)\n"
        "• 기본 능력치: 힘 7  지혜 7  신앙 10  생명 8  민첩 10  운 7 (합계 49)\n"
        "• 종족 특성: 석화(마비) 내성 굴림 -2 보너스\n"
        "• 특징: 민첩성과 신앙심 우수 (사제·도적 유리, 균형 잡힌 신체)"
    ),
    "E": (
        "호빗 (Hobbit)\n"
        "• 기본 능력치: 힘 5  지혜 7  신앙 7  생명 6  민첩 10  운 15 (합계 50)\n"
        "• 종족 특성: 주문(마법 공격) 내성 굴림 -3 보너스\n"
        "• 특징: 압도적인 운(15)과 높은 민첩 (함정 해제 도적·닌자 최적)"
    ),
}

_BONUS_TOOLTIP = (
    "상급 직업 전직/선택 조건\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "• 사무라이 (Samurai)  [성향: 선 / 중립]\n"
    "  필요 스탯: 힘 15, 지혜 11, 신앙 10, 생명 14, 민첩 10\n"
    "  ※ 드워프·엘프·노움은 보너스 18+, 인간은 23+ 필요\n"
    "\n"
    "• 로드 (Lord)  [성향: 선 전용]\n"
    "  필요 스탯: 힘 15, 지혜 12, 신앙 12, 생명 15, 민첩 14, 운 15\n"
    "  ※ 최소 33+ 필요 (초기 생성 극희귀, 전사/사제 육성 후 전직 권장)\n"
    "\n"
    "• 닌자 (Ninja)  [성향: 악 전용]\n"
    "  필요 스탯: 모든 능력치 17 이상 (힘·지·신·생·민·운 17+)\n"
    "  ※ 초기 생성 불가 (52+ 필요, 도적/전사 육성 후 전직 필수)"
)


class ToolTip:
    """Simple tooltip window shown on mouse hover."""

    def __init__(self, widget, text, delay_ms=250):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.tip_win = None
        self._after_id = None
        self.widget.bind("<Enter>", self._on_enter, add="+")
        self.widget.bind("<Leave>", self._on_leave, add="+")
        self.widget.bind("<ButtonPress>", self._on_leave, add="+")
        self.widget.bind("<Destroy>", self._on_destroy, add="+")

    def _on_enter(self, event=None):
        self._cancel()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _on_leave(self, event=None):
        self._cancel()
        self._hide()

    def _on_destroy(self, event=None):
        self._cancel()
        self._hide()

    def _cancel(self):
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        if self.tip_win or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 15
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
            self.tip_win = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.attributes("-topmost", True)
            tw.geometry(f"+{x}+{y}")
            frame = tk.Frame(tw, bg="#24273a", highlightbackground="#89b4fa", highlightthickness=1, padx=8, pady=6)
            frame.pack()
            lbl = tk.Label(frame, text=self.text, font=("맑은 고딕", 9), fg="#cdd6f4", bg="#24273a", justify=tk.LEFT)
            lbl.pack()
        except Exception:
            self._hide()

    def _hide(self):
        if self.tip_win:
            try:
                self.tip_win.destroy()
            except Exception:
                pass
            self.tip_win = None


class CharacterRoller:
    """Press one key for the screen that is showing. The next key waits until that screen changes."""

    def __init__(self):
        self.active = False
        self.game = 1
        self.name = ""
        self.race = "A"
        self.align = "A"
        self.target = 18
        self.name_i = 0
        self.line_spent = 0
        self.stat_line = 0   # which stat the cursor is on (0 strength, 1 I.Q.)
        self.waiting = False
        self.sent_at = 0.0
        self.sent_key = None
        self.sent_kind = ""
        self.seen_kind = ""
        self.sent_bonus = None
        self.sent_norm = ""
        self.sent_cursor = ()
        self.cursor = ()
        self.expect_name = ""
        self.stable_sig = None
        self.stable_hits = 0
        self.rolls = 0
        self.status = ""
        self.next_poll = 0.0

    def start(self, name, align, target, race="A", game=1):
        self.__init__()
        self.game = game
        self.active = True
        self.name = name
        self.race = race
        self.align = align
        self.target = int(target)
        self.status = "트레이닝 그라운드 화면을 기다리는 중"

    def stop(self):
        self.active = False
        self.waiting = False

    def consider(self, text, now, cursor=()):
        if not self.active:
            return None
        kind = roll_screen_kind(text)
        self.seen_kind = kind
        self.cursor = tuple(cursor)
        bonus = roll_bonus(text) if kind == "stats" else None
        sig = (kind, bonus, (roll_norm(text), self.cursor) if kind == "stats" else kind)
        if sig != self.stable_sig:
            self.stable_sig = sig
            self.stable_hits = 1
        else:
            self.stable_hits += 1
        stable = self.stable_hits >= 2
        if kind == "noqualify" and stable:
            self.active = False
            self.waiting = False
            self.status = "전직 가능한 직업이 없어 멈췄습니다"
            return None
        if self.waiting:
            if self._screen_moved(kind, bonus, text) and stable:
                self._take_move(kind, bonus)
                self.waiting = False
            elif now - self.sent_at >= 1.5 and stable:
                self.status = "화면이 그대로라 같은 키만 다시 누릅니다"
                return self.sent_key
            else:
                self.status = "화면이 바뀌길 기다리는 중"
                return None
        if not stable:
            return None
        return self._key_for_screen(kind, bonus, text)

    def _screen_moved(self, kind, bonus, text):
        key = self.sent_key
        if self.sent_kind == "menu" and key == "C":
            return kind == "name"
        if self.sent_kind == "name" and key and len(key) == 1:
            return roll_name_echo(text, self.expect_name)
        if self.sent_kind == "name" and key == "ENTER":
            return kind in (("password", "race", "create") if self.game == 5 else ("password",))
        if self.sent_kind == "password" and key == "ENTER":
            return kind in (("password_confirm", "race", "keep", "menu") if self.game == 5 else ("race",))
        if self.sent_kind == "password_confirm" and key == "ENTER":
            return kind in ("race", "keep", "menu")
        if self.sent_kind == "create" and key == "Y":
            return kind in ("password", "race", "stats", "keep", "menu")
        if self.sent_kind == "create" and key == "N":
            return kind == "menu"
        if self.sent_kind == "race" and key == self.race:
            return kind == "align"
        if self.sent_kind == "align" and key == self.align:
            return kind == "stats"
        if self.sent_kind == "stats" and key in ("UP", "+"):
            return kind == "stats" and bonus is not None and bonus < self.sent_bonus
        if self.sent_kind == "stats" and key == "ENTER":
            # The stat cursor reads as a space, so its cell is compared too (enter moves only it).
            return kind == "stats" and bonus == self.sent_bonus and (
                roll_norm(text) != self.sent_norm or self.cursor != self.sent_cursor)
        if self.sent_kind == "stats" and key == "ESC":
            return kind == "class"
        if self.sent_kind == "class" and key in ("A", "B"):
            return kind in (("keep", "create") if self.game == 5 else ("keep",))
        if self.sent_kind == "keep" and key == "N":
            return kind == "menu"
        return False

    def _take_move(self, kind, bonus):
        if self.sent_kind == "name" and self.sent_key and len(self.sent_key) == 1:
            self.name_i = len(self.expect_name)
        elif self.sent_kind == "stats" and self.sent_key in ("UP", "+") and bonus is not None:
            self.line_spent += self.sent_bonus - bonus
        elif self.sent_kind == "stats" and self.sent_key == "ENTER":
            self.line_spent = 0
            self.stat_line += 1
        elif self.sent_kind in ("keep", "create") and self.sent_key == "N":
            self.rolls += 1
            self.name_i = 0
            self.line_spent = 0
            self.stat_line = 0
            self.status = f"{self.rolls}회 취소. 트레이닝 그라운드로 돌아왔습니다"

    def mark_sent(self, key, now, bonus, kind, text):
        self.waiting = True
        self.sent_at = now
        self.sent_key = key
        self.sent_kind = kind
        self.sent_bonus = bonus
        self.sent_norm = roll_norm(text)
        self.sent_cursor = getattr(self, "cursor", ())
        self.expect_name = self.name[:self.name_i + 1] if kind == "name" and len(key) == 1 else ""

    def _key_for_screen(self, kind, bonus, text):
        if kind == "menu":
            self.status = f"{self.rolls + 1}번째. 트레이닝 그라운드에서 C"
            return "C"
        if kind == "name":
            if not roll_name_echo(text, self.name[:self.name_i]):
                self.status = "화면에 입력한 이름이 보이길 기다리는 중"
                return None
            if self.name_i < len(self.name):
                self.status = f"이름 {self.name[:self.name_i + 1]}"
                return self.name[self.name_i]
            self.status = "이름이 화면에 있습니다"
            return "ENTER"
        if kind == "create":
            return "N" if self.sent_kind == "class" else "Y"
        if kind in ("password", "password_confirm"):
            self.status = "비밀번호 화면. 엔터"
            return "ENTER"
        if kind == "race":
            label = {"A": "인간", "B": "엘프", "C": "드워프", "D": "노움", "E": "호빗"}.get(self.race, self.race)
            self.status = f"종족 화면. {label}({self.race})"
            return self.race
        if kind == "align":
            label = {"A": "선", "B": "중립", "C": "악"}.get(self.align, self.align)
            self.status = f"성향 화면. {label}"
            return self.align
        if kind == "stats" and bonus is not None:
            self.status = f"{self.rolls + 1}번째 보너스 {bonus} / 목표 {self.target}"
            if bonus >= self.target:
                self.active = False
                self.waiting = False
                self.status = f"보너스 {bonus}. 목표 {self.target} 이상이라 스탯 화면에서 멈췄습니다"
                return None
            if bonus <= 0:
                self.status = "보너스가 0입니다"
                return "ESC"
            # A hobbit (strength 5) rarely makes a fighter (11) and stops at
            # "don't qualify"; its points go to I.Q. (7, a mage needs 11).
            if self.race == "E" and self.stat_line == 0:
                self.status = f"보너스 {bonus}. 호빗은 지능부터"
                return "ENTER"
            if self.line_spent >= 8:
                self.status = f"보너스 {bonus}. 다음 능력치로 이동"
                return "ENTER"
            return "+" if self.game == 5 else "UP"
        if kind == "class":
            if self.race == "E":
                self.status = "직업 화면. 마법사(B)"
                return "B"
            self.status = "직업 화면. 전사(A)"
            return "A"
        if kind == "keep":
            self.status = "저장 질문. N"
            return "N"
        self.status = "만들 화면이 아닙니다"
        return None


class WizardryDualApp:
    _town_node = None        # Wizardry 5 castle / edge-of-town box the party is in
    _map_town_view = False   # the map shows that town map, not a maze floor
    _party_redraw = False    # heal / revive wrote memory: show HITS and STATUS from it
    _party_snap, _party_snap_at = None, 0.0

    def __init__(self, root):
        self.root = root
        self.mono_font_family = self._select_mono_font_family()

        # Hook & State
        self.hook = DOSBoxHook()
        ko_json = resource_path("wiz1_ko_data.json")
        self.state = Wizardry1State(self.hook, ko_json)

        # High-Speed CGA Screen Text Extractor
        self.unified_translations = load_unified_translations(ko_json)
        self.cga_extractor = CGATextExtractor(self.hook)
        self.cga_extractor.update_translations(self.unified_translations)
        with open(resource_path("wiz2_monsters.json"), encoding="utf-8") as f:
            self._wiz2_monsters = json.load(f)
        with open(resource_path("wiz2_items.json"), encoding="utf-8") as f:
            self._wiz2_items = screen_item_keys(json.load(f))
        with open(resource_path("wiz2_sentences.json"), encoding="utf-8") as f:
            self._wiz2_sentences = json.load(f)
        with open(resource_path("wiz3_monsters.json"), encoding="utf-8") as f:
            self._wiz3_monsters = json.load(f)
        with open(resource_path("wiz3_items.json"), encoding="utf-8") as f:
            self._wiz3_items = screen_item_keys(json.load(f))
        with open(resource_path("wiz3_sentences.json"), encoding="utf-8") as f:
            self._wiz3_sentences = json.load(f)
        with open(resource_path("wiz4_monsters.json"), encoding="utf-8") as f:
            self._wiz4_monsters = json.load(f)
        with open(resource_path("wiz4_items.json"), encoding="utf-8") as f:
            self._wiz4_items = screen_item_keys(json.load(f))
        with open(resource_path("wiz4_sentences.json"), encoding="utf-8") as f:
            self._wiz4_sentences = json.load(f)
        with open(resource_path("wiz5_monsters.json"), encoding="utf-8") as f:
            self._wiz5_monsters = json.load(f)
        with open(resource_path("wiz5_items.json"), encoding="utf-8") as f:
            self._wiz5_items = screen_item_keys(json.load(f))
        with open(resource_path("wiz5_sentences.json"), encoding="utf-8") as f:
            self._wiz5_sentences = json.load(f)
        with open(resource_path("wiz5_glyphs.json"), encoding="utf-8") as f:
            self._wiz5_glyphs = json.load(f)

        # Mode: 'companion' or 'overlay'
        self.mode = 'companion'
        settings = _load_settings()
        saved_raw = settings.get("game")
        saved_game = int(saved_raw) if saved_raw in ("1", "2", "3", "4", "5") else 1
        self._translation_game = saved_game
        if saved_game == 5:
            self.cga_extractor.update_glyphs(self._wiz5_glyphs)
            self.cga_extractor.number_templates = self._wiz5_sentences
            self.cga_extractor.monster_keys.update(self._wiz5_monsters)
            self.cga_extractor.item_keys.update(self._wiz5_items)
            t = self.unified_translations.copy()
            t.update(self._wiz5_monsters)
            t.update(self._wiz5_items)
            t.update(self._wiz5_sentences)
            self.cga_extractor.update_translations(t)
        elif saved_game == 4:
            self.cga_extractor.number_templates = self._wiz4_sentences
            self.cga_extractor.monster_keys.update(self._wiz4_monsters)
            self.cga_extractor.item_keys.update(self._wiz4_items)
            t = self.unified_translations.copy()
            t.update(self._wiz4_monsters)
            t.update(self._wiz4_items)
            t.update(self._wiz4_sentences)
            self.cga_extractor.update_translations(t)
        elif saved_game == 3:
            self.cga_extractor.monster_keys.update(self._wiz3_monsters)
            self.cga_extractor.item_keys.update(self._wiz3_items)
            t = self.unified_translations.copy()
            t.update(self._wiz3_monsters)
            t.update(self._wiz3_items)
            t.update(self._wiz3_sentences)
            self.cga_extractor.update_translations(t)
        elif saved_game == 2:
            self.cga_extractor.monster_keys.update(self._wiz2_monsters)
            self.cga_extractor.item_keys.update(self._wiz2_items)
            t = self.unified_translations.copy()
            t.update(self._wiz2_monsters)
            t.update(self._wiz2_items)
            t.update(self._wiz2_sentences)
            self.cga_extractor.update_translations(t)
        self._companion_translate = settings.get("companion_translate", False) is True
        self.theme_color = 'mono' if settings.get("color") == 'mono' else 'color'
        self._map_fow = settings.get("map_fow", True) is not False
        self.state.prevent_stat_loss = settings.get("stat_protect", True) is not False
        self.last_rect = None
        self._detached_hwnds = set()
        self._overlay_video = None
        self._overlay_box = None
        self._overlay_draw_sig = None
        self._overlay_protected = ()
        self._overlay_size = None
        self._last_heavy = 0.0
        self.trade_stage = None
        self.stairs_stage = None
        self.tavern_stage = None
        self.inspect_action = None
        self.equip_stage = None
        self.inspect_party_index = None
        self.inn_stage = None
        self.inn_party_index = None
        self.inn_message_until = 0.0
        self.shop_stage = None
        self.shop_party_index = None
        self.training_action = None
        self.scene_override = None
        self._last_state1 = 0
        self._last_party_count = 0
        self._key_down = {}
        self._spell_win = None
        self._roll_win = None
        self._map_win = None
        self._maps = None
        self._explored = None
        self._explored_dirty = False
        self._map_position = None
        self._town_node = None
        self._map_town_view = False
        self._overlay_panel_kind = None
        self._map_level = 1
        self._roll = CharacterRoller()

        # ----------------------------------------------------
        # Window 1: Companion Window (Main Root)
        # ----------------------------------------------------
        self._build_companion_window()

        # ----------------------------------------------------
        # Window 2: Transparent In-Game Overlay Window (Toplevel)
        # ----------------------------------------------------
        self._build_overlay_window()

        # Start in Companion Mode by default (100% stable, no screen blockage)
        self.set_mode('companion')
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(50, self._restore_saved_popups)

        self._poll_loop()

    def _current_companion_popups(self):
        popups = []
        map_win = getattr(self, '_map_win', None)
        if map_win is not None:
            try:
                if map_win.winfo_exists() and map_win.state() != 'withdrawn':
                    popups.append('map')
            except Exception:
                pass
        spell_win = getattr(self, '_spell_win', None)
        if spell_win is not None:
            try:
                if spell_win.winfo_exists() and spell_win.state() != 'withdrawn':
                    popups.append('spells')
            except Exception:
                pass
        return popups

    def _save_companion_popups(self):
        if self.mode == 'companion':
            _remember(companion_popups=self._current_companion_popups())

    def _restore_saved_popups(self):
        if self.mode != 'companion':
            return
        saved = _load_settings().get("companion_popups")
        if isinstance(saved, list):
            if 'map' in saved and (getattr(self, '_map_win', None) is None or not self._map_win.winfo_exists()):
                self._show_map()
            if 'spells' in saved and (getattr(self, '_spell_win', None) is None or not self._spell_win.winfo_exists()):
                self._show_spells()

    def _on_close(self):
        try:
            self._save_companion_popups()
        except Exception:
            pass
        try:
            self._save_explored()
        except Exception:
            pass
        try:
            self.cga_extractor.restore_blanked_text()
        finally:
            self.root.destroy()

    def _build_launch_section(self):
        """DOSBox path, Wizardry folder and a button that starts the game."""
        settings = _load_settings()
        dosbox = settings.get("dosbox") or _guess_dosbox()
        wiz_dir = settings.get("wiz_dir") or _guess_wiz_dir()
        self._launch_dosbox = tk.StringVar(value=dosbox)
        self._launch_dir = tk.StringVar(value=wiz_dir)
        self._launch_game_number = tk.StringVar(value=settings.get("game") if settings.get("game") in ("1", "2", "3", "4", "5") else "1")
        names = [name for name, _scale in _WINDOW_SIZES]
        self._launch_window = tk.StringVar(
            value=settings.get("window_size") if settings.get("window_size") in names else names[0])
        box = tk.Frame(self.root, bg="#181825", padx=8, pady=0)
        box.pack(fill=tk.X, pady=(6, 0))
        self._launch_frame = box

        def row(label, var, browse):
            line = tk.Frame(box, bg="#181825")
            line.pack(fill=tk.X, pady=1)
            tk.Label(line, text=label, width=12, anchor="w", font=("맑은 고딕", 8),
                     fg="#a6adc8", bg="#181825").pack(side=tk.LEFT)
            tk.Button(line, text="찾기", font=("맑은 고딕", 8), bg="#24273a", fg="#cdd6f4",
                      activebackground="#363a4f", activeforeground="#ffffff", bd=1,
                      relief=tk.SOLID, command=browse).pack(side=tk.RIGHT, padx=(2, 0))
            tk.Entry(line, textvariable=var, font=("맑은 고딕", 8), bg="#11111b", fg="#cdd6f4",
                     insertbackground="#cdd6f4", relief=tk.SOLID, bd=1).pack(
                         side=tk.LEFT, fill=tk.X, expand=True)

        row("DOSBox", self._launch_dosbox, self._browse_dosbox)
        row("위저드리 폴더", self._launch_dir, self._browse_wiz_dir)
        line = tk.Frame(box, bg="#181825")
        line.pack(fill=tk.X, pady=(3, 0))
        tk.Label(line, text="창 크기", width=12, anchor="w", font=("맑은 고딕", 8),
                 fg="#a6adc8", bg="#181825").pack(side=tk.LEFT)
        for name in names:
            tk.Radiobutton(line, text=name, variable=self._launch_window, value=name, padx=0, bd=0,
                           font=("맑은 고딕", 8), bg="#181825", fg="#cdd6f4", selectcolor="#24273a",
                           activebackground="#181825", activeforeground="#ffffff",
                           command=self._save_launch_settings).pack(side=tk.LEFT)
        line_games = tk.Frame(box, bg="#181825")
        line_games.pack(fill=tk.X, pady=(3, 0))
        for number in ("1", "2", "3", "4", "5"):
            tk.Radiobutton(line_games, text=f"{number}편", variable=self._launch_game_number, value=number,
                           command=self._save_launch_settings,
                           font=("맑은 고딕", 8),
                           bg="#181825", fg="#cdd6f4", selectcolor="#24273a",
                           activebackground="#181825", activeforeground="#ffffff").pack(side=tk.LEFT, padx=(0, 6))
        line_launch = tk.Frame(box, bg="#181825")
        line_launch.pack(fill=tk.X, pady=(4, 0))
        tk.Button(
            line_launch, text="게임 실행", font=("맑은 고딕", 10, "bold"), bg="#363a4f", fg="#f9e2af",
            activebackground="#494d64", activeforeground="#ffffff", bd=1, relief=tk.SOLID,
            command=self._launch_game,
        ).pack(fill=tk.X)

    def _fill_dosbox_path(self):
        """An empty DOSBox field takes the path of the DOSBox just connected."""
        var = getattr(self, '_launch_dosbox', None)
        if var is None or var.get().strip() or not self.hook.handle:
            return
        size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        try:
            if ctypes.windll.kernel32.QueryFullProcessImageNameW(self.hook.handle, 0, buf, ctypes.byref(size)):
                var.set(buf.value)
        except Exception:
            pass

    def _save_launch_settings(self):
        data = _load_settings()
        data["dosbox"] = self._launch_dosbox.get().strip()
        data["wiz_dir"] = self._launch_dir.get().strip()
        data["window_size"] = self._launch_window.get()
        data["game"] = self._launch_game_number.get()
        _save_settings(data)
        if not self.hook.is_alive():
            self._set_translation_game(int(self._launch_game_number.get()))
        self._sync_roll_labels()

    def _browse_dosbox(self):
        current = self._launch_dosbox.get().strip()
        path = filedialog.askopenfilename(
            parent=self.root, title="DOSBox.exe 선택",
            initialdir=os.path.dirname(current) if current else None,
            filetypes=[("DOSBox", "*.exe"), ("모든 파일", "*.*")])
        if path:
            self._launch_dosbox.set(os.path.normpath(path))
            self._save_launch_settings()

    def _browse_wiz_dir(self):
        current = self._launch_dir.get().strip()
        path = filedialog.askdirectory(
            parent=self.root, title="위저드리 폴더 선택 (게임 실행 파일이 있는 곳)",
            initialdir=current or None)
        if path:
            self._launch_dir.set(os.path.normpath(path))
            self._save_launch_settings()

    def _launch_game(self):
        """Start DOSBox with Wizardry. The user's DOSBox settings load first
        (-userconf), then our conf overrides the screen and mouse options."""
        dosbox = self._launch_dosbox.get().strip().strip('"')
        wiz_dir = self._launch_dir.get().strip().strip('"').rstrip("\\/")
        if not os.path.isfile(dosbox):
            messagebox.showerror("게임 실행", f"DOSBox 실행 파일이 없습니다:\n{dosbox or '(비어 있음)'}", parent=self.root)
            return
        if not os.path.isdir(wiz_dir):
            messagebox.showerror("게임 실행", f"위저드리 폴더가 없습니다:\n{wiz_dir or '(비어 있음)'}", parent=self.root)
            return
        names = {name.upper() for name in os.listdir(wiz_dir)}
        game_file = f"WIZ{self._launch_game_number.get()}.COM"
        if game_file not in names:
            messagebox.showerror("게임 실행", f"이 폴더에 {game_file}이 없습니다:\n{wiz_dir}", parent=self.root)
            return
        if self.hook.is_alive():
            messagebox.showinfo("게임 실행", "DOSBox가 이미 실행 중입니다.", parent=self.root)
            return
        self._save_launch_settings()
        conf = os.path.join(_app_dir(), _DOSBOX_CONF_FILE)
        try:
            os.remove(os.path.join(_app_dir(), _OLD_DOSBOX_CONF_FILE))   # written fresh on every launch
        except OSError:
            pass
        env = dict(os.environ)
        pos = _load_settings().get("dosbox_pos")
        if (isinstance(pos, list) and len(pos) == 2 and all(isinstance(v, int) for v in pos)
                and _on_a_monitor(pos[0] + 40, pos[1] + 10)):
            # SDL 1.2 puts the game picture's top-left (client area) here.
            env["SDL_VIDEO_WINDOW_POS"] = f"{pos[0]},{pos[1]}"
        try:
            with open(conf, "w", encoding="ascii") as f:
                f.write(_DOSBOX_CONF.format(window=_big_window_size(dict(_WINDOW_SIZES)[self._launch_window.get()])))
            # DOSBox 0.74 has no -set; -conf after -userconf overrides it.
            subprocess.Popen(
                [dosbox, "-userconf", "-conf", conf,
                 "-c", f'mount k "{wiz_dir}"', "-c", "k:", "-c", game_file, "-noconsole"],
                cwd=os.path.dirname(dosbox), close_fds=True, env=env)
        except Exception as exc:
            self._log_error()
            messagebox.showerror("게임 실행", f"DOSBox를 실행하지 못했습니다:\n{exc}", parent=self.root)
            return
        self._launched_at = time.monotonic()
        self._last_connect_try = 0.0
        self.comp_status.config(text="DOSBox 실행 중... 연결 대기")

    def _on_companion_configure(self, event):
        """Save the companion's position half a second after it stops moving."""
        if event.widget is not self.root or self.root.state() != "normal":
            return
        job = getattr(self, "_companion_pos_job", None)
        if job:
            self.root.after_cancel(job)
        self._companion_pos_job = self.root.after(500, self._save_companion_pos)

    def _save_companion_pos(self):
        self._companion_pos_job = None
        here = _parse_geometry(self.root.geometry())
        if here and self.root.state() == "normal":
            _remember(companion_pos=[here[2], here[3]])

    def _dark_titlebar(self, win):
        """Dark caption (Win10 1809+/Win11) so the title bar matches the #181825 windows."""
        def apply(_event=None):
            try:
                hwnd = int(user32.GetAncestor(win.winfo_id(), GA_ROOT) or win.winfo_id())
                dwm = ctypes.windll.dwmapi
                for attr, val in ((20, 1), (35, 0x00251818)):   # dark mode, caption color (BGR)
                    dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(ctypes.c_int(val)), 4)
            except (OSError, AttributeError, tk.TclError):
                pass
        apply()
        win.bind("<Map>", apply, add="+")

    def _build_companion_window(self):
        self.root.title("WizKR")
        self._dark_titlebar(self.root)
        try:
            # default= gives every later Toplevel (map, spells) the icon too.
            self.root.iconbitmap(default=resource_path("wiz_icon.ico"))
        except tk.TclError:
            pass
        # Where the user last left it (it snaps beside DOSBox once connected).
        pos = _load_settings().get("companion_pos")
        if not (isinstance(pos, list) and len(pos) == 2 and all(isinstance(v, int) for v in pos)
                and _on_a_monitor(pos[0] + 40, pos[1] + 10)):
            pos = [100, 100]
        self.root.geometry(f"360x300+{pos[0]}+{pos[1]}")
        self.root.bind("<Configure>", self._on_companion_configure, add="+")
        self.root.configure(bg="#181825")
        self.root.attributes("-topmost", True)

        # Header Bar
        hdr = tk.Frame(self.root, bg="#11111b", padx=10, pady=6)
        hdr.pack(fill=tk.X)

        tk.Label(
            hdr,
            text="WIZARDRY 한글 컴패니언",
            font=("맑은 고딕", 11, "bold"),
            fg="#89b4fa",
            bg="#11111b",
            anchor="w",
        ).pack(fill=tk.X)

        btn_bar = tk.Frame(hdr, bg="#11111b")
        btn_bar.pack(fill=tk.X, pady=(6, 0))

        self.btn_to_overlay = tk.Button(
            btn_bar,
            text="오버레이",
            font=("맑은 고딕", 10, "bold"),
            bg="#363a4f",
            fg="#cdd6f4",
            activebackground="#494d64",
            activeforeground="#ffffff",
            bd=1,
            relief=tk.SOLID,
            command=lambda: self.set_mode('overlay')
        )
        self.btn_to_overlay.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        self.btn_to_color = tk.Button(
            btn_bar, text="", font=("맑은 고딕", 10, "bold"), bg="#363a4f",
            activebackground="#494d64", activeforeground="#ffffff", bd=1,
            relief=tk.SOLID, command=self.toggle_color_mode,
        )
        self.btn_to_color.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        self._sync_color_button()

        row2 = tk.Frame(hdr, bg="#11111b")
        row2.pack(fill=tk.X, pady=(4, 0))
        self.btn_to_translate = tk.Button(
            row2, text="", font=("맑은 고딕", 10, "bold"), bg="#363a4f",
            activebackground="#494d64", activeforeground="#ffffff", bd=1,
            relief=tk.SOLID, command=self._toggle_companion_translation,
        )
        self.btn_to_translate.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        self._sync_translate_button()
        self.btn_stat = tk.Button(
            row2, text="", font=("맑은 고딕", 10, "bold"), bg="#363a4f",
            activebackground="#494d64", activeforeground="#ffffff", bd=1,
            relief=tk.SOLID, command=self._toggle_stat_protection,
        )
        self.btn_stat.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        self.btn_reset_map = tk.Button(
            hdr, text="지도 초기화", font=("맑은 고딕", 10, "bold"), bg="#363a4f",
            fg="#f38ba8", activebackground="#494d64", activeforeground="#ffffff",
            bd=1, relief=tk.SOLID, command=self._reset_all_explored,
        )
        self.btn_reset_map.pack(fill=tk.X, pady=(4, 0))
        self.comp_stat_note = tk.Label(
            hdr, text="", font=("맑은 고딕", 8),
            fg="#89dceb", bg="#11111b", anchor="w", justify=tk.LEFT, wraplength=330,
        )
        self._build_launch_section()

        # Footer (Pack FIRST to guarantee it never gets pushed off screen)
        ftr = tk.Frame(self.root, bg="#11111b", padx=10, pady=5)
        ftr.pack(fill=tk.X, side=tk.BOTTOM)
        self.comp_status = tk.Label(ftr, text="DOSBox 연결 대기 중...", font=("맑은 고딕", 8), fg="#6c7086", bg="#11111b")
        self.comp_status.pack(side=tk.LEFT)
        self.btn_reconnect = tk.Button(
            ftr,
            text="DOSBox 재연결",
            font=("맑은 고딕", 8, "bold"),
            bg="#363a4f",
            fg="#89b4fa",
            activebackground="#494d64",
            activeforeground="#ffffff",
            bd=1,
            relief=tk.SOLID,
            command=self._reconnect_dosbox
        )
        self.btn_reconnect.pack(side=tk.RIGHT)

        # Main Container (Padded inside remaining window area)
        container = tk.Frame(self.root, bg="#181825", padx=8, pady=0)
        container.pack(fill=tk.X)

        BTN_GAP = 4
        SECTION_GAP = 12

        def side_button(text, command, fg="#cdd6f4", pady=(0, BTN_GAP)):
            btn = tk.Button(
                container,
                text=text,
                font=("맑은 고딕", 10, "bold"),
                bg="#24273a",
                fg=fg,
                activebackground="#363a4f",
                activeforeground="#ffffff",
                bd=1,
                relief=tk.SOLID,
                command=command,
            )
            btn.pack(fill=tk.X, pady=pady)
            return btn

        # 2. 주문 보기 & 지도 (섹션 간격 12px, 버튼 사이 4px)
        side_button("지도 (F1)", self._toggle_map, pady=(SECTION_GAP, BTN_GAP))
        side_button("주문 보기 (F2)", self._toggle_spells, pady=(0, BTN_GAP))
        self.btn_items = side_button("아이템 도감 (F3)", self._toggle_items, pady=(0, 0))

        # 3. 파티 조작 & 캐릭터 만들기 (섹션 간격 12px, 버튼 사이 4px, 하단 간격 12px)
        self.btn_identify = side_button("미감정 아이템 감정", self._identify_party, pady=(SECTION_GAP, BTN_GAP))
        self.btn_heal = side_button("체력 회복", self._heal_party, pady=(0, BTN_GAP))
        self.btn_revive = side_button("죽은 동료 부활", self._revive_party, pady=(0, BTN_GAP))
        self.btn_roll = side_button("캐릭터 만들기", self._on_roll_button, pady=(0, SECTION_GAP))
        self.comp_roll_note = tk.Label(
            container, text="", font=("맑은 고딕", 8),
            fg="#f9e2af", bg="#181825", anchor="w", justify=tk.LEFT, wraplength=330,
        )
        self._sync_roll_labels()
        self._refresh_stat_button()

        # Focus redirection: When companion window is clicked, restore focus to DOSBox
        self.root.bind("<Configure>", self._on_root_configure, add="+")
        self.root.bind_all("<Button-1>", self._on_companion_click)
        self.root.bind("<FocusIn>", self._on_companion_focus, add="+")

    def _on_companion_focus(self, event):
        if event.widget is self.root and self.mode == 'companion':
            self.root.after_idle(self._focus_dosbox)

    def _on_root_configure(self, event):
        if event.widget is not self.root:
            return
        if self.mode == 'companion':
            self._place_roll_window()
            self._place_map_window()
            self._place_spell_window()

    def _on_companion_click(self, event=None):
        """Return input focus to DOSBox. The spell list keeps the click so it can scroll."""
        if event is not None:
            if isinstance(event.widget, tk.Entry):
                return   # typing a path: keep the focus here
            for held_name in ("_spell_win", "_roll_win", "_map_win"):
                held = getattr(self, held_name, None)
                if held is None:
                    continue
                try:
                    if not held.winfo_exists():
                        continue
                    widget = event.widget
                    while widget is not None:
                        if widget == held:
                            return
                        widget = getattr(widget, "master", None)
                except Exception:
                    pass
        if self.hook.hwnd and user32.IsWindow(self.hook.hwnd):
            self.root.after(30, self._focus_dosbox)

    def _flash_buttons(self, buttons, text):
        """Show a result on the buttons for a moment, then restore their labels."""
        for btn in buttons:
            if btn is None:
                continue
            label = getattr(btn, '_label', None) or btn.cget('text')
            btn._label = label
            btn.config(text=text)
            self.root.after(1500, lambda b=btn, t=label: b.winfo_exists() and b.config(text=t))

    def _write_party_debug(self, action, notes, names):
        """Read-only dump of the party records for checking offsets."""
        if RELEASE:
            return
        try:
            with open(dev_path('logs', 'wiz_party_debug.log'), 'w', encoding='utf-8') as handle:
                handle.write(time.strftime('[%Y-%m-%d %H:%M:%S] ') + action + '\n')
                handle.write('\n'.join(notes) + '\n')
                handle.write(f"written: {names}\n")
        except OSError:
            pass

    def _wiz2_in_town(self):
        """Town is the floor word 65535. The maze keeps a floor of 1-6."""
        anchor = self.state._wiz2_anchor
        if self.state.game != 2 or not anchor or self.state._wiz2_state1 in (0, 10148, 21574):
            return False
        raw = self.hook.read_bytes(anchor + 48462, 2)
        # A game loaded straight into the castle still has floor 0 (read live), not 65535.
        return bool(raw and len(raw) == 2 and raw[0] == raw[1] and raw[0] in (0, 0xFF))

    def _wiz3_in_town(self):
        """Town is the floor word 65535. The maze keeps a floor of 1-6."""
        anchor = self.state._wiz3_anchor
        if self.state.game != 3 or not anchor:
            return False
        raw = self.hook.read_bytes(anchor + 48628, 2)
        # Like Wizardry 2: a game that has not been in the maze yet has floor 0 (read live).
        return bool(raw and len(raw) == 2 and raw[0] == raw[1] and raw[0] in (0, 0xFF))

    def _party_action(self, action, buttons, verb):
        # Castle and town only. In the maze it would skip the game's risk.
        if not self._in_town():
            self._flash_buttons(buttons, "성에서만 가능")
            self._focus_dosbox()
            return
        notes = []
        names = getattr(self.state, action)(notes)
        self._write_party_debug(action, notes, names)
        if names:
            self._party_redraw, self._party_snap = True, None
            self._overlay_draw_sig = None
            text = f"{len(names)}명 {verb}"
        elif any(n.startswith('FAIL') or n == 'anchor: none' for n in notes):
            text = "파티 읽기 실패"
        else:
            text = f"{verb}할 동료 없음"
        self._flash_buttons(buttons, text)
        self._focus_dosbox()

    def _in_town(self):
        if self.state.game == 5:
            anchor = self.state._wiz5_anchor
            raw = self.hook.read_bytes(anchor + 77458, 2) if anchor is not None else None
            # WAW GetMainState: town entrance, castle, tavern, inn, shop, temple.
            return bool(raw and len(raw) == 2 and int.from_bytes(raw, 'little') in {
                33706, 34002, 34196, 34208, 34212, 34246, 34248,
                34296, 34632, 35104, 35516, 35720, 36178, 36298})
        return ((self.state.game == 1 and self.state.state1 in _TOWN_STATE1)
                or self._wiz2_in_town() or self._wiz3_in_town())

    def _party_snapshot(self):
        now = time.monotonic()
        if self._party_snap is None or now - self._party_snap_at > 0.3:
            self._party_snap, self._party_snap_at = self.state._party_records(), now
        return self._party_snap

    def _draw_party_updates(self, lines, scale_x, scale_y, font):
        """After heal / revive the game's party list still shows the old HITS
        and STATUS. Paint the values now in memory over them (screen buffer
        untouched). A redrawn list matches memory and is left alone."""
        if not self._party_redraw:
            return
        if not self._in_town():
            self._party_redraw = False
            return
        records = self._party_snapshot()
        for line in lines or ():
            m = _PARTY_ROW_RE.match(line['text'])
            if not m or int(m.group(1)) > len(records):
                continue
            _, name, status, hp, hp_max = records[int(m.group(1)) - 1]
            if status != 0:
                continue
            color = _LOW_HP_COLOR if hp * 3 <= hp_max else self.get_color('white')
            for group, text in ((3, str(hp)), (4, str(hp_max))):
                if m.group(group) == text:
                    continue
                start, end = m.span(group)
                first = min(start, end - len(text))
                self.canvas.create_rectangle(first * 8 * scale_x, line['y'] * scale_y, end * 8 * scale_x,
                                             (line['y'] + 8) * scale_y, fill='#000000', outline='')
                for i, ch in enumerate(text):
                    self.canvas.create_text(((end - len(text) + i) * 8 + 4) * scale_x, (line['y'] + 4) * scale_y,
                                            anchor='center', text=ch, fill=color, font=font)

    def _heal_party(self):
        self._party_action('heal_party', (getattr(self, 'btn_heal', None),), "회복")

    def _revive_party(self):
        self._party_action('revive_party', (getattr(self, 'btn_revive', None),), "부활")

    def _identify_party(self):
        self._party_action('identify_party', (getattr(self, 'btn_identify', None),), "감정")

    def _toggle_companion_translation(self):
        self._companion_translate = not getattr(self, '_companion_translate', False)
        _remember(companion_translate=bool(self._companion_translate))
        if not self._companion_translate:
            if self.over.winfo_exists() and self.over.winfo_viewable():
                self.over.withdraw()
            self.canvas.delete("all")
            self.cga_extractor.restore_blanked_text()
            self.cga_extractor.reset_blank_shadow()
            self._overlay_video = None
            self._overlay_draw_sig = None
        else:
            self._overlay_video = None
            self._overlay_draw_sig = None
            self.cga_extractor.reset_blank_shadow()
            if self.hook.is_alive():
                self._snap_overlay()
        self._sync_translate_button()
        self._focus_dosbox()

    def _sync_translate_button(self):
        btn = getattr(self, 'btn_to_translate', None)
        if btn is not None:
            on = getattr(self, '_companion_translate', False)
            btn.config(
                text="번역: 켜짐" if on else "번역: 꺼짐",
                fg="#a6e3a1" if on else "#cdd6f4",
            )

    def _current_game(self):
        if self.state.game:
            return self.state.game
        if hasattr(self, '_launch_game_number'):
            try:
                return int(self._launch_game_number.get())
            except (ValueError, TypeError):
                pass
        return 1

    def _toggle_stat_protection(self):
        self.state.prevent_stat_loss = not self.state.prevent_stat_loss
        _remember(stat_protect=bool(self.state.prevent_stat_loss))
        self._refresh_stat_button()

    def _refresh_stat_button(self):
        on = bool(self.state.prevent_stat_loss)
        self.btn_stat.config(
            text="스탯 보호: 켜짐" if on else "스탯 보호: 꺼짐",
            fg="#a6e3a1" if on else "#f38ba8",
            # Party records are read for 1-3 only (4: Werdna alone, 5: record layout of stats unknown).
            state=tk.DISABLED if self._current_game() in (4, 5) else tk.NORMAL,
        )

    def _ui_k(self):
        """Overlay UI scale: 1 up to a 960-pixel-high game picture, then in
        proportion (a 4K fullscreen made the buttons and map tiny)."""
        size = getattr(self, '_overlay_size', None)
        if not size or not size[1]:
            return 1.0
        return max(1.0, size[1] / 960.0)

    def _ovf(self, pt, *style):
        """Overlay font scaled with the game picture (pixel size)."""
        return (self.mono_font_family, -max(8, round(pt * 4 / 3 * self._ui_k())), *style)

    def _close_overlay_panel(self):
        panel = getattr(self, '_overlay_panel', None)
        if panel is not None:
            panel.destroy()
        self._overlay_panel = None
        self._overlay_panel_kind = None
        if self.mode == 'overlay':
            self._snap_overlay()

    def _open_overlay_panel(self, kind):
        if getattr(self, '_overlay_panel_kind', None) == kind:
            self._close_overlay_panel()
            return None
        self._close_overlay_panel()
        panel = tk.Frame(self.control, bg='#000000', highlightbackground='#ffffff', highlightthickness=2)
        panel.pack(fill=tk.BOTH, expand=True)
        self._overlay_panel = panel
        self._overlay_panel_kind = kind
        header = tk.Frame(panel, bg='#000000')
        header.pack(fill=tk.X, padx=6, pady=2)
        tk.Label(header, text=kind, bg='#000000', fg='#ffffff', font=self._ovf(11)).pack(side=tk.LEFT)
        tk.Button(header, text='닫기', command=self._close_overlay_panel,
                  font=self._ovf(9), bg='#000000', fg='#ffffff',
                  activebackground='#ffffff', activeforeground='#000000', relief=tk.SOLID, bd=1).pack(side=tk.RIGHT)
        body = tk.Frame(panel, bg='#000000')
        body.pack(fill=tk.BOTH, expand=True)
        self._snap_overlay()
        return body

    def _toggle_items(self):
        win = getattr(self, '_item_win', None)
        if win is not None and win.winfo_exists():
            win.destroy()
            self._item_win = None
        else:
            self._show_items()

    def _show_items(self):
        """Item book: every item of the disk with its stats (1-5, read only)."""
        from tkinter import ttk
        win = getattr(self, '_item_win', None)
        if win is not None and win.winfo_exists():
            win.deiconify()
            win.lift()
            return
        game = self._current_game()
        try:
            items = _read_item_book(self._wiz_dir(), game)
        except (OSError, ValueError) as exc:
            messagebox.showinfo("아이템 도감", str(exc))
            return
        ko = {}
        for key, val in self.cga_extractor.translations.items():
            ko.setdefault(key, val.get('ko', '') if isinstance(val, dict) else str(val))
        win = tk.Toplevel(self.root)
        self._item_win = win
        win.title("아이템 도감")
        win.configure(bg="#181825")
        win.transient(self.root)
        win.attributes("-topmost", bool(self.root.attributes("-topmost")))
        win.geometry("1100x520")
        here = _parse_geometry(self.root.geometry())
        saved = _load_settings().get("item_window")   # [x, y, w, h], Tk geometry
        if (isinstance(saved, list) and len(saved) == 4 and all(isinstance(v, int) for v in saved)
                and _on_a_monitor(saved[0] + 40, saved[1] + 10)):
            win.geometry(f"{max(200, saved[2])}x{max(120, saved[3])}+{saved[0]}+{saved[1]}")
        elif here:
            win.geometry(f"+{here[2]}+{here[3] + here[1] + 2}")
        cols = (("name", "이름", 220), ("type", "종류", 70), ("price", "가격", 60), ("dice", "공격", 50),
                ("ac", "방어", 45), ("align", "성향", 50), ("cls", "사용 직업", 200), ("effect", "특수 효과", 420))
        style = ttk.Style(win)
        self._dark_titlebar(win)
        style.theme_use("clam")   # the native theme ignores colors
        style.configure("Items.Treeview", rowheight=22, font=("맑은 고딕", 9), background="#181825",
                        fieldbackground="#181825", foreground="#cdd6f4", borderwidth=0)
        style.map("Items.Treeview", background=[("selected", "#363a4f")], foreground=[("selected", "#f9e2af")])
        style.configure("Items.Treeview.Heading", font=("맑은 고딕", 9, "bold"), background="#24273a",
                        foreground="#89b4fa", relief="flat")
        style.map("Items.Treeview.Heading", background=[("active", "#363a4f")])
        style.configure("Vertical.TScrollbar", background="#363a4f", troughcolor="#181825",
                        arrowcolor="#cdd6f4", bordercolor="#181825")
        tree = ttk.Treeview(win, columns=[c[0] for c in cols], show="headings", style="Items.Treeview")
        scroll = ttk.Scrollbar(win, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True)
        rows = []
        # Item names inside the effect text ("... BAG OF GEMS(으)로 변함") in Korean too.
        ko_names = sorted(((it['en'], _item_ko(ko, it['en'])) for it in items), key=lambda p: -len(p[0]))
        name_re = re.compile('(?:' + '|'.join(re.escape(en) for en, k in ko_names if k) + r')(?=\(으\)로|\(이\)가)') if any(k for _, k in ko_names) else None
        ko_of = dict(ko_names)
        for it in items:
            name = _item_ko(ko, it['en']) or it['en']
            if it['cursed']:
                name += " (저주)"
            allc = len(it['classes']) == len(_ITEM_CLASSES)
            rows.append({
                'name': f"{name}  {it['en']}" if name != it['en'] else name,
                'type': it['type'], 'price': it['price'] or 0, 'dice': it['dice'],
                'ac': it['ac'] or "", 'align': it['align'],
                'cls': "모두" if allc else ", ".join(it['classes']),
                'effect': (name_re.sub(lambda m: ko_of[m.group(0)], "; ".join(it['effect'])) if name_re
                           else "; ".join(it['effect'])),
            })
        for c, label, width in cols:
            tree.heading(c, text=label)
            tree.column(c, width=width, anchor="w" if c in ("name", "cls", "effect") else "center")
        order = {'col': None, 'rev': False}

        def fill():
            tree.delete(*tree.get_children())
            for r in rows:
                tree.insert("", tk.END, values=[r[c[0]] if c[0] != 'price' else (r['price'] or "—") for c in cols])

        def sort_by(col, rev=None):
            order['rev'] = (not order['rev'] if order['col'] == col else False) if rev is None else rev
            order['col'] = col
            rows.sort(key=lambda r: (r[col] == "", r[col]) if col != 'price' else r[col], reverse=order['rev'])
            fill()
            _remember(item_sort=[col, order['rev']])

        for c, _, _ in cols:
            tree.heading(c, command=lambda col=c: sort_by(col))
        saved_sort = _load_settings().get("item_sort")   # [column, reversed]
        if (isinstance(saved_sort, list) and len(saved_sort) == 2
                and saved_sort[0] in [c[0] for c in cols] and isinstance(saved_sort[1], bool)):
            sort_by(*saved_sort)
        else:
            fill()

        # Columns grow with the window in their proportions, but never past
        # their longest text.
        cell_font = tkfont.Font(root=win, font=("맑은 고딕", 9))
        head_font = tkfont.Font(root=win, font=("맑은 고딕", 9, "bold"))
        pad = 16
        longest = {c: max([head_font.measure(label)] + [cell_font.measure(str(r[c] if c != 'price' else (r[c] or "—")))
                                                         for r in rows]) + pad
                   for c, label, _ in cols}

        def fit_columns(event=None):
            left = tree.winfo_width()
            if left <= 1:
                return
            open_cols = {c: base for c, _, base in cols}
            widths = {}
            while open_cols:
                total = sum(open_cols.values())
                capped = [c for c, base in open_cols.items() if left * base / total >= longest[c]]
                if not capped:
                    for c, base in open_cols.items():
                        widths[c] = max(20, int(left * base / total))
                    break
                for c in capped:
                    widths[c] = longest[c]
                    left -= longest[c]
                    del open_cols[c]
            for c, width in widths.items():
                if tree.column(c, 'width') != width:
                    tree.column(c, width=width, stretch=False)
        tree.bind("<Configure>", fit_columns, add="+")

        # A cell cut by its column shows its whole text under the mouse.
        tip = {'win': None, 'cell': None}

        def hide_tip(event=None):
            if tip['win'] is not None:
                tip['win'].destroy()
            tip['win'], tip['cell'] = None, None

        def on_motion(event):
            row, col = tree.identify_row(event.y), tree.identify_column(event.x)
            if not row or not col or tree.identify_region(event.x, event.y) != 'cell':
                hide_tip()
                return
            index = int(col[1:]) - 1
            text = str(tree.item(row, 'values')[index])
            if cell_font.measure(text) + pad <= tree.column(cols[index][0], 'width'):
                hide_tip()
                return
            if tip['cell'] != (row, col):
                hide_tip()
                tip['cell'] = (row, col)
                tip['win'] = tw = tk.Toplevel(win)
                tw.wm_overrideredirect(True)
                tw.attributes("-topmost", True)
                tk.Label(tw, text=text, font=("맑은 고딕", 9), fg="#cdd6f4", bg="#24273a", padx=8, pady=4,
                         highlightbackground="#89b4fa", highlightthickness=1).pack()
            tip['win'].geometry(f"+{event.x_root + 14}+{event.y_root + 18}")
        tree.bind("<Motion>", on_motion, add="+")
        tree.bind("<Leave>", hide_tip, add="+")

        # Size and place are kept (item_window), saved half a second after a change.
        job = {'id': None}

        def save_geometry():
            job['id'] = None
            g = _parse_geometry(win.geometry()) if win.winfo_exists() else None
            if g and win.state() == 'normal':
                _remember(item_window=[g[2], g[3], g[0], g[1]])

        def on_configure(event):
            if event.widget is win:
                if job['id'] is not None:
                    win.after_cancel(job['id'])
                job['id'] = win.after(500, save_geometry)
        win.bind("<Configure>", on_configure, add="+")

        def close():
            hide_tip()
            if job['id'] is not None:
                win.after_cancel(job['id'])
            save_geometry()
            win.destroy()
            self._item_win = None
        win.protocol("WM_DELETE_WINDOW", close)

    def _show_spells(self):
        if self.mode == 'overlay':
            win = self._open_overlay_panel('주문')
            if win is None:
                return
        else:
            win = getattr(self, "_spell_win", None)
            if win is not None and win.winfo_exists():
                win.deiconify()
                win.lift()
                return
            win = tk.Toplevel(self.root)
            self._spell_win = win
            self._spell_win_placed = False
            win.title("주문")
            win.configure(bg="#181825")
            self._dark_titlebar(win)
            win.transient(self.root)
            win.attributes("-topmost", bool(self.root.attributes("-topmost")))
            def _close_spells():
                win.destroy()
                self._spell_win = None
                self._save_companion_popups()
            win.protocol("WM_DELETE_WINDOW", _close_spells)
        overlay = self.mode == 'overlay'
        frame = tk.Frame(win, bg="#000000" if overlay else "#181825")
        frame.pack(fill=tk.BOTH, expand=True)
        mono = self.theme_color == 'mono'
        bg = '#000000' if overlay else '#181825'
        kinds = [(k, c) for k, c, _ in _SPELL_KINDS] + [_SPELL_OTHER]
        self._spell_filter = None   # None shows every spell

        def spell_items(category):
            """[(text, colour, bold)]: headings are bold and white, a blank is None."""
            items = []
            current = None
            for group, en, ko, when, target, effect in SPELL_BOOK:
                kind, color = _SPELL_KIND_OF.get(en, _SPELL_OTHER)
                if category and not group.startswith(category):
                    continue
                if self._spell_filter and kind != self._spell_filter:
                    continue
                if group != current:
                    if items:
                        items.append(("", None, False))
                    items.append((group, '#ffffff', True))
                    current = group
                color = '#ffffff' if mono else color
                items.append((f"{ko}  {en}  ·  {when}, {target}", color, False))
                items.append((f"  {effect}", color, False))
            return items

        # Filter bar: all, then each kind in its own colour.
        bar = tk.Frame(frame, bg=bg)
        bar.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(8, 0))
        filter_buttons = {}

        def choose(kind):
            self._spell_filter = kind
            for key, btn in filter_buttons.items():
                on = key == kind
                btn.config(relief=tk.SUNKEN if on else tk.FLAT, bg='#45475a' if on else bg)
            render()

        for kind, color in [(None, '#ffffff')] + kinds:
            btn = tk.Button(bar, text=kind or '전체', fg='#ffffff' if mono else color, bg=bg,
                            activebackground='#45475a', activeforeground='#ffffff', relief=tk.FLAT,
                            bd=2, padx=8, pady=0, cursor='hand2',
                            font=self._ovf(10, 'bold') if overlay else ("맑은 고딕", 9, "bold"),
                            command=lambda k=kind: choose(k))
            btn.pack(side=tk.LEFT, padx=(0, 6))
            filter_buttons[kind] = btn

        if overlay:
            scroll = tk.Scrollbar(frame)
            scroll.pack(side=tk.RIGHT, fill=tk.Y)
            canvas = tk.Canvas(frame, bg='#000000', highlightthickness=0, yscrollcommand=scroll.set)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scroll.config(command=canvas.yview)
            columns = tk.Frame(canvas, bg='#000000')
            item = canvas.create_window(0, 0, window=columns, anchor='nw')
            labels = []
            cols = []
            for index in range(2):
                columns.grid_columnconfigure(index, weight=1, uniform='spell_columns')
                col = tk.Frame(columns, bg='#000000')
                col.grid(row=0, column=index, sticky='nsew', padx=(10, 20) if index == 0 else (20, 10), pady=8)
                cols.append(col)
            wrap = {'width': 1}

            def wheel(event):
                canvas.yview_scroll(-int(event.delta / 120), 'units')

            def render():
                labels.clear()
                for col, category in zip(cols, ('마법사', '사제')):
                    for child in col.winfo_children():
                        child.destroy()
                    for text, color, bold in spell_items(category):
                        label = tk.Label(col, text=text or " ", bg='#000000', fg=color or '#ffffff',
                                         font=self._ovf(10, 'bold') if bold else self._ovf(10),
                                         anchor='nw', justify=tk.LEFT, wraplength=wrap['width'])
                        label.pack(fill=tk.X, anchor='nw')
                        label.bind('<MouseWheel>', wheel)
                        labels.append(label)
                canvas.yview_moveto(0)

            def resize_columns(event):
                canvas.itemconfigure(item, width=event.width)
                wrap['width'] = max(1, (event.width - 60) // 2)
                for label in labels:
                    label.config(wraplength=wrap['width'])
            canvas.bind('<Configure>', resize_columns)
            columns.bind('<Configure>', lambda event: canvas.configure(scrollregion=canvas.bbox('all')))
            for widget in (canvas, columns):
                widget.bind('<MouseWheel>', wheel)
            choose(None)
        else:
            scroll = tk.Scrollbar(frame)
            scroll.pack(side=tk.RIGHT, fill=tk.Y)
            text = tk.Text(frame, wrap=tk.WORD, font=("맑은 고딕", 10), bg="#11111b",
                           fg="#cdd6f4", insertbackground="#cdd6f4", relief=tk.FLAT,
                           padx=10, pady=8, yscrollcommand=scroll.set)
            text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scroll.config(command=text.yview)
            text.tag_configure('bold', font=("맑은 고딕", 10, "bold"))

            def render():
                text.config(state=tk.NORMAL)
                text.delete('1.0', tk.END)
                for line, color, bold in spell_items(''):
                    tags = []
                    if color:
                        text.tag_configure(f"c{color}", foreground=color)
                        tags.append(f"c{color}")
                    if bold:
                        tags.append('bold')
                    text.insert(tk.END, line + "\n", tuple(tags))
                text.config(state=tk.DISABLED)
                text.yview_moveto(0)
            choose(None)
            self._place_spell_window()
            win.deiconify()
            win.lift()
            self._save_companion_popups()

    def _wiz_dir(self):
        """The Wizardry folder in the companion field, saved or not."""
        launch_dir = getattr(self, '_launch_dir', None)
        return ((launch_dir.get().strip().strip('"') if launch_dir is not None else "")
                or _load_settings().get("wiz_dir"))

    def _load_maps(self):
        """Maze data read from the user's WIZ1.DSK (not shipped with the exe)."""
        current_game = self._current_game()
        if self._translation_game != current_game:
            raise OSError("이전 게임의 탐험 기록을 저장하지 못했습니다.")
        if self._maps is not None:
            return self._maps
        # Exploration asks every tick; do not reread a missing disk that often.
        now = time.monotonic()
        if now - getattr(self, '_maps_failed_at', -10.0) < 5.0:
            raise FileNotFoundError(self._maps_error)
        wiz_dir = self._wiz_dir()
        try:
            game = current_game
            maps = _read_maze(wiz_dir, game)
        except OSError as exc:
            maps, reason = None, str(exc)
        else:
            reason = (f"위저드리 폴더에서 WIZ{game}.DSK 또는 SAVE{game}.DSK를 찾지 못했습니다. 컴패니언의 '위저드리 폴더'를 지정하세요."
                      if wiz_dir else "컴패니언의 '위저드리 폴더'를 지정하세요.")
        if maps is None:
            self._maps_failed_at, self._maps_error = now, reason
            raise FileNotFoundError(reason)
        self._maps = maps
        return maps

    def _show_map(self):
        overlay = self.mode == 'overlay'
        if overlay:
            win = self._open_overlay_panel('지도')
            if win is None:
                return
        else:
            win = getattr(self, "_map_win", None)
            if win is not None and win.winfo_exists():
                win.deiconify()
                win.lift()
                return
            win = tk.Toplevel(self.root)
            self._map_win = win
            self._map_win_placed = False
            win.title("미궁 지도")
            win.configure(bg="#181825")
            self._dark_titlebar(win)
            # Owned by the companion so it never opens behind it; the user sizes it.
            win.transient(self.root)
            win.attributes("-topmost", bool(self.root.attributes("-topmost")))
            def _close_map():
                win.destroy()
                self._map_win = None
                self._save_companion_popups()
            win.protocol("WM_DELETE_WINDOW", _close_map)
        self._refresh_map_position()
        self._refresh_map_darkness()
        self._record_explored()
        try:
            self._dump_maze_once()
        except Exception:
            self._log_error()
        self._map_level = self._map_position[0] if self._map_position else 1
        rect = self.hook.get_client_rect_on_screen() if overlay else None
        self._map_cell = _MAP_CELL
        bg = "#000000" if overlay else "#181825"
        levels = tk.Frame(win, bg=bg)
        levels.pack(fill=tk.X, padx=8, pady=(8, 0))
        self._map_level_btns = []
        game = self._current_game()
        max_floor = 9 if game == 5 else (15 if game == 4 else (7 if game in (2, 3) else 11))
        self._map_town_btn = None
        if game in (1, 2, 3, 5):   # 0층: the castle and edge of town, with the party's box when in town
            self._map_town_btn = tk.Button(
                levels, text="성", font=self._ovf(11) if overlay else ("맑은 고딕", 9, "bold"), width=2,
                bg="#000000" if overlay else "#24273a", fg="#ffffff" if overlay else "#cdd6f4",
                activebackground="#ffffff" if overlay else "#363a4f",
                activeforeground="#000000" if overlay else "#ffffff", bd=1, relief=tk.SOLID,
                command=self._show_town_level)
            self._map_town_btn.pack(side=tk.LEFT, padx=1)
        for number in range(1, max_floor):
            btn = tk.Button(
                levels, text=str(number), font=self._ovf(11) if overlay else ("맑은 고딕", 9, "bold"), width=2,
                bg="#000000" if overlay else "#24273a", fg="#ffffff" if overlay else "#cdd6f4", activebackground="#ffffff" if overlay else "#363a4f",
                activeforeground="#000000" if overlay else "#ffffff", bd=1, relief=tk.SOLID,
                command=lambda number=number: self._set_map_level(number),
            )
            btn.pack(side=tk.LEFT, padx=1)
            self._map_level_btns.append(btn)
        buttons = [("", self._toggle_map_fow)]
        if not overlay:
            buttons.insert(0, ("이 층 초기화", self._reset_explored))
        for text, command in buttons:
            btn = tk.Button(
                levels, text=text, font=self._ovf(11) if overlay else ("맑은 고딕", 9),
                bg="#000000" if overlay else "#24273a", fg="#ffffff" if overlay else "#cdd6f4",
                activebackground="#ffffff" if overlay else "#363a4f", activeforeground="#000000" if overlay else "#ffffff",
                bd=1, relief=tk.SOLID, command=command,
            )
            btn.pack(side=tk.RIGHT, padx=1)
        self._map_fow_btn = btn
        self._sync_map_fow_btn()
        cols, rows = self._map_dimensions()
        span = _MAP_PAD * 2 + max(cols, rows) * self._map_cell
        canvas = tk.Canvas(win, width=span, height=span, bg="#000000" if overlay else "#11111b", highlightthickness=0)
        canvas.bind("<Button-1>", self._on_map_click)
        self._map_canvas = canvas
        # Text goes under the map. A fixed two-line box keeps a click's
        # description from pushing the map down.
        self._map_north_label = tk.Label(
            win, text="북 ↑    왼쪽 아래가 (0, 0)", font=self._ovf(10) if overlay else ("맑은 고딕", 8),
            fg="#ffffff" if overlay else "#6c7086", bg=bg,
        )
        self._map_north_label.pack(anchor="w", padx=8)
        self._map_info = tk.Label(
            win, text="칸을 누르면 설명이 나옵니다", font=self._ovf(11) if overlay else ("맑은 고딕", 9), height=2,
            fg="#ffffff" if overlay else "#cdd6f4", bg=bg, anchor="nw", justify=tk.LEFT, wraplength=span,
        )
        self._map_info.pack(fill=tk.X, padx=8)
        legend = tk.Label(
            win,
            text=(
                "▲ 현재 위치  어두운 칸: 미탐색  노란 점선: 숨은 문  (칸을 누르면 이름)"
            ),
            font=self._ovf(10) if overlay else ("맑은 고딕", 8), fg="#ffffff" if overlay else "#a6adc8", bg=bg,
            anchor="w", justify=tk.LEFT, wraplength=span,
        )
        legend.pack(fill=tk.X, padx=8, pady=(0, 8))
        self._map_legend = legend
        if overlay:
            canvas.pack(padx=8, pady=4, before=self._map_north_label)
        else:
            # Packed last with a tiny request: the text keeps its rows and the
            # map takes the rest of the window.
            canvas.config(width=1, height=1)
            canvas.pack(padx=8, pady=4, fill=tk.BOTH, expand=True, before=self._map_north_label)
            canvas.bind("<Configure>", self._on_map_resize)
        if overlay and rect:
            # The map takes the height the text leaves in the panel. The text
            # wraps to the map's width, so measure again after the first fit.
            w, h = rect[2], rect[3]
            room_w = w - 2 * max(12, w // 80) - 40 - 2 * _MAP_PAD
            self._map_cell = max(2, min(96, room_w // cols))
            for _ in range(2):
                span = _MAP_PAD * 2 + cols * self._map_cell
                canvas.config(width=span, height=_MAP_PAD * 2 + rows * self._map_cell)
                self._map_info.config(wraplength=span)
                legend.config(wraplength=span)
                self._overlay_panel.update_idletasks()
                others = self._overlay_panel.winfo_reqheight() - canvas.winfo_reqheight()
                room_h = h - 2 * max(12, h // 80) - others - 8
                self._map_cell = max(2, min(96, room_h // rows, room_w // cols))
            span = _MAP_PAD * 2 + cols * self._map_cell
            canvas.config(width=span, height=_MAP_PAD * 2 + rows * self._map_cell)
            self._map_info.config(wraplength=span)
            legend.config(wraplength=span)
        try:
            self._load_maps()
        except Exception as exc:
            self._map_info.config(text=f"지도를 읽지 못했습니다: {exc}")
        else:
            self._draw_map()
        if overlay:
            self._snap_overlay()
        if not overlay:
            self._place_map_window()
            win.deiconify()
            win.lift()
            self._save_companion_popups()

    def _user_interacting_with_window(self, win, attr_name):
        if win is None:
            setattr(self, attr_name, False)
            return False
        try:
            if not win.winfo_exists():
                setattr(self, attr_name, False)
                return False
        except tk.TclError:
            setattr(self, attr_name, False)
            return False

        if not (user32.GetAsyncKeyState(0x01) & 0x8000):
            setattr(self, attr_name, False)
            return False

        if getattr(self, attr_name, False):
            return True

        hwnd = self._widget_hwnd(win)
        if not hwnd or not user32.IsWindow(hwnd):
            return False
        pt = wintypes.POINT()
        if user32.GetCursorPos(ctypes.byref(pt)):
            rect = wintypes.RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                margin = 16
                if (rect.left - margin <= pt.x <= rect.right + margin and
                    rect.top - margin <= pt.y <= rect.bottom + margin):
                    setattr(self, attr_name, True)
                    return True
        return False

    def _user_interacting_with_map(self):
        return self._user_interacting_with_window(getattr(self, "_map_win", None), "_map_drag_active")

    def _place_map_window(self):
        """Keep the companion's map window where the user put it, relative to
        the companion, so it moves with the companion.

        The offset from the companion and the size are saved (map_window).
        Without one, or when the first placement would leave the title bar on
        no monitor, it opens under the companion, 2px apart, at its width.
        Called on open and on every companion tick; it only moves the window
        when it is not already there.
        """
        win = getattr(self, "_map_win", None)
        try:
            if win is None or not win.winfo_exists():
                return
            root = _parse_geometry(self.root.geometry())
            here = _parse_geometry(win.geometry())
        except tk.TclError:
            return
        if not root:
            return
        rw, rh, rx, ry = root
        saved = _load_settings().get("map_window")
        if isinstance(saved, list) and len(saved) == 4 and all(isinstance(v, int) for v in saved):
            dx, dy, w, h = saved
        else:
            dx, dy, w, h = None, None, None, None
        if not getattr(self, "_map_win_placed", False):
            self._map_win_placed = True
            if dx is None or not _on_a_monitor(rx + dx + 40, ry + dy + 10):
                root_hwnd = self._widget_hwnd(self.root)
                rect = wintypes.RECT()
                outer_h = rh
                if root_hwnd and user32.GetWindowRect(root_hwnd, ctypes.byref(rect)):
                    outer_h = int(rect.bottom - rect.top)
                dx = 0
                dy = outer_h + 2
                w = rw
                h = 560
                win.geometry(f"{w}x{h}+{rx + dx}+{ry + dy}")
                _remember(map_window=[dx, dy, w, h])
            else:
                win.geometry(f"{max(100, w)}x{max(100, h)}+{rx + dx}+{ry + dy}")
            win.bind("<Configure>", self._on_map_win_configure, add="+")
            return
        if self._user_interacting_with_map() or getattr(self, "_map_geometry_job", None) is not None:
            return
        if dx is not None and here and (abs(here[2] - (rx + dx)) > 2 or abs(here[3] - (ry + dy)) > 2):
            self._map_follow_to = (rx + dx, ry + dy)
            win.geometry(f"+{rx + dx}+{ry + dy}")

    def _on_map_win_configure(self, event):
        """Save the map window's place and size shortly after a move or resize."""
        win = getattr(self, "_map_win", None)
        if event.widget is not win:
            return
        if not self._user_interacting_with_map():
            return
        pending = getattr(self, "_map_geometry_job", None)
        if pending:
            self.root.after_cancel(pending)
        self._map_geometry_job = self.root.after(300, self._save_map_geometry)

    def _save_map_geometry(self):
        self._map_geometry_job = None
        win = getattr(self, "_map_win", None)
        try:
            if win is None or not win.winfo_exists() or win.state() != "normal":
                return
            here = _parse_geometry(win.geometry())
            root = _parse_geometry(self.root.geometry())
        except tk.TclError:
            return
        if here and root:
            w, h, x, y = here
            _remember(map_window=[x - root[2], y - root[3], w, h])

    def _place_spell_window(self):
        win = getattr(self, "_spell_win", None)
        try:
            if win is None or not win.winfo_exists():
                return
            root = _parse_geometry(self.root.geometry())
            here = _parse_geometry(win.geometry())
        except tk.TclError:
            return
        if not root:
            return
        rw, rh, rx, ry = root
        saved = _load_settings().get("spell_window")
        if isinstance(saved, list) and len(saved) == 4 and all(isinstance(v, int) for v in saved):
            dx, dy, w, h = saved
        else:
            dx, dy, w, h = None, None, None, None
        if not getattr(self, "_spell_win_placed", False):
            self._spell_win_placed = True
            if dx is None or not _on_a_monitor(rx + dx + 40, ry + dy + 10):
                dos_rect = self._visible_window_rect(self.hook.hwnd) if self.hook.is_alive() else None
                if dos_rect and _on_a_monitor(dos_rect[2] + 40, ry + 10):
                    target_x = dos_rect[2] + 4
                    target_y = ry
                else:
                    target_x = rx + rw + 4
                    target_y = ry
                dx = target_x - rx
                dy = target_y - ry
                w, h = 560, 640
                win.geometry(f"{w}x{h}+{target_x}+{target_y}")
                _remember(spell_window=[dx, dy, w, h])
            else:
                win.geometry(f"{max(100, w)}x{max(100, h)}+{rx + dx}+{ry + dy}")
            self._spell_follow_to = (rx + dx, ry + dy)
            win.bind("<Configure>", self._on_spell_win_configure, add="+")
            return
        if self._user_interacting_with_window(win, "_spell_drag_active"):
            return
        if dx is not None and here and (abs(here[2] - (rx + dx)) > 2 or abs(here[3] - (ry + dy)) > 2):
            self._spell_follow_to = (rx + dx, ry + dy)
            win.geometry(f"+{rx + dx}+{ry + dy}")

    def _on_spell_win_configure(self, event):
        win = getattr(self, "_spell_win", None)
        if event.widget is not win:
            return
        if not self._user_interacting_with_window(win, "_spell_drag_active"):
            return
        pending = getattr(self, "_spell_geometry_job", None)
        if pending:
            self.root.after_cancel(pending)
        self._spell_geometry_job = self.root.after(300, self._save_spell_geometry)

    def _save_spell_geometry(self):
        self._spell_geometry_job = None
        win = getattr(self, "_spell_win", None)
        try:
            if win is None or not win.winfo_exists() or win.state() != "normal":
                return
            here = _parse_geometry(win.geometry())
            root = _parse_geometry(self.root.geometry())
        except tk.TclError:
            return
        if here and root:
            w, h, x, y = here
            _remember(spell_window=[x - root[2], y - root[3], w, h])

    def _map_dimensions(self):
        try:
            block = self._load_maps()['levels'][self._map_level - 1]
        except (OSError, IndexError):
            return 20, 20
        return block.get('width', 20), block.get('height', 20)

    def _on_map_resize(self, event):
        """Fit the current floor to the canvas the user sized."""
        cols, rows = self._map_dimensions()
        cell = max(2, min(96, (event.width - 2 * _MAP_PAD) // cols,
                         (event.height - 2 * _MAP_PAD) // rows))
        self._map_info.config(wraplength=max(100, event.width))
        self._map_legend.config(wraplength=max(100, event.width))
        if cell == self._map_cell:
            return
        self._map_cell = cell
        try:
            self._draw_map()
        except Exception as exc:
            self._map_info.config(text=f"지도를 읽지 못했습니다: {exc}")

    def _show_town_level(self):
        self._map_town_view = True
        try:
            self._draw_map()
        except Exception as exc:
            self._map_info.config(text=f"지도를 읽지 못했습니다: {exc}")

    def _paint_level_buttons(self):
        """The floor shown is highlighted; the castle button stands for floor 0."""
        on, off = ("#ffff55", "#ffffff") if getattr(self, 'mode', None) == 'overlay' else ("#a6e3a1", "#cdd6f4")
        shown = 0 if self._map_town_view else self._map_level
        for index, btn in enumerate(getattr(self, '_map_level_btns', ()), start=1):
            btn.config(fg=on if index == shown else off)
        if getattr(self, '_map_town_btn', None) is not None:
            self._map_town_btn.config(fg=on if shown == 0 else off)

    def _set_map_level(self, level):
        self._map_level = level
        self._map_town_view = False
        try:
            canvas = self._map_canvas
            cols, rows = self._map_dimensions()
            self._map_cell = max(2, min(96, (canvas.winfo_width() - 2 * _MAP_PAD) // cols,
                                      (canvas.winfo_height() - 2 * _MAP_PAD) // rows))
            self._draw_map()
        except Exception as exc:
            self._map_info.config(text=f"지도를 읽지 못했습니다: {exc}")

    def _draw_map(self):
        # WhereAreWe stores each side on its own cell. A shared edge keeps the
        # north or east value. The other side is not averaged in.
        canvas = self._map_canvas
        cell = self._map_cell
        canvas.delete("all")
        self._paint_level_buttons()
        if self._map_town_view:
            self._draw_town_map()
            return
        data = self._load_maps()
        level = self._map_level
        block = data["levels"][level - 1]
        cols, rows = block.get('width', 20), block.get('height', 20)
        spots = {}
        spots_raw = {}
        for spot in data.get("spots", []):
            if spot.get("level") != level:
                continue
            spots.setdefault((spot["x"], spot["y"]), []).append(self._spot_label(spot))
            spots_raw.setdefault((spot["x"], spot["y"]), []).append(spot.get("name", ""))
        self._map_spots = spots
        types = block["types"]

        wall_w = max(2, round(cell / 14))
        def paint_wall(x1, y1, x2, y2, wall):
            if wall == 1:
                canvas.create_line(x1, y1, x2, y2, fill="#cdd6f4", width=wall_w)
            elif wall == 2:
                # Door: wall-coloured stubs at both ends, open in the middle.
                stub = .25
                dx, dy = (x2 - x1) * stub, (y2 - y1) * stub
                canvas.create_line(x1, y1, x1 + dx, y1 + dy, fill="#cdd6f4", width=wall_w)
                canvas.create_line(x2 - dx, y2 - dy, x2, y2, fill="#cdd6f4", width=wall_w)
            elif wall == 3:
                canvas.create_line(x1, y1, x2, y2, fill="#f9e2af", width=wall_w, dash=(3, 2))

        # Fog of war: only squares the party has seen show their contents.
        seen = self._map_seen(level)
        for y in range(rows):
            for x in range(cols):
                if 'cells' in block and (x, y) not in block['cells']:
                    continue
                i = y * cols + x
                visible = (x, y) in seen
                extra = block["extra"][i]
                kind = types[extra] if 0 <= extra < len(types) else 0
                fill = (_MAP_AREA_FILL[5] if (x, y) in block.get('dark', ())
                        else _MAP_AREA_FILL.get(kind, _MAP_FLOOR_FILL))
                if not visible:
                    fill = _MAP_UNSEEN_FILL
                px = _MAP_PAD + x * cell
                py = _MAP_PAD + (rows - 1 - y) * cell
                background = canvas.create_rectangle(px, py, px + cell, py + cell, fill=fill, outline="#313244")
                canvas.tag_lower(background)
                # Each square stores its own four sides, and the two sides of
                # one edge can differ (a door on one side, a wall on the other).
                # Same value: one line on the edge, shown when either square was
                # seen. Different: each square's value drawn on its own side of
                # the line,
                # shown when that square was seen.
                # Lines are 2px wide: 1px off the edge on each side, so the two
                # faces touch and read as one wall with two sides.
                inset = 1
                if y < rows - 1:
                    mine, theirs = block["north"][i], block["south"][i + cols]
                    above = (x, y + 1) in seen
                    if mine == theirs:
                        if visible or above:
                            paint_wall(px, py, px + cell, py, mine)
                    else:
                        if visible:
                            paint_wall(px, py + inset, px + cell, py + inset, mine)
                        if above:
                            paint_wall(px, py - inset, px + cell, py - inset, theirs)
                elif visible:
                    paint_wall(px, py, px + cell, py, block["north"][i])
                if x < cols - 1:
                    mine, theirs = block["east"][i], block["west"][i + 1]
                    right = (x + 1, y) in seen
                    if mine == theirs:
                        if visible or right:
                            paint_wall(px + cell, py, px + cell, py + cell, mine)
                    else:
                        if visible:
                            paint_wall(px + cell - inset, py, px + cell - inset, py + cell, mine)
                        if right:
                            paint_wall(px + cell + inset, py, px + cell + inset, py + cell, theirs)
                elif visible:
                    paint_wall(px + cell, py, px + cell, py + cell, block["east"][i])
                if y == 0 and visible:
                    paint_wall(px, py + cell, px + cell, py + cell, block["south"][i])
                if x == 0 and visible:
                    paint_wall(px, py, px, py + cell, block["west"][i])
                # A sector map (Wizardry 5) is not a rectangle: an edge with no
                # square of the map beyond it is the outside, drawn as a wall.
                # The south and west edges were never drawn there, since only the
                # square on the other side (missing here) draws them.
                if visible and 'cells' in block:
                    outside = lambda cx, cy: (cx, cy) not in block['cells']
                    if y > 0 and outside(x, y - 1):
                        paint_wall(px, py + cell, px + cell, py + cell, block["south"][i] or 1)
                    if x > 0 and outside(x - 1, y):
                        paint_wall(px, py, px, py + cell, block["west"][i] or 1)
                    if outside(x, y + 1) and not block["north"][i]:
                        paint_wall(px, py, px + cell, py, 1)
                    if outside(x + 1, y) and not block["east"][i]:
                        paint_wall(px + cell, py, px + cell, py + cell, 1)
                if not visible:
                    continue
                named = spots_raw.get((x, y), ())
                # A named spot (key, statue...) is usually also a message square;
                # its own icon says more than the message bubble.
                if not (named and kind == 11) or 'world' in block:
                    _draw_map_icon(canvas, kind, px, py, cell, self._map_stairs_dir(level, x, y))
                if 'world' not in block:
                    for name in named:
                        _draw_spot_icon(canvas, name, px, py, cell)
        # Dead party members left in the maze (red cross) and an OUT party
        # (green flag), drawn whether or not the square was explored.
        wiz_dir = self._wiz_dir()
        # The party being played is not left behind: its saved places move with
        # every save and would show up as an OUT party.
        mine = {rec[1] for rec in self.state._party_records()} if self.state.game in (1, 2, 3) else set()
        for name, body_level, bx, by, status in (_lost_bodies(wiz_dir, self.state.game) if self.state.game in (1, 2, 3) else []):
            if body_level != level or name in mine:
                continue
            px = _MAP_PAD + bx * cell
            py = _MAP_PAD + (rows - 1 - by) * cell
            w = max(2, round(cell / 8))
            if status in (5, 6):
                canvas.create_line(px + cell * .5, py + cell * .15, px + cell * .5, py + cell * .85,
                                   fill="#f38ba8", width=w)
                canvas.create_line(px + cell * .25, py + cell * .38, px + cell * .75, py + cell * .38,
                                   fill="#f38ba8", width=w)
                label = f"{name} {'시체' if status == 5 else '재'}"
            else:
                # OUT party (alive, waiting in the maze): a green flag.
                canvas.create_line(px + cell * .3, py + cell * .15, px + cell * .3, py + cell * .85,
                                   fill="#a6e3a1", width=w)
                canvas.create_polygon(px + cell * .3, py + cell * .15, px + cell * .78, py + cell * .3,
                                      px + cell * .3, py + cell * .45, fill="#a6e3a1", outline="")
                label = f"{name} 미궁 대기"
            spots.setdefault((bx, by), []).append(label)
        self._draw_map_position()

    def _dump_maze_once(self):
        """Read-only copy of the maze data (WAE AllMaps and Map) for working
        out the stairs directions. Written once to wiz_maze_dump.bin."""
        if RELEASE:
            return
        anchor = self.state._anchor
        if anchor is None:
            return
        path = dev_path(os.path.join('reference', 'dumps'), 'wiz_maze_dump.bin')
        if os.path.exists(path):
            return
        all_maps = self.hook.read_bytes(anchor + 201222, 12 * 1024)   # WAE Wiz1Memory.AllMaps
        current = self.hook.read_bytes(anchor + 39116, 1024)           # WAE Wiz1Memory.Map
        if not all_maps or not current:
            return
        try:
            with open(path, 'wb') as handle:
                handle.write(b'WIZ1MAZE' + len(all_maps).to_bytes(4, 'little') + all_maps
                             + len(current).to_bytes(4, 'little') + current)
        except OSError:
            self._log_error()

    def _map_stairs_dir(self, level, x, y):
        """'up', 'down' or None from the map's AUX0 data, when the file has it."""
        try:
            block = self._load_maps()["levels"][level - 1]
            if (x, y) in block.get('stairs', {}):
                return block['stairs'][(x, y)]
            aux0 = block.get("aux0")
            if not aux0:
                return None
            extra = block["extra"][y * block.get('width', 20) + x]
            target = aux0[extra]
        except (KeyError, IndexError, TypeError):
            return None
        return 'up' if target < level else 'down'

    def _refresh_map_position(self):
        moved = self._refresh_party_position()
        return self._refresh_town_node() or moved

    def _refresh_town_node(self):
        """Castle / edge-of-town box for the party while it is not in the maze."""
        game = self.state.game
        if game not in (1, 2, 3, 5):
            return False
        node = self._town_node
        if self._map_position is not None:
            node = None
        else:
            if game == 5:
                anchor = getattr(self.state, '_wiz5_anchor', None)
                raw = self.hook.read_bytes(anchor + 77458, 2) if anchor is not None else None
                state1 = int.from_bytes(raw, 'little') if raw and len(raw) == 2 else None
            elif game == 1:
                state1 = self.state.state1
            else:
                state1 = None
            if state1 is not None:
                node = _TOWN_STATE_NODES[1 if game == 1 else 5].get(state1, node)
            elif game in (2, 3):
                shown = getattr(getattr(self, 'cga_extractor', None), '_shadow', None)
                text = '\n'.join(''.join(row) for row in shown) if shown else ''
                node = next((n for key, n in _TOWN_TEXT_NODES if key in text), node)
            # The game always starts in the castle.
            node = node or 'castle'
        changed = node != self._town_node
        self._town_node = node
        if changed:
            self._map_town_view = node is not None
        return changed

    def _refresh_party_position(self):
        """Party floor and cell from WAE LocationDown/North/East.

        Read in every state except the town ones. A state1 we do not know,
        such as the OUCH! after a wall, still reads the position.
        """
        previous = getattr(self, '_map_position', None)
        if self.state.game == 5:
            anchor = getattr(self.state, '_wiz5_anchor', None)
            position = None if anchor is None else previous
            raw = self.hook.read_bytes(anchor + 58904, 8) if anchor is not None else None
            if raw and len(raw) == 8:
                floor = int.from_bytes(raw[2:4], 'little')
                if floor in (0, 65535):
                    position = None
                elif 1 <= floor <= 8:
                    try:
                        block = self._load_maps()['levels'][floor - 1]
                        cell = block['world_to_cell'].get((raw[6] - 129, raw[4] - 129))
                    except OSError:
                        cell = None
                    if cell is not None:
                        position = (floor, *cell, raw[0] if raw[0] < 4 else None)
            self._map_position = position
            return position != previous
        if self.state.game == 4:
            anchor = getattr(self.state, '_wiz4_anchor', None)
            if anchor is None:
                position = None
            else:
                raw = self.hook.read_bytes(anchor + 63396, 8)
                if raw and len(raw) == 8:
                    facing = int.from_bytes(raw[0:2], 'little', signed=True)
                    floor = int.from_bytes(raw[2:4], 'little', signed=True)
                    north = int.from_bytes(raw[4:6], 'little', signed=True)
                    east = int.from_bytes(raw[6:8], 'little', signed=True)
                    if 1 <= floor <= 14 and 0 <= east < 20 and 0 <= north < 20:
                        position = (floor, east, north, facing if 0 <= facing < 4 else None)
                    else:
                        position = previous
                else:
                    position = previous
            changed = position != previous
            self._map_position = position
            return changed

        if self.state.game == 3:
            anchor = self.state._wiz3_anchor
            if anchor is None:
                position = None
            else:
                raw = self.hook.read_bytes(anchor + 48626, 7)
                if raw and len(raw) == 7 and raw[2] == 0xFF and raw[3] == 0xFF:
                    position = None
                elif raw and len(raw) == 7 and 1 <= raw[2] <= 6 and raw[4] < 20 and raw[6] < 20:
                    facing = raw[0] if raw[0] < 4 else None
                    position = (raw[2], raw[6], raw[4], facing)
                else:
                    position = previous
            changed = position != previous
            self._map_position = position
            return changed

        if self.state.game == 2:
            # Facing, floor, north, east. Maze state 21574 read 0,1,0,0.
            # The tavern (21644) and a floor of 65535 are not a cell.
            # The title (10148) is not the maze. Any other state keeps the
            # cell while those same bytes stay inside the maze.
            anchor = self.state._wiz2_anchor
            state1 = self.state._wiz2_state1
            if anchor is None or state1 in (10148, 21644):
                position = None
            else:
                raw = self.hook.read_bytes(anchor + 48460, 7)
                if raw and len(raw) == 7 and raw[2] == 0xFF and raw[3] == 0xFF:
                    position = None
                elif raw and len(raw) == 7 and 1 <= raw[2] <= 6 and raw[4] < 20 and raw[6] < 20:
                    facing = raw[0] if raw[0] < 4 else None
                    position = (raw[2], raw[6], raw[4], facing)
                else:
                    position = previous
            changed = position != previous
            self._map_position = position
            return changed
        state1 = self.state.state1
        if (self.state._anchor is None or not state1 or state1 in _TOWN_STATE1
                or self.state.current_scene.startswith('캐릭터 작성')):
            position = None
        else:
            # WAE Facing 48294, LocationDown 48296, North 48298, East 48300.
            raw = self.hook.read_bytes(self.state._anchor + 48294, 7)
            if raw and len(raw) == 7 and 1 <= raw[2] <= 10 and raw[4] < 20 and raw[6] < 20:
                facing = raw[0] if raw[0] < 4 else None
                position = (raw[2], raw[6], raw[4], facing)
            else:
                position = previous
        changed = position != previous
        self._map_position = position
        return changed

    def _spot_label(self, spot):
        """Korean text for a named square: an item or monster from the disk, or a fixed name."""
        role = spot.get('role')
        if not role:
            return _spot_ko(spot.get("name", ""))
        ko = {k: (v.get('ko', '') if isinstance(v, dict) else str(v))
              for k, v in getattr(getattr(self, 'cga_extractor', None), 'translations', {}).items()}
        if role == 'fight':
            name = spot.get('monster') or ''
            return f"고정 전투: {ko.get(name) or name}" if name else "고정 전투"
        item = spot.get('item', '')
        name = _item_ko(ko, item) or item
        return {'get': f"{name} 얻음", 'search': f"조사하면 {name}", 'need': f"{name} 있어야 지나감"}[role]

    def _draw_town_map(self):
        """Castle on the left, edge of town on the right, party marker on its box."""
        canvas = self._map_canvas
        canvas.delete('all')
        cols, rows = self._map_dimensions()
        w, h = cols * self._map_cell, rows * self._map_cell
        sx, sy = w / 100, h / 100
        font = (self.mono_font_family, -max(9, int(h / 30)))
        def at(x, y):
            return _MAP_PAD + x * sx, _MAP_PAD + y * sy
        for title, x1, x2 in _TOWN_PANELS:
            ax, ay = at(x1, 1)
            bx, by = at(x2, 99)
            canvas.create_rectangle(ax, ay, bx, by, outline='#45475a')
            canvas.create_text((ax + bx) / 2, at(0, 5)[1], text=title, fill='#89b4fa', font=font)
        a, b = _TOWN_NODES['castle'], _TOWN_NODES['edge']
        (lx, ly), (rx, ry) = at(a[2], (a[1] + a[3]) / 2), at(b[0], (b[1] + b[3]) / 2)
        canvas.create_line(lx, ly, rx, ry, fill='#a6adc8', arrow=tk.BOTH)
        here = self._town_node
        for key, (x1, y1, x2, y2, label) in _TOWN_NODES.items():
            ax, ay = at(x1, y1)
            bx, by = at(x2, y2)
            on = key == here
            canvas.create_rectangle(ax, ay, bx, by, fill='#313244' if on else '#1e1e2e',
                                    outline='#ffff55' if on else '#cdd6f4', width=3 if on else 1)
            canvas.create_text((ax + bx) / 2, (ay + by) / 2, text=label,
                               fill='#ffff55' if on else '#cdd6f4', font=font)
        self._map_spots = {}
        position = getattr(self, '_map_position', None)
        self._map_info.config(text=f"현재 위치: {_TOWN_NODES[here][4]}" if here in _TOWN_NODES
                              else f"현재 위치: 미궁 {position[0]}층" if position else "성·마을 지도")

    def _draw_map_position(self):
        canvas = self._map_canvas
        canvas.delete('party_position')
        if self._map_town_view:
            self._draw_town_map()
            return
        position = self._map_position
        if not position or position[0] != self._map_level:
            return
        _, x, y, facing = position
        cell = self._map_cell
        px = _MAP_PAD + x * cell
        _, rows = self._map_dimensions()
        py = _MAP_PAD + (rows - 1 - y) * cell
        if facing is None:
            canvas.create_oval(px + cell * .2, py + cell * .2, px + cell * .8, py + cell * .8,
                               fill='#ffff55', outline='#000000', tags='party_position')
            return
        # Wizardry direction: 0 north (up), 1 east, 2 south, 3 west.
        cx, cy = px + cell / 2, py + cell / 2
        tip, half = cell * .38, cell * .3
        dx, dy = ((0, -1), (1, 0), (0, 1), (-1, 0))[facing]
        points = (cx + dx * tip, cy + dy * tip,
                  cx - dx * tip * .7 - dy * half, cy - dy * tip * .7 + dx * half,
                  cx - dx * tip * .7 + dy * half, cy - dy * tip * .7 - dx * half)
        canvas.create_polygon(points, fill='#ffff55', outline='#000000', tags='party_position')

    def _refresh_map_darkness(self):
        if self.state.game != 5 or not self._map_position:
            return False
        anchor = self.state._wiz5_anchor
        if anchor is None:
            return False
        try:
            block = self._load_maps()['levels'][self._map_position[0] - 1]
        except OSError:
            return False
        raw = self.hook.read_bytes(anchor + 59840, 256)  # WAW Wiz5Memory.MapDarkBits
        if not raw or len(raw) != 256 or raw == block.get('_dark_bytes'):
            return False
        # Reject the old floor's flags while the game is switching maps.
        if self.hook.read_bytes(anchor + 46488, 32) != block['sectors']:
            return False
        dark = {cell for cell, bit in block['dark_indices'].items()
                if raw[bit // 8 * 2] & (1 << (bit % 8))}
        changed = dark != block.get('dark', set())
        block['dark'], block['_dark_bytes'] = dark, raw
        return changed

    def _map_seen(self, level):
        """Squares drawn with their contents: the explored ones, or all with fog off."""
        if not getattr(self, '_map_fow', True):
            block = self._load_maps()['levels'][level - 1]
            cols, rows = block.get('width', 20), block.get('height', 20)
            return block.get('cells', {(x, y) for x in range(cols) for y in range(rows)})
        return self._load_explored().get(level, set())

    def _sync_map_fow_btn(self):
        self._map_fow_btn.config(text="안개 켬" if getattr(self, '_map_fow', True) else "안개 끔")

    def _toggle_map_fow(self):
        self._map_fow = not getattr(self, '_map_fow', True)
        _remember(map_fow=self._map_fow)
        self._sync_map_fow_btn()
        try:
            self._draw_map()
        except Exception as exc:
            self._map_info.config(text=f"지도를 읽지 못했습니다: {exc}")

    def _on_map_click(self, event):
        x = (event.x - _MAP_PAD) // self._map_cell
        row = (event.y - _MAP_PAD) // self._map_cell
        cols, rows = self._map_dimensions()
        if not (0 <= x < cols and 0 <= row < rows):
            return
        y = rows - 1 - row
        data = self._load_maps()
        block = data["levels"][self._map_level - 1]
        if 'cells' in block and (x, y) not in block['cells']:
            return
        i = y * cols + x
        wx, wy = block.get('world', {}).get((x, y), (x, y))
        if (x, y) not in self._map_seen(self._map_level):
            names = " · ".join(getattr(self, "_map_spots", {}).get((x, y), []))
            self._map_info.config(text=f"{self._map_level}층 ({wx}, {wy}) 아직 보지 못한 칸"
                                  + (f" · {names}" if names else ""))
            return
        extra = block["extra"][i]
        types = block["types"]
        kind = types[extra] if 0 <= extra < len(types) else 0
        kind_ko = _MAP_KIND_KO[kind] if 0 <= kind < len(_MAP_KIND_KO) else str(kind)
        if (x, y) in block.get('dark', ()) and kind != 5:
            kind_ko = '암흑' if kind == 0 else '암흑 · ' + kind_ko
        walls = []
        for label, side in (("북", "north"), ("동", "east"), ("남", "south"), ("서", "west")):
            walls.append(f"{label}-{_MAP_WALL_KO.get(block[side][i], '열림')}")
        names = " · ".join(getattr(self, "_map_spots", {}).get((x, y), []))
        text = f"{self._map_level}층 ({wx}, {wy}) {kind_ko}"
        if kind == 1:
            aux0 = block.get("aux0")
            if aux0:
                target = aux0[extra]
                where = "성" if target == 0 else f"{target}층"
                text += f" ({'위로' if target < self._map_level else '아래로'} → {where})"
        if names:
            text += f" · {names}"
        self._map_info.config(text=text + " [" + " ".join(walls) + "]")

    def _sync_roll_labels(self):
        btn = getattr(self, "btn_roll", None)
        if btn is None:
            return
        # Wizardry 2-4 have no character creation: the training grounds offer only
        # I)NSPECT and R)OSTER (2 and 3 bring characters over from 1; 3 makes legacies).
        if self._current_game() in (2, 3, 4):
            btn.config(text="캐릭터 만들기", state=tk.DISABLED, disabledforeground="#6c7086")
            return
        btn.config(state=tk.NORMAL)
        roll = getattr(self, "_roll", None)
        active = bool(roll.active) if roll else False
        text = "만들기 중지" if active else "캐릭터 만들기"
        fg = "#f9e2af" if active else "#cdd6f4"
        btn.config(text=text, fg=fg)

    def _set_roll_note(self, text):
        note = getattr(self, "comp_roll_note", None)
        if note is None:
            return
        if text:
            note.config(text=text)
            if not note.winfo_ismapped():
                note.pack(fill=tk.X, after=self.btn_roll, pady=(2, 0))
        else:
            if note.winfo_ismapped():
                note.pack_forget()

    def _on_roll_button(self):
        game = self._current_game()
        if game in (2, 3, 4):
            return
        roll = self._roll
        if roll.active:
            roll.stop()
            self._sync_roll_labels()
            self._set_roll_note("만들기를 멈췄습니다")
            return
        win = getattr(self, "_roll_win", None)
        if win is not None:
            try:
                if win.winfo_exists():
                    self._place_roll_window()
                    win.lift()
                    return
            except Exception:
                pass
        win = tk.Toplevel(self.root)
        self._roll_win = win
        win.title("캐릭터 만들기")
        win.configure(bg="#181825")
        self._dark_titlebar(win)
        win.transient(self.root)
        win.resizable(False, False)
        win.attributes("-topmost", bool(self.root.attributes("-topmost")))
        pad = {"padx": 12, "pady": 4}
        tk.Label(win, text="이름 (영문)", font=("맑은 고딕", 9), fg="#cdd6f4", bg="#181825").pack(anchor="w", **pad)
        name_var = tk.StringVar()
        tk.Entry(win, textvariable=name_var, font=("맑은 고딕", 11), bg="#11111b", fg="#cdd6f4", insertbackground="#cdd6f4").pack(fill=tk.X, padx=12)
        roll_saved = _load_settings()
        tk.Label(win, text="종족 (마우스 올리면 특성 안내)", font=("맑은 고딕", 9), fg="#cdd6f4", bg="#181825").pack(anchor="w", **pad)
        race_saved = roll_saved.get("roll_race") if roll_saved.get("roll_race") in ("A", "B", "C", "D", "E") else "A"
        race_var = tk.StringVar(value=race_saved)

        race_row1 = tk.Frame(win, bg="#181825")
        race_row1.pack(fill=tk.X, padx=12, pady=(0, 2))
        for value, label in (("A", "인간"), ("B", "엘프"), ("C", "드워프")):
            rb = tk.Radiobutton(
                race_row1, text=label, variable=race_var, value=value,
                font=("맑은 고딕", 10), fg="#cdd6f4", bg="#181825",
                selectcolor="#11111b", activebackground="#181825", activeforeground="#ffffff",
            )
            rb.pack(side=tk.LEFT, padx=(0, 10))
            ToolTip(rb, _RACE_TOOLTIPS.get(value, ""))

        race_row2 = tk.Frame(win, bg="#181825")
        race_row2.pack(fill=tk.X, padx=12, pady=(0, 4))
        for value, label in (("D", "노움"), ("E", "호빗")):
            rb = tk.Radiobutton(
                race_row2, text=label, variable=race_var, value=value,
                font=("맑은 고딕", 10), fg="#cdd6f4", bg="#181825",
                selectcolor="#11111b", activebackground="#181825", activeforeground="#ffffff",
            )
            rb.pack(side=tk.LEFT, padx=(0, 10))
            ToolTip(rb, _RACE_TOOLTIPS.get(value, ""))
        tk.Label(win, text="성향", font=("맑은 고딕", 9), fg="#cdd6f4", bg="#181825").pack(anchor="w", **pad)
        align_var = tk.StringVar(value=roll_saved.get("roll_align") if roll_saved.get("roll_align") in ("A", "B", "C") else "A")
        row = tk.Frame(win, bg="#181825")
        row.pack(fill=tk.X, padx=12)
        for value, label in (("A", "선"), ("B", "중립"), ("C", "악")):
            tk.Radiobutton(
                row, text=label, variable=align_var, value=value,
                font=("맑은 고딕", 10), fg="#cdd6f4", bg="#181825",
                selectcolor="#11111b", activebackground="#181825", activeforeground="#ffffff",
            ).pack(side=tk.LEFT, padx=6)
        target_lbl = tk.Label(win, text="목표 보너스 (마우스 올리면 전직 조건)", font=("맑은 고딕", 9), fg="#cdd6f4", bg="#181825")
        target_lbl.pack(anchor="w", **pad)
        ToolTip(target_lbl, _BONUS_TOOLTIP)
        target_var = tk.StringVar(value=str(roll_saved.get("roll_target", 18)))
        target_ent = tk.Entry(win, textvariable=target_var, font=("맑은 고딕", 11), bg="#11111b", fg="#cdd6f4", insertbackground="#cdd6f4")
        target_ent.pack(fill=tk.X, padx=12)
        ToolTip(target_ent, _BONUS_TOOLTIP)
        err = tk.Label(win, text="", font=("맑은 고딕", 8), fg="#f38ba8", bg="#181825")
        err.pack(anchor="w", padx=12, pady=2)

        def begin():
            name = name_var.get().strip().upper()
            if not re.fullmatch(r"[A-Z]{1,15}", name):
                err.config(text="이름은 영문 1~15자입니다")
                return
            try:
                target = int(target_var.get().strip())
            except ValueError:
                err.config(text="목표 보너스는 숫자입니다")
                return
            if not 1 <= target <= 29:
                err.config(text="목표 보너스는 1~29입니다")
                return
            _remember(roll_race=race_var.get(), roll_align=align_var.get(), roll_target=target)
            self._roll.start(name, align_var.get(), target, race=race_var.get(), game=game)
            self._sync_roll_labels()
            self._set_roll_note(self._roll.status)
            win.destroy()
            self._focus_dosbox()
            self.root.after(50, self._focus_dosbox)

        tk.Button(
            win, text="시작", font=("맑은 고딕", 10, "bold"),
            bg="#24273a", fg="#a6e3a1", activebackground="#363a4f", activeforeground="#ffffff",
            bd=1, relief=tk.SOLID, command=begin,
        ).pack(fill=tk.X, padx=12, pady=10)
        self._place_roll_window()

    def _place_roll_window(self):
        """Stick the character dialog to the companion's bottom edge."""
        win = getattr(self, "_roll_win", None)
        if win is None:
            return
        try:
            if not win.winfo_exists():
                return
        except tk.TclError:
            return
        root_hwnd = self._widget_hwnd(self.root)
        rect = wintypes.RECT()
        if not root_hwnd or not user32.GetWindowRect(root_hwnd, ctypes.byref(rect)):
            return
        win.update_idletasks()
        height = max(win.winfo_reqheight(), 1)
        x = int(rect.left)
        y = int(rect.bottom) + 2
        got = self._window_rect(self._widget_hwnd(win))
        if got and abs(got[0] - x) <= 2 and abs(got[1] - y) <= 2:
            return
        win.geometry(f"360x{height}+{x}+{y}")

    def _roll_poll_ms(self):
        """Up spends 35ms (30% under the old 50ms). Name letters 47ms (30% under the old 67ms). Other keys stay at 100ms."""
        roll = getattr(self, "_roll", None)
        if roll is None or not roll.active:
            return 100
        if roll.waiting and roll.sent_key in ("UP", "+"):   # 5편은 +
            return 35
        if roll.sent_kind == "name" or roll.seen_kind == "name":
            return 47
        return 100

    def _roll_step(self):
        roll = getattr(self, "_roll", None)
        if roll is None or not roll.active:
            return
        now = time.monotonic()
        if now < roll.next_poll:
            return
        if not self.hook.is_alive():
            roll.next_poll = now + self._roll_poll_ms() / 1000
            roll.status = "DOSBox 연결을 기다리는 중"
            self._set_roll_note(roll.status)
            return
        lines = self.cga_extractor.scan_screen()
        text = "\n".join(line.get("text", "") for line in lines)
        bonus = roll_bonus(text)
        kind = roll_screen_kind(text)
        key = roll.consider(text, now, getattr(self.cga_extractor, "cursor_cells", ()))
        roll.next_poll = now + self._roll_poll_ms() / 1000
        self._set_roll_note(roll.status)
        if not roll.active:
            self._sync_roll_labels()
        if key is None:
            return
        if self._send_dos_key(key):
            roll.mark_sent(key, now, bonus, kind, text)
            roll.next_poll = now + self._roll_poll_ms() / 1000
            self._set_roll_note(roll.status)
        else:
            self._set_roll_note("키를 게임 입력 버퍼에 넣지 못했습니다")

    def _read_bios_u16(self, addr):
        data = self.hook.read_bytes(addr, 2)
        if not data or len(data) < 2:
            return None
        return int.from_bytes(data, "little")

    def _send_dos_key(self, key):
        """One key into the BIOS keyboard buffer the game reads.

        DOSBox ddraw takes keys from DirectInput. Injected Windows keys never
        arrive there. The buffer is the PC BIOS area, after the 32-byte malloc
        header when that header is what the live memory size and timer show.
        """
        code = _bios_key_word(key)
        if code is None or self.state.game not in (1, 5) or not self.hook.is_alive():
            return False
        for shift in (0x20, 0x00):
            memsize = self._read_bios_u16(shift + 0x413)
            start = self._read_bios_u16(shift + 0x480)
            end = self._read_bios_u16(shift + 0x482)
            head = self._read_bios_u16(shift + 0x41A)
            tail = self._read_bios_u16(shift + 0x41C)
            if memsize != 640 or None in (start, end, head, tail):
                continue
            if not (0x1E <= start < end <= 0x40):
                continue
            if not (start <= head < end and start <= tail < end):
                continue
            if ((head - start) | (tail - start)) & 1:
                continue
            new_tail = tail + 2
            if new_tail >= end:
                new_tail = start
            if new_tail == head:
                return False
            slot = shift + 0x400 + tail
            if not self.hook.write_bytes(slot, code.to_bytes(2, "little")):
                return False
            if not self.hook.write_bytes(shift + 0x41C, new_tail.to_bytes(2, "little")):
                return False
            return True
        return False

    def _select_mono_font_family(self):
        """Choose an installed font whose Latin and Korean glyphs are fixed-width."""
        try:
            families = {name.casefold(): name for name in tkfont.families(self.root)}
            for candidate in ("Neo둥근모", "NeoDunggeunmo", "DungGeunMo", "둥근모꼴", "갈무리11", "Galmuri11", "D2Coding", "GulimChe"):
                if candidate.casefold() in families:
                    return families[candidate.casefold()]
        except Exception:
            pass
        return "GulimChe"

    def _focus_dosbox(self):
        if self.hook.hwnd and user32.IsWindow(self.hook.hwnd):
            try:
                user32.SetForegroundWindow(self.hook.hwnd)
            except Exception:
                pass

    def _clear_connection(self):
        """Discard every process-specific value before locating a new DOSBox."""
        self.cga_extractor.restore_blanked_text()
        self.canvas.delete("all")
        self.over.withdraw()
        self.control.withdraw()
        self.hook.close()
        self.hook.pid = None
        self.hook.dos_base = None
        self.hook.hwnd = None
        for name in ('_video_address', '_trade_video_address', '_trade_next_search', '_stairs_next_search'):
            if hasattr(self.hook, name):
                delattr(self.hook, name)
        self.state.update()
        self._map_position = None
        map_canvas = getattr(self, '_map_canvas', None)
        if map_canvas is not None and map_canvas.winfo_exists():
            map_canvas.delete('party_position')
        self.last_rect = None
        self._overlay_video = None
        self._overlay_box = None
        self._overlay_draw_sig = None
        self._overlay_protected = ()
        self._overlay_size = None
        self._last_heavy = 0.0
        self.trade_stage = None
        self.stairs_stage = None
        self.tavern_stage = None

        self.inspect_action = None
        self.equip_stage = None
        self.inspect_party_index = None
        self.inn_stage = None
        self.inn_party_index = None
        self.inn_message_until = 0.0
        self.shop_stage = None
        self.shop_party_index = None
        self.training_action = None
        self.scene_override = None
        self._last_state1 = 0
        self._last_party_count = 0
        self._key_down.clear()

    def _reconnect_dosbox(self):
        self._clear_connection()
        self.comp_status.config(text="DOSBox 다시 찾는 중...", fg="#f9e2af")
        if self.hook.connect():
            self.state.update()
            self._track_menu_context()
            self.comp_status.config(text=f"연결됨 (PID {self.hook.pid})", fg="#a6e3a1")
            if self.mode == 'companion':
                self._snap_companion()
                self._render_companion()
            else:
                self._snap_overlay()
        else:
            self._clear_connection()
            self.comp_status.config(text="DOSBox를 찾지 못했습니다", fg="#f38ba8")

    def _create_card(self, parent, title, color):
        frame = tk.LabelFrame(parent, text=f" {title} ", font=("맑은 고딕", 9, "bold"), fg=color, bg="#24273a", bd=1, relief=tk.SOLID)
        frame.pack(fill=tk.X, pady=3)
        return frame

    def _build_overlay_window(self):
        self.over = tk.Toplevel(self.root)
        self.over.title("Wiz Overlay")
        self.over.overrideredirect(True)
        self.over.attributes("-topmost", False)

        self.TRANSPARENT_COLOR = "#010101"
        self.over.attributes("-transparentcolor", self.TRANSPARENT_COLOR)
        self.over.config(bg=self.TRANSPARENT_COLOR)

        self.canvas = tk.Canvas(
            self.over,
            bg=self.TRANSPARENT_COLOR,
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # The overlay itself is click-through so it never blocks the game.
        # Its controls therefore live in a separate, clickable mini-window.
        self.control = tk.Toplevel(self.root)
        # One named font for the button row; resized with the game picture.
        self._ov_btn_font = tkfont.Font(root=self.root, family=self.mono_font_family, size=9)
        self.control.overrideredirect(True)
        self.control.attributes("-topmost", False)
        self.control.configure(bg="#000000")
        self.control_bar = tk.Frame(self.control, bg="#000000")
        self.control_bar.pack(fill=tk.X)
        self.control_buttons = tk.Frame(self.control_bar, bg="#000000")
        self.control_buttons.pack(side=tk.RIGHT)
        self._overlay_panel = None
        self._overlay_panel_kind = None
        self.btn_to_comp = tk.Button(
            self.control_buttons,
            text="컴패니언",
            font=self._ov_btn_font,
            bg="#000000",
            fg="#ffffff",
            activebackground="#ffffff",
            activeforeground="#000000",
            bd=1,
            relief=tk.SOLID,
            command=lambda: self.set_mode('companion')
        )
        self.btn_to_comp.pack(side=tk.LEFT, padx=(2, 1), pady=2)

        self.btn_over_map = tk.Button(
            self.control_buttons,
            text="지도",
            font=self._ov_btn_font,
            bg="#000000",
            fg="#ffffff",
            activebackground="#ffffff",
            activeforeground="#000000",
            bd=1,
            relief=tk.SOLID,
            command=self._toggle_map,
        )
        self.btn_over_map.pack(side=tk.LEFT, padx=(1, 1), pady=2)

        self.btn_over_spells = tk.Button(
            self.control_buttons, text="주문", font=self._ov_btn_font,
            bg="#000000", fg="#ffffff", activebackground="#ffffff",
            activeforeground="#000000", bd=1, relief=tk.SOLID, command=self._toggle_spells,
        )
        self.btn_over_spells.pack(side=tk.LEFT, padx=(1, 1), pady=2)

        self.over.update_idletasks()
        self.control.update_idletasks()
        self._detach_owner(self._widget_hwnd(self.over))
        self._detach_owner(self._widget_hwnd(self.control))
        self.control.withdraw()
        self._apply_overlay_clickthrough()

    def _widget_hwnd(self, widget):
        hwnd = int(widget.winfo_id())
        # GetParent of a top-level window is its owner, not the window itself.
        root = user32.GetAncestor(hwnd, GA_ROOT)
        return int(root or hwnd)

    def _visible_window_rect(self, hwnd):
        """Return (left, top, right, bottom) of visible window excluding DWM drop shadows."""
        rect = wintypes.RECT()
        try:
            if ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect)) == 0:
                return (rect.left, rect.top, rect.right, rect.bottom)
        except Exception:
            pass
        if not hwnd or not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        return (rect.left, rect.top, rect.right, rect.bottom)

    def _window_rect(self, hwnd):
        rect = wintypes.RECT()
        if not hwnd or not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)

    def _rects_close(self, got, want, tol=4):
        if not got or not want:
            return False
        return all(abs(a - b) <= tol for a, b in zip(got, want))

    def _detach_owner(self, hwnd):
        """Drop the companion owner once. A topmost owner keeps the overlay above every app."""
        if not hwnd or hwnd in self._detached_hwnds:
            return
        _set_owner(hwnd, GWLP_HWNDPARENT, 0)
        self._detached_hwnds.add(hwnd)

    def _place_window(self, hwnd, insert_after, x, y, w, h):
        # First argument must be a window this process created. SetWindowPos on
        # Shell_TrayWnd clears its topmost bit, and that bit stays off after exit.
        ours = (
            self._widget_hwnd(self.over),
            self._widget_hwnd(self.control),
            self._widget_hwnd(self.root),
        )
        if int(hwnd) not in ours:
            return
        user32.SetWindowPos(hwnd, insert_after, int(x), int(y), int(w), int(h), SWP_NOACTIVATE)

    def _is_taskbar(self, hwnd):
        if not hwnd:
            return False
        buf = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, buf, 64)
        return buf.value in ("Shell_TrayWnd", "Shell_SecondaryTrayWnd")

    def _next_visible(self, hwnd):
        cur = user32.GetWindow(hwnd, GW_HWNDPREV)
        while cur:
            if user32.IsWindowVisible(cur):
                return cur
            cur = user32.GetWindow(cur, GW_HWNDPREV)
        return None

    def _is_topmost(self, hwnd):
        return bool(user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOPMOST)

    def _is_above(self, lower, upper):
        cur = user32.GetWindow(lower, GW_HWNDPREV)
        upper = int(upper)
        while cur:
            if int(cur) == upper:
                return True
            cur = user32.GetWindow(cur, GW_HWNDPREV)
        return False

    def _set_tk_topmost(self, enabled):
        """Keep Tk from clearing the Win32 topmost bit on the next geometry update."""
        if getattr(self, "_tk_topmost", None) == enabled:
            return
        self.over.attributes("-topmost", enabled)
        self.control.attributes("-topmost", enabled)
        self._tk_topmost = enabled

    def _sync_overlay_zorder(self, over_rect, control_rect):
        """Stay on the DOSBox client: above DOSBox, and below another app only while that app is in front."""
        dos = self.hook.hwnd
        if not dos or not user32.IsWindow(dos):
            return
        over = self._widget_hwnd(self.over)
        control = self._widget_hwnd(self.control)
        self._detach_owner(over)
        self._detach_owner(control)
        ox, oy, ow, oh = over_rect
        cx, cy, cw, ch = control_rect
        ours = {over, control, self._widget_hwnd(self.root)}
        blocker = None
        cur = user32.GetWindow(dos, GW_HWNDPREV)
        while cur:
            current = int(cur)
            if current not in ours and user32.IsWindowVisible(cur):
                if not self._is_topmost(cur):
                    blocker = cur
                    break
            cur = user32.GetWindow(cur, GW_HWNDPREV)

        fg = int(user32.GetForegroundWindow() or 0)
        if not fg:
            # Activation is changing hands (a click on the overlay). Keep the
            # current order; dropping now hid the overlay for a frame.
            return
        # Topmost only while the game or this overlay is in front. Once a topmost
        # window is up, no normal window can pass it, so "nothing above DOSBox"
        # must not be treated as a reason to stay on top. That locks out the taskbar
        # and Alt+Tab. Any window of this process counts as ours: a click on the
        # overlay can activate Tk's hidden root instead of the panel.
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
        cover = fg == int(dos) or fg in ours or pid.value == os.getpid()
        if not cover and self._is_topmost(dos):
            # DOSBox itself is topmost (fullscreen output). The normal band is
            # under it, so dropping topmost hid the whole overlay. Stay in the
            # topmost band, right above DOSBox and under the window above it.
            above = user32.GetWindow(dos, GW_HWNDPREV)
            while above and int(above) in ours:
                above = user32.GetWindow(above, GW_HWNDPREV)
            in_place = (
                self._rects_close(self._window_rect(over), (ox, oy, ow, oh))
                and self._rects_close(self._window_rect(control), (cx, cy, cw, ch))
                and self._is_topmost(over)
                and self._is_topmost(control)
                and self._is_above(dos, over)
                and self._is_above(over, control)
                and (not above or self._is_above(control, above))
            )
            if in_place:
                return
            self._set_tk_topmost(True)
            insert = above if above else HWND_TOPMOST
            self._place_window(control, insert, cx, cy, cw, ch)
            self._place_window(over, control, ox, oy, ow, oh)
            self._apply_overlay_clickthrough()
            return
        if self.mode == 'companion':
            if not self.over.winfo_viewable():
                return
            over_in_place = self._rects_close(self._window_rect(over), (ox, oy, ow, oh))
            if cover:
                if not (over_in_place and self._is_topmost(over) and self._is_above(dos, over)):
                    self.over.attributes("-topmost", True)
                    self._place_window(over, HWND_TOPMOST, ox, oy, ow, oh)
                    self._apply_overlay_clickthrough()
            else:
                above_dos = self._next_visible(dos)
                if not (over_in_place and not self._is_topmost(over) and int(above_dos or 0) == over):
                    self.over.attributes("-topmost", False)
                    if blocker and user32.IsWindow(blocker):
                        if self._is_topmost(over):
                            self._place_window(over, HWND_NOTOPMOST, ox, oy, ow, oh)
                        self._place_window(over, blocker, ox, oy, ow, oh)
                    else:
                        self._place_window(over, HWND_NOTOPMOST, ox, oy, ow, oh)
                    self._apply_overlay_clickthrough()
            return

        placed = (
            self._rects_close(self._window_rect(over), (ox, oy, ow, oh))
            and self._rects_close(self._window_rect(control), (cx, cy, cw, ch))
        )
        if cover:
            in_place = (
                placed
                and self._is_topmost(over)
                and self._is_topmost(control)
                and self._is_above(dos, over)
                and self._is_above(over, control)
            )
            if in_place:
                return
            self._set_tk_topmost(True)
            self._place_window(over, HWND_TOPMOST, ox, oy, ow, oh)
            self._place_window(control, HWND_TOPMOST, cx, cy, cw, ch)
        else:
            # Sit right above DOSBox, under whatever window is right above it.
            # Placing under the foreground app instead lifted the overlay over
            # every window between that app and DOSBox.
            above_dos = self._next_visible(dos)
            above_over = self._next_visible(over)
            in_place = (
                placed
                and not self._is_topmost(over)
                and not self._is_topmost(control)
                and int(above_dos or 0) == over
                and int(above_over or 0) == control
                and (not blocker or int(self._next_visible(control) or 0) == int(blocker))
            )
            if in_place:
                return
            self._set_tk_topmost(False)
            if blocker and user32.IsWindow(blocker):
                for hwnd, pos in ((over, over_rect), (control, control_rect)):
                    if self._is_topmost(hwnd):
                        self._place_window(hwnd, HWND_NOTOPMOST, *pos)
                self._place_window(over, blocker, ox, oy, ow, oh)
                self._place_window(control, blocker, cx, cy, cw, ch)
            else:
                # No normal window above DOSBox: the top of the normal band is
                # right above it.
                self._place_window(over, HWND_NOTOPMOST, ox, oy, ow, oh)
                self._place_window(control, HWND_NOTOPMOST, cx, cy, cw, ch)
        self._apply_overlay_clickthrough()

    def _apply_overlay_clickthrough(self):
        try:
            parent = self._widget_hwnd(self.over)
            style = user32.GetWindowLongW(parent, GWL_EXSTYLE)
            if style & WS_EX_TRANSPARENT and style & WS_EX_LAYERED:
                return
            user32.SetWindowLongW(parent, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)
        except Exception:
            pass

    def set_mode(self, mode):
        if self.mode == 'overlay' and mode != 'overlay':
            if not getattr(self, '_companion_translate', False):
                self.cga_extractor.restore_blanked_text()
            self._close_overlay_panel()
        if self.mode == 'companion' and mode != 'companion':
            popups = []
            map_win = getattr(self, '_map_win', None)
            if map_win is not None:
                try:
                    if map_win.winfo_exists() and map_win.state() != 'withdrawn':
                        popups.append('map')
                except Exception:
                    pass
            spell_win = getattr(self, '_spell_win', None)
            if spell_win is not None:
                try:
                    if spell_win.winfo_exists() and spell_win.state() != 'withdrawn':
                        popups.append('spells')
                except Exception:
                    pass
            roll_win = getattr(self, '_roll_win', None)
            if roll_win is not None:
                try:
                    if roll_win.winfo_exists() and roll_win.state() != 'withdrawn':
                        popups.append('roll')
                except Exception:
                    pass
            self._prev_companion_popups = popups
        self.mode = mode
        if mode == 'companion':
            if not getattr(self, '_companion_translate', False):
                self.over.withdraw()
            self.control.withdraw()
            self.root.deiconify()
            self._snap_companion()
            prev = getattr(self, '_prev_companion_popups', None)
            if prev:
                if 'map' in prev and (getattr(self, '_map_win', None) is None or not self._map_win.winfo_exists()):
                    self._show_map()
                if 'spells' in prev and (getattr(self, '_spell_win', None) is None or not self._spell_win.winfo_exists()):
                    self._show_spells()
                if 'roll' in prev and (getattr(self, '_roll_win', None) is None or not self._roll_win.winfo_exists()):
                    self._on_roll_button()
        else:
            for name in ('_map_win', '_spell_win'):
                win = getattr(self, name, None)
                if win is not None and win.winfo_exists():
                    win.destroy()
                    setattr(self, name, None)
            self.root.withdraw()
            self.cga_extractor.reset_blank_shadow()
            self._overlay_video = None
            self._overlay_draw_sig = None
            self._overlay_protected = ()
            self.over.deiconify()
            self.control.deiconify()
            self._apply_overlay_clickthrough()
            self._snap_overlay()
        self._focus_dosbox()

    def _sync_companion_topmost(self):
        """Drop the companion when another program is in front so it cannot cover that window."""
        fg = int(user32.GetForegroundWindow() or 0)
        root = self._widget_hwnd(self.root)
        dos = int(self.hook.hwnd or 0)
        if not fg:
            return
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
        # The map and spell windows are ours too.
        want = fg in (root, dos) or pid.value == os.getpid()
        if getattr(self, "_companion_topmost", None) == want:
            return
        self.root.attributes("-topmost", want)
        self._companion_topmost = want
        for name in ("_roll_win", "_map_win"):
            held = getattr(self, name, None)
            if held is not None:
                try:
                    if held.winfo_exists():
                        held.attributes("-topmost", want)
                except tk.TclError:
                    pass

    def _snap_companion(self):
        """Snaps companion window to the LEFT of DOSBox window."""
        self._sync_companion_topmost()
        if not self.hook.hwnd or not user32.IsWindow(self.hook.hwnd):
            # Not connected: keep the position, but fit the height to the
            # contents. The fixed start height hid the lower buttons.
            self.root.update_idletasks()
            need = max(self.root.winfo_reqheight(), 200)
            if abs(self.root.winfo_height() - need) > 2:
                pos = re.search(r'([+-]-?\d+[+-]-?\d+)$', self.root.geometry())
                self.root.geometry(f"360x{need}{pos.group(1) if pos else ''}")
                self.root.update_idletasks()
            self._place_roll_window()
            self._place_map_window()
            self._place_spell_window()
            return
        rect = wintypes.RECT()
        if user32.GetWindowRect(self.hook.hwnd, ctypes.byref(rect)):
            ow = 360
            self.root.update_idletasks()
            root_hwnd = user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            dos_vis = self._visible_window_rect(self.hook.hwnd)
            comp_vis = self._visible_window_rect(root_hwnd)
            root_rect = wintypes.RECT()
            user32.GetWindowRect(root_hwnd, ctypes.byref(root_rect))

            if dos_vis and comp_vis and root_rect:
                comp_vis_w = comp_vis[2] - comp_vis[0]
                margin_left = comp_vis[0] - root_rect.left
                ox = max(0, dos_vis[0] - comp_vis_w - margin_left)
                oy = dos_vis[1]
            else:
                ox = max(0, rect.left - ow)
                oy = rect.top
            oh = max(self.root.winfo_reqheight(), 200)

            cur_geo = _parse_geometry(self.root.geometry())
            if not cur_geo or abs(cur_geo[2] - ox) > 2 or abs(cur_geo[3] - oy) > 2 or abs(self.root.winfo_height() - oh) > 2:
                self.root.geometry(f"{ow}x{oh}+{ox}+{oy}")
                self.root.update_idletasks()

        self._place_roll_window()
        self._place_map_window()
        self._place_spell_window()

    def _watch_dosbox_pos(self):
        """Remember where the DOSBox window is, for the next 게임 실행.

        Saved one second after it stops moving. Minimised and fullscreen
        (no caption) windows are not a place to start in.
        """
        hwnd = self.hook.hwnd
        if not hwnd or user32.IsIconic(hwnd) or not user32.GetWindowLongW(hwnd, GWL_STYLE) & WS_CAPTION:
            return
        rect = self.hook.get_client_rect_on_screen()
        if not rect or rect[:2] == getattr(self, '_dosbox_pos_seen', None):
            return
        self._dosbox_pos_seen = rect[:2]
        job = getattr(self, '_dosbox_pos_job', None)
        if job:
            self.root.after_cancel(job)
        self._dosbox_pos_job = self.root.after(
            1000, lambda pos=list(rect[:2]): (_remember(dosbox_pos=pos), setattr(self, '_dosbox_pos_job', None)))

    def _fit_game_rect(self, hwnd, x, y, w, h):
        """Windowed DOSBox fills the client. Borderless fullscreen letterboxes 4:3."""
        if w < 32 or h < 32:
            return (x, y, w, h)
        if user32.GetWindowLongW(hwnd, GWL_STYLE) & WS_CAPTION:
            return (x, y, w, h)
        mon = user32.MonitorFromWindow(hwnd, 2)
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not mon or not user32.GetMonitorInfoW(mon, ctypes.byref(info)):
            return (x, y, w, h)
        mw = info.rcMonitor.right - info.rcMonitor.left
        mh = info.rcMonitor.bottom - info.rcMonitor.top
        if mw < 32 or mh < 32 or w < mw * 0.90 or h < mh * 0.90:
            return (x, y, w, h)
        if w * 3 == h * 4:
            return (x, y, w, h)
        if w * 3 > h * 4:
            cw = int(round(h * 4 / 3))
            ch = h
        else:
            cw = w
            ch = int(round(w * 3 / 4))
        return (x + (w - cw) // 2, y + (h - ch) // 2, max(cw, 1), max(ch, 1))

    def _note_overlay_size(self, w, h):
        """A fullscreen toggle must not keep the previous screen's remembered text."""
        prev = self._overlay_size
        if prev is not None and abs(prev[0] - w) <= 8 and abs(prev[1] - h) <= 8:
            return
        self._overlay_size = (w, h)
        self._ov_btn_font.configure(size=self._ovf(9)[1])
        kind = getattr(self, '_overlay_panel_kind', None)
        if kind and self.mode == 'overlay':
            # Rebuild the open panel at the new size.
            self._close_overlay_panel()
            self.root.after(0, self._show_map if kind == '지도' else self._show_spells)
        if prev is None:
            return
        self.cga_extractor.reset_blank_shadow()
        self.canvas.delete("all")
        self._overlay_video = None
        self._overlay_box = None
        self._overlay_draw_sig = None
        self._overlay_protected = ()
        relock_cga_video(self.hook)

    def _nudge_dosbox_paint(self):
        """DOSBox can keep the previous frame after a mode switch. Ask it to paint."""
        dos = self.hook.hwnd
        now = time.monotonic()
        if not dos or now - getattr(self, "_dos_nudge", 0.0) < 0.20:
            return
        if not user32.IsWindow(dos):
            return
        self._dos_nudge = now
        user32.RedrawWindow(dos, None, None, RDW_INVALIDATE | RDW_UPDATENOW | RDW_ALLCHILDREN)

    def _snap_overlay(self):
        dos = self.hook.hwnd
        if not dos or not user32.IsWindow(dos) or user32.IsIconic(dos):
            if self.over.winfo_exists() and self.over.winfo_viewable():
                self.over.withdraw()
            if self.control.winfo_exists() and self.control.winfo_viewable():
                self.control.withdraw()
            self.last_rect = None
            if self._overlay_size not in (None, (0, 0)):
                self._overlay_size = (0, 0)
            return
        if not self.over.winfo_viewable():
            self.over.deiconify()
            if self.mode == 'overlay':
                self.control.deiconify()
            self._apply_overlay_clickthrough()
        elif self.mode == 'companion' and self.control.winfo_viewable():
            self.control.withdraw()
        self.control.update_idletasks()
        rect = self.hook.get_client_rect_on_screen()
        if rect:
            rect = self._fit_game_rect(dos, *rect)
            self._note_overlay_size(rect[2], rect[3])
            x, y, w, h = rect
            margin_x, margin_y = max(12, w // 80), max(12, h // 80)
            cw = max(32, self.control_bar.winfo_reqwidth())
            # The button row grows with its scaled font.
            ch = max(32, self.control_bar.winfo_reqheight())
            if self._overlay_panel is not None:
                map_cell = getattr(self, '_map_cell', _MAP_CELL)
                cw = w - 2 * margin_x if self._overlay_panel_kind == '주문' else min(
                    w - 2 * margin_x, max(cw, int(420 * self._ui_k()), self._map_dimensions()[0] * map_cell + 2 * _MAP_PAD + 40))
                ch = h - 2 * margin_y
            cx, cy = max(x + margin_x, x + w - cw - margin_x), y + margin_y
            desired = (x, y, w, h)
            control_desired = (cx, cy, cw, ch)
            over_hwnd = self._widget_hwnd(self.over)
            control_hwnd = self._widget_hwnd(self.control)
            if (self.last_rect != desired
                    or not self._rects_close(self._window_rect(over_hwnd), desired)
                    or not self._rects_close(self._window_rect(control_hwnd), control_desired)):
                self.last_rect = desired
                self.over.geometry(f"{w}x{h}+{x}+{y}")
                self.control.geometry(f"{cw}x{ch}+{cx}+{cy}")
                self.over.update_idletasks()
                self.control.update_idletasks()
                self._apply_overlay_clickthrough()
            self._sync_overlay_zorder(desired, control_desired)
        else:
            self.over.geometry("1x1+-3000+-3000")
            self.over.update_idletasks()

    def _load_explored(self):
        if self._explored is None:
            self._explored = {}
            try:
                with open(_explored_path(self._translation_game), encoding="utf-8") as handle:
                    raw = json.load(handle)
                for level, cells in raw.items():
                    self._explored[int(level)] = {tuple(c) for c in cells}
            except (OSError, ValueError, TypeError):
                pass
        return self._explored

    def _save_explored(self):
        if not self._explored_dirty:
            return
        path = _explored_path(self._translation_game)
        try:
            with open(path + ".tmp", "w", encoding="utf-8") as handle:
                json.dump({str(k): sorted(v) for k, v in self._load_explored().items()}, handle)
            os.replace(path + ".tmp", path)
            self._explored_dirty = False
        except OSError:
            self._log_error()

    def _record_explored(self):
        """Mark what the party sees now. Returns True when new cells appear."""
        position = self._map_position
        # A teleporter is left before the next poll reads it: after a jump,
        # mark the squares the party walked into from its last position.
        # Leaving the maze counts too (a teleporter back to the castle).
        came, self._explored_from = getattr(self, '_explored_from', None), position
        entered = False
        if came and came[3] is not None and (not position or came[0] != position[0]
                                             or abs(came[1] - position[1]) + abs(came[2] - position[2]) > 1):
            try:
                old = self._load_explored().setdefault(came[0], set())
                for cell in _entered_cells(self._load_maps()["levels"][came[0] - 1], came[1], came[2], came[3]):
                    if cell not in old:
                        old.add(cell)
                        entered = True
            except Exception:
                pass
        if not position:
            if entered:
                self._explored_dirty = True
                self._save_explored()
            return entered
        level, x, y, facing = position
        try:
            block = self._load_maps()["levels"][level - 1]
        except Exception:
            return False
        game = self.state.game
        anchor = (self.state._wiz5_anchor if game == 5 else self.state._wiz4_anchor if game == 4 else self.state._wiz3_anchor if game == 3
                  else self.state._wiz2_anchor if game == 2 else self.state._anchor)
        light_offset = {5: 58976, 4: 63456, 3: 48682, 2: 48516}.get(game, 48350)
        light = self.hook.read_bytes(anchor + light_offset, 2) if anchor is not None else None
        lit = bool(light and len(light) == 2 and (light[0] or light[1]))
        cells = self._load_explored().setdefault(level, set())
        new = [c for c in _visible_cells(block, x, y, facing, _VIEW_LIT if lit else _VIEW_DARK) if c not in cells]
        if not new:
            if entered:
                self._explored_dirty = True
                self._save_explored()
            return entered
        cells.update(new)
        self._explored_dirty = True
        self._save_explored()
        return True

    def _reset_explored(self):
        """Clear the fog record of the level shown on the map."""
        game = getattr(self.state, "game", 1)
        if not messagebox.askyesno("지도 초기화", f"{game}편 {self._map_level}층의 탐색 기록을 지울까요?"):
            return
        self._load_explored().pop(self._map_level, None)
        self._explored_dirty = True
        self._save_explored()
        self._record_explored()
        self._draw_map()

    def _reset_all_explored(self):
        """Clear the fog record of every level."""
        game = getattr(self.state, "game", 1)
        if not messagebox.askyesno("지도 초기화", f"{game}편 모든 층의 탐색 기록을 지울까요?"):
            return
        self._load_explored().clear()
        self._explored_dirty = True
        self._save_explored()
        self._record_explored()
        win = getattr(self, '_map_win', None)
        if (self._overlay_panel_kind == '지도'
                or (win is not None and win.winfo_exists())):
            self._draw_map()

    def _dump_memory(self):
        """F8: copy DOS memory (640 KB) and the CGA screen to files. Read only.

        For working out how the game unpacks its text (ASCII.KRN). Writes
        wiz_memdump_<time>.bin and a .txt with the screen lines and state.
        """
        mem = bytearray()
        for start in range(0, 0xA0000, 0x10000):
            chunk = self.hook.read_bytes(start, 0x10000)
            if not chunk:
                break
            mem += chunk
        video = self.cga_extractor.read_video_memory() or b''
        if not mem:
            return
        stamp = time.strftime('%Y%m%d_%H%M%S')
        base = dev_path(os.path.join('reference', 'dumps'), f'wiz_memdump_{stamp}')
        try:
            with open(base + '.bin', 'wb') as handle:
                handle.write(b'WIZMEM01' + len(mem).to_bytes(4, 'little') + bytes(mem)
                             + len(video).to_bytes(4, 'little') + bytes(video))
            lines = self.cga_extractor.scan_screen(video) if video else []
            with open(base + '.txt', 'w', encoding='utf-8') as handle:
                handle.write(f"anchor {self.state._anchor} state1 {self.state.state1} scene {self.state.current_scene}\n")
                handle.write('\n'.join(f"{line['y']:3d} {line['text']}" for line in lines) + '\n')
        except OSError:
            self._log_error()
            return
        try:
            user32.MessageBeep(0)   # saved
        except Exception:
            pass

    def _toggle_map(self):
        win = getattr(self, '_map_win', None)
        if self.mode != 'overlay' and win is not None and win.winfo_exists():
            win.destroy()
            self._map_win = None
            self.root.after_idle(self._save_companion_popups)
            return
        self._show_map()

    def _toggle_spells(self):
        win = getattr(self, '_spell_win', None)
        if self.mode != 'overlay' and win is not None and win.winfo_exists():
            win.destroy()
            self._spell_win = None
            self.root.after_idle(self._save_companion_popups)
            return
        self._show_spells()

    def _poll_hotkeys(self):
        """F1 toggles the map, F2 the spell list, F3 the item book.

        Only while DOSBox or one of our windows is in front, and not with
        Alt/Ctrl/Win held. The key still reaches the game. Tab is not used:
        it turns the party around in the maze.
        """
        caps = self._key_pressed(0x70)   # F1: map
        grave = self._key_pressed(0x71)  # F2: spells
        items = self._key_pressed(0x72)  # F3: item book
        dump = self._key_pressed(0x77)   # F8: read-only memory dump
        if not (caps or grave or items or dump):
            return
        if any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in (0x12, 0x11, 0x5B, 0x5C)):
            return
        fg = int(user32.GetForegroundWindow() or 0)
        if not fg:
            return
        fg = int(user32.GetAncestor(fg, GA_ROOT) or fg)
        ours = {int(self.hook.hwnd or 0)}
        for name in ('root', 'over', 'control', '_map_win', '_spell_win', '_item_win'):
            widget = getattr(self, name, None)
            try:
                if widget is not None and widget.winfo_exists():
                    ours.add(int(self._widget_hwnd(widget)))
            except tk.TclError:
                pass
        if fg not in ours:
            return
        try:
            if isinstance(self.root.focus_get(), tk.Entry):
                return   # Caps Lock while typing a path
        except (tk.TclError, KeyError):
            pass
        if dump and not RELEASE:
            self._dump_memory()
        if caps:
            self._toggle_map()
        if grave:
            self._toggle_spells()
        if items and self.mode == 'companion':
            self._toggle_items()

    def _poll_map(self):
        # Exploration is recorded whether or not the map is open.
        expected_game = self._current_game()
        if self._translation_game != expected_game:
            return
        previous_position = getattr(self, '_map_position', None)
        view_before = self._map_town_view
        moved = self._refresh_map_position()
        darkness_changed = self._refresh_map_darkness()
        revealed = self._record_explored()
        if (moved or revealed or darkness_changed) and ((self.mode == 'overlay' and self._overlay_panel_kind == '지도')
                      or (self.mode == 'companion' and self._map_win is not None and self._map_win.winfo_exists())):
            # Follow the party to its floor when the map showed the floor it
            # left, or showed no floor of it yet: a map restored before DOSBox
            # connected opened on floor 1 and stayed there (Wiz4 starts on 11).
            if view_before != self._map_town_view:
                # Leaving the town map: show the floor the party is on.
                if self._map_position and not self._map_town_view:
                    self._set_map_level(self._map_position[0])
                else:
                    self._draw_map()
            elif (self._map_position and self._map_level != self._map_position[0]
                    and (not previous_position or self._map_level == previous_position[0])):
                self._set_map_level(self._map_position[0])
            elif (revealed or darkness_changed) and self._map_position and self._map_position[0] == self._map_level:
                self._draw_map()
            else:
                self._draw_map_position()

    def _set_translation_game(self, game):
        game = game if game in (1, 2, 3, 4, 5) else self._current_game()
        if game != self._translation_game:
            if getattr(self, '_explored_dirty', False):
                self._save_explored()
                if self._explored_dirty:
                    return
            self._explored = None
            self._maps = None
            self._maps_failed_at = -10.0
            translations = self.unified_translations.copy()
            self.cga_extractor.update_glyphs(self._wiz5_glyphs if game == 5 else FONT_GLYPHS)
            self.cga_extractor.monster_keys = MONSTER_KEYS.copy()
            self.cga_extractor.item_keys = ITEM_KEYS.copy()
            self.cga_extractor.equipped_unidentified = {'ARMOR', 'SHIELD', 'WEAPON', 'HELM'} if game == 5 else set()
            self.cga_extractor.number_templates = self._wiz5_sentences if game == 5 else (self._wiz4_sentences if game == 4 else None)
            if game == 5:
                translations.update(self._wiz5_monsters)
                translations.update(self._wiz5_items)
                translations.update(self._wiz5_sentences)
                self.cga_extractor.monster_keys.update(self._wiz5_monsters)
                self.cga_extractor.item_keys.update(self._wiz5_items)
            elif game == 4:
                translations.update(self._wiz4_monsters)
                translations.update(self._wiz4_items)
                translations.update(self._wiz4_sentences)
                self.cga_extractor.monster_keys.update(self._wiz4_monsters)
                self.cga_extractor.item_keys.update(self._wiz4_items)
            elif game == 3:
                translations.update(self._wiz3_monsters)
                translations.update(self._wiz3_items)
                translations.update(self._wiz3_sentences)
                self.cga_extractor.monster_keys.update(self._wiz3_monsters)
                self.cga_extractor.item_keys.update(self._wiz3_items)
            elif game == 2:
                translations.update(self._wiz2_monsters)
                translations.update(self._wiz2_items)
                translations.update(self._wiz2_sentences)
                self.cga_extractor.monster_keys.update(self._wiz2_monsters)
                self.cga_extractor.item_keys.update(self._wiz2_items)
            self.cga_extractor.update_translations(translations)
            self.cga_extractor.reset_blank_shadow()
            self._translation_game = game
            self._overlay_video = None
            self._overlay_draw_sig = None
            had_overlay_map = (getattr(self, '_overlay_panel_kind', None) == '지도')
            if had_overlay_map:
                self._close_overlay_panel()
            map_win = getattr(self, '_map_win', None)
            had_comp_map = (map_win is not None and map_win.winfo_exists())
            if had_comp_map:
                map_win.destroy()
                self._map_win = None
            self._map_position = None
            if getattr(self, 'btn_stat', None) is not None:
                self._refresh_stat_button()
            if had_comp_map and self.mode == 'companion':
                self._show_map()
            elif had_overlay_map and self.mode == 'overlay':
                self._show_map()

    def _poll_game_state(self):
        detected = self.state.update()
        if not detected and self.hook.is_alive():
            now = time.monotonic()
            if now - getattr(self, '_last_base_check', -1.0) >= 0.5:
                self._last_base_check = now
                # DOSBox can allocate its final RAM block after the first connection.
                base = self.hook._find_dos_base(require_signature=True)
                if base is not None and base != self.hook.dos_base:
                    self.hook.dos_base = base
                    self.state.update()
        self._set_translation_game(self.state.game)
        if self.state.game not in (1, 5) and self._roll.active:
            self._roll.stop()
            self._sync_roll_labels()
        try:
            self._poll_hotkeys()
        except Exception:
            self._log_error()
        try:
            self._poll_map()
        except Exception:
            self._log_error()
        self._track_menu_context()
        if self.state.state1 == 22696:
            self.trade_stage = read_trade_stage(self.hook)
        else:
            self.trade_stage = None
        if self.state.state1 in (21616, 21840) or "미궁" in self.state.current_scene or "Maze" in self.state.current_scene:
            self.stairs_stage = read_stairs_prompt(self.hook)
        else:
            self.stairs_stage = None

    def _poll_loop(self):
        # One failing step must not stop the chain. An exception before
        # root.after used to end polling, and the overlay drew nothing.
        try:
            self._poll_tick()
        except Exception:
            self._log_error()
        try:
            translating = (self.mode == 'overlay' or getattr(self, '_companion_translate', False))
            delay = 2 if translating else self._roll_poll_ms()
        except Exception:
            delay = 16
        self.root.after(delay, self._poll_loop)

    def _log_error(self):
        """Append a traceback once per distinct error to wiz_overlay_error.log."""
        import traceback
        text = traceback.format_exc()
        seen = self.__dict__.setdefault('_logged_errors', set())
        if text in seen:
            return
        seen.add(text)
        try:
            with open(os.path.join(project_dir(), 'wiz_overlay_error.log'), 'a', encoding='utf-8') as handle:
                handle.write(time.strftime('[%Y-%m-%d %H:%M:%S]\n') + text + '\n')
        except OSError:
            pass

    def _poll_tick(self):
        overlay = self.mode == 'overlay'
        if not self.hook.is_alive():
            if self.hook.handle or self.hook.pid or self.hook.dos_base or self.hook.hwnd:
                self._clear_connection()
            # Look for DOSBox twice a second, not every 2ms tick.
            now = time.monotonic()
            if now - getattr(self, '_last_connect_try', 0.0) < 0.5:
                self._roll_step()
                return
            self._last_connect_try = now
            if self.mode == 'companion':
                self._snap_companion()
            # Just launched: wait for the BIOS string instead of guessing a block.
            fresh = now - getattr(self, '_launched_at', -100.0) < 10.0
            if self.hook.connect(require_signature=fresh):
                self._fill_dosbox_path()
                if self.mode == 'companion':
                    self._snap_companion()
                else:
                    self._snap_overlay()
        elif overlay:
            now = time.monotonic()
            if now - self._last_heavy >= 0.016:
                self._last_heavy = now
                self._poll_game_state()
                self._snap_overlay()
                self._watch_dosbox_pos()
            # Video is checked every tick. State and z-order stay on the slower tick
            # so a new English frame is covered before the next refresh.
            if self.last_rect:
                _, _, w, h = self.last_rect
                self._render_overlay(w, h)
        else:
            now = time.monotonic()
            heavy = getattr(self, '_companion_translate', False)
            if not heavy or now - self._last_heavy >= 0.016:
                if heavy:
                    self._last_heavy = now
                self._poll_game_state()
                self._snap_companion()
                self._render_companion()
                self._watch_dosbox_pos()
            if getattr(self, '_companion_translate', False) and self.hook.is_alive():
                self._snap_overlay()
                if self.last_rect:
                    _, _, w, h = self.last_rect
                    self._render_overlay(w, h)

        self._roll_step()

    def _key_pressed(self, vk):
        """Return True once for a physical key press without consuming input."""
        value = user32.GetAsyncKeyState(vk)
        down = bool(value & 0x8000)
        pressed = bool(value & 0x0001) or (down and not self._key_down.get(vk, False))
        self._key_down[vk] = down
        return pressed

    def _track_menu_context(self):
        """Track inspect submenus whose DOS state value is shared or delayed."""
        state1 = self.state.state1
        entering = state1 != self._last_state1
        keys = {
            'enter': self._key_pressed(0x0D),
            'escape': self._key_pressed(0x1B),
            'e': self._key_pressed(ord('E')),
            'd': self._key_pressed(ord('D')),
            'i': self._key_pressed(ord('I')),
            'r': self._key_pressed(ord('R')),
            'm': self._key_pressed(ord('M')),
            'p': self._key_pressed(ord('P')),
            'l': self._key_pressed(ord('L')),
            'a': self._key_pressed(ord('A')),
            'b': self._key_pressed(ord('B')),
            'c': self._key_pressed(ord('C')),
            'f': self._key_pressed(ord('F')),
            'g': self._key_pressed(ord('G')),
            'h': self._key_pressed(ord('H')),
            'j': self._key_pressed(ord('J')),
            'k': self._key_pressed(ord('K')),
            'n': self._key_pressed(ord('N')),
            'o': self._key_pressed(ord('O')),
            'q': self._key_pressed(ord('Q')),
            's': self._key_pressed(ord('S')),
            't': self._key_pressed(ord('T')),
            'u': self._key_pressed(ord('U')),
            'v': self._key_pressed(ord('V')),
            'w': self._key_pressed(ord('W')),
            'x': self._key_pressed(ord('X')),
            'y': self._key_pressed(ord('Y')),
            'z': self._key_pressed(ord('Z')),
        }
        selected_party = None
        selected_item = None
        for index in range(8):
            top_row = self._key_pressed(ord('1') + index)
            numpad = self._key_pressed(0x61 + index)
            if top_row or numpad:
                selected_item = index
                if index < 6:
                    selected_party = index

        if selected_party is not None and (
            state1 == 21678 or (state1 == 22704 and entering)
        ):
            self.inspect_party_index = selected_party

        # The inn uses the same memory state for its character and room menus.
        # Selecting a party number is therefore the reliable transition signal.
        if state1 == 22234:
            if entering or self.inn_stage is None:
                self.inn_stage = 'character'
                self.inn_party_index = None
                self.inn_message_until = 0.0
            if selected_party is not None:
                self.inn_stage = 'room'
                self.inn_party_index = selected_party
            elif self.inn_stage == 'napping' and time.monotonic() >= self.inn_message_until:
                # THE <NAME> IS NAPPING remains on screen for one second only.
                self.inn_stage = 'need_experience'
            elif self.inn_stage == 'room' and keys['a']:
                self.inn_stage = 'napping'
                self.inn_message_until = time.monotonic() + 1.5
            elif self.inn_stage == 'room' and any(keys[key] for key in ('b', 'c', 'd', 'e')):
                self.inn_stage = 'need_experience'
            elif self.inn_stage == 'need_experience' and (keys['enter'] or keys['escape']):
                self.inn_stage = 'room'
            elif self.inn_stage == 'room' and (keys['enter'] or keys['escape']):
                self.inn_stage = 'character'
                self.inn_party_index = None
        else:
            self.inn_stage = None
            self.inn_party_index = None
            self.inn_message_until = 0.0

        # Boltac's uses one state value for both its character selector and
        # the selected character's command menu, just like the inn.
        if state1 == 22310:
            if entering or self.shop_stage is None:
                self.shop_stage = 'character'
                self.shop_party_index = None
            if selected_party is not None:
                self.shop_stage = 'menu'
                self.shop_party_index = selected_party
            elif self.shop_stage == 'menu' and keys['b']:
                self.shop_stage = 'buy'
            elif self.shop_stage == 'menu' and keys['s']:
                self.shop_stage = 'sell'
            elif self.shop_stage == 'menu' and keys['u']:
                self.shop_stage = 'uncurse'
            elif self.shop_stage == 'menu' and keys['i']:
                self.shop_stage = 'identify'
            elif self.shop_stage in ('buy', 'sell', 'uncurse', 'identify') and (
                keys['l'] or keys['enter'] or keys['escape']
            ):
                self.shop_stage = 'menu'
            elif self.shop_stage == 'menu' and (
                keys['l'] or keys['enter'] or keys['escape']
            ):
                self.shop_stage = 'character'
                self.shop_party_index = None
        else:
            self.shop_stage = None
            self.shop_party_index = None

        # Tavern selectors may share/lag state values.  ADD accepts several
        # roster letters in succession and therefore stays open until Enter.
        party_count = len(self.state.party)
        party_removed = (
            state1 == 21780
            and self._last_party_count > 0
            and party_count < self._last_party_count
        )
        if state1 == 21678:
            if entering or self.tavern_stage is None:
                self.tavern_stage = 'main'
            if keys['a']:
                self.tavern_stage = 'add'
            elif keys['r']:
                self.tavern_stage = 'remove'
        elif state1 == 22602:
            if entering or self.tavern_stage is None:
                self.tavern_stage = 'add'
            if keys['enter'] or keys['escape']:
                self.tavern_stage = 'main'
        elif state1 == 21780:
            if entering or self.tavern_stage is None:
                self.tavern_stage = 'remove'
            if keys['enter'] or keys['escape'] or party_removed:
                self.tavern_stage = 'main'
        elif state1 not in (22704, 23692, 22696):
            self.tavern_stage = None

        # ADD closes automatically as soon as the sixth member joins.  The
        # memory state can lag behind the redraw, so party size is authoritative.
        if self.tavern_stage == 'add' and party_count >= 6:
            self.tavern_stage = 'main'

        # Character deletion has a confirmation screen but may retain the
        # selected-character state value for several frames.
        if state1 == 21122 and entering:
            self.training_action = 'selected'
        if state1 == 21122 and keys['d']:
            self.training_action = 'delete_confirm'
        elif self.training_action == 'delete_confirm' and keys['n']:
            self.training_action = 'selected'
        elif self.training_action == 'delete_confirm' and keys['y']:
            self.training_action = None
        elif state1 == 21048:
            self.training_action = None

        if state1 == 22704 and entering:
            self.inspect_action = 'base'
            self.equip_stage = None
        elif state1 == 23692 and entering:
            self.inspect_action = 'read'
        elif state1 == 22696:
            self.inspect_action = 'trade'
        elif state1 == 21678:
            self.inspect_action = None
            self.equip_stage = None

        # A key can be observed just before or just after DOS changes state, so
        # retain the last inspect context while handling the transition.
        in_inspect = self.inspect_action is not None or state1 in (22704, 23692, 22696)
        if in_inspect:
            if keys['e']:
                self.inspect_action = 'equip'
                self.equip_stage = 0
            elif keys['d']:
                self.inspect_action = 'drop'
                self.equip_stage = None
            elif keys['i'] and self._can_identify():
                self.inspect_action = 'identify'
                self.equip_stage = None
            elif keys['r']:
                self.inspect_action = 'read'
                self.equip_stage = None
            elif self.inspect_action == 'read' and (keys['m'] or keys['p']):
                self.inspect_action = 'spell_list'
            elif self.inspect_action == 'equip' and keys['escape']:
                self.inspect_action = 'base'
                self.equip_stage = None
            elif self.inspect_action == 'equip' and (selected_item is not None or keys['enter']):
                if self.equip_stage is None:
                    self.equip_stage = 0
                elif self.equip_stage < 4:
                    self.equip_stage += 1
                else:
                    self.inspect_action = 'base'
                    self.equip_stage = None
            elif keys['enter'] or keys['escape']:
                if self.inspect_action == 'spell_list':
                    self.inspect_action = 'read'
                elif self.inspect_action in ('drop', 'identify', 'trade'):
                    self.inspect_action = 'base'
                elif self.inspect_action == 'read':
                    self.inspect_action = 'base'

        self._last_state1 = state1
        self._last_party_count = party_count

    def _can_identify(self):
        index = self.inspect_party_index
        return (
            index is not None
            and 0 <= index < len(self.state.party)
            and self.state.party[index].get('class') == '비숍'
        )

    def _sync_color_button(self):
        btn = getattr(self, 'btn_to_color', None)
        if btn is not None:
            mono = self.theme_color == 'mono'
            btn.config(text="색상: 흑백" if mono else "색상: 컬러", fg="#cdd6f4" if mono else "#a6e3a1")

    def toggle_color_mode(self):
        self.theme_color = 'mono' if self.theme_color == 'color' else 'color'
        _remember(color=self.theme_color)
        self._sync_color_button()
        if self.mode == 'overlay' and self.last_rect:
            _, _, w, h = self.last_rect
            self._render_overlay(w, h)

    def get_color(self, ctype):
        if self.theme_color == 'mono':
            return "#ffffff"
        if ctype in ('hotkey', 'ac', 'combat'):
            return "#ffff55"
        elif ctype == 'spaced':
            return "#55ffff"
        elif ctype == 'killed':
            return "#ff5555"
        elif ctype in ('hp', 'status_ok'):
            return "#a6e3a1"
        elif ctype == 'status_bad':
            return "#f38ba8"
        elif ctype == 'subtext':
            return "#a6adc8"
        return "#ffffff"

    @staticmethod
    def _get_cga_text_width(text):
        w = 0
        for ch in text:
            if ord(ch) < 128:
                w += 4
            else:
                w += 8
        return w

    def _calculate_menu_layout(self, matches):
        """
        Analyzes matches to identify vertical menu blocks that are crammed against the left border.
        Shifts them rightward toward the center while preserving 100% left-alignment across the menu.
        """
        row_counts = {}
        for m in matches:
            y = m['y']
            row_counts[y] = row_counts.get(y, 0) + 1

        menu_candidates = []
        for m in matches:
            if m.get('is_raw_token', False) or m.get('is_char_name', False):
                continue
            y = m['y']
            x = m['x']
            orig = m['original']
            is_single = (row_counts.get(y, 0) == 1)
            is_upper = (20 <= y <= 150)
            is_left = (x <= 32)
            is_hotkey = any(orig.startswith(k) for k in (
                "A)", "B)", "C)", "D)", "E)", "F)", "F↵", "G)", "I)", "L)", "L↵", "M)", "P)", "P↵", "R)", "S)", "T)", "U)", "#)", "↵)", ")"
            )) or orig in ("CHANGE CLASS", "LEAVE", "L↵EAVE", "P↵ARRY", "PARRY", "F↵IGHT", "FIGHT") or orig.startswith("↵") or orig.startswith(")")

            if is_single and is_upper and is_left and is_hotkey:
                menu_candidates.append(m)

        menu_candidates.sort(key=lambda m: m['y'])
        blocks = []
        current_block = []
        for m in menu_candidates:
            if not current_block:
                current_block.append(m)
            else:
                prev_y = current_block[-1]['y']
                if 4 <= (m['y'] - prev_y) <= 20:
                    current_block.append(m)
                else:
                    if len(current_block) >= 2:
                        blocks.append(current_block)
                    current_block = [m]
        if len(current_block) >= 2:
            blocks.append(current_block)

        shifted_positions = {}
        for block in blocks:
            orig_left = block[0]['x'] // 8
            max_orig_cols = max(m['w'] for m in block) // 8
            orig_right = orig_left + max_orig_cols
            # Place halfway between the left and right of original text placement (col 6 ~ 7)
            target_col = min(7, max(orig_left + 4, (orig_left + orig_right) // 2))
            target_x = target_col * 8
            for m in block:
                shifted_positions[id(m)] = target_x

        return shifted_positions

    def _render_auto_cga_translations(self, w, h, font_ko, video_bytes=None, detected_lines=None):
        """Automatically scans CGA screen for English words/phrases and renders Korean translations with coordinates."""
        def _cover_rect(x1, y1, x2, y2, **kw):
            # Whole pixels outward. A fractional edge left the first scaled
            # pixel column of a letter showing (two dots beside a centered "M)").
            return self.canvas.create_rectangle(math.floor(x1), math.floor(y1),
                                                math.ceil(x2), math.ceil(y2), **kw)

        try:
            # Determine game scene context (chest, combat, town)
            scene = getattr(self.state, 'current_scene', '') or ''
            state1 = getattr(self.state, 'state1', 0) or 0
            stairs_stage = getattr(self, 'stairs_stage', None)
            if stairs_stage == 'up':
                ctx = "stairs_up"
            elif stairs_stage == 'down':
                ctx = "stairs_down"
            elif state1 == 21676 or "보물상자" in scene or "Chest" in scene:
                ctx = "chest"
            elif state1 in (21962, 22296) or (("전투" in scene or "Combat" in scene) and state1 != 22692):
                # 22692 is WAE SelectSpell/UseSelectItem: camp as well as combat.
                # Treating it as combat re-flowed the camp stat sheet rows.
                ctx = "combat"
            elif any(k in scene for k in ("마을", "주점", "훈련장", "Castle", "Tavern", "Training", "Camp", "Inn")):
                ctx = "town"
            else:
                ctx = None

            if detected_lines is not None:
                lines = detected_lines
            elif video_bytes is not None:
                lines = self.cga_extractor.scan_screen(video_bytes)
            else:
                lines = None
            matches = self.cga_extractor.find_translations(
                context=ctx, detected_lines=lines,
                video_bytes=None if lines is not None else video_bytes,
            )
            guard = bool(getattr(self.state, "prevent_stat_loss", False))
            protected = tuple(sorted(getattr(self.state, "levelup_protected", ())))
            draw_sig = (
                w, h, self.theme_color, guard, protected,
                tuple(
                    (m['x'], m['y'], m['w'], m['original'], m['korean'],
                     bool(m.get('is_raw_token')), bool(m.get('is_stat_attr')),
                     bool(m.get('is_char_name')), bool(m.get('letter_spaced')), bool(m.get('wrapped_sentence')),
                     m.get('context'), m.get('min_bound_x'), m.get('max_bound_x'))
                    for m in matches
                ),
            )
            if draw_sig == self._overlay_draw_sig:
                return True
            # The black rectangle covers the English. Writing a blank over the
            # game's letter deletes that letter, and the Korean goes with it.
            self._overlay_draw_sig = draw_sig
            self.canvas.delete("all")
            if not matches:
                return True
            scale_x = w / 320.0
            scale_y = h / 200.0

            # Calculate centered layout for vertical menu blocks
            shifted_positions = self._calculate_menu_layout(matches)

            hot_color = self.get_color('hotkey')
            white = self.get_color('white')
            combat_color = self.get_color('combat')
            battle_rows = {m['y'] for m in matches if not m.get('paragraph') and battle_line_mark(m['original'])}
            hot_re = re.compile(r'((?<![\w/(#])[A-Z0-9#]\)|↵)')
            message_positions = {}
            message_rows = {}
            if ctx == 'combat' or battle_rows:
                font_measure = tkfont.Font(root=self.root, font=font_ko)
                message_rows = {}
                message_positions = _combat_message_positions(matches, lines, ctx, font_measure.measure, scale_x,
                                                              message_rows)
            measures = {}
            # Party list: HITS at or below a third of the max (STATUS column)
            # is drawn yellow. A word in STATUS (DEAD, ASLEEP...) is skipped.
            low_hp = set()
            for line in lines or ():
                hp = _PARTY_HP_RE.match(line['text'])
                if hp and int(hp.group(1)) * 3 <= int(hp.group(2)):
                    low_hp.add((line['y'], hp.start(1)))
            row_text = {line['y']: line['text'] for line in lines or ()}

            def font_measure_once(font):
                if font not in measures:
                    measures[font] = tkfont.Font(root=self.root, font=font)
                return measures[font]

            def draw_segments(x0, cy, segs, font):
                ids = []
                cur = x0
                for text, col in segs:
                    if not text:
                        continue
                    tid = self.canvas.create_text(cur, cy, anchor="w", text=text, fill=col, font=font)
                    ids.append(tid)
                    bb = self.canvas.bbox(tid)
                    if bb:
                        cur = bb[2]
                return ids, cur

            reflowed = set()
            paragraphs = {}
            for m in matches:
                if m.get('paragraph') is not None:
                    paragraphs.setdefault(m['paragraph'], []).append(m)
            if paragraphs:
                line_by_y = {line['y']: line for line in lines or ()}
                font_measure = tkfont.Font(root=self.root, font=font_ko)
                for (_first, korean), items in paragraphs.items():
                    items.sort(key=lambda m: m['y'])
                    rows = [_paragraph_row_bounds(line_by_y.get(m['y']), m) for m in items]
                    spill = _blank_rows_below(video_bytes, line_by_y, items[-1]['y'], rows[-1][1], rows[-1][2])
                    is_centered = False
                    if items and len(rows) == len(items):
                        row_centered = [
                            abs((m['x'] - r[1]) - (r[2] - m['x'] - m['w'])) <= 8
                            for m, r in zip(items, rows)
                        ]
                        if len(items) >= 2:
                            start_cols = [m['x'] // 8 for m in items]
                            all_same_start = len(set(start_cols)) == 1
                            if all(row_centered) and not all_same_start:
                                is_centered = True
                            elif all(row_centered) and all_same_start:
                                if (items[0]['x'] - rows[0][1]) > 8:
                                    is_centered = True
                        elif len(items) == 1:
                            m0, r0 = items[0], rows[0]
                            if row_centered[0]:
                                line_text = row_text.get(m0['y'], '')
                                left_edge = line_text.rfind(FRAME_CHAR, 0, m0['x'] // 8)
                                right_edge = line_text.find(FRAME_CHAR, (m0['x'] + m0['w']) // 8)
                                start_col = m0['x'] // 8
                                in_block = any(
                                    _row_start_col(row_text.get(m0['y'] + dy, ''), left_edge, right_edge) == start_col
                                    for dy in (-8, 8)
                                )
                                if not in_block:
                                    is_centered = True

                    layout = None
                    for extra in range(len(spill) + 1):
                        bounds = [(m['y'], lo * scale_x + 1, hi * scale_x - 2)
                                  for m, (lo, hi) in zip(items, ((r[1], r[2]) for r in rows))]
                        bounds += [(y, lo * scale_x + 1, hi * scale_x - 2) for y, lo, hi in spill[:extra]]
                        layout = _layout_translated_rows([(korean, white)], bounds, font_measure.measure,
                                                         align='center' if is_centered else 'left')
                        if layout is not None:
                            break
                    if layout is None:
                        continue
                    for m in items:
                        bg = _cover_rect(m['x'] * scale_x, m['y'] * scale_y,
                                                          (m['x'] + m['w']) * scale_x, (m['y'] + 8) * scale_y,
                                                          fill='#000000', outline='')
                        self.canvas.tag_lower(bg)
                        reflowed.add(id(m))
                    for draw_x, draw_y, word, color in layout:
                        self.canvas.create_text(draw_x, (draw_y + 4) * scale_y, anchor='w',
                                                text=word, fill=color, font=font_ko)

            for m in matches:
                if id(m) in reflowed:
                    continue
                x = m['x']
                y = m['y']
                w_px = m['w']
                orig = m['original']
                ko = m['korean']
                cy = (y + 4) * scale_y
                min_bx = m.get('min_bound_x', 0) * scale_x
                max_bx = m.get('max_bound_x', 320) * scale_x
                is_char_name = m.get('is_char_name', False)
                is_raw = m.get('is_raw_token', False) or (ko == orig and ko.isascii())
                emph = (y in battle_rows or 48 <= y < 88) and combat_emphasis(
                    orig, is_char_name, is_raw, y in battle_rows, m.get('context'),
                    self.cga_extractor.monster_keys,
                )
                body = (self.get_color('killed') if emph and 'KILLED' in orig.upper()
                        else self.get_color('spaced') if m.get('letter_spaced')
                        else combat_color if emph else white)
                is_hotkey = not is_char_name and bool(re.match(r'[A-Z0-9#]\)|[A-Z]?↵', orig))

                if id(m) in message_positions:
                    x1 = max(min_bx, x * scale_x)
                    x2 = min(max_bx, (x + w_px) * scale_x)
                    bg = _cover_rect(x1, y * scale_y, x2, (y + 8) * scale_y,
                                                      fill="#000000", outline="")
                    self.canvas.tag_lower(bg)
                    draw_x = message_positions[id(m)]
                    draw_y = message_rows.get(id(m), y)   # a continued sentence sits on its first row
                    _, cur = draw_segments(draw_x, (draw_y + 4) * scale_y, [(ko, body)], font_ko)
                    if ko:
                        bg = _cover_rect(draw_x, draw_y * scale_y, cur, (draw_y + 8) * scale_y,
                                                          fill="#000000", outline="")
                        self.canvas.tag_lower(bg)
                    continue

                # 1) Untranslated English / numbers / names: redraw cell-by-cell on the
                #    original 8px CGA grid so right-aligned numbers and columns stay aligned.
                is_grid = m.get('is_raw_token', False) or (ko == orig and ko.isascii())
                if is_grid:
                    x1 = max(min_bx, x * scale_x)
                    x2 = min(max_bx, (x + w_px) * scale_x)
                    _cover_rect(x1, y * scale_y, x2, (y + 8) * scale_y,
                                                 fill="#000000", outline="")
                    col_char = hot_color if is_hotkey else body
                    if (y, x // 8) in low_hp:
                        col_char = body = _LOW_HP_COLOR
                    hk_len = 0
                    if is_hotkey:
                        mm = hot_re.match(ko)
                        hk_len = len(mm.group(0)) if mm else 0
                    for i, ch in enumerate(ko):
                        if ch == ' ':
                            continue
                        c = hot_color if i < hk_len else (body if hk_len else col_char)
                        self.canvas.create_text((x + i * 8 + 4) * scale_x, cy, anchor="center",
                                                text=ch, fill=c, font=font_ko)
                    continue

                # 2) Translated text
                is_stat = m.get('is_stat_attr', False) or orig in (
                    "STRENGTH", "I.Q.", "PIETY", "VITALITY", "AGILITY", "LUCK", "BONUS"
                )
                if not is_stat and id(m) in shifted_positions:
                    draw_x = shifted_positions[id(m)] * scale_x
                else:
                    draw_x = x * scale_x
                    # A centered line (a sign, a status box) stays centered on the
                    # middle of the English. Only the text inside the window that
                    # holds it counts: maze lines beside the box are not part of it.
                    line_text = row_text.get(y, '')
                    left_edge = line_text.rfind(FRAME_CHAR, 0, x // 8)
                    right_edge = line_text.find(FRAME_CHAR, (x + w_px) // 8)
                    inside = line_text[left_edge + 1:right_edge if right_edge >= 0 else len(line_text)]
                    # Hotkey rows too: a lone centered menu line ("S)TART GAME")
                    # is centered; a menu block shares its start column.
                    # Keys can carry the game's double spaces ("WORLD  OF").
                    # The game draws the LIGHT/PROTECT status word at the box's left;
                    # these two are centered in the box on purpose.
                    box_word = orig in ('LIGHT', 'PROTECT') and left_edge >= 0 and right_edge >= 0
                    if box_word:
                        draw_x = ((left_edge + 1 + right_edge) * 4) * scale_x - font_measure_once(font_ko).measure(ko) / 2
                    elif orig == 'WIZARDRY V':
                        # Between two heart pictures: the box test sees extra shapes.
                        # Center on the English, which is centered between them.
                        draw_x = (x + w_px / 2) * scale_x - font_measure_once(font_ko).measure(ko) / 2
                    elif not is_stat and re.sub(' +', ' ', inside.strip(' ')) == re.sub(' +', ' ', orig.strip()):
                        lo = (left_edge + 1) * 8 if left_edge >= 0 else 0
                        hi = right_edge * 8 if right_edge >= 0 else 320
                        # A row in a left-aligned paragraph has a neighbour row that
                        # starts in the same column; such rows are never centered,
                        # however even their margins look.
                        start_col = x // 8
                        in_block = any(
                            _row_start_col(row_text.get(y + dy, ''), left_edge, right_edge) == start_col
                            for dy in (-8, 8))
                        # No minimum margin: a title that fills its box leaves
                        # 0 and 1 cells ("LLYLGAMYN" in the town title box).
                        if not in_block and abs((x - lo) - (hi - x - w_px)) <= 8:
                            draw_x = (x + w_px / 2) * scale_x - font_measure_once(font_ko).measure(ko) / 2
                    # A label right before '=' ("MAGE SPELLS =") ends where the
                    # English ended, so the labels line up on the '='.
                    elif (not is_stat and line_text[(x + w_px) // 8:].lstrip(' ').startswith('=')
                            and not hot_re.search(ko)):
                        draw_x = (x + w_px) * scale_x - font_measure_once(font_ko).measure(ko)

                # A number kept at the end ("MAGE 0/" -> "마법사 0/") stays in its
                # own CGA cells, in line with the counts the game prints after it.
                tail = re.search(r' ([0-9][0-9/]*)$', orig)
                tail_x = None
                if tail and ko.endswith(' ' + tail.group(1)) and w_px == len(orig) * 8:
                    tail_x = x + (len(orig) - len(tail.group(1))) * 8
                    label = ko[:-len(tail.group(1))].rstrip()
                    if font_measure_once(font_ko).measure(label) + draw_x < tail_x * scale_x:
                        ko = label
                    else:
                        tail_x = None

                # Keep the line inside its window.
                if tail_x is None:
                    text_w = font_measure_once(font_ko).measure(ko)
                    if draw_x + text_w > max_bx:
                        draw_x = max(min_bx, max_bx - text_w)

                # Hotkeys (A), ↵ ...) in hotkey colour, labels in white for readability
                segs = []
                for part in hot_re.split(ko):
                    if not part:
                        continue
                    segs.append((part, hot_color if hot_re.fullmatch(part) else body))

                _, cur = draw_segments(draw_x, cy, segs, font_ko)
                if tail_x is not None:
                    for i, ch in enumerate(tail.group(1)):
                        self.canvas.create_text((tail_x + i * 8 + 4) * scale_x, cy, anchor="center",
                                                text=ch, fill=body, font=font_ko)
                    cur = max(cur, (tail_x + len(tail.group(1)) * 8) * scale_x)

                if guard and orig in _LEVELUP_LOST:
                    gap = max(4, int(scale_x))
                    note_id = self.canvas.create_text(
                        cur + gap, cy, anchor="w", text="→ 스텟 보호",
                        fill="#a6e3a1", font=font_ko,
                    )
                    bb = self.canvas.bbox(note_id)
                    if bb:
                        cur = bb[2]

                if is_stat:
                    x1 = max(min_bx, x * scale_x)
                    x2 = min(max_bx, (x + w_px) * scale_x)
                else:
                    x1 = max(min_bx, min(draw_x, x * scale_x))
                    x2 = min(max_bx, max((x + w_px) * scale_x, cur))
                # Constrain vertically strictly within the 8px CGA row to protect borders and corners
                bg_id = _cover_rect(x1, y * scale_y, x2, (y + 8) * scale_y,
                                                     fill="#000000", outline="")
                self.canvas.tag_lower(bg_id)
            self._draw_party_updates(lines, scale_x, scale_y, font_ko)
            return True
        except Exception:
            self._log_error()
            self._overlay_draw_sig = None
            return False

    # ----------------------------------------------------
    # In-Game Overlay Drawing (Authentic Retro CGA Aesthetic)
    # ----------------------------------------------------
    def _render_overlay(self, w, h):
        video = self.cga_extractor.read_video_memory()
        if not video:
            if self._overlay_video is not None:
                self.canvas.delete("all")
                self.cga_extractor.reset_blank_shadow()
                self._overlay_video = None
                self._overlay_box = None
                self._overlay_draw_sig = None
            return
        if video != self._overlay_video:
            self._nudge_dosbox_paint()
        box = (w, h, self.theme_color)
        # Same pixels and same window: painting again flashes the color-key surface.
        protected = (
            bool(getattr(self.state, "prevent_stat_loss", False)),
            tuple(sorted(getattr(self.state, "levelup_protected", ()))),
        )
        if (video == self._overlay_video and box == self._overlay_box
                and protected == self._overlay_protected):
            return
        row_h = h / 25.0
        font_pixel_h = max(10, int(round(row_h)))
        font_ko = (self.mono_font_family, -font_pixel_h, "normal")

        # Read the English and cover it on this window. Do not write the
        # game's framebuffer. A blank written over a letter removes it.
        lines = self.cga_extractor.remember_shown_text(video)
        if self._render_auto_cga_translations(w, h, font_ko, video, detected_lines=lines):
            frame = ImageTk.PhotoImage(_cga_image(video, w, h), master=self.over)
            self.canvas.delete('cga_frame')
            self.canvas.create_image(0, 0, image=frame, anchor='nw', tags='cga_frame')
            self.canvas.tag_lower('cga_frame')
            self._cga_frame = frame
            self._overlay_video = self.cga_extractor._shown
            self._overlay_box = box
            self._overlay_protected = protected
        return

        font_mono = (self.mono_font_family, int(row_h * 0.46), "bold")
        font_small = (self.mono_font_family, int(row_h * 0.38), "normal")

        scene = self.scene_override or self.state.current_scene
        if self.tavern_stage == 'add':
            scene = "선술집 - 모험가 추가"
        elif self.tavern_stage == 'remove':
            scene = "선술집 - 모험가 제외"
        elif self.tavern_stage == 'main' and self.state.state1 in (21678, 21780, 22602):
            scene = "길가메시의 선술집"
        if self.training_action and scene.startswith("알 수 없는 상태"):
            scene = ("훈련장 - 캐릭터 삭제 확인"
                     if self.training_action == 'delete_confirm'
                     else "훈련장 - 캐릭터 선택됨")
        if self.inspect_action and scene.startswith("알 수 없는 상태"):
            scene = "캐릭터 상세 점검"
        elif scene.startswith("알 수 없는 상태"):
            # Unknown scene: auto-scan CGA screen and translate words dynamically!
            self._render_auto_cga_translations(w, h, font_ko)
            return
        is_utility = "유틸리티" in scene or "Utilities" in scene
        is_training_main = self.state.state1 == 21048
        training_states = {21048, 21782, 21122, 22178, 21154, 23166,
                           21082, 21126, 21078, 21448, 20888}
        is_training = self.state.state1 in training_states or self.training_action is not None
        is_castle = is_utility or is_training or any(k in scene for k in ["성", "선술집", "상점", "사원", "여관", "외곽", "Castle", "Tavern", "Trading", "Temple", "Inn", "Edge", "Shop", "점검", "Inspect"])

        # ====================================================
        # 1. Castle / Town Screens
        # ====================================================
        if is_castle:
            if is_utility:
                # WIZARDRY UTILITIES uses the wider original title box.
                self.canvas.create_rectangle(col_w * 10.4, row_h * 0.45, col_w * 29.6, row_h * 2.55, fill="#000000", outline="#000000")
                self.canvas.create_text(col_w * 20.0, row_h * 1.5, text="위저드리 유틸리티", fill="#ffffff", font=font_ko, anchor="center")
            elif is_training:
                # TRAINING GROUNDS has a wider title box than CASTLE.
                # The full-screen roster has no title box at all.
                if self.state.state1 != 20888:
                    self.canvas.create_rectangle(col_w * 11.55, row_h * 0.75, col_w * 28.45, row_h * 2.25, fill="#000000", outline="")
                    self.canvas.create_text(col_w * 20.0, row_h * 1.5, text="훈련장", fill="#ffffff", font=font_ko, anchor="center")
            else:
                # Cover only CASTLE's letters.  The original box outline must stay.
                self.canvas.create_rectangle(col_w * 16.85, row_h * 0.95, col_w * 23.15, row_h * 1.95, fill="#000000", outline="")
                place_title = "마을 외곽" if ("외곽" in scene or "Edge" in scene) else "릴가민 성"
                self.canvas.create_text(col_w * 20.0, row_h * 1.6, text=place_title, fill="#ffffff", font=font_ko, anchor="center")

            # ------------------------------------------------
            # Scene: 캐릭터 상세 및 인벤토리 점검 (Inspect)
            # (Prioritized so inspecting from Tavern or Camp is always caught)
            # ------------------------------------------------
            if is_utility:
                # C) CHANGE NAME / M) MOVE CHARACTERS /
                # P) RESTART AN "OUT" PARTY / L) LEAVE UTILITIES
                self.canvas.create_rectangle(
                    col_w * 7.35, row_h * 8.2,
                    col_w * 32.65, row_h * 13.65,
                    fill="#000000", outline="#000000"
                )
                utility_opts = [
                    ("C)", " 이름 변경"),
                    ("M)", " 캐릭터 이동"),
                    ("P)", " 중단된 파티 재개"),
                    ("L)", " 유틸리티 나가기")
                ]
                for idx, (hk, desc) in enumerate(utility_opts):
                    self._draw_colored_line(
                        col_w * 8.1, row_h * (9.4 + idx),
                        [(hk, self.get_color('hotkey')), (desc, "#ffffff")],
                        font_ko
                    )

            elif is_training:
                self._render_training_overlay(col_w, row_h, font_ko, font_mono, font_small)

            elif "모험가 추가" in scene:
                # Keep both original boxes and the roster below them.  Replace
                # only GILGAMESH'S TAVERN and the selector prompt.
                self.canvas.create_rectangle(
                    col_w * 9.5, row_h * 4.7,
                    col_w * 30.5, row_h * 6.0,
                    fill="#000000", outline=""
                )
                self.canvas.create_text(
                    col_w * 20.0, row_h * 5.4,
                    text="길가메시의 선술집", fill="#ffffff",
                    font=font_ko, anchor="center"
                )
                self.canvas.create_rectangle(
                    col_w * 2.35, row_h * 6.35,
                    col_w * 37.65, row_h * 8.85,
                    fill="#000000", outline=""
                )
                self.canvas.create_text(
                    col_w * 20.0, row_h * 7.4,
                    text="(문자) 선택,  ↵ 나가기",
                    fill="#ffffff", font=font_ko, anchor="center"
                )

            elif "모험가 제외" in scene:
                # Screenshot: Gilgamesh's Tavern → R) REMOVE
                # Preserve the original popup border and replace only its two
                # English text rows.
                self.canvas.create_rectangle(col_w * 8.2, row_h * 8.0,
                    col_w * 31.8, row_h * 10.2, fill="#000000", outline="")
                self.canvas.create_text(col_w * 20.0, row_h * 8.55,
                    text="누구를 제외합니까 (#)?", fill="#ffffff", font=font_ko, anchor="center")
                self.canvas.create_text(col_w * 20.0, row_h * 9.55,
                    text="↵ 나가기", fill="#ffffff", font=font_ko, anchor="center")

            elif "점검" in scene or "Inspect" in scene:
                if self.inspect_action == 'trade':
                    # Original popup interior: cols 13.4..38.6, rows 8.3..12.7.
                    # Only replace the two text rows; row 11 input stays visible.
                    if self.trade_stage is not None:
                        row = 10 if self.trade_stage == 'who' else 9
                        prompt = {'who': '누구에게 양도합니까 (#)?',
                                  'gold': '양도할 골드 금액은?',
                                  'item': '양도할 아이템 번호는 (#)?'}[self.trade_stage]
                        self.canvas.create_rectangle(col_w*13.5, row_h*row,
                            col_w*38.5, row_h*(row+2), fill='#000000', outline='')
                        self.canvas.create_text(col_w*26, row_h*(row+.5), text=prompt,
                            fill='#ffffff', font=font_ko, anchor='center')
                        self.canvas.create_text(col_w*26, row_h*(row+1.5), text='↵ 나가기',
                            fill='#ffffff', font=font_ko, anchor='center')
                elif self.inspect_action == 'spell_list':
                    # M/P opens the actual spell list; leave it completely
                    # unobscured even while state1 still reports InspectRead.
                    pass
                elif self.inspect_action == 'equip':
                    # Preserve the item list; cover only SELECT ... and the
                    # EQUIP/LEAVE prompt rows inside the original popup.
                    self.canvas.create_rectangle(col_w * 8.3, row_h * 8.55,
                        col_w * 31.7, row_h * 9.65, fill='#000000', outline='')
                    equip_names = ('무기', '갑옷', '방패', '투구', '건틀릿')
                    equip_name = equip_names[self.equip_stage or 0]
                    self.canvas.create_text(col_w * 20, row_h * 9.2,
                        text=f'{equip_name} 선택', fill='#ffffff', font=font_ko, anchor='center')
                    self.canvas.create_rectangle(col_w * 8.3, row_h * 12.55,
                        col_w * 31.7, row_h * 15.55, fill='#000000', outline='')
                    self.canvas.create_text(col_w * 20, row_h * 13.8,
                        text=f'어느 {equip_name}을 장착합니까 (#)?', fill='#ffffff', font=font_ko, anchor='center')
                    self.canvas.create_text(col_w * 20, row_h * 14.8,
                        text='↵ 장착하지 않음', fill='#ffffff', font=font_ko, anchor='center')
                elif self.inspect_action == 'drop':
                    self.canvas.create_rectangle(col_w * 13.4, row_h * 8.2,
                        col_w * 38.6, row_h * 12.8, fill='#000000', outline='')
                    self.canvas.create_text(col_w * 26, row_h * 9.5,
                        text='버릴 아이템 번호는 (#)?', fill='#ffffff', font=font_ko, anchor='center')
                    self.canvas.create_text(col_w * 26, row_h * 10.7,
                        text='↵ 나가기', fill='#ffffff', font=font_ko, anchor='center')
                elif self.inspect_action == 'identify' and self._can_identify():
                    self.canvas.create_rectangle(col_w * 13.4, row_h * 8.2,
                        col_w * 38.6, row_h * 12.8, fill='#000000', outline='')
                    self.canvas.create_text(col_w * 26, row_h * 9.35,
                        text='감정할 아이템 번호는 (#)?', fill='#ffffff', font=font_ko, anchor='center')
                    self.canvas.create_text(col_w * 26, row_h * 10.55,
                        text='↵ 나가기', fill='#ffffff', font=font_ko, anchor='center')
                elif self.inspect_action == 'read':
                    # Keep the spell counts, replace labels and M/P/Enter menu.
                    for row, label in ((8, '마법사 주문 ='), (9, '사제 주문 =')):
                        self.canvas.create_rectangle(col_w*.8, row_h*row,
                            col_w*16, row_h*(row+1), fill='#000000', outline='')
                        self.canvas.create_text(col_w*15.8, row_h*(row+.5), text=label,
                            fill='#ffffff', font=font_ko, anchor='e')
                    self.canvas.create_rectangle(col_w*8.8, row_h*12,
                        col_w*29, row_h*15, fill='#000000', outline='')
                    for row, key, label in ((12, 'M)', ' 마법사 주문서'),
                                             (13, 'P)', ' 사제 주문서'),
                                             (14, '↵', ' 나가기')):
                        self._draw_colored_line(col_w*9, row_h*(row+.5),
                            [(key, self.get_color('hotkey')), (label, '#ffffff')], font_ko)
                else:
                    self.canvas.create_rectangle(col_w*.6, row_h*21.3,
                        col_w*39.4, row_h*24.6, fill='#000000', outline='')
                    inspect_options = [
                        (1,22,'R)', ' 읽기'), (8,22,'T)', ' 양도'),
                        (15,22,'P)', ' 골드 모으기'), (26,22,'L / ↵', ' 나가기'),
                        (1,23,'E)', ' 장착'), (8,23,'D)', ' 버리기')]
                    if self._can_identify():
                        inspect_options.append((15,23,'I)', ' 감정'))
                    for col, row, key, label in inspect_options:
                        self._draw_colored_line(col_w*col, row_h*(row+.5),
                            [(key, self.get_color('hotkey')), (label, '#ffffff')], font_ko)

            # ------------------------------------------------
            # Scene: 길가메시의 선술집 (Gilgamesh's Tavern)
            # ------------------------------------------------
            elif "선술집" in scene or "Tavern" in scene:
                # Tavern box inside: cols 9.4 to 30.6, rows 4.35 to 12.8
                self.canvas.create_rectangle(col_w * 9.4, row_h * 4.35, col_w * 30.6, row_h * 12.8, fill="#000000", outline="#000000")
                self.canvas.create_text(col_w * 20.0, row_h * 5.3, text="길가메시 선술집", fill="#ffffff", font=font_ko, anchor="center")

                opts = [
                    ("A)", " 모험가 추가"),
                    ("R)", " 파티원 제외"),
                    ("#)", " 상태 점검"),
                    ("D)", " 골드 분배"),
                    ("L / ↵)", " 선술집 나가기")
                ]
                for idx, (hk, desc) in enumerate(opts):
                    cy = row_h * (7.0 + idx * 1.0)
                    self._draw_colored_line(col_w * 11.5, cy, [(hk, self.get_color('hotkey')), (desc, "#ffffff")], font_ko)

            # ------------------------------------------------
            # Scene: 볼탁 상점 - 아이템 구매 (Boltac's Buy Menu)
            # ------------------------------------------------
            elif "구매" in scene or "Shop Buy" in scene:
                self.canvas.create_rectangle(col_w * 0.6, row_h * 3.0, col_w * 39.4, row_h * 15.5, fill="#000000", outline="#000000")
                self.canvas.create_text(col_w * 2.5, row_h * 4.0, text="볼탁 만물상점 - 아이템 구매", fill="#ffffff", font=font_ko, anchor="w")

                items = [
                    ("1)", " 롱 소드 (장검)", "25 GP"),
                    ("2)", " 쇼트 소드 (단검)", "15 GP"),
                    ("3)", " 성유 바른 메이스 (성직자용)", "30 GP"),
                    ("4)", " 성유 바른 플레일", "150 GP"),
                    ("5)", " 지팡이 (호신용)", "10 GP"),
                    ("6)", " 대거 (단도)", "5 GP")
                ]
                for idx, (hk, name, price) in enumerate(items):
                    cy = row_h * (5.2 + idx * 0.95)
                    self._draw_colored_line(col_w * 2.5, cy, [(hk, self.get_color('hotkey')), (name, "#ffffff")], font_ko)
                    self.canvas.create_text(col_w * 28.0, cy, text=price, fill=self.get_color('hotkey'), font=font_mono, anchor="w")

                self.canvas.create_text(col_w * 2.5, row_h * 11.4, text="소지금(GP) 확인 후 구매할 번호를 입력하십시오", fill="#ffffff", font=font_small, anchor="w")

                self._draw_colored_line(col_w * 2.5, row_h * 13.0, [
                    ("P)", self.get_color('hotkey')), (" 구매   ", "#ffffff"),
                    ("B)", self.get_color('hotkey')), (" 이전   ", "#ffffff"),
                    ("L)", self.get_color('hotkey')), (" 나가기", "#ffffff")
                ], font_ko)
                self._draw_colored_line(col_w * 2.5, row_h * 14.2, [
                    ("F)", self.get_color('hotkey')), (" 다음   ", "#ffffff"),
                    ("S)", self.get_color('hotkey')), (" 처음", "#ffffff")
                ], font_ko)

            # ------------------------------------------------
            # Scene: 볼탁 만물상점 메인 (Boltac's Trading Post)
            # ------------------------------------------------
            elif "상점" in scene or "Trading" in scene or "Boltac" in scene:
                self.canvas.create_rectangle(
                    col_w * 0.8, row_h * 2.55,
                    col_w * 39.2, row_h * 15.45,
                    fill="#000000", outline="#000000"
                )
                if self.shop_stage == 'buy':
                    # Keep the game's current item page and prices.  Translate
                    # only the fixed shopping controls, which do not depend on
                    # inventory or pagination.
                    self.canvas.create_text(
                        col_w * 20.0, row_h * 3.4,
                        text="볼탁 만물상점 - 구매",
                        fill="#ffffff", font=font_ko, anchor="center"
                    )
                    self.canvas.create_rectangle(
                        col_w * 0.9, row_h * 12.0,
                        col_w * 39.1, row_h * 15.2,
                        fill="#000000", outline=""
                    )
                    self._draw_colored_line(col_w * 2.0, row_h * 13.0, [
                        ("P)", self.get_color('hotkey')), (" 구매  ", "#ffffff"),
                        ("B)", self.get_color('hotkey')), (" 이전  ", "#ffffff"),
                        ("F)", self.get_color('hotkey')), (" 다음", "#ffffff")
                    ], font_ko)
                    self._draw_colored_line(col_w * 2.0, row_h * 14.1, [
                        ("S)", self.get_color('hotkey')), (" 처음  ", "#ffffff"),
                        ("L)", self.get_color('hotkey')), (" 나가기", "#ffffff")
                    ], font_ko)
                elif self.shop_stage in ('sell', 'uncurse', 'identify'):
                    labels = {
                        'sell': '판매할 아이템 번호는 (#)?',
                        'uncurse': '저주 해제할 아이템 번호는 (#)?',
                        'identify': '감정할 아이템 번호는 (#)?',
                    }
                    self.canvas.create_rectangle(
                        col_w * 13.4, row_h * 8.2,
                        col_w * 38.6, row_h * 12.8,
                        fill="#000000", outline=""
                    )
                    self.canvas.create_text(col_w * 26, row_h * 9.5,
                        text=labels[self.shop_stage], fill="#ffffff",
                        font=font_ko, anchor="center")
                    self.canvas.create_text(col_w * 26, row_h * 10.7,
                        text="↵ 나가기", fill="#ffffff",
                        font=font_ko, anchor="center")
                elif self.shop_stage != 'menu':
                    self.canvas.create_text(
                        col_w * 20.0, row_h * 3.4,
                        text="볼탁 만물상점에 오신 것을 환영합니다",
                        fill="#ffffff", font=font_ko, anchor="center"
                    )
                    self.canvas.create_text(
                        col_w * 20.0, row_h * 5.4,
                        text="누가 들어가겠습니까 (#)?",
                        fill="#ffffff", font=font_ko, anchor="center"
                    )
                    self._draw_colored_line(
                        col_w * 16.8, row_h * 6.4,
                        [("↵", self.get_color('hotkey')), (" 나가기", "#ffffff")],
                        font_ko
                    )
                else:
                    guest = None
                    if (
                        self.shop_party_index is not None
                        and self.shop_party_index < len(self.state.party)
                    ):
                        guest = self.state.party[self.shop_party_index]
                    guest_name = guest['name'] if guest else "모험가"
                    guest_gold = guest.get('gold', 0) if guest else 0
                    self.canvas.create_text(
                        col_w * 1.1, row_h * 3.4,
                        text=f"어서 오세요, {guest_name}.",
                        fill="#ffffff", font=font_ko, anchor="w"
                    )
                    self.canvas.create_text(
                        col_w * 1.1, row_h * 4.4,
                        text=f"보유 골드: {guest_gold} G.P.",
                        fill="#ffffff", font=font_ko, anchor="w"
                    )
                    shop_opts = [
                        ("B)", " 구매"),
                        ("S)", " 판매"),
                        ("U)", " 저주 해제"),
                        ("I)", " 감정"),
                        ("P)", " 골드 모으기"),
                        ("L)", " 나가기")
                    ]
                    for idx, (hk, desc) in enumerate(shop_opts):
                        self._draw_colored_line(
                            col_w * 1.1, row_h * (6.4 + idx),
                            [(hk, self.get_color('hotkey')), (desc, "#ffffff")],
                            font_ko
                        )

            # ------------------------------------------------
            # Scene: 모험가의 여관 (Adventurer's Inn)
            # ------------------------------------------------
            elif "여관" in scene or "Inn" in scene:
                # Stay inside the large original panel.  In particular, do not
                # erase its bottom edge or the narrow separator box below it.
                if self.inn_stage != 'need_experience':
                    self.canvas.create_rectangle(col_w * 0.8, row_h * 2.55, col_w * 39.2, row_h * 14.35, fill="#000000", outline="#000000")
                if self.inn_stage == 'napping':
                    guest = None
                    if (
                        self.inn_party_index is not None
                        and self.inn_party_index < len(self.state.party)
                    ):
                        guest = self.state.party[self.inn_party_index]
                    guest_name = guest['name'] if guest else "모험가"
                    self.canvas.create_text(
                        col_w * 20.0, row_h * 3.6,
                        text=f"{guest_name}는 낮잠을 자고 있습니다.",
                        fill="#ffffff", font=font_ko, anchor="center"
                    )
                elif self.inn_stage == 'need_experience':
                    # Keep the variable number supplied by the game in place;
                    # replace only the English words around it.
                    self.canvas.create_rectangle(
                        col_w * 0.8, row_h * 2.7,
                        col_w * 10.0, row_h * 4.0,
                        fill="#000000", outline=""
                    )
                    self.canvas.create_rectangle(
                        col_w * 14.4, row_h * 2.7,
                        col_w * 21.0, row_h * 4.0,
                        fill="#000000", outline=""
                    )
                    self.canvas.create_text(
                        col_w * 1.0, row_h * 3.4,
                        text="다음 레벨까지", fill="#ffffff",
                        font=font_ko, anchor="w"
                    )
                    self.canvas.create_text(
                        col_w * 14.5, row_h * 3.4,
                        text=" 더 필요", fill="#ffffff",
                        font=font_ko, anchor="w"
                    )
                    self.canvas.create_rectangle(
                        col_w * 0.8, row_h * 4.0,
                        col_w * 29.0, row_h * 5.2,
                        fill="#000000", outline=""
                    )
                    self.canvas.create_text(
                        col_w * 1.0, row_h * 4.4,
                        text="경험치가 필요합니다.", fill="#ffffff",
                        font=font_ko, anchor="w"
                    )
                    self.canvas.create_rectangle(
                        col_w * 14.4, row_h * 11.7,
                        col_w * 27.0, row_h * 13.2,
                        fill="#000000", outline=""
                    )
                    self._draw_colored_line(
                        col_w * 16.8, row_h * 12.4,
                        [("↵", self.get_color('hotkey')), (" 나가기", "#ffffff")],
                        font_ko
                    )
                elif self.inn_stage != 'room':
                    # ADVENTURER'S INN / WHO (#) WILL STAY? / TO LEAVE
                    self.canvas.create_text(col_w * 20.0, row_h * 3.4, text="모험가의 여관", fill="#ffffff", font=font_ko, anchor="center")
                    self.canvas.create_text(col_w * 20.0, row_h * 5.4, text="누가 묵겠습니까 (#)?", fill="#ffffff", font=font_ko, anchor="center")
                    self._draw_colored_line(
                        col_w * 16.8,
                        row_h * 6.4,
                        [("↵", self.get_color('hotkey')), (" 나가기", "#ffffff")],
                        font_ko
                    )
                else:
                    guest = None
                    if self.inn_party_index is not None and self.inn_party_index < len(self.state.party):
                        guest = self.state.party[self.inn_party_index]
                    guest_name = guest['name'] if guest else "모험가"
                    guest_gold = guest.get('gold', 0) if guest else 0
                    # WELCOME, <NAME>. WE HAVE:
                    self.canvas.create_text(col_w * 3.2, row_h * 3.4,
                        text=f"어서 오세요, {guest_name}. 객실을 선택하세요.",
                        fill="#ffffff", font=font_ko, anchor="w")
                    inn_rooms = [
                        ("A)", " 말구유", "무료"),
                        ("B)", " 간이침대", "주당 10 GP"),
                        ("C)", " 일반실", "주당 50 GP"),
                        ("D)", " 상인 스위트", "주당 200 GP"),
                        ("E)", " 로열 스위트", "주당 500 GP"),
                    ]
                    for idx, (hk, rname, price) in enumerate(inn_rooms):
                        cy = row_h * (5.4 + idx * 1.0)
                        self._draw_colored_line(
                            col_w * 3.2,
                            cy,
                            [(hk, self.get_color('hotkey')), (rname, "#ffffff"), (f"  {price}", self.get_color('subtext'))],
                            font_ko
                        )
                    self._draw_colored_line(
                        col_w * 3.2,
                        row_h * 11.4,
                        [("P)", self.get_color('hotkey')), (" 골드 모으기 또는 ", "#ffffff"), ("↵", self.get_color('hotkey')), (" 나가기", "#ffffff")],
                        font_ko
                    )
                    self.canvas.create_text(col_w * 1.1, row_h * 13.4,
                        text=f"보유 골드: {guest_gold} G.P.", fill="#ffffff",
                        font=font_ko, anchor="w")

            # ------------------------------------------------
            # Scene: 신규 캐릭터 작성 (Create Character)
            # ------------------------------------------------
            elif "작성" in scene or "Create Character" in scene:
                self.canvas.create_rectangle(col_w * 0.6, row_h * 3.0, col_w * 39.4, row_h * 15.5, fill="#000000", outline="#000000")
                self.canvas.create_text(col_w * 20.0, row_h * 4.3, text="신규 캐릭터 생성 단계", fill="#ffffff", font=font_ko, anchor="center")
                steps = [
                    ("1단계", "주사위 보너스 포인트 (7~29점) 확인 (18점 이상 엘리트직업 추천)"),
                    ("2단계", "캐릭터 이름 입력 (영문 대문자 최대 15자)"),
                    ("3단계", "종족 선택 (Human, Elf, Dwarf, Gnome, Hobbit)"),
                    ("4단계", "성향 선택 (Good, Neutral, Evil)"),
                    ("5단계", "6대 능력치 보너스 포인트 분배 (STR, IQ, PIE, VIT, AGI, LUC)"),
                    ("6단계", "최종 직업 선택 (전사, 마법사, 사제, 도적, 비숍, 사무라이, 로드, 닌자)")
                ]
                for idx, (st, desc) in enumerate(steps):
                    cy = row_h * (5.8 + idx * 1.1)
                    self._draw_colored_line(col_w * 3.0, cy, [
                        (f"[{st}] ", self.get_color('hotkey')),
                        (desc, "#ffffff")
                    ], font_small)

            # ------------------------------------------------
            # Scene: 칸트 사원 (Temple of Cant)
            # ------------------------------------------------
            elif "사원" in scene or "Temple" in scene:
                # Preserve the Temple panel and party list; replace its three
                # English prompt rows only.
                self.canvas.create_rectangle(
                    col_w * 2.3, row_h * 4.3,
                    col_w * 37.7, row_h * 8.9,
                    fill="#000000", outline="#000000"
                )
                self.canvas.create_text(
                    col_w * 20.0, row_h * 5.4,
                    text="칸트 사원에 오신 것을 환영합니다",
                    fill="#ffffff", font=font_ko, anchor="center"
                )
                self.canvas.create_text(
                    col_w * 20.0, row_h * 6.4,
                    text="누구를 도와드릴까요 (문자)?",
                    fill="#ffffff", font=font_ko, anchor="center"
                )
                self._draw_colored_line(
                    col_w * 16.8, row_h * 7.4,
                    [("↵", self.get_color('hotkey')), (" 나가기", "#ffffff")],
                    font_ko
                )

            # ------------------------------------------------
            # Scene: 훈련장 (Training Grounds)
            # ------------------------------------------------
            elif "훈련장" in scene or "Training" in scene:
                self.canvas.create_rectangle(col_w * 0.6, row_h * 3.0, col_w * 39.4, row_h * 14.5, fill="#000000", outline="#000000")
                self.canvas.create_text(col_w * 20.0, row_h * 4.8, text="훈련장", fill="#ffffff", font=font_ko, anchor="center")

                train_opts = [
                    ("C)", " 캐릭터 작성 (Create Character)"),
                    ("I)", " 캐릭터 점검 및 전직 (Inspect & Class Change)"),
                    ("R)", " 캐릭터 명단 (Roster of Characters)"),
                    ("D)", " 캐릭터 삭제 (Delete Character)"),
                    ("L / ↵)", " 훈련장 나가기")
                ]
                for idx, (hk, desc) in enumerate(train_opts):
                    cy = row_h * (6.8 + idx * 1.1)
                    self._draw_colored_line(col_w * 10.0, cy, [(hk, self.get_color('hotkey')), (desc, "#ffffff")], font_ko)

            # ------------------------------------------------
            # Scene: 마을 외곽 (Edge of Town)
            # ------------------------------------------------
            elif "외곽" in scene or "Edge" in scene:
                # Replace only the five English menu rows inside the original
                # popup.  Keep its border and do not add a title or menu item.
                self.canvas.create_rectangle(
                    col_w * 13.35, row_h * 4.25,
                    col_w * 26.65, row_h * 10.55,
                    fill="#000000", outline="#000000"
                )
                edge_opts = [
                    ("T)", " 훈련장", " (캐릭터 관리)"),
                    ("M)", " 미궁", " (탐험)"),
                    ("C)", " 성", " (상점·여관)"),
                    ("U)", " 유틸리티", " (디스크)"),
                    ("L)", " 게임 종료", "")
                ]
                for idx, (hk, name, desc) in enumerate(edge_opts):
                    cy = row_h * (5.4 + idx * 1.0)
                    self._draw_colored_line(
                        col_w * 14.0, cy,
                        [(hk, self.get_color('hotkey')), (name, "#ffffff"), (desc, self.get_color('subtext'))],
                        font_ko
                    )

            # ------------------------------------------------
            # Scene: 릴가민 성 본부 메뉴 (The Castle Root)
            # ------------------------------------------------
            else:
                self.canvas.create_rectangle(col_w * 7.4, row_h * 4.35, col_w * 32.6, row_h * 10.7, fill="#000000", outline="#000000")
                menus = [
                    ("G)", " 길가메시의 선술집", " (파티 편성/해산)"),
                    ("A)", " 모험가의 여관", " (휴식/마법 회복)"),
                    ("T)", " 칸트 사원", " (치료/부활 기도)"),
                    ("B)", " 볼탁 만물상점", " (장비 구매/판매/감정)"),
                    ("E)", " 마을 외곽", " (미궁 진입)")
                ]
                for idx, (hk, name, desc) in enumerate(menus):
                    cy = row_h * (5.2 + idx * 1.0)
                    self._draw_colored_line(col_w * 8.5, cy, [
                        (hk, self.get_color('hotkey')),
                        (name, "#ffffff"),
                        (desc, self.get_color('subtext'))
                    ], font_ko)

        # ====================================================
        # 2. Maze / Dungeon Exploration
        # ====================================================
        elif "미궁" in scene or "Maze" in scene:
            # 2a. Top menu bar interior:
            # Mask from row 0.95 to 2.80 to completely cover the top text (C)AMP S)TATUS...)
            # while leaving the bottom white line (row 3.58) completely untouched.
            self.canvas.create_rectangle(
                col_w * 0.8, row_h * 0.95,
                col_w * 39.2, row_h * 2.80,
                fill="#000000", outline=""
            )
            maze_menu_items = [
                ("C)", self.get_color('hotkey')), (" 캠프   ", "#ffffff"),
                ("S)", self.get_color('hotkey')), (" 상태창   ", "#ffffff"),
                ("I)", self.get_color('hotkey')), (" 조사   ", "#ffffff"),
                ("O)", self.get_color('hotkey')), (" UI 끄기   |   이동: ", "#ffffff"),
                ("[W]", self.get_color('hotkey')), ("전진 ", "#ffffff"),
                ("[A]", self.get_color('hotkey')), ("좌 ", "#ffffff"),
                ("[D]", self.get_color('hotkey')), ("우", "#ffffff")
            ]
            self._draw_colored_line(col_w * 1.2, row_h * 1.85, maze_menu_items, font_ko)

            # 2b. Center Stairs / Prompt Popup
            # Mask from row 10.75 to 13.60 to completely cover STAIRS UP and prompt
            # while strictly preserving top border (row 10.55) and bottom border (row 14.16).
            if self.stairs_stage:
                self.canvas.create_rectangle(
                    col_w * 10.5, row_h * 10.75,
                    col_w * 29.5, row_h * 13.60,
                    fill="#000000", outline=""
                )
                title_txt = "위층으로 통하는 사다리" if self.stairs_stage == 'up' else "아래층으로 통하는 사다리"
                self.canvas.create_text(
                    col_w * 20.0, row_h * 11.85,
                    text=title_txt, fill="#ffffff", font=font_ko, anchor="center"
                )
                self.canvas.create_text(
                    col_w * 20.0, row_h * 12.85,
                    text="사다리를 이용합니까 (Y/N)?", fill="#ffffff", font=font_ko, anchor="center"
                )





        # ====================================================
        # 3. Combat
        # ====================================================
        elif "전투" in scene or "Combat" in scene:
            self.canvas.create_rectangle(col_w * 0.6, 0, col_w * 39.4, row_h * 1.0, fill="#000000", outline="#000000")
            items = [
                ("F)", self.get_color('hotkey')), ("공격  ", "#ffffff"),
                ("P)", self.get_color('hotkey')), ("방어  ", "#ffffff"),
                ("S)", self.get_color('hotkey')), ("주문  ", "#ffffff"),
                ("U)", self.get_color('hotkey')), ("도구  ", "#ffffff"),
                ("R)", self.get_color('hotkey')), ("도주", "#ffffff")
            ]
            self._draw_colored_line(col_w * 2.0, row_h * 0.5, items, font_ko)

            if self.state.monsters:
                self.canvas.create_rectangle(col_w * 2.0, row_h * 2.0, col_w * 38.0, row_h * 6.5, fill="#000000", outline="#f38ba8")
                for idx, m in enumerate(self.state.monsters[:2]):
                    m_items = [
                        ("⚔️ ", self.get_color('status_bad')),
                        (f"[{m['ko']}]", self.get_color('hotkey')),
                        (f" (위험도: {m['danger']}) - ", self.get_color('status_bad')),
                        (m['desc'], "#ffffff")
                    ]
                    self._draw_colored_line(col_w * 3.0, row_h * (3.0 + idx * 1.8), m_items, font_ko)

        # ====================================================
        # 4. Treasure Chest
        # ====================================================
        elif "보물상자" in scene or "Chest" in scene:
            self.canvas.create_rectangle(col_w * 0.6, 0, col_w * 39.4, row_h * 2.2, fill="#000000", outline="#f9e2af")
            self.canvas.create_text(col_w * 20.0, row_h * 0.6, text="🎁 몬스터의 보물상자를 발견했습니다!", fill="#f9e2af", font=font_ko, anchor="center")
            chest_opts = [
                ("O)", self.get_color('hotkey')), (" 즉시개봉  ", "#ffffff"),
                ("I)", self.get_color('hotkey')), (" 함정조사(도적)  ", "#ffffff"),
                ("C)", self.get_color('hotkey')), (" 칼포주문(사제)  ", "#ffffff"),
                ("D)", self.get_color('hotkey')), (" 함정해제  ", "#ffffff"),
                ("L)", self.get_color('hotkey')), (" 상자포기", "#ffffff")
            ]
            self._draw_colored_line(col_w * 3.0, row_h * 1.5, chest_opts, font_ko)

        # ====================================================
        # 5. Camp (In Dungeon)
        # ====================================================
        elif "캠프" in scene or "Camp" in scene:
            # CAMP has its own title box and a compact centered command box.
            # Paint only the glyph interiors; the game's white frames remain.
            self.canvas.create_rectangle(
                # CAMP title frame interior.  Canvas coordinates start below
                # the DOSBox title bar, so the native title is on rows 0~3.
                # Keep the black fill inside the game's thick white frame.
                col_w * 17.4, row_h * 0.25,
                col_w * 22.6, row_h * 2.70,
                fill="#000000", outline=""
            )
            self.canvas.create_text(
                col_w * 20.0, row_h * 1.50,
                text="캠프", fill="#ffffff", font=font_ko, anchor="center"
            )
            self.canvas.create_rectangle(
                # Command frame interior only.  Cover every native glyph from
                # INSPECT through LEAVE, while retaining the surrounding line.
                col_w * 14.40, row_h * 4.30,
                col_w * 25.80, row_h * 9.65,
                fill="#000000", outline=""
            )
            camp_opts = (
                ("#)", " 상태 점검"),
                ("R)", " 대열 변경"),
                ("E)", " 장비 장착"),
                ("↵", " 나가기"),
            )
            for idx, (key, label) in enumerate(camp_opts):
                self._draw_colored_line(
                    col_w * 15.0, row_h * (5.40 + idx * 0.98),
                    [(key, self.get_color('hotkey')), (label, "#ffffff")],
                    font_ko
                )

        # ====================================================
        # 6. Utilities
        # ====================================================
        elif "유틸리티" in scene or "Utilities" in scene:
            self.canvas.create_rectangle(col_w * 0.6, row_h * 3.0, col_w * 39.4, row_h * 12.0, fill="#000000", outline="#000000")
            self.canvas.create_text(col_w * 20.0, row_h * 5.0, text="시스템 유틸리티", fill="#ffffff", font=font_ko, anchor="center")
            self.canvas.create_text(col_w * 20.0, row_h * 6.8, text="디스크 백업 및 시스템 설정 메뉴입니다.", fill="#ffffff", font=font_small, anchor="center")
            self._draw_colored_line(col_w * 13.0, row_h * 9.0, [
                ("L / ↵)", self.get_color('hotkey')), (" 외곽으로 나가기", "#ffffff")
            ], font_ko)

        # ====================================================
        # 7. Title Screen (Handled purely by dynamic CGA text extractor)
        # ====================================================
        elif "타이틀" in scene or "Title" in scene:
            pass

        # ====================================================
        # 8. Bottom Party Status Table (Always Row 16..24)
        #    (Hidden when inspecting character or creating character)
        # ====================================================
        is_inspect = any(k in scene for k in ["점검", "Inspect", "작성", "Create", "모험가 추가", "보물상자", "Chest", "유틸리티", "Utilities", "타이틀", "Title"])
        if (is_castle or self.state.party) and not is_inspect and not is_training:
            y_bottom = 24.8 if self.state.party else 18.0
            self.canvas.create_rectangle(col_w * 0.6, row_h * 16.2, col_w * 39.4, row_h * y_bottom, fill="#000000", outline="#000000")

            # 8a. Header Row (Row 17.5)
            hdr_y = row_h * 17.5
            self.canvas.create_text(col_w * 2.0, hdr_y, text="#", fill="#ffffff", font=font_mono, anchor="w")
            self.canvas.create_text(col_w * 4.0, hdr_y, text="캐릭터 이름", fill="#ffffff", font=font_ko, anchor="w")
            self.canvas.create_text(col_w * 19.0, hdr_y, text="직업", fill="#ffffff", font=font_ko, anchor="w")
            self.canvas.create_text(col_w * 25.5, hdr_y, text="AC", fill="#ffffff", font=font_mono, anchor="w")
            self.canvas.create_text(col_w * 29.0, hdr_y, text="체력", fill="#ffffff", font=font_ko, anchor="w")
            self.canvas.create_text(col_w * 34.0, hdr_y, text="상태", fill="#ffffff", font=font_ko, anchor="w")

            # 5b. Party Member Rows (Row 18.5 + i)
            for i in range(min(6, len(self.state.party))):
                p = self.state.party[i]
                row_y = row_h * (18.5 + i)

                align_letter = p['align'][0] if p['align'] else ""
                short_cls = SHORT_CLASS.get(p['class'], p['class'][:2])
                class_str = f"{align_letter}-{short_cls}" if align_letter else short_cls
                color_status = self.get_color('status_ok') if "정상" in p['status'] else self.get_color('status_bad')

                self.canvas.create_text(col_w * 2.0, row_y, text=str(i + 1), fill="#ffffff", font=font_mono, anchor="w")
                self.canvas.create_text(col_w * 4.0, row_y, text=p['name'], fill="#ffffff", font=font_mono, anchor="w")
                self.canvas.create_text(col_w * 19.0, row_y, text=class_str, fill="#ffffff", font=font_ko, anchor="w")
                self.canvas.create_text(col_w * 25.5, row_y, text=f"{p['ac']:>2d}", fill=self.get_color('ac'), font=font_mono, anchor="w")
                self.canvas.create_text(col_w * 29.0, row_y, text=f"{p['hp']:>2d}/{p['max_hp']:>2d}", fill=self.get_color('hp'), font=font_mono, anchor="w")
                self.canvas.create_text(col_w * 34.0, row_y, text=p['status'], fill=color_status, font=font_ko, anchor="w")

        # Dynamically scan and overlay any in-game prompts, messages, and words
        self._render_auto_cga_translations(w, h, font_ko)

    def _render_training_overlay(self, col_w, row_h, font_ko, font_mono, font_small):
        """Translate the active Training Grounds screen without inventing UI."""
        state1 = self.state.state1
        state2 = self.state.state2
        white = "#ffffff"
        hot = self.get_color('hotkey')
        pale = self.get_color('subtext')

        def clear(x1, y1, x2, y2):
            # Coordinates stay just inside the game's white frame.
            self.canvas.create_rectangle(
                col_w * x1, row_h * y1, col_w * x2, row_h * y2,
                fill="#000000", outline=""
            )

        def option(x, y, key, label, detail=""):
            parts = [(key, hot), (label, white)]
            if detail:
                parts.append((detail, pale))
            self._draw_colored_line(col_w * x, row_h * y, parts, font_ko)

        if self.training_action == 'delete_confirm':
            # Full-screen confirmation: replace only its single English row.
            clear(3.7, 11.8, 36.3, 14.0)
            self.canvas.create_text(
                col_w * 20, row_h * 12.9,
                text="정말 이 캐릭터를 삭제합니까 (Y/N)?",
                fill=white, font=font_ko, anchor="center"
            )
            return

        if state1 == 21048:
            clear(8.3, 8.2, 31.7, 13.65)
            for idx, (key, label) in enumerate((
                ("C)", " 캐릭터 생성"),
                ("I)", " 캐릭터 점검"),
                ("R)", " 캐릭터 명단"),
                ("↵", " 나가기"),
            )):
                option(9.1, 9.4 + idx, key, label)
            return

        if state1 == 21782:
            # (LETTER) SELECTS, ENTER TO LEAVE + the character roster.
            clear(11.2, 8.65, 28.7, 10.4)
            self.canvas.create_text(col_w * 20, row_h * 9.55,
                                    text="(문자) 선택,  ↵ 나가기",
                                    fill=white, font=font_ko, anchor="center")
            return

        if state1 == 21122 or self.training_action == 'selected':
            # This popup is narrower than the Training Grounds main popup.
            clear(11.2, 8.65, 28.7, 15.1)
            for idx, (key, label) in enumerate((
                ("I)", " 캐릭터 점검"),
                ("D)", " 캐릭터 삭제"),
                ("C)", " 직업 변경"),
                ("A)", " 암호 변경"),
                ("↵", " 나가기"),
            )):
                option(12.0, 9.65 + idx, key, label)
            return

        if state1 == 22178:
            # Keep the character sheet and item values, replacing its command rows.
            clear(.8, 21.2, 39.2, 24.6)
            option(1.2, 22.1, "R)", " 주문서 읽기")
            option(27.0, 22.1, "↵", " 나가기")
            return

        if state1 == 23166:
            clear(8.5, 11.7, 31.5, 15.2)
            option(9.2, 12.5, "M)", " 마법사 주문서")
            option(9.2, 13.5, "P)", " 사제 주문서")
            option(9.2, 14.5, "↵", " 나가기")
            return

        if state1 == 21154:
            clear(7.8, 8.0, 32.2, 12.8)
            self.canvas.create_text(col_w * 20, row_h * 9.4,
                                    text="변경 가능한 직업이 없습니다.",
                                    fill=white, font=font_ko, anchor="center")
            self.canvas.create_text(col_w * 20, row_h * 11.0,
                                    text="↵ 계속", fill=white,
                                    font=font_ko, anchor="center")
            return

        if state1 == 21082:
            clear(5.5, 7.7, 34.5, 11.2)
            prompt = "새 암호를 입력하세요:" if state2 == 53733 else "캐릭터 이름을 입력하세요:"
            self.canvas.create_text(col_w * 8.0, row_h * 9.0, text=prompt,
                                    fill=white, font=font_ko, anchor="w")
            return

        if state1 == 21126:
            clear(8.2, 7.8, 31.8, 14.2)
            races = (("A)", " 인간"), ("B)", " 엘프"), ("C)", " 드워프"),
                     ("D)", " 놈"), ("E)", " 호빗"))
            for idx, (key, label) in enumerate(races):
                option(9.0, 8.8 + idx, key, label)
            return

        if state1 == 21078:
            clear(9.0, 8.2, 31.0, 12.8)
            for idx, (key, label) in enumerate((
                ("A)", " 선"), ("B)", " 중립"), ("C)", " 악")
            )):
                option(10.0, 9.2 + idx, key, label)
            return

        if state1 == 21448 and state2 == 40838:
            clear(8.0, 18.5, 32.0, 22.2)
            self.canvas.create_text(col_w * 20, row_h * 20.0,
                                    text="이 캐릭터를 저장합니까 (Y/N)?",
                                    fill=white, font=font_ko, anchor="center")
            return

        if state1 == 21448:
            # Attribute values and the qualified-class list remain game-owned.
            clear(.8, 21.0, 39.2, 24.5)
            self.canvas.create_text(
                col_w * 20, row_h * 22.0,
                text="↵ 다음 능력치   + / - 점수 조절   Esc 완료",
                fill=white, font=font_small, anchor="center"
            )
            self.canvas.create_text(col_w * 20, row_h * 23.2,
                                    text="능력치 배분 후 직업을 선택하세요.",
                                    fill=pale, font=font_small, anchor="center")
            return

        if state1 == 20888:
            # Leave every roster entry untouched.  Only PRESS + the blinking
            # return glyph inside the game's small bottom box is translated.
            clear(15.7, 21.55, 21.25, 23.75)
            self.canvas.create_text(col_w * 18.45, row_h * 22.65,
                                    text="계속", fill=white,
                                    font=font_ko, anchor="center")

    def _draw_colored_line(self, x, y, items, font):
        cur_x = x
        for text, color in items:
            t_id = self.canvas.create_text(cur_x, y, text=text, fill=color, font=font, anchor="w")
            bbox = self.canvas.bbox(t_id)
            if bbox:
                cur_x = bbox[2]

    # ----------------------------------------------------
    # Sidecar Companion Window Rendering
    # ----------------------------------------------------
    def _render_companion(self):
        in_town = self._in_town()
        self._sync_roll_labels()
        for btn in (getattr(self, 'btn_heal', None), getattr(self, 'btn_revive', None), getattr(self, 'btn_identify', None)):
            if btn is not None:
                want = tk.NORMAL if in_town and (btn is not getattr(self, 'btn_identify', None) or self.state.game in (1, 2, 3, 5)) else tk.DISABLED
                if str(btn.cget('state')) != want:
                    btn.config(state=want)
        logs = self.state.stat_protection_logs
        stat_text = logs[-1] if logs else ""
        if stat_text:
            self.comp_stat_note.config(text=stat_text)
            if not self.comp_stat_note.winfo_ismapped():
                self.comp_stat_note.pack(fill=tk.X, after=self.btn_reset_map, pady=(2, 0))
        else:
            if self.comp_stat_note.winfo_ismapped():
                self.comp_stat_note.pack_forget()
        if self.hook.is_alive():
            game = self.state.game
            label = f"위저드리 {game}" if game else "게임 확인 중"
            self.comp_status.config(text=f"{label} · DOSBox 연결됨", fg="#a6e3a1")
        else:
            self.comp_status.config(text="DOSBox 연결 대기 중...", fg="#6c7086")

def main():
    root = tk.Tk()
    WizardryDualApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()

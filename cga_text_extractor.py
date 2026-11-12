"""
cga_text_extractor.py - High-Speed Automatic CGA Screen Text & Coordinate Extractor
Decodes 16KB DOSBox CGA Framebuffer into a complete 40x25 character grid in ~1ms.
Automatically detects WHICH WORD is rendered at WHICH POSITION (X, Y) without manual state mapping.
"""

import ctypes
import json
import os
import sys
import time
import re
import bisect
import hashlib
from functools import lru_cache

from wiz_build_flags import RELEASE


def _load_hashed(name):
    """{hashed key: Korean} from a shipped file next to the program, or {}."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    try:
        with open(os.path.join(base, name), encoding='utf-8') as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}



# The long keys of the code dictionaries below, hashed (see text_hash).
_HASHED_WIZ1 = _load_hashed('wiz1_hashed.json')

# Comprehensive Apple II / Wizardry CGA font glyph table (8x8 dot-matrix bitmaps)
FONT_GLYPHS = {
    # Uppercase Letters A-Z
    '101028287c44ee00': 'A',
    '7c22223c22227c00': 'B',
    '1824404040241800': 'C',
    '7824222222247800': 'D',
    '7e22203820227e00': 'E',
    '7e22203820207000': 'F',
    '3844808e84443800': 'G',
    'ee44447c4444ee00': 'H',
    '3810101010103800': 'I',
    '0e04040404241800': 'J',
    'e44850605048e400': 'K',
    '7020202020227e00': 'L',
    'c66c6c545444ee00': 'M',
    'ce646454544cec00': 'N',
    '3c42424242423c00': 'O',
    '7c22223c20207000': 'P',
    '3c4242424a443a00': 'Q',
    '7824243824246600': 'R',
    '3c42403c02423c00': 'S',
    'fe92101010103800': 'T',
    'ee44444444443800': 'U',
    'e642442428181000': 'V',
    'd654545428282800': 'W',
    # Letter X glyphs (36141c081c143600 is the authentic Wizardry 1 CGA dot-matrix glyph)
    '36141c081c143600': 'X',
    '3614080808143600': 'X',
    '3614181818143600': 'X',
    '3614180818143600': 'X',
    '24141c081c142400': 'X',
    '2414080808142400': 'X',
    '6c28381038286c00': 'X',
    '6c28101010286c00': 'X',
    '763c1c081c3c7600': 'X',
    'ee4428102844ee00': 'X',
    'ee44442810103800': 'Y',
    'ee44281010103800': 'Y',
    '3c24080810143c00': 'Z',

    # Bold / composite CGA rendering variants for letters
    '1018383c7e66fe00': 'A',
    '10183c3c7e66ee00': 'A',
    'fe6660786066fe00': 'E',
    '3818181818183c00': 'I',
    '3c62603c02633e00': 'S',
    'feda181818183800': 'T',
    'ee64646464643800': 'U',
    'e6c6cc6c78381000': 'V',

    # Numbers 0-9
    '1824242424241800': '0',
    '0818080808081c00': '1',
    '3844043840447c00': '2',
    '1824041804241800': '3',
    '081828487e080800': '4',
    '081028487c081c00': '4',
    '3c20380404241800': '5',
    '3c20380404043800': '5',
    '1824203824241800': '6',
    '3e04081020202000': '7',
    '7c44040810101000': '7',
    '7c44040808101000': '7',
    '7c44040810202000': '7',
    '7c44081010202000': '7',
    '7c44081020202000': '7',
    '7c44040818101000': '7',
    '7c44040810102000': '7',
    '7c44040808080800': '7',
    '3c24040810101000': '7',
    '3c24040808101000': '7',
    '3c24040810202000': '7',
    '3c24040808080800': '7',
    '3e2202040c080800': '7',
    '3e22020408080800': '7',
    '3e24040810101000': '7',
    '3e24040808101000': '7',
    '3e44040810101000': '7',
    '3e44040808101000': '7',
    '7e44040810101000': '7',
    '7e44040808101000': '7',
    '7e44081010202000': '7',
    '7e44040810202000': '7',
    '1824241824241800': '8',
    '1824241c04241800': '9',
    '1824241c04040400': '9',

    # Punctuation & Symbols
    '0000000000000000': ' ',
    '147e28fc50000000': '#',
    '062666fefc602000': '↵',  # Left-hook return arrow (↵)
    '0000000000001000': '.',  # Wizardry 1-dot period in I.Q., E.P., H.P., A.C.
    '0008081010202000': '/',  # Spell slot and HP fraction slash (0/0, 8/8)
    # Read from the game font 200.CHARSET on WIZ1.DSK (2026-11-02).
    '1c08080808483000': 'J',
    '103c503814781000': '$',
    '2c542808141a2400': '%',
    '3048306494887600': '&',
    '0010100010102000': ';',
    '384492aa9a4c3800': '@',
    '0010307c30100000': '←',
    '0010387c10100000': '↑',
    '0010187c18100000': '→',
    '0010107c38100000': '↓',
    # Item icons: font code x (potion) and y (scroll) in ASCII.KRN item names.
    '3c18346a566a3c00': 'Ⓟ',
    '78e46c2436271e00': 'Ⓢ',
    '0265949664140800': '~',  # Single-character 'of' ligature in GLOVESofCOPPER, POTIONofDIOS, etc.
    '0000007e00000000': '-',
    '0010107c10100000': '+',
    '0010543854100000': '*',
    '1008080808081000': ')',
    '0810101010100800': '(',
    '0008102010080000': '<',  # Stables price brackets: <FREE!>
    '0010080408100000': '>',
    # The on-screen chevron sits in columns 2-4, one column left of the
    # stables bracket above. Bit-reversing that bracket does not land here.
    '0020100810200000': '>',
    '2828000000000000': '"',
    '1010000000000000': "'",
    '0000000000181800': '.',
    '0018180000181800': ':',
    '00003c003c000000': '=',  # Equals sign between SPELLS and the slot counts, and in the teleport EAST =
    '0010100000101000': ':',  # Thin colon in sign text (A LARGE SIGN ON THE WALL READS:)
    '0000000000181808': ',',
    '0000000000180800': ',',  # Shorter comma in "(LETTER) SELECTS, ↵ TO LEAVE"
    '3844040810001000': '?',
    '3c42020c10001000': '?',  # Wider prompt question mark: EQUIP WHICH (#) ?
    '1010101010001000': '!',
    '0204081020408000': '/',
    '7c10101010107c00': '[',
    '7c08080808087c00': ']',
    '00007c007c000000': '=',
    # 00000000000000ff is the maze ceiling and a window edge. A font '_'
    # blanks that bar into the one-pixel mark, which reads as a row of dots.
    '1818000000000000': '`',
    '0000000018180000': '.',
}

# Window-frame cells are not text. scan_screen writes this instead of '?'.
FRAME_CHAR = '\u2502'

# Four CGA pixels packed in one byte, collapsed to 4 ink bits. scan_screen shifts
# two of these together to rebuild the 8-bit font row.
_PIX4 = tuple(
    (((v >> 6) & 3 != 0) << 3)
    | (((v >> 4) & 3 != 0) << 2)
    | (((v >> 2) & 3 != 0) << 1)
    | ((v & 3) != 0)
    for v in range(256)
)


def is_frame_glyph(raw):
    """True when every lit pixel lies on a straight box edge.

    Wizardry draws window borders as 8x8 cells: vertical bars, horizontal
    bars, and corners. An unrecognized letter has a short interior stroke
    those bars do not explain, so it stays unknown.
    """
    if len(raw) != 8:
        return False
    pixels = [[(byte >> (7 - x)) & 1 for x in range(8)] for byte in raw]
    explained = [[False] * 8 for _ in range(8)]
    for y in range(8):
        x = 0
        while x < 8:
            if not pixels[y][x]:
                x += 1
                continue
            x2 = x
            while x2 < 8 and pixels[y][x2]:
                x2 += 1
            if x == 0 or x2 == 8 or (x2 - x) >= 6:
                for i in range(x, x2):
                    explained[y][i] = True
            x = x2
    for x in range(8):
        y = 0
        while y < 8:
            if not pixels[y][x]:
                y += 1
                continue
            y2 = y
            while y2 < 8 and pixels[y2][x]:
                y2 += 1
            if y == 0 or y2 == 8 or (y2 - y) >= 6:
                for i in range(y, y2):
                    explained[i][x] = True
            y = y2
    lit = False
    for y in range(8):
        for x in range(8):
            if not pixels[y][x]:
                continue
            lit = True
            if not explained[y][x]:
                return False
    return lit


def _build_cell_offs():
    """Byte offset of each of the 8 rows in one 8x8 cell. Each row is 2 bytes."""
    table = []
    for row in range(25):
        half = row * 4 * 80
        row_offs = []
        for col in range(40):
            col_off = half + col * 2
            offs = []
            for half_i in range(4):
                even = col_off + half_i * 80
                offs.append(even)
                offs.append(even + 8192)
            row_offs.append(tuple(offs))
        table.append(tuple(row_offs))
    return tuple(table)


_CELL_OFFS = _build_cell_offs()
# A picture change this large is a new screen (castle to maze), not a cursor blink.
# Frame cells are excluded from the count. A border drawn a frame after the
# letters is not a new screen.
_SCENE_RESET_BYTES = 2048


def _cga_from_glyph_hex(hx):
    """Pack an 8-byte ink glyph as CGA pixels of color 3. Inverse of the decoder."""
    raw = bytes.fromhex(hx)
    out = bytearray(16)
    for i, bits in enumerate(raw):
        b0 = 0
        b1 = 0
        for k, shift in enumerate((6, 4, 2, 0)):
            if (bits >> (7 - k)) & 1:
                b0 |= 3 << shift
            if (bits >> (3 - k)) & 1:
                b1 |= 3 << shift
        out[i * 2] = b0
        out[i * 2 + 1] = b1
    return bytes(out)


# One interior pixel. A blank of all zeros is what the game writes when it
# erases a line, so a zero cannot mean "we hid this letter". This mark is not
# a frame and not a font glyph. The overlay covers it while the Korean is up.
_SENTINEL_INK = bytes((0, 0, 0x20, 0, 0, 0, 0, 0))
_SENTINEL_ACC = int.from_bytes(_SENTINEL_INK, 'big')
# Dark-zone fill: a one-pixel checkerboard. The game erases text there with
# this pattern instead of zeros, so it is a space, not an unknown glyph.
# The input cursor (a left-pointing triangle, read live in Wizardry 2) is no
# letter either: as an unknown shape it kept the letter backspace had deleted,
# and letters of an earlier input came back under it on an empty prompt.
_CURSOR_ACC = 0x0818387838180800
_FOG_ACC = frozenset((0xaa55aa55aa55aa55, 0x55aa55aa55aa55aa, _CURSOR_ACC))
_SENTINEL_CGA = _cga_from_glyph_hex(_SENTINEL_INK.hex())
SENTINEL_CHAR = '\uE000'


def _zero_cell(buf, row, col):
    dirty = False
    for off in _CELL_OFFS[row][col]:
        if buf[off] or buf[off + 1]:
            buf[off] = 0
            buf[off + 1] = 0
            dirty = True
    return dirty


def _cell_is_blank(buf, row, col):
    for off in _CELL_OFFS[row][col]:
        if buf[off] or buf[off + 1]:
            return False
    return True


def _cell_is_sentinel(buf, row, col):
    cga = _SENTINEL_CGA
    for i, off in enumerate(_CELL_OFFS[row][col]):
        if buf[off] != cga[i * 2] or buf[off + 1] != cga[i * 2 + 1]:
            return False
    return True


def _stamp_cell(buf, row, col):
    """Leave the blank mark. Returns True when the cell bytes change."""
    dirty = False
    cga = _SENTINEL_CGA
    for i, off in enumerate(_CELL_OFFS[row][col]):
        b0 = cga[i * 2]
        b1 = cga[i * 2 + 1]
        if buf[off] != b0 or buf[off + 1] != b1:
            buf[off] = b0
            buf[off + 1] = b1
            dirty = True
    return dirty


def _held_blank(ch):
    """No new game ink: a space the game wrote, or a cell we already marked."""
    return ch == ' ' or ch == SENTINEL_CHAR


def _word_spans(chars):
    """Runs of remembered letters. A space separates the label from the number."""
    spans = []
    start = None
    for c, ch in enumerate(chars):
        if ch != ' ':
            if start is None:
                start = c
        elif start is not None:
            spans.append((start, c))
            start = None
    if start is not None:
        spans.append((start, len(chars)))
    return spans


def _rewritten_word_cells(old_chars, live_row, new_cols):
    """Cells of a word the game replaced.

    One changed digit stays inside its own word. The label beside it is a
    different word and is not returned.
    """
    hit = {c for c in new_cols if old_chars[c] not in (' ', live_row[c])}
    if not hit:
        return set()
    drop = set()
    for a, b in _word_spans(old_chars):
        word_hit = [c for c in range(a, b) if c in hit]
        if not word_hit:
            continue
        stable = 0
        for c in range(a, b):
            if c in hit:
                continue
            if _held_blank(live_row[c]) or live_row[c] == old_chars[c]:
                stable += 1
        if len(word_hit) >= stable:
            drop.update(range(a, b))
    return drop


def _paint_cell(buf, row, col, cga16):
    for i, off in enumerate(_CELL_OFFS[row][col]):
        buf[off] = cga16[i * 2]
        buf[off + 1] = cga16[i * 2 + 1]


def _is_text_char(ch, col, real_q):
    """Known letters, digits, punctuation, and a genuine '?'. Frames and unknown '?' are not text."""
    if ch == ' ' or ch == FRAME_CHAR or ch == SENTINEL_CHAR:
        return False
    if ch == '?' and col not in real_q:
        return False
    return True


def _byte_diff(a, b, limit):
    n = 0
    for i in range(0, len(a), 128):
        chunk_a = a[i:i + 128]
        chunk_b = b[i:i + 128]
        if chunk_a == chunk_b:
            continue
        for x, y in zip(chunk_a, chunk_b):
            if x != y:
                n += 1
                if n >= limit:
                    return n
    return n


# Built-in core translations for UI, Stats, and Menus
KRN_ITEM_TRANSLATIONS = {
    # Identified names whose screen spelling the JSON keys do not produce.
    "HELM+2 (E)": "투구+2(악)", "CHAIN+2 (E)": "사슬 갑옷+2(악)", "PLATE+2 (N)": "판금 갑옷+2(중립)",
    "SHIELD+3 (E)": "방패+3(악)", "SWORD+3 (E)": "검+3(악)", "S-SWORD+3 (E)": "쇼트 소드+3(악)",
    "PLATE+3 (E)": "판금 갑옷+3(악)", "BLADE CUSINART'": "블레이드 커시너트", "MURAMASA BLADE!": "무라마사 블레이드!",
    "PRIESTS RING": "사제의 반지", "RING~DEATH!": "죽음의 반지!", "LEATHER-2": "가죽 갑옷-2", "CHAIN-2": "사슬 갑옷-2",
}

KRN_TEXT_TRANSLATIONS = {
    # Game text from ASCII.KRN (docs/wiz1_text.txt). Existing keys win.
    "SEARCHING.": "수색 중.",
    "PARTY POSITION:": "파티 위치:",
    "FACING NORTH.": "북쪽을 향함.", "FACING EAST.": "동쪽을 향함.",
    "FACING SOUTH.": "남쪽을 향함.", "FACING WEST.": "서쪽을 향함.",
    "GOT AN ITEM.": "아이템을 얻었다.",
    "TRADED AN ITEM!": "아이템을 건넸다!",
    "NOT WITHOUT PAYMENT!": "대가 없이는 안 된다!",
    "WRONG!": "틀렸다!",
    "CORRECT!": "정답이다!",
    "THE FEE IS": "요금은",
    "WILL YOU PAY": "지불하겠습니까",
    "PARTY TELEPORT:": "파티 순간이동:",
    "EAST =": "동 =", "NORTH =": "북 =", "UP =": "위 =",
    "E)AST": "E) 동", "W)EST": "W) 서", "N)ORTH": "N) 북", "S)OUTH": "S) 남",
    "U)P": "U) 위", "D)OWN": "D) 아래", "T)ELEPORT": "T) 순간이동", "Q)UIT": "Q) 그만",
    "POWER OF YOUR": "아이템:",
    "SELECT GAUNTLETS": "장갑 선택",
    "SELECT MISC. ITEM": "기타 아이템 선택",
    "* CURSED *": "* 저주받음 *",
    "(A)-(H) CHANGES,": "(A)-(H) 변경,",
    "YOUR PASSWORD": "암호가",
    "PASSWORD >": "암호 >",
    "A)LTER PASSWORD": "A) 암호 변경",
    "* OUT *": "* 미궁에 있음 *",
    "IS RECUPERATING.": "회복 중입니다.",
    "CHANT -": "영창 -", "PRAY -": "기도 -", "INVOKE!": "발동!",
    "PERHAPS ANOTHER ?": "다른 것도 보시겠습니까 ?",
    "FIZZLE!": "불발!",
    "OOPS": "이런",
    "NOT DEAD": "죽지 않았음",
    "TRY KADORTO": "카도르토를 쓰시오",
    "WHAT ?": "무엇을 ?",
    "DONE!": "완료!",
    "POWERLESS": "효력 없음",
    "NOT EQUIPPED": "장착 안 함",
    "CURSED": "저주받음",
    "EQUIPPED": "장착함",
    "DROPPED": "버렸음",
    "BAD AMOUNT": "잘못된 금액",
    "TOO MUCH": "너무 많음",
    "IT'S DARK": "어둡다",
    "OUCH!!": "아야!!",
    "A CHUTE!": "미끄럼틀이다!",
    "DELAY (1-99) >": "지연 (1-99) >",
    "HAS DIED!": "죽었다!",
    "IS SLAIN!": "살해당했다!",
    "FOUND :": "의 판단:",
    "O)PEN": "O) 열기", "C)ALFO": "C) 칼포", "D)ISARM": "D) 해제", "L)EAVE ALONE": "L) 내버려 두기",
    "ALIVE!": "살아 있다!",
    "LOCATE A BODY": "시체 찾기",
    "FIND WHOM ?": "누구를 찾습니까 ?",
    "WAS DRAINED!": "레벨을 빼앗겼다!",
    "SPELL POINTS EXHAUSTED": "주문 횟수 소진",
    "CURE PARTY": "파티 치료",
    "SILENCE ENEMIES": "적 침묵",
    "AUGUMENT MAGIC": "마법 강화",
    "TELEPORT ENEMIES": "적 순간이동",
    "HEAL PARTY": "파티 회복",
    "PROTECT PARTY": "파티 보호",
    "RAISE THE DEAD!": "죽은 자 소생!",
    "IS DECAPITATED!": "목이 잘렸다!",
    "IS HELD": "움직임이 묶였다", "IS NOT HELD": "묶이지 않았다",
    "IS SILENCED": "침묵당했다", "IS NOT SILENCED": "침묵당하지 않았다",
    "IS SLAIN": "살해당했다", "IS NOT SLAIN": "살아남았다",
    "IS SLEPT": "잠들었다", "IS NOT SLEPT": "잠들지 않았다",
    "IS DECAPITATED": "목이 잘렸다",
    "NOTHING HAPPENS": "아무 일도 일어나지 않는다",
    "IS CURED": "치료되었다",
    "IS NOT CURED": "치료되지 않았다",
    "BUT CANNOT SPEAK!": "- 말을 할 수 없다!",
    "BUT NOTHING HAPPENS!": "- 아무 일도 없다!",
    "NEW NAME": "새 이름",
    "NAME CHANGED": "이름을 바꿨습니다",
    "WAS NOT MOVED": "옮기지 못했습니다",
    "HAS BEEN MOVED": "옮겼습니다",
    "HAS BEEN RESTORED": "복구했습니다",
    "NO SPELL": "주문 없음",
    "PETRIFIED": "석화",
    # Maze messages that fit on one row.
    "\"A DUNGEON'S DARK...\"": "\"미궁은 어둡지...\"",
    "\"TURN LEFT.\"": "\"왼쪽으로 돌아라.\"",
    "\"TURN RIGHT.\"": "\"오른쪽으로 돌아라.\"",
    "\"TURN AROUND.\"": "\"뒤로 돌아라.\"",
    "AUTHORIZED PERSONNEL ONLY!": "관계자 외 출입 금지!",
    "\"TREASURE REPOSITORY.\"": "\"보물 보관소.\"",
    "\"MONSTER ALLOCATION CENTER\"": "\"몬스터 배치 센터\"",
    "AUTHORIZED USERS ONLY!": "허가된 사용자 전용!",
    "\"CONTRA-DEXTRA AVENUE\"": "\"콘트라-덱스트라 거리\"",
    "BY APPOINTMENT ONLY": "예약자만 받음",
}
KRN_TEXT_TRANSLATIONS.update(_HASHED_WIZ1.get('KRN_TEXT', {}))

DEFAULT_UI_TRANSLATIONS = {
    # Title Screen & Boot Loader
    "WORLD  OF WIZARDRY!": "위저드리의 세계!",
    "WORLD OF WIZARDRY!": "위저드리의 세계!",
    "WORLD ~ WIZARDRY!": "위저드리의 세계!",
    "WORLD~WIZARDRY!": "위저드리의 세계!",
    "WORLD  OF WIZARDRY": "위저드리의 세계",
    "WORLD OF WIZARDRY": "위저드리의 세계",
    "WORLD ~ WIZARDRY": "위저드리의 세계",
    "WORLD~WIZARDRY": "위저드리의 세계",
    "SCENARIO DISK!": "게임을 진행할 수 없습니다!",
    "SCENARIO DISK": "시나리오 디스크",
    "MASTER DISK": "마스터 디스크",
    "S)TART GAME": "S) 게임 시작",
    "M)AKE SCENARIO DISK": "M) 시나리오 디스크 생성",
    "START GAME": "게임 시작",
    "MAKE SCENARIO DISK": "시나리오 디스크 생성",
    "INSERT SCENARIO DISK": "시나리오 디스크를 삽입하세요",
    "INSERT MASTER DISK": "마스터 디스크를 삽입하세요",
    # Castle Main Hub
    "THE CASTLE": "릴가민 성",
    "CASTLE": "릴가민 성",
    "G)ILGAMESH'S TAVERN": "G) 길가메시 선술집",
    "G) ILGAMESH'S TAVERN": "G) 길가메시 선술집",
    "GILGAMESH'S TAVERN": "길가메시 선술집",
    "B)OLTAC'S TRADING POST": "B) 볼탁 만물상점",
    "BOLTAC'S TRADING POST": "볼탁 만물상점",
    "A)DVENTURER'S INN": "A) 모험가의 여관",
    "A) DVENTURER'S INN": "A) 모험가의 여관",
    "ADVENTURER'S INN": "모험가의 여관",
    "T)EMPLE OF CANT": "T) 칸트 사원",
    "TEMPLE OF CANT": "칸트 사원",
    "E)DGE OF TOWN": "E) 마을 외곽",
    "EDGE OF TOWN": "마을 외곽",
    # Gilgamesh's Tavern
    "A)DD": "A) 영입",
    "A) DD": "A) 영입",
    "R)EMOVE": "R) 제외",
    "R) EMOVE": "R) 제외",
    "#)INSPECT": "#) 점검",
    "#) INSPECT": "#) 점검",
    "D)IVVY GOLD": "D) 골드 분배",
    "D) IVVY GOLD": "D) 골드 분배",
    "DIVVY GOLD": "골드 분배",
    "L↵EAVE": "↵ 나가기",
    "L↵ EAVE": "↵ 나가기",
    "↵EAVE": "↵ 나가기",
    "L)EAVE": "L) 나가기",
    "L) EAVE": "L) 나가기",
    # Edge of Town
    "M)AZE": "M) 미궁 진입",
    "M) AZE": "M) 미궁 진입",
    "C)ASTLE": "C) 성으로 귀환",
    "C) ASTLE": "C) 성으로 귀환",
    "U)TILITIES": "U) 유틸리티",
    "U) TILITIES": "U) 유틸리티",
    "T)RAINING GROUNDS": "T) 훈련장",
    "T) RAINING GROUNDS": "T) 훈련장",
    "TRAINING GROUNDS": "훈련장",
    "T)RAINING": "T) 훈련장",
    "T) RAINING": "T) 훈련장",
    "TRAINING": "훈련장",
    "RAINING": "훈련장",
    "T) RAIN": "T) 훈련장",
    "T)RAIN": "T) 훈련장",
    # Training Grounds
    "C)REATE A CHARACTER": "C) 캐릭터 생성",
    "CREATE A CHARACTER": "캐릭터 생성",
    "I)NSPECT": "I) 캐릭터 점검",
    "I) NSPECT": "I) 캐릭터 점검",
    "R)OSTER OF CHARACTERS": "R) 캐릭터 명부",
    "ROSTER OF CHARACTERS": "캐릭터 명부",
    "D)ELETE A CHARACTER": "D) 캐릭터 삭제",
    "DELETE A CHARACTER": "캐릭터 삭제",
    "CHANGE CLASS": "전직",
    # Boltac's Trading Post
    "WELCOME TO BOLTAC'S": "볼탁 상점에 오신 것을 환영합니다",
    "WELCOME TO": "환영합니다 -",
    "WELCOME, ": "환영합니다, ",
    "WELCOME,": "환영합니다, ",
    "YOU HAVE ": "소지금: ",
    "YOU HAVE": "소지금: ",
    "GP LEFT": "GP 남음",
    "P)URCHASE": "P) 구매",
    "P) URCHASE": "P) 구매",
    "PURCHASE": "구매",
    "B)ACKWARD": "B) 이전",
    "B) ACKWARD": "B) 이전",
    "BACKWARD": "이전",
    "F)ORWARD": "F) 다음",
    "F) ORWARD": "F) 다음",
    "FORWARD": "다음",
    "S)TART": "S) 처음",
    "S) TART": "S) 처음",
    "P)OOL GOLD": "P) 골드 몰아주기",
    "P) OOL GOLD": "P) 골드 몰아주기",
    "POOL GOLD": "골드 몰아주기",
    "B)UY": "B) 구매",
    "B) UY": "B) 구매",
    "S)ELL": "S) 판매",
    "S) ELL": "S) 판매",
    "I)DENTIFY": "I) 감정",
    "I) IDENTIFY": "I) 감정",
    "U)NCURSE": "U) 저주 해제",
    "U) NCURSE": "U) 저주 해제",
    "SELL WHICH (#)": "판매할 아이템 번호 (#)",
    "SELL WHICH": "판매할 아이템 번호",
    "UNCURSE WHICH (#)": "저주 풀 아이템 번호 (#)",
    "UNCURSE WHICH": "저주 풀 아이템 번호",
    # Adventurer's Inn
    "A) THE STABLES": "A) 말구유 (무료)",
    "THE STABLES": "말구유 (무료)",
    "B) A COT": "B) 간이침대 (10 GP)",
    "COT": "간이침대",
    "C) ECONOMY ROOMS": "C) 일반실 (50 GP/주)",
    "ECONOMY ROOMS": "일반실 (50 GP)",
    "D) MERCHANT SUITES": "D) 상인실 (200 GP/주)",
    "MERCHANT SUITE": "상인실 (200 GP)",
    "THE ROYAL SUITE": "로열 스위트 (1000 GP)",
    "WE HAVE ROOMS": "방이 있습니다",
    "WE HAVE": "방이 있습니다",
    # Prompts, Popups & Commands
    "SELECT WEAPON": "무기 선택",
    "SELECT ARMOR": "방어구 선택",
    "SELECT SHIELD": "방패 선택",
    "SELECT HELM": "투구 선택",
    "SELECT GLOVES": "장갑 선택",
    "SELECT ITEM": "아이템 선택",
    "EQUIP WHICH": "장착 번호",
    "DROP WHICH": "버릴 번호",
    "IDENTIFY WHICH": "감정 번호",
    "TRADE WHICH": "건넬 번호",
    ") FOR NONE": "↵ 장착하지 않음",
    "FOR NONE": "장착하지 않음",
    "↵ FOR NONE": "↵ 장착하지 않음",
    "ENTER FOR NONE": "장착하지 않음",
    "WHO WILL ENTER": "누가 입장하시겠습니까?",
    "WHO WILL STAY": "누가 숙박하시겠습니까?",
    "F)IGHT OR L)EAVE": "F) 공격 또는 L) 나가기",
    "L)EAVE ?": "L) 나가기 ?",
    "L) EAVE ?": "L) 나가기 ?",
    ") TO LEAVE": "↵ 나가기",
    "↵ TO LEAVE": "↵ 나가기",
    "ENTER TO LEAVE": "↵ 나가기",
    ") TO": "↵",
    "PRESS ↵": "↵ 누르기",
    "PRESS )": "↵ 누르기",
    "WHO WILL INSPECT": "누구를 점검하시겠습니까?",
    "WHO WILL OPEN": "누가 상자를 열겠습니까?",
    "WHO WILL DISARM": "누가 함정을 해제하겠습니까?",
    "WHO WILL TRADE": "누구에게 건네주시겠습니까?",
    "WHO WILL IDENTIFY": "누가 감정하시겠습니까?",
    "WHO WILL READ": "누가 읽으시겠습니까?",
    "WHO WILL DROP": "누가 버리시겠습니까?",
    "WHO WILL CAST": "누가 시전하시겠습니까?",
    "WHO WILL DISPEL": "누가 퇴치하시겠습니까?",
    "REMOVE WHO (#)": "제외할 파티원 번호 (#)",
    "REMOVE WHO": "제외할 파티원",
    "TRADE WITH WHOM": "건넬 파티원",
    "WITH WHOM (#)": "누구와 (#)",
    "WITH WHOM": "누구와",
    "WHO (#) ?": "누구 (#) ?",
    "TRADE GOLD (AMT)": "건넬 금액 (골드)",
    "TRADE GOLD": "골드 건네기",
    "(AMT) ?": "(골드 금액) ?",
    "(AMT)": "(골드 금액)",
    "IDENTIFY WHAT ?": "감정할 아이템 번호 ?",
    "IDENTIFY WHAT": "감정할 아이템 번호",
    "YOU IDENTIFIED IT!": "아이템 감정에 성공했습니다!",
    "YOU IDENTIFIED IT": "아이템 감정에 성공했습니다!",
    "M)AGE SPELL BOOKS": "M) 마법사 주문서",
    "P)RIEST SPELL BOOKS": "P) 사제 주문서",
    "MAGE SPELLS": "마법사 주문",
    "PRIEST SPELLS": "사제 주문",
    "E)QUIP": "E) 장착",
    "E) QUIP": "E) 장착",
    "EQUIP": "장착",
    # Unidentified items (shown with a leading '?')
    # Unidentified item names: ASCII.KRN 14000-14201, even numbers (docs/wiz1_text.txt).
    # Ⓟ/Ⓢ are the potion/scroll icon glyphs (font codes x/y).
    "?SWORD": "?검", "?STAFF": "?지팡이", "?DAGGER": "?단검", "?SHIELD": "?방패",
    "?CLOTHING": "?옷", "?ARMOR": "?갑옷", "?HELM": "?투구", "?Ⓟ": "?물약", "?Ⓢ": "?두루마리",
    "?AMULET": "?부적", "?GLOVES": "?장갑", "?RING": "?반지", "?ROD": "?막대",
    "?CHAIN": "?사슬 갑옷", "?STARS": "?별", "?STATUE": "?조각상", "?KEY": "?열쇠", "?RIBBON": "?리본",
    "D)ROP": "D) 버리기",
    "D) ROP": "D) 버리기",
    "DROP": "버리기",
    "T)RADE": "T) 건네기",
    "T) RADE": "T) 건네기",
    "TRADE": "건네기",
    "R)EAD": "R) 읽기",
    "R) EAD": "R) 읽기",
    "INSPECT": "점검",
    "REMOVE": "제외",
    "LEAVE": "나가기",
    "STAIRS UP": "위층 계단",
    "STAIRS DOWN": "아래층 계단",
    "CAMP": "캠프",
    "F↵IGHT": "F/↵ 공격",
    "F↵ IGHT": "F/↵ 공격",
    "↵IGHT": "↵ 공격",
    "F)IGHT": "F) 공격",
    "F) IGHT": "F) 공격",
    "P↵ARRY": "↵ 방어",
    "P↵ ARRY": "↵ 방어",
    "↵ARRY": "↵ 방어",
    "P)ARRY": "↵ 방어",
    "P) ARRY": "↵ 방어",
    "C)AST": "C) 주문",
    "C) AST": "C) 주문",
    "R)UN": "R) 도주",
    "R) UN": "R) 도주",
    "D)ISPEL": "D) 퇴치",
    "D)ISPELL": "D) 퇴치",
    "U)SE ITEM": "U) 도구",
    "U)SE IT": "U) 도구",
    "U) SE IT": "U) 도구",
    "USE ITEM": "도구",
    "USE IT": "도구",
    "U)SE": "U) 사용",
    "S)PELL": "S) 주문",
    "S) PELL": "S) 주문",
    "T)AKE BACK ORDERS": "T) 명령 취소",
    "T)AKE BACK": "T) 이전 취소",
    "T)AKE": "T) 취소",
    "T) AKE BACK": "T) 이전 취소",
    "T) AKE": "T) 취소",
    ")AKE BACK": ") 이전 취소",
    "AKE BACK": "이전 취소",
    "WHICH GROUP (#)": "공격할 몬스터 그룹 (#)",
    "FIGHT": "공격",
    "PARRY": "방어",
    "RUN": "도주",
    "CAST": "주문",
    "DISPEL": "퇴치",
    # Combat Class Options & Prompts
    "'S OPTIONS ?": "의 행동 선택 ?",
    "'S OPTIONS": "의 행동 선택",
    " OPTIONS ?": " 행동 선택 ?",
    " OPTIONS": " 행동 선택",
    # Combat Battle Logs & Monster Encounters
    "ATTEMPTS TO SLICE": "베기를 시도합니다",
    "THRUSTS VIOLENTLY AT": "맹렬히 찌르기 ->",
    "TRIES TO STAB": "찌르기 시도 ->",
    "CHARGES AT A": "돌격 ->",
    "CHARGES AT": "돌격 ->",
    "LEAPS AT A": "도약 공격 ->",
    "LEAPS AT": "도약 공격 ->",
    "ATTEMPTS TO CHEW": "씹어삼키기 시도 ->",
    "TRIES TO GNAW": "물어뜯기 시도 ->",
    "BITES AT": "물어뜯기 ->",
    "CLAWS AT": "할퀴기 ->",
    "RUNS AWAY": "도망쳤습니다!",
    "THE SLIME": "슬라임",
    "IS KILLED!": "쓰러졌다!",
    "ARE KILLED!": "쓰러졌다!",
    "IS DEAD!": "사망했다!",
    "ARE DEAD!": "사망했다!",
    "FOR 1 DAMAGE": "1 피해",
    "FOR 2 DAMAGE": "2 피해",
    "FOR 3 DAMAGE": "3 피해",
    "FOR 4 DAMAGE": "4 피해",
    "FOR 5 DAMAGE": "5 피해",
    "FOR 6 DAMAGE": "6 피해",
    "FOR 7 DAMAGE": "7 피해",
    "FOR 8 DAMAGE": "8 피해",
    "FOR 9 DAMAGE": "9 피해",
    "FOR 10 DAMAGE": "10 피해",
    "FOR 1": "1 피해",
    "FOR 2": "2 피해",
    "FOR 3": "3 피해",
    "FOR 4": "4 피해",
    "FOR 5": "5 피해",
    "FOR 6": "6 피해",
    "FOR 7": "7 피해",
    "FOR 8": "8 피해",
    "FOR 9": "9 피해",
    "FOR 10": "10 피해",
    "ONCE FOR": "1회 명중:",
    "TIMES FOR": "회 명중:",
    "AND HITS ONCE": "1회 명중",
    "HITS ONCE FOR": "1회 명중:",
    "HITS ONCE": "1회 명중",
    "AND HITS": "명중!",
    "AND MISSES ?": "빗나갔다!",
    "AND MISSES": "빗나갔다!",
    "MISSES": "빗나감!",
    "AN ENCOUNTER!": "적과 조우!",
    "AN ENCOUNTER": "적과 조우!",
    "DAMAGE": "피해",
    "EACH SURVIVOR GETS": "생존자 각자 획득:",
    "G.P.": "골드",
    "TO FIGHT": "전투",
    "CAST WHAT SPELL": "시전할 주문 이름 ?",
    "WHAT SPELL ?": "시전할 주문 ?",
    "WHAT SPELL": "시전할 주문",
    "ON WHOM (#)": "누구에게 (#)",
    "ON WHOM ?": "누구에게 ?",
    "ON WHOM": "누구에게",
    "UNDEAD KOBOLDS": "언데드 코볼트",
    "UNDEAD KOBOLD": "언데드 코볼트",
    "SKELETONS": "스켈레톤",
    "SKELETON": "스켈레톤",
    "SLIMES": "슬라임",
    "SLIME": "슬라임",
    "ZOMBIES": "좀비",
    "ZOMBIE": "좀비",
    "KOBOLDS": "코볼트",
    "KOBOLD": "코볼트",
    "ORCS": "오크",
    "ORC": "오크",
    "SMALL HUMANOIDS": "작은 인간형",
    "SMALL HUMANOID": "작은 인간형",
    "MEN IN ROBES": "로브를 입은 무리",
    "MAN IN ROBES": "로브를 입은 자",
    "ANIMALS": "동물 무리",
    "ANIMAL": "동물",
    "FRIENDLY GROUP OF": "우호적인 무리:",
    # Treasure Chest & Investigation
    "A CHEST!": "상자 발견!",
    "TRAPLESS CHEST": "함정 없는 상자",
    "TAKE THEM (Y/N)": "이용하시겠습니까 (Y/N)",
    "TAKE THEM": "이용하시겠습니까",
    "TAKE IT (Y/N)": "이용하시겠습니까 (Y/N)",
    "TAKE IT": "이용하시겠습니까",
    "L)EAVE ALONE": "L) 상자 포기",
    "LEAVE ALONE": "상자 포기",
    "I)NSPECT D)ISARM": "I) 함정 확인  D) 함정 해제",
    "TRAP (↵ EXITS)": "함정 명칭 입력 (↵ 나가기)",
    "TRAP (↵": "함정 (↵ 나가기)",
    "OOPS!": "이런!",
    "POISON NEEDLE": "독침 (POISON NEEDLE)",
    "GAS BOMB": "가스 폭탄 (GAS BOMB)",
    "CROSSBOW BOLT": "쇠뇌 화살 (CROSSBOW BOLT)",
    "EXPLODING BOX": "폭발 상자 (EXPLODING BOX)",
    "STUNNER": "기절 함정 (STUNNER)",
    "TELEPORTER": "순간이동 함정 (TELEPORTER)",
    "MAGE BLASTER": "마법사 폭탄 (MAGE BLASTER)",
    "PRIEST BLASTER": "사제 폭탄 (PRIEST BLASTER)",
    "ALARM": "경보 (ALARM)",
    "COULD NOT DISARM": "함정을 해제하지 못했습니다",
    "YOU MAY?": "선택 가능:",
    "YOU MAY": "선택 가능:",
    "SELECT": "선택",
    "STABLES": "말구유",
    # Status, Camp & Commands
    "DROP ITEM (#)": "버릴 아이템 번호 (#)",
    "DROP ITEM": "버릴 아이템 번호",
    "ITEM (#) ?": "아이템 번호 (#) ?",
    "ITEM (#)": "아이템 번호 (#)",
    "EQUIP WHICH (#)": "장착할 아이템 번호 (#)",
    "IP WHICH (#)": "장착할 아이템 번호 (#)",
    "O)FF": "O) UI 끄기",
    "O) FF": "O) UI 끄기",
    "R)EAD": "R) 주문서",
    "R) EAD": "R) 주문서",
    "T)RADE": "T) 건네기",
    "T) RADE": "T) 건네기",
    "P)OOL GOLD": "P) 골드 모으기",
    "P)OOL G": "P) 골드 모으기",
    "P)OOL": "P) 골드 모으기",
    ", OR": ", 또는",
    "? OR": ", 또는",
    "OR": "또는",
    "USELESS": "사용 불가",
    "IS NAPPING.": "휴식 중입니다.",
    "IS NAPPING": "휴식 중",
    "SPELL BOOKS": "주문서 목록",
    "YOU NEED": "필요 경험치:",
    "MORE": "남음",
    "THE NEXT LEVEL!": "레벨 업!",
    "YOU GAINED STRENGTH": "힘이 상승했습니다!",
    "YOU GAINED I.Q.": "지능이 상승했습니다!",
    "YOU GAINED PIETY": "신앙이 상승했습니다!",
    "YOU GAINED VITALITY": "생명력이 상승했습니다!",
    "YOU GAINED AGILITY": "민첩성이 상승했습니다!",
    "YOU GAINED LUCK": "행운이 상승했습니다!",
    "YOU GAINED": "능력치 상승:",
    "YOU LOST STRENGTH": "힘이 하락했습니다.",
    "YOU LOST I.Q.": "지능이 하락했습니다.",
    "YOU LOST PIETY": "신앙이 하락했습니다.",
    "YOU LOST VITALITY": "생명력이 하락했습니다.",
    "YOU LOST AGILITY": "민첩성이 하락했습니다.",
    "YOU LOST LUCK": "행운이 하락했습니다.",
    "YOU LOST": "능력치 하락:",
    "HIT POINTS.": "최대 HP 증가.",
    "HIT POINTS": "최대 HP",
    "WELCOME?": "환영합니다,",
    "WE HAVE?": "빈 방이 있습니다.",
    # Utilities & Castle
    "TEMPLE OF CANT": "칸트 사원",
    "WHO WILL TITHE": "누가 기부하시겠습니까?",
    "MURMUR -": "중얼중얼...",
    "HAS BEEN HEALED": "치료되었습니다!",
    "NEEDS KADORTO NOW": "카도르토(부활)가 필요합니다",
    "WILL BE BURIED": "매장될 것입니다 (부활 실패)",
    "WHO (#) WILL": "누가 (#)",
    "SHALL WE HELP": "치료/부활하시겠습니까",
    "SELECT GAUNTLETS": "장갑 선택",
    "(LETTER) CHANGES NAME?": "(글자) 이름 변경",
    "(LETTER) SELECTS?": "(글자)로 선택",
    "(LETTER) SELECTS": "(글자)로 선택",
    "WIZARDRY UTILITIES": "위저드리 유틸리티",
    "RESTART A PARTY": "파티 재개",
    "CHANGE NAME": "이름 변경",
    "MOVE CHARACTERS": "캐릭터 이동",
    "M)OVE CHARACTERS": "M) 캐릭터 이동",
    "C)HANGE NAME": "C) 이름 변경",
    "ALTER PASSWORD ?": "비밀번호 변경 ?",
    "ALTER PASSWORD": "비밀번호 변경",
    "A)LTER PASSWORD ?": "A) 비밀번호 변경 ?",
    "A)LTER PASSWORD": "A) 비밀번호 변경",
    "ENTER NEW PASSWORD": "새 비밀번호 입력",
    "ENTER PASSWORD ?": "비밀번호를 입력하세요",
    "ENTER PASSWORD?": "비밀번호를 입력하세요",
    "KEEP THIS CHARACTER": "캐릭터 저장",
    "ENTERING": "입장 중...",
    "PASSWORD CHANGED": "비밀번호 변경 완료",
    "L)EAVE UTILITIES": "L) 유틸리티 나가기",
    "L)EAVE GAME ?": "L) 게임 종료",
    "L)EAVE GAME": "L) 게임 종료",
    "LEAVE UTILITIES": "유틸리티 나가기",
    "LEAVE GAME ?": "게임 종료",
    "LEAVE GAME": "게임 종료",
    "SWAP DISKETTES": "디스켓 교체",
    "OF THE GAME.": "게임 성능을 높입니다.",
    "OF THE GAME": "게임의",
    "ONE MOMENT?": "잠시만 기다려요",
    "ONE MOMENT": "잠시만 기다려요",
    "SEARCHING....": "탐색 중....",
    "SEARCHING...": "탐색 중....",
    "FOUND?": "발견!",
    "FOUND": "발견!",
    "REORDERING?": "순서 변경 중",
    "REORDERING": "순서 변경 중",
    "R)EORDER": "R) 순서 변경",
    # Adventurer's Inn Rooms (Full lines and flexible sub-phrases)
    "THE STABLES (FREE!)": "말구유 (무료)",
    "THE STABLES FREE!": "말구유 (무료)",
    "THE STABLES (FREE)": "말구유 (무료)",
    "THE STABLES": "말구유",
    "(FREE!)": "(무료)",
    "(FREE)": "(무료)",
    "FREE!": "무료!",
    "FREE": "무료",
    "STABLES": "말구유",
    "A COT.": "간이침대",
    "A COT": "간이침대",
    "COT.": "간이침대",
    "COT": "간이침대",
    "10 GP/WEEK": "10 GP/주",
    "ECONOMY ROOMS.": "일반실",
    "ECONOMY ROOMS": "일반실",
    "ECONOMY": "일반실",
    "ROOMS.": "객실",
    "ROOMS": "객실",
    "50 GP/WEEK": "50 GP/주",
    "MERCHANT SUITES.": "상인실",
    "MERCHANT SUITES": "상인실",
    "MERCHANT": "상인실",
    "SUITES.": "스위트룸",
    "SUITES": "스위트룸",
    "200 GP/WEEK": "200 GP/주",
    "THE ROYAL SUITE.": "로열 스위트",
    "THE ROYAL SUITE": "로열 스위트",
    "ROYAL SUITE.": "로열 스위트",
    "ROYAL SUITE": "로열 스위트",
    "ROYAL": "로열",
    "SUITE.": "스위트",
    "SUITE": "스위트",
    "500 GP/WEEK": "500 GP/주",
    "GP/WEEK": "GP/주",
    # Character Sheet Headers & Stats (Aligned and concise)
    "CHARACTER NAME": "캐릭터 이름",
    "CLASS": "직업",
    "AC": "AC",
    "HITS": "체력",
    "STATUS": "상태",
    "STATUS OK": "상태 정상",
    "STRENGTH": "힘",
    "I.Q.": "지능",
    "PIETY": "신앙",
    "VITALITY": "생명",
    "AGILITY": "민첩",
    "LUCK": "행운",
    "BONUS": "보너스",
    "BONUS ": "보너스 ",
    "CHOOSE RACE ?": "종족을 선택하세요",
    "CHOOSE RACE?": "종족을 선택하세요",
    "CHOOSE RACE": "종족 선택",
    "CHOOSE ALIGNMENT ?": "성향을 선택하세요",
    "CHOOSE ALIGNMENT?": "성향을 선택하세요",
    "CHOOSE ALIGNMENT": "성향 선택",
    "MOVES POINTER": "항목 이동",
    "AND - ALTER": "+ / - 점수 조절",
    "ALTER SCORES": "점수 조절",
    "(ESC) WHEN FINISHED.": "완료 시 (ESC)",
    "(ESC) WHEN FINISHED": "완료 시 (ESC)",
    "GOLD": "골드",
    "LEV": "레벨",
    "AGE": "나이",
    "E.P.": "경험치",
    "H.P.": "체력",
    "A.C.": "방어력",
    "PRST": "사제",
    "PARALYZED": "마비",
    "PARALY": "마비",
    "PETRIF": "석화",
    "PARALY?": "마비",
    "USELESS?": "장착 불가",
    "POISONED": "중독",
    "POISON": "독",
    "AFRAID": "공포",
    "ASLEEP": "수면",
    "STONED": "석화",
    "DEAD": "사망",
    "ASHES": "재",
    "LOST": "소멸",
    "MAGE 0/": "마법사 0/",
    "MAGE 1/": "마법사 1/",
    "MAGE 2/": "마법사 2/",
    "MAGE 3/": "마법사 3/",
    "MAGE 4/": "마법사 4/",
    "MAGE 5/": "마법사 5/",
    "MAGE 6/": "마법사 6/",
    "MAGE 7/": "마법사 7/",
    "MAGE 8/": "마법사 8/",
    "MAGE 9/": "마법사 9/",
    "PRST 0/": "사제 0/",
    "PRST 1/": "사제 1/",
    "PRST 2/": "사제 2/",
    "PRST 3/": "사제 3/",
    "PRST 4/": "사제 4/",
    "PRST 5/": "사제 5/",
    "PRST 6/": "사제 6/",
    "PRST 7/": "사제 7/",
    "PRST 8/": "사제 8/",
    "PRST 9/": "사제 9/",
    # Equipment items & common prefixes
    "SMALL SHIELD": "소형 방패",
    "LARGE SHIELD": "대형 방패",
    "SHORT SWORD": "쇼트 소드",
    "LONG SWORD": "롱 소드",
    "LEATHER ARMOR": "가죽 갑옷",
    "CHAIN MAIL": "사슬 갑옷",
    "PLATE MAIL": "판금 갑옷",
    "ROBES": "로브",
    "DAGGER": "대거",
    "ANOINTED MACE": "성유 바른 메이스",
    "ANOINTED FLAIL": "성유 바른 플레일",
    "GLOVES OF COPPER": "구리 장갑",
    "COPPER GLOVES": "구리 장갑",
    "STAFF+2": "지팡이+2",
    "STAFF+1": "지팡이+1",
    "STAFF": "지팡이",
    "BREAST PLATE+1": "흉갑+1",
    "BREAST PLATE": "흉갑",
    "SHIELD+1": "방패+1",
    "SHIELD": "방패",
    "HELM": "투구",
    "SHORT SWORD+1": "단검+1",
    "LONG SWORD+1": "장검+1",
    "LONG SWORD+2": "장검+2",
    "MACE+1": "메이스+1",
    "MACE+2": "메이스+2",
    "GLOVES~COPPER": "구리 장갑",
    "GLOVES OF COPPER": "구리 장갑",
    # Complete 101 Monster Names (Singular & Plural)
    "BUBBLY SLIME": "버블리 슬라임",
    "BUBBLY SLIMES": "버블리 슬라임",
    "ORC": "오크",
    "ORCS": "오크",
    "KOBOLD": "코볼트",
    "KOBOLDS": "코볼트",
    "UNDEAD KOBOLD": "언데드 코볼트",
    "UNDEAD KOBOLDS": "언데드 코볼트",
    "ROGUE": "로그",
    "ROGUES": "로그",
    "BUSHWACKER": "부시래커",
    "BUSHWACKERS": "부시래커",
    "HIGHWAYMAN": "하이웨이맨",
    "ZOMBIE": "좀비",
    "ZOMBIES": "좀비",
    "CREEPING CRUD": "크리핑 크루드",
    "CREEPING CRUDS": "크리핑 크루드",
    "GAS CLOUD": "가스 클라우드",
    "GAS CLOUDS": "가스 클라우드",
    "LEVEL 1 MAGE": "1레벨 마법사",
    "LEVEL 1 MAGES": "1레벨 마법사",
    "LVL 1 MAGE": "1레벨 마법사",
    "LVL 1 MAGES": "1레벨 마법사",
    "LEVEL 1 PRIEST": "1레벨 사제",
    "LEVEL 1 PRIESTS": "1레벨 사제",
    "LVL 1 PRIEST": "1레벨 사제",
    "LVL 1 PRIESTS": "1레벨 사제",
    "CREEPING COIN": "크리핑 코인",
    "CREEPING COINS": "크리핑 코인",
    "LEVEL 1 NINJA": "1레벨 닌자",
    "LEVEL 1 NINJAS": "1레벨 닌자",
    "LVL 1 NINJA": "1레벨 닌자",
    "LVL 1 NINJAS": "1레벨 닌자",
    "VORPAL BUNNY": "보팔 버니",
    "CAPYBARA": "카피바라",
    "CAPYBARAS": "카피바라",
    "GIANT TOAD": "거대 두꺼비",
    "GIANT TOADS": "거대 두꺼비",
    "COYOTE": "코요테",
    "COYOTES": "코요테",
    "LEVEL 3 PRIEST": "3레벨 사제",
    "LEVEL 3 PRIESTS": "3레벨 사제",
    "LVL 3 PRIEST": "3레벨 사제",
    "LVL 3 PRIESTS": "3레벨 사제",
    "LEVEL 3 SAMURAI": "3레벨 사무라이",
    "LVL 3 SAMURAI": "3레벨 사무라이",
    "LEVEL 3 NINJA": "3레벨 닌자",
    "LEVEL 3 NINJAS": "3레벨 닌자",
    "LVL 3 NINJA": "3레벨 닌자",
    "LVL 3 NINJAS": "3레벨 닌자",
    "WERE BEAR": "웨어 베어",
    "WERE BEARS": "웨어 베어",
    "DRAGON FLY": "드래곤 플라이",
    "ROTTING CORPSE": "썩은 시체",
    "ROTTING CORPSES": "썩은 시체",
    "OGRE": "오거",
    "OGRES": "오거",
    "HUGE SPIDER": "거대 거미",
    "HUGE SPIDERS": "거대 거미",
    "BORING BEETLE": "보링 비틀",
    "BORING BEETLES": "보링 비틀",
    "GAS DRAGON": "가스 드래곤",
    "GAS DRAGONS": "가스 드래곤",
    "PRIESTESS": "여사제",
    "SWORDSMAN": "검사",
    "ATTACK DOG": "군견",
    "ATTACK DOGS": "군견",
    "GARGOYLE": "가고일",
    "GARGOYLES": "가고일",
    "GRAVE MIST": "그레이브 미스트",
    "GRAVE MISTS": "그레이브 미스트",
    "DRAGON PUPPY": "드래곤 퍼피",
    "WERE WOLF": "웨어 울프",
    "SHADE": "셰이드",
    "SHADES": "셰이드",
    "MINOR DAIMYO": "소 다이묘",
    "MINOR DAIMYOS": "소 다이묘",
    "LEVEL 5 MAGE": "5레벨 마법사",
    "LEVEL 5 MAGES": "5레벨 마법사",
    "LVL 5 MAGE": "5레벨 마법사",
    "LVL 5 MAGES": "5레벨 마법사",
    "LEVEL 4 THIEF": "4레벨 도적",
    "LVL 4 THIEF": "4레벨 도적",
    "KILLER WOLF": "킬러 울프",
    "SPIRIT": "스피릿",
    "SPIRITS": "스피릿",
    "GIANT SPIDER": "자이언트 스파이더",
    "GIANT SPIDERS": "자이언트 스파이더",
    "MEDUSALIZARD": "메두사 리자드",
    "MEDUSALIZARDS": "메두사 리자드",
    "LEVEL 5 PRIEST": "5레벨 사제",
    "LEVEL 5 PRIESTS": "5레벨 사제",
    "LVL 5 PRIEST": "5레벨 사제",
    "LVL 5 PRIESTS": "5레벨 사제",
    "LEVEL 6 NINJA": "6레벨 닌자",
    "LEVEL 6 NINJAS": "6레벨 닌자",
    "LVL 6 NINJA": "6레벨 닌자",
    "LVL 6 NINJAS": "6레벨 닌자",
    "LEVEL 7 MAGE": "7레벨 마법사",
    "LEVEL 7 MAGES": "7레벨 마법사",
    "LVL 7 MAGE": "7레벨 마법사",
    "LVL 7 MAGES": "7레벨 마법사",
    "MASTER THIEF": "마스터 도적",
    "MAJOR DAIMYO": "대 다이묘",
    "MAJOR DAIMYOS": "대 다이묘",
    "HIGH PRIEST": "대사제",
    "HIGH PRIESTS": "대사제",
    "CHAMP SAMURAI": "챔프 사무라이",
    "ARCH MAGE": "아치 메이지",
    "ARCH MAGES": "아치 메이지",
    "GAZE HOUND": "게이즈 하운드",
    "GAZE HOUNDS": "게이즈 하운드",
    "OGRE LORD": "오거 로드",
    "OGRE LORDS": "오거 로드",
    "TROLL": "트롤",
    "TROLLS": "트롤",
    "LIFESTEALER": "라이프스틸러",
    "LIFESTEALERS": "라이프스틸러",
    "NIGHTSTALKER": "나이트스토커",
    "NIGHTSTALKERS": "나이트스토커",
    "WYVERN": "와이번",
    "WYVERNS": "와이번",
    "LEVEL 8 PRIEST": "8레벨 사제",
    "LEVEL 8 PRIESTS": "8레벨 사제",
    "LVL 8 PRIEST": "8레벨 사제",
    "LVL 8 PRIESTS": "8레벨 사제",
    "LEVEL 10 FIGHTER": "10레벨 전사",
    "LEVEL 10 FIGHTERS": "10레벨 전사",
    "LVL 10 FIGHTER": "10레벨 전사",
    "LVL 10 FIGHTERS": "10레벨 전사",
    "LEVEL 7 THIEF": "7레벨 도적",
    "LVL 7 THIEF": "7레벨 도적",
    "LEVEL 8 NINJA": "8레벨 닌자",
    "LEVEL 8 NINJAS": "8레벨 닌자",
    "LVL 8 NINJA": "8레벨 닌자",
    "LVL 8 NINJAS": "8레벨 닌자",
    "EARTH GIANT": "어스 자이언트",
    "EARTH GIANTS": "어스 자이언트",
    "LESSER DEMON": "레서 데몬",
    "LESSER DEMONS": "레서 데몬",
    "CHIMERA": "키메라",
    "CHIMERAS": "키메라",
    "FIRE GIANT": "파이어 자이언트",
    "FIRE GIANTS": "파이어 자이언트",
    "GORGON": "고르곤",
    "GORGONS": "고르곤",
    "LEVEL 8 BISHOP": "8레벨 비숍",
    "LEVEL 8 BISHOPS": "8레벨 비숍",
    "LVL 8 BISHOP": "8레벨 비숍",
    "LVL 8 BISHOPS": "8레벨 비숍",
    "LEVEL 8 FIGHTER": "8레벨 전사",
    "LEVEL 8 FIGHTERS": "8레벨 전사",
    "LVL 8 FIGHTER": "8레벨 전사",
    "LVL 8 FIGHTERS": "8레벨 전사",
    "LEVEL 10 MAGE": "10레벨 마법사",
    "LEVEL 10 MAGES": "10레벨 마법사",
    "LVL 10 MAGE": "10레벨 마법사",
    "LVL 10 MAGES": "10레벨 마법사",
    "MASTER NINJA": "마스터 닌자",
    "MASTER NINJAS": "마스터 닌자",
    "MURPHY'S GHOST": "머피의 유령",
    "MURPHY'S GHOSTS": "머피의 유령",
    "WILL O' WISP": "윌 오 위스프",
    "WILL O' WISPS": "윌 오 위스프",
    "BLEEB": "블리브",
    "BLEEBS": "블리브",
    "FROST GIANT": "프로스트 자이언트",
    "FROST GIANTS": "프로스트 자이언트",
    "FIRE DRAGON": "파이어 드래곤",
    "FIRE DRAGONS": "파이어 드래곤",
    "HIGH WIZARD": "대위저드",
    "HIGH WIZARDS": "대위저드",
    "HATAMOTO": "하타모토",
    "HATAMOTOS": "하타모토",
    "VAMPIRE": "뱀파이어",
    "VAMPIRES": "뱀파이어",
    "GREATER DEMON": "그레이터 데몬",
    "GREATER DEMONS": "그레이터 데몬",
    "POISON GIANT": "포이즌 자이언트",
    "POISON GIANTS": "포이즌 자이언트",
    "DRAGON ZOMBIE": "드래곤 좀비",
    "DRAGON ZOMBIES": "드래곤 좀비",
    "RAVER LORD": "레이버 로드",
    "RAVER LORDS": "레이버 로드",
    "THE HIGH MASTER": "하이 마스터",
    "THE HIGH MASTERS": "하이 마스터",
    "HIGH MASTER": "하이 마스터",
    "HIGH MASTERS": "하이 마스터",
    "FLACK": "플랙",
    "MAELIFIC": "말리픽",
    "MAELIFICS": "말리픽",
    "VAMPIRE LORD": "뱀파이어 로드",
    "VAMPIRE LORDS": "뱀파이어 로드",
    "WERDNA": "베르드나",
    "HIGH NINJA": "하이 닌자",
    "HIGH NINJAS": "하이 닌자",
    "LEVEL 7 FIGHTER": "7레벨 전사",
    "LEVEL 7 FIGHTERS": "7레벨 전사",
    "LVL 7 FIGHTER": "7레벨 전사",
    "LVL 7 FIGHTERS": "7레벨 전사",
    # Complete 101 Item Names & Ligatures
    "BROKEN ITEM": "부서진 아이템",
    "LONG SWORD": "롱 소드",
    "SHORT SWORD": "쇼트 소드",
    "ANOINTED MACE": "성유 바른 메이스",
    "ANOINTED FLAIL": "성유 바른 플레일",
    "STAFF": "지팡이",
    "DAGGER": "대거",
    "SMALL SHIELD": "소형 방패",
    "LARGE SHIELD": "대형 방패",
    "ROBES": "로브",
    "LEATHER ARMOR": "가죽 갑옷",
    "CHAIN MAIL": "사슬 갑옷",
    "BREAST PLATE": "흉갑",
    "PLATE MAIL": "판금 갑옷",
    "HELM": "투구",
    "LONG SWORD +1": "롱 소드+1",
    "LONG SWORD+1": "롱 소드+1",
    "SHORT SWORD +1": "쇼트 소드+1",
    "SHORT SWORD+1": "쇼트 소드+1",
    "MACE +1": "메이스+1",
    "MACE+1": "메이스+1",
    "STAFF OF MOGREF": "모그레프의 지팡이",
    "STAFF~MOGREF": "모그레프의 지팡이",
    "LEATHER ARMOR +1": "가죽 갑옷+1",
    "LEATHER+1": "가죽 갑옷+1",
    "CHAIN MAIL +1": "사슬 갑옷+1",
    "CHAIN+1": "사슬 갑옷+1",
    "PLATE MAIL +1": "판금 갑옷+1",
    "PLATE+1": "판금 갑옷+1",
    "SHIELD +1": "방패+1",
    "SHIELD+1": "방패+1",
    "BREAST PLATE +1": "흉갑+1",
    "LONG SWORD -1": "롱 소드-1",
    "LONG SWORD-1": "롱 소드-1",
    "SHORT SWORD -1": "쇼트 소드-1",
    "SHORT SWORD-1": "쇼트 소드-1",
    "MACE -1": "메이스-1",
    "MACE-1": "메이스-1",
    "STAFF +2": "지팡이+2",
    "STAFF+2": "지팡이+2",
    "SLAYER OF DRAGONS": "드래곤 슬레이어",
    "SLAYER~DRAGONS": "드래곤 슬레이어",
    "DRAGON SLAYER": "드래곤 슬레이어",
    "HELM +1": "투구+1",
    "HELM+1": "투구+1",
    "LEATHER ARMOR -1": "가죽 갑옷-1",
    "LEATHER-1": "가죽 갑옷-1",
    "CHAIN MAIL -1": "사슬 갑옷-1",
    "CHAIN-1": "사슬 갑옷-1",
    "BREAST PLATE -1": "흉갑-1",
    "SHIELD -1": "방패-1",
    "SHIELD-1": "방패-1",
    "AMULET OF JEWELS": "보석의 부적",
    "AMULET~JEWELS": "보석의 부적",
    "LONG SWORD +2": "롱 소드+2",
    "LONG SWORD+2": "롱 소드+2",
    "SHORT SWORD +2": "쇼트 소드+2",
    "SHORT SWORD+2": "쇼트 소드+2",
    "MACE +2": "메이스+2",
    "MACE+2": "메이스+2",
    "GLOVES OF COPPER": "구리 장갑",
    "GLOVES~COPPER": "구리 장갑",
    "COPPER GLOVES": "구리 장갑",
    "LEATHER ARMOR +2": "가죽 갑옷+2",
    "LEATHER+2": "가죽 갑옷+2",
    "CHAIN MAIL +2": "사슬 갑옷+2",
    "CHAIN+2": "사슬 갑옷+2",
    "PLATE MAIL +2": "판금 갑옷+2",
    "PLATE+2": "판금 갑옷+2",
    "SHIELD +2": "방패+2",
    "SHIELD+2": "방패+2",
    "HELM +2": "투구+2",
    "HELM+2": "투구+2",
    "RING OF PORFIC": "포르픽 반지",
    "RING~PORFIC": "포르픽 반지",
    "WERE SLAYER": "웨어 슬레이어",
    "MAGE MASHER": "메이지 매셔",
    "MACE OF POISON": "독의 메이스",
    "MACE~POISON": "독의 메이스",
    "STAFF OF MONTINO": "몬티노의 지팡이",
    "STAFF~MONTINO": "몬티노의 지팡이",
    "BLADE CUSINART": "블레이드 커시너트",
    "AMULET OF MANIFO": "마니포의 부적",
    "AMULET~MANIFO": "마니포의 부적",
    "ROD OF FLAME": "화염의 지팡이",
    "ROD~FLAME": "화염의 지팡이",
    "EVIL SHIELD +3": "악의 방패+3",
    "AMULET OF MAKANITO": "마카니토의 부적",
    "AMULET~MAKANITO": "마카니토의 부적",
    "HELM OF MALOR": "말로르의 투구",
    "HELM~MALOR": "말로르의 투구",
    "SHORT SWORD -2": "쇼트 소드-2",
    "DAGGER +2": "대거+2",
    "DAGGER+2": "대거+2",
    "MACE -2": "메이스-2",
    "STAFF -2": "지팡이-2",
    "DAGGER OF SPEED": "신속의 대거",
    "DAGGER~SPEED": "신속의 대거",
    "ROBE OF CURSES": "저주의 로브",
    "ROBE~CURSES": "저주의 로브",
    "LEATHER ARMOR -2": "가죽 갑옷-2",
    "CHAIN MAIL -2": "사슬 갑옷-2",
    "BREAST PLATE -2": "흉갑-2",
    "SHIELD -2": "방패-2",
    "HELM OF CURSES": "저주의 투구",
    "HELM~CURSES": "저주의 투구",
    "BREAST PLATE +2": "흉갑+2",
    "GLOVES OF SILVER": "은 장갑",
    "GLOVES~SILVER": "은 장갑",
    "SILVER GLOVES": "은 장갑",
    "EVIL SWORD +3": "악의 검+3",
    "DAGGER OF THIEVES": "도적의 대거",
    "DAGGER~THIEVES": "도적의 대거",
    "BREAST PLATE +3": "흉갑+3",
    "GARB OF LORDS": "로드의 갑주",
    "GARB~LORDS": "로드의 갑주",
    "LORDS GARB": "로드의 갑주",
    "MURAMASA BLADE": "무라마사 블레이드",
    "SHURIKENS": "수리검",
    "COLD CHAIN MAIL": "빙결 사슬 갑옷",
    "EVIL PLATE +3": "악의 판금 갑옷+3",
    "SHIELD +3": "방패+3",
    "SHIELD+3": "방패+3",
    "RING OF HEALING": "치유의 반지",
    "RING~HEALING": "치유의 반지",
    "PRIEST'S RING": "사제의 반지",
    "RING OF DEATH": "죽음의 반지",
    "RING OF DEATH!": "죽음의 반지",
    "RING~DEATH": "죽음의 반지",
    "RING~DEATH!": "죽음의 반지",
    "AMULET OF WERDNA": "베르드나의 부적",
    "AMULET~WERDNA": "베르드나의 부적",
    "STATUE OF BEAR": "곰의 조각상",
    "STATUE~BEAR": "곰의 조각상",
    "STATUE OF FROG": "개구리의 조각상",
    "STATUE~FROG": "개구리의 조각상",
    "KEY OF BRONZE": "청동 열쇠",
    "KEY~BRONZE": "청동 열쇠",
    "KEY OF SILVER": "은 열쇠",
    "KEY~SILVER": "은 열쇠",
    "KEY OF GOLD": "황금 열쇠",
    "KEY~GOLD": "황금 열쇠",
    "BLUE RIBBON": "푸른 리본",
    # Races & Alignments
    "HUMAN": "인간", "ELF": "엘프", "DWARF": "드워프", "GNOME": "노움", "HOBBIT": "호빗",
    "GOOD": "선", "NEUTRAL": "중립", "EVIL": "악",
    # --- Newly Added Translations from Gameplay Logs ---
    # Inn, Resting, Level Up & Stats
    "LEARNED NEW SPELLS!!": "새로운 주문을 배웠습니다!!",
    "LEARNED NEW SPELLS!": "새로운 주문을 배웠습니다!",
    "YOU GAINED STRENGTH": "힘이 상승했습니다",
    "YOU GAINED I.Q.": "지혜(I.Q.)가 상승했습니다",
    "YOU GAINED PIETY": "신앙심이 상승했습니다",
    "YOU GAINED VITALITY": "생명력이 상승했습니다",
    "YOU GAINED AGILITY": "민첩성이 상승했습니다",
    "YOU GAINED LUCK": "운이 상승했습니다",
    "YOU LOST STRENGTH": "힘이 하락했습니다",
    "YOU LOST I.Q.": "지혜(I.Q.)가 하락했습니다",
    "YOU LOST PIETY": "신앙심이 하락했습니다",
    "YOU LOST VITALITY": "생명력이 하락했습니다",
    "YOU LOST AGILITY": "민첩성이 하락했습니다",
    "YOU LOST LUCK": "운이 하락했습니다",
    "FIGHTER": "전사",
    "MAGE": "마법사",
    "PRIEST": "사제",
    "SAMURAI": "사무라이",
    "LORD": "로드",
    "NINJA": "닌자",
    "FIGHTER IS NAPPING.": "전사는 낮잠을 자고 있습니다.",
    "MAGE IS NAPPING.": "마법사는 낮잠을 자고 있습니다.",
    "PRIEST IS NAPPING.": "사제는 낮잠을 자고 있습니다.",
    "THIEF IS NAPPING.": "도적은 낮잠을 자고 있습니다.",
    "BISHOP IS NAPPING.": "비숍은 낮잠을 자고 있습니다.",
    "SAMURAI IS NAPPING.": "사무라이는 낮잠을 자고 있습니다.",
    "LORD IS NAPPING.": "로드는 낮잠을 자고 있습니다.",
    "NINJA IS NAPPING.": "닌자는 낮잠을 자고 있습니다.",
    "IS NAPPING.": "낮잠을 자고 있습니다.",
    "IS NAPPING": "낮잠을 자고 있습니다",
    "WE HAVE?": "빈 방 목록:",
    "WE HAVE": "빈 방 목록:",
    "THE STABLES <FREE!>": "마구간 <무료!>",
    "<FREE!>": "<무료!>",
    ". 10 GP/WEEK": "10 GP/주",
    ". 50 GP/WEEK": "50 GP/주",
    ". 200 GP/WEEK": "200 GP/주",
    ". 500 GP/WEEK": "500 GP/주",
    "GP/WEEK": "GP/주",
    "? OR L)EAVE": "또는 L) 나가기",
    "? OR ↵LEAVE": "또는 ↵ 나가기",
    "? OR": "또는",
    # Temple of Cant
    "WHO WILL TITHE": "누가 십일조를 내겠습니까",
    "SHALL WE HELP": "치료해 드릴까요",
    "HAS BEEN HEALED": "치료되었습니다",
    "WILL BE BURIED": "매장될 것입니다",
    "NEEDS KADORTO NOW": "지금 카도르토가 필요합니다",
    "MURMUR -": "중얼거림 -",
    # Combat: Encounters, Actions, Attacks, Results
    "AN ENCOUNTER": "조우했습니다!",
    "FIGHT WHICH GROUP": "어느 무리를 공격하시겠습니까",
    "ATTEMPTS TO SLICE": "베기를 시도합니다",
    "TRIES TO GNAW": "물어뜯으려 합니다",
    "TRIES TO STAB": "찌르기를 시도합니다",
    "ATTEMPTS TO CHEW": "씹으려 시도합니다",
    "CLAWS AT": "할퀴기를 시도합니다",
    "BITES AT": "물어뜯으려 합니다",
    "CHARGES AT": "돌진합니다",
    "THRUSTS VIOLENTLY AT": "맹렬하게 찔러옵니다",
    "LEAPS AT": "도약하여 덮칩니다",
    "RUNS AWAY": "도망쳤습니다!",
    "AND MISSES": "빗나갔습니다!",
    "AND HIT": "명중했습니다!",
    "AND HITS": "명중했습니다!",
    "HITS ONCE FOR": "1회 명중,",
    "FOR 1 DAMAGE": "1 피해",
    "FOR 2 DAMAGE": "2 피해",
    "FOR 3 DAMAGE": "3 피해",
    "FOR 4 DAMAGE": "4 피해",
    "FOR 5 DAMAGE": "5 피해",
    "FOR 6 DAMAGE": "6 피해",
    "FOR 7 DAMAGE": "7 피해",
    "FOR 8 DAMAGE": "8 피해",
    "FOR 9 DAMAGE": "9 피해",
    "FOR 10 DAMAGE": "10 피해",
    "FOR 11 DAMAGE": "11 피해",
    "FOR 12 DAMAGE": "12 피해",
    "FOR 13 DAMAGE": "13 피해",
    "FOR 14 DAMAGE": "14 피해",
    "FOR 15 DAMAGE": "15 피해",
    "FOR 16 DAMAGE": "16 피해",
    "FOR 17 DAMAGE": "17 피해",
    "FOR 18 DAMAGE": "18 피해",
    "FOR 19 DAMAGE": "19 피해",
    "FOR 20 DAMAGE": "20 피해",
    "ARE RESTORED TO": "회복되었습니다 ->",
    "EACH SURVIVOR GETS": "생존자 1인당 획득:",
    "IS KILLED!": "처치되었습니다!",
    "IS KILLED": "처치되었습니다",
    "UNSEEN ENTITY": "보이지 않는 존재",
    "SMALL HUMANOID": "소형 휴머노이드",
    "SMALL HUMANOIDS": "소형 휴머노이드 무리",
    # Unidentified group name seen in combat on the PC version (2026-11-03).
    "WEIRD HUMANOID": "기묘한 휴머노이드",
    "WEIRD HUMANOIDS": "기묘한 휴머노이드 무리",
    # Seen in combat on the PC version (2026-11-03).
    "KIMONOED MAN": "기모노 입은 남자",
    "KIMONOED MEN": "기모노 입은 남자들",
    "SCRUFFY MAN": "지저분한 남자",
    "SCRUFFY MEN": "지저분한 남자들",
    "UNDEAD KOBOLD": "언데드 코볼트",
    "UNDEAD KOBOLDS": "언데드 코볼트 무리",
    "BUBBLY SLIME": "거품 슬라임",
    "MURPHY'S GHOST": "머피의 유령",
    "'S GHOST": "의 유령",
    "FIGHTER FOUND": "전사가 발견함:",
    "MAGE FOUND": "마법사가 발견함:",
    "PRIEST FOUND": "사제가 발견함:",
    "THIEF FOUND": "도적이 발견함:",
    "BISHOP FOUND": "비숍이 발견함:",
    "SAMURAI FOUND": "사무라이가 발견함:",
    "LORD FOUND": "로드가 발견함:",
    "NINJA FOUND": "닌자가 발견함:",
    "FOUND ? SWORD": "검을 발견했습니다",
    "FOUND": "발견함:",
    # Options prompts
    # Maze, Events & Messages
    "SHOUTS \"BEGONE? STRANGERS!\"": '외칩니다: "물러가라, 불청객들아!"',
    "SHOUTS \"BEGONE! STRANGERS!\"": '외칩니다: "물러가라, 불청객들아!"',
    "INCENSE IS BURNING.": "향이 타오르고 있습니다.",
    "IS BURNING.": "타오르고 있습니다.",
    "WILL YOU SEARCH": "수색하시겠습니까",
    "SEARCHING...": "수색 중...",
    "SEARCHING....": "수색 중...",
    # Chests, Traps & Inspection
    "NOT TRAPPED": "함정이 없었습니다",
    "TRAP WAS TRIGGERED": "함정이 격발되었습니다!",
    "DISARMED THE TRAP!": "함정을 성공적으로 해제했습니다!",
    "TRAP (↵ EXITS)": "함정 이름 입력 (↵ 나가기)",
    "(↵ EXITS)": "(↵ 나가기)",
    "TRAPLESS CHEST": "함정 없는 상자",
    "POISON NEEDLE": "독침 (POISON NEEDLE)",
    "GAS BOMB": "가스 폭탄 (GAS BOMB)",
    "EXPLODING BOX": "폭발 상자 (EXPLODING BOX)",
    "CROSSBOW BOLT": "석궁 화살 (CROSSBOW BOLT)",
    "MAGE BLASTER": "마법사 블래스터 (MAGE BLASTER)",
    "PRIEST BLASTER": "사제 블래스터 (PRIEST BLASTER)",
    "TELEPORTER": "텔레포터 (TELEPORTER)",
    "ALARM": "경보 (ALARM)",
    "WHO WILL OPEN": "누가 상자를 열겠습니까",
    "WHO WILL DISARM": "누가 함정을 해제하겠습니까",
    "WHO WILL INSPECT": "누가 점검/감정하겠습니까",
    "YOU MAY": "행동 선택:",
    "L)EAVE ALONE": "L) 내버려두기",
    "I)NSPECT D)ISARM": "I) 감정   D) 해제",
    # Character Sheet / Camp Actions
    "CAST ON WHOM": "누구에게 시전하시겠습니까",
    "CAST WHAT SPELL": "어떤 주문을 외우시겠습니까",
    "TRADE WITH WHOM": "누구와 교환하시겠습니까",
    "TRADE GOLD (AMT)": "골드 교환 (금액 입력)",
    "DROP ITEM (#)": "버릴 아이템 선택 (#)",
    "IDENTIFY WHAT": "감정할 아이템 선택",
    "YOU IDENTIFIED IT!": "아이템을 감정했습니다!",
    "YOU IDENTIFIED IT": "아이템을 감정했습니다",
    "SELL WHICH (#)": "판매할 아이템 선택 (#)",
    "UNCURSE WHICH (#)": "저주를 해제할 아이템 (#)",
    "IP WHICH (#)": "장착할 아이템 선택 (#)",
    "T)AKE BACK ORDERS": "T) 이전 명령 취소",
    "T)AKE BACK": "T) 이전 취소",
    "* DONE! *": "* 완료! *",
    "* OK *": "* 완료 *",
    "MISC. ITEM": "기타 아이템", "DUPLICATE SCENARIO": "복제 시나리오",
    "READING MASTER DISK...": "마스터 디스크 읽는 중...", "WRITING BLANK DISK...": "빈 디스크에 쓰는 중...",
    '"MAPIRO MAHAMA DIROMAT"': '"마피로 마하마 디로마트"',
    "CASTS A": "주문 시전:",
    "SPELL NAME": "주문명 입력",
    "IS COMPLETELY HEALED": "완전히 회복되었습니다",
    "SPELL BOOK": "주문서",
    "SPELL BOOKS": "주문서",
    "M)AGE SPELL BOOKS": "M) 마법사 주문서",
    "P)RIEST SPELL BOOKS": "P) 사제 주문서",
    "M)AGE SPELL BOOK": "M) 마법사 주문서",
    "P)RIEST SPELL BOOK": "P) 사제 주문서",
    "P)URCHASE": "P) 구매",
    "SELECT GAUNTLETS": "건틀릿 선택",
    # Utilities & Training Grounds
    "WIZARDRY UTILITIES": "위저드리 유틸리티",
    "IN THE MAZE": "미궁에 남겨짐",
    "RESTART A PARTY": "미궁의 파티 재개",
    "YOU DON'T QUALIFY": "조건을 만족하지 못합니다",
    "KEEP THIS CHARACTER": "이 캐릭터를 등록하시겠습니까",
    "CHOOSE ALIGNMENT": "성향을 선택하세요",
    "CHOOSE RACE": "종족을 선택하세요",
    "SELECT CLASS": "직업을 선택하세요",
    "C)HANGE CLASS": "C) 전직",
    "C)HANGE NAME": "C) 이름 변경",
    "CHANGE NAME": "이름 변경",
    "(LETTER) CHANGES NAME": "(문자) 이름 변경",
    "M)OVE CHARACTERS": "M) 캐릭터 디스크 이동",
    "MOVE CHARACTERS": "캐릭터 디스크 이동",
    "R)EORDER": "R) 순서 정렬",
    "REORDERING": "순서 정렬 중",
    "REMOVE WHO (#)": "누구를 제외하시겠습니까 (#)",
    "REMOVE WHO": "누구를 제외하시겠습니까",
    "D)ELETE": "D) 캐릭터 삭제",
    "I)NSPECT A CHARACTER": "I) 캐릭터 점검",
    "L)EAVE UTILITIES": "L) 유틸리티 종료",
    # The utilities leave line uses the return arrow, so L)EAVE UTILITIES
    # does not match. The leftover word is redrawn one cell at a time.
    "L↵EAVE UTILITIES": "↵ 유틸리티 종료",
    "UTILITIES": "유틸리티",
    "L)EAVE GAME": "L) 게임 종료",
    "A)LTER PASSWORD": "A) 비밀번호 변경",
    "ALTER PASSWORD": "비밀번호 변경",
    "ENTER PASSWORD": "비밀번호를 입력하세요",
    "ENTER NEW PASSWORD": "새 비밀번호를 입력하세요",
    "WHEN FINISHED.": "완료 후.",
    "MOVES POINTER": "포인터 이동",
    # Lines the log kept. A one-cell gap is matched as a space, so these
    # keys stay in normal spelling.
    "BE ERASED!": "지워집니다!",
    "CYCLES COMPLETED": "작성 회차 완료",
    "SCENARIO DISK MADE": "시나리오 디스크 완성",
    "EXIT WITHOUT MOVING": "옮기지 않고 종료",
    "YOU ALREADY LOOKED!": "이미 살펴보았습니다!",
    "CHEAP APOSTATES! OUT!": "싸구려 배교자들아! 나가라!",
    "OLD NAME IS": "기존 이름:",
    # =========================================================================
    # PREEMPTIVE COMPREHENSIVE TRANSLATIONS (Dungeon Events, Combat, Town, Shops)
    # =========================================================================
    "SHOUTS \"BEGONE, STRANGERS!\"": "외칩니다: \"물러가라, 불청객들아!\"",
    "SHOUTS \"BEGONE! STRANGERS!\"": "외칩니다: \"물러가라, 불청객들아!\"",
    "\"MAPIRO MAHAMA DIROMAT!!\"": "\"마피로 마하마 디로마트!!\"",
    "MAPIRO MAHAMA DIROMAT!!": "마피로 마하마 디로마트!!",
    "INCENSE IS BURNING.": "향이 타오르고 있습니다.",
    "WILL YOU SEARCH": "수색하시겠습니까",
    "SEARCHING...": "수색 중...",
    "SEARCHING....": "수색 중...",
    "THEREON.": "새겨져 있습니다.",
    "\"YEAH.. YEAH..\"": "\"예.. 예..\"",
    "YEAH.. YEAH..": "예.. 예..",
    "\"A DUNGEON'S DARK...\"": "\"던전은 어둡고...\"",
    "\"MONSTER ALLOCATION CENTER\"": "\"몬스터 배치 센터\"",
    "MONSTER ALLOCATION CENTER": "몬스터 배치 센터",
    "\"TREASURE REPOSITORY.\"": "\"보물 보관소\"",
    "TREASURE REPOSITORY.": "보물 보관소",
    "AUTHORIZED PERSONNEL ONLY!": "인가된 인원 외 출입 엄금!",
    "DO NOT ENTER": "절대 들어가지 마시오",
    "AUTHORIZED USERS ONLY!": "허가된 사용자만 탑승 가능!",
    "\"TURN AROUND.\"": "\"뒤로 돌아가라.\"",
    "\"TURN LEFT.\"": "\"좌회전하라.\"",
    "\"TURN RIGHT.\"": "\"우회전하라.\"",
    "TURN AROUND.": "뒤로 돌아가라.",
    "TURN LEFT.": "좌회전하라.",
    "TURN RIGHT.": "우회전하라.",
    "\"CONGRATULATIONS, BRAVE ADVENTURERS!": "\"축하하오, 용감한 모험가들이여!",
    "\"CONTRA-DEXTRA AVENUE\"": "\"콘트라-덱스트라 대로\"",
    "CONTRA-DEXTRA AVENUE": "콘트라-덱스트라 대로",
    "TREBOR SUX!": "트레보 멍청이!",
    "CASTS A SPELL": "주문을 시전합니다:",
    "RESISTS THE SPELL": "주문에 저항했습니다!",
    "RESISTS": "저항했습니다!",
    "CALLS FOR HELP": "도움을 요청합니다!",
    "DECAPITATED!": "목이 베였습니다!",
    "ATTEMPTS TO FLEE": "도주를 시도합니다",
    "CANNOT FLEE": "도망칠 수 없습니다!",
    # Light spell status box in the maze view, seen on the PC version (2026-11-03).
    # Pit square message box in the maze, seen on the PC version (2026-11-03).
    "A PIT!": "구덩이다!",
    "LIGHT": "빛",
    # MAPORFIC status in the same box, seen on the PC version (2026-11-03).
    "PROTECT": "보호",
    # Seen on the PC version (2026-11-03): "SISTER DISPELLS ONE MONSTER".
    "DISPELLS ONE MONSTER": "몬스터 하나를 퇴치했습니다",
    # Plural seen by the user on the PC version (2026-11-03): "DISPELLS 2 MONSTERS".
    "DISPELLS 2 MONSTERS": "몬스터 2마리를 퇴치했습니다",
    "DISPELLS 3 MONSTERS": "몬스터 3마리를 퇴치했습니다",
    "DISPELLS 4 MONSTERS": "몬스터 4마리를 퇴치했습니다",
    "DISPELLS 5 MONSTERS": "몬스터 5마리를 퇴치했습니다",
    "DISPELLS 6 MONSTERS": "몬스터 6마리를 퇴치했습니다",
    "DISPELLS 7 MONSTERS": "몬스터 7마리를 퇴치했습니다",
    "DISPELLS 8 MONSTERS": "몬스터 8마리를 퇴치했습니다",
    "DISPELLS 9 MONSTERS": "몬스터 9마리를 퇴치했습니다",
    "IS ASLEEP": "잠들어 있습니다",
    "WAKES UP": "잠에서 깨어났습니다!",
    "IS PARALYZED": "몸이 마비되었습니다!",
    "IS STONED": "돌로 석화되었습니다!",
    "IS POISONED": "독에 중독되었습니다!",
    "TAKES POISON DAMAGE": "독 피해를 입었습니다!",
    "POISON DAMAGE": "독 피해",
    "BREATHES FIRE": "화염을 내뿜습니다!",
    "BREATHES COLD": "냉기를 내뿜습니다!",
    "BREATHES POISON": "독기를 내뿜습니다!",
    "BREATHES GAS": "가스를 내뿜습니다!",
    "BREATHES": "숨결(브레스)을 내뿜습니다!",
    "WHO WILL BUY?": "누가 구매하시겠습니까?",
    "WHO WILL BUY": "누가 구매하시겠습니까?",
    "WHO WILL SELL?": "누가 판매하시겠습니까?",
    "WHO WILL SELL": "누가 판매하시겠습니까?",
    "WHO WILL IDENTIFY?": "누가 감정하시겠습니까?",
    "WHO WILL IDENTIFY": "누가 감정하시겠습니까?",
    "WHO WILL UNCURSE?": "누가 저주를 해제하시겠습니까?",
    "WHO WILL UNCURSE": "누가 저주를 해제하시겠습니까?",
    "CAN'T AFFORD THAT": "골드가 부족합니다",
    "CAN'T AFFORD": "골드 부족",
    "NO ROOM": "공간 부족",
    "CANNOT BE USED": "사용 불가",
    "THAT IS CURSED!": "그 아이템은 저주받았습니다!",
    "IS CURSED!": "저주받았습니다!",
    "IS CURSED": "저주받음",
    "ARE YOU SURE?": "정말 진행하시겠습니까?",
    "ARE YOU SURE": "정말 진행하시겠습니까",
    "THANK YOU!": "감사합니다!",
    "THANK YOU": "감사합니다",
    "WHO WILL LEAVE?": "누구를 파티에서 제외하시겠습니까?",
    "WHO WILL LEAVE": "누구를 파티에서 제외하시겠습니까?",
    "PARTY IS FULL!": "파티 정원(6명)이 가득 찼습니다!",
    "PARTY IS FULL": "파티 정원이 가득 찼습니다",
    "DIVVY GOLD": "골드 공평 분배",
    "WHO WILL REST?": "누가 휴식을 취하시겠습니까?",
    "WHO WILL REST": "누가 휴식을 취하시겠습니까?",
    "FULL HEALING": "완전 회복",
    "THE TITHE IS": "십일조 금액:",
    "THE DONATION IS": "기부금 금액:",
    "HAS BEEN CURED!": "상태이상이 완치되었습니다!",
    "HAS BEEN CURED": "완치되었습니다",
    "HAS BEEN RESTORED!": "생명력이 온전히 회복되었습니다!",
    "SPELL HAS FAILED!": "기도와 주문이 실패했습니다!",
    "SPELL FAILED!": "주문 실패!",
    "ENTER THE MAZE": "미궁으로 진입",
    "TRAINING GROUNDS": "훈련장",
    "CREATE A CHARACTER": "새 캐릭터 생성",
    "CHANGE CLASS": "전직",
    "DELETE A CHARACTER": "캐릭터 삭제",
    "REORDER CHARACTERS": "캐릭터 순서 변경",
    "MOVE CHARACTERS": "캐릭터 디스크 이동",
    "ALTER PASSWORD": "비밀번호 변경",
    "LEAVE UTILITIES": "유틸리티 종료",
}
DEFAULT_UI_TRANSLATIONS.update(_HASHED_WIZ1.get('DEFAULT_UI', {}))

# Context-specific translation tables for words that have different meanings depending on scene
CONTEXT_TRANSLATIONS = {
    "chest": {
        "OOPS!": "앗! 함정 발동!",
        "POISON NEEDLE": "독침 (POISON NEEDLE)",
        "GAS BOMB": "가스 폭탄 (GAS BOMB)",
        "CROSSBOW BOLT": "쇠뇌 화살 (CROSSBOW BOLT)",
        "EXPLODING BOX": "폭발 상자 (EXPLODING BOX)",
        "STUNNER": "기절 함정 (STUNNER)",
        "TELEPORTER": "순간이동 함정 (TELEPORTER)",
        "MAGE BLASTER": "마법사 폭탄 (MAGE BLASTER)",
        "PRIEST BLASTER": "사제 폭탄 (PRIEST BLASTER)",
        "ALARM": "경보 (ALARM)",
        "JAX SLING": "잭스 슬링 (JAX SLING)",
        "VAPOR COIL": "증기 코일 (VAPOR COIL)",
        "RAINBOW RAY": "무지개 광선 (RAINBOW RAY)",
        "DAEMON EYE": "데몬 아이 (DAEMON EYE)",
        "SIRENS": "세이렌 (SIRENS)",
        "PSIONICS": "사이오닉스 (PSIONICS)",
        "MAGNETICS": "자기장 (MAGNETICS)",
        "LAPIS SPINE": "청옥 가시 (LAPIS SPINE)",
        "ASTRAL CUBE": "아스트랄 큐브 (ASTRAL CUBE)",
        "POWDER KEG": "화약통 (POWDER KEG)",
        "FIGBY FIST": "피그비 피스트 (FIGBY FIST)",
        "DRAGON'S ASP": "드래곤의 독사 (DRAGON'S ASP)",
        "ELECTRIC BOLT": "전기 볼트 (ELECTRIC BOLT)",
        "MAGIC DRAIN": "마력 흡수 (MAGIC DRAIN)",
        # Chest / Trap Inspection: 'INSPECT' means inspect the chest for traps, not character sheet!
        "WHO (#) WILL INSPECT ?": "누가 (#) 함정을 확인하시겠습니까?",
        "WHO (#) WILL INSPECT": "누가 (#) 함정을 확인하시겠습니까?",
        "WHO WILL INSPECT ?": "누가 함정을 확인하시겠습니까?",
        "WHO WILL INSPECT": "누가 함정을 확인하시겠습니까?",
        "WHO (#) WILL OPEN ?": "누가 (#) 상자를 열겠습니까?",
        "WHO (#) WILL OPEN": "누가 (#) 상자를 열겠습니까?",
        "WHO WILL OPEN ?": "누가 상자를 열겠습니까?",
        "WHO WILL OPEN": "누가 상자를 열겠습니까?",
        "WHO (#) WILL DISARM ?": "누가 (#) 함정을 해제하겠습니까?",
        "WHO (#) WILL DISARM": "누가 (#) 함정을 해제하겠습니까?",
        "WHO WILL DISARM ?": "누가 함정을 해제하겠습니까?",
        "WHO WILL DISARM": "누가 함정을 해제하겠습니까?",
        "I)NSPECT": "I) 함정 확인",
        "I) NSPECT": "I) 함정 확인",
        "INSPECT": "함정 확인",
        "O)PEN": "O) 열기",
        "O) PEN": "O) 열기",
        "OPEN": "열기",
        "C)ALFO": "C) 칼포",
        "C) ALFO": "C) 칼포",
        "CALFO": "칼포",
        "D)ISARM": "D) 함정 해제",
        "D) ISARM": "D) 함정 해제",
        "DISARM": "함정 해제",
        "L↵EAVE": "↵ 상자 포기",
        "L↵ EAVE": "↵ 상자 포기",
        "L)EAVE": "L) 상자 포기",
        "L) EAVE": "L) 상자 포기",
        "LEAVE": "상자 포기",
        "COULD NOT DISARM": "함정을 해제하지 못했습니다",
        "A CHEST!": "상자 발견!",
    },
    "combat": {
        # Article before a monster: "AN ORC" -> "한 오크". Combat only.
        "AN": "한",
        "A": "한",
        "AND": "그리고",
        # "^ CALLS FOR HELP... BUT NO HELP COMES" wraps after any word: the
        # first piece carries the sentence, the rest is only covered.
        "BUT NO HELP COMES": "아무도 오지 않는다", "BUT NO HELP": "아무도 오지 않는다",
        "BUT NO": "아무도 오지 않는다", "HELP COMES": "", "COMES": "",
        "ONE MONSTER APPEARS": "한 마리가 나타났다", "ONE MONSTER": "한 마리가 나타났다",
        "APPEARS": "",
        # "^ TRIES TO CAST A ? BUT CANNOT SPEAK!" / "... BUT NOTHING HAPPENS!" wrap the same way.
        "BUT": "", "CANNOT SPEAK!": "- 말을 할 수 없다!", "BUT CANNOT": "- 말을 할 수 없다!", "SPEAK!": "",
        "NOTHING HAPPENS!": "- 아무 일도 없다!", "BUT NOTHING": "- 아무 일도 없다!", "HAPPENS!": "",
        "NO HELP COMES": "아무도 오지 않는다",
        "THE": "그",
        "BUBBLY": "버블리",
        "DISPELL WHICH GROUP (#) ?": "어느 무리를 퇴치하시겠습니까 (#) ?",
        "CAST SPELL ON GROUP (#) ?": "어느 무리에 주문을 외우시겠습니까 (#) ?",
        "ATTEMPTS TO DISPELL": "퇴치를 시도합니다",
        "AND FAILS": "실패했습니다!",
        "IS SLEPT": "잠들었습니다",
        "KILLED!": "처치되었습니다!",
        "BISHOP": "비숍",
        "PRIEST": "사제",
        "BISHOPS": "비숍",
        "THIEF": "도적",
        "WARRIOR": "전사",
        "MAGE": "마법사",
        "F)IGHT": "F) 공격",
        "F) IGHT": "F) 공격",
        "P↵ARRY": "↵ 방어",
        "P↵ ARRY": "↵ 방어",
        "↵ARRY": "↵ 방어",
        "P)ARRY": "↵ 방어",
        "P) ARRY": "↵ 방어",
        "C)AST": "C) 주문",
        "C) AST": "C) 주문",
        "R)UN": "R) 도주",
        "R) UN": "R) 도주",
        "D)ISPEL": "D) 퇴치",
        "D)ISPELL": "D) 퇴치",
        "U)SE ITEM": "U) 도구",
        "U)SE": "U) 사용",
        "S)PELL": "S) 주문",
        "S) PELL": "S) 주문",
        "T)AKE BACK ORDERS": "T) 명령 취소",
        "T)AKE BACK": "T) 이전 취소",
        "T)AKE": "T) 취소",
        "L)EAVE": "L) 나가기",
        "L) EAVE": "L) 나가기",
        "L)EAVE ?": "L) 나가기 ?",
        "F)IGHT OR L)EAVE ?": "F) 공격 또는 L) 나가기 ?",
        "F)IGHT OR L)EAVE": "F) 공격 또는 L) 나가기",
    },
    "town": {
        "#)INSPECT": "#) 점검",
        "#) INSPECT": "#) 점검",
        "I)NSPECT": "I) 캐릭터 점검",
        "I) NSPECT": "I) 캐릭터 점검",
        "INSPECT": "점검",
        "WHO (#) WILL INSPECT ?": "누구를 (#) 점검하시겠습니까?",
        "WHO (#) WILL INSPECT": "누구를 (#) 점검하시겠습니까?",
        "WHO WILL INSPECT ?": "누구를 점검하시겠습니까?",
        "WHO WILL INSPECT": "누구를 점검하시겠습니까?",
        "L↵EAVE": "↵ 나가기",
        "L↵ EAVE": "↵ 나가기",
    },
    "stairs_up": {
        "TAKE THEM (Y/N) ?": "올라가시겠습니까 (Y/N) ?",
        "TAKE THEM (Y/N)": "올라가시겠습니까 (Y/N)",
        "TAKE THEM": "올라가시겠습니까",
        "TAKE IT (Y/N) ?": "올라가시겠습니까 (Y/N) ?",
        "TAKE IT (Y/N)": "올라가시겠습니까 (Y/N)",
        "TAKE IT": "올라가시겠습니까",
    },
    "stairs_down": {
        "TAKE THEM (Y/N) ?": "내려가시겠습니까 (Y/N) ?",
        "TAKE THEM (Y/N)": "내려가시겠습니까 (Y/N)",
        "TAKE THEM": "내려가시겠습니까",
        "TAKE IT (Y/N) ?": "내려가시겠습니까 (Y/N) ?",
        "TAKE IT (Y/N)": "내려가시겠습니까 (Y/N)",
        "TAKE IT": "내려가시겠습니까",
    },
    "elevator": {
        "TAKE THEM (Y/N) ?": "탑승하시겠습니까 (Y/N) ?",
        "TAKE THEM (Y/N)": "탑승하시겠습니까 (Y/N)",
        "TAKE THEM": "탑승하시겠습니까",
        "TAKE IT (Y/N) ?": "탑승하시겠습니까 (Y/N) ?",
        "TAKE IT (Y/N)": "탑승하시겠습니까 (Y/N)",
        "TAKE IT": "탑승하시겠습니까",
    }
}


# Enemy names. JSON monsters are added in load_unified_translations.
# Item names from the JSON, filled by load_unified_translations.
ITEM_KEYS = set(KRN_ITEM_TRANSLATIONS)
DEFAULT_UI_TRANSLATIONS.update(KRN_ITEM_TRANSLATIONS)
for _alignment, _alignment_ko in (("G", "선"), ("N", "중"), ("E", "악")):
    for _class, _class_ko in (("FIG", "전사"), ("MAG", "마법"), ("PRI", "사제"),
                              ("THI", "도적"), ("BIS", "비숍"), ("SAM", "사무"),
                              ("LOR", "로드"), ("NIN", "닌자")):
        DEFAULT_UI_TRANSLATIONS[f"{_alignment}-{_class}"] = f"{_alignment_ko}-{_class_ko}"
for _k, _v in KRN_TEXT_TRANSLATIONS.items():
    DEFAULT_UI_TRANSLATIONS.setdefault(_k, _v)

MONSTER_KEYS = {
    "KIMONOED MAN", "KIMONOED MEN",
    "WEIRD HUMANOID", "WEIRD HUMANOIDS",
    "SKELETON", "SKELETONS", "SLIME", "SLIMES", "KOBOLD", "KOBOLDS",
    "ZOMBIE", "ZOMBIES", "ORC", "ORCS", "UNSEEN ENTITY",
    "SMALL HUMANOID", "SMALL HUMANOIDS", "SCRUFFY MAN", "SCRUFFY MEN",
    "UNDEAD KOBOLD", "UNDEAD KOBOLDS", "BUBBLY SLIME", "MURPHY'S GHOST",
}

_BATTLE_ACTIONS = (
    "TRIES TO TOUCH", "REACHES FOR", "GRASPS AT", "TEARS AT", "CLAWS VICIOUSLY AT",
    "BITES AT", "TRIES TO RIP APART", "POUNCES AT", "TRIES TO RAM", "ATTEMPTS TO STRANGLE",
    "KICKS AT", "LEAPS AT", "LUNGES AT", "CHARGES AT", "CHOPS SAVAGELY AT", "SWINGS AT",
    "THRUSTS HARD AT", "TRIES TO BASH", "TRIES TO SLICE", "ATTEMPTS TO STAB", "TRIES TO STOMP ON",
    "ATTEMPTS TO SMASH", "TRIES TO STING", "TRIES TO LAND ON", "ATTEMPTS TO NEEDLE",
    "TRIES TO CHEW UP", "FIRES AT", "SHOOTS AT", "TAKES AIM AT", "TRIES TO AMBUSH",
    "TRIES TO SURPRISE", "ATTEMPS TO BACKSTAB",
    "TRIES TO GNAW", "ATTEMPTS TO CHEW", "TRIES TO NIBBLE ON", "TRIES TO STAB",
    "THRUSTS VIOLENTLY AT", "ATTEMPTS TO SLICE", "CLAWS AT",   # decoded verbs 1150-1159
)
# Results the game prints only in a fight (decoded 1100-1134). Camp and temple
# results (IS CURED, HIT POINTS ARE RESTORED) are left out: those are centered there.
_BATTLE_RESULTS = ("CASTS A", "CALLS FOR HELP", "IS SLAIN", "IS HELD", "IS SILENCED", "IS SLEPT", "IS NOT SLAIN",
                   "IS NOT HELD", "IS NOT SILENCED", "IS NOT SLEPT", "IS DRAINED", "IS POISONED", "IS PARALYZED",
                   "IS STONED", "IS DECAPITATED", "RUNS AWAY", "DISPELLS", "ATTEMPTS TO DISPELL",
                   "RESISTS THE SPELL", "TRIES TO CAST A", "BREATHES ON THE PARTY",
                   "BUT CANNOT SPEAK", "BUT NOTHING HAPPENS", "CANNOT SPEAK", "SPEAK!", "HAPPENS!")
_BATTLE_ROW = ("MISSES", "KILLED", "DAMAGE", "THRUSTS", "CLAWS AT", "AND HIT", *_BATTLE_RESULTS, *_BATTLE_ACTIONS)
_BATTLE_CONTEXT_RE = re.compile(r'(?<![A-Z])(?:' + '|'.join(re.escape(p) for p in (
    *_BATTLE_ACTIONS, 'AND HITS', 'AND MISSES', 'IS KILLED!', 'IS BEHEADED!', *_BATTLE_RESULTS)) + r')(?![A-Z])')


def _has_text_run(line_text):
    """True when two letters or digits sit next to each other.

    A maze wall cell can match one font glyph. That row has no word.
    "I.Q." counts: with the spell box over the rest of its row, it was the
    only word there and the row was skipped as a picture.
    """
    if 'I.Q.' in line_text:
        return True
    # A hotkey row whose name is one letter ("D)  C" on the restart list).
    if re.search(r'(?<![A-Za-z0-9])[A-Z0-9]\) *[A-Za-z0-9]', line_text):
        return True
    # A name spelled out letter by letter ("W...E...R...D...N...A...", Wizardry 4).
    if re.search(r'[A-Z]\.{3}[A-Z]\.{3}[A-Z]|[A-Z]\*[A-Z]\*[A-Z]\*[A-Z]', line_text):   # also Wiz1's **W*E*R*D*N*A**
        return True
    run = 0
    for ch in line_text:
        if ch.isalnum():
            run += 1
            if run >= 2:
                return True
        else:
            run = 0
    return False


assert _has_text_run("  P  ") is False
assert _has_text_run("N-FIG") is True
assert _has_text_run("A SKELETON") is True
assert _has_text_run("#") is False
assert _has_text_run("    I.Q.  8 ") is True
assert _has_text_run(" D)  C ") is True
assert _has_text_run('"W...E...R...D...N...A..."') is True

# Combat prints one space between letters: "T H E", "A N D", "G A S   C L O U D".
_SPACE_GLUE = "'!.?"


def _single_spaced(line, i):
    """One combat letter, not the last letter of a normal word."""
    ch = line[i]
    if not (ch.isalpha() or ch in _SPACE_GLUE):
        return False
    if i > 0 and line[i - 1].isalnum():
        return False
    # The S of "TRAP'S A CROCK" ends a word: with the A after it, it read as spaced letters.
    if i > 1 and line[i - 1] == "'" and line[i - 2].isalnum():
        return False
    return i + 1 >= len(line) or not line[i + 1].isalnum()


def _collapse_letter_spaces(line):
    """Join a letter-spaced combat line. A normal line comes back unchanged.

    The column map points at the original cell of each kept character.
    A match then covers the gaps, so the spaced English is hidden.
    """
    n = len(line)
    out = []
    i = 0
    found = False
    while i < n:
        if line[i].isalpha() and _single_spaced(line, i):
            chars = [(line[i], i)]
            j = i + 1
            while j + 1 < n and line[j] == ' ' and _single_spaced(line, j + 1):
                chars.append((line[j + 1], j + 1))
                j += 2
            if sum(ch.isalpha() for ch, _c in chars) >= 2:
                found = True
                out.extend(chars)
                i = j
                if i < n and line[i] == ' ':
                    gap = i
                    while i < n and line[i] == ' ':
                        i += 1
                    if i < n:
                        out.append((' ', gap))
                continue
        out.append((line[i], i))
        i += 1
    if not found:
        return line, None
    squeezed = []
    scols = []
    prev_space = False
    for ch, c in out:
        if ch == ' ':
            if prev_space:
                continue
            prev_space = True
        else:
            prev_space = False
        squeezed.append(ch)
        scols.append(c)
    # "O ' WISP" is the name WILL O'WISP. Spaces beside ' ! . ? are not word gaps.
    cleaned = []
    ccols = []
    i = 0
    while i < len(squeezed):
        ch = squeezed[i]
        if ch == ' ' and i + 1 < len(squeezed) and squeezed[i + 1] in _SPACE_GLUE:
            i += 1
            continue
        cleaned.append(ch)
        ccols.append(scols[i])
        if ch in _SPACE_GLUE and i + 1 < len(squeezed) and squeezed[i + 1] == ' ':
            i += 2
            continue
        i += 1
    return ''.join(cleaned), ccols


assert _collapse_letter_spaces("T H E") == ("THE", [0, 2, 4])
assert _collapse_letter_spaces("A N")[0] == "AN"
assert _collapse_letter_spaces("A N D")[0] == "AND"
assert _collapse_letter_spaces("THE SKELETON") == ("THE SKELETON", None)
assert _collapse_letter_spaces("A SKELETON")[1] is None
assert _collapse_letter_spaces("G A S   C L O U D")[0] == "GAS CLOUD"
assert _collapse_letter_spaces("M U R P H Y ' S   G H O S T")[0] == "MURPHY'S GHOST"
assert _collapse_letter_spaces("W I L L   O '   W I S P")[0] == "WILL O'WISP"
assert _collapse_letter_spaces("F O R   6   D A M A G E")[0] == "FOR 6 DAMAGE"
assert _collapse_letter_spaces("  P  ")[1] is None
assert _collapse_letter_spaces("N-FIG")[1] is None
assert _collapse_letter_spaces("C)AMP S)TATUS I)NSPECT O)FF   A-W-D  K")[1] is None


# Sentences the game splits over several rows. Translate the whole sentence once;
# the overlay wraps the Korean words to the rows. '#' stands for a number.
SENTENCE_TRANSLATIONS = {
    # Chicken-bodied cat-headed statue room. Rows confirmed on screen (2026-11-03).
    # Silver boar statue room. Rows confirmed on screen (2026-11-03).
    # Game text from ASCII.KRN (docs/wiz1_text.txt): sentences that run over rows,
    # and sentences with a number ('#').
    "TAKES # DAMAGE": "# 피해를 입었다",
    '"CONGRATULATIONS, BRAVE ADVENTURERS!': '"축하하오, 용감한 모험가들이여!',
}
SENTENCE_TRANSLATIONS.update(_HASHED_WIZ1.get('SENTENCE', {}))

# Long dictionary keys (whole game sentences) are not shipped as text: a key of
# four words or more is stored as a hash of its words, and the screen text is
# hashed to find it. Prefixes: \x01 sentence, \x02 sentence with its numbers as
# '#', \x03 / \x04 the start / end of a sentence cut at a page break (value
# \x00 when several sentences share it). Built by the local tool hash_dict.py.
HASH_SENTENCE, HASH_TEMPLATE, HASH_HEAD, HASH_TAIL = '\x01', '\x02', '\x03', '\x04'
HASH_MIN_WORDS = 4


def text_hash(text):
    """Hash of a phrase with its spaces collapsed (what the dictionaries store)."""
    norm = re.sub(r' +', ' ', text.strip())
    return hashlib.sha1(norm.encode('utf-8')).hexdigest()[:16].upper()


@lru_cache(maxsize=4096)
def _hash_candidates(view):
    """[(phrase, sentence hash, number-template hash, numbers)] for the word spans
    of a screen row with four words or more. A span starts and ends where a word
    starts and ends; punctuation and a window edge may sit outside it."""
    parts = list(re.finditer(r' +|[^ ]', view))
    text = ''.join(' ' if m.group()[0] == ' ' else m.group() for m in parts)
    n = len(text)
    starts = [i for i in range(n) if text[i] != ' ' and (i == 0 or not text[i - 1].isalnum())
              and (i == 0 or text[i - 1] != text[i] or not text[i].isalnum())]
    ends = [j for j in range(1, n + 1) if text[j - 1] != ' ' and (j == n or not text[j].isalnum())]
    out = []
    for i in starts:
        for j in ends:
            if j <= i:
                continue
            phrase = text[i:j].strip()
            if phrase.count(' ') < HASH_MIN_WORDS - 1:
                continue
            nums = re.findall(r'\d+', phrase)
            # The screen text with its own spacing, so it is found in the row.
            out.append((view[parts[i].start():parts[j - 1].end()], text_hash(phrase),
                        text_hash(re.sub(r'\d+', '#', phrase)) if nums else None, nums))
    return out


_STAT_LABELS = ("STRENGTH", "I.Q.", "PIETY", "VITALITY", "AGILITY", "LUCK")
_template_cache = {}


def _number_templates(extra=None):
    """[(key, regex, korean)] for keys with '#' (a number on screen)."""
    cache_key = (len(SENTENCE_TRANSLATIONS), id(extra), len(extra) if extra else 0)
    hit = _template_cache.get(cache_key)
    if hit is not None:
        return hit
    out = []
    # Menu keys use a literal '(#)' prompt.
    for key, value in list(SENTENCE_TRANSLATIONS.items()) + list((extra or {}).items()):
        # '$' is a name slot in the game text, but these spots are numbers.
        if '$' in key and re.search(r'1-\$\)|LEVEL \$|\$ G\.P\.', key):
            key, value = key.replace('$', '#'), value.replace('$', '#')
        if '#' not in key or '(#)' in key or value.count('#') != key.count('#'):
            continue
        if not re.search(r'[A-Z]{2}', key):
            continue
        body = r' +'.join(re.escape(w).replace('\\#', r'(\d+)').replace('#', r'(\d+)') for w in key.split())
        out.append((key, re.compile(r'(?<![A-Z0-9])' + body + r'(?![A-Z0-9])'), value))
    if len(_template_cache) > 16:
        _template_cache.clear()
    _template_cache[cache_key] = out
    return out


_CLASS_WORD = re.compile(r'\b(?:FIGHTER|MAGE|PRIEST|THIEF|BISHOP|SAMURAI|LORD|NINJA)\b')
_lookup_cache = {}


def _sentence_lookup(translations, cache_key=None):
    """Exact dictionary key first, then the same sentence with its numbers as '#'."""
    cache_key = cache_key or (id(translations), len(translations))
    hit = _lookup_cache.get(cache_key)
    if hit is not None:
        return hit
    exact = {}
    templates = {}
    hashed = {HASH_SENTENCE: {}, HASH_TEMPLATE: {}, HASH_HEAD: {}, HASH_TAIL: {}}
    for key, value in list(translations.items()) + list(SENTENCE_TRANSLATIONS.items()):
        if key[:1] in hashed:
            if isinstance(value, str):
                table = hashed[key[0]]
                if key[0] in (HASH_HEAD, HASH_TAIL) and table.get(key[1:], value) != value:
                    value = '\x00'   # another file's sentence shares this start or end
                table.setdefault(key[1:], value)
            continue
        # '?' inside a word is an old OCR copy; a question mark ending a
        # sentence (before a quote, a space or the end) is a real one.
        if not isinstance(value, str) or not value or re.search(r'\?(?![\s"]|$)', key):
            continue
        norm = re.sub(r' +', ' ', key.strip())
        if '#' in norm:
            templates.setdefault(norm, value)
            continue
        exact.setdefault(norm, value)
        nums = re.findall(r'\d+', norm)
        # "YOU GAINED 5 HIT POINTS." -> "YOU GAINED # HIT POINTS." when the value
        # carries the same numbers in the same order.
        if nums and len(set(nums)) == len(nums) and re.findall(r'\d+', value) == nums:
            templates.setdefault(re.sub(r'\d+', '#', norm), re.sub(r'\d+', '#', value))

    def lookup(text):
        if text in exact:
            return exact[text]
        value = hashed[HASH_SENTENCE].get(text_hash(text)) if text.count(' ') >= HASH_MIN_WORDS - 1 else None
        if value:
            return value
        nums = re.findall(r'\d+', text)
        if not nums:
            return None
        value = templates.get(re.sub(r'\d+', '#', text))
        if value is None and text.count(' ') >= HASH_MIN_WORDS - 1:
            value = hashed[HASH_TEMPLATE].get(text_hash(re.sub(r'\d+', '#', text)))
        if value is None or value.count('#') != len(nums):
            return None
        for n in nums:
            value = value.replace('#', n, 1)
        return value

    heads = sorted(exact)
    tails = sorted(k[::-1] for k in exact)

    def cut(text, tail_of_key):
        """Korean of the one sentence the message window cut at a page break.

        text is the start of a key (tail_of_key False) or its end, and the cut
        falls between two words. At least two words, and every such key must
        share one translation, or None.
        """
        if ' ' not in text or len(text) < 8:
            return None
        keys, probe = (tails, text[::-1]) if tail_of_key else (heads, text)
        values = set()
        part = hashed[HASH_TAIL if tail_of_key else HASH_HEAD].get(text_hash(text))
        if part is not None:
            values.add(part)
        i = bisect.bisect_left(keys, probe)
        while i < len(keys) and keys[i].startswith(probe):
            key = keys[i]
            i += 1
            if len(key) > len(probe) and key[len(probe)] == ' ':
                values.add(exact[key[::-1] if tail_of_key else key])
        values.discard(None)
        return values.pop() if len(values) == 1 and '\x00' not in values else None

    lookup.cut = cut
    if len(_lookup_cache) > 16:
        _lookup_cache.clear()
    _lookup_cache[cache_key] = lookup
    return lookup


def _row_prose(line):
    """Plain sentence text of a row and its screen columns, or None.

    Menus (hotkeys), unknown glyphs and inner window edges are not prose.
    """
    text, mapping = _collapse_letter_spaces(line['text'])
    # An unknown glyph reads as '?'. A real question mark (real_q) is prose:
    # "WHICH WAY SEEMS BEST, RIGHT OR LEFT?" kept the whole paragraph English.
    real_q = line.get('real_q') or ()
    if SENTINEL_CHAR in text or any(
            ch == '?' and (mapping[i] if mapping else i) not in real_q for i, ch in enumerate(text)):
        return None
    start = len(text) - len(text.lstrip(' ' + FRAME_CHAR))
    end = len(text.rstrip(' ' + FRAME_CHAR))
    text, mapping = text[start:end], (mapping[start:end] if mapping else list(range(start, end)))
    if not text or FRAME_CHAR in text or re.search(r'\b[A-Z0-9]\)', text):
        return None
    if '↵' in text and not re.search(r'[.!?]\s+PRESS ↵', text):
        return None
    parts = list(re.finditer(r' +|[^ ]', text))
    return (''.join(' ' if p.group()[0] == ' ' else p.group() for p in parts),
            [mapping[p.start()] for p in parts])


def _translate_joined(joined, row_ends, lookup, head=False, tail=False):
    """Cover the joined rows with translated sentences.

    Sentences end after . ! ? or at a row end. Fewest pieces wins. Returns the
    Korean, or None when a piece is unknown or no piece crosses a row.
    The window holds 13 rows, so a long message is cut mid-sentence. With tail
    the last piece may be the start of a known sentence and takes its whole
    Korean. With head the first piece may be its end: that page only covers
    it, so the sentence is not shown twice.
    """
    cuts = sorted({0, len(joined)} | set(row_ends)
                  | {m.end() for m in re.finditer(r'[.!?](?= )', joined)})
    best = {0: (0, [])}
    for i, start in enumerate(cuts):
        if start not in best:
            continue
        for end in cuts[i + 1:]:
            piece = joined[start:end].strip()
            # Class names keep sheet and roster rows out; a finished sentence
            # ("...LORD HAWKWIND FALL TO THE STAB OF A LOWLY DINK!") is prose.
            if not piece or (_CLASS_WORD.search(piece) and not re.search(r'[.!?]"?$', piece)):
                continue
            korean = lookup(piece)
            extra = 0
            if korean is None and tail and end == len(joined):
                korean, extra = lookup.cut(piece, False), 1
            if korean is None and head and start == 0 and lookup.cut(piece, True) is not None:
                korean, extra = '', 1   # shown whole on the page before: only cover the English
            if korean is None:
                continue
            # A cut sentence counts like a crossing one: the rest of it is on
            # the other page, so a one-row block may hold it.
            crosses = any(start < r < end for r in row_ends) or extra
            score = best[start][0] + 1 + extra
            if end not in best or score < best[end][0]:
                best[end] = (score, best[start][1] + [(korean, crosses)])
    done = best.get(len(joined))
    if not done or not any(crosses for _k, crosses in done[1]):
        return None
    return ' '.join(k for k, _c in done[1] if k)


def _paragraph_matches(lines, translations, reserved, cache_key=None):
    """Translate sentences that run over adjacent rows as one sentence.

    Returns {row: ((lo, hi), english, korean_part)} and {row: (first_row, korean)}.
    The overlay wraps the whole Korean over the rows by word; korean_part is
    only a width estimate for when that does not fit.
    """
    rows = {line['y']: line for line in lines}
    lookup = _sentence_lookup(translations, cache_key)
    found, para = {}, {}
    ys = sorted(rows)
    i = 0
    while i < len(ys):
        run = []
        y = ys[i]
        while y in rows and y not in reserved:
            item = _row_prose(rows[y])
            if not item:
                break
            run.append((y, *item))
            y += 8
        i += max(1, len(run))
        # Longest block first, then shorter blocks inside the run.
        taken = set()
        for size in range(len(run), 0, -1):
            for lo in range(0, len(run) - size + 1):
                block = run[lo:lo + size]
                if any(r[0] in taken for r in block):
                    continue
                joined, row_ends = '', []
                for _y, text, _cols in block:
                    joined = (joined + ' ' + text) if joined else text
                    row_ends.append(len(joined))
                # Only the ends of the whole run can be a page break.
                korean = _translate_joined(joined, row_ends[:-1], lookup,
                                           head=lo == 0, tail=lo + size == len(run))
                if korean is None:
                    continue
                words = korean.split()
                for row, text, cols in block:
                    border = rows[row]['text'].rfind(FRAME_CHAR)
                    limit = border if border >= cols[-1] + 1 else 40
                    room = (limit - cols[0]) * 8
                    part = []
                    while words and _ko_width(' '.join(part + [words[0]])) <= room:
                        part.append(words.pop(0))
                    if row == block[-1][0] and words:
                        part += words
                        words = []
                    found[row] = ((cols[0], cols[-1] + 1), joined, ' '.join(part))
                    para[row] = (block[0][0], korean)
                    taken.add(row)
    return found, para


def _ko_width(text):
    """Rough CGA pixel width: Korean is two cells, ASCII one."""
    return sum(8 if ord(ch) < 128 else 16 for ch in text)


assert _translate_joined("YOU NEED 1000 MORE E.P. TO MAKE THE NEXT LEVEL.", [18],
                         _sentence_lookup({})) == "다음 레벨까지 경험치가 1000 더 필요합니다."


def battle_line_mark(orig):
    u = (orig or "").upper()
    return any(k in u for k in _BATTLE_ROW)


def combat_emphasis(orig, is_char_name, is_raw, battle_line, context, monster_keys=None):
    """Names, monsters, miss, death, and damage on a fight line."""
    if context != "combat" and not battle_line:
        return False
    u = (orig or "").upper()
    if "MISSES" in u or "KILLED" in u or "DAMAGE" in u:
        return True
    if u in ("DEAD", "DEAD!") or u.endswith(" DEAD") or u.endswith(" DEAD!"):
        return True
    if u in (MONSTER_KEYS if monster_keys is None else monster_keys):
        return True
    if is_char_name:
        return True
    if not (battle_line and is_raw):
        return False
    # The damage figure is its own cell when a longer phrase already took "FOR".
    return bool(re.fullmatch(r"[A-Z][A-Z']*", u) or u.isdigit())


assert combat_emphasis("AND MISSES", False, False, True, None)
assert combat_emphasis("IS KILLED!", False, False, False, "combat")
assert combat_emphasis("FOR 6 DAMAGE", False, False, False, "combat")
assert combat_emphasis("DUKE", True, True, False, "combat")
assert not combat_emphasis("DUKE", True, True, False, "town")
assert combat_emphasis("DUKE", False, True, True, None)
assert not combat_emphasis("N-FIG", False, True, True, "combat")
assert not combat_emphasis("FIGHT", False, False, False, "combat")
assert combat_emphasis("SKELETON", False, False, False, "combat")
assert not combat_emphasis("SKELETON", False, False, False, None)
assert not combat_emphasis("DEADLY RING", False, False, False, "combat")
assert combat_emphasis("6", False, True, True, None)
assert not combat_emphasis("16", False, True, False, "combat")


def screen_item_keys(items):
    """Item names as the screen shows them, added to a per-game item dict.

    The game draws "POTION OF " / "SCROLL OF " as an icon glyph (Ⓟ / Ⓢ) and
    " OF " as the "of" ligature (~). The decoded text writes those x, y and w
    ("xwPORFIC"). The 1-3 base dictionary gets these keys in
    load_unified_translations; the Wizardry 2-4 dictionaries did not, so a
    potion only those games have ("Ⓟ~PORFIC") stayed English.
    """
    out = dict(items)
    for key, value in items.items():
        if not isinstance(value, str):
            continue
        screen = re.sub(r'^([?]?)x(?=w|[A-Z])', r'\1Ⓟ', key)
        screen = re.sub(r'^([?]?)y(?=w|[A-Z])', r'\1Ⓢ', screen)
        screen = re.sub(r'^([?]?)X(?=~)', r'\1Ⓟ', screen)
        screen = re.sub(r'^([?]?)Y(?=~)', r'\1Ⓢ', screen)
        screen = re.sub(r'(?<=[A-ZⓅⓈ])w(?=[A-Z])', '~', screen)
        for word, icon in (("POTION OF ", "Ⓟ~"), ("SCROLL OF ", "Ⓢ~")):
            if screen.startswith(word):
                screen = icon + screen[len(word):]
        screen = screen.replace(" OF ", "~")
        out.setdefault(screen, value)
    return out


assert screen_item_keys({"xwPORFIC": "a", "POTION OF LATUMOFIS": "b", "RINGwPORFIC": "c"}) == {
    "xwPORFIC": "a", "Ⓟ~PORFIC": "a", "POTION OF LATUMOFIS": "b", "Ⓟ~LATUMOFIS": "b",
    "RINGwPORFIC": "c", "RING~PORFIC": "c"}


_UNIDENTIFIED_BARE = ('AMULET', 'ARMOR', 'CHAIN', 'CLOTHING', 'GLOVES', 'KEY', 'RIBBON', 'RING', 'ROD',
                       'SHIELD', 'STARS', 'STATUE', 'SWORD')


SPELL_CUT_KEYS = set()   # first six letters of longer spell names (party list only)


def load_unified_translations(json_path=None):
    """
    Loads translations from JSON file and merges with default UI translations.
    Sorts keys by length descending to match longest phrases first.
    """
    trans = DEFAULT_UI_TRANSLATIONS.copy()
    spell_cuts = {}

    if json_path and os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for category, items in data.items():
                if isinstance(items, dict):
                    for k, v in items.items():
                        ko = v.get('ko') if isinstance(v, dict) else str(v)
                        if ko:
                            clean_ko = ko.split(' (')[0].strip()
                            clean_ko = clean_ko.replace("소형 방패", "방패").replace("강철 투구", "투구")
                            k_up = k.upper()
                            trans[k_up] = clean_ko
                            if category == 'spells' and len(k_up) > 6:
                                spell_cuts.setdefault(k_up[:6], set()).add(clean_ko)
                            if category == 'items':
                                ITEM_KEYS.add(k_up)
                                for word, icon in (("POTION OF ", "Ⓟ~"), ("SCROLL OF ", "Ⓢ~")):
                                    if k_up.startswith(word):
                                        trans[icon + k_up[len(word):]] = clean_ko
                                        ITEM_KEYS.add(icon + k_up[len(word):])
                                if " OF " in k_up:
                                    k_lig = k_up.replace(" OF ", "~")
                                    trans[k_lig] = clean_ko
                                    ITEM_KEYS.add(k_lig)
                                    for suffix in ('+1', '+2', '+3', '-1', '-2', '-3'):
                                        trans[f"{k_lig}{suffix}"] = f"{clean_ko}{suffix}"
                                for suffix in ('+1', '+2', '+3', '-1', '-2', '-3'):
                                    trans[f"{k_up}{suffix}"] = f"{clean_ko}{suffix}"
                            elif category == 'monsters':
                                MONSTER_KEYS.add(k_up)
                                if not k_up.endswith('S'):
                                    trans[f"{k_up}S"] = clean_ko
                                    trans[f"{k_up}ES"] = clean_ko
                                    MONSTER_KEYS.add(k_up + "S")
                                    MONSTER_KEYS.add(k_up + "ES")
                elif isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict) and 'name' in item and 'ko' in item:
                            clean_ko = item['ko'].split(' (')[0].strip()
                            clean_ko = clean_ko.replace("소형 방패", "방패").replace("강철 투구", "투구")
                            k_up = item['name'].upper()
                            trans[k_up] = clean_ko
                            if " OF " in k_up:
                                k_lig = k_up.replace(" OF ", "~")
                                trans[k_lig] = clean_ko
                                for suffix in ('+1', '+2', '+3', '-1', '-2', '-3'):
                                    trans[f"{k_lig}{suffix}"] = f"{clean_ko}{suffix}"
                            for suffix in ('+1', '+2', '+3', '-1', '-2', '-3'):
                                trans[f"{k_up}{suffix}"] = f"{clean_ko}{suffix}"
        except Exception as e:
            print(f"[CGATextExtractor] Error loading {json_path}: {e}")

    # The party list shows the spell a member will cast in six cells ("MASOPI").
    for cut, names in spell_cuts.items():
        if len(names) == 1 and cut not in trans:
            trans[cut] = next(iter(names))
            SPELL_CUT_KEYS.add(cut)

    # An equipped item shows '*' in the mark column, so an unidentified one shows
    # its bare generic name ("6)*ARMOR"). Only unidentified items use these names.
    for name in _UNIDENTIFIED_BARE:
        if '?' + name in trans:
            trans[name] = trans['?' + name]
            ITEM_KEYS.add(name)

    # Return dict sorted by key length descending
    return dict(sorted(trans.items(), key=lambda x: len(x[0]), reverse=True))


def project_dir():
    """Project root: the script's folder, or the parent of dist for the exe.

    Logs and saved map data live here so they stay in one place.
    """
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
        if os.path.basename(base).lower() == 'dist':
            return os.path.dirname(base)
        return base
    return os.path.dirname(os.path.abspath(__file__))


def dev_path(folder, name):
    """Developer output in a folder under the project root, made on first use."""
    path = os.path.join(project_dir(), folder)
    os.makedirs(path, exist_ok=True)
    return os.path.join(path, name)


class UntranslatedLogger:
    """
    Automatically logs untranslated English text appearing on the DOSBox CGA screen.
    Writes clean, deduplicated, and ready-to-translate entries to untranslated_strings.log.
    """
    def __init__(self):
        self.seen_phrases = set()
        self.log_files = []
        self._init_log_files()

    def _init_log_files(self):
        # One log in the project logs folder, also for the exe in dist\.
        self.log_files.append(dev_path("logs", "untranslated_strings.log"))

        for lf in self.log_files:
            if os.path.exists(lf):
                try:
                    with open(lf, 'r', encoding='utf-8') as f:
                        for line in f:
                            if 'Phrase: "' in line:
                                phrase = line.split('Phrase: "')[1].split('"')[0]
                                if phrase:
                                    self.seen_phrases.add(phrase)
                except Exception:
                    pass

    def log_untranslated(self, line_text, y, occupied_cols):
        # Ignore character names on party member list rows
        is_party_row = bool(re.match(r'^\s*[1-6]\s+[A-Za-z]', line_text))

        chars = []
        for col, c in enumerate(line_text):
            if col in occupied_cols or c == FRAME_CHAR:
                chars.append(' ')
            elif is_party_row and 2 <= col <= 18:
                chars.append(' ')
            else:
                chars.append(c)
        masked_line = "".join(chars)

        raw_chunks = re.split(r'\s{2,}', masked_line)
        for chunk in raw_chunks:
            chunk = chunk.strip()
            if not chunk or len(chunk) < 2:
                continue
            if not re.search(r'[A-Za-z]', chunk):
                continue

            cleaned = re.sub(r'^\d+\)\s*\*?\s*', '', chunk)
            cleaned = re.sub(r'^\d+\s+', '', cleaned).strip()
            if not cleaned or len(cleaned) < 2:
                continue
            if not re.search(r'[A-Za-z]', cleaned):
                continue

            if cleaned in self.seen_phrases:
                continue

            self.seen_phrases.add(cleaned)
            self._write_entry(cleaned, line_text.strip(), y)

    def _write_entry(self, phrase, full_line, y):
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = (
            f"[{now_str}] [Y={y:3d}]\n"
            f'  Phrase: "{phrase}"\n'
            f'  Line:   "{full_line}"\n'
            f'  JSON:   "{phrase}": "",\n'
            f"--------------------------------------------------------------------------------\n"
        )
        for lf in self.log_files:
            try:
                new_file = not os.path.exists(lf) or os.path.getsize(lf) == 0
                with open(lf, 'a', encoding='utf-8') as f:
                    if new_file:
                        f.write(
                            "================================================================================\n"
                            " Wizardry 1 Korean Overlay - Untranslated English Strings Log\n"
                            " (번역되지 않은 게임 내 영문 텍스트가 자동으로 수집되어 기록됩니다)\n"
                            "================================================================================\n\n"
                        )
                    f.write(entry)
            except Exception:
                pass


class CGATextExtractor:
    def __init__(self, hook=None, glyphs=None, translation_dict=None):
        self.hook = hook
        self.number_templates = None
        self.monster_keys = MONSTER_KEYS.copy()
        self.item_keys = ITEM_KEYS.copy()
        self.equipped_unidentified = set()
        self.glyphs = glyphs or FONT_GLYPHS.copy()
        raw_dict = translation_dict or DEFAULT_UI_TRANSLATIONS.copy()
        self.translations = dict(sorted(raw_dict.items(), key=lambda x: len(x[0]), reverse=True))
        self.unmapped_glyphs = {}
        self.untranslated_logger = None if RELEASE else UntranslatedLogger()
        self._glyph_cache = {int(hx, 16): ch for hx, ch in self.glyphs.items()}
        self._glyph_cache[0] = ' '
        self._real_q_glyphs = {acc for acc, ch in self._glyph_cache.items() if ch == '?'}
        self._restore_cga = {}
        for hx, ch in self.glyphs.items():
            if ch != ' ' and ch not in self._restore_cga:
                self._restore_cga[ch] = _cga_from_glyph_hex(hx)
        self.reset_blank_shadow()

    def update_translations(self, translation_dict):
        self.translations = dict(sorted(translation_dict.items(), key=lambda x: len(x[0]), reverse=True))

    def update_glyphs(self, glyphs):
        self.glyphs = glyphs.copy()
        self._glyph_cache = {int(hx, 16): ch for hx, ch in glyphs.items()}
        self._glyph_cache[0] = ' '
        self._real_q_glyphs = {acc for acc, ch in self._glyph_cache.items() if ch == '?'}
        if self.hook is not None:
            self.hook._cga_glyphs = self.glyphs
        self.reset_blank_shadow()

    @staticmethod
    def verify_word_at(cga_buf, word, row, col):
        """Verifies if the specified ASCII word exists at character grid (row, col) in cga_buf."""
        if len(cga_buf) < 16384:
            return False
        y = row * 8
        for i, expected_char in enumerate(word):
            col_idx = col + i
            if col_idx >= 40:
                return False
            glyph_bytes = bytearray(8)
            for dy in range(8):
                line_y = y + dy
                b_offset = (line_y % 2) * 8192 + (line_y // 2) * 80 + (col_idx * 2)
                if b_offset + 1 >= len(cga_buf):
                    return False
                b0 = cga_buf[b_offset]
                b1 = cga_buf[b_offset + 1]
                bits = 0
                for shift in (6, 4, 2, 0):
                    bits = (bits << 1) | (1 if ((b0 >> shift) & 3) else 0)
                for shift in (6, 4, 2, 0):
                    bits = (bits << 1) | (1 if ((b1 >> shift) & 3) else 0)
                glyph_bytes[dy] = bits
            gh = bytes(glyph_bytes).hex()
            char = FONT_GLYPHS.get(gh)
            if char != expected_char:
                return False
        return True

    def read_video_memory(self):
        """Reads 16KB CGA framebuffer directly from DOSBox process memory."""
        if not self.hook or not self.hook.handle:
            return None

        vaddr = getattr(self.hook, '_video_address', None) or getattr(self.hook, '_trade_video_address', None)
        if not vaddr:
            from wiz_screen import find_cga_video_address
            vaddr = find_cga_video_address(self.hook)
            if not vaddr:
                return None

        from wiz_hook import kernel32
        buf = ctypes.create_string_buffer(16384)
        count = ctypes.c_size_t()
        if kernel32.ReadProcessMemory(self.hook.handle, ctypes.c_void_p(vaddr),
                                      buf, 16384, ctypes.byref(count)):
            return buf.raw[:count.value]
        return None

    def reset_blank_shadow(self):
        """Drop remembered text. The CGA buffer is left as it is."""
        self._shadow = None
        self._owned = None
        self._picture = None
        self._frame_cells = set()
        self._text_count = 0
        self._shown = None

    def _decode_grid(self, video_bytes):
        rows = []
        real_qs = []
        cursors = []   # the input cursor reads as a space; character creation needs where it is
        pix = _PIX4
        cache = self._glyph_cache
        for row in range(25):
            half = row * 4 * 80
            row_chars = []
            real_q = set()
            for col in range(40):
                acc = 0
                col_off = half + col * 2
                for half_i in range(4):
                    off = col_off + half_i * 80
                    acc = (acc << 8) | ((pix[video_bytes[off]] << 4) | pix[video_bytes[off + 1]])
                    off += 8192
                    acc = (acc << 8) | ((pix[video_bytes[off]] << 4) | pix[video_bytes[off + 1]])
                if acc == _SENTINEL_ACC:
                    ch = SENTINEL_CHAR
                elif acc in _FOG_ACC:
                    ch = ' '
                    if acc == _CURSOR_ACC:
                        cursors.append((row, col))
                else:
                    ch = cache.get(acc)
                if ch is None:
                    glyph_bytes = acc.to_bytes(8, 'big')
                    if is_frame_glyph(glyph_bytes):
                        ch = FRAME_CHAR
                    else:
                        ch = '?'
                        gh = glyph_bytes.hex()
                        self.unmapped_glyphs[gh] = self.unmapped_glyphs.get(gh, 0) + 1
                    cache[acc] = ch
                elif acc in self._real_q_glyphs:
                    # Genuine question-mark glyph (prompts, unidentified items like ?SWORD)
                    real_q.add(col)
                row_chars.append(ch)
            rows.append(row_chars)
            real_qs.append(real_q)
        self.cursor_cells = tuple(cursors)
        return rows, real_qs

    def _lines_from_grid(self, rows, real_qs):
        detected_lines = []
        for row_i, row_chars in enumerate(rows):
            letter_count = 0
            for ch in row_chars:
                if ch.isalnum():
                    letter_count += 1
            # A bracket is text. A row that is only '>' was dropped, then the
            # blank mark was the only thing left on screen.
            if letter_count < 1 and '<' not in row_chars and '>' not in row_chars:
                continue
            y = row_i * 8
            line_str = "".join(row_chars)
            real_q = real_qs[row_i]
            words = []
            in_word = False
            start_col = 0
            for col, c in enumerate(row_chars):
                if c != ' ' and c != '?' and c != FRAME_CHAR and c != SENTINEL_CHAR:
                    if not in_word:
                        in_word = True
                        start_col = col
                elif in_word:
                    in_word = False
                    w_str = line_str[start_col:col]
                    if any(char.isalnum() for char in w_str):
                        words.append({
                            'word': w_str,
                            'col': start_col,
                            'x': start_col * 8,
                            'y': y,
                            'w': (col - start_col) * 8,
                            'h': 8
                        })
            if in_word:
                w_str = line_str[start_col:40]
                if any(char.isalnum() for char in w_str):
                    words.append({
                        'word': w_str,
                        'col': start_col,
                        'x': start_col * 8,
                        'y': y,
                        'w': (40 - start_col) * 8,
                        'h': 8
                    })
            detected_lines.append({
                'y': y,
                'text': line_str,
                'words': words,
                'real_q': real_q
            })
        return detected_lines

    def scan_screen(self, video_bytes=None):
        """
        Scans CGA VRAM (320x200) across all 25 rows (8x8 character grid)
        and extracts all recognized text rows and words with exact coordinates.
        """
        if video_bytes is None:
            video_bytes = self.read_video_memory()
        if not video_bytes or len(video_bytes) < 16384:
            return []
        rows, real_qs = self._decode_grid(video_bytes)
        return self._lines_from_grid(rows, real_qs)

    def _mask_text(self, video, extra):
        """Picture with remembered blanks and this frame's new letters removed."""
        pic = bytearray(video[:16384])
        owned = self._owned
        if owned:
            for r in range(25):
                row = owned[r]
                for c in range(40):
                    if row[c]:
                        _zero_cell(pic, r, c)
        for r, c in extra:
            _zero_cell(pic, r, c)
        return pic

    def _picture_diff(self, video, fresh, frames):
        """Bytes that changed besides remembered blanks and window borders.

        A border that appears on the next read used to look like a new screen
        and threw away letters that had already been blanked.
        """
        masked = self._mask_text(video, fresh)
        old = bytearray(self._picture)
        # The blank mark lives in owned cells. It is not a picture change.
        owned = self._owned
        if owned:
            for r in range(25):
                row = owned[r]
                for c in range(40):
                    if row[c]:
                        _zero_cell(old, r, c)
        for r, c in frames:
            _zero_cell(masked, r, c)
            _zero_cell(old, r, c)
        for r, c in self._frame_cells:
            _zero_cell(masked, r, c)
            _zero_cell(old, r, c)
        return _byte_diff(masked, old, _SCENE_RESET_BYTES)

    def _compose_grid(self, rows, real_qs):
        """Shadow text, plus borders. Unknown '?' hides a letter only if we never read one."""
        composed = []
        real_out = []
        shadow = self._shadow
        for r in range(25):
            line = []
            rq = set()
            src_q = real_qs[r]
            for c in range(40):
                ch = rows[r][c]
                s = shadow[r][c]
                # A border still splits words. An unknown '?' on a cell we
                # already read must not hide that letter, or "B)OLTAC" becomes
                # "C'S TRADING POST" and the dictionary misses.
                if ch == FRAME_CHAR or (ch == '?' and c not in src_q and s == ' '):
                    line.append(ch)
                else:
                    line.append(s)
                    if s == '?':
                        rq.add(c)
            composed.append(line)
            real_out.append(rq)
        return composed, real_out

    def _write_cells(self, buf, cells):
        """Write only the listed cells into the CGA buffer the overlay reads."""
        hook = self.hook
        if not cells or not hook or not hook.handle:
            return False
        vaddr = getattr(hook, '_video_address', None) or getattr(hook, '_trade_video_address', None)
        if not vaddr:
            return False
        by_row = [[] for _ in range(25)]
        for r, c in cells:
            by_row[r].append(c)
        ranges = []
        for r, cols in enumerate(by_row):
            if not cols:
                continue
            cols.sort()
            span_s = prev = cols[0]
            spans = []
            for c in cols[1:]:
                if c == prev + 1:
                    prev = c
                else:
                    spans.append((span_s, prev))
                    span_s = prev = c
            spans.append((span_s, prev))
            y = r * 8
            for c0, c1 in spans:
                nbytes = (c1 - c0 + 1) * 2
                for dy in range(8):
                    line = y + dy
                    off = (line % 2) * 8192 + (line // 2) * 80 + c0 * 2
                    ranges.append((off, nbytes))
        from wiz_hook import kernel32
        for off, nbytes in ranges:
            chunk = (ctypes.c_char * nbytes).from_buffer_copy(buf[off:off + nbytes])
            written = ctypes.c_size_t()
            ok = kernel32.WriteProcessMemory(
                hook.handle, ctypes.c_void_p(vaddr + off), chunk, nbytes, ctypes.byref(written)
            )
            if not ok or written.value != nbytes:
                return False
        return True

    def remember_shown_text(self, video_bytes):
        """Remember recognized text. Does not write the framebuffer.

        The overlay's black rectangle is what hides the English. A blank
        written over a game letter removes that letter.
        A space is what the game writes when it erases a line, and that
        drops the memory.
        """
        if not video_bytes or len(video_bytes) < 16384:
            return []
        rows, real_qs = self._decode_grid(video_bytes)
        fresh = []
        frames = set()
        for r in range(25):
            rq = real_qs[r]
            for c in range(40):
                ch = rows[r][c]
                if ch == FRAME_CHAR:
                    frames.add((r, c))
                elif _is_text_char(ch, c, rq):
                    fresh.append((r, c))
        diff = 0
        if self._shadow is not None and self._picture is not None:
            diff = self._picture_diff(video_bytes, fresh, frames)
        # The next menu line is not a new screen. Earlier lines are already
        # zeros in VRAM, so they show up only in the shadow. Replacing the
        # shadow whenever a new line arrived kept one line and dropped the rest.
        full = self._shadow is None or diff >= _SCENE_RESET_BYTES
        if full:
            prev_shadow = self._shadow
            prev_owned = self._owned
            shadow = [[' '] * 40 for _ in range(25)]
            owned = [bytearray(40) for _ in range(25)]
            for r, c in fresh:
                shadow[r][c] = rows[r][c]
                owned[r][c] = 1
            # A large picture change is not the game erasing a letter. The
            # erase is a zero. A cell that still holds our mark keeps its letter
            # unless that word was rewritten or a frame cut the sentence.
            if prev_shadow is not None and prev_owned is not None:
                for r in range(25):
                    old_chars = prev_shadow[r]
                    old_start = None
                    old_end = -1
                    for c in range(40):
                        if old_chars[c] != ' ':
                            if old_start is None:
                                old_start = c
                            old_end = c
                    if old_start is not None:
                        blocked = False
                        for fr, fc in frames:
                            if fr == r and old_start < fc < old_end:
                                blocked = True
                                break
                        if blocked:
                            continue
                    rq = real_qs[r]
                    live_cols = [
                        c for c in range(40) if _is_text_char(rows[r][c], c, rq)
                    ]
                    rewritten = _rewritten_word_cells(old_chars, rows[r], live_cols)
                    for c in range(40):
                        if shadow[r][c] != ' ' or not prev_owned[r][c]:
                            continue
                        if c in rewritten or rows[r][c] != SENTINEL_CHAR:
                            continue
                        shadow[r][c] = old_chars[c]
                        owned[r][c] = 1
            self._shadow = shadow
            self._owned = owned
        else:
            shadow = self._shadow
            owned = self._owned
            for r in range(25):
                old_chars = shadow[r][:]
                old_start = None
                old_end = -1
                for c in range(40):
                    if old_chars[c] != ' ':
                        if old_start is None:
                            old_start = c
                        old_end = c
                new_cols = []
                rq = real_qs[r]
                for c in range(40):
                    if _is_text_char(rows[r][c], c, rq):
                        new_cols.append(c)
                new_start = new_cols[0] if new_cols else None
                new_end = new_cols[-1] if new_cols else -1
                for c in range(40):
                    ch = rows[r][c]
                    if _is_text_char(ch, c, rq):
                        shadow[r][c] = ch
                        owned[r][c] = 1
                    elif ch == FRAME_CHAR and owned[r][c]:
                        # A border drawn over a letter replaces it. A half-drawn
                        # glyph or cursor is an unknown '?' and must stay stored.
                        shadow[r][c] = ' '
                        owned[r][c] = 0
                    elif ch == ' ' and owned[r][c]:
                        # Our blank leaves a mark. A real space means the game
                        # erased this cell (the disk prompt, the loading line).
                        shadow[r][c] = ' '
                        owned[r][c] = 0
                    elif ch == ' ':
                        shadow[r][c] = ' '
                    elif (ch == '?' and c not in rq and owned[r][c]
                          and '>' in rows[r][:c]
                          and all(_held_blank(rows[r][k]) for k in range(c + 1, 40))):
                        # The input cursor ('>NAME' + unknown shape at the end)
                        # sits where a deleted letter was. Keep that letter and
                        # it stays on screen after backspace.
                        shadow[r][c] = ' '
                        owned[r][c] = 0
                # A remembered letter under an unknown shape stays only while
                # another letter of its word is still on screen (a box over
                # part of a sentence). When the rest of the word is gone, the
                # shape is the maze drawn where a message used to be; keeping
                # the letter painted a stray "I" or "N" over the picture.
                c = 0
                while c < 40:
                    if shadow[r][c] == ' ':
                        c += 1
                        continue
                    start = c
                    while c < 40 and shadow[r][c] != ' ':
                        c += 1
                    if not any(_is_text_char(rows[r][k], k, rq) for k in range(start, c)):
                        for k in range(start, c):
                            if owned[r][k] and not _is_text_char(rows[r][k], k, rq):
                                shadow[r][k] = ' '
                                owned[r][k] = 0
                cut = False
                if old_start is not None and not new_cols:
                    # A window edge through a sentence the game already
                    # finished (NOW LOADING, THIS WILL IMPROVE). The sides
                    # would stay painted after the box covers the middle.
                    for fr, fc in frames:
                        if fr == r and old_start < fc < old_end:
                            cut = True
                            break
                if new_cols and old_start is not None:
                    # Drop leftover marks only inside the word that changed.
                    # The stat label is a separate word from its number, so
                    # editing the number does not forget the label.
                    for c in _rewritten_word_cells(old_chars, rows[r], new_cols):
                        if owned[r][c] and _held_blank(rows[r][c]):
                            shadow[r][c] = ' '
                            owned[r][c] = 0
                if cut:
                    keep = set(new_cols)
                    for c in range(40):
                        if c in keep or not owned[r][c]:
                            continue
                        if _held_blank(rows[r][c]):
                            shadow[r][c] = ' '
                            owned[r][c] = 0
                if (new_start is not None and old_start is not None
                        and new_start <= old_start and new_end < old_end):
                    gap = 0
                    for c in range(new_end + 1, old_end + 1):
                        if shadow[r][c] == ' ':
                            gap += 1
                            if gap >= 2:
                                break
                        else:
                            gap = 0
                        if _held_blank(rows[r][c]):
                            shadow[r][c] = ' '
                            owned[r][c] = 0
        self._frame_cells = frames
        self._text_count = sum(ch != ' ' for line in self._shadow for ch in line)
        self._picture = bytes(video_bytes[:16384])
        self._shown = self._picture
        composed, composed_q = self._compose_grid(rows, real_qs)
        return self._lines_from_grid(composed, composed_q)

    def restore_blanked_text(self):
        """Forget remembered letters. Do not write the screen buffer.

        A write into a block that was only guessed to be video once landed
        in the scenario image the game saves. The tavern then skipped
        characters that training still listed.
        """
        self.reset_blank_shadow()
        return False

    def find_translations(self, translation_dict=None, detected_lines=None, video_bytes=None, context=None):
        """
        Matches detected screen text with translation_dict and returns
        precise overlay draw targets (x, y, w, h).
        Guarantees non-overlapping matches by tracking occupied column spans.
        Supports context-dependent translations (e.g. chest vs town inspect).
        """
        if detected_lines is None:
            detected_lines = self.scan_screen(video_bytes)

        # Detect active context from screen text if not explicitly provided
        all_screen_text = " ".join(line_info['text'] for line_info in detected_lines)
        if (any(k in all_screen_text for k in ("CHEST", "A CHEST", "CALFO", "DISARM", "TRAP"))
                or re.search(r'\bFOUND\s*:', all_screen_text)):
            active_context = "chest"
        elif "STAIRS UP" in all_screen_text:
            active_context = "stairs_up"
        elif "STAIRS DOWN" in all_screen_text:
            active_context = "stairs_down"
        elif any(k in all_screen_text for k in ("ELEVATOR", "CHUTE")):
            active_context = "elevator"
        elif context:
            active_context = context
        elif any(_BATTLE_CONTEXT_RE.search(_collapse_letter_spaces(line['text'])[0]) for line in detected_lines):
            active_context = 'combat'
        elif any(k in all_screen_text for k in ("OPTIONS", "A FRIENDLY GROUP", "ENCOUNTER")):
            active_context = "combat"
        elif any(k in all_screen_text for k in ("BOLTAC", "GILGAMESH", "TAVERN", "TRAINING", "EDGE OF TOWN")):
            active_context = "town"
        else:
            active_context = None

        if translation_dict is None:
            base_dict = self.translations
        else:
            base_dict = translation_dict

        if active_context and active_context in CONTEXT_TRANSLATIONS:
            merged = base_dict.copy()
            merged.update(CONTEXT_TRANSLATIONS[active_context])
            active_dict = dict(sorted(merged.items(), key=lambda x: len(x[0]), reverse=True))
        else:
            active_dict = base_dict

        matches = []
        wrapped = {}
        if active_context == 'combat':
            by_y = {line['y']: line for line in detected_lines}
            for y in sorted(by_y):
                if y not in by_y or y + 8 not in by_y:
                    continue
                left, left_map = _collapse_letter_spaces(by_y[y]['text'])
                right, right_map = _collapse_letter_spaces(by_y[y + 8]['text'])
                for name in sorted(self.monster_keys, key=len, reverse=True):
                    if name not in base_dict or ' ' not in name:
                        continue
                    words = name.split()
                    for split in range(1, len(words)):
                        first, second = ' '.join(words[:split]), ' '.join(words[split:])
                        a = re.search(r'(?<![A-Za-z])' + re.escape(first) + r'\s*[│ ]*$', left)
                        b = re.search(r'^[│ ]*(' + re.escape(second) + r')(?![A-Za-z])', right)
                        if not a or not b:
                            continue
                        def span(m, mapping, group=0):
                            start, end = m.span(group)
                            return (mapping[start], mapping[end - 1] + 1) if mapping else (start, end)
                        first_span = span(a, left_map)
                        # The left match also includes padding after the word.
                        first_end = a.start() + len(first)
                        first_span = (first_span[0], left_map[first_end - 1] + 1 if left_map else first_end)
                        wrapped[y] = (first_span, name, '')
                        wrapped[y + 8] = (span(b, right_map, 1), name, base_dict[name])
                        break
                    if y in wrapped:
                        break
        # "^ ? % AND HITS # TIMES FOR & DAMAGE" always wraps (41 letters at least).
        # Wherever the row breaks, the result is one piece on the second row
        # ("3회 명중: 7 피해") and its English on the first row is only covered.
        text_by_y = {line['y']: line['text'] for line in detected_lines}
        for y, text in text_by_y.items():
            first = text_by_y.get(y - 8, '').rstrip('│ ')
            lead = len(text) - len(text.lstrip('│ '))
            second = text[lead:].rstrip('│ ')
            hit = re.search(r'(?<![A-Z])(?:AND )?HITS (?:(\d+) TIMES|ONCE) FOR (\d+) DAMAGE', first + ' ' + second)
            # A result that is whole on the second row is translated by its own keys.
            if (not first or not hit or hit.end() <= len(first) or hit.start() >= len(first)
                    or y in wrapped or y - 8 in wrapped):
                continue
            wrapped[y - 8] = ((hit.start(), len(first)), first[hit.start():], '')
            lo, hi = lead + max(0, hit.start() - len(first) - 1), lead + hit.end() - len(first) - 1
            wrapped[y] = ((lo, hi), text[lo:hi], f'{hit.group(1) or 1}회 명중: {hit.group(2)} 피해')
        sentence_wrapped, paragraphs = _paragraph_matches(
            detected_lines, active_dict, wrapped, (id(base_dict), len(base_dict), active_context))
        wrapped.update(sentence_wrapped)
        # Names in the party table ("1 DUKE  N-FIG ..."). These stay English
        # even where an item list would otherwise translate the same word.
        party_names = set()
        for line_info in detected_lines:
            m_party = re.search(r"^[ \u2502?]*[1-6]\s+([A-Za-z0-9_'-]+(?: [A-Za-z0-9_'-]+)*)\s+(?:[GNE]-[A-Z]{3}|[A-Z]{3}|LOST|DEAD|ASHES|OK|\d+)",
                                _collapse_letter_spaces(line_info['text'])[0])
            if m_party and ' DAMAGE' not in line_info['text']:   # "4 TIMES FOR 57 DAMAGE" is no party row
                party_names.add(m_party.group(1))
        # Training grounds' class change lists classes ("B)  MAGE"), not characters.
        class_menu = any('(A)-(H) CHANGES' in l['text'] for l in detected_lines)
        # "A) GOOD / B) NEUTRAL / C) EVIL" under a "... ALIGNMENT ..." line, likewise.
        align_menu = any('ALIGNMENT' in l['text'] for l in detected_lines)
        for line_info in detected_lines:
            y = line_info['y']
            line_text = line_info['text']
            collapsed, colmap = _collapse_letter_spaces(line_text)
            if active_context == 'combat' and colmap is not None:
                for article in re.finditer(r'(?<![A-Za-z])(?:THE|AN|A)', collapsed):
                    for prefix in ('THE', 'AN', 'A'):
                        if not collapsed.startswith(prefix, article.start()):
                            continue
                        end = article.start() + len(prefix)
                        if any(collapsed.startswith(name, end) and
                               (end + len(name) == len(collapsed) or not collapsed[end + len(name)].isalnum())
                               for name in self.monster_keys):
                            collapsed = collapsed[:end] + ' ' + collapsed[end:]
                            colmap.insert(end, colmap[end] - 1)
                            break
                    else:
                        continue
                    break
            real_q = line_info.get('real_q', set())
            occupied_cols = set()
            if y in wrapped:
                (lo, hi), name, translated = wrapped[y]
                occupied_cols.update(range(lo, hi))
                matches.append({'original': name, 'korean': translated, 'x': lo * 8,
                                'y': y, 'w': (hi - lo) * 8, 'h': 8,
                                'context': active_context,
                                'wrapped_sentence': y in sentence_wrapped,
                                'paragraph': paragraphs.get(y),
                                'letter_spaced': bool(re.search(r'(?<![A-Za-z0-9])(?:[A-Za-z] ){2,}[A-Za-z](?![A-Za-z0-9])', line_text[lo:hi]))})

            def is_border(ci, _lt=line_text, _rq=real_q):
                # Unknown glyphs and window frames break text. A real '?' does not.
                return (_lt[ci] == FRAME_CHAR or _lt[ci] == SENTINEL_CHAR
                        or (_lt[ci] == '?' and ci not in _rq))

            # Protect character names from being translated by dictionary words.
            # Character names must always remain in their original English form in Neo둥근모.
            char_name_spans = []

            # A window edge is not part of the name. The party panel starts
            # with one, and without it THIEF and BISHOP match the monster keys.
            name_prefix = f"(?:^|[ {FRAME_CHAR}?\\s])"
            line_prefix = f"^[ {FRAME_CHAR}?]*"

            # Pattern 1: Tavern & Training Grounds Roster: 'A)  NAME', 'B)  NAME', ...
            # Exclude Inn rooms, Castle menu, and Edge of Town menu options
            is_menu_line = bool(re.search(r'GP/WEEK|STABLES|FREE|ROOMS|SUITE|COT|TAVERN|TRADING|TEMPLE|INN|EDGE OF TOWN|ENTER THE MAZE|UTILITIES|LEAVE GAME', collapsed))
            if not is_menu_line:
                for m_r in re.finditer(name_prefix + r"([A-T]\))\s+([A-Za-z0-9_'-]+)", collapsed):
                    # Wizardry 4's summon list ("A) A DINK  G) GAS CLOUDS")
                    # names monsters, not characters.
                    rest = re.sub(r'^(?:AN?|THE) ', '', collapsed[m_r.start(2):])
                    if class_menu and _CLASS_WORD.match(rest):
                        continue
                    if align_menu and re.match(r'(?:GOOD|NEUTRAL|EVIL)\s*(?:│|$)', rest):
                        continue
                    if any(rest.startswith(k) and (len(rest) == len(k) or not rest[len(k)].isalnum())
                           for k in self.monster_keys):
                        continue
                    char_name_spans.append(m_r.span(2))

            # Pattern 2: Party Member Numbered Selection: '1)  NAME', '2)  NAME', ...
            # "1) OR 2) DISK DRIVES" is the scenario-disk question, not a roster.
            if "DISK DRIVES" not in collapsed and not (active_context == "combat" and y < 40):
                for m_r in re.finditer(name_prefix + r"([1-6]\))\s+([A-Za-z0-9_'-]+)", collapsed):
                    # "1)  STAFF" in the equip list is an item, not a party
                    # member. A name in the party table stays protected even
                    # if an item has the same name.
                    rest = collapsed[m_r.start(2):]
                    if m_r.group(2) not in party_names and any(
                            rest.startswith(k) and (len(rest) == len(k) or not rest[len(k)].isalnum())
                            for k in self.item_keys):
                        continue
                    char_name_spans.append(m_r.span(2))

            # Pattern 3: Party Status Table Rows: '?1 FIGHTER         N-FIG 10    8    8  ?'
            m_party = re.search(
                line_prefix + r"([1-6])\s+([A-Za-z0-9_'-]+(?: [A-Za-z0-9_'-]+)*)\s+([GNE]-[A-Z]{3}|[A-Z]{3}|LOST|DEAD|ASHES|OK|\d+)(?:\s|$)",
                collapsed)
            if m_party and ' DAMAGE' not in collapsed:
                char_name_spans.append(m_party.span(2))

            # Pattern 4: Character Sheet Header (Camp / Inspect): 'FIGHTER        L   1  G-FIG  HUMAN'
            m_sheet = re.search(line_prefix + r"([A-Za-z0-9_'-]+)\s+L\s+\d+\s+", collapsed)
            if m_sheet:
                char_name_spans.append(m_sheet.span(1))

            # Pattern 5: Welcome Greetings (Inn / Boltac): 'WELCOME, FIGHTER.' or 'WELCOME? BISHOP.'
            m_welcome = re.search(r"WELCOME[?,]\s+([A-Za-z0-9_'-]+)", collapsed)
            if m_welcome:
                char_name_spans.append(m_welcome.span(1))

            # Pattern 6: Combat Action Prompt: "FIGHTER'S OPTIONS"
            m_opt = re.search(r"([A-Za-z0-9_'-]+)'S OPTIONS", collapsed)
            if m_opt:
                char_name_spans.append(m_opt.span(1))

            # Pattern 7: Inn Resting: 'FIGHTER IS NAPPING.'
            m_nap = re.search(r"([A-Za-z0-9_'-]+)\s+IS NAPPING", collapsed)
            if m_nap:
                char_name_spans.append(m_nap.span(1))

            # Pattern 8: Combat Battle Log: 'SAMURAI AND MISSES'
            m_miss = re.search(r"([A-Za-z0-9_'-]+)\s+AND MISSES", collapsed)
            if m_miss:
                actor = re.search(r"\b(?:THE|AN|A)\s+([A-Za-z0-9_'-]+(?:\s+[A-Za-z0-9_'-]+)*)$", collapsed[:m_miss.end(1)])
                if not (active_context == "combat" and actor and actor.group(1) in self.monster_keys):
                    char_name_spans.append(m_miss.span(1))

            # Pattern 9: Trap Disarm Input Prompt: 'TRAP (↵ EXITS) ? POISON NEEDLE'
            m_trap_in = re.search(r"TRAP\s*(?:\([^)]*\)\s*)?\?\s*>?\s*([A-Za-z0-9_'-]+(?:\s+[A-Za-z0-9_'-]+)*)", collapsed)
            if m_trap_in:
                char_name_spans.append(m_trap_in.span(1))

            # Register protected character name spans and emit them as raw English tokens
            for ns, ne in char_name_spans:
                if colmap is not None:
                    src_ns = colmap[ns]
                    src_ne = colmap[ne - 1] + 1
                    name_token = collapsed[ns:ne]
                else:
                    src_ns, src_ne = ns, ne
                    name_token = line_text[ns:ne]
                col_range = range(src_ns, src_ne)
                if not any(c in occupied_cols for c in col_range):
                    occupied_cols.update(col_range)
                    ns, ne = src_ns, src_ne
                    left_b = -1
                    for ci in range(ns - 1, -1, -1):
                        if is_border(ci):
                            left_b = ci
                            break
                    right_b = len(line_text)
                    for ci in range(ne, len(line_text)):
                        if is_border(ci):
                            right_b = ci
                            break
                    matches.append({
                        'original': name_token,
                        'korean': name_token,
                        'x': ns * 8,
                        'y': y,
                        'w': (ne - ns) * 8,
                        'h': 8,
                        'box': (max(0, ns * 8 - 2), max(0, y - 2), (ne - ns) * 8 + 4, 12),
                        'context': active_context,
                        'is_raw_token': True,
                        'is_char_name': True,
                        'min_bound_x': (left_b + 1) * 8,
                        'max_bound_x': right_b * 8
                    })

            # A lone unknown '?' between tokens is a missed word gap
            # ("YOU?CANNOT", "1,?THEN"). Search that view first.
            # The original line is searched after, so a '?' that stands
            # for a missing letter ("NE?T") still hits its own key.
            gap_edge = set(",.!?:;\"')(↵#<>*")
            search_views = [line_text]
            if '?' in line_text:
                buf = list(line_text)
                n = len(buf)
                changed = False
                for i, ch in enumerate(buf):
                    if ch != '?' or i in real_q or i == 0 or i + 1 == n:
                        continue
                    left, right = line_text[i - 1], line_text[i + 1]
                    if (left == ' ' or right == ' ' or left == FRAME_CHAR
                            or right == FRAME_CHAR):
                        continue
                    if ((left.isalnum() or left in gap_edge)
                            and (right.isalnum() or right in gap_edge)):
                        buf[i] = ' '
                        changed = True
                if changed:
                    search_views = [''.join(buf), line_text]

            # A maze diagonal can equal one letter. That row has no word, so
            # it is not translated and the wall is left alone.
            # Letter-spaced combat text is a word once the gaps are closed.
            graphic_row = not _has_text_run(collapsed)
            normalized_views = {}

            # Match longest phrases first (active_dict is sorted by len descending)
            # '#' keys stand for a number. Turn the ones on this row into
            # plain keys ("TAKES 12 DAMAGE") so they compete by length.
            row_items = active_dict.items()
            partial_stats = {}
            if not graphic_row:
                extra = {}
                # Hashed sentences: the words on screen are hashed and looked up.
                # A hit goes in as a plain key, so it is placed like any other.
                for view in {collapsed, *search_views}:
                    for phrase, h_sentence, h_template, nums in _hash_candidates(view):
                        ko = active_dict.get(HASH_SENTENCE + h_sentence)
                        if ko is None and h_template:
                            # '#' sentences live in SENTENCE_TRANSLATIONS and the game's sentence file.
                            hk = HASH_TEMPLATE + h_template
                            ko = (active_dict.get(hk) or SENTENCE_TRANSLATIONS.get(hk)
                                  or (self.number_templates or {}).get(hk))
                            if isinstance(ko, str) and ko.count('#') == len(nums):
                                for num in nums:
                                    ko = ko.replace('#', num, 1)
                            else:
                                ko = None
                        if ko is not None and phrase not in active_dict:   # a plain (context) key wins
                            extra.setdefault(phrase, ko)
                for tpl, rx, ko_tpl in _number_templates(self.number_templates):
                    for m in rx.finditer(collapsed):
                        ko = ko_tpl
                        for num in m.groups():
                            ko = ko.replace('#', num, 1)
                        extra.setdefault(m.group(0), ko)
                # A popup window cuts the character sheet: "PIET│", "LUC│",
                # "1)*GLOV│". A word that ends at the popup edge and starts a
                # stat label or an item name takes that label, or the item's
                # common last word ("GLOV" -> 장갑, gloves of copper or silver).
                for m in re.finditer(r'(?<![A-Z.])([A-Z][A-Z.]+)(?=' + FRAME_CHAR + ')', collapsed):
                    word = m.group(1)
                    if word in active_dict or word in extra:
                        continue
                    stat = [k for k in _STAT_LABELS if k.startswith(word) and k in active_dict]
                    if stat:
                        extra[word] = active_dict[stat[0]]
                        partial_stats[word] = stat[0]   # same 8-column field as the full label
                        continue
                    # Several words cut by the popup ("# CHARACTER NA│") take
                    # the one translation of the keys they start, when it fits.
                    seg = re.split(r'  +', collapsed[:m.end()].rsplit(FRAME_CHAR, 1)[-1])[-1]
                    seg = re.sub(r'^[^A-Z]+', '', seg)
                    whole = set()
                    if ' ' in seg and seg not in active_dict:
                        whole = {v for k, v in active_dict.items()
                                 if isinstance(v, str) and v and len(k) > len(seg)
                                 and k.startswith(seg) and '#' not in k}
                    if len(whole) == 1 and _ko_width(next(iter(whole))) <= len(seg) * 8:
                        extra[seg] = whole.pop()
                        continue
                    if len(word) < 3:
                        continue
                    lasts = set()
                    for k in self.item_keys:
                        if k.startswith(word) and k != word and isinstance(active_dict.get(k), str):
                            base = re.sub(r'\(.*?\)|[+-]\d+', '', active_dict[k]).strip()
                            if base:
                                lasts.add(base.split()[-1])
                    if len(lasts) == 1:
                        extra[word] = lasts.pop()
                if extra:
                    row_items = sorted(list(extra.items()) + list(active_dict.items()),
                                       key=lambda x: len(x[0]), reverse=True)
            for en_key, ko_val in (() if graphic_row else row_items):
                # The party header is a set of columns, not a single sentence.
                if en_key.startswith('# CHARACTER NAME') and ' '.join(en_key.split()) == '# CHARACTER NAME CLASS AC HITS STATUS':
                    continue
                # "A)" is a hotkey. A one-letter article still has to be a whole word.
                if not en_key or (len(en_key) < 2 and en_key != "A"):
                    continue
                k_len = len(en_key)
                # Space keys use the gap view. Keys that contain '?' stay
                # on the original line, so NE?T and E?ITS still match.
                # A lone article has no space, but "A?SKELETON" is still "A SKELETON".
                if colmap is not None:
                    view = collapsed
                elif len(search_views) > 1 and '?' not in en_key and (
                        ' ' in en_key or en_key in ("A", "AN")):
                    view = search_views[0]
                else:
                    view = line_text
                view_colmap = colmap
                match_key = en_key
                if ' ' in en_key and ('  ' in view or '  ' in en_key) and en_key not in view:
                    if view not in normalized_views:
                        parts = list(re.finditer(r' +|[^ ]', view))
                        normalized_views[view] = (
                            ''.join(' ' if m.group(0)[0] == ' ' else m.group(0) for m in parts),
                            [colmap[m.start()] if colmap is not None else m.start() for m in parts],
                        )
                    normalized, normalized_map = normalized_views[view]
                    normalized_key = re.sub(r' +', ' ', en_key)
                    if normalized_key in normalized:
                        view_colmap = normalized_map
                        view = normalized
                        match_key = normalized_key
                        k_len = len(match_key)
                start = 0
                while True:
                        pos = view.find(match_key, start)
                        if pos == -1:
                            break
                        # Whole-word boundary check for purely alphanumeric keys (e.g. 'FIGHT' shouldn't match 'FIGHTER')
                        if en_key[0].isalnum() and pos > 0 and view[pos - 1].isalnum():
                            start = pos + 1
                            continue
                        if en_key[-1].isalnum() and (pos + k_len) < len(view) and view[pos + k_len].isalnum():
                            start = pos + 1
                            continue
                        # Typing a spell name ("SPELL NAME ? >MASOPI"): not the cut name yet.
                        if en_key in SPELL_CUT_KEYS and '>' in view[:pos]:
                            start = pos + 1
                            continue
                        if en_key in ("A", "AN"):
                            prev_ok = pos == 0 or view[pos - 1] in (" ", FRAME_CHAR)
                            next_ok = (pos + k_len) >= len(view) or view[pos + k_len] in (" ", FRAME_CHAR)
                            if not (prev_ok and next_ok):
                                start = pos + 1
                                continue

                        # Letter-spaced text matches on the closed line. The box
                        # uses the original cells, gaps included.
                        if view_colmap is not None:
                            src_lo = view_colmap[pos]
                            src_hi = view_colmap[pos + k_len - 1] + 1
                        else:
                            src_lo = pos
                            src_hi = pos + k_len

                        if en_key in ("A CHEST! YOU MAY", "A CHEST!  YOU MAY") and src_hi < len(line_text):
                            if line_text[src_hi] in '!:' or (line_text[src_hi] == '?' and src_hi in real_q):
                                src_hi += 1
                        # A translation that ends with ':' also covers the game's
                        # colon right after the key ("WE HAVE:" -> "빈 방 목록:").
                        elif (src_hi < len(line_text) and line_text[src_hi] == ':'
                                and isinstance(ko_val, str) and ko_val.rstrip().endswith(':')):
                            src_hi += 1

                        # Check if this character span overlaps with an already matched longer phrase
                        is_stat = (en_key in ("STRENGTH", "I.Q.", "PIETY", "VITALITY", "AGILITY", "LUCK", "BONUS")
                                   or en_key in partial_stats)
                        if is_stat and colmap is None:
                            # In Wizardry CGA, stat labels are right-justified in an 8-col field.
                            # Align the stat box to the full 8-character column span (col_right - 8 to col_right)
                            col_right = src_hi
                            if en_key in partial_stats:
                                # Cut by a popup: the field ends where the whole label would.
                                # The box stops at the popup edge.
                                col_left = max(0, src_lo + len(partial_stats[en_key]) - 8)
                            else:
                                col_left = max(0, col_right - 8)
                            col_range = range(col_left, col_right)
                        else:
                            col_left = src_lo
                            col_right = src_hi
                            col_range = range(col_left, col_right)

                        if not any(c in occupied_cols for c in col_range):
                            occupied_cols.update(col_range)
                            x = col_left * 8
                            w = (col_right - col_left) * 8
                            ko_text = ko_val if isinstance(ko_val, str) else ko_val.get('ko', str(ko_val))
                            # Wizardry 5: these also label shop categories, so only an
                            # equipped item row ("6)*ARMOR") is an unidentified item.
                            if (en_key in self.equipped_unidentified and not ko_text.startswith('?')
                                    and re.search(r'\d\)\*$', line_text[max(0, col_left - 3):col_left])):
                                ko_text = '?' + ko_text

                            # Determine nearest '?' borders to protect box frames
                            left_b = -1
                            for ci in range(col_left - 1, -1, -1):
                                if is_border(ci):
                                    left_b = ci
                                    break
                            right_b = len(line_text)
                            for ci in range(col_right, len(line_text)):
                                if is_border(ci):
                                    right_b = ci
                                    break

                            matches.append({
                                'original': en_key,
                                'korean': ko_text,
                                'x': x,
                                'y': y,
                                'w': w,
                                'h': 8,
                                'box': (max(0, x - 2), max(0, y - 2), w + 4, 12),
                                'context': active_context,
                                'letter_spaced': bool(colmap is not None and re.search(
                                    r'(?<![A-Za-z0-9])(?:[A-Za-z] ){2,}[A-Za-z](?![A-Za-z0-9])',
                                    line_text[src_lo:src_hi])),
                                'is_stat_attr': is_stat,
                                'min_bound_x': (left_b + 1) * 8,
                                'max_bound_x': right_b * 8
                            })
                        start = pos + 1

            if getattr(self, 'untranslated_logger', None):
                self.untranslated_logger.log_untranslated(line_text, y, occupied_cols)

            # Scan remaining non-occupied columns to redraw untranslated English text, numbers,
            # genuine '?' glyphs and character names in Neo둥근모 (cell-by-cell on the CGA grid).
            # A lone '#' is the character-number column. A lone '<' or '>' is the
            # bracket just read. Leaving either blank shows only the one-pixel cover.
            def emit_raw(rs, re_):
                raw_token = line_text[rs:re_]
                has_q = any(ci in real_q for ci in range(rs, re_))
                if not (any(ch.isalnum() for ch in raw_token) or '↵' in raw_token
                        or '#' in raw_token or '<' in raw_token or '>' in raw_token or has_q):
                    return
                if graphic_row and not any(ch in "#<>↵" for ch in raw_token):
                    return
                left_b = -1
                for ci in range(rs - 1, -1, -1):
                    if is_border(ci):
                        left_b = ci
                        break
                right_b = len(line_text)
                for ci in range(re_, len(line_text)):
                    if is_border(ci):
                        right_b = ci
                        break
                matches.append({
                    'original': raw_token,
                    'korean': raw_token,
                    'x': rs * 8,
                    'y': y,
                    'w': (re_ - rs) * 8,
                    'h': 8,
                    'box': (max(0, rs * 8 - 2), max(0, y - 2), (re_ - rs) * 8 + 4, 12),
                    'context': active_context,
                    'is_raw_token': True,
                    'min_bound_x': (left_b + 1) * 8,
                    'max_bound_x': right_b * 8
                })
                occupied_cols.update(range(rs, re_))

            raw_start = None
            for col in range(len(line_text)):
                c = line_text[col]
                if col in occupied_cols or c == ' ' or is_border(col):
                    if raw_start is not None:
                        emit_raw(raw_start, col)
                        raw_start = None
                else:
                    if raw_start is None:
                        raw_start = col
            if raw_start is not None:
                emit_raw(raw_start, len(line_text))

        return matches


if __name__ == '__main__':
    print("=" * 60)
    print("CGA Screen Text & Coordinate Extractor - Real-time Diagnostic")
    print("=" * 60)

    from wiz_hook import DOSBoxHook

    hook = DOSBoxHook()
    pid = hook.find_dosbox_pid()
    if not pid:
        print("[!] DOSBox process not found. Please run Wizardry 1 in DOSBox first.")
        sys.exit(1)

    print(f"[+] Found DOSBox PID: {pid}")
    hwnd = hook.find_dosbox_hwnd()
    from wiz_hook import kernel32, PROCESS_VM_READ, PROCESS_QUERY_INFORMATION
    hook.handle = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    hook.hwnd = hwnd

    json_path = os.path.join(os.path.dirname(__file__), "wiz1_ko_data.json")
    trans_map = load_unified_translations(json_path)
    extractor = CGATextExtractor(hook, translation_dict=trans_map)

    print("[*] Reading DOSBox CGA video memory...")
    lines = extractor.scan_screen()
    if not lines:
        print("[-] Could not locate CGA video allocation or screen is blank.")
    else:
        print(f"[+] Successfully extracted {len(lines)} text lines from screen:")
        for line in lines:
            print(f"  Y={line['y']:3d} | {line['text'].strip()}")
            for w in line['words']:
                print(f"       -> Word: '{w['word']}' at X={w['x']}, Y={w['y']} (Col={w['col']}, W={w['w']})")

        matches = extractor.find_translations(detected_lines=lines)
        print(f"\n[+] Matched {len(matches)} translations:")
        for m in matches:
            print(f"  * '{m['original']}' -> '{m['korean']}' at (X={m['x']}, Y={m['y']}, W={m['w']}, H={m['h']})")

    if extractor.unmapped_glyphs:
        print(f"\n[i] Unmapped glyph count: {len(extractor.unmapped_glyphs)}")

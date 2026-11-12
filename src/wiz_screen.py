"""Read DOSBox's CGA framebuffer to distinguish its shared trade state.

The 8x8 glyphs below come from the supplied DOS screenshots. VGA RAM is separate
from DOS conventional memory. No keyboard input or game-memory writes occur.
"""
import ctypes

GLYPHS = {
    'T': 'fe92101010103800', 'R': '7824243824246600',
    'A': '101028287c44ee00', 'D': '7824222222247800',
    'E': '7e22203820227e00', 'G': '3844808e84443800',
    'O': '3c42424242423c00', 'L': '7020202020227e00',
    'I': '3810101010103800', 'M': 'c66c6c545444ee00',
}


def trade_stage(width, height, pixel):
    """pixel(x,y) returns RGB; classify only the original prompt area."""
    glyphs = {bytes.fromhex(value): key for key, value in GLYPHS.items()}
    lines = []
    for row in (9, 10):
        line = ''
        for col in range(14, 38):
            glyph = []
            for dy in range(8):
                bits = 0
                for dx in range(8):
                    x = min(width - 1, int((col * 8 + dx + .5) * width / 320))
                    y = min(height - 1, int((row * 8 + dy + .5) * height / 200))
                    bits = bits * 2 + int(min(pixel(x, y)[:3]) > 160)
                glyph.append(bits)
            line += glyphs.get(bytes(glyph), ' ' if not any(glyph) else '?')
        lines.append(line)
    text = ' '.join(lines)
    if 'TRADE GOLD' in text:
        return 'gold'
    if 'TRADE ' in text and 'TEM' in text:
        return 'item'
    if 'TRADE ' in text:
        return 'who'
    return None


def _screen_anchor(text):
    """A line that only the game framebuffer draws at a fixed column."""
    return (
        ('CASTLE' in text and text.find('CASTLE') == 17)
        or ('CHARACTER NAME' in text and text.find('CHARACTER NAME') == 3)
        or ('GILGAMESH' in text and text.find('GILGAMESH') == 11)
        or ('WELCOME' in text and text.find('WELCOME') in (2, 3))
        or ('SCENARIO DISK' in text)
        or ('A)DD' in text and text.find('A)DD') in (10, 11, 12))
    )


def _lock_video(hook, cand):
    hook._video_address = cand
    hook._trade_video_address = cand
    return cand


# One stray glyph used to lock a 128KB–2MB block for the rest of the
# run. Blanking then kept writing that address, including after the
# block was reused for the scenario disk the game saves.
_MIN_VIDEO_LETTERS = 12


def find_cga_video_address(hook):
    """Find DOSBox's CGA video allocation in process memory.

    A block is the framebuffer only when it shows a known game screen,
    or it is the block with the most decoded letters and that count is
    at least _MIN_VIDEO_LETTERS. Returns the exact base address.
    """
    cached = getattr(hook, '_video_address', None) or getattr(hook, '_trade_video_address', None)
    if cached is not None:
        return cached

    if not hook or not getattr(hook, 'handle', None):
        return None

    import time
    now = time.monotonic()
    if now < getattr(hook, '_cga_next_search', 0):
        return None
    hook._cga_next_search = now + 0.8

    from wiz_hook import MEMORY_BASIC_INFORMATION, kernel32
    from cga_text_extractor import CGATextExtractor

    def read(address, size):
        buf = ctypes.create_string_buffer(size)
        count = ctypes.c_size_t()
        if kernel32.ReadProcessMemory(hook.handle, ctypes.c_void_p(address),
                                      buf, size, ctypes.byref(count)):
            return buf.raw[:count.value]
        return b''

    extractor = CGATextExtractor(glyphs=getattr(hook, '_cga_glyphs', None))
    address = 0
    mbi = MEMORY_BASIC_INFORMATION()
    best = None
    best_n = 0

    while kernel32.VirtualQueryEx(hook.handle, ctypes.c_void_p(address),
                                  ctypes.byref(mbi), ctypes.sizeof(mbi)):
        base = mbi.BaseAddress or 0
        size = mbi.RegionSize
        end = base + size
        if end <= address:
            break
        if mbi.State == 0x1000 and not (mbi.Protect & 0x100) and (mbi.Protect & 0xCC):
            # In DOSBox 0.74, vga.mem.linear is allocated via malloc() in a 512KB committed block.
            # 32-bit MSVC CRT malloc() places a 32-byte (0x20) chunk header before the allocated buffer.
            if 0x20000 <= size <= 0x200000:
                for delta in (0x20, 0x00):
                    cand = base + delta
                    cga_data = read(cand, 16384)
                    if len(cga_data) == 16384:
                        lines = extractor.scan_screen(cga_data)
                        if lines:
                            anchored = False
                            letters = 0
                            for l in lines:
                                t = l['text']
                                if _screen_anchor(t):
                                    anchored = True
                                    break
                                for ch in t:
                                    if ch.isalnum():
                                        letters += 1
                            if anchored:
                                return _lock_video(hook, cand)
                            if delta == 0x20 and letters > best_n:
                                best_n = letters
                                best = cand
        address = end

    if best is not None and best_n >= _MIN_VIDEO_LETTERS:
        return _lock_video(hook, best)
    return None


def relock_cga_video(hook):
    """Pick the framebuffer again after DOSBox changes window size.

    A fullscreen toggle can leave the locked block as a frozen copy while
    the picture DOSBox shows is a newer allocation. Prefer an anchored
    block whose pixels differ from that copy.
    """
    if not hook or not getattr(hook, 'handle', None):
        return None
    old = getattr(hook, '_video_address', None) or getattr(hook, '_trade_video_address', None)

    from wiz_hook import MEMORY_BASIC_INFORMATION, kernel32
    from cga_text_extractor import CGATextExtractor

    def read(address):
        buf = ctypes.create_string_buffer(16384)
        count = ctypes.c_size_t()
        if kernel32.ReadProcessMemory(hook.handle, ctypes.c_void_p(address),
                                      buf, 16384, ctypes.byref(count)):
            return buf.raw[:count.value]
        return b''

    snapshot = read(old) if old else b''
    extractor = CGATextExtractor(glyphs=getattr(hook, '_cga_glyphs', None))
    address = 0
    mbi = MEMORY_BASIC_INFORMATION()
    found = []
    while kernel32.VirtualQueryEx(hook.handle, ctypes.c_void_p(address),
                                  ctypes.byref(mbi), ctypes.sizeof(mbi)):
        base = mbi.BaseAddress or 0
        size = mbi.RegionSize
        end = base + size
        if end <= address:
            break
        if mbi.State == 0x1000 and not (mbi.Protect & 0x100) and (mbi.Protect & 0xCC):
            if 0x20000 <= size <= 0x200000:
                for delta in (0x20, 0x00):
                    cand = base + delta
                    data = read(cand)
                    if len(data) != 16384:
                        continue
                    lines = extractor.scan_screen(data)
                    anchored = False
                    letters = 0
                    for line in lines:
                        text = line['text']
                        if _screen_anchor(text):
                            anchored = True
                            break
                        for ch in text:
                            if ch.isalnum():
                                letters += 1
                    if anchored:
                        found.append((cand, data, letters))
                        break
        address = end

    changed = [item for item in found if item[1] != snapshot]
    if changed:
        changed.sort(key=lambda item: item[2], reverse=True)
        return _lock_video(hook, changed[0][0])
    if old and any(item[0] == old for item in found):
        return _lock_video(hook, old)
    if found:
        return _lock_video(hook, found[0][0])
    if old:
        return _lock_video(hook, old)
    return None


def read_trade_stage(hook):
    """Find DOSBox's separate CGA video allocation and read its prompt."""
    from wiz_hook import kernel32

    def read(address, size):
        buf = ctypes.create_string_buffer(size)
        count = ctypes.c_size_t()
        if kernel32.ReadProcessMemory(hook.handle, ctypes.c_void_p(address),
                                      buf, size, ctypes.byref(count)):
            return buf.raw[:count.value]
        return b''

    def classify(video):
        if len(video) < 16384:
            return None
        def pixel(x, y):
            b = video[(y % 2)*8192 + (y//2)*80 + x//4]
            value = 255 if (b >> (6-2*(x%4))) & 3 else 0
            return (value, value, value)
        return trade_stage(320, 200, pixel)

    cached = find_cga_video_address(hook)
    if cached is not None:
        return classify(read(cached, 16384))
    return None


_SIG_TAIR = bytes.fromhex('fffc03000fc03fc0')


def read_stairs_prompt(hook):
    """Detect if the center STAIRS popup is active in CGA video memory."""
    from wiz_hook import kernel32

    def read(address, size):
        buf = ctypes.create_string_buffer(size)
        count = ctypes.c_size_t()
        if kernel32.ReadProcessMemory(hook.handle, ctypes.c_void_p(address),
                                      buf, size, ctypes.byref(count)):
            return buf.raw[:count.value]
        return b''

    cached = find_cga_video_address(hook)
    if cached is not None:
        video = read(cached, 16384)
        if len(video) == 16384:
            pos = video.find(_SIG_TAIR)
            if pos != -1 and 3000 <= pos <= 4500:
                up_marker = video[pos + 12: pos + 14]
                if up_marker == bytes.fromhex('fcfc'):
                    return 'up'
                return 'down'
    return None


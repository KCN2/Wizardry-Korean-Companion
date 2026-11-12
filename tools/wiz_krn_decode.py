"""Decode the game text in ASCII.KRN from a Wizardry (ASCII Corp. IBM PC port) disk image.

Usage:
    python tools/wiz_krn_decode.py WIZ1.DSK > wiz1_text.txt

Read only. See docs/ASCII_KRN.md for the format. Written for Wizardry 1
(WIZ1.DSK); the same port is used for 2-5, so it should work there too, but
check the output.
"""
import sys

KEY_MOD = 51          # K = 67 * (string number mod 51)
KEY_MUL = 67
POS_MUL = 23          # minus 23 * character position (1-based)


def ucsd_files(disk):
    """{name: bytes} from the UCSD Pascal directory at block 2."""
    u = lambda o: int.from_bytes(disk[o:o + 2], 'little')
    base, files = 1024, {}
    for i in range(1, u(base + 16) + 1):
        o = base + i * 26
        first, nxt = u(o), u(o + 2)
        name = disk[o + 7:o + 7 + disk[o + 6]].decode('latin1')
        files[name] = disk[first * 512:nxt * 512]
    return files


def find_offset_table(krn):
    """The strOffsets table: the longest run of increasing 16-bit word offsets."""
    u = lambda o: int.from_bytes(krn[o:o + 2], 'little')
    best = (0, 0)
    for start in range(0, len(krn) - 4, 2):
        if u(start) > 16:
            continue
        o, prev = start + 2, u(start)
        while o + 2 <= len(krn) and prev < u(o) < len(krn) // 2:
            prev, o = u(o), o + 2
        n = (o - start) // 2
        if n > best[1]:
            best = (start, n)
    start, n = best
    return [u(start + 2 * i) for i in range(n)]


def decrypt(cipher, residue):
    """One string: c -> (c + 16384 - 67*residue - 23*i) mod 256, i from 1."""
    return ''.join(chr((c + 16384 - KEY_MUL * residue - POS_MUL * (i + 1)) % 256)
                   for i, c in enumerate(cipher))


def _score(text):
    good = ".,!?'-()0123456789:/*\"#~^&<>@;=+%$"
    return sum(3 if 'A' <= ch <= 'Z' else 2 if ch == ' ' else 1 if ch in good else -8 for ch in text)


def decode_all(krn, jump=12):
    """Decrypt every string in file order.

    The key uses the string number mod 51, which this tool does not take from
    the strTree. Neighbouring strings almost always have consecutive numbers,
    so a Viterbi pass picks, per string, the residue that reads as English and
    mostly follows the previous one + 1.
    """
    offsets = find_offset_table(krn)
    raws = [krn[2 * o + 1:2 * o + 1 + krn[2 * o]] for o in offsets]
    scores = [[_score(decrypt(c, r)) for r in range(KEY_MOD)] for c in raws]
    best, back = scores[0][:], []
    for row in scores[1:]:
        nb, bk = [], []
        for r in range(KEY_MOD):
            q = max(range(KEY_MOD), key=lambda q: best[q] - (0 if (q + 1) % KEY_MOD == r else jump))
            nb.append(best[q] - (0 if (q + 1) % KEY_MOD == r else jump) + row[r])
            bk.append(q)
        best, back = nb, back + [bk]
    r = max(range(KEY_MOD), key=lambda x: best[x])
    path = [r]
    for bk in reversed(back):
        r = bk[r]
        path.append(r)
    path.reverse()
    return [decrypt(c, r) for c, r in zip(raws, path)]


def find_str_tree(krn, count):
    """String numbers from the strTree: {file index: string number}.

    Records are 10 bytes (left, right, start, end, indexOffset). The tree sits
    right after strOffsets; the records are read until one stops making sense.
    Returns {} when no tree covering every string is found.
    """
    u = lambda o: int.from_bytes(krn[o:o + 2], 'little')
    for base in range(0, len(krn) - 10, 2):
        numbers, o = {}, base
        while o + 10 <= len(krn):
            left, right, start, end, idx = (u(o + 2 * k) for k in range(5))
            if not (start <= end < 65536 and idx + end - start < count
                    and left < 1000 and right < 1000):
                break
            if any(idx + k in numbers for k in range(end - start + 1)):
                break
            for k in range(end - start + 1):
                numbers[idx + k] = start + k
            o += 10
        if len(numbers) == count:
            return numbers
    return {}


def decode_numbered(krn):
    """[(string number or None, text)] in file order.

    Uses the exact key from the strTree when it is found; otherwise falls back
    to decode_all (number None).
    """
    offsets = find_offset_table(krn)
    numbers = find_str_tree(krn, len(offsets))
    if not numbers:
        return [(None, t) for t in decode_all(krn)]
    out = []
    for i, o in enumerate(offsets):
        n = numbers[i]
        out.append((n, decrypt(krn[2 * o + 1:2 * o + 1 + krn[2 * o]], n % KEY_MOD)))
    return out


def main():
    disk = open(sys.argv[1], 'rb').read()
    krn = ucsd_files(disk)['ASCII.KRN']
    for i, (n, text) in enumerate(decode_numbered(krn)):
        print(f"{i:4d}\t{'' if n is None else n}\t{text}")


if __name__ == '__main__':
    main()

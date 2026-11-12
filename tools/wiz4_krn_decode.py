"""Decode Wizardry 4 (The Return of Werdna) strings using exact UCSD p-code block indexing and ASCII.HUFF.

Reverse-engineered from SYSTEM.PASCAL (Proc 85, Proc 87, Proc 9):
- Block 112 holds 113 little-endian 16-bit word offsets (starting string ID per 512-byte block).
- Each 512-byte block has metadata packed in reverse order from byte 511 down:
  - count (number of spans) at byte 511
  - span length and individual string compressed byte lengths (stride)
  - skip deltas (>=128 uses 2-byte delta) between spans
- If ASCII.HUFF exists (checked in Proc 9, sets global flag 2061), Proc 87 uses
  ASCII.HUFF tree to decode the bitstream starting at bit 0 of the exact byte offset found by Proc 85.
- The first decoded Huffman symbol is the exact Pascal string length (L).
- The decoder then decodes exactly L symbols and immediately terminates,
  preventing any adjacent string bleed, false prefixes, or trailing artifacts.
"""

import sys
from pathlib import Path
try:
    from tools.wiz_krn_decode import ucsd_files
except ModuleNotFoundError:
    from wiz_krn_decode import ucsd_files


def decode_pascal_string(krn_stream, byte_offset, plane0, plane1, plane2, max_chars=255):
    """Decode a single length-prefixed Pascal string starting at bit 0 of byte_offset."""
    node = 0
    symbols = bytearray()
    bit_pos = byte_offset * 8
    target_len = None

    while bit_pos < len(krn_stream) * 8:
        b = krn_stream[bit_pos // 8]
        bit = (b >> (bit_pos % 8)) & 1
        bit_pos += 1

        if bit == 0:
            child = plane2[node]
            leaf = (plane0[node] & 2) != 0
        else:
            child = plane1[node]
            leaf = (plane0[node] & 1) != 0

        if leaf:
            if target_len is None:
                target_len = child
                if target_len == 0 or target_len > max_chars:
                    return ""
            else:
                symbols.append(child)
                if len(symbols) == target_len:
                    break
            node = 0
        else:
            node = child

    if target_len is None:
        return ""
    return symbols.decode("latin1", errors="replace")


def decode_wiz4_strings(disk_path):
    with open(disk_path, "rb") as f:
        files = ucsd_files(f.read())
    huff, krn = files['ASCII.HUFF'], files['ASCII.KRN']

    plane0 = huff[0:256]
    plane1 = huff[256:512]
    plane2 = huff[512:768]

    block_count = int.from_bytes(krn[:2], 'little')
    index_size = int.from_bytes(krn[2:4], 'little')
    if index_size != (block_count + 1) * 2 or len(krn) < block_count * 512 + index_size:
        raise ValueError('Invalid ASCII.KRN block index')
    index = krn[block_count * 512 : block_count * 512 + index_size]
    index_table = [int.from_bytes(index[i : i + 2], "little") for i in range(0, index_size, 2)]

    id_to_string = {}

    for blk_idx in range(block_count):
        blk = krn[blk_idx * 512 : (blk_idx + 1) * 512]
        count = blk[511]
        p = 510
        cur_id = index_table[blk_idx]
        offset = 4 if blk_idx == 0 else 0

        for s in range(count):
            if p < 0:
                break
            span = blk[p]
            p -= 1
            if span > p + 1:
                break
            lengths = [blk[p - i] for i in range(span)]
            p -= span

            for idx, l in enumerate(lengths):
                str_id = cur_id + idx
                file_byte = blk_idx * 512 + offset
                text = decode_pascal_string(krn, file_byte, plane0, plane1, plane2)
                id_to_string[str_id] = text
                offset += l

            cur_id += span - 1
            if p >= 0 and s < count - 1:
                delta = blk[p]
                p -= 1
                if delta < 128:
                    cur_id += delta
                elif p >= 0:
                    cur_id += 256 * (delta - 128) + blk[p]
                    p -= 1

    return id_to_string


if __name__ == "__main__":
    disk_path = sys.argv[1] if len(sys.argv) > 1 else r"D:\DOS\WIZ15\WIZ4.DSK"
    extracted = decode_wiz4_strings(disk_path)
    print(f"Decoded {len(extracted)} indexed strings from {disk_path}")

    out_path = sys.argv[2] if len(sys.argv) > 2 else r"docs/wiz4_extracted_strings.txt"
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for sid in sorted(extracted.keys()):
            f.write(f"[{sid:5d}] {extracted[sid]}\n")
    print(f"Saved indexed strings to {out_path}")

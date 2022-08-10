#!/usr/bin/env python3
import enum
import io
import toml
import sys
import struct
import pyfastgbalz77


class C(enum.Enum):
    Control = 0
    Text = 1


def unlz77(f):
    out = bytearray()

    header, = struct.unpack('<I', f.read(4))
    if (header & 0xff) != 0x10:
        raise ValueError("invalid header")

    n = header >> 8
    while len(out) < n:
        ref, = struct.unpack('<B', f.read(1))

        for i in range(8):
            if len(out) >= n:
                break

            if (ref & (0x80 >> i)) == 0:
                c, = struct.unpack('<B', f.read(1))
                out.append(c)
                continue

            info, = struct.unpack('>H', f.read(2))
            m = info >> 12
            off = info & 0xfff

            for _ in range(m + 3):
                out.append(out[-off - 1])

    return bytes(out[:n])


def unpack_text_archive_header(f):
    start, = struct.unpack("<H", f.read(2))
    out = [start]
    for _ in range(start // 2 - 1):
        v, = struct.unpack("<H", f.read(2))
        out.append(v)
    return out


def read_text(f, max_len, end_cc):
    out = bytearray()
    while max_len == -1 or len(out) < max_len:
        c, = f.read(1)
        out.append(c)
        if c == end_cc:
            break
    return bytes(out)


def decode_text(buf, extend_cc):
    out = []
    i = 0
    typ = C.Text
    while i < len(buf):
        c = buf[i]
        i += 1
        if c > extend_cc:
            typ = C.Control
        elif c == extend_cc:
            c += buf[i]
            i += 1
        out.append((typ, c))
        typ = C.Text
    return out


def encode_text(buf, old_charset, mapping, extend_cc):
    out = []
    for (typ, v) in buf:
        if typ == C.Control:
            out.append(v)
        else:
            # NOTE: Super ugly but it works, I guess.
            t = old_charset[v].upper()
            if t not in mapping:
                out.append(v)
                continue

            v = mapping[t]
            if v >= extend_cc:
                out.append(extend_cc)
                out.append(v - extend_cc)
            else:
                out.append(v)
    return bytes(out)


with open(sys.argv[1], 'r') as f:
    config = toml.load(f)


with open(sys.argv[2], 'rb') as f:
    old = f.read()

with open(sys.argv[3], 'rb') as f:
    out = bytearray(f.read())


mapping = {
    c: config['charset']['new'].index(c)
    for c in config['charset']['old']
    if c in config['charset']['new'] and c != '�'
}


eor_cc = config['charset']['end_cc']
extend_cc = config['charset']['extend_cc']

for text_archive in config['text_archives']:
    new_entries = []

    offset = text_archive['old']
    r = io.BytesIO(old[offset:])

    if text_archive['compressed']:
        d = unlz77(r)
        n, = struct.unpack('<I', d[:4])
        if len(d) != (n >> 8):
            raise ValueError("invalid compressed text archive")
        r = io.BytesIO(d[4:])

    header = unpack_text_archive_header(r)
    for i, suboffset in enumerate(header):
        r.seek(suboffset)
        old_text = read_text(
            r,
            header[i + 1] - suboffset if i < len(header) - 1 else -1,
            eor_cc)

        decoded = decode_text(old_text, extend_cc)

        new_entries.append(encode_text(
            decoded, config['charset']['old'], mapping, extend_cc))

    index = io.BytesIO()
    w = io.BytesIO()
    for e in new_entries:
        index.write(struct.pack('<H', w.tell() + len(new_entries) * 2))
        w.write(e)

    out_archive = index.getvalue() + w.getvalue()

    # Find free space at the end of the ROM.
    next_free_loc = len(out) - 1
    while out[next_free_loc] == 0xff:
        next_free_loc -= 1
    next_free_loc += 1

    # Extend ROM to be aligned on a 4-byte boundary.
    next_alignment = (next_free_loc + 4 - 1) // 4 * 4

    new_ptr = next_alignment | 0x08000000

    if text_archive['compressed']:
        new_ptr |= 0x80000000
        out_archive = pyfastgbalz77.compress(
            struct.pack('<I', (len(out_archive) + 4) << 8) + out_archive, True)

    out[next_alignment:next_alignment+len(out_archive)] = out_archive

    for loc in text_archive['locations']:
        old_ptr, = struct.unpack('<I', out[loc:loc+4])

        expected_ptr = text_archive["new"] | 0x08000000
        if text_archive['compressed']:
            expected_ptr |= 0x80000000

        print(f'0x{loc:08x}: 0x{expected_ptr:08x} -> 0x{new_ptr:08x}')

        if old_ptr != expected_ptr:
            raise Exception(
                f'text archive location mismatch: {old_ptr:08x} != {expected_ptr:08x}')

        out[loc:loc+4] = struct.pack('<I', new_ptr)

with open(sys.argv[4], 'wb') as f:
    f.write(out)

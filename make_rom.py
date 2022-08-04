#!/usr/bin/env python3
import enum
import io
import toml
import sys
import struct


class C(enum.Enum):
    Control = 0
    Text = 1


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


old = open(sys.argv[2], 'rb')

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

    # TODO: Handle LZ77 compression.
    offset = text_archive['old']
    old.seek(offset)

    header = unpack_text_archive_header(old)
    for i, suboffset in enumerate(header):
        old.seek(offset + suboffset)
        old_text = read_text(
            old,
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

    # Extend ROM to be aligned on a 4-byte boundary.
    next_alignment = (len(out) + 4 - 1) // 4 * 4
    out.extend(b'\0' * (next_alignment - len(out)))

    # TODO: Handle LZ77 compression.
    new_ptr = len(out)
    out.extend(out_archive)

    for loc in text_archive['locations']:
        old_ptr, = struct.unpack('<I', out[loc:loc+4])
        # TODO: Handle LZ77 compression.
        old_ptr &= ~0x88000000
        if old_ptr != text_archive['new']:
            raise Exception(
                f'text archive location mismatch: {old_ptr:08x} != {text_archive["new"]:08x}')

        out[loc:loc+4] = struct.pack('<I', new_ptr | 0x08000000)

with open(sys.argv[4], 'wb') as f:
    f.write(out)

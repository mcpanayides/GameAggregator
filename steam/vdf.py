"""
Minimal binary VDF reader/writer for Steam's shortcuts.vdf.

shortcuts.vdf is a binary key-value format. We only need enough of it to
read existing non-Steam shortcuts and append new ones without corrupting
the file. Format reference (reverse-engineered, stable for years):

  0x00  = nested object start, followed by null-terminated key
  0x01  = string field: 0x01 <key\0> <value\0>
  0x02  = int32 field:  0x02 <key\0> <4 bytes little-endian>
  0x08  = end of object
  0x08 0x08 at top level = end of file

Top-level structure:
  \x00 "shortcuts" \x00
     \x00 "0" \x00  <fields...> \x08
     \x00 "1" \x00  <fields...> \x08
     ...
  \x08 \x08
"""

import struct


def _read_cstr(data, i):
    end = data.index(b"\x00", i)
    return data[i:end].decode("utf-8", "replace"), end + 1


def parse(data: bytes):
    """Parse shortcuts.vdf bytes into a list of dicts (one per shortcut)."""
    shortcuts = []
    if not data:
        return shortcuts
    i = 0
    # Skip the leading \x00 "shortcuts" \x00
    if data[i] == 0x00:
        i += 1
        _, i = _read_cstr(data, i)  # "shortcuts"
    while i < len(data):
        t = data[i]
        if t == 0x08:  # end of shortcuts object (and file)
            break
        if t == 0x00:  # start of an indexed shortcut object
            i += 1
            _, i = _read_cstr(data, i)  # the index key "0", "1", ...
            entry = {}
            while data[i] != 0x08:
                ft = data[i]
                i += 1
                key, i = _read_cstr(data, i)
                if ft == 0x01:  # string
                    val, i = _read_cstr(data, i)
                    entry[key] = val
                elif ft == 0x02:  # int32
                    val = struct.unpack("<I", data[i:i + 4])[0]
                    i += 4
                    entry[key] = val
                elif ft == 0x00:  # nested object (e.g. "tags")
                    nested = {}
                    while data[i] != 0x08:
                        i += 1  # field type (string)
                        nk, i = _read_cstr(data, i)
                        nv, i = _read_cstr(data, i)
                        nested[nk] = nv
                    i += 1  # consume nested end 0x08
                    entry[key] = nested
            i += 1  # consume entry end 0x08
            shortcuts.append(entry)
        else:
            i += 1
    return shortcuts


def _write_field(key, value):
    if isinstance(value, dict):  # nested object, e.g. tags
        out = b"\x00" + key.encode() + b"\x00"
        for nk, nv in value.items():
            out += b"\x01" + str(nk).encode() + b"\x00" + str(nv).encode() + b"\x00"
        out += b"\x08"
        return out
    if isinstance(value, int):
        return b"\x02" + key.encode() + b"\x00" + struct.pack("<I", value & 0xFFFFFFFF)
    return b"\x01" + key.encode() + b"\x00" + str(value).encode() + b"\x00"


def dump(shortcuts) -> bytes:
    """Serialize a list of shortcut dicts back into shortcuts.vdf bytes."""
    out = b"\x00shortcuts\x00"
    for idx, entry in enumerate(shortcuts):
        out += b"\x00" + str(idx).encode() + b"\x00"
        for key, value in entry.items():
            out += _write_field(key, value)
        out += b"\x08"
    out += b"\x08\x08"
    return out

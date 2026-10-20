"""Minimal HWP 5.x text extractor (BodyText/Section*, handles compressed streams). Usage: python hwp_text.py in.hwp out.txt"""
import sys, struct, zlib, os
try:
    import olefile
except ImportError:
    sys.exit("pip install olefile  (needed to read .hwp)")

SINGLE = {10, 13, 24, 25, 26, 27, 28, 29, 30, 31, 0}

def para_text(data: bytes) -> str:
    out, i, n = [], 0, len(data) // 2
    w = struct.unpack("<%dH" % n, data[: n * 2])
    while i < n:
        c = w[i]
        if c >= 32:
            out.append(chr(c)); i += 1
        elif c in (10, 13):
            out.append("\n"); i += 1
        elif c in (30, 31):
            out.append(" "); i += 1
        elif c in SINGLE:
            i += 1
        else:                       # inline / extended control: 8 wchar total
            if c == 9: out.append("\t")
            i += 8
    return "".join(out)

def extract(path):
    ole = olefile.OleFileIO(path)
    hdr = ole.openstream("FileHeader").read()
    flags = struct.unpack("<I", hdr[36:40])[0]
    compressed, encrypted, distribution = bool(flags & 1), bool(flags & 2), bool(flags & 4)
    info = f"version={hdr[32:36][::-1].hex()} compressed={compressed} encrypted={encrypted} distribution={distribution}"
    if encrypted:
        return info, "ENCRYPTED (password) - cannot parse"
    sections = sorted([s for s in ole.listdir() if s[0] == "BodyText"], key=lambda s: int("".join(ch for ch in s[1] if ch.isdigit()) or 0))
    if distribution and not sections:
        sections = sorted([s for s in ole.listdir() if s[0] == "ViewText"])
    texts = []
    for s in sections:
        raw = ole.openstream("/".join(s)).read()
        if compressed:
            raw = zlib.decompress(raw, -15)
        pos = 0
        while pos + 4 <= len(raw):
            h = struct.unpack("<I", raw[pos:pos + 4])[0]
            tag, level, size = h & 0x3FF, (h >> 10) & 0x3FF, (h >> 20) & 0xFFF
            pos += 4
            if size == 0xFFF:
                size = struct.unpack("<I", raw[pos:pos + 4])[0]; pos += 4
            body = raw[pos:pos + size]; pos += size
            if tag == 67:           # HWPTAG_PARA_TEXT
                t = para_text(body).rstrip("\n")
                if t.strip():
                    texts.append(t)
    return info, "\n".join(texts)

if __name__ == "__main__":
    info, txt = extract(sys.argv[1])
    open(sys.argv[2], "w", encoding="utf-8").write(txt)
    print(info, "| chars:", len(txt), "| lines:", txt.count("\n") + 1)

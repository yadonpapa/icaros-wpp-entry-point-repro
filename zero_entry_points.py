"""Zero every entry_point_offset_minus1 field in an Annex B HEVC stream.

usage: zero_entry_points.py <in.h265> <trace.txt> <out.h265>

<trace.txt> is the output of
  ffmpeg -loglevel trace -i in.h265 -c:v copy -bsf:v trace_headers -f null -
filtered to the "[trace_headers ...]" lines (prefix stripped). Bit positions in that
trace are RBSP positions counted from the start of the NAL unit (2-byte header included),
so the fields are zeroed in the RBSP and emulation-prevention bytes are re-inserted.
"""
import re
import sys


def split_nals(data: bytes):
    """Return list of (start_code_bytes, nal_bytes) in file order."""
    pos = [m.start() for m in re.finditer(b"\x00\x00\x01", data)]
    nals = []
    for i, p in enumerate(pos):
        sc = 4 if p > 0 and data[p - 1] == 0 else 3
        start = p + 3
        end = pos[i + 1] - (1 if pos[i + 1] > 0 and data[pos[i + 1] - 1] == 0 else 0) if i + 1 < len(pos) else len(data)
        nals.append((data[start - sc:start], data[start:end]))
    return nals


def remove_epb(nal: bytes) -> bytes:
    out = bytearray()
    zeros = 0
    i = 0
    while i < len(nal):
        b = nal[i]
        if zeros >= 2 and b == 3 and i + 1 < len(nal) and nal[i + 1] <= 3:
            zeros = 0
            i += 1
            continue
        if zeros >= 2 and b == 3 and i + 1 == len(nal):
            break  # trailing cabac_zero/emulation byte
        out.append(b)
        zeros = zeros + 1 if b == 0 else 0
        i += 1
    return bytes(out)


def add_epb(rbsp: bytes) -> bytes:
    out = bytearray()
    zeros = 0
    for b in rbsp:
        if zeros >= 2 and b <= 3:
            out.append(3)
            zeros = 0
        out.append(b)
        zeros = zeros + 1 if b == 0 else 0
    if zeros >= 2:
        out.append(3)
    return bytes(out)


def zero_bits(buf: bytearray, bitpos: int, nbits: int) -> None:
    for k in range(nbits):
        p = bitpos + k
        buf[p >> 3] &= ~(0x80 >> (p & 7)) & 0xFF


def parse_trace(path: str):
    """Yield, per VCL NAL in trace order, a list of (bitpos, nbits) of entry_point_offset_minus1 fields."""
    blocks = []
    cur = None
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"nal_unit_type: (\d+)\(", line)
        if m:
            t = int(m.group(1))
            cur = [] if t <= 21 else None
            if cur is not None:
                blocks.append(cur)
            continue
        if cur is None:
            continue
        m = re.match(r"(\d+)\s+entry_point_offset_minus1\[\d+\]\s+([01]+)\s+=", line)
        if m:
            cur.append((int(m.group(1)), len(m.group(2))))
    return blocks


def main():
    src, trace, dst = sys.argv[1:4]
    data = open(src, "rb").read()
    nals = split_nals(data)
    fields = parse_trace(trace)
    vcl_idx = [i for i, (_, n) in enumerate(nals) if ((n[0] >> 1) & 0x3F) <= 21]
    if len(vcl_idx) != len(fields):
        sys.exit(f"VCL NAL count mismatch: file={len(vcl_idx)} trace={len(fields)}")
    out = bytearray()
    zeroed = 0
    for i, (sc, n) in enumerate(nals):
        if i in vcl_idx:
            flist = fields[vcl_idx.index(i)]
            if flist:
                rb = bytearray(remove_epb(n))
                for bitpos, nbits in flist:
                    zero_bits(rb, bitpos, nbits)
                    zeroed += 1
                n = add_epb(bytes(rb))
        out += sc + n
    open(dst, "wb").write(out)
    print(f"NALs={len(nals)} VCL={len(vcl_idx)} entry_point_offset fields zeroed={zeroed} bytes {len(data)} -> {len(out)}")


if __name__ == "__main__":
    main()

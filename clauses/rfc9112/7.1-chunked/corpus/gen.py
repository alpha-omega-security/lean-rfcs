"""
Grammar-derived corpus for RFC 9112 §7.1 chunked-body.

The grammar is encoded as an ordered list of terminal positions. A valid
body is the concatenation of each position's canonical bytes. For every
terminal position we also enumerate a fixed violation set. The corpus is
then: one valid body, plus one body per (position, violation) pair with
exactly that terminal replaced.

No knowledge of any specific CVE is encoded here; the violation sets are
generic (drop, truncate, substitute, wrong-length) applied uniformly to
every terminal.
"""

import random


CRLF = b"\r\n"


def crlf_violations(rnd):
    return [
        b"",                                  # dropped
        b"\n",                                # LF only
        b"\r",                                # CR only
        bytes([rnd.randint(0, 255)]),         # 1 arbitrary byte
        bytes([rnd.randint(0, 255)] * 2),     # 2 arbitrary bytes, same length as CRLF
        b"\r\r\n",                            # doubled CR
        b" \r\n",                             # leading whitespace
    ]


def hex_violations(rnd, n):
    return [
        b"",                                  # 0 digits
        b"Z" + format(n, "x").encode(),       # non-hex prefix
        b"-" + format(n, "x").encode(),       # sign
        b"0x" + format(n, "x").encode(),      # 0x prefix
    ]


def data_violations(rnd, data):
    return [
        data[:-1],                            # one short
        data + rnd.randbytes(1),              # one long
        data + rnd.randbytes(len(data)),      # doubled
    ]


def zero_violations(rnd):
    return [
        b"",                                  # missing last-chunk
        b"00",                                # multiple zeros (actually valid per RFC)
    ]


def build_template(rnd):
    """One data chunk + last-chunk + no trailers + final CRLF.
    Returns list of (position_name, canonical_bytes, violation_fn)."""
    data = rnd.randbytes(rnd.randint(4, 16))
    size = format(len(data), "x").encode()
    return [
        ("chunk_size",   size,  lambda r: hex_violations(r, len(data))),
        ("size_crlf",    CRLF,  crlf_violations),
        ("chunk_data",   data,  lambda r: data_violations(r, data)),
        ("data_crlf",    CRLF,  crlf_violations),
        ("last_zero",    b"0",  zero_violations),
        ("last_crlf",    CRLF,  crlf_violations),
        ("final_crlf",   CRLF,  crlf_violations),
    ]


def render(tmpl, override_idx=None, override_bytes=None):
    out = bytearray()
    for i, (_, canon, _) in enumerate(tmpl):
        out += override_bytes if i == override_idx else canon
    return bytes(out)


def corpus(seed, n_templates):
    """Yield (label, bytes) for n_templates base templates × all single-fault mutations."""
    rnd = random.Random(seed)
    out = []
    for _ in range(n_templates):
        tmpl = build_template(rnd)
        out.append(("valid", render(tmpl)))
        for i, (name, _, viol_fn) in enumerate(tmpl):
            for j, v in enumerate(viol_fn(rnd)):
                out.append((f"{name}:v{j}", render(tmpl, i, v)))
    return out


if __name__ == "__main__":
    import sys
    for label, buf in corpus(0, 1):
        print(f"{label:20} {buf!r}")

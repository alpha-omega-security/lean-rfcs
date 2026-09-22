#!/usr/bin/env python3
"""Gate 2: oracle must accept every must_accept and reject every must_reject."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oracle as oracle_mod


def main(clause_dir):
    o, meta = oracle_mod.for_clause(clause_dir)
    ctrl = json.load(open(os.path.join(clause_dir, "controls.json")))
    fail = 0
    for kind, expect in [("must_accept", True), ("must_reject", False)]:
        for c in ctrl[kind]:
            buf = bytes.fromhex(c["hex"])
            ok, body = o.check(buf)
            mark = "ok" if ok == expect else "FAIL"
            if ok != expect:
                fail += 1
            elif expect and "expect_body_hex" in c and body.hex() != c["expect_body_hex"]:
                mark, fail = "FAIL(body)", fail + 1
            print(f"  [{mark}] {c['id']:36} accept={ok}")
    o.close()
    print(f"{meta['id']}: {fail} failures")
    return fail


if __name__ == "__main__":
    total = 0
    for d in sys.argv[1:] or ["clauses/rfc9112/7.1-chunked"]:
        total += main(d)
    sys.exit(1 if total else 0)

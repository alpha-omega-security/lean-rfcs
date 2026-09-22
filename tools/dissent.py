#!/usr/bin/env python3
"""Gate 5: for every input the oracle accepts that any reference adapter
rejects, require a matching `dissent:` note in SPEC.md."""
import json
import os
import re
import sys


def load_dissent_notes(clause_dir):
    spec = os.path.join(clause_dir, "SPEC.md")
    if not os.path.exists(spec):
        return set()
    notes = set()
    for line in open(spec):
        m = re.match(r"^\s*-\s*dissent:\s*(\S+)", line)
        if m:
            notes.add(m.group(1))
    return notes


def main(clause_dir):
    meta = json.load(open(os.path.join(clause_dir, "clause.json")))
    m = json.load(open(os.path.join("matrix", meta["id"] + ".json")))
    notes = load_dissent_notes(clause_dir)
    flags = []
    for row in m["rows"]:
        if not row["oracle"]["accept"]:
            continue
        rejecters = [a for a in m["adapters"] if not row[a]["accept"]]
        if rejecters:
            label = row["id"].split("/")[1] if "/" in row["id"] else row["id"]
            flags.append((row["id"], label, rejecters))
    unnoted = [f for f in flags if f[1] not in notes]
    print(f"{meta['id']}: {len(flags)} oracle-accepts-adapter-rejects; {len(unnoted)} without SPEC.md dissent note")
    for rid, label, rej in unnoted[:20]:
        print(f"  FLAG {rid}: rejected by {rej}")
    return len(unnoted)


if __name__ == "__main__":
    total = 0
    for d in sys.argv[1:] or ["clauses/rfc9112/7.1-chunked"]:
        total += main(d)
    sys.exit(1 if total else 0)

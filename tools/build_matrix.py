#!/usr/bin/env python3
"""Gate 4: run every adapter for the clause's protocol against the corpus."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oracle as oracle_mod
import adapter as adapter_mod


def main(clause_dir, python):
    o, meta = oracle_mod.for_clause(clause_dir)
    names = adapter_mod.list_adapters(meta["protocol"])
    versions = {n: adapter_mod.adapter_version(meta["protocol"], n, python) for n in names}
    adapters = {n: adapter_mod.Adapter(meta["protocol"], n, python) for n in names}

    corpus = []
    with open(os.path.join(clause_dir, "corpus", "seed0.jsonl")) as f:
        for line in f:
            corpus.append(json.loads(line))

    rows = []
    for inp in corpus:
        buf = bytes.fromhex(inp["hex"])
        ok, body = o.check(buf)
        row = {"id": inp["id"], "oracle": {"accept": ok, "body_hex": body.hex() if body is not None else None}}
        for name, a in adapters.items():
            v = a.feed(buf)
            row[name] = v
        rows.append(row)

    o.close()
    for a in adapters.values():
        a.close()

    matrix = {
        "clause": meta["id"],
        "adapters": names,
        "adapter_versions": versions,
        "rows": rows,
    }
    os.makedirs("matrix", exist_ok=True)
    out = os.path.join("matrix", meta["id"] + ".json")
    with open(out, "w") as f:
        json.dump(matrix, f, indent=2)
    print(f"{meta['id']}: {len(rows)} inputs × {len(names)} adapters → {out}")


if __name__ == "__main__":
    py = os.environ.get("ADAPTER_PYTHON", "python3")
    for d in sys.argv[1:] or ["clauses/rfc9112/7.1-chunked"]:
        main(d, py)

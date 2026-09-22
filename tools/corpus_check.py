#!/usr/bin/env python3
"""Gate 3: regenerate the corpus to a temp file and compare byte-for-byte
with the committed seed0.jsonl. Never touches the committed file, so
readers running in parallel are safe."""
import importlib.util
import json
import os
import sys


def main(clause_dir, seed=0, n=50):
    gen_path = os.path.join(clause_dir, "corpus", "gen.py")
    committed = os.path.join(clause_dir, "corpus", f"seed{seed}.jsonl")
    spec = importlib.util.spec_from_file_location("gen", gen_path)
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    lines = []
    for i, (label, buf) in enumerate(gen.corpus(seed=seed, n_templates=n)):
        lines.append(json.dumps({"id": f"seed{seed}/{label}/{i}",
                                 "label": label, "hex": buf.hex()}) + "\n")
    fresh = "".join(lines)
    with open(committed) as f:
        existing = f.read()
    if fresh != existing:
        print(f"gate 3: corpus not deterministic: {clause_dir}")
        return 1
    print(f"gate 3: {clause_dir} corpus deterministic ({len(lines)} inputs)")
    return 0


if __name__ == "__main__":
    total = 0
    for d in sys.argv[1:] or ["clauses/rfc9112/7.1-chunked"]:
        total += main(d)
    sys.exit(1 if total else 0)

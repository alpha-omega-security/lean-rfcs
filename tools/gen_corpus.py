#!/usr/bin/env python3
"""Gate 3: regenerate corpus/seed0.jsonl from corpus/gen.py at seed 0."""
import importlib.util
import json
import os
import sys


def main(clause_dir, seed=0, n=50):
    gen_path = os.path.join(clause_dir, "corpus", "gen.py")
    spec = importlib.util.spec_from_file_location("gen", gen_path)
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    out_path = os.path.join(clause_dir, "corpus", f"seed{seed}.jsonl")
    with open(out_path, "w") as f:
        for i, (label, buf) in enumerate(gen.corpus(seed=seed, n_templates=n)):
            f.write(json.dumps({"id": f"seed{seed}/{label}/{i}", "label": label, "hex": buf.hex()}) + "\n")
    print(f"{clause_dir}: wrote {out_path}")


if __name__ == "__main__":
    for d in sys.argv[1:] or ["clauses/rfc9112/7.1-chunked"]:
        main(d)

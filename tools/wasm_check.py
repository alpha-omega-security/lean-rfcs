#!/usr/bin/env python3
"""Native and WASM oracles must produce identical output on every corpus
input. Catches word-size and runtime differences (e.g. 32-bit small-Nat
threshold on WASM vs 64-bit native)."""
import json
import os
import subprocess
import sys

WASM_RUN = os.environ.get("WASM_RUN", "wasmtime").split()


def main(clause_dir):
    meta = json.load(open(os.path.join(clause_dir, "clause.json")))
    cid = meta["id"]
    hexes = []
    with open(os.path.join(clause_dir, "corpus", "seed0.jsonl")) as f:
        for line in f:
            hexes.append(json.loads(line)["hex"])
    ctrl = json.load(open(os.path.join(clause_dir, "controls.json")))
    for c in ctrl["must_accept"] + ctrl["must_reject"]:
        hexes.append(c["hex"])
    stdin = ("\n".join(hexes) + "\n").encode()

    native = subprocess.run([f"dist/{cid}-oracle"], input=stdin,
                            capture_output=True, check=True).stdout
    wasm = subprocess.run(WASM_RUN + [f"dist/{cid}-oracle.wasm"], input=stdin,
                          capture_output=True, check=True).stdout
    if native != wasm:
        nl, wl = native.splitlines(), wasm.splitlines()
        for i, (a, b) in enumerate(zip(nl, wl)):
            if a != b:
                print(f"  DIVERGE at input {i}: hex={hexes[i]}")
                print(f"    native: {a!r}")
                print(f"    wasm:   {b!r}")
        if len(nl) != len(wl):
            print(f"  DIVERGE: native {len(nl)} lines, wasm {len(wl)} lines")
        print(f"wasm-check: {cid} FAILED")
        return 1
    print(f"wasm-check: {cid} native == wasm ({len(hexes)} inputs)")
    return 0


if __name__ == "__main__":
    total = 0
    for d in sys.argv[1:] or ["clauses/rfc9112/7.1-chunked"]:
        total += main(d)
    sys.exit(1 if total else 0)

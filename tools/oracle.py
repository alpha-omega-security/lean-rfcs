"""Wrapper around a compiled oracle binary (native or wasm)."""
import json
import os
import subprocess


class Oracle:
    def __init__(self, binary, runner=None):
        argv = [binary] if runner is None else runner + [binary]
        self.proc = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, bufsize=1,
        )

    def check(self, buf: bytes):
        self.proc.stdin.write(buf.hex() + "\n")
        self.proc.stdin.flush()
        r = json.loads(self.proc.stdout.readline())
        body = bytes.fromhex(r["body"]) if r.get("body") is not None else None
        return r["valid"], body

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=2)
        except Exception:
            self.proc.kill()


def for_clause(clause_dir, dist_dir="dist"):
    meta = json.load(open(os.path.join(clause_dir, "clause.json")))
    native = os.path.join(dist_dir, meta["id"] + "-oracle")
    if os.path.exists(native):
        return Oracle(native), meta
    wasm = os.path.join(dist_dir, meta["id"] + "-oracle.wasm")
    if os.path.exists(wasm):
        return Oracle(wasm, runner=["wasmtime"]), meta
    raise FileNotFoundError(f"no oracle for {meta['id']} in {dist_dir}")

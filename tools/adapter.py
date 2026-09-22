"""Wrapper around an adapter process (adapters/<protocol>/<name>)."""
import json
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _argv(protocol, name, python):
    d = os.path.join(ROOT, "adapters", protocol)
    if os.path.isfile(os.path.join(d, name + ".py")):
        return [python, os.path.join(d, name + ".py")]
    if os.path.isdir(os.path.join(d, name)):
        exe = os.path.join(d, name, name)
        return [exe]
    raise FileNotFoundError(f"adapter {protocol}/{name}")


class Adapter:
    def __init__(self, protocol, name, python="python3"):
        self.name = name
        self.proc = subprocess.Popen(
            _argv(protocol, name, python),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, bufsize=1,
        )

    def feed(self, buf: bytes):
        self.proc.stdin.write(buf.hex() + "\n")
        self.proc.stdin.flush()
        return json.loads(self.proc.stdout.readline())

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=2)
        except Exception:
            self.proc.kill()


def list_adapters(protocol):
    d = os.path.join(ROOT, "adapters", protocol)
    out = []
    for e in sorted(os.listdir(d)):
        if e.startswith("_") or e.startswith("."):
            continue
        if e.endswith(".py"):
            out.append(e[:-3])
        elif os.path.isdir(os.path.join(d, e)):
            out.append(e)
    return out


def adapter_version(protocol, name, python="python3"):
    """Best-effort version of the implementation an adapter wraps."""
    if name.startswith("pypi-"):
        pkg = name[len("pypi-"):]
        r = subprocess.run(
            [python, "-c", f"from importlib.metadata import version; print(version({pkg!r}))"],
            capture_output=True, text=True,
        )
        return r.stdout.strip() or "unknown"
    if name.startswith("go-"):
        r = subprocess.run(["go", "version"], capture_output=True, text=True)
        parts = r.stdout.split()
        return parts[2] if len(parts) > 2 else "unknown"
    return "unknown"

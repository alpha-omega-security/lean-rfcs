#!/usr/bin/env python3
import json
import sys
import h11

REQ_HEAD = b"POST / HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\n"


def feed(buf):
    conn = h11.Connection(h11.SERVER)
    total = REQ_HEAD + buf
    conn.receive_data(total)
    body = bytearray()
    try:
        while True:
            ev = conn.next_event()
            if ev is h11.NEED_DATA:
                return {"accept": False, "error": "incomplete"}
            if isinstance(ev, h11.Request):
                continue
            if isinstance(ev, h11.Data):
                body += ev.data
                continue
            if isinstance(ev, h11.EndOfMessage):
                trailing, _ = conn.trailing_data
                consumed = len(total) - len(REQ_HEAD) - len(trailing)
                return {"accept": True, "body_hex": bytes(body).hex(), "consumed": consumed}
            return {"accept": False, "error": f"unexpected:{type(ev).__name__}"}
    except h11.RemoteProtocolError as e:
        return {"accept": False, "error": str(e)}


for line in sys.stdin:
    hx = line.strip()
    try:
        buf = bytes.fromhex(hx)
    except ValueError:
        print(json.dumps({"accept": False, "error": "bad-hex"}))
        continue
    print(json.dumps(feed(buf)))
    sys.stdout.flush()

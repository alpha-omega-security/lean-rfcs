#!/usr/bin/env python3
import json
import sys
import httptools

REQ_HEAD = b"POST / HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\n"


class P:
    def __init__(self):
        self.body = bytearray()
        self.done = False
    def on_body(self, d):
        if not self.done:
            self.body += d
    def on_message_complete(self): self.done = True


def feed(buf):
    p = P()
    parser = httptools.HttpRequestParser(p)
    total = REQ_HEAD + buf
    # Feed one byte at a time so we can stop precisely at the first
    # message boundary; trailing bytes must not affect the verdict.
    try:
        for i in range(len(total)):
            parser.feed_data(total[i:i+1])
            if p.done:
                consumed = i + 1 - len(REQ_HEAD)
                return {"accept": True, "body_hex": bytes(p.body).hex(),
                        "consumed": consumed}
    except httptools.HttpParserError as e:
        if p.done:
            return {"accept": True, "body_hex": bytes(p.body).hex()}
        return {"accept": False, "error": str(e)}
    return {"accept": False, "error": "incomplete"}


for line in sys.stdin:
    hx = line.strip()
    try:
        buf = bytes.fromhex(hx)
    except ValueError:
        print(json.dumps({"accept": False, "error": "bad-hex"}))
        continue
    print(json.dumps(feed(buf)))
    sys.stdout.flush()

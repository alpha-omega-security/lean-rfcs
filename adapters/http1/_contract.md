# http1 adapter contract

One process per implementation. stdin: newline-delimited hex-encoded chunked-body byte strings. stdout: newline-delimited JSON verdicts, one per input line, in order.

Verdict:

    {"accept": true,  "body_hex": "68656c6c6f", "consumed": 18}
    {"accept": false, "error": "..."}

`consumed` is optional. Adapters that cannot compute the byte offset omit the key.

For §7.1 the input is a chunked-body alone (no request line, no headers). The adapter wraps it in a minimal `POST / HTTP/1.1` request with `Transfer-Encoding: chunked` if the underlying parser needs a full request.

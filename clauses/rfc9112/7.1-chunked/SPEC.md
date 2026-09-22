# RFC 9112 §7.1 chunked transfer coding

Scope: request-side chunked-body only. `chunk = chunk-size [chunk-ext] CRLF chunk-data CRLF`, `last-chunk = 1*"0" [chunk-ext] CRLF`, `trailer-section = *(field-line CRLF)`, final CRLF.

Model restrictions relative to the RFC grammar:

- chunk-size is 1..15 HEXDIG (RFC: `1*HEXDIG`, unbounded). A 16th digit is rejected. Values stay below 2^60 so the oracle needs no arbitrary-precision arithmetic; every reference implementation rejects a 2^60-byte chunk anyway.
- chunk-ext-name and chunk-ext-val are not validated beyond "no bare CR/LF and a leading `;`".
- trailer field-lines must contain a `:` (RFC 9110 §5.1 field-line requires one) but field-name and field-value are not otherwise validated.

Property P1 (`Rfc9112.valid`): chunk framing (size, data, terminators, last-chunk, trailer-section CRLF sequence) matches the grammar under the restrictions above. Decidable via `parseChunkedBody`.

Proof `takeCRLF_sound` (in `lean/Rfc9112/Chunked.lean`): if `takeCRLF c = some c'` then the two bytes at `c` are exactly CR LF and `c'` is `c` advanced by 2. `parseChunk` on a nonzero chunk requires `takeCRLF` immediately after `takeData`, so no data chunk is accepted with any other terminator.

Dissent notes (gate 5): none. All inputs the oracle accepts are accepted by every reference adapter.

Known permitted leniences (oracle rejects, RFC MAY permits, some adapters accept):

- Bare LF as final-CRLF terminator (§2.2 permits for start-line and fields; trailers are fields). h11, Go, HAProxy accept.
- These are `deviates` findings against those adapters, not `permitted-lenient`, until an oracle-lenient predicate encoding §2.2 is added.

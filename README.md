# lean-rfcs

Formal models of RFC clauses as Lean 4 decision procedures, compiled to portable WASM oracles, plus reference adapters and a per-clause behaviour matrix.

    lean/                     Lean sources, one module per clause
    clauses/<rfc>/<sec>/      per-clause assets: clause.json, SPEC.md, controls.json, corpus/
    adapters/<protocol>/      reference adapters implementing adapters/<protocol>/_contract.md
    tools/                    shim.c, leanrt_lite.c, gate scripts
    matrix/                   generated: oracle + adapter verdicts per corpus row
    dist/                     generated: <clause>-oracle (native) and <clause>-oracle.wasm

## Build

    make lean         # gate 1: lake build, no sorry
    make oracle       # native oracle binaries in dist/
    make dist         # WASM oracles (needs WASI_SDK=/path/to/wasi-sdk)
    make adapters     # build reference adapters
    make gates        # gates 1-5

## Gates

1. `lake build` typechecks; no `sorry` in any clause.
2. `tools/check_controls.py`: oracle agrees with every `must_accept` / `must_reject` in `controls.json`.
3. `tools/gen_corpus.py` regenerates `seed0.jsonl`; `git diff --exit-code` proves determinism.
4. `tools/build_matrix.py`: every adapter run against the corpus, `matrix/<clause>.json` written.
5. `tools/dissent.py`: for every input the oracle accepts that any reference adapter rejects, a `- dissent: <label>` line in the clause's `SPEC.md` must cite the RFC text that permits acceptance.

## Adding a clause

Add `lean/<Rfc>/<Name>.lean` with a `parseX : ByteArray → Option ByteArray` (or equivalent decidable predicate) and any proofs. Add `clauses/<rfc>/<sec>/{clause.json,SPEC.md,controls.json,corpus/gen.py}`. Add the clause id to `CLAUSES` in the Makefile. Run `make gates`.

## Oracle distribution

`tools/shim.c` (55 lines) + `tools/leanrt_lite.c` (159 lines) + the Lean-generated `.c` compile with only libc; the same three files compile for `wasm32-wasip1` via wasi-sdk. The WASM module runs under wazero (pure Go, no cgo) with byte-identical output to native. `leanrt_lite.c` provides a malloc allocator, ctor/sarray destructor, and ByteArray extract/append; big-Nat and closure-apply paths abort since pure grammar oracles never reach them.

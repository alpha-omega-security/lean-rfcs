LEAN_ROOT := $(shell lean --print-prefix)
LEAN_INC  := $(LEAN_ROOT)/include
CLAUSES   := clauses/rfc9112/7.1-chunked
PYTHON    ?= tools/venv/bin/python3
WASI_SDK  ?= /tmp/wasi-sdk
WASM_RUN  ?= wasmtime

# Derive clause ids from clause.json so adding to CLAUSES is the only
# per-clause Makefile edit.
clause_id = $(shell python3 -c "import json;print(json.load(open('$(1)/clause.json'))['id'])")
CLAUSE_IDS := $(foreach c,$(CLAUSES),$(call clause_id,$(c)))
ORACLES_NATIVE := $(foreach id,$(CLAUSE_IDS),dist/$(id)-oracle)
ORACLES_WASM   := $(foreach id,$(CLAUSE_IDS),dist/$(id)-oracle.wasm)

.PHONY: all lean lean-c oracle adapters corpus controls matrix dissent \
        gates wasm-check dist venv clean sorry-check compile_flags.txt

all: gates

lean:
	lake build

# Gate 1 also fails on `sorry`: lake exits 0 with a warning, so grep.
sorry-check: lean
	@! grep -RIn --include='*.lean' -w sorry lean/ \
	  || (echo "gate 1: sorry present in source"; exit 1)

# Force emission of :c artefacts (lake build alone may skip them for a lib).
lean-c: lean
	@for c in $(CLAUSES); do \
	  cf=$$(python3 -c "import json;print(json.load(open('$$c/clause.json'))['lean_c'])"); \
	  test -f $$cf || lake build $$(python3 -c "import json;print(json.load(open('$$c/clause.json'))['lean_module'])"):c; \
	done

define ORACLE_CC
  cid=$*; \
  cdir=$$(grep -rl '"id": "'"$$cid"'"' clauses --include=clause.json | xargs dirname); \
  meta() { python3 -c "import json,sys;print(json.load(open('$$cdir/clause.json'))[sys.argv[1]])" $$1; }
endef

dist/%-oracle: lean-c tools/shim.c tools/leanrt_lite.c
	@mkdir -p dist
	@$(ORACLE_CC); \
	  cc -O2 -I$(LEAN_INC) \
	    -DCLAUSE_PARSE=$$(meta parse_symbol) -DCLAUSE_INIT=$$(meta init_symbol) \
	    tools/shim.c $$(meta lean_c) tools/leanrt_lite.c -o $@

dist/%-oracle.wasm: lean-c tools/shim.c tools/leanrt_lite.c
	@mkdir -p dist
	@$(ORACLE_CC); \
	  $(WASI_SDK)/bin/clang --target=wasm32-wasip1 --sysroot=$(WASI_SDK)/share/wasi-sysroot \
	    -O2 -I$(LEAN_INC) \
	    -DCLAUSE_PARSE=$$(meta parse_symbol) -DCLAUSE_INIT=$$(meta init_symbol) \
	    tools/shim.c $$(meta lean_c) tools/leanrt_lite.c -o $@

oracle: $(ORACLES_NATIVE)

dist: $(ORACLES_WASM)

venv:
	@test -d tools/venv || (uv venv tools/venv --python 3.12 && uv pip install --python tools/venv h11 httptools)

adapters: venv
	cd adapters/http1/go-nethttp && go mod tidy && go build -o go-nethttp .

corpus:
	python3 tools/gen_corpus.py $(CLAUSES)

controls: oracle
	python3 tools/check_controls.py $(CLAUSES)

matrix: oracle adapters | corpus-check
	ADAPTER_PYTHON=$(PYTHON) python3 tools/build_matrix.py $(CLAUSES)

dissent: matrix
	python3 tools/dissent.py $(CLAUSES)

# Gate 3: regenerate to a temp file and compare; never overwrites the
# committed seed0.jsonl, so parallel readers are safe.
corpus-check:
	@python3 tools/corpus_check.py $(CLAUSES)

# WASM gate: native and wasm oracles must agree byte-for-byte on every
# corpus input.
wasm-check: oracle dist
	@python3 tools/wasm_check.py $(CLAUSES)

gates: sorry-check controls corpus-check matrix dissent
gates-wasm: gates wasm-check

compile_flags.txt:
	echo "-I$(LEAN_INC)" > $@

clean:
	rm -rf .lake dist matrix/*.json tools/venv adapters/http1/go-nethttp/go-nethttp compile_flags.txt

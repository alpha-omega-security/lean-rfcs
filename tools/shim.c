// Generic C shim: reads hex-encoded inputs on stdin, calls the pure
// Lean parse function, writes JSON verdicts on stdout. Compiled per
// clause with -DCLAUSE_PARSE=<sym> -DCLAUSE_INIT=<sym>.
#include <lean/lean.h>
#include <stdio.h>
#include <string.h>

#ifndef CLAUSE_PARSE
#error "define -DCLAUSE_PARSE=lp_leanrfcs_<Ns>_<fn>"
#endif
#ifndef CLAUSE_INIT
#error "define -DCLAUSE_INIT=initialize_leanrfcs_<Module>"
#endif

extern lean_object* CLAUSE_PARSE(lean_object*);
extern lean_object* CLAUSE_INIT(uint8_t builtin);

static int hexval(int c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

int main(void) {
    lean_object* r = CLAUSE_INIT(1);
    if (lean_io_result_is_error(r)) return 1;
    lean_dec_ref(r);
    lean_io_mark_end_initialization();

    char* line = NULL;
    size_t cap = 0;
    ssize_t rn;
    while ((rn = getline(&line, &cap, stdin)) >= 0) {
        size_t n = (size_t)rn;
        while (n && (line[n-1] == '\n' || line[n-1] == '\r')) n--;
        if (n % 2) { printf("{\"valid\":false,\"body\":null,\"error\":\"bad-hex\"}\n"); fflush(stdout); continue; }
        size_t blen = n / 2;
        lean_object* ba = lean_alloc_sarray(1, blen, blen);
        uint8_t* dst = lean_sarray_cptr(ba);
        int bad = 0;
        for (size_t i = 0; i < blen; i++) {
            int hi = hexval(line[2*i]), lo = hexval(line[2*i+1]);
            if (hi < 0 || lo < 0) { bad = 1; break; }
            dst[i] = (uint8_t)(hi * 16 + lo);
        }
        if (bad) { lean_dec(ba); printf("{\"valid\":false,\"body\":null,\"error\":\"bad-hex\"}\n"); fflush(stdout); continue; }

        lean_object* res = CLAUSE_PARSE(ba);
        if (lean_obj_tag(res) == 0) {
            printf("{\"valid\":false,\"body\":null}\n");
        } else {
            lean_object* body = lean_ctor_get(res, 0);
            size_t bl = lean_sarray_size(body);
            uint8_t* bp = lean_sarray_cptr(body);
            printf("{\"valid\":true,\"body\":\"");
            for (size_t i = 0; i < bl; i++) printf("%02x", bp[i]);
            printf("\"}\n");
        }
        lean_dec(res);
        fflush(stdout);
    }
    free(line);
    return 0;
}

// Minimal Lean runtime for the pure Rfc9112 oracle. Provides only the
// symbols shim.o + Rfc9112.o reference. Allocator = malloc; big-Nat and
// closure-apply = abort (unreachable on this oracle's inputs).
#include <lean/lean.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

__attribute__((noreturn))
static void die(const char* s) { fprintf(stderr, "leanrt_lite: %s\n", s); abort(); }

// -- allocator ---------------------------------------------------------

void* mi_malloc_small(size_t sz) { return malloc(sz); }
void* mi_malloc(size_t sz) { return malloc(sz); }
void mi_free(void* p) { free(p); }
void lean_inc_ref_huge_n(lean_object* o, size_t n) { die("inc_huge"); }

lean_object* lean_alloc_object(size_t sz) {
    lean_object* o = (lean_object*)malloc(sz);
    if (!o) die("oom");
    return o;
}

void lean_free_object(lean_object* o) { free(o); }

void lean_internal_panic_out_of_memory(void) { die("oom"); }
void lean_internal_panic(const char* msg) { die(msg); }
void lean_internal_panic_unreachable(void) { die("unreachable"); }
void lean_internal_panic_overflow(void) { die("overflow"); }
void lean_mark_persistent(lean_object* o) {
    // m_rc == 0 means persistent. The real runtime recurses into
    // children; this lite version handles only leaf objects (sarray,
    // string, mpz) and rejects composites so a future clause with a
    // composite constant fails loudly instead of corrupting refcounts.
    if (lean_is_scalar(o)) return;
    switch (lean_ptr_tag(o)) {
        case LeanScalarArray:
        case LeanString:
        case LeanMPZ:
            o->m_rc = 0;
            return;
        default:
            die("mark_persistent: composite object; extend leanrt_lite");
    }
}
void lean_notify_assert(const char* f, int l, const char* c) {
    fprintf(stderr, "assert failed: %s at %s:%d\n", c, f, l); abort();
}
void lean_inc_heartbeat(void) {}

// -- destructor: free an object whose RC has hit zero -------------------

void lean_del_ctor(lean_object* o) {
    unsigned n = lean_ctor_num_objs(o);
    lean_object** p = lean_ctor_obj_cptr(o);
    for (unsigned i = 0; i < n; i++) lean_dec(p[i]);
    lean_free_object(o);
}

void lean_dec_ref_cold(lean_object* o) {
    switch (lean_ptr_tag(o)) {
        case LeanArray: {
            size_t n = lean_array_size(o);
            lean_object** p = lean_array_cptr(o);
            for (size_t i = 0; i < n; i++) lean_dec(p[i]);
            lean_free_object(o);
            return;
        }
        case LeanScalarArray:
        case LeanString:
            lean_free_object(o);
            return;
        case LeanClosure: {
            unsigned n = lean_closure_num_fixed(o);
            lean_object** p = lean_closure_arg_cptr(o);
            for (unsigned i = 0; i < n; i++) lean_dec(p[i]);
            lean_free_object(o);
            return;
        }
        case LeanMPZ:
            lean_free_small_object(o);
            return;
        case LeanExternal:
        case LeanReserved:
        case LeanThunk:
        case LeanTask:
        case LeanRef:
            die("dec_ref_cold: unsupported tag");
        default:
            lean_del_ctor(o);
            return;
    }
}

// -- ByteArray (from libInit) ------------------------------------------

lean_object* l_ByteArray_empty;

// src, soff, doff, len are borrowed; dst is owned (consumed).
lean_object* lean_byte_array_copy_slice(lean_object* src, lean_object* soff_o,
                                         lean_object* dst, lean_object* doff_o,
                                         lean_object* len_o, uint8_t exact) {
    size_t soff = lean_unbox(soff_o);
    size_t doff = lean_unbox(doff_o);
    size_t len  = lean_unbox(len_o);
    size_t ssz = lean_sarray_size(src);
    if (soff > ssz) soff = ssz;
    if (soff + len > ssz) len = ssz - soff;
    lean_object* d = dst;
    if (!lean_is_exclusive(dst)) {
        size_t dcap = lean_sarray_size(dst);
        d = lean_alloc_sarray(1, dcap, dcap);
        memcpy(lean_sarray_cptr(d), lean_sarray_cptr(dst), dcap);
        lean_dec(dst);
    }
    size_t dsz = lean_sarray_size(d);
    // Lean's copySlice clamps doff to dst.size; matching that avoids
    // exposing uninitialized bytes when a caller passes doff > size.
    if (doff > dsz) doff = dsz;
    size_t need = doff + len;
    if (need > lean_sarray_capacity(d)) {
        size_t cap = need > dsz * 2 ? need : dsz * 2;
        lean_object* nd = lean_alloc_sarray(1, dsz, cap);
        memcpy(lean_sarray_cptr(nd), lean_sarray_cptr(d), dsz);
        lean_dec(d);
        d = nd;
    }
    memcpy(lean_sarray_cptr(d) + doff, lean_sarray_cptr(src) + soff, len);
    if (need > dsz) lean_sarray_set_size(d, need);
    (void)exact;
    return d;
}

// a, b, e are borrowed.
lean_object* l_ByteArray_extract(lean_object* a, lean_object* b_o, lean_object* e_o) {
    size_t b = lean_unbox(b_o), e = lean_unbox(e_o);
    size_t sz = lean_sarray_size(a);
    if (b > sz) b = sz;
    if (e > sz) e = sz;
    if (e < b) e = b;
    size_t n = e - b;
    lean_object* r = lean_alloc_sarray(1, n, n);
    memcpy(lean_sarray_cptr(r), lean_sarray_cptr(a) + b, n);
    return r;
}

// -- big-Nat: uint64-backed heap Nat -----------------------------------
// The Lean model caps hex accumulation at 15 digits (< 2^60), so every
// Nat fits in uint64. On 32-bit targets the small-Nat threshold is
// 2^31, so values in [2^31, 2^60) take this path. On 64-bit targets
// the small-Nat threshold is 2^63 and this path is unreachable.

typedef struct { lean_object m_header; uint64_t m_val; } lite_nat;

static lean_object* lite_nat_mk(uint64_t v) {
    if (v <= LEAN_MAX_SMALL_NAT) return lean_box((size_t)v);
    lite_nat* o = (lite_nat*)lean_alloc_small_object(sizeof(lite_nat));
    lean_set_st_header((lean_object*)o, LeanMPZ, 0);
    o->m_val = v;
    return (lean_object*)o;
}

static uint64_t lite_nat_val(lean_object* o) {
    return lean_is_scalar(o) ? (uint64_t)lean_unbox(o) : ((lite_nat*)o)->m_val;
}

lean_object* lean_big_usize_to_nat(size_t n) { return lite_nat_mk((uint64_t)n); }

lean_object* lean_nat_overflow_mul(size_t a, size_t b) {
    uint64_t r;
    if (__builtin_mul_overflow((uint64_t)a, (uint64_t)b, &r)) die("nat > 2^64");
    return lite_nat_mk(r);
}

// Args are borrowed (via b_lean_obj_arg in lean_nat_add/sub/mul).
lean_object* lean_nat_big_add(lean_object* a, lean_object* b) {
    uint64_t r;
    if (__builtin_add_overflow(lite_nat_val(a), lite_nat_val(b), &r)) die("nat > 2^64");
    return lite_nat_mk(r);
}

lean_object* lean_nat_big_sub(lean_object* a, lean_object* b) {
    uint64_t av = lite_nat_val(a), bv = lite_nat_val(b);
    return lite_nat_mk(av > bv ? av - bv : 0);
}

lean_object* lean_nat_big_mul(lean_object* a, lean_object* b) {
    uint64_t r;
    if (__builtin_mul_overflow(lite_nat_val(a), lite_nat_val(b), &r)) die("nat > 2^64");
    return lite_nat_mk(r);
}

bool lean_nat_big_eq(lean_object* a, lean_object* b) { return lite_nat_val(a) == lite_nat_val(b); }
bool lean_nat_big_le(lean_object* a, lean_object* b) { return lite_nat_val(a) <= lite_nat_val(b); }
bool lean_nat_big_lt(lean_object* a, lean_object* b) { return lite_nat_val(a) <  lite_nat_val(b); }

// -- closure apply: only referenced from proof-machinery, never called -

lean_object* lean_apply_1(lean_object* f, lean_object* a) { die("apply_1"); return 0; }

// -- init --------------------------------------------------------------

void lean_initialize_runtime_module(void) {
    l_ByteArray_empty = lean_alloc_sarray(1, 0, 0);
    lean_mark_persistent(l_ByteArray_empty);
}

lean_object* initialize_Init(uint8_t builtin) {
    (void)builtin;
    return lean_io_result_mk_ok(lean_box(0));
}

void lean_io_mark_end_initialization(void) {}

/-
RFC 9112 §7.1 chunked transfer coding, strict.

  chunked-body   = *chunk last-chunk trailer-section CRLF
  chunk          = chunk-size [ chunk-ext ] CRLF chunk-data CRLF
  chunk-size     = 1*HEXDIG
  last-chunk     = 1*("0") [ chunk-ext ] CRLF
  chunk-data     = 1*OCTET

Simplifications: chunk-ext and trailer field-lines are accepted as any run
of non-CR/non-LF bytes. Does not affect the CRLF-after-chunk-data property.
-/

namespace Rfc9112

def CR : UInt8 := 13
def LF : UInt8 := 10

def isHexDigit (b : UInt8) : Bool :=
  (48 ≤ b && b ≤ 57) || (65 ≤ b && b ≤ 70) || (97 ≤ b && b ≤ 102)

def hexVal (b : UInt8) : Nat :=
  if 48 ≤ b && b ≤ 57 then (b.toNat - 48)
  else if 65 ≤ b && b ≤ 70 then (b.toNat - 55)
  else (b.toNat - 87)

structure Cursor where
  buf : ByteArray
  pos : Nat

def Cursor.atEnd (c : Cursor) : Bool := c.pos ≥ c.buf.size

def Cursor.peek (c : Cursor) : Option UInt8 :=
  if h : c.pos < c.buf.size then some c.buf[c.pos] else none

def Cursor.advance (c : Cursor) (n : Nat) : Cursor := { c with pos := c.pos + n }

def Cursor.remaining (c : Cursor) : Nat := c.buf.size - c.pos

/-- Consume exactly CR LF. Bare LF, bare CR, or anything else is rejected. -/
def takeCRLF (c : Cursor) : Option Cursor :=
  match c.peek with
  | some b0 =>
    if b0 = CR then
      let c1 := c.advance 1
      match c1.peek with
      | some b1 => if b1 = LF then some (c1.advance 1) else none
      | none => none
    else none
  | none => none

/-- Read HEXDIG, at most 15 digits so the value stays below 2^60 and the
    intermediate `acc * 16` never needs arbitrary-precision arithmetic.
    A 16th hex digit is left at the cursor; `skipChunkExt` then rejects
    it, so a chunk-size with 16+ digits is invalid. The RFC grammar is
    unbounded but no implementation can hold a 2^60-byte chunk. -/
partial def takeHexDigits (c : Cursor) (acc : Nat) (n : Nat) : (Nat × Cursor × Nat) :=
  if n ≥ 15 then (acc, c, n)
  else match c.peek with
  | some b =>
    if isHexDigit b then takeHexDigits (c.advance 1) (acc * 16 + hexVal b) (n + 1)
    else (acc, c, n)
  | none => (acc, c, n)

def takeHex (c : Cursor) : Option (Nat × Cursor) :=
  let (v, c', n) := takeHexDigits c 0 0
  if n = 0 then none else some (v, c')

def COLON : UInt8 := 58

/-- Consume run of non-CR, non-LF bytes; report whether a `:` was seen.
    Used for trailer field-lines, which must be `field-name ":" ...`. -/
partial def skipToCR (c : Cursor) (sawColon : Bool) : Option (Cursor × Bool) :=
  match c.peek with
  | none => none
  | some b =>
    if b = CR then some (c, sawColon)
    else if b = LF then none
    else skipToCR (c.advance 1) (sawColon || b = COLON)

def SP : UInt8 := 32
def HTAB : UInt8 := 9
def SEMI : UInt8 := 59

/-- chunk-ext = *( BWS ";" BWS chunk-ext-name [ BWS "=" BWS chunk-ext-val ] ).
    Simplified: optional BWS then `;` then anything to CR, repeated. A bare
    space with no following `;` is rejected. -/
partial def skipChunkExt (c : Cursor) : Option Cursor :=
  match c.peek with
  | none => none
  | some b =>
    if b = CR then some c
    else if b = LF then none
    else if b = SEMI then afterSemi (c.advance 1)
    else if b = SP || b = HTAB then
      match skipBWS (c.advance 1) with
      | none => none
      | some c' =>
        match c'.peek with
        | some b' => if b' = SEMI then afterSemi (c'.advance 1) else none
        | none => none
    else none
where
  skipBWS (c : Cursor) : Option Cursor :=
    match c.peek with
    | some b => if b = SP || b = HTAB then skipBWS (c.advance 1) else some c
    | none => none
  afterSemi (c : Cursor) : Option Cursor :=
    -- rest of this extension segment: anything up to CR, LF, or `;`
    match c.peek with
    | none => none
    | some b =>
      if b = CR then some c
      else if b = LF then none
      else if b = SEMI then afterSemi (c.advance 1)
      else afterSemi (c.advance 1)

def takeData (c : Cursor) (n : Nat) : Option (ByteArray × Cursor) :=
  if c.pos + n ≤ c.buf.size then
    some (c.buf.extract c.pos (c.pos + n), c.advance n)
  else none

/-- One chunk. Returns (some data, c') for a data chunk, (none, c') after
    consuming last-chunk + trailer-section + final CRLF. -/
partial def parseChunk (c : Cursor) : Option (Option ByteArray × Cursor) :=
  match takeHex c with
  | none => none
  | some (size, c1) =>
    match skipChunkExt c1 with
    | none => none
    | some c2 =>
      match takeCRLF c2 with
      | none => none
      | some c3 =>
        if size = 0 then
          parseTrailers c3
        else
          match takeData c3 size with
          | none => none
          | some (data, c4) =>
            match takeCRLF c4 with
            | none => none
            | some c5 => some (some data, c5)
where
  parseTrailers (c : Cursor) : Option (Option ByteArray × Cursor) :=
    match c.peek with
    | none => none
    | some b =>
      if b = CR then
        match takeCRLF c with
        | none => none
        | some c' => some (none, c')
      else if b = LF then none
      else
        match skipToCR c false with
        | none => none
        | some (c1, sawColon) =>
          if !sawColon then none
          else match takeCRLF c1 with
          | none => none
          | some c2 => parseTrailers c2

partial def parseChunkedBody (buf : ByteArray) : Option ByteArray :=
  go ⟨buf, 0⟩ ByteArray.empty
where
  go (c : Cursor) (acc : ByteArray) : Option ByteArray :=
    match parseChunk c with
    | none => none
    | some (none, c') => if c'.atEnd then some acc else none
    | some (some d, c') => go c' (acc ++ d)

def valid (buf : ByteArray) : Bool := (parseChunkedBody buf).isSome

/-- Soundness of `takeCRLF`: if it succeeds, the two bytes at the cursor
    were exactly CR then LF, and the cursor advanced by 2. This is P3's
    core lemma: no other byte pair is accepted after chunk-data. -/
theorem takeCRLF_sound {c c' : Cursor} (h : takeCRLF c = some c') :
    c.peek = some CR ∧ (c.advance 1).peek = some LF ∧ c' = c.advance 2 := by
  unfold takeCRLF at h
  split at h
  · rename_i b0 hp0
    split at h
    · rename_i hcr
      dsimp only at h
      split at h
      · rename_i b1 hp1
        split at h
        · rename_i hlf
          refine ⟨hp0 ▸ hcr ▸ rfl, hp1 ▸ hlf ▸ rfl, ?_⟩
          injection h with h
          subst h
          rfl
        · simp at h
      · simp at h
    · simp at h
  · simp at h

/-- P3, stated over the position immediately after chunk-data: if
    `takeCRLF` succeeds there, the bytes were CR LF. `parseChunk` on a
    non-zero chunk requires exactly this, so no data chunk is accepted
    with any other terminator. -/
theorem p3_data_terminator {c c' : Cursor} (h : takeCRLF c = some c') :
    c.peek = some CR ∧ (c.advance 1).peek = some LF :=
  ⟨(takeCRLF_sound h).1, (takeCRLF_sound h).2.1⟩

end Rfc9112

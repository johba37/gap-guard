# Cross-lane artifact format — `student_export.json`, `golden_vectors.json`, `calendar_table.json`

Normative source: `DESIGN.md` §3.2.13–14, §3.3.23–24, §5.8. **This document is the
boundary between the ML lane (A) and the contracts lane (B).** Changes require
agreement of all three lanes.

Lane A produces these artifacts; Lane B's tooling generates Rust/Solidity constants
from them; CI pins them to the chain. If it is not in this document, it does not
cross the boundary.

---

## 1. `student_export.json`

Canonical, hash-pinned description of the quantized student. The example below is
annotated (comments are documentation only — the artifact itself is strict JSON,
see §1.3).

### 1.1 Annotated example

```json
{
  "featureSpecVersion": 1,
  "weightsHash": "0x<keccak256 of this file in canonical form, see §1.3>",
  "architecture": {
    "inputDim": 9,
    "layers": [
      { "in": 9, "out": 24, "activation": "relu" },
      { "in": 24, "out": 24, "activation": "relu" },
      { "in": 24, "out": 1, "activation": "sigmoid" }
    ],
    "parameterCount": 0
  },
  "quantization": {
    "scheme": "per-channel-symmetric-int8-weights / per-tensor-symmetric-int8-activations",
    "weights": { "dtype": "int8", "zeroPoint": 0, "granularity": "per-channel", "axis": 0 },
    "activations": { "dtype": "int8", "zeroPoint": 0, "granularity": "per-tensor" },
    "biases": { "dtype": "int32" },
    "accumulator": { "dtype": "int32" },
    "requantize": { "multiplierRange": "[0.5, 1)", "shift": "uint8 right-shift" },
    "scaleEncoding": "Q16 fixed-point uint32",
    "sigmoidLutQ16": [ 0, 0 ],
    "rounding": "round-half-away-from-zero"
  },
  "layers": [
    {
      "weightsHex": "0x…",
      "weightScalesQ16": [ 0, 0 ],
      "biasInt32": [ 0 ],
      "inputScaleQ16": 0,
      "outputScaleQ16": 0,
      "requantMultiplierQ16": 0,
      "requantShift": 0
    }
  ],
  "featureNormalization": {
    "secsSinceClose":     { "min": 0, "max": 604800 },
    "secsToOpen":         { "min": 0, "max": 604800 },
    "realizedVolBps":     { "min": 0, "max": 65535 },
    "oracleDeviationBps": { "min": 0, "max": 65535 },
    "stalenessSecs":      { "min": 0, "max": 65535 },
    "assetClass":         { "min": 0, "max": 3 },
    "ltvBps":             { "min": 0, "max": 10000 },
    "concentrationBps":   { "min": 0, "max": 10000 },
    "flags":              { "min": 0, "max": 1 }
  },
  "temperature": 1.0
}
```

### 1.2 Field semantics

- **`featureSpecVersion`** (uint): version of the `Features` encoding, matching
  [`IGapRiskModel`](./IGapRiskModel.md) §5.1. Bumped on any struct/field change;
  contracts reject exports with an unknown version.
- **`architecture`**: layer sizes (`in`/`out` per layer, input→output order),
  per-layer activation (`relu` hidden, `sigmoid` output head), `parameterCount`
  (must be in the 3–5K budget, DESIGN.md §3.2). Exact widths are chosen by Lane A
  during distillation (DESIGN.md §8) — the export is where they become normative.
- **`quantization`** (DESIGN.md §3.2.14, TFLite/Jacob et al. 2018 pattern):
  - **Weights:** per-channel symmetric int8, zero-point 0 (one scale per output
    channel).
  - **Activations:** per-tensor symmetric int8, zero-point 0.
  - **Biases:** int32. **Accumulators:** int32. Overflow is ruled out
    arithmetically at our fan-ins: fan_in × 16,129 ≪ 2³¹ even at fan_in = 1024
    (DESIGN.md §2.3).
  - **Scales:** all scales are **Q16 fixed-point** constants (uint32), embedded in
    the model contract.
- **Per-layer op order (binding):**
  1. `acc[i] = Σ_j W[i,j]·x[j]` in int32, `j` ascending;
  2. `acc[i] += biasInt32[i]`;
  3. if `relu`: `acc[i] = max(acc[i], 0)`;
  4. requantize.
- **Requantization (binding, int64 intermediate):** `S = 16 + requantShift`;
  `p = acc * requantMultiplierQ16` (int64);
  `y = (p + copysign(1<<(S−1), p)) >> S` (arithmetic shift), saturated to
  [−128, 127] — **round-half-away-from-zero**.
- **Sigmoid head (binding):** the logit is scaled by `temperatureQ16` (same
  round-half-away-from-zero rounding), requantized to an int8 logit with
  `outputScaleQ16`; `p_Q16 = sigmoidLutQ16[logit + 128]`;
  `riskBps = (p_Q16 * 10000 + 65535) >> 16` (round-up).
- **`sigmoidLutQ16`:** exactly 256 uint16 entries,
  `entry[i] = round(sigmoid((i−128)·outputScale)·65536)`. Generated float-side by
  Lane A, embedded verbatim by Lane B, part of the canonical hash (§1.3).
- **`layers[].weightsHex`**: int8 weights as hex arrays (two's-complement bytes,
  row-major, output-channel-major so per-channel scales align).
- **`layers[].weightScalesQ16` / `inputScaleQ16` / `outputScaleQ16` /
  `requantMultiplierQ16` / `requantShift` / `biasInt32`**: the constants the Rust
  forward pass is generated from.
- **`featureNormalization`**: fixed published min/max **per `Features` field, in
  raw units** (seconds, bps, enum index — never int8-domain values). The contract
  normalizes raw → int8 internally with these ranges; callers never see the scheme.
  The formula is pinned:
  `x_int8 = clamp(−128, 127, ((x−min)*254 + range//2) // range − 127)`
  (integer floor division, non-negative operands; `range = max − min`).
  **Lane A must clamp every training feature to its published range BEFORE
  normalization, `stalenessSecs` included**, so teacher and student see identical
  saturated inputs (train/serve skew rule). Ranges match the field table in
  [`IGapRiskModel`](./IGapRiskModel.md), including the 604800 s caps.
- **`temperature`**: the calibration temperature constant fitted post-distillation
  (D3, DESIGN.md day plan); applied to the logit before the sigmoid head. Written
  as a decimal in the export, embedded as a Q16 constant in the contract.
- **`weightsHash`**: `keccak256` of the canonical serialization (§1.3). Equal to
  `IGapRiskModel.weightsHash()` on-chain and to the value pinned by
  [`IModelRegistry.propose`](./IModelRegistry.md).

### 1.3 Canonical serialization (defines the hash — precisely)

`weightsHash = keccak256(C)` where `C` is the byte string produced by:

1. Start from the parsed JSON value.
2. Serialize with **object keys sorted lexicographically at every depth**
   (recursive), **no whitespace** (no spaces, no newlines, separators `,` and `:`),
   UTF-8 encoding.
3. Numbers serialize in shortest round-trip form (no trailing zeros, no `+`, no
   exponent unless required); strings are minimal UTF-8 with JSON escaping.
4. The `weightsHash` field itself is serialized with value `"0x"` (empty
   placeholder) when computing the hash — the hash is over the artifact with its
   own digest blanked.
5. Hash the resulting UTF-8 bytes with keccak256 (Ethereum keccak, not SHA3-256).

Reference implementation: `json.dumps(obj, sort_keys=True, separators=(",", ":"),
ensure_ascii=False)` in Python, then `.encode("utf-8")`.

---

## 2. `golden_vectors.json`

Two vector sets, both produced by the **quantized Python reference** (not the float
model — the vectors define what the *contract* must output, quantization included).

```json
{
  "featureSpecVersion": 1,
  "modelVectors": [
    {
      "features": {
        "secsSinceClose": 193200,
        "secsToOpen": 54000,
        "realizedVolBps": 850,
        "oracleDeviationBps": 120,
        "stalenessSecs": 36000,
        "assetClass": 0,
        "ltvBps": 4500,
        "concentrationBps": 6000,
        "flags": 0
      },
      "expectedRiskBps": 1234
    }
  ],
  "calendarVectors": [
    {
      "timestamp": 1767225600,
      "expected": { "secsSinceClose": 0, "secsToOpen": 0, "holidayAdjacent": false }
    }
  ]
}
```

- **`modelVectors`: exactly 100 rows** — raw `Features` → `expectedRiskBps` from the
  quantized reference. Rows are chosen to cover the feature ranges and the step
  table's decision boundaries. **Must include ≥2 rows with
  `stalenessSecs = 65535` at distinct weekend timestamps**, to lock the saturation
  clamp in CI.
- **`calendarVectors`: 50 rows** — unix timestamp →
  `(secsSinceClose, secsToOpen, holidayAdjacent)` per
  [`INyseCalendar`](./INyseCalendar.md). (CI additionally sweeps 1000 random
  timestamps against `exchange_calendars` directly.)

---

## 3. `calendar_table.json`

Generated by Lane A tooling from `exchange_calendars==4.13.2` (XNYS), covering
**2024–2028** sessions including early closes. Lane B generates Solidity constants
from it.

```json
{
  "source": "exchange_calendars==4.13.2",
  "calendar": "XNYS",
  "rangeStart": 1704067200,
  "rangeEnd": 1893456000,
  "sessions": [
    { "open": 1704119400, "close": 1704157200, "earlyClose": false }
  ]
}
```

`open`/`close` are unix timestamps of the regular session; `earlyClose: true` marks
shortened sessions (these drive `holidayAdjacent` for the following closure).

---

## 4. CI rules (binding)

1. **Student match:** the on-chain (or local-Stylus) student must reproduce all
   **100 model vectors exactly** — `score(features) == expectedRiskBps`, no
   tolerance. The vectors come from the quantized reference, so exactness is
   achievable; any mismatch is a bug in the port, not noise.
2. **Hash pin:** on-chain `weightsHash()` must equal the `weightsHash` field of the
   canonical `student_export.json` (§1.3), which must equal the `weightsHash`
   pinned in [`IModelRegistry`](./IModelRegistry.md) on activation.
3. **Calendar match:** all 50 calendar vectors must match; the 1000-timestamp sweep
   against `exchange_calendars` must pass.
4. **Version gate:** contracts reject exports with an unknown `featureSpecVersion`.

These run in Lane B's golden-vector CI **from the arrival of Lane A's export
artifacts** (planned Wed 9/30). Until then Lane B CI runs the committed synthetic
vectors (`contracts/test/synthetic_export.json` + `synthetic_vectors.json`), which
are also the Stylus go/no-go signal (DESIGN.md §3.3.22) and depend on nothing from
Lane A.

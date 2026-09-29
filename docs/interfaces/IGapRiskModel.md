# IGapRiskModel — Stylus student contract

Normative source: `DESIGN.md` §5.1–5.2. Changes require agreement of all three lanes.

## Purpose

`IGapRiskModel` is the on-chain student model: a small int8 MLP (3–5K parameters,
distilled from an off-chain teacher) implemented in Rust/Stylus. It maps a raw,
human-meaningful feature vector to a single gap-risk score. It is a **pure function**:
view-only, no storage writes, no external calls, no operator inputs. Everything it
knows is baked in at deploy time (weights, scales, feature-normalization ranges) and
pinned by `weightsHash()`.

## Interface

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

struct Features {
    uint32 secsSinceClose;     // s since last NYSE regular-session close (cap 604800)
    uint32 secsToOpen;         // s until next NYSE regular-session open (cap 604800)
    uint16 realizedVolBps;     // on-chain vol estimate, bps (0..65535)
    uint16 oracleDeviationBps; // |latest feed reading − previous accepted reading| / previous, bps
    uint16 stalenessSecs;      // s since ref feed update (cap 65535) — saturates ~18.2h by design; weekend signal lives in secsSinceClose/secsToOpen
    uint8  assetClass;         // 0=large-cap tech, 1=large-cap other, 2=high-beta, 3=other
    uint16 ltvBps;             // current position LTV, bps
    uint16 concentrationBps;   // share of this token in account collateral, bps
    uint8  flags;              // bit0: session before close is a shortened/holiday-adjacent session
}

interface IGapRiskModel {
    function score(Features calldata f) external view returns (uint16 riskBps);
    function weightsHash() external view returns (bytes32); // keccak of canonical student_export.json
}
```

## The `Features` struct (§5.1)

Callers pass **raw, human-meaningful values**. Normalization to the model's int8
input domain and all quantization arithmetic happen **inside the contract**, using
the fixed published ranges from [`student-export-format.md`](./student-export-format.md).
Callers never learn the int8 scheme.

| Field | Type | Units | Range | Meaning / producer |
|---|---|---|---|---|
| `secsSinceClose` | uint32 | seconds | 0..604800 (cap) | Seconds since the last NYSE regular-session close. From [`INyseCalendar`](./INyseCalendar.md). Values beyond 7 days saturate at 604800. |
| `secsToOpen` | uint32 | seconds | 0..604800 (cap) | Seconds until the next NYSE regular-session open. Same source, same cap. |
| `realizedVolBps` | uint16 | bps | 0..65535 | On-chain realized-volatility estimate for the token, from [`IVolatilityOracle`](./IVolatilityOracle.md) (EMA of \|relative returns\|, integer bps). |
| `oracleDeviationBps` | uint16 | bps | 0..65535 | Feed-jump deviation: \|latest feed reading − previous accepted reading\| / previous, in bps. |
| `stalenessSecs` | uint16 | seconds | 0..65535 (cap) | Seconds since the reference Chainlink-compatible feed last updated. Saturates at 65535 (~18.2h) **by design**; weekend differentiation is carried by `secsSinceClose`/`secsToOpen` — this field's independent signal is intra-week feed misbehavior. Do not widen. Feeds are 24/5, so weekend staleness is a *feature input*, not an error. |
| `assetClass` | uint8 | enum | 0..3 | 0 = large-cap tech, 1 = large-cap other, 2 = high-beta, 3 = other. |
| `ltvBps` | uint16 | bps | 0..10000 | Current position LTV of the querying account. |
| `concentrationBps` | uint16 | bps | 0..10000 | Share of this token in the account's collateral, bps. |
| `flags` | uint8 | bitmask | bit0 used | bit0: the session preceding the last close was a shortened / holiday-adjacent session. From the on-chain calendar. Bits 1–7 reserved, must be 0. |

All fields are range-checked; any out-of-range value is a fail-closed condition at
the policy (see [`IRiskPolicy`](./IRiskPolicy.md)).

## Score semantics

```
riskBps = ceil( P(|open_t / close_{t−1} − 1| > 5%) × 10000 )
```

- The label is the probability that the **next close→open transition** gaps by more
  than 5% in either direction.
- The score is a uint16 in 0..10000 (bps). **Scores round up** (toward higher risk);
  this is the conservative direction and is fixed by DESIGN.md §3.3.24.
- The score is computed **fresh per transaction** — no caching; the model has no
  `poke` (only the vol oracle accumulates state, via `poke(token)`).
  Fresh-per-tx is the synchronously-composable product claim.

## Position features

`ltvBps` / `concentrationBps` are in the struct for **interface
forward-compatibility** and pass-through to
[`IRiskPolicy.maxLtvBps`](./IRiskPolicy.md); the label is **position-independent**.
Training samples them uniformly (`ltvBps ~ U(0,7000)`,
`concentrationBps ~ U(0,10000)`) and the adversarial fidelity grid sweeps their
full range, so the score is **certified position-independent** rather than assumed
so (DESIGN.md §3.2.7).

## `weightsHash()` semantics

Returns `keccak256` of the canonical `student_export.json` byte string (canonical
serialization defined precisely in
[`student-export-format.md`](./student-export-format.md): UTF-8 JSON, sorted keys,
no whitespace). This is the link between the deployed model and the off-chain
artifact: CI asserts `weightsHash() == keccak256(canonical student_export.json)`,
and the value is what [`IModelRegistry`](./IModelRegistry.md) pins on activation.

## Gas

- Test ceiling (Stylus backend): **200,000 gas per `score()` call** (asserted in
  the test suite).
- The Solidity-fallback backend uses `SCORE_GAS_CEILING_FALLBACK = 3,000,000`
  (constants-in-code port, expected ~0.3–1M — see DESIGN.md §3.3.22).
- Expected: order 10⁵ gas (the MLP is ~5–10× less work than one stylus-nanoGPT
  token step at 4.1M gas), plus ~9k uncached call-init. Trivially inside any
  realistic tx cap. Measured values land in the README gas table (D3).

## Purity guarantees

- `view` only; **no storage writes**, no external calls, no `block.timestamp`
  dependence (time enters only via the `Features` struct, computed by the calendar).
- Deterministic integer math only — no floats (WASM floats are rejected at
  activation on Arbitrum chains).
- The purity is load-bearing: it is what makes fidelity testing, reproducible
  builds (`cargo stylus verify`), and the reserved M3/M6 attestation/ZK slots
  possible.

## For integrators

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IGapRiskModel, Features} from "./IGapRiskModel.sol";

contract ConsumerExample {
    IGapRiskModel public immutable model;

    constructor(address model_) {
        model = IGapRiskModel(model_);
    }

    function currentRisk(Features calldata f) external view returns (uint16 riskBps) {
        // Synchronous, same-transaction read. f is built from the calendar,
        // the vol oracle, the reference feed, and the caller's position.
        riskBps = model.score(f);
    }
}
```

Most consumers should not call the model directly — read the gated parameter from
[`IRiskPolicy.maxLtvBps`](./IRiskPolicy.md), which applies hard caps and
fail-closed rules around the score.

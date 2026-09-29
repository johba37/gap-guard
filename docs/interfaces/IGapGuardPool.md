# IGapGuardPool — mock Morpho-style isolated vault

Normative source: `DESIGN.md` §1, §3.1.1, §5.7. Changes require agreement of all
three lanes.

## Purpose — read this first

**This is a mock. The feed is the product.** The pool exists to demonstrate a
consumer of the GapGuard parameter feed in the shape of the named first integrator
archetype: a Morpho-style isolated lending vault (per-token LLTV, no cross-margin).
It is deliberately minimal — full control, zero integration risk. Nothing about it
is production lending code.

## Interface

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IGapGuardPool {
    function depositCollateral(uint256 amount) external;
    function borrow(uint256 amount) external;
    function repay(uint256 amount) external;
    function withdrawCollateral(uint256 amount) external;
}
```

## Mechanics

- **Single isolated market:** one stock token as collateral vs one borrow asset
  (WETH or USDC) at a time. Per-token LLTV, no cross-margin, no portfolio netting
  (explicit MVP non-goal).
- **LLTV source:** the pool reads [`IRiskPolicy.maxLtvBps`](./IRiskPolicy.md)
  **at borrow time and at withdraw time** — synchronously, in the same transaction.
  The policy's answer already includes the student score, the step table, hard caps,
  and all fail-closed rules. The pool holds no risk logic of its own.
- **Liquidation bonus:** fixed **5%**.
- **Pricing:** no oracle pricing of its own beyond the reference
  Chainlink-compatible feed — keeps the mock honest about what it is.
- **Gating events:** the pool emits `LimitChecked` on every gated borrow/withdraw
  and `CapHit` when a requested action exceeds the applicable cap. These live here,
  not on the policy, because `IRiskPolicy.maxLtvBps` is `view` and cannot emit —
  the pool holds the action context (see [`events.md`](./events.md)).
- **Gas:** test ceiling **500,000 gas** for a gated `borrow` /
  `withdrawCollateral` (policy call + two ERC-20 transfers + accounting + events)
  — the ≤1.5%-of-32M-block-cap budget attached to the real user transaction
  (DESIGN.md §3.3.16).

## Demo behavior (Tuesday/Saturday contrast)

The demo script runs the same borrow twice against a demoMode policy deployment
(see [`IRiskPolicy`](./IRiskPolicy.md) demo mode):

- **Tuesday** (`demoNow` mid-session week): gap-risk score is low → step-table
  factor near 100% → the borrow succeeds at a high LLTV.
- **Saturday** (staged): mock feed `pushRound(fridayClosePrice)` →
  `volOracle.poke(TSLA)` → `setDemoNow(Saturday)` → identical borrow. `demoNow`
  deep into the weekend closure makes `secsSinceClose` large, and `stalenessSecs`
  now rises via the policy's demo-time semantics (see
  [`IRiskPolicy`](./IRiskPolicy.md) demo mode) — "feed staleness rising" is real,
  not scripted. Score high → factor steps down → the identical borrow is
  **blocked or attenuated**, and the UI shows the pool-emitted `LimitChecked` /
  `CapHit` events (see [`events.md`](./events.md)).

The contrast — identical action allowed Tuesday, blocked Saturday — is MVP success
criterion 5 (goal.md §5).

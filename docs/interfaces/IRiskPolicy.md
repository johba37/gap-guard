# IRiskPolicy — policy / orchestrator contract

Normative source: `DESIGN.md` §3.2.12, §3.3.24, §3.4.25, §3.4.27, §3.5.30, §5.5.
Changes require agreement of all three lanes.

## Purpose

`IRiskPolicy` turns the student model's gap-risk score into a **dynamic max-LTV
parameter** and gates consumers (the mock pool, agent session-key guards). It owns
all safety machinery: hard caps, the monotonic step table, fail-closed conditions,
the pause/unpause asymmetry, and the demo-mode time override. The model itself stays
a pure function; every value judgment lives here.

## Interface

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IRiskPolicy {
    function maxLtvBps(address token, uint16 ltvBps, uint16 concentrationBps)
        external view returns (uint16 maxLtv, uint16 riskBps);
    function pause() external;              // guardian, instant
    function scheduleUnpause() external;    // guardian, executable after 48h
    function setDemoNow(uint40 t) external; // demoMode deployments only
}
```

## Risk curve: 5-breakpoint monotonic step table

The mapping `riskBps → factor` is a **5-breakpoint monotonically non-increasing step
table** of constants. The *shape* (5 monotonic steps) is fixed; the *breakpoint
values* freeze Wed 9/30 morning after the threat-model session (DESIGN.md §8).

Example only (placeholder, **not** the frozen table):

| riskBps ≥ | factor (% of base max LTV) |
|---|---|
| 0 | 100% |
| 500 | 85% |
| 1500 | 65% |
| 3000 | 45% |
| 5000 | 25% |

Chosen over a linear clamp because it is auditable at a glance, tunable without
touching the model, and un-gameable-by-epsilon: a step function has no gradient to
surf, so an attacker cannot buy a better limit by nudging the score.

`maxLtv = baseMaxLtv(token) × factor(riskBps)`, then clamped by the hard caps below.

## Constants

```solidity
uint16 constant MAX_LTV_HARD_CAP_BPS   = 7000; // 70% — binds regardless of score
uint16 constant COLD_START_MAX_LTV_BPS = 3500; // 35% — tokens without a registered model/vol history
uint16 constant MIN_LTV_FLOOR_BPS      = 0;    // fail-closed floor
```

- `MAX_LTV_HARD_CAP_BPS` caps every output no matter how benign the score. This is
  the un-gameable backstop that bounds the damage of a fooled model.
- `COLD_START_MAX_LTV_BPS` applies to any token without a registered model / vol
  history. Documented as governance-tunable post-MVP.
- Floor is 0: fail-closed paths return `maxLtv = 0`.

## Token registry (constructor-set)

The constructor takes `TokenConfig[]`:

```solidity
struct TokenConfig {
    address token;
    uint16 baseMaxLtvBps;
    uint8 assetClass;
    address referenceFeed;
}
```

Stored immutably. A token is **registered iff it appears in this list**.
Unregistered tokens skip scoring and get `COLD_START_MAX_LTV_BPS` directly — no
model call, no vol read. `baseMaxLtvBps ≤ MAX_LTV_HARD_CAP_BPS` is enforced in the
constructor. **No function exists to add tokens post-deploy; adding a token =
redeploy** (same story as the calendar table).

## Fail-closed conditions

`maxLtvBps` returns `maxLtv = 0` when **any** of the following holds:

1. Any `Features` field is out of range (see
   [`IGapRiskModel`](./IGapRiskModel.md) field table).
2. The volatility oracle is stale: [`IVolatilityOracle.isStale(token)`](./IVolatilityOracle.md)
   is true (>26h since that token's last update).
3. The reference Chainlink-compatible feed is paused (`oraclePaused()`, used during
   corporate actions).
4. The policy itself is paused.

Fail-closed means uncertainty tightens limits to zero; it never loosens them.

## Pause / unpause

- `pause()` — guardian only, **instant**. Sets all limits to 0. Emits `Paused`.
- `scheduleUnpause()` — guardian only; queues an unpause executable **after a 48h
  timelock**. Emits `UnpauseScheduled`, then `Unpaused` on execution.

The asymmetry is deliberate: fast to stop, slow to restart (DESIGN.md §3.4.27).
MVP guardian is the deployer EOA (documented, not hidden); M5 moves it to a
2-of-3 Safe.

## Demo mode

- `demoMode` is an **immutable constructor flag**.
- Demo deployments (separate address) set it true, enabling `setDemoNow(uint40 t)`
  (emits `DemoTimeSet`) so the Tuesday/Saturday contrast can be shown on a live
  testnet.
- Production deployments have `demoMode = false` and **no override path exists in
  the bytecode** — there is no admin function, proxy, or storage slot that can
  re-enable it.

### Demo time semantics

`demoNow` affects **exactly two reads** in `maxLtvBps`:

1. The `now` passed to `NyseCalendar.windows()` — calendar features
   (`secsSinceClose`, `secsToOpen`) plus `flags` bit0.
2. `stalenessSecs = min(demoNow > feed.updatedAt ? demoNow − feed.updatedAt : 0, 65535)`
   — saturating subtraction; `demoNow` may move backward.

Unchanged on real `block.timestamp`: `IVolatilityOracle.isStale` (fail-closed #2)
and `oraclePaused` (fail-closed #3). Rationale: `demoNow` fakes calendar position
and feed freeze, never the liveness of our own infrastructure.

## Rounding

- Scores round **up** (toward higher risk) — see [`IGapRiskModel`](./IGapRiskModel.md).
- LTV limits round **down** (toward tighter limits).
- Both directions are the conservative one. Fixed by DESIGN.md §3.3.24; no 18-decimal
  values anywhere — bps (uint16, 0..10000) across every boundary.

## Gas

Test ceiling: **250,000 gas per `maxLtvBps` call** (asserted in the test suite) —
the `score()` ceiling plus ≤~30k of vol SLOADs, calendar math, step table, and
range checks.

## Events

The policy emits `Paused`, `UnpauseScheduled`, `Unpaused`, and `DemoTimeSet` (demo
deployments only). `maxLtvBps` is `view` and cannot emit, so `LimitChecked` and
`CapHit` are emitted by the pool — full catalog in [`events.md`](./events.md).

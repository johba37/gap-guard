# Event catalog

Normative source: `DESIGN.md` §5.9. Events are the interface for the demo UI and
future watchtowers; changes require agreement of all three lanes.

Consumers: **demo UI** (live readout of the Tuesday/Saturday contrast),
**watchtower** (post-MVP monitoring/alerting, roadmap M1), **judges** (explorer-verifiable
evidence that the mechanism fired).

## Pool — [`IGapGuardPool`](./IGapGuardPool.md)

The pool emits the gating events, not the policy: `IRiskPolicy.maxLtvBps` is `view`
and cannot emit, and the pool holds the action context (DESIGN.md §5.9).

| Event | Fields | Emitted when | Consumer |
|---|---|---|---|
| `LimitChecked` | `token` (address), `ltvBps` (uint16), `maxLtv` (uint16), `riskBps` (uint16) | On **every** gated borrow/withdraw — the pool logs the score and the limit the policy returned. Primary demo-UI event. | demo UI, watchtower, judges |
| `CapHit` | `token` (address), `requestedLtv` (uint16), `cap` (uint16) | A requested action exceeded the applicable cap (step-table limit or hard cap). Evidence that caps bind. | demo UI, watchtower, judges |

## Policy — [`IRiskPolicy`](./IRiskPolicy.md)

| Event | Fields | Emitted when | Consumer |
|---|---|---|---|
| `Paused` | — | Guardian `pause()` executed; all limits are 0, instant. | watchtower, judges |
| `UnpauseScheduled` | — | Guardian queued an unpause; executable after the 48h timelock. | watchtower |
| `Unpaused` | — | Timelocked unpause executed; service resumed. | watchtower, judges |
| `DemoTimeSet` | `t` (uint40) | `setDemoNow(t)` shifted the demo clock. **Demo deployments only** — never emitted by production bytecode. | demo UI, judges |

## Volatility oracle — [`IVolatilityOracle`](./IVolatilityOracle.md)

| Event | Fields | Emitted when | Consumer |
|---|---|---|---|
| `VolUpdated` | `token` (address), `volBps` (uint16), `updatedAt` (uint40) | A `poke(token)` observation was accepted and the EMA updated. Rejected observations (jump clamp) emit nothing; an early poke reverts `PokeTooSoon()`. | demo UI, watchtower |

## Model registry — [`IModelRegistry`](./IModelRegistry.md)

| Event | Fields | Emitted when | Consumer |
|---|---|---|---|
| `ModelProposed` | `model` (address), `weightsHash` (bytes32), `activateAfter` (uint64) | Owner proposed a new student; 24h timelock started. The public review window opens here. | watchtower, judges |
| `ModelActivated` | `model` (address), `weightsHash` (bytes32) | Timelock elapsed and `activate()` executed; the policy now reads this model. | watchtower, judges |

## Notes for consumers

- All bps fields are uint16, 0–10000, per the fixed-point convention
  (DESIGN.md §3.3.24).
- `LimitChecked` fires on every gate including fail-closed outcomes (`maxLtv = 0`);
  the reason is recoverable from contract state (`paused`, `isStale(token)`, etc.).
- The registry events are the audit trail for the public-weights claim: every model
  ever activated is a `(model, weightsHash)` pair in the logs, each reproducible via
  `cargo stylus verify` (see README reproducibility section).

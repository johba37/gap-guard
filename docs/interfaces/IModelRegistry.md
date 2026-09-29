# IModelRegistry — model pointer with timelocked updates

Normative source: `DESIGN.md` §3.3.21, §3.4.28, §5.6. Changes require agreement of
all three lanes.

## Purpose

`IModelRegistry` holds the pointer to the active [`IGapRiskModel`](./IGapRiskModel.md)
and its `weightsHash`. It is the only upgrade path: new weights mean a **new model
contract** plus a timelocked registry update. [`IRiskPolicy`](./IRiskPolicy.md)
reads the model from the registry, so consumers need no redeploy when the model
changes.

## Interface

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IModelRegistry {
    function currentModel() external view returns (address model, bytes32 weightsHash, uint64 activatedAt);
    function propose(address model, bytes32 weightsHash) external; // owner; starts 24h timelock
    function activate() external;                                  // anyone, after timelock
    event ModelProposed(address model, bytes32 weightsHash, uint64 activateAfter);
    event ModelActivated(address model, bytes32 weightsHash);
}
```

## Update flow

0. **Genesis model:** the constructor takes the initial `(model, weightsHash)` and
   sets `activatedAt = deploy time` — the initial deployment cannot wait out the
   24h timelock. Rationale: the timelock exists to give the public a review window
   on *changes* to a live system; at genesis there is no live state to protect,
   and the genesis pair is visible in the deploy transaction itself. The
   timelocked propose/activate path below governs **all subsequent updates**.
1. **Deploy** the new student contract (reproducible build; verify with
   `cargo stylus verify --deployment-tx <hash>`).
2. **`propose(model, weightsHash)`** — owner only. Starts a **24h timelock** and
   emits `ModelProposed(model, weightsHash, activateAfter)`. The proposed
   `weightsHash` must match the deployed contract's `weightsHash()`; CI checks this.
3. **`activate()`** — callable by anyone once `activateAfter` has passed. Emits
   `ModelActivated`. Anyone-can-activate is safe because the proposal (and its
   24h public window) is the governed step.

## Redeploy-not-proxy rationale

No proxies, no mutable bytecode. A proxy would let the same address serve different
weights, which silently breaks the public-weights honesty claim: an auditor pinning
a `weightsHash` to an address could be re-pointed underfoot. Redeploy + registry
pointer makes every model an immutable artifact and every update a public event
with a 24h review window. M5 moves the owner key to a 2-of-3 Safe multisig.

## Reserved post-MVP extension slots (named, unimplemented)

Two extensions are **named here but deliberately not implemented** at MVP, so
consumers know the interface will not break when they land:

- **M3 — attestation bond slot:** a bonded-attestation layer where an off-chain
  teacher-grade model posts scores with a bond and the on-chain student acts as
  watchdog (disagreement > τ → flag/pause). Reserved as a future field/companion
  contract alongside the registry.
- **M6 — ZK-proof slot:** a proof-agnostic update path where a model update is
  backed by a validity proof instead of (or in addition to) a proposal.

Neither exists in MVP code. Documenting them here is the commitment that
`currentModel / propose / activate` and the events above remain stable across the
roadmap.

## Incident runbook (miscalibration discovered in production)

1. **Guardian calls `RiskPolicy.pause()`** — instant; all limits go to 0.
2. **Fix off-chain:** recalibrate/retrain, regenerate `student_export.json` and
   golden vectors, redeploy the student contract.
3. **`propose(newModel, newWeightsHash)`** — 24h timelock, public via
   `ModelProposed`.
4. **`activate()`** — policy now reads the new model; no consumer redeploy needed.
5. **`scheduleUnpause()`** — 48h timelock; service resumes.

Two deliberate delays in series: 24h on the model swap, 48h on the unpause. Fast to
stop, slow to restart.

## Events

`ModelProposed`, `ModelActivated` — full catalog in [`events.md`](./events.md).

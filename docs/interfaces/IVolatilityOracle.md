# IVolatilityOracle — on-chain realized-volatility oracle

Normative source: `DESIGN.md` §3.2.10, §3.4.25, §5.3. Changes require agreement of
all three lanes.

## Purpose

`IVolatilityOracle` maintains a manipulation-resistant realized-volatility estimate
per token, in integer bps, for use as the `realizedVolBps` model feature. It is the
only stateful component in the scoring path (volatility accumulates by nature); the
student model stays a pure function. **One oracle instance per deployment serves all
registered tokens, with per-token state.**

## Interface

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IVolatilityOracle {
    function realizedVolBps(address token) external view returns (uint16 volBps, uint40 updatedAt);
    function poke(address token) external;                 // permissionless; reverts PokeTooSoon() if <1h since last
    function isStale(address token) external view returns (bool); // true if >26h since updatedAt
}
```

## Mechanics

- **Ring buffer:** 32 × (price, timestamp) observations **per token**.
- **Registered tokens:** the constructor-configured (token → referenceFeed) map.
  `poke()` on an unknown token reverts `UnknownToken()`.
- **`poke(token)`:** permissionless; appends the **reference feed's current answer**
  for `token` (mock Chainlink feed on testnet, real Chainlink feed on mainnet).
  **Reverts `PokeTooSoon()`** if less than **1 hour** has passed since that token's
  last accepted observation (decision: revert, not skip — deterministic and
  trivially testable). The interval is a minimum, not a liveness requirement.
  Freshness within the 26h window is an **availability assumption**: permissionless
  poke means anyone can provide it; the team runs a convenience keeper at MVP; a
  keeper failure fails closed at the policy, never opens.
- **Jump bound:** an observation is **rejected** if
  |new − last accepted| / last accepted > **10%**. Manipulation is bounded by the
  clamp: an attacker cannot move the series faster than 10% per accepted poke, and
  each accepted poke must come from the reference feed itself.
- **Trust assumption:** the reference feed is trusted (deployer-controlled mock on
  testnet; Chainlink on mainnet). Feed integrity is out of scope for on-chain
  defense and is documented in the README's threat model.
- **Estimator:** EMA of \|relative returns\| (log-free), integer math only, output
  in bps (uint16). No floats anywhere in the path.
- **`isStale(token)`:** true when more than **26h** have passed since that token's
  `updatedAt`. The policy consumes this as a fail-closed condition (see
  [`IRiskPolicy`](./IRiskPolicy.md)); the oracle itself never refuses reads.

## Failure handling

The oracle does not fail-closed on its own; fail-closed is the policy's job via
`isStale(token)`. Staleness and deviation also reach the model as *features*
(`stalenessSecs`, `oracleDeviationBps`), so a gaming attempt moves the score toward
caution, not away (DESIGN.md §3.4.25b).

## Replaceability

The estimator is deliberately **replaceable behind this interface**. Post-MVP
candidates: TWAP-window estimators, Parkinson (high-low) volatility. M2 candidates
also include an **external AMM price source** with a staleness-aware two-tier clamp
(±10% while the reference feed is live, ±25% when the feed has slept >18h) —
recorded here so the weekend-dislocation case has a home. The interface —
`realizedVolBps / poke / isStale` — does not change, so the policy and the model's
feature contract are unaffected by an estimator swap.

## Events

`VolUpdated(token, volBps, updatedAt)` — emitted on each **accepted** `poke(token)`;
rejected observations emit nothing. See [`events.md`](./events.md).

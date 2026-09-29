# INyseCalendar — NYSE session calendar library

Normative source: `DESIGN.md` §3.2.9, §5.4. Changes require agreement of all three
lanes.

## Purpose

`INyseCalendar` answers the two calendar-native model features — how long since the
last NYSE regular-session close, and how long until the next open — plus the
holiday-adjacent flag, entirely on-chain from a baked constant table. It is a **pure
library**: no storage, no external calls, no admin.

## Interface

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface INyseCalendar {
    function windows(uint40 now)
        external
        pure
        returns (uint32 secsSinceClose, uint32 secsToOpen, bool holidayAdjacent);
}
```

## Table generation

- Source: `exchange_calendars==4.13.2` (pinned), XNYS calendar, spot-verified
  against the official NYSE holiday/early-close list.
- Coverage: **2024–2028** regular sessions **including early closes** (e.g. day
  after Thanksgiving, Christmas Eve).
- Lane A tooling emits `calendar_table.json` (see
  [`student-export-format.md`](./student-export-format.md)); Lane B generates
  Solidity constants from it. The table is baked at deploy time — there is no
  update path; deployments past 2028 redeploy.

## Semantics

For a timestamp `now` (uint40, seconds since epoch):

| Return | Type | Meaning |
|---|---|---|
| `secsSinceClose` | uint32 | Seconds since the most recent regular-session close (early closes count as closes). **Capped at 604800** (7 days); longer closures saturate. |
| `secsToOpen` | uint32 | Seconds until the next regular-session open. **Capped at 604800**; saturates the same way. |
| `holidayAdjacent` | bool | True when the session preceding the last close was a shortened / holiday-adjacent session. Feeds `Features.flags` bit0. |

Inside an active trading session, `secsSinceClose`/`secsToOpen` still refer to the
bracketing regular-session boundaries (previous close, next open) — the functions
describe position within the market-closure cycle, not within the trading day.

## Testing contract

The generated library **must match the Python `exchange_calendars` library
exactly**. Two layers, per DESIGN.md §5.4/§5.8:

1. **50 committed golden vectors** in `golden_vectors.json` (the `calendarVectors`
   subset — see [`student-export-format.md`](./student-export-format.md)) —
   timestamp → `(secsSinceClose, secsToOpen, holidayAdjacent)`; all 50 must match
   exactly.
2. **A 1000-random-timestamp sweep in CI** against the live Python library, using
   the same generator, across the covered range.

Any mismatch fails the build — the on-chain calendar and the training-time feature
pipeline must be bit-identical, or the calendar features are meaningless.

## Consumers

[`IRiskPolicy`](./IRiskPolicy.md) builds `secsSinceClose`, `secsToOpen`, and
`flags` bit0 from this library when assembling the `Features` struct for
[`IGapRiskModel.score`](./IGapRiskModel.md). Demo deployments evaluate it at
`demoNow` instead of `block.timestamp` (see IRiskPolicy demo mode).

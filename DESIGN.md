# GapGuard — Design Document

Status: v1.1 — 2026-09-29 (post-review re-plan: 2-day crash schedule, vol-oracle redefinition, spec hardening)
Input: `goal.md` (hackathon goal document). This document resolves its open questions (§7), dispositions its risk register (§8), and pins the interfaces (§11) so three work lanes can proceed in parallel.
Constraint: implementable and deployable in 4 days (D0–D4); v1.1 re-plan compresses to a **2-day crash schedule** (§6) with submission planned **Sep 30 evening SGT**, well ahead of the confirmed **Oct 4** deadline (§2.4).
Companion docs (prewritten, normative where marked): `docs/interfaces/*.md`, `README.md` skeleton.

---

## 1. Product in one paragraph

GapGuard is an on-chain risk-parameter feed for stock-token collateral on Robinhood Chain. A tiny int8 MLP (the "student", 3–5K params, distilled from an off-chain teacher) runs as a Stylus contract and scores overnight/weekend **gap risk** from chain-native and calendar-native features only. A Solidity **policy contract** turns the score into a dynamic max-LTV factor and gates a mock lending pool. No operator can inject or withhold data — vol-oracle freshness is permissionless (anyone can poke): inference is deterministic, weights are public, and every consumer reads the parameter synchronously in the same transaction. Hard caps and fail-closed paths bound the damage of a fooled model.

One-liner (deck): *"A Saturday-morning seatbelt for stock-backed loans — a tiny on-chain model that feels the weekend coming and quietly tightens the straps."*

**Named first integrator archetype (D4):** a Morpho-style isolated lending vault using GapGuard as its LLTV oracle. The mock pool is built to look like that archetype (per-token LLTV, no cross-margin). Secondary consumer shown in the demo: an agent session-key guard reading the same policy before spending. Rationale: vault LLTV is the most legible "risk parameter as a product" shape for this jury, and the session-key read costs us one extra view call in the demo script.

---

## 2. Verified external facts (research results, with sources)

These replace goal.md §7 guesses. Confidence and URLs included; time-sensitive items re-verified on D0.

### 2.1 Chain

| Fact | Value | Confidence / source |
|---|---|---|
| Chain IDs | mainnet **4663** (`0x1237`), testnet **46630** | confirmed — docs.robinhood.com/chain/deploy-smart-contracts |
| RPC | `https://rpc.{mainnet,testnet}.chain.robinhood.com` | confirmed — official docs |
| Explorer | mainnet: robinhoodchain.blockscout.com; testnet: explorer.testnet.chain.robinhood.com | confirmed — official docs |
| Gas token | ETH (18 dec); mainnet gas floor 0.02 gwei, recent base fee ~0.5 gwei → deploy ≈ single-digit dollars | confirmed — Bitquery investigation 2026-09-04 |
| Block/tx gas limit | **No Robinhood-specific value published.** Arbitrum effective per-block execution cap **32M gas**; observed sustained throughput ~40M gas/s. Self-reported speed limit (7M gas/s) is unreliable. | inferred from Arbitrum defaults + Bitquery; probe on D0 |
| Max contract size | 96 KB code / 192 KB initcode | confirmed — docs "Differences from Ethereum" |
| `block.number` quirk | returns L1 block estimate; use `ArbSys(0x64).arbBlockNumber()` for L2 height (we use timestamps everywhere, so unaffected) | confirmed — official docs |
| Sequencer compliance screening | sanctioned-address transactions excluded at sequencer | confirmed — official docs (note in threat model, not a design dependency) |
| Stylus on testnet | **confirmed**: `ArbWasm.stylusVersion()` = 3 (chain 46630); two independent projects deployed (Sigma, HarvestBot). Testnet has **no ArbOS cache manager** → our gas numbers will be worst-case (a feature: honest upper bound) | confirmed — github.com/dmetagame/sigma, hackquest.io/projects/HarvestBot |
| Stylus on mainnet | **unconfirmed.** Mainnet runs a Stylus-capable Nitro build; no official statement, no confirmed deployment | D0 probe: call `ArbWasm(0x71).stylusVersion()` on mainnet |
| Faucet | faucet.testnet.chain.robinhood.com — 0.01 ETH + 5 of each test Stock Token per 24h; backups: Alchemy (0.1 ETH/24h), QuickNode (12h), Chainstack (1 ETH/24h). No advance request needed | confirmed |
| Permissionless deploy | both networks confirmed permissionless | confirmed — official docs + observed third-party deployments |
| Stock tokens | ERC-20, **18 decimals**, ERC-8056 `uiMultiplier()` for corporate actions; ~95 on mainnet. Testnet faucet tokens: TSLA, AMZN, NFLX, PLTR, AMD (addresses in `docs/interfaces/deployments.md`) | confirmed — docs.robinhood.com/chain/stock-tokens; testnet addresses from community repos (verify on D0) |
| Chainlink | official oracle; Data Feeds + Streams + CCIP **mainnet only**. Feeds are 24/5 (sleep on weekends), pause via `oraclePaused()` during corporate actions, USD feeds 8 dec. **No ETH/USD feed on the chain.** No testnet feeds → mock feeds on testnet (same pattern as the official example repo `hummusonrails/robinhood-chain-dapp-example`) | confirmed — chain.link blog, docs.chain.link/data-feeds/tokenized-equity-feeds/robinhood |

### 2.2 Stylus engineering

| Fact | Value | Source |
|---|---|---|
| Toolchain | Rust 1.91+, cargo-stylus 0.10.7, `wasm32-unknown-unknown`, **Docker required** for check/deploy | docs.arbitrum.io/stylus/quickstart |
| Deploy flow | `cargo stylus check` (compile + Brotli + dry-run activation) → `cargo stylus deploy --endpoint=<RPC>` (2 txs: deploy + activate). Activation ≈ 1,659,168 gas fixed + data fee | docs.arbitrum.io/stylus |
| **No floats** | WASM floats are rejected at activation (consensus determinism). Integer-only math required — proven pattern: stylus-nanoGPT ran a 20,304-param int8 model (fixed-point, 12 fractional bits, LUT for nonlinearities) in one tx at 4.1M gas; ~200× cheaper than Solidity | docs.arbitrum.io/stylus/concepts/webassembly; github.com/OffchainLabs/stylus-nanoGPT |
| Expected inference gas | our MLP is ~5–10× less work than one nanoGPT token step → **order 10⁴–10⁵ gas per inference** + ~9k call-init (uncached). Trivially inside any realistic tx cap. Measure on D2–D3 | inferred from nanoGPT data |
| Call overhead | uncached entry ~8,832 gas, cached 352 gas (testnet: no cache manager → always worst case) | docs.arbitrum.io/stylus/concepts/gas-metering |
| Program expiry | Stylus programs expire ~365 days without keepalive (`ArbWasm.codehashKeepalive`) — post-hackathon concern, note in README/roadmap M1 | docs.arbitrum.io/stylus/concepts/activation |
| Size limits | 128 KB decompressed WASM (256 KB at ArbOS61+); compressed >24KB auto-fragmented. Our ~4KB weights are far under every limit | docs.arbitrum.io/stylus |
| Source verification | **Problem outdated**: `cargo stylus deploy` builds in a pinned Docker container (reproducible by default); `cargo stylus verify --deployment-tx <hash>` rebuilds and compares on-chain bytecode. No Arbiscan verification on Orbit chains → README ships: committed `Cargo.lock` + `rust-toolchain.toml` + `cargo stylus verify` instructions | docs.arbitrum.io/stylus/cli-tools/verify-contracts |
| Interop | Stylus contract = plain address + standard ABI; Solidity calls it normally. `cargo stylus export-abi` generates the Solidity interface (note snake_case→camelCase selector conversion) | docs.arbitrum.io/stylus/how-tos/exporting-abi |

### 2.3 ML / data

| Fact | Decision it feeds | Source |
|---|---|---|
| `exchange_calendars` (v4.13.2, 2026-03) — actively maintained; has `previous_close`, `next_open`, native early closes | calendar feature generation + on-chain calendar table | github.com/gerrymanoim/exchange_calendars |
| yfinance: `auto_adjust=False, actions=True`, build own adjustment factors; known dividend-misclassification bug (issue #2666) corrupts Adj Close | data pipeline | github.com/ranaroussi/yfinance/issues/2666 |
| sklearn has `mean_pinball_loss`, `brier_score_loss`; ECE not in sklearn → use `netcal` ECE (10 bins, fixed) | bake-off metrics | sklearn docs; github.com/efs-opensource/calibration-framework |
| TabPFN: `pip install tabpfn`; v2 ≤10K rows/500 feats, does regression quantiles; 2.5+ needs PriorLabs login + non-commercial license | TabPFN gets a 1h box, v2, Apache-2.0 weights; drop cleanly if it fights | github.com/PriorLabs/TabPFN |
| Distillation GBM→tiny MLP | mimic distillation on teacher soft outputs (Buciluǎ 2006 pattern); oversample near teacher decision boundaries | arXiv 2005.11638; PriorLabs' own product validates the pattern |
| int8 scheme | **per-channel symmetric int8 weights, per-tensor symmetric int8 activations (zp=0), int32 accumulators, requantize via multiplier+shift** (TFLite/Jacob et al. 2018). Overflow ruled out arithmetically: fan_in×16,129 ≪ 2^31 even at fan_in=1024 | arXiv 1712.05877; LiteRT quantization spec |
| Fidelity measurement | holdout + pseudo-data agreement, boundary-weighted sampling, PGD-style divergence attack (student is differentiable) | arXiv 1805.05532 |
| Weekend gap evidence | structural: Kraken xStocks mostly 24/5, Bitget stock perps freeze prices on weekends, RWA.xyz documents tokenized-stock NAV problems | support.kraken.com xStocks FAQ; app.rwa.xyz blog |

### 2.4 HackQuest / submission

| Fact | Value | Source |
|---|---|---|
| **Deadline** | Submissions **Sep 13/14 – Oct 4, 2026**; winners announced **Oct 12**. Confirmed across openhouse.arbitrum.io, the HackQuest event page, and mirrors. | re-verified 2026-09-29: openhouse.arbitrum.io, hackquest.io event page |
| **Submission plan** | **Submit Sep 30 evening SGT**, ~4 days ahead of the deadline (R13). Confirm format rules in event Discord (still outstanding) | — |
| Submission form | project name, one-liner, **demo video AND separate pitch video**, description, "Progress During Hackathon" changelog, team, payout wallet, deployment environment, **contract address + explorer link** (judge-only). Repo must be public with real commit history | secondhand field map (github.com/zedili/Signal402) + HackQuest best-practices blog |
| Video length | generic guidance 2–5 min; NYC edition reportedly 1–2 min → **cap both videos at 2:00** | competehub.dev + HackQuest blog |
| Eligibility | 18+; existing projects allowed if meaningfully developed during window (CoC wording conflicts; our repo starts clean → moot). No language requirement found → English | T&Cs §1, §3 |
| Judging criteria | Innovation; Technical implementation; Use of Arbitrum technology; Potential impact; Presentation quality (+ novelty bonus). **No published weights.** goal.md's four-criteria mapping stays, plus add "Use of Arbitrum technology" (Stylus) and "Presentation" rows to the README matrix | T&Cs; DevConnect mirror |
| Prize payout | **25%** on signing grant agreement, **25%** at 1-month check-in (building exclusively on an Arbitrum chain), **50%** after mainnet launch + agreed KPI. Roadmap slide must be written as 25/25/50 milestone candidates, not "50/50" | T&Cs §6.2 |
| Robinhood podium | confirmed: ≥1 of 3 podium prizes per track reserved for Robinhood Chain projects | T&Cs §6.2 |
| Collision | **Sigma** (London buildathon entry): Stylus on-chain risk engine for tokenized-equity collateral, parametric VaR, owner-updated vols, testnet-only, dormant. No production risk/vol oracle exists on Robinhood Chain. | github.com/dmetagame/sigma |

---

## 3. Decisions — all goal.md §7 questions resolved

Format: `#. Decision — rationale`. (V) items become D0 verification tasks with the exact probe.

### 3.1 Product & market
1. **Mock pool; the feed is the product.** Pool is shaped as a Morpho-style isolated vault (per-token LLTV) so it demos the named archetype without integration risk.
2. **Collision answered (R):** Sigma exists (Stylus VaR engine, London entry). Our wedge — *gap risk from market-closure structure, distilled neural model, public weights, no operator data inputs* — is disjoint from parametric VaR with owner-updated vols. README gets an explicit "How we differ from Sigma" paragraph. Naming/branding freezes as "GapGuard" (no collision found).
3. **Business model: public good.** Free read (view function), no fee switch at MVP. M2 pitch: monetization only via optional premium SLA/watchtower services later; the parameter feed itself stays a public good. Picked because it matches the credible-neutrality claim and the prize's public-infrastructure framing.
4. **First integrator archetype: Morpho-style isolated vault** (see §1).

### 3.2 Data & model
5. **Token universe:** demo on testnet faucet tokens (TSLA primary; AMZN, NFLX, PLTR, AMD available). Teacher training universe: ~30 large-cap US equities with clean 10y history (TSLA, NVDA, AAPL, AMZN, NFLX, PLTR, AMD, MSFT, META, GOOGL, JPM, XOM, …) matching mainnet-listed tokens where possible. D0: verify testnet token addresses on explorer.
6. **Label (D):** primary output `p = P(|open_t / close_{t−1} − 1| > 5%)` over the next close→open transition; secondary quantile heads q90/q95 of |overnight return| (teacher only, used for bake-off selection and distillation targets). **Student exports a single score: `riskBps = round_up(p × 10000)`.** Fixed on D1 before anything downstream.
7. **Position features have no empirical distribution — the gap-risk label is position-independent (D).** During teacher training and distillation, `ltvBps ~ U(0,7000)` and `concentrationBps ~ U(0,10000)` are sampled independently per row (7000 = `MAX_LTV_HARD_CAP_BPS`). The adversarial fidelity grid (item 13) sweeps both axes, so the ≤200 bps threshold certifies position-independence instead of assuming it.
8. **Corporate actions (R):** pull raw OHLC + actions (`auto_adjust=False, actions=True`); build adjustment factors ourselves; **exclude close→open pairs that span an ex-dividend or split date from training labels** (they are mechanical, not risk). Keep the affected rows as a feature-engineering sanity set. Cross-check a sample against Stooq.
9. **Calendar (R):** `exchange_calendars` (pin `exchange_calendars==4.13.2`), XNYS calendar, spot-verified against the official NYSE 2026–2028 holiday/early-close list. The same library generates the on-chain calendar table (§5.4).
10. **On-chain volatility (D):** one `VolatilityOracle` contract per deployment, serving all registered tokens with per-token state (see §5.3). Ring buffer of 32 observations per token; permissionless `poke(token)` with min interval 1h (reverts `PokeTooSoon()` earlier) **appends the reference feed's current answer** (mock Chainlink on testnet, real feed on mainnet); a per-poke **jump bound** rejects the observation if |new − last accepted| / last accepted > 10%; vol estimator = EMA of |log-free relative returns| in bps, integer math only. Feed integrity is a documented **trust assumption** (deployer-controlled mock on testnet; Chainlink on mainnet) — no AMM/DEX price source exists on testnet, so the original pool-price design was circular. Rationale: manipulation bounded by the clamp, estimator replaceable behind the interface, keeps the student a pure function.
11. **Score cadence (D):** **computed fresh per transaction.** Stylus inference is ~10⁴–10⁵ gas — cheap enough that caching adds staleness for no meaningful saving, and fresh-per-tx is the synchronously-composable product claim. No `poke()` on the policy; `poke()` exists only on the vol oracle (which accumulates state by nature).
12. **Cold start (D):** `COLD_START_MAX_LTV_BPS = 3500` (35%) — a conservative constant applied to any token without a registered model/vol history. Registration = immutable constructor token list (token, baseMaxLtvBps, assetClass, referenceFeed); no admin setter at MVP. Adding a token = redeploy, same story as the calendar table. Documented as governance-tunable post-MVP.
13. **Fidelity threshold (D):** **≤ 200 bps worst-case |p_student − p_teacher|** on the adversarial evaluation grid (boundary-weighted + PGD), fixed *before* distillation starts. If unmet: first remedy is one QAT epoch; second is +1 hidden unit width; we do not tune the threshold to taste.
14. **Quantization (R):** per-channel symmetric int8 weights; per-tensor symmetric int8 activations (zp=0); int32 accumulators; bias int32; requant = multiplier∈[0.5,1) + right shift. Overflow: ruled out arithmetically at our fan-ins (§2.3). Feature→int8 normalization uses **fixed published ranges** embedded in the model contract.
15. Time-series models (N-BEATS/PatchTST): **parked, do not revive this week** (unchanged).

### 3.3 Chain & contracts
16. **Gas budget (V):** layered test ceilings — `score()` ≤ **200k** gas; `RiskPolicy.maxLtvBps` ≤ **250k**; pool gated borrow/withdraw ≤ **500k** (the 500k keeps the ≤1.5%-of-32M-block-cap rationale, now attached to the real user transaction). The Solidity-fallback backend gets `SCORE_GAS_CEILING_FALLBACK = 3,000,000`. D0: probe actual per-tx cap via a gas-estimation call on both networks.
17. **Stylus mainnet (V):** D0 probe `ArbWasm(0x71).stylusVersion()` on chain 4663. Result recorded in README; deployment ladder unchanged (testnet primary, mainnet stretch).
18. **Faucet (V):** answered in §2.1 — no advance request; hit official faucet + Alchemy on D0 for deployer + demo wallets.
19. **Chainlink feeds (V):** mainnet only. Testnet: mock feeds (AggregatorV3-compatible, pattern from the official example repo). Mainnet deployment would use real feed addresses (documented in `docs/interfaces/deployments.md`). Feed staleness windows must be ≥72h-aware (24/5 feeds sleep on weekends — staleness is a *feature input*, not an error).
20. **Contract boundary (D):** split. `GapRiskModel` (Stylus, pure score), `VolatilityOracle` (stateful, own contract), `NyseCalendar` (library, pure), `RiskPolicy` (orchestrator), `ModelRegistry` (pointer). The student stays a pure function of an 8-field feature vector — that purity is what makes fidelity testing, reproducibility, and future ZK/dispute slots possible.
21. **Upgradeability (D):** redeploy + registry pointer with timelocked propose/activate (24h param). No proxies. Honest for public-weights claims; roadmap M5 swaps owner → multisig.
22. **Stylus fallback trigger (D):** hard deadline **EOD today, 2026-09-29** (with the hello-world deploy). Signal: `cargo stylus check` passes **and** deploy+activate succeeds on testnet **and** one on-chain `score()` call on the committed synthetic test model matches Lane B's independently computed reference output **exactly**. The synthetic model (`contracts/test/synthetic_export.json` — hand-set int8 weights on a small MLP, written in the student-export-format.md schema) and `synthetic_vectors.json` (3 feature vectors; expected scores from a ~30-line standalone script written and hand-checked by Lane B) are committed today and depend on nothing from Lane A. Lane A's `golden_vectors.json` remains a binding CI gate (student-export-format.md §4), never the go/no-go input. Failing any → Lane B switches to a Solidity implementation of the identical int8 model (architecture is deployment-constrained, so the port is mechanical; **~0.3–1M gas expected** — the earlier 50–200× figure came from stylus-nanoGPT's comparison against a storage-based Solidity interpreter; with weights as code constants (~15–25 gas per multiply-accumulate, 10–20K MACs) the port is ~3–10× the Stylus expectation, and Lane B gas-measures the port before go/no-go — it is written either way, so the measurement is free). Owner: Lane B lead; no meeting required, the signal is objective.
23. **Source verification (R):** solved by cargo-stylus ≥0.5 defaults: Docker reproducible build + committed `Cargo.lock` + `rust-toolchain.toml`; README ships `cargo stylus verify --deployment-tx …` instructions and the weights hash. No Arbiscan on Orbit → local verify is the proof path.
24. **Fixed point (D):** **bps (uint16, 0–10000) across every boundary** — no 18-decimal values in any interface. Rounding: scores round **up** (toward higher risk); LTV limits round **down** (toward tighter limits). Quantization scales are Q16 fixed-point constants, documented in the export format.

### 3.4 Trust & security
25. **Input manipulation (R):** controls that are MVP-scope: (a) vol oracle **jump clamp vs last accepted observation** (±10%) + 1h min poke interval; (b) oracle-staleness and deviation are *inputs to the model*, so a gaming attempt moves the score toward caution, not away; (c) hard caps bound max LTV regardless of score; (d) fail-closed: any out-of-range feature, stale vol oracle (>26h since update), or paused reference feed → `maxLtv = 0`; (e) **availability:** poke freshness is permissionless; team convenience keeper at MVP documented in README — an availability assumption, not trust; a down keeper only fails closed. Full threat model in `README.md#threat-model`.
26. **White-box model (R):** acknowledged by design: public weights + hard caps + fail-closed + conservative rounding. Residual risk (adversarial feature-space search) written down honestly in README §"Limitations".
27. **Kill switch (D):** `RiskPolicy.pause()` by a guardian (MVP: deployer EOA, documented; M5: 2-of-3 Safe). Pause is instant and sets all limits to 0; **unpause requires a 48h timelock** (queued via `unpause()` → `UnpauseScheduled` event → executable). Asymmetry chosen deliberately: fast to stop, slow to restart.
28. **Miscalibration incident path (D):** guardian pauses (instant) → new weights go through registry `propose` (24h timelock) → `activate`. Policy reads model from registry, so consumers need no redeploy. README documents this as the runbook; M5 adds the multisig and recalibration cadence.
29. **Exploit walkthrough (R):** table-topped **Wed 9/30 morning** before policy math freeze. The "wash-trade to spike vol → tighten rivals' limits" attack is moot: **no AMM exists on the deployment networks**, so there is nothing to wash-trade — the manipulation surface is reference-feed integrity, listed as a trust assumption (§3.2.10). The remaining canonical attack ("smooth own inputs → inflate own limit → walk away Monday") is written up in README §threat-model with why each control blunts it (caps bind, fail-closed triggers).

### 3.5 Demo & submission
30. **Time travel (V):** **demo-mode deployment.** `RiskPolicy` has an immutable `demoMode` constructor flag. Demo deployment (separate address) sets it true, enabling a `setDemoNow(uint40)` that shifts the calendar's view of time (emits `DemoTimeSet`, flagged in README as demo-only). Production deployment has `demoMode = false` and **no override path exists in the bytecode**. Chosen over timestamp-as-feature (keeps the Features struct clean and the trust story intact) and over local fork (judges can replay on the live testnet).
31. **HackQuest format (V):** see §2.4 — repo + 2 videos (demo ≤2:00, pitch ≤2:00) + contract address/explorer link + changelog field. **Deadline Oct 4**; confirm format rules in Discord; submit Sep 30 evening SGT (R13).
32. **Demo medium (D):** recorded video primary (scripted, deterministic); live demo optional during any judging call. Judges are assumed to *watch and read*, not run code — but everything is reproducible from the README.
33. **Language (R):** no requirement found → English for all submission material.
34. **Eligibility (V):** existing projects allowed if meaningfully developed in-window; our repo starts clean → non-issue.

---

## 4. Architecture

```
Off-chain (Lane A, build time)                On-chain (Lane B, runtime)
─────────────────────────────                 ─────────────────────────────────────────
yfinance raw bars + actions                   ┌─────────────────────────────┐
  → clean/adjust, drop CA-spanning gaps       │ GapRiskModel (Stylus, WASM)  │
  → features via exchange_calendars           │ int8 MLP, pure function      │
  → teacher bake-off (LGBM/MLP/TabPFN)        │ score(Features) → riskBps    │
  → distill → per-channel int8 quantize       │ weightsHash() → bytes32      │
  → student_export.json ─────────────────────→└──────────────▲──────────────┘
  → golden_vectors.json ──────────┐                        │ view call
  → calendar_table.bin ───────┐   │               ┌─────────┴───────────────┐
                              │   │               │ RiskPolicy (Solidity)    │
                              ▼   ▼               │  NyseCalendar (library)  │
                     weights + ranges +           │  score → maxLtv factor   │
                     calendar baked at            │  hard caps, fail-closed  │
                     deploy; verified vs          │  pause / 48h unpause     │
                     golden vectors in CI         │  demoMode (immutable)    │
                                                  └───▲───────────▲─────────┘
                              ┌───────────────┐       │           │
                              │ ModelRegistry │───────┘           │ reads
                              │ propose/act.  │                   ▼
                              │ + timelock    │          ┌──────────────────┐
                              └───────────────┘          │ VolatilityOracle │
                                                         │ ring buffer ×32  │
                              ┌───────────────┐          │ poke() ≥1h,      │
                              │ MockChainlink │◄─────────│ ±10% clamp       │
                              │ Feed (testnet)│  clamp   └──────────────────┘
                              └──────┬────────┘
                                     ▼
                              MockLendingPool (Morpho-style isolated vault)
                              borrow/withdraw gated by RiskPolicy.maxLtvBps
```

Trust boundary: everything right of the dashed line needs no operator. The only off-chain artifact that crosses the boundary is `student_export.json` (+ calendar table), pinned by `weightsHash` and reproducible-build verification.

---

## 5. Interfaces (normative — changes require all three lanes to agree)

Full prewritten docs: `docs/interfaces/`. Summary here; the docs are the contract.

### 5.1 `Features` — the one shared struct

```solidity
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
```

Rules: raw, human-meaningful units only — **quantization/normalization happens inside the model contract**, so callers never learn the int8 scheme. All fields range-checked; out-of-range → fail-closed at the policy. bps everywhere; no 18-dec values in any interface. `flags` bit0 comes from the on-chain calendar.

### 5.2 `IGapRiskModel` (Stylus student) — `docs/interfaces/IGapRiskModel.md`

```solidity
interface IGapRiskModel {
    function score(Features calldata f) external view returns (uint16 riskBps);
    function weightsHash() external view returns (bytes32); // keccak of canonical student_export.json
}
```
Pure, view, no storage writes. `riskBps = ceil(P(|gap|>5%) × 10000)`. Test ceiling: 200k gas per call (expected ~10⁵ + ~9k uncached init).

### 5.3 `IVolatilityOracle` — `docs/interfaces/IVolatilityOracle.md`

```solidity
interface IVolatilityOracle {
    function realizedVolBps(address token) external view returns (uint16 volBps, uint40 updatedAt);
    function poke(address token) external;                 // permissionless; reverts PokeTooSoon() if <1h since last
    function isStale(address token) external view returns (bool); // true if >26h since updatedAt
}
```
One oracle instance per deployment serving all registered tokens; per-token ring buffer 32×(price,timestamp). `poke(token)` appends the reference feed's current answer; observation rejected if it jumps >10% vs the last accepted observation; estimator = EMA of |relative returns| (integer math). Early `poke()` reverts (deterministic, trivially testable). Fail-closed handled by the policy via `isStale(token)`.

### 5.4 `INyseCalendar` (library) — `docs/interfaces/INyseCalendar.md`

```solidity
interface INyseCalendar {
    function windows(uint40 now) external pure returns (uint32 secsSinceClose, uint32 secsToOpen, bool holidayAdjacent);
}
```
Generated table (2024–2028 sessions incl. early closes), produced by Lane A tooling from `exchange_calendars`, baked as constants. Pure. Test contract: 50 committed calendar golden vectors in `golden_vectors.json` **plus** a 1000-timestamp CI sweep against the live Python library.

### 5.5 `IRiskPolicy` — `docs/interfaces/IRiskPolicy.md`

```solidity
interface IRiskPolicy {
    function maxLtvBps(address token, uint16 ltvBps, uint16 concentrationBps)
        external view returns (uint16 maxLtv, uint16 riskBps);
    function pause() external;            // guardian, instant
    function scheduleUnpause() external;  // guardian, executable after 48h
    function setDemoNow(uint40 t) external; // demoMode deployments only
}
```
Risk curve: **5-breakpoint monotonic step table** (constants, e.g. risk 0/500/1500/3000/5000 bps → factor 100/85/65/45/25% of base max LTV). Chosen over a linear clamp: auditable at a glance, tunable without touching the model, and steps are un-gameable-by-epsilon (no gradient to surf). Hard caps: `MAX_LTV_HARD_CAP_BPS = 7000`; floor 0 under fail-closed; cold start 3500. Fail-closed conditions enumerated in the doc.

### 5.6 `IModelRegistry` — `docs/interfaces/IModelRegistry.md`

```solidity
interface IModelRegistry {
    function currentModel() external view returns (address model, bytes32 weightsHash, uint64 activatedAt);
    function propose(address model, bytes32 weightsHash) external; // owner; starts 24h timelock
    function activate() external;                                  // anyone, after timelock
    event ModelProposed(address model, bytes32 weightsHash, uint64 activateAfter);
    event ModelActivated(address model, bytes32 weightsHash);
}
```
Documented-but-unimplemented slots (M3/M6): attestation-bond field and ZK-proof slot are named in the doc as reserved extensions so the interface survives the roadmap without a breaking change.

### 5.7 `IGapGuardPool` (mock pool) — `docs/interfaces/IGapGuardPool.md`

Morpho-style isolated vault: `depositCollateral / borrow / repay / withdrawCollateral`, single market (WETH or USDC borrow asset vs one stock token at a time), LLTV read from `IRiskPolicy.maxLtvBps` at borrow/withdraw time, liquidation bonus fixed 5%. No oracle pricing of its own beyond the reference feed — keeps the mock honest about what it is.

### 5.8 Cross-lane artifacts (A→B) — `docs/interfaces/student-export-format.md`

- **`student_export.json`** — canonical, hash-pinned: architecture (layer sizes), per-channel weight scales (Q16), activation scales, int8 weights (hex), feature normalization ranges (min/max per field), temperature constant, `featureSpecVersion`, `weightsHash`. Lane B tooling generates Rust constants from it; CI checks `weightsHash == on-chain weightsHash()`.
- **`golden_vectors.json`** — 100 rows: raw `Features` → expected `riskBps` (from the quantized Python reference, not the float model). Lane B's student must match all 100 exactly; 50 calendar timestamps → `(secsSinceClose, secsToOpen, flag)` for the calendar library.
- **`calendar_table.json`** — sessions/early-closes 2024–2028 → generated Solidity constants.

### 5.9 Events (consumed by demo UI and future watchtowers)

`LimitChecked(token, ltvBps, maxLtv, riskBps)` (emitted by the **pool** on every gated borrow/withdraw — the policy's `maxLtvBps` is `view` and cannot emit; the pool holds the action context), `VolUpdated(token, volBps, updatedAt)` (oracle, on accepted poke), `CapHit(token, requestedLtv, cap)` (pool), `Paused/UnpauseScheduled/Unpaused` (policy), `ModelProposed/ModelActivated` (registry), `DemoTimeSet(t)` (demo deployments only).

---

## 6. Lanes (parallel work plan)

| Lane | Owns | Consumes | Produces |
|---|---|---|---|
| **A — Model** | data pipeline, bake-off, distill+quantize, export, fidelity | §3.2 decisions; §5.8 format | `student_export.json`, `golden_vectors.json`, `calendar_table.json`, bake-off + fidelity + calibration tables |
| **B — Contracts** | all contracts, tests, deploy scripts, gas measurement | §5 interfaces; A's artifacts (stubbed with a hand-specified model until D2 — R2 fallback built in) | deployed addresses, ABIs, gas table, test + invariant/fuzz results |
| **C — Demo & submission** | README from D1, demo script + UI, videos, HackQuest form, Discord confirmations | B's addresses/ABIs/events; A's tables | README, ≤2:00 demo video, ≤2:00 pitch video, submission |

Lane decoupling guarantees:
- B never blocks on A: a `HandcraftedModel` (Solidity, ~10 lines, hand-set weights from domain priors) implements `IGapRiskModel` from D1 morning; the real student is a drop-in registry update.
- C never blocks on B: demo script is written against §5 interfaces and run against a local devnode/fork until testnet addresses exist.
- A never blocks on B: fidelity is measured Python-side against the export format; on-chain match is B's golden-vector CI.

### Day plan (supersedes goal.md §9 — **2-day crash schedule**; deadline **Oct 4**; submission planned **Sep 30 evening SGT**)

| Day | Lane A | Lane B | Lane C |
|---|---|---|---|
| **Tue 9/29** (D0+D1 merged) | Data pull + feature pipeline (clamp-before-normalize, feed-jump deviation series, position-feature marginalization); bake-off starts; TabPFN box cut to 1h | Outstanding probes by noon (`ArbWasm.stylusVersion()` both nets, per-tx gas-cap probe, faucet both wallets, verify testnet token addresses), then all contracts vs `HandcraftedModel`; commit `synthetic_export.json` + `synthetic_vectors.json`; hello-world Stylus deploy → **go/no-go EOD today** | Discord deadline/video confirmation; README skeleton |
| **Wed 9/30** (D2+D3 merged) | Distill + quantize + adversarial fidelity by 10:00 SGT (hard gate) | Testnet deploy by 12:00 SGT with the student as the registry's GENESIS model; end-to-end integration; gas table; threat-model session + policy-math freeze folded into the morning; golden-vector CI runs on artifact arrival | Record both ≤2:00 videos 13:00–17:00 SGT against deployed contracts; **submit ≤ 20:00 SGT** |
| **Cuts** | Calibration refit — ship ECE as measured (goal.md §5.3 permits) | Fuzz reduced to smoke set | Mainnet stretch; demo UI → scripted screenflow |

---

## 7. Risk register dispositions (goal.md §8)

| # | Disposition |
|---|---|
| R1 Stylus snags | Testnet Stylus confirmed (v3, two prior deployments) → likelihood downgraded Medium→Low. Fallback (Solidity port) and EOD-9/29 trigger retained. |
| R2 Data plumbing | Mitigated structurally: `HandcraftedModel` stub means contracts + demo ship even with zero ML. yfinance pitfalls pre-answered (§3.2.8). |
| R3 Bake-off expansion | TabPFN boxed at 1h, v2 weights (Apache-2.0), drop = table ships with two rows. |
| R4 "Is the ML real?" | Bake-off table + adversarial fidelity + ECE published; honesty framing kept. |
| R5 Input manipulation | Controls are MVP-scope and specified (§3.4.25); threat-model session 9/30 morning before policy freeze. |
| R6 Demo time-travel | **Resolved**: demoMode deployment design (§3.5.30). |
| R7 Testnet instability | 4 faucets identified; ladder unchanged; mainnet is an upgrade path not a rescue. |
| R8 Scope creep | Cut principle restated; the only sanctioned scope question this week is "does it make the Sep 30 submission safer?" |
| R9 Collision | **Resolved with evidence**: Sigma documented; differentiation paragraph is a required README section. |
| R10 int8 overflow | Ruled out arithmetically (§2.3); property tests on feature bounds + score∈[0,10000] invariant retained as belt-and-braces. |
| R11 Prize expectations | Corrected: payout is **25/25/50** with mainnet-launch KPI; roadmap slide written as milestone candidates accordingly. |
| R12 Regulatory optics | Unchanged framing: infrastructure parameter feed; no advice anywhere. |
| R13 Submission surprise | Format extracted (§2.4); **deadline confirmed Oct 4**; submission planned Sep 30 evening SGT. |

---

## 8. What this design deliberately does not decide

- Exact MLP layer widths (A chooses within 3–5K params during distillation).
- Step-table breakpoint values (freeze **Wed 9/30 morning** after the threat-model session; the *shape* — 5 monotonic steps — is fixed).
- TabPFN's row in the bake-off (1h box decides).

These are the only parameters left floating; every interface above is closed.

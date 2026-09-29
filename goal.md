GapGuard — Hackathon Goal Document

Event: Arbitrum Open House Singapore — Online Buildathon (Phase 1)
Submission deadline: October 4, 2026 (confirm timezone on HackQuest — open question, see §7)
Target track: General track, Robinhood Chain deployment (reserved podium spot exists for Robinhood Chain projects)
Document purpose: Input for interface definitions and the technical spec. Records what we build, why, every decision taken, and every known unknown.
1. Mission

Put the risk referee inside the vault: a small neural risk model that lives on-chain and continuously scores gap risk for stock-token collateral on Robinhood Chain, with a policy contract that enforces the score as dynamic borrowing limits — no off-chain operator in the critical path, nothing attested, nothing trusted.

One-liner for the deck: "A Saturday-morning seatbelt for stock-backed loans — a tiny on-chain model that feels the weekend coming and quietly tightens the straps."

2. Problem statement

- Robinhood Chain trades tokenized equities 24/7; the reference market (NYSE/Nasdaq) does not. Overnight/weekend price gaps, stale oracle feeds, and thin weekend liquidity are documented risks of this structure.
- Stock tokens are already DeFi collateral (Morpho-powered lending, perp margin on Lighter). Liquidation is automatic, with no grace period.
- Always-on agents already manage positions around the clock, but the risk logic they follow lives off-chain with an operator: opaque, not composable, and a single key away from abuse.
- The missing infrastructure is a credibly neutral, synchronously composable risk parameter that any contract can read in the same transaction, with deterministic execution and public weights.

3. MVP scope

Four components. Nothing else ships.

# Component Description Done means
1 Teacher bake-off (off-chain) Train GBM, tuned MLP, and (time-boxed) TabPFN on identical features with a time split; select by tail metrics (pinball loss @90/95%, Brier for P(gap>5%), calibration error) Winner selected; comparison table in README
2 On-chain student (Stylus) Distill/quantize winner into a small int8 MLP (3–5K params, 4KB); forward pass implemented in Rust/Stylus; inputs are chain-native features only Deployed on target chain; per-inference gas measured; fidelity vs. teacher measured (see §5)
3 Policy contract (Solidity) Reads student score → risk multiplier → dynamic max-LTV/margin factor; gates borrow/withdraw/agent-session-key transactions; hard caps as un-gameable backstop; fail-closed on any uncertainty Demo flow passes: identical action allowed Tuesday, blocked/attenuated Saturday
4 Demo "Saturday morning" scenario: limits visibly tighten as gap risk rises; attack/score readout; README mapping each judging criterion to evidence Runnable end-to-end + recorded video fallback

Feature set (all chain-native or calendar-native — this is the load-bearing decision of the trust model):
time since last NYSE close, time to next open, holiday flag, on-chain realized volatility (from AMM swap history), Chainlink feed staleness and deviation vs. last close, asset class/beta bucket, position LTV, concentration.

Explicit non-goals for MVP

- ❌ Interactive dispute game (bisection, bonds, one-step arbitration) — secures attestations nobody posts at MVP scale
- ❌ ZK proof path — same object, same cut
- ❌ Semantic/policy layer (Laya) — introduces an input-oracle hole we cannot close this week
- ❌ Real lending-protocol integration (mock pool instead)
- ❌ GBM→if/else port benchmark (stretch only, if Day 3 finishes early)
- ❌ Multi-asset portfolio netting/cross-margining (per-token multiplier only)

Cut principle (applies to any new proposal): name what the component secures; if that thing is not in the system, the component does not go in.

4. Architecture sketch

```
Off-chain (build time)                On-chain (runtime)
─────────────────────────             ─────────────────────────────────
yfinance daily bars                   ┌──────────────────────────┐
  → feature engineering               │  Student contract (Stylus)│
  → teacher bake-off                  │  int8 MLP forward pass    │
  → distill + quantize int8           │  in: feature vector       │
  → weight export (Rust constants) ──→│  out: risk score (bps)    │
                                      └────────────┬─────────────┘
                                      Chain-native inputs:        │
                                      calendar, AMM vol,          ▼
                                      oracle staleness   ┌──────────────────────────┐
                                      (computed/read     │  Policy contract          │
                                       on-chain)      ──→│  score → max-LTV factor   │
                                                         │  gates borrow/withdraw/   │
                                                         │  session-key spends       │
                                                         │  hard caps, fail-closed   │
                                                         └────────────┬─────────────┘
                                                                      ▼
                                                         Demo lending pool (mock)
```

Deployment ladder (in order of preference): Robinhood Chain testnet (chain ID 46630) → Robinhood Chain mainnet (chain ID 4663, permissionless deployment, cheap — arguably the stronger submission) → Arbitrum Sepolia (still satisfies "deployed on an Arbitrum chain," loses the Robinhood podium angle).

5. Success criteria (measurable)

1. Student deployed and callable on the target chain before submission; contract address in README.
2. Student–teacher fidelity: worst-case output deviation ≤ agreed threshold (proposed: ≤ 200 bps on tail probability across the evaluation grid; threshold itself is an open question, §7) — measured adversarially near decision boundaries, not just on the test set.
3. Calibration: ECE reported on held-out data after temperature fit; documented, not necessarily "good."
4. Per-inference gas measured and within one Robinhood Chain block limit (limit unknown — verify Day 0).
5. Demo passes the Tuesday/Saturday contrast test end-to-end.
6. README maps all four judging criteria (smart contract quality, PMF, innovation, real problem-solving) to concrete evidence: tests, fuzz/invariant results, gas table, fidelity table.

6. Roadmap (post-hackathon — one slide, sequenced by prize-milestone logic)

Prizes pay 50% against milestones, so the roadmap is written as milestone candidates:

Phase Content Depends on
M1 Mainnet deployment, monitoring/alerting, model-registry with pinned weight-hash + timelocked updates MVP
M2 Live Chainlink Data Feeds/Streams integration (replace mocks); first external consumer (test Morpho-style vault or agent wallet reading the feed) M1, feed availability (§7)
M3 Bonded attestation layer for teacher-grade scores (off-chain heavy model posts scores with bond; on-chain student as watchdog, disagreement > τ → flag/pause) M1
M4 Deterministic dispute game: bisection over layers/trees, one-step arbitration executed in Stylus, slashing; verdict computed, not voted M3
M5 Governance: multisig + timelock for model updates, kill switch policy, recalibration cadence M1
M6 (stretch) ZK verifier slot in the update interface (proof-agnostic updates: attestation or proof); Laya semantic layer for natural-language mandate checks (input-oracle problem must be addressed first) M3/M4

7. Open questions

Organized by domain. (V) = verify on Day 0, (D) = needs a decision, (R) = research needed.

7.1 Product & market
1. (D) Is a risk-parameter feed a sufficient product for the jury, or do we need the mock pool to look like a "real" lending market? (Current decision: mock pool, feed is the product.)
2. (R) Does anything similar already exist on Robinhood Chain (risk oracles, volatility feeds)? Collision check owed before naming/branding freezes.
3. (D) Business model honesty: public good vs. operator-fee reading contract? Roadmap slide should pick one; affects M2 pitch.
4. (R) Who is the named first integrator archetype — Morpho-style vault, perp venue, or agent session-key guard? Demo narrative depends on this.

7.2 Data & model
5. (V) Which stock tokens actually exist on Robinhood Chain testnet/mainnet, with what symbols/decimals? Teacher universe must match demoable tokens.
6. (D) Label definition: P(|gap| > 5%)? Expected shortfall bucket? Quantile level? — Day 1 first decision; everything downstream consumes it.
7. (R) Corporate actions/splits/dividends in 10y training data — adjustment methodology, or restricted universe of clean names?
8. (R) Trading calendar source for holidays/early closes through 2026 (NYSE calendar library vs. manual table).
9. (D) On-chain realized volatility: computed how, at what cost? (Ring buffer of swap prices in the student? A separate volatility oracle contract reading a Uniswap TWAP? Gas and manipulation implications differ.)
10. (D) Score update cadence: computed fresh per transaction (expensive) vs. cached with a permissionless `poke()` (stale up to X minutes)? Affects interface and gas.
11. (D) Cold-start rule for newly listed tokens with no history: fixed conservative multiplier? Needs a constant in the policy contract.
12. (D) Student fidelity acceptance threshold (§5.2) — number must be fixed before distillation, else we tune to taste.
13. (R) Quantization error budget: int8 per-tensor vs. per-channel; int32 accumulator overflow bounds given feature ranges.
14. (R) Does the bake-off include a time-series model over raw return windows (N-BEATS/PatchTST)? Parked — but changes the input contract if revived; do not revive this week.

7.3 Chain & contracts
15. (V) Robinhood Chain block gas limit and per-tx limit (mainnet 4663 / testnet 46630) — sizes the student.
16. (V) Is Stylus enabled and stable on Robinhood Chain mainnet (verified on testnet by a prior project; mainnet unconfirmed)?
17. (V) Testnet RPC/faucet reliability; do we need to request funds in advance?
18. (V) Chainlink feed availability per token on testnet vs. mainnet; do we mock feeds everywhere (official example repo ships mock feeds)?
19. (D) Contract boundary: one Stylus contract exposing `score(features) → bps`, or split volatility computation into its own contract? (Single is simpler; split is more composable.)
20. (D) Upgradeability: redeploy + registry pointer vs. proxy? (Redeploy+registry is more honest for public-weights claims.)
21. (D) Stylus→Solidity fallback trigger: hard deadline end of Day 2 — who decides, by what signal (successful `cargo stylus deploy` on testnet)?
22. (R) WASM contracts cannot be source-verified on explorers — how do we prove deployed bytecode = published source? (Reproducible-build instructions + hash? Document in README.)
23. (R) Fixed-point conventions: bps vs. 18-decimals across the Stylus↔Solidity boundary; rounding direction must be conservative (round toward higher risk).

7.4 Trust & security
24. (R) Input manipulation is the primary attack vector: AMM-volatility and oracle-deviation features can be gamed (wash trades spike "volatility" → attacker tightens/loosens limits for others, or smooths their own). Needs: input sanity bounds, TWAP windows, documented threat model. Highest-priority security item.
25. (R) White-box model: public weights let adversaries search the feature space for blind spots — mitigation is hard caps + fail-closed + asymmetric loss; residual risk must be written down honestly in the README.
26. (D) Kill switch: who can pause the policy contract in an emergency, under what timelock? (Too fast = centralization critique; too slow = useless.)
27. (D) Miscalibration incident policy: if the model is discovered to be miscalibrated in production, what is the recalibration/update path, and who can trigger it?
28. (R) Economic exploit walkthrough: "manipulate inputs → borrow against inflated limit → walk away on Monday gap" — must be table-topped before finalizing policy math.

7.5 Demo & submission
29. (V) Time-travel problem: the demo needs "Saturday" on a live testnet. Options: inject timestamp as an explicit feature input (demo mode) vs. local fork. Decision affects contract interface (feature passed in vs. read from block time).
30. (V) HackQuest submission format: repo link? video length? contract addresses? team page? Deadline timezone. (HackQuest page could not be fully retrieved; assign someone to extract requirements Day 0.)
31. (D) Live demo vs. recorded video as primary; environment assumptions for judges (do they run anything, or watch?).
32. (R) Do we present in English (submission) with the German pitch as team-internal material? Presumably yes — confirm no language requirement.
33. (V) Eligibility: new-project-only rules? Our repo starts clean either way, but confirm.
8. Risk register

# Risk Likelihood Impact Mitigation / pre-declared cut line
R1 Stylus deploy snags on young chain (activation, RPC, gas estimation) Medium High Solidity implementation of identical model (fine at this size); hard trigger end of Day 2
R2 Data plumbing overruns Day 1 (corporate actions, calendar, gaps labeling) Medium Medium Fallback: hand-specified scoring function feeds the same pipeline; ML story weakened, mechanism intact
R3 Teacher bake-off expands (TabPFN integration fights) Medium Low 2-hour box on TabPFN; table ships with two rows if dropped
R4 Model is thin / judges ask "is the ML real?" Medium Medium Publish bake-off table + fidelity metrics + calibration; honesty beats hype
R5 Input-manipulation attack found late (§7.24) Medium High Threat-model session before policy math frozen; input bounds + TWAP windows are MVP-scope, not roadmap
R6 Demo time-travel (§7.29) unresolved High if unaddressed Medium Day 0 decision; demo-mode feature input is the cheap escape
R7 Testnet instability / faucet issues Medium Medium Deployment ladder (§4); mainnet deploy is a legitimate upgrade, not just fallback
R8 Scope creep — someone re-adds the dispute game or ZK mid-week High (it was fun) High Cut principle (§3) + this document; roadmap is one slide, no code
R9 Idea collision with another team / prior-edition entries (a Stylus risk engine ran in London) Medium Medium Gap-risk-for-24/7-equities wedge is distinct; say so explicitly in README
R10 Quantization/int8 overflow bug produces nonsense scores on-chain Low High Property tests on feature-range bounds; invariant tests on score ∈ [0, 1]; conservative rounding
R11 Milestone-dependent prize (50% post-hackathon) mis-set expectations — Low Roadmap written as milestone candidates; team commits to M1 minimum before claiming victory
R12 Regulatory optics ("are you giving financial advice?") Low Low Frame as infrastructure parameter feed; no portfolio recommendations anywhere in materials
R13 HackQuest submission format surprise (§7.30) Unknown Medium Day 0 assignment; submit 24h early if format allows

9. Timeline (Day 0 = today, submission Oct 4)

Day Workstream A (model) Workstream B (contracts) Workstream C (demo/submission)
D0 Verify §7 items marked (V); label definition decision (§7.6); data pull Repo scaffold; toolchain check; `cargo stylus` hello-world on testnet Extract HackQuest requirements; demo time-travel decision (§7.29)
D1 Feature pipeline; teacher bake-off (all three) Contract skeletons: student interface, policy, mock pool README skeleton mapped to judging criteria
D2 Distill + quantize; fidelity vs. threshold (§5.2) Stylus deploy trigger point (fallback decision); policy math frozen after threat-model session (R5) Demo scenario scripted
D3 Calibration refit; README numbers Integration end-to-end; gas measurement; invariant tests Web UI or scripted demo + video
D4 Buffer Buffer Record video; final README; submit early

10. Decision log (do not re-litigate this week)

Decision Rationale
No off-chain operator in the critical path; no attestations Makes security intrinsic (deterministic execution, public weights) instead of procedural (bonds, games, provers); removes the need for every component we cut
Chain-native features only Closes the input-oracle hole; the one thing that makes "trustless" claimable
Teacher chosen by bake-off on tail metrics, not by fashion Neural operators are a category error here; rigor reads better than buzzwords to this jury
Student is an int8 MLP regardless of teacher On-chain artifact is neural either way; deployment constraint fixes the architecture
Fail-closed + hard caps always on A fooled model must never be profitable on its own (white-box reality)
Dispute game / ZK / semantic layer → roadmap only They secure off-chain actors that do not exist at MVP scale
Mock lending pool, not a fork of a real protocol Full control, zero integration risk; the feed is the product
Robinhood Chain first (testnet → mainnet ladder) Reserved podium spot; ecosystem's documented pain point; Chainlink partnership narrative

11. Inputs for interface/spec writing

These are the seams the spec must pin down first — each becomes a spec section. Draft shapes only, to be finalized:

1. Feature vector encoding — `struct Features { uint32 secsSinceClose; uint32 secsToOpen; uint16 realizedVolBps; uint16 oracleDeviationBps; uint16 stalenessSecs; uint8 assetClass; uint16 ltvBps; uint16 concentrationBps; }` — exact types, scaling, and who computes each field (§7.9, §7.10, §7.29 are blockers).
2. Student interface — `score(Features) → uint16 riskBps`; view-only; gas ceiling assertion in tests.
3. Policy interface — `maxLtv(token, position) → uint16`; mapping `riskBps → factor` (linear clamp vs. step function — decision owed); hard-cap constants; cold-start constant (§7.11).
4. Registry/update interface — `currentModel() → (address, bytes32 weightsHash)`; timelocked `propose/activate`; events. Proof-agnostic update slot left documented-but-unimplemented for M3/M6.
5. Demo-mode flag — explicit feature-override input path (§7.29) that is provably disabled outside demo deployment.
6. Events & monitoring — `ScoreComputed`, `LimitChanged`, `CapHit`, `ModelUpdated`; enough for the demo UI and future watchtowers to consume.
Prepared 2026-09-29. All ecosystem facts as of that date; re-verify time-sensitive items (chain limits, feed availability, submission rules) before relying on them.

# Deployments — network reference

Normative source: `DESIGN.md` §2.1–2.2. Time-sensitive items are re-verified on D0.

## Networks

| | Robinhood Chain mainnet | Robinhood Chain testnet |
|---|---|---|
| Chain ID | **4663** (`0x1237`) | **46630** |
| RPC | `https://rpc.mainnet.chain.robinhood.com` | `https://rpc.testnet.chain.robinhood.com` |
| Explorer | robinhoodchain.blockscout.com | explorer.testnet.chain.robinhood.com |
| Gas token | ETH (18 dec) | ETH (18 dec) |
| Deployment | permissionless | permissionless |

## Faucets (testnet)

- Official: faucet.testnet.chain.robinhood.com — **0.01 ETH + 5 of each test Stock
  Token per 24h**.
- Backups: Alchemy (0.1 ETH/24h), QuickNode (12h cadence), Chainstack (1 ETH/24h).
- No advance request needed.

## Known chain facts

| Fact | Value | Status |
|---|---|---|
| Effective per-block gas cap | 32M gas (Arbitrum default; sustained ~40M gas/s observed) | **(verify D0)** — no Robinhood-specific value published; probe per-tx cap via gas estimation on both networks |
| Max contract size | 96 KB code / 192 KB initcode | confirmed |
| `ArbWasm` precompile | `0x0000000000000000000000000000000000000071` | confirmed |
| `ArbSys` precompile | `0x0000000000000000000000000000000000000064` | confirmed |
| `block.number` | returns an **L1 block estimate**; use `ArbSys(0x64).arbBlockNumber()` for L2 height (we use timestamps everywhere, so unaffected) | confirmed |
| Stylus on testnet | enabled; `ArbWasm.stylusVersion()` = 3 on chain 46630 | confirmed |
| Stylus on mainnet | Stylus-capable Nitro build, no confirmed deployment | **(verify D0)**: call `ArbWasm(0x71).stylusVersion()` on 4663 |
| Testnet cache manager | **none** (no ArbOS cache manager) → uncached Stylus call-init every call; our gas numbers are worst-case | confirmed |
| Stylus program expiry | programs expire **~365 days** without keepalive (`ArbWasm.codehashKeepalive`) — post-hackathon concern (roadmap M1) | confirmed |
| Sequencer screening | sanctioned-address transactions excluded at the sequencer | confirmed — noted in the threat model, not a design dependency |
| Chainlink feeds | mainnet only (Data Feeds + Streams + CCIP); 24/5 (sleep on weekends); `oraclePaused()` during corporate actions; USD feeds 8 dec; **no ETH/USD feed**. Testnet → mock AggregatorV3-compatible feeds | confirmed |

## Testnet stock token addresses (community sources — **verify D0** on explorer)

ERC-20, 18 decimals.

| Token | Address |
|---|---|
| TSLA | `0xC9f9c86933092BbbfFF3CCb4b105A4A94bf3Bd4E` |
| AMZN | `0x5884aD2f920c162CFBbACc88C9C51AA75eC09E02` |
| NFLX | `0x3b8262A63d25f0477c4DDE23F83cfe22Cb768C93` |
| PLTR | `0x1FBE1a0e43594b3455993B5dE5Fd0A7A266298d0` |
| AMD | `0x71178BAc73cBeb415514eB542a8995b82669778d` |
| USDC (6 dec) | `0xAc80194dc1aE8eF52df73e7e1864fB3C62290fe0` |

## Mainnet Chainlink feeds (USD, 8 decimals)

| Pair | Address |
|---|---|
| TSLA/USD | `0x4A1166a659A55625345e9515b32adECea5547C38` |
| NVDA/USD | `0x379EC4f7C378F34a1B47E4F3cbeBCbAC3E8E9F15` |
| AAPL/USD | `0x6B22A786bAa607d76728168703a39Ea9C99f2cD0` |

## MockChainlinkFeed (testnet) — behavior contract

- **AggregatorV3-compatible:** `latestRoundData()`, 8 decimals, plus
  `oraclePaused()`.
- **Owner-gated `pushRound(int256 answer)`** — sets `updatedAt = block.timestamp`.
  Deployer/demo script only; no keeper.
- **The 24/5 freeze is NOT simulated in-contract** — it emerges because nothing is
  pushed during a staged weekend.
- **Owner-gated `setPaused(bool)`**, default false — for demonstrating fail-closed
  #3 (paused reference feed → `maxLtv = 0`).

## GapGuard deployments

| Contract | Network | Address | Deployment tx | Notes |
|---|---|---|---|---|
| GapRiskModel (student, Stylus) | testnet 46630 | TBD | TBD | `cargo stylus verify --deployment-tx` instructions in README |
| VolatilityOracle | testnet 46630 | TBD | TBD | |
| RiskPolicy (production, `demoMode=false`) | testnet 46630 | TBD | TBD | |
| RiskPolicy (demo, `demoMode=true`) | testnet 46630 | TBD | TBD | demo-only; `setDemoNow` enabled |
| ModelRegistry | testnet 46630 | TBD | TBD | |
| GapGuardPool (mock) | testnet 46630 | TBD | TBD | mock — the feed is the product |
| MockChainlinkFeed | testnet 46630 | TBD | TBD | AggregatorV3-compatible |
| (stretch) full stack | mainnet 4663 | TBD | TBD | cut in the v1.1 re-plan — testnet submission is complete |

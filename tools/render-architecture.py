#!/usr/bin/env python3
"""Draw the GapGuard architecture diagram as a native vector graphic.

Outputs docs/architecture.svg (master) and docs/architecture.png.
Pure matplotlib — no external tools required:

    python3 tools/render-architecture.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parent.parent
SVG_OUT = ROOT / "docs" / "architecture.svg"
PNG_OUT = ROOT / "docs" / "architecture.png"

MONO = "DejaVu Sans Mono"

fig, ax = plt.subplots(figsize=(16, 10))
ax.set_xlim(0, 100)
ax.set_ylim(0, 62)
ax.axis("off")


def panel(x, y, w, h, title, color):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4",
                                facecolor=color, edgecolor="#bbbbbb", linewidth=1))
    ax.text(x + w / 2, y + h - 1.6, title, ha="center", va="center",
            fontsize=12, fontweight="bold", color="#333333")


def box(x, y, w, h, title, lines, edge="#555555", lw=1.4, face="white"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25",
                                facecolor=face, edgecolor=edge, linewidth=lw))
    n = len(lines)
    if n:
        ax.text(x + w / 2, y + h - 1.7, title, ha="center", va="center",
                fontsize=10, fontweight="bold", family=MONO)
        for i, line in enumerate(lines):
            ax.text(x + w / 2, y + h - 3.6 - i * 2.0, line, ha="center",
                    va="center", fontsize=8.5, family=MONO, color="#222222")
    else:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center",
                fontsize=9.5, family=MONO)


def arrow(x0, y0, x1, y1, label=None, rad=0.0, lx=None, ly=None):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>",
                                 mutation_scale=15, linewidth=1.5,
                                 color="#444444",
                                 connectionstyle=f"arc3,rad={rad}"))
    if label:
        ax.text(lx if lx is not None else (x0 + x1) / 2,
                ly if ly is not None else (y0 + y1) / 2 + 1.2,
                label, ha="center", va="center", fontsize=8, family=MONO,
                color="#333333",
                bbox=dict(facecolor="white", edgecolor="none", pad=1.2))


# ── lanes ────────────────────────────────────────────────────────────────
panel(2, 2, 28, 58, "Off-chain — Lane A (build time)", "#f5f5f5")
panel(33, 2, 65, 58, "On-chain — Lane B (runtime)", "#eef4fb")

ax.plot([31.5, 31.5], [3, 59], linestyle=(0, (4, 4)), color="#999999", linewidth=1)
ax.text(31.2, 51.5, "trust boundary", rotation=90, ha="center", va="center",
        fontsize=8, color="#777777", family=MONO,
        bbox=dict(facecolor="white", edgecolor="none", pad=1.2))

# ── left lane: model pipeline ────────────────────────────────────────────
box(5, 49, 22, 5.5, "yfinance raw bars + actions", [], edge="#888888")
box(5, 41, 22, 5.5, "clean / adjust, drop CA gaps", [], edge="#888888")
box(5, 33, 22, 5.5, "features via exchange_calendars", [], edge="#888888")
box(5, 25, 22, 5.5, "teacher bake-off (LGBM/MLP/TabPFN)", [], edge="#888888")
box(5, 17, 22, 5.5, "distill → per-channel int8 quantize", [], edge="#888888")
box(5, 5, 22, 9, "build artifacts",
    ["student_export.json", "golden_vectors.json", "calendar_table.json"],
    edge="#888888")

for y0, y1 in [(49, 46.9), (41, 38.9), (33, 30.9), (25, 22.9), (17, 14.4)]:
    arrow(16, y0, 16, y1)

# ── right lane: contracts ────────────────────────────────────────────────
box(36, 40, 24, 12, "GapRiskModel (Stylus/WASM)",
    ["int8 MLP, pure function", "score(Features) → riskBps", "weightsHash() → bytes32"],
    edge="#1f6feb", lw=2.2)
box(66, 30, 28, 18, "RiskPolicy (Solidity)",
    ["NyseCalendar library", "score → maxLtv factor", "hard caps · fail-closed",
     "pause / 48h unpause", "demoMode immutable"],
    edge="#2da44e", lw=1.8)
box(36, 24, 24, 10, "ModelRegistry",
    ["propose / activate", "24h timelock"])
box(66, 16, 28, 11, "VolatilityOracle",
    ["ring buffer ×32", "poke(token) ≥ 1h", "±10% jump bound"])
box(66, 4, 28, 9, "MockChainlinkFeed (testnet)",
    ["AggregatorV3-compatible"])
box(36, 4, 24, 12, "GapGuardPool (mock)",
    ["Morpho-style isolated vault", "borrow / withdraw gated", "by policy.maxLtvBps"])

# ── cross-lane and on-chain wiring ───────────────────────────────────────
ax.text(16, 3.9, "baked into contracts at deploy", ha="center", va="center",
        fontsize=7, family=MONO, color="#777777")
ax.text(16, 2.7, "pinned by weightsHash · CI vs golden vectors", ha="center",
        va="center", fontsize=7, family=MONO, color="#777777")
arrow(27.3, 10, 35.6, 45, rad=-0.25)
arrow(66, 44, 60.4, 46, label="score() view call", lx=63, ly=48.5)
arrow(60.4, 30, 66, 36, label="currentModel()", lx=63, ly=31)
arrow(80, 27.3, 80, 30, label="realizedVolBps · isStale", lx=80, ly=28.7)
arrow(80, 13.3, 80, 16, label="reads", lx=80, ly=14.7)
arrow(70, 29.6, 56, 16.3, rad=0.25)

fig.savefig(SVG_OUT, bbox_inches="tight")
fig.savefig(PNG_OUT, dpi=200, bbox_inches="tight")
print(f"wrote {SVG_OUT}")
print(f"wrote {PNG_OUT}")

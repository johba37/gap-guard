#!/usr/bin/env python3
"""Render the README architecture diagram to SVG (master) and PNG.

The ASCII block is extracted from README.md, so the README text stays the
single source of truth. Every non-space character is pinned to an absolute
grid cell in the SVG, which makes alignment exact by construction — no
reliance on font advance widths in any renderer.

Usage:
    python3 tools/render-architecture.py            # writes docs/architecture.svg
    /tmp/svgenv/bin/python tools/render-architecture.py --png   # + docs/architecture.png
PNG rasterization needs cairosvg (e.g. a venv with `pip install cairosvg`).
"""
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
SVG_OUT = ROOT / "docs" / "architecture.svg"
PNG_OUT = ROOT / "docs" / "architecture.png"

FONT_SIZE = 16
CELL_W = 9.64   # DejaVu Sans Mono advance at 16px (0.6025 em)
CELL_H = 20     # line height
BASELINE = 15   # baseline offset within a cell
PAD = 16


def extract_block() -> list[str]:
    text = README.read_text()
    block = re.search(r"## Architecture\s+```\n(.*?)```", text, re.S).group(1)
    return block.rstrip("\n").split("\n")


def build_svg(lines: list[str]) -> str:
    cols = max(len(line) for line in lines)
    w = cols * CELL_W + 2 * PAD
    h = len(lines) * CELL_H + 2 * PAD
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}"',
        f' width="{w:.0f}" height="{h:.0f}" font-family="DejaVu Sans Mono, monospace"',
        f' font-size="{FONT_SIZE}">',
        f'<rect width="{w:.0f}" height="{h:.0f}" fill="white"/>',
        '<g fill="black">',
    ]
    for row, line in enumerate(lines):
        y = PAD + row * CELL_H + BASELINE
        for col, chv in enumerate(line):
            if chv != " ":
                x = PAD + col * CELL_W
                parts.append(f'<text x="{x:.2f}" y="{y:.2f}">{escape(chv)}</text>')
    parts.append("</g></svg>")
    return "\n".join(parts)


def main() -> None:
    lines = extract_block()
    SVG_OUT.write_text(build_svg(lines))
    print(f"wrote {SVG_OUT}")
    if "--png" in sys.argv:
        import cairosvg

        cairosvg.svg2png(url=str(SVG_OUT), write_to=str(PNG_OUT), scale=3.0)
        print(f"wrote {PNG_OUT}")


if __name__ == "__main__":
    main()

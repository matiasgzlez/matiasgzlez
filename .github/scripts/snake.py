#!/usr/bin/env python3
"""
Generate a growing-snake SVG animation from GitHub contribution data.
The snake grows from MIN_L to MAX_L segments as it eats contributions.
"""

import json
import os
import urllib.request

USER  = os.environ.get("GITHUB_USER",  "matiasgzlez")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

CELL  = 11    # cell size in px
GAP   = 2     # gap between cells in px
STEP  = CELL + GAP
ROWS  = 7
MIN_L = 3     # starting snake length
MAX_L = 12    # maximum snake length
SPD   = 80    # milliseconds per animation step


def fetch_grid():
    q = (
        "query($l:String!){user(login:$l){contributionsCollection{"
        "contributionCalendar{weeks{contributionDays{contributionCount color}}}}}}"
    )
    body = json.dumps({"query": q, "variables": {"l": USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as r:
        raw = json.loads(r.read())
    grid = []
    for wk in raw["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
        col = [(d["contributionCount"], d["color"]) for d in wk["contributionDays"]]
        while len(col) < ROWS:
            col.append((0, "#ebedf0"))
        grid.append(col)
    return grid


def make_path(ncols):
    """Zigzag: even cols top→bottom, odd cols bottom→top."""
    path = []
    for c in range(ncols):
        rs = range(ROWS) if c % 2 == 0 else range(ROWS - 1, -1, -1)
        for r in rs:
            path.append((c, r))
    return path


def make_lengths(path, grid):
    """
    Snake length at each step.
    Grows from MIN_L to MAX_L proportionally to contributions eaten.
    Appends MAX_L * extra steps so the tail clears the grid before the loop resets.
    """
    total = sum(1 for c, r in path if grid[c][r][0] > 0)
    eaten = 0
    lengths = []
    n = len(path)
    for c, r in path:
        if grid[c][r][0] > 0:
            eaten += 1
        ratio = (eaten / total) if total else (len(lengths) / max(n - 1, 1))
        lengths.append(min(MIN_L + round(ratio * (MAX_L - MIN_L)), MAX_L))
    return lengths + [MAX_L] * MAX_L  # tail-clearing phase


def find_interval(i, lengths):
    """(t_enter, t_leave) — step when head arrives and when tail departs cell i."""
    for t in range(i, len(lengths)):
        if t - lengths[t] + 1 > i:
            return i, t
    return i, len(lengths)


THEMES = {
    "light": {"bg": "#ffffff", "empty": "#ebedf0", "head": "#26c441", "body": "#2ea043"},
    "dark":  {"bg": "#0d1117", "empty": "#161b22", "head": "#39d353", "body": "#26a641"},
}


def build_svg(grid, theme="light"):
    col = THEMES[theme]
    path = make_path(len(grid))
    n    = len(path)
    lens = make_lengths(path, grid)
    TS   = n + MAX_L                   # total animation steps (including clearing phase)
    dur  = round(TS * SPD / 1000, 3)  # seconds

    W = len(grid) * STEP + 2
    H = ROWS * STEP + 2

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="{col["bg"]}"/>',
    ]

    for i, (cx, row) in enumerate(path):
        x = cx * STEP + 1
        y = row * STEP + 1
        cnt, hex_c = grid[cx][row]
        base = hex_c if cnt else col["empty"]

        te, tl = find_interval(i, lens)

        # Keyframes: dict keyed by step → color.
        # Duplicate steps resolve to last assignment (intentional for te=0).
        kf = {
            0:  base,        # original cell color at loop start
            te: col["head"], # head arrives (overwrites base when te=0)
            tl: col["empty"],  # snake leaves, contribution eaten
            TS: col["empty"],  # hold until loop resets (ensures keyTimes ends at 1.0)
        }
        if te + 1 < tl:
            kf[te + 1] = col["body"]  # cell becomes body segment

        clean = sorted(kf.items())  # [(step, color), ...]

        kt = ";".join(f"{s / TS:.5f}" for s, _ in clean)
        vs = ";".join(c for _, c in clean)

        parts.append(
            f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{base}">'
            f'<animate attributeName="fill" values="{vs}" keyTimes="{kt}" '
            f'dur="{dur}s" repeatCount="indefinite" calcMode="discrete"/>'
            f'</rect>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def main():
    os.makedirs("dist", exist_ok=True)
    print(f"Fetching contributions for {USER} …")
    grid = fetch_grid()
    print(f"  {len(grid)} weeks of data")
    for theme, fn in [
        ("light", "dist/github-contribution-grid-snake.svg"),
        ("dark",  "dist/github-contribution-grid-snake-dark.svg"),
    ]:
        svg = build_svg(grid, theme)
        with open(fn, "w") as f:
            f.write(svg)
        print(f"  Saved {fn} ({len(svg):,} bytes)")


if __name__ == "__main__":
    main()

"""Generate ShellShelf PWA icons with the standard library only.

Writes `static/icons/icon-{192,512}.png`, `apple-touch-icon.png (180)` and
`icon.svg`. No third-party packages; safe to re-run offline.

Design: dark rounded square (#1a2129), accent ring (#4da3ff), `$` prompt glyph
from a tiny inline 5x7 bitmap plus a block cursor — matching `packaging/icon.svg`.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "static" / "icons"

BG = (26, 33, 41)        # --panel #1a2129
ACCENT = (77, 163, 255)  # --accent #4da3ff
FG = (232, 238, 244)     # --text #e8eef4

# 5x7 bitmap for "$" (rows top→bottom, "#" = on).
GLYPH_DOLLAR = [
    "..#..",
    ".####",
    "#.#..",
    ".###.",
    "..#.#",
    "####.",
    "..#..",
]


def _crc(chunk_type: bytes, data: bytes) -> bytes:
    return struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)


def _chunk(chunk_type: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + chunk_type + data + _crc(chunk_type, data)


def write_png(path: Path, size: int) -> None:
    scale = max(1, size // 16)
    gw, gh = 5 * scale, 7 * scale
    cursor_w, cursor_h = 3 * scale, 1 * scale
    gap = 2 * scale
    total_w = gw + gap + cursor_w
    ox = (size - total_w) // 2
    oy = (size - gh) // 2
    ring = max(2, size // 48)
    radius = size // 8

    px = bytearray(size * size * 3)
    for y in range(size):
        for x in range(size):
            # Rounded-square mask: outside corners stay background-dark too, so
            # just compute ring vs fill for a rounded rect.
            dx = min(x, size - 1 - x)
            dy = min(y, size - 1 - y)
            # Corner rounding: cut a quarter circle of `radius`.
            if dx < radius and dy < radius:
                cx, cy = radius - dx, radius - dy
                outside = cx * cx + cy * cy > radius * radius
            else:
                outside = False
            if outside:
                color = BG  # transparent corners would need alpha; keep flat bg
            elif dx < ring or dy < ring:
                color = ACCENT
            else:
                color = BG
            # "$" glyph in light foreground (centered: never overlaps the ring).
            gx, gy = x - ox, y - oy
            if 0 <= gx < gw and 0 <= gy < gh:
                if GLYPH_DOLLAR[gy // scale][gx // scale] == "#":
                    color = FG
            # Block cursor "_" in accent, right of the glyph, bottom aligned.
            cx0 = ox + gw + gap
            if cx0 <= x < cx0 + cursor_w and oy + gh - cursor_h <= y < oy + gh:
                color = ACCENT
            i = (y * size + x) * 3
            px[i], px[i + 1], px[i + 2] = color

    raw = b"".join(b"\x00" + bytes(px[y * size * 3:(y + 1) * size * 3]) for y in range(size))
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    data = (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + _chunk(b"IEND", b""))
    path.write_bytes(data)
    print(f"Wrote {path} ({len(data)} bytes)")


SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect x="4" y="4" width="56" height="56" rx="12" fill="#1a2129"/>
  <rect x="4" y="4" width="56" height="56" rx="12" fill="none" stroke="#4da3ff" stroke-width="3"/>
  <text x="14" y="42" font-family="monospace" font-size="26" fill="#e8eef4">$</text>
  <text x="28" y="42" font-family="monospace" font-size="26" fill="#4da3ff">_</text>
</svg>
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write_png(OUT / "icon-192.png", 192)
    write_png(OUT / "icon-512.png", 512)
    write_png(OUT / "apple-touch-icon.png", 180)
    (OUT / "icon.svg").write_text(SVG, encoding="utf-8")
    print(f"Wrote {OUT / 'icon.svg'}")


if __name__ == "__main__":
    main()

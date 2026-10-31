"""Draws the Mac app's pictures as SVG (docs/macos-app.md, "The pictures"):

- AppIcon.icon: the app's icon from macOS 26 on, for Icon Composer and actool. The
  system draws the outline, the fill (white down to the page's ground) and the glass;
  the one layer is the caret, drawn flat: macOS lights it.
- AppIcon.svg: the same icon drawn on Apple's grid with its own light, for macOS 13 to 15.
- VolumeIcon.svg: the disk image's icon, the icon's card standing in a sleeve.
- dmg-background.svg: the disk image's window, 640 by 400 points.

    python3 packaging/macos/art.py

writes them beside itself, and the PNGs made from them are kept beside them too: the
icons with rsvg-convert, the window in a browser, which has the page's font.

The icon is one mark: the caret a proofreader writes where something goes in, in red on
white. It is what a sync does (the page writes the new value in after a caret) and the
mark before the name on the site; square-cut, as the page's marks are, with a sharp
apex. It replaced the e-reader with the two-way sync (0.18.0 to 0.20.0), five things on
one tile; the owner chose it from six directions.
"""

import math
import pathlib
import re

HERE = pathlib.Path(__file__).parent
FONT = "../../src/lastread/web/static/fonts/SchibstedGrotesk-latin.woff2"

# DESIGN.md's colours, light.
INK, GRAPHITE, GROUND = "#17191c", "#4a4f57", "#edefea"
BLUE = "#1c5e8b"
# The icon's own: the site's Name Caret red, and the tile from white down to near the ground.
RED = "#e8343f"
TILE_TOP, TILE_BOTTOM = "#ffffff", "#e9ebe6"
SLEEVE_TOP, SLEEVE_BOTTOM = "#46606f", "#1c2a33"

# The caret on the 1024 canvas, which is the tile itself (flat_icon scales it onto Apple's
# grid): its two feet and apex, and its stroke. A mitred apex and butt ends: square-cut.
# Its ink runs from y 282 (the mitre's point) to 746 (the outer corners of the feet),
# centred on the tile.
CARET = ((322, 720), (512, 400), (702, 720))
CARET_WIDTH = 112


def shadow(name, dy, blur, opacity, colour="#000"):
    return (
        f'<filter id="{name}" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="{dy}"'
        f' stdDeviation="{blur}" flood-color="{colour}" flood-opacity="{opacity}"/></filter>'
    )


def gradient(name, top, bottom):
    return (
        f'<linearGradient id="{name}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/>'
        f'<stop offset="1" stop-color="{bottom}"/></linearGradient>'
    )


def rounded(box, fill, extra=""):
    x, y, w, h, r = box
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}"{extra}/>'


def caret(points=CARET, width=CARET_WIDTH, colour=RED):
    (ax, ay), (bx, by), (cx, cy) = points
    return (
        f'<path d="M{ax} {ay} L{bx} {by} L{cx} {cy}" fill="none" stroke="{colour}"'
        f' stroke-width="{width}" stroke-linejoin="miter" stroke-miterlimit="10"/>'
    )


def svg(body, defs="", size=1024):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
        f"<defs>{defs}</defs>{body}</svg>\n"
    )


def squircle(x, y, s, n=5.0, steps=256):
    """Apple's icon outline, near enough: a superellipse filling the square at x, y."""
    r = s / 2
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        c, d = math.cos(t), math.sin(t)
        pts.append((x + r + r * math.copysign(abs(c) ** (2 / n), c), y + r + r * math.copysign(abs(d) ** (2 / n), d)))
    return "M" + " L".join(f"{a:.2f} {b:.2f}" for a, b in pts) + " Z"


def srgb(hex_colour):
    """A colour as Icon Composer writes it."""
    r, g, b = (int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return f"srgb:{r:.5f},{g:.5f},{b:.5f},1.00000"


def icon_composer():
    """The .icon bundle: the fill a gradient from white down to near the page's ground,
    the caret above it in glass."""
    folder = HERE / "AppIcon.icon"
    (folder / "Assets").mkdir(parents=True, exist_ok=True)
    (folder / "Assets" / "caret.svg").write_text(svg(caret()))
    (folder / "icon.json").write_text(
        f"""{{
  "fill" : {{
    "linear-gradient" : [
      "{srgb(TILE_BOTTOM)}",
      "{srgb(TILE_TOP)}"
    ],
    "orientation" : {{
      "start" : {{
        "x" : 0.5,
        "y" : 1
      }},
      "stop" : {{
        "x" : 0.5,
        "y" : 0
      }}
    }}
  }},
  "groups" : [
    {{
      "layers" : [
        {{
          "glass" : true,
          "image-name" : "caret.svg",
          "name" : "caret"
        }}
      ],
      "name" : "caret",
      "shadow" : {{
        "kind" : "layer-color",
        "opacity" : 0.5
      }},
      "specular" : true
    }}
  ],
  "supported-platforms" : {{
    "squares" : [
      "macOS"
    ]
  }}
}}
"""
    )


def flat_icon():
    """For macOS 13 to 15: the outline is drawn here, an 824 square with 100 around it,
    lit from above as macOS lights its icons, with a hairline so that white stays a tile
    on a white window."""
    shape = squircle(100, 100, 824)
    defs = f'<clipPath id="tile"><path d="{shape}"/></clipPath>' + shadow("lift", 10, 10, 0.28) + gradient("ground", TILE_TOP, TILE_BOTTOM)
    body = (
        f'<g filter="url(#lift)"><path d="{shape}" fill="url(#ground)"/></g>'
        f'<path d="{shape}" fill="none" stroke="{INK}" stroke-opacity="0.08" stroke-width="4"/>'
        f'<g clip-path="url(#tile)"><g transform="translate(100 100) scale({824 / 1024})">{caret()}</g></g>'
    )
    return svg(body, defs)


def volume_icon():
    """The icon's card standing half out of a slate cloth sleeve, so the disk and the app
    tell apart on the desktop; the caret above the sleeve's edge."""
    defs = shadow("drop", 16, 16, 0.32) + shadow("stand", 10, 12, 0.30, "#06111a") + gradient("card", TILE_TOP, TILE_BOTTOM)
    body = (
        f'<g filter="url(#stand)">{rounded((262, 96, 500, 640, 44), "url(#card)")}</g>'
        + caret(((404, 440), (512, 256), (620, 440)), 70)
        + '<g filter="url(#drop)">'
        '<rect x="150" y="492" width="724" height="500" rx="48" fill="url(#sleeve)"/>'  # the sleeve
        '<rect x="150" y="492" width="724" height="34" rx="17" fill="#5a7383"/>'  # its hem, catching the light
        "</g>"
    )
    return svg(body, defs + gradient("sleeve", SLEEVE_TOP, SLEEVE_BOTTOM))


def move_mark():
    """The proofreader's mark that moves a thing: a loop round it, drawn as a hand would,
    a little uneven and left open, and a line from it to where it goes. Round the app at
    170, 218 (with its name under it), to Applications at 470, 200."""
    cx, cy, rx, ry = 170, 218, 94, 116
    pts = []
    for i in range(0, 309, 7):  # from below the right, round the bottom, the left and the top
        t = math.radians(28 + i)
        wobble = 1 + 0.018 * math.sin(2 * t + 0.9) + 0.008 * math.sin(5 * t)
        pts.append((cx + rx * wobble * math.cos(t), cy + ry * wobble * math.sin(t)))
    d = f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"
    for i in range(1, len(pts)):  # through every point, smoothly (Catmull-Rom as cubic Béziers)
        a, b = pts[i - 1], pts[i]
        z, c = pts[max(i - 2, 0)], pts[min(i + 1, len(pts) - 1)]
        d += (
            f" C{a[0] + (b[0] - z[0]) / 6:.1f} {a[1] + (b[1] - z[1]) / 6:.1f}"
            f" {b[0] - (c[0] - a[0]) / 6:.1f} {b[1] - (c[1] - a[1]) / 6:.1f} {b[0]:.1f} {b[1]:.1f}"
        )
    ex, ey = pts[-1]
    d += f" C{ex + 22:.1f} {ey + 36:.1f} 318 200 392 200"
    return (
        f'<g fill="none" stroke="{BLUE}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="{d}"/><path d="M378 189 L394 200 L377 210"/></g>'
    )


def window(icon):
    """The disk's window: the app icon printed in non-repro blue, the blue a camera does not
    see, so that it stays behind Finder's icons and names; one sentence; the move mark."""
    icon = re.sub(
        r"<svg [^>]*>", '<svg x="80" y="-6" width="480" height="480" viewBox="0 0 1024 1024" filter="url(#nonrepro)">', icon, count=1
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 400" width="640" height="400">
<defs>
<style>
@font-face {{ font-family: "Schibsted Grotesk"; src: url("{FONT}") format("woff2"); font-weight: 400 900; }}
text {{ font-family: "Schibsted Grotesk"; }}
</style>
<filter id="nonrepro" color-interpolation-filters="sRGB">
<feColorMatrix type="saturate" values="0"/>
<feComponentTransfer>
<feFuncR type="table" tableValues="0.78 0.962"/><feFuncG type="table" tableValues="0.875 0.977"/><feFuncB type="table" tableValues="0.91 0.983"/>
</feComponentTransfer>
</filter>
</defs>
<rect width="640" height="400" fill="{GROUND}"/>
{icon}<text x="320" y="54" text-anchor="middle" font-size="19" font-weight="750" letter-spacing="-0.25" fill="{INK}">Drag Lastread onto Applications.</text>
{move_mark()}
<text x="320" y="380" text-anchor="middle" font-size="11.5" fill="{GRAPHITE}">Independent: not affiliated with Rakuten Kobo or Hardcover.</text>
</svg>
"""


def small_icon(size):
    """The flat icon at 16 and 32 pixels, drawn on their own pixel grid rather than shrunk:
    the tile, its hairline and the caret with its feet on a pixel row."""
    if size == 32:
        tile = squircle(3, 3, 26, steps=128)
        mark = caret(((10, 22.5), (16, 12.5), (22, 22.5)), 3.5)
    else:
        tile = squircle(1, 1, 14, steps=96)
        mark = caret(((5, 11.5), (8, 6.5), (11, 11.5)), 2)
    return svg(
        f'<path d="{tile}" fill="url(#ground)"/><path d="{tile}" fill="none" stroke="{INK}" stroke-opacity="0.18" stroke-width="1"/>{mark}',
        gradient("ground", TILE_TOP, TILE_BOTTOM),
        size,
    )


def small_volume(size):
    """The disk's icon at 16 and 32 pixels: the card standing out of its sleeve, square
    to the grid, with the caret above the sleeve's edge."""
    if size == 32:
        card, sleeve = (9, 2, 14, 20, 2), (4, 14, 24, 16, 2)
        mark = caret(((12.5, 12), (16, 6.5), (19.5, 12)), 2.2)
    else:
        card, sleeve = (5, 1, 6, 10, 1), (2, 8, 12, 7, 1)
        mark = caret(((6, 6.5), (8, 3.5), (10, 6.5)), 1.4)
    x, y, w, h, r = sleeve
    return svg(
        rounded(card, TILE_TOP)
        + mark
        + f'<rect x="{x}" y="{y + 1}" width="{w}" height="{h}" rx="{r}" fill="#000" opacity="0.25"/>'  # the sleeve's shadow on the card
        + rounded(sleeve, "url(#sleeve)"),
        gradient("sleeve", SLEEVE_TOP, SLEEVE_BOTTOM),
        size,
    )


if __name__ == "__main__":
    icon_composer()
    flat = flat_icon()
    (HERE / "AppIcon.svg").write_text(flat)
    (HERE / "VolumeIcon.svg").write_text(volume_icon())
    (HERE / "dmg-background.svg").write_text(window(flat))
    for size in (16, 32):
        (HERE / f"AppIcon-{size}.svg").write_text(small_icon(size))
        (HERE / f"VolumeIcon-{size}.svg").write_text(small_volume(size))

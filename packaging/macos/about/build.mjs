// The About window's picture: Lastread as a tabletop proof press.
//
//   node packaging/macos/about/build.mjs [--light] [--out file.html]
//
// The Kobo is the forme, locked on the bed. The carriage with its
// cylinder (the sync, the one lit part) runs on bearers that are exactly
// type-high, so it touches what is on the Kobo and nothing else. The
// proof of your Hardcover shelf lies on the feed board, with red carets in
// the margin where the sync changes something. A cable from the Kobo to
// the trip box: plugging in starts the run. On the galley at the other
// end, two slugs wait to go on the Kobo: the books of the EPUB folder.
//
// Drawn with the anatomy kit (kit/, MIT). The page this writes is
// captured into About-light.png and About-dark.png beside the app's other
// pictures; see packaging/macos/about/README.md.

import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as k from "./kit/iso-kit.mjs";
import * as G from "./kit/lathe.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const theme = process.argv.includes("--light") ? "light" : "dark";
const outAt = process.argv.indexOf("--out");
const OUT = outAt > 0 ? process.argv[outAt + 1] : join(HERE, `about-${theme}.html`);
const pxAt = process.argv.indexOf("--px");
const PX = pxAt > 0 ? Number(process.argv[pxAt + 1]) : 720; // the picture's width on the page, for capturing it large

const WIDTH = 720;
const HEIGHT = 400;

// World units are millimetres of a small tabletop press; z is up.
const BASE = { x: -300, y: -128, w: 520, d: 274, r: 10 };
const BASE_H = 16;
const FOOT_H = 7;
const BED = { x: -150, y: -80, w: 300, d: 160, r: 4 };
const BED_TOP = 22;
const TYPE_HIGH = 26; // the bearers' top, the Kobo's top and the cylinder's lowest line
const RAIL_X = [-205, 205];
const RAILS_Y = [-97, 87]; // each rail is 10 deep
const CHASE = { x: -112, y: -70, w: 224, d: 140, r: 2 };
const CHASE_BAR = 8;
const KOBO = { x: -96, y: -56, w: 160, d: 112, r: 7 };
const CX = 152; // where the carriage stands: at the end of the bed, about to run
const CYL_R = 46;
const AXIS_Z = TYPE_HIGH + CYL_R;
const CYL_Y = [-84, 84];
const BEARER_Y = [[-97, -87], [87, 97]];
const CHEEK_Y = [[-114, -104], [104, 114]];
const ROLLERS = [CX - 86, CX - 64]; // the inking rollers lead, toward the Kobo
const CHEEK = { x: CX - 100, w: 142, r: 10 };
const CHEEK_Z = [6, AXIS_Z + 24];
const ROLLER_R = 8;
const FEED = { x: -292, y: -74, w: 96, d: 148, r: 3 };
const FEED_Z = 30;
const SHEET = { x: -282, y: -64, w: 76, d: 128, r: 0.5 };
const GALLEY = { x: -290, y: 100, w: 84, d: 30, r: 2 };
const TRIP = { x: -178, y: 104, w: 36, d: 24, r: 3 };
const MAKER = { x: -112, y: 118, w: 40, d: 18, r: 1.5 }; // the maker's plate on the front ledge
const INK = [-34, 124]; // the ink disc on the front ledge, with a brayer on it
const INK_R = 19;

const P = k.fitProjection(
  [...k.boxCorners(BASE, -BASE_H - FOOT_H, 0), [CX, CHEEK_Y[0][0], CHEEK_Z[1]], [CX, CHEEK_Y[1][1] + 20, AXIS_Z + 40]],
  WIDTH,
  HEIGHT,
  { pad: 22, azimuth: 58, elevation: 36 },
);

const at = (p) => k.iso(p, P);
const S = (paths, style) => k.solidSvg(paths, style);
const L = (d, style) => k.lineSvg(d, style);
const D = (points, style) => k.dotsSvg(points, style);
const byDepth = (points) => [...points].sort((a, b) => k.depthOf([a[0], a[1], 0], P) - k.depthOf([b[0], b[1], 0], P));
const alongY = (x, y, z) => G.frameOf([x, y, z], [0, 1, 0], [1, 0, 0], [0, 0, 1]);

function base() {
  const out = [`<path class="iso-halo" d="${k.haloOf(BASE, -BASE_H - FOOT_H, BASE_H, P)}"/>`];
  for (const [x, y] of byDepth(k.corners(BASE, 26))) {
    out.push(S(k.cylinder(x, y, 9, -BASE_H - FOOT_H, 2, P, 28), { tone: "lo" }));
    out.push(S(k.cylinder(x, y, 7, -BASE_H - FOOT_H + 2, FOOT_H - 2, P, 28), { tone: "mid" }));
  }
  out.push(S(k.slabOf(BASE, -BASE_H, BASE_H, P, 8, 1.6), { tone: "lo", inner: L(k.sideSeam(BASE, -BASE_H + 5, P, 8), { tone: "faint" }) }));
  out.push(L(k.planOutline(k.insetPlan(BASE, 6), 0, P), { tone: "faint" }));
  const screws = k.corners(BASE, 12);
  out.push(L(screws.map(([x, y]) => k.ring(x, y, 2.6, 0, P, 16)).join(""), { tone: "lo" }));
  out.push(D(screws.map(([x, y]) => at([x, y, 0])), { size: 0.55 }));
  // The guide grooves the cheeks' shoes run in, outside the rails.
  for (const [y0, y1] of CHEEK_Y) {
    out.push(L(k.planOutline({ x: RAIL_X[0] + 6, y: y0 + 2, w: RAIL_X[1] - RAIL_X[0] - 12, d: y1 - y0 - 4, r: 2 }, 0, P, 3), { tone: "lo" }));
  }
  // Line gauge along the front edge: a ruler strip.
  const strip = { x: 20, y: BASE.y + BASE.d - 11, w: 190, d: 7, r: 1 };
  out.push(S(k.slabOf(strip, 0, 0.6, P, 3), { tone: "lo", crease: "none" }));
  const ticks = k.topTicks(strip.x + 4, strip.x + strip.w - 4, 5, 5, strip.y + 0.8, 0.6, [2, 3.8], P);
  out.push(L(ticks.minor, { tone: "lo" }), L(ticks.major, { tone: "mid" }));
  out.push(D([at([strip.x + 2, strip.y + 3.5, 0.6]), at([strip.x + strip.w - 2, strip.y + 3.5, 0.6])], { size: 0.45 }));
  out.push(S(k.slabOf(MAKER, 0, 0.8, P, 3), { tone: "mid", crease: "none" }));
  out.push(L(k.planOutline(k.insetPlan(MAKER, 1.6), 0.8, P, 3), { tone: "faint" }));
  for (const [i, len] of [[0, 26], [1, 18], [2, 22]]) {
    const yy = MAKER.y + 5 + i * 4;
    out.push(L(k.lineOnTop([MAKER.x + 7, yy], [MAKER.x + 7 + len, yy], 0.8, P), { tone: "lo", free: true }));
  }
  out.push(D([at([MAKER.x + 3.4, MAKER.y + MAKER.d / 2, 0.8]), at([MAKER.x + MAKER.w - 3.4, MAKER.y + MAKER.d / 2, 0.8])], { size: 0.45 }));
  return out.join("");
}

function rail(y) {
  const out = [];
  const plan = { x: RAIL_X[0], y, w: RAIL_X[1] - RAIL_X[0], d: 10, r: 1.2 };
  out.push(S(k.slabOf(plan, 0, TYPE_HIGH, P, 3, 0.5), { tone: "mid", inner: L(k.sideSeam(plan, 8, P, 3), { tone: "faint" }) }));
  out.push(D([-180, -60, 60, 180].map((x) => at([x, y + 5, TYPE_HIGH])), { size: 0.45 }));
  for (const x of [RAIL_X[0] - 8, RAIL_X[1]]) {
    const stop = { x, y: y - 3, w: 8, d: 16, r: 1.5 };
    out.push(S(k.slabOf(stop, 0, TYPE_HIGH + 8, P, 3, 0.5), { tone: "mid" }));
    out.push(D([at([x + 4, y + 1, TYPE_HIGH + 8]), at([x + 4, y + 9, TYPE_HIGH + 8])], { size: 0.45 }));
  }
  return out.join("");
}

function rack(y) {
  // The rack the carriage's pinion runs on, on the near rail's outer face.
  const plan = { x: -120, y, w: RAIL_X[1] - 10 + 120, d: 4, r: 0.4 };  // from past the trip box to the far stop
  const out = [S(k.slabOf(plan, 4, 16, P, 2), { tone: "mid", crease: "none" })];
  const teeth = k.sideTicks(plan.x + 3, plan.x + plan.w - 3, 3, 1000, y + 4, 20, [6, 6], P, "x");
  out.push(L(teeth.minor + teeth.major, { tone: "lo" }));
  return out.join("");
}

function bed() {
  const out = [S(k.slabOf(BED, 0, BED_TOP, P, 4, 0.8), { tone: "mid", inner: L(k.sideSeam(BED, 6, P, 4), { tone: "faint" }) })];
  // The chase: an iron frame that locks the forme.
  const { x, y, w, d } = CHASE;
  const bars = [
    { x, y, w, d: CHASE_BAR, r: 1 },
    { x, y: y + CHASE_BAR, w: CHASE_BAR, d: d - 2 * CHASE_BAR, r: 0.6 },
    { x: x + w - CHASE_BAR, y: y + CHASE_BAR, w: CHASE_BAR, d: d - 2 * CHASE_BAR, r: 0.6 },
    { x, y: y + d - CHASE_BAR, w, d: CHASE_BAR, r: 1 },
  ];
  for (const plan of bars) out.push(S(k.slabOf(plan, BED_TOP, TYPE_HIGH - BED_TOP - 0.6, P, 2, 0.3), { tone: "mid" }));
  out.push(D(k.corners({ x, y, w, d, r: 0 }, 4).map(([px, py]) => at([px, py, TYPE_HIGH - 0.6])), { size: 0.45 }));
  // Furniture: wood that packs the Kobo in, and two quoins that lock it.
  const inner = { x: x + CHASE_BAR, y: y + CHASE_BAR, w: w - 2 * CHASE_BAR, d: d - 2 * CHASE_BAR };
  const pieces = [
    { x: inner.x, y: inner.y, w: KOBO.x - inner.x, d: inner.d, r: 0.5 },
    { x: KOBO.x, y: inner.y, w: KOBO.w, d: KOBO.y - inner.y, r: 0.5 },
    { x: KOBO.x, y: KOBO.y + KOBO.d, w: KOBO.w, d: inner.y + inner.d - KOBO.y - KOBO.d, r: 0.5 },
    { x: KOBO.x + KOBO.w, y: inner.y, w: 18, d: inner.d, r: 0.5 },
  ];
  for (const plan of pieces) {
    out.push(S(k.slabOf(plan, BED_TOP, TYPE_HIGH - BED_TOP - 1.2, P, 2), { tone: "lo", crease: "none" }));
  }
  const quoinX = KOBO.x + KOBO.w + 18;
  for (const qy of [inner.y + 18, inner.y + inner.d - 46]) {
    const q = { x: quoinX, y: qy, w: inner.x + inner.w - quoinX, d: 28, r: 0.6 };
    out.push(S(k.slabOf(q, BED_TOP, TYPE_HIGH - BED_TOP - 1, P, 2, 0.3), { tone: "mid" }));
    out.push(L(k.ring(q.x + q.w / 2, q.y + q.d / 2, 2, TYPE_HIGH - 1, P, 12), { tone: "lo" }));
  }
  return out.join("");
}

function kobo() {
  // The forme: the Kobo, face up, locked in the chase.
  const out = [S(k.slabOf(KOBO, BED_TOP, TYPE_HIGH - BED_TOP, P, 8, 0.6), { tone: "hi", crease: "lo" })];
  const screen = { x: KOBO.x + 12, y: KOBO.y + 10, w: KOBO.w - 30, d: KOBO.d - 20, r: 1.5 };
  out.push(L(k.planOutline(screen, TYPE_HIGH, P, 3), { tone: "lo" }));
  // A page of text on the screen: rule lines, ragged on the right.
  const lines = [];
  for (let i = 0; i < 8; i++) {
    const yy = screen.y + 10 + i * 9.6;
    const end = screen.x + screen.w - 8 - ((i * 37) % 23);
    lines.push(L(k.lineOnTop([screen.x + 8, yy], [i === 7 ? screen.x + 50 : end, yy], TYPE_HIGH, P), { tone: "lo", free: true }));
  }
  out.push(lines.join(""));
  // How far: the reading progress the sync carries, 34% of the way.
  const track = [screen.x + 8, screen.x + screen.w - 8];
  const py = screen.y + screen.d - 5;
  out.push(L(k.lineOnTop([track[0], py], [track[1], py], TYPE_HIGH, P), { tone: "lo" }));
  out.push(`<path class="iso-line" data-tone="hi" d="${k.lineOnTop([track[0], py], [track[0] + 0.34 * (track[1] - track[0]), py], TYPE_HIGH, P)}" style="stroke-width:1.4"/>`);
  out.push(D([at([track[0], py, TYPE_HIGH]), at([track[1], py, TYPE_HIGH])], { size: 0.45, tone: "lo" }));
  // The home light, and the USB port on the edge facing the trip box.
  out.push(D([at([KOBO.x + KOBO.w - 9, KOBO.y + KOBO.d / 2, TYPE_HIGH])], { size: 0.7, tone: "mid" }));
  return out.join("");
}

function feedBoard() {
  const out = [];
  for (const y of [FEED.y + 16, FEED.y + FEED.d - 26]) {
    const bracket = { x: FEED.x + 30, y, w: 36, d: 10, r: 1 };
    out.push(S(k.slabOf(bracket, 0, FEED_Z - 4, P, 2, 0.4), { tone: "mid" }));
  }
  out.push(S(k.slabOf(FEED, FEED_Z - 4, 4, P, 3, 0.6), { tone: "mid" }));
  // Side lay and head lays: where the sheet is laid square.
  out.push(S(k.slabOf({ x: SHEET.x - 6, y: SHEET.y + 10, w: 4, d: 30, r: 0.6 }, FEED_Z, 3, P, 2), { tone: "mid" }));
  out.push(S(k.slabOf({ x: SHEET.x + 10, y: SHEET.y - 6, w: 22, d: 4, r: 0.6 }, FEED_Z, 3, P, 2), { tone: "mid" }));
  // The proof: your Hardcover shelf. A row per book; a caret where the sync changes it.
  out.push(S(k.slabOf(SHEET, FEED_Z, 0.6, P, 2), { tone: "hi", crease: "none" }));
  const top = FEED_Z + 0.6;
  const margin = SHEET.x + SHEET.w - 14;
  out.push(L(k.lineOnTop([margin, SHEET.y], [margin, SHEET.y + SHEET.d], top, P), { tone: "faint" }));  // edge to edge
  const rows = [];
  const marked = new Set([2, 5, 6]);
  for (let i = 0; i < 11; i++) {
    const yy = SHEET.y + 10 + i * 10.6;
    rows.push(L(k.lineOnTop([SHEET.x + 7, yy], [SHEET.x + 7 + 34 + ((i * 29) % 17), yy], top, P), { tone: "lo", free: true }));
    rows.push(L(k.lineOnTop([SHEET.x + 7, yy + 3.4], [SHEET.x + 7 + 18 + ((i * 13) % 9), yy + 3.4], top, P), { tone: "faint", free: true }));
    if (marked.has(i)) {
      const c = [margin + 6, yy + 1.6];
      rows.push(L(k.onTop([[c[0] + 2.4, c[1] - 2.6], [c[0] - 1.8, c[1]], [c[0] + 2.4, c[1] + 2.6]], top, P), { tone: "red", free: true }));
    }
  }
  out.push(rows.join(""));
  return out.join("");
}

function galley() {
  // A brass galley: a tray open toward the bed, with two slugs set to go on the Kobo.
  const out = [S(k.slabOf(GALLEY, 0, 4, P, 3, 0.5), { tone: "mid" })];
  const wall = 3;
  out.push(S(k.slabOf({ x: GALLEY.x, y: GALLEY.y, w: GALLEY.w, d: wall, r: 0.5 }, 4, 7, P, 2), { tone: "mid" }));
  out.push(S(k.slabOf({ x: GALLEY.x + GALLEY.w - wall, y: GALLEY.y + wall, w: wall, d: GALLEY.d - 2 * wall, r: 0.5 }, 4, 7, P, 2), { tone: "mid" }));
  for (const [i, len] of [[0, 46], [1, 38]]) {
    const slug = { x: GALLEY.x + GALLEY.w - wall - len - 2, y: GALLEY.y + wall + 1 + i * 12.5, w: len, d: 11, r: 0.4 };
    out.push(S(k.slabOf(slug, 4, 9, P, 2, 0.3), { tone: "hi", crease: "lo" }));
    out.push(L(k.lineOnTop([slug.x + 4, slug.y + 5.5], [slug.x + slug.w - 6, slug.y + 5.5], 13, P), { tone: "lo", free: true }));
  }
  out.push(S(k.slabOf({ x: GALLEY.x, y: GALLEY.y + GALLEY.d - wall, w: GALLEY.w, d: wall, r: 0.5 }, 4, 7, P, 2), { tone: "mid" }));
  return out.join("");
}

function tripBox() {
  const out = [S(k.slabOf(TRIP, 0, 18, P, 3, 0.6), { tone: "mid" })];
  out.push(L(k.planOutline(k.insetPlan(TRIP, 3), 18, P, 2), { tone: "faint" }));
  out.push(D(k.corners(TRIP, 3).map(([x, y]) => at([x, y, 18])), { size: 0.45 }));
  return out.join("");
}

function inkDisc() {
  // The ink disc on its pedestal, and a brayer resting on it.
  const [x, y] = INK;
  const out = [S(k.cylinder(x, y, 7, 0, 3, P, 24), { tone: "mid" })];
  out.push(S(k.cylinder(x, y, 3.2, 3, 7, P, 16), { tone: "mid", crease: "none" }));
  out.push(S(k.cylinder(x, y, INK_R, 10, 2.4, P, 64, 0.5), { tone: "hi", crease: "lo" }));
  out.push(L(k.ring(x, y, INK_R - 3, 12.4, P, 56), { tone: "faint" }));
  out.push(L(k.ring(x, y, 7, 12.4, P, 32), { tone: "faint" }));
  const F = G.frameOf([x - 10, y - 2, 12.4 + 4], [1, 0.25, 0], [0, 0, 1], [-0.25, 1, 0]);
  const axis = G.frameAlong([x - 10, y - 2, 12.4 + 4], [1, 0.25, 0]);
  out.push(S(G.solidOf([[0, 3.2], [0.6, 4], [15.4, 4], [16, 3.2]], axis, P), { tone: "mid" }));
  const hx = [x + 7, y + 2.25, 16.4];
  out.push(S(k.slabOf({ x: hx[0], y: hx[1] - 1, w: 4, d: 2, r: 0.6 }, 15.4, 2, P, 2), { tone: "mid", crease: "none" }));
  out.push(S(G.solidOf([[0, 1.8], [12, 2.2, 1], [22, 2.4, 1], [24, 1.6]], G.frameAlong([x + 11, y + 3.25, 17.4], [1, 0.25, 0.35]), P), { tone: "mid" }));
  void F;
  return out.join("");
}

function cable() {
  // From the Kobo's port, over the chase and down to the trip box.
  const port = KOBO.x + 30;
  const from = [port, KOBO.y + KOBO.d, TYPE_HIGH - 2];
  const via = [
    [port, CHASE.y + CHASE.d + 4, TYPE_HIGH + 6],
    [port - 20, RAILS_Y[1] + 5, TYPE_HIGH + 10],
    [TRIP.x + TRIP.w / 2 + 6, TRIP.y - 6, 22],
  ].map(at);
  return k.wireSvg(at(from), at([TRIP.x + TRIP.w / 2, TRIP.y + 8, 18]), { via, tone: "mid", size: 1.4 });
}

function cylinder() {
  const F = alongY(CX, CYL_Y[0], AXIS_Z);
  const len = CYL_Y[1] - CYL_Y[0];
  const body = G.solidOf([[0, CYL_R - 1], [2, CYL_R], [len - 2, CYL_R], [len, CYL_R - 1]], F, P);
  const seams = [10, len - 10].map((s) => G.arcOf(F, s, CYL_R, P)).join("");
  // The gripper edge where the sheet is held, turned toward the viewer.
  const grip = G.angleToward(F, [0.2, 1, 1.4]);
  const g0 = G.pointOf(F, 10, CYL_R, grip);  // from seam to seam
  const g1 = G.pointOf(F, len - 10, CYL_R, grip);
  const edge = k.segment(g0, g1, P);
  const second = k.segment(G.pointOf(F, 10, CYL_R, grip + 0.09), G.pointOf(F, len - 10, CYL_R, grip + 0.09), P);
  const screws = [];
  for (let s = 20; s <= len - 20; s += 16) screws.push(at(G.pointOf(F, s, CYL_R, grip + 0.045)));
  return S(body, { tone: "hi", lit: true, inner: L(seams, { tone: "faint" }) + L(edge, { tone: "mid" }) + L(second, { tone: "lo" }) }) + D(screws, { size: 0.45 });
}

function bearer([y0, y1]) {
  const F = alongY(CX, y0, AXIS_Z);
  return S(G.disc(0, y1 - y0, CYL_R, F, P), { tone: "mid" });
}

function rollers() {
  return ROLLERS.map((x) => {
    const F = alongY(x, CYL_Y[0] + 4, TYPE_HIGH + ROLLER_R);
    const len = CYL_Y[1] - CYL_Y[0] - 8;
    return S(G.solidOf([[0, ROLLER_R - 0.8], [1.2, ROLLER_R], [len - 1.2, ROLLER_R], [len, ROLLER_R - 0.8]], F, P), { tone: "mid" });
  }).join("");
}

function shafts(cheek) {
  // Journals of the cylinder and the rollers, from cylinder to cheek.
  const out = [];
  const [y0, y1] = cheek;
  const from = y0 < 0 ? y1 : y0;
  const span = y0 < 0 ? [from, CYL_Y[0]] : [CYL_Y[1], from];
  out.push(S(G.disc(0, span[1] - span[0], 9, alongY(CX, span[0], AXIS_Z), P), { tone: "mid" }));
  for (const x of ROLLERS) out.push(S(G.disc(0, span[1] - span[0] + 4, 3, alongY(x, span[0] - (y0 < 0 ? 0 : 4), TYPE_HIGH + ROLLER_R), P), { tone: "mid" }));
  return out.join("");
}

function cheekPlate([y0, y1], near) {
  const plan = { x: CHEEK.x, y: y0, w: CHEEK.w, d: y1 - y0, r: CHEEK.r };
  const out = [];
  // The shoe that runs in the base's groove.
  out.push(S(k.slabOf({ x: CHEEK.x + 6, y: y0 + 1, w: CHEEK.w - 12, d: y1 - y0 - 2, r: 2 }, 0, CHEEK_Z[0], P, 3), { tone: "lo" }));
  out.push(S(k.slabOf(plan, CHEEK_Z[0], CHEEK_Z[1] - CHEEK_Z[0], P, 8, 0.8), { tone: "mid", inner: L(k.sideSeam(plan, CHEEK_Z[0] + 10, P, 8), { tone: "faint" }) }));
  // The oil cup over the cylinder's journal.
  const mid = (y0 + y1) / 2;
  out.push(S(k.cylinder(CX, mid, 3.4, CHEEK_Z[1], 5, P, 20), { tone: "mid" }));
  out.push(S(k.cylinder(CX, mid, 4.6, CHEEK_Z[1] + 5, 2.4, P, 24, 0.3), { tone: "mid" }));
  out.push(L(k.knurl(CX, mid, 4.6, CHEEK_Z[1] + 5, CHEEK_Z[1] + 7.4, 20, P), { tone: "lo" }));
  if (!near) return out.join("");
  // Outside the near cheek: the journal's cap, the pinion's guard and the hand wheel.
  const face = y1;
  const hub = alongY(CX, face, AXIS_Z);
  out.push(S(G.disc(0, 4, 16, hub, P), { tone: "mid" }));
  out.push(D(G.dotsOf(hub, 4, 12, 6, P, { all: true }), { size: 0.45 }));
  const wheel = alongY(CX, face + 4, AXIS_Z);
  // A solid cast hand wheel: a turned groove on its face, and the hub standing out of it.
  out.push(S(G.disc(4, 12, 10, wheel, P), { tone: "mid" }));
  out.push(S(G.disc(12, 15, 36, wheel, P), { tone: "mid", inner: L(G.circleOf(wheel, 15, 30, P), { tone: "lo" }) + L(G.circleOf(wheel, 15, 27, P), { tone: "faint" }) }));
  out.push(S(G.disc(15, 18, 8, wheel, P), { tone: "mid" }));
  out.push(D(G.dotsOf(wheel, 18, 5, 4, P, { all: true }), { size: 0.45 }));
  const grip = G.pointOf(wheel, 15, 22, Math.PI * 0.32);
  const handle = alongY(grip[0], grip[1], grip[2]);
  out.push(S(G.disc(0, 14, 2.4, handle, P), { tone: "mid" }));
  out.push(S(G.sphereOf([grip[0], grip[1] + 17, grip[2]], 4.6, P), { tone: "mid" }));
  // The one engraved word on the press.
  out.push(k.faceTextSvg(k.sideMatrix([CHEEK.x + 34, face], CHEEK_Z[0] + 16, P, "left"), "LASTREAD", { size: 4.2, tone: "lo", anchor: "middle" }));
  // Rivets along the face, under its top edge.
  out.push(D([CHEEK.x + 10, CHEEK.x + 34, CHEEK.x + 58].map((x) => at([x, face, CHEEK_Z[1] - 7])), { size: 0.5 }));
  // The trip lever: plugging in the Kobo throws it.
  const trip = [CHEEK.x + 16, (y0 + y1) / 2];
  out.push(S(k.slabOf({ x: trip[0] - 5, y: y0 + 1, w: 10, d: y1 - y0 - 2, r: 2 }, CHEEK_Z[1], 4, P, 3, 0.4), { tone: "mid" }));
  out.push(S(k.cylinder(trip[0], trip[1], 1.8, CHEEK_Z[1] + 4, 26, P, 16), { tone: "mid", crease: "none" }));
  out.push(S(G.sphereOf([trip[0], trip[1], CHEEK_Z[1] + 33], 5, P), { tone: "mid" }));
  // Rivets along the cheek's top edge.
  out.push(D([CHEEK.x + 12, CHEEK.x + CHEEK.w - 12].map((x) => at([x, (y0 + y1) / 2, CHEEK_Z[1]])), { size: 0.5 }));
  return out.join("");
}

const svg = k.figureSvg({
  width: WIDTH,
  height: HEIGHT,
  label:
    "Lastread drawn as a tabletop proof press. A Kobo lies locked in the chase on the bed; a carriage with an impression cylinder runs over it on type-high bearers. On the feed board lies the proof of the Hardcover shelf, one row per book, with red carets in the margin where the sync changes something. A cable runs from the Kobo to the trip box, and on the galley two slugs wait to go on the Kobo.",
  body: [
    base(),
    feedBoard(),
    cheekPlate(CHEEK_Y[0], false),
    shafts(CHEEK_Y[0]),
    rail(RAILS_Y[0]),
    bed(),
    kobo(),
    bearer(BEARER_Y[0]),
    cylinder(),
    rollers(),
    rail(RAILS_Y[1]),
    rack(RAILS_Y[1] + 10),
    bearer(BEARER_Y[1]),
    shafts(CHEEK_Y[1]),
    tripBox(),
    inkDisc(),
    cable(),
    cheekPlate(CHEEK_Y[1], true),
    galley(),
  ],
});

const css = `
/* The app's own paper (Paper.swift: sheet) and red (what a sync sends), so the picture sits on the window without an edge. */
.iso[data-theme="light"]{--anatomy-red:#c0212b;--anatomy-paper:#fbfbf8;--anatomy-card:#fbfbf8;--anatomy-page:#fbfbf8}
.iso:not([data-theme="light"]){--anatomy-red:#ff8077;--anatomy-paper:#171a1e;--anatomy-card:#171a1e;--anatomy-page:#171a1e}
.iso-page{width:${PX}px;margin:0}
.iso{--anatomy-weight:${(0.6 * PX / 720).toFixed(2)}px}
.about svg{width:${PX}px;height:auto}
`;
const page = k.pageHtml({ title: "Lastread", theme, width: PX, body: `<style>${css}</style><div class="about">${svg}</div>` });
writeFileSync(OUT, page);
console.log("wrote", OUT);

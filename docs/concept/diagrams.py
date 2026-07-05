"""The eight vector diagrams (V1–V8). Each returns a self-contained figure
(index tag, title, subtitle, body, caption) sized on a 1000-wide design canvas,
usable standalone or embedded in the paper at native vector fidelity.
"""
from __future__ import annotations

from kit import (AMBER, AMBER_T, DANGER, FAINT, HAIR, HAIR2, INK, INK_SOFT,
                 PANEL, PANEL2, PAPER, PRIMARY, PRIMARY_D, PRIMARY_T, SLATE,
                 TEAL, TEAL_T, VIOLET, VIOLET_T, WARN, arrow, card, chip,
                 circle, icon, line, measure, paragraph, path, rect, text, wrap)

W = 1000
PAD = 36


class Fig:
    """A titled, captioned figure frame. body() draws into the content band."""

    def __init__(self, idx, title, subtitle, height, caption):
        self.idx, self.title, self.subtitle = idx, title, subtitle
        self.H = height
        self.caption = caption
        self.parts: list[str] = []

    def add(self, *svg):
        self.parts.extend(svg)

    @property
    def top(self):
        return 104           # y where body content may start

    @property
    def bottom(self):
        return self.H - self._cap_h() - 24

    def _cap_h(self):
        lines = wrap(self.caption, 13, W - 2 * PAD, 400, True)
        return 13 * 1.5 * len(lines)

    def render(self) -> str:
        s = [rect(0, 0, W, self.H, fill=PAPER)]
        s.append(rect(0, 0, W, self.H, fill="none", stroke=HAIR, sw=1.4, rx=14))
        # header
        tag_w = measure(self.idx, 11, 700, spacing=1) + 20
        s.append(rect(PAD, 40, tag_w, 24, fill=PRIMARY, rx=6))
        s.append(text(PAD + tag_w / 2, 56, self.idx, 11, 700, PAPER, "middle",
                      spacing=1))
        s.append(text(PAD + tag_w + 16, 52, self.title, 22, 600, INK))
        s.append(text(PAD + tag_w + 16, 72, self.subtitle, 12.5, 400, SLATE))
        s.append(line(PAD, 88, W - PAD, 88, HAIR, 1.2))
        # body
        s.extend(self.parts)
        # caption
        cs, _ = paragraph(PAD, self.H - self._cap_h() - 6, self.caption, 13,
                          W - 2 * PAD, 400, SLATE, 1.5, italic=True)
        s.append(line(PAD, self.H - self._cap_h() - 26, W - PAD,
                      self.H - self._cap_h() - 26, HAIR, 1.0))
        s.append(cs)
        return "".join(s)


def _node(x, y, w, h, title, sub=None, fill=PAPER, stroke=HAIR2, accent=PRIMARY,
          tsize=13, icon_name=None):
    s = card(x, y, w, h, fill=fill, stroke=stroke, sw=1.3, rx=9, accent=accent)
    tx = x + 18
    ty = y + (h / 2 + 4 if not sub else h / 2 - 3)
    if icon_name:
        s += icon(icon_name, x + 15, y + h / 2 - 11, 22, accent, 1.7)
        tx = x + 46
    s += text(tx, ty, title, tsize, 600, INK)
    if sub:
        s += text(tx, ty + 16, sub, 10.2, 400, SLATE)
    return s


def _pill(x, y, label, fill, tx, size=10.5, h=24, pad=13, weight=600):
    w = measure(label, size, weight) + pad * 2
    return (rect(x, y, w, h, fill=fill, rx=h / 2)
            + text(x + w / 2, y + h / 2 + size * 0.35, label, size, weight, tx,
                   "middle")), w


# --------------------------------------------------------------------------- #
# V1 — Concept keyframe (hero)
# --------------------------------------------------------------------------- #
def v1():
    f = Fig("V1", "Sound, compiled — not recorded",
            "The concept at a glance: one idea, three properties, three audiences",
            560,
            "AudioForge treats a finished sound as a build artifact: an "
            "inspectable source compiles to a hashed contract that renders to "
            "byte-identical audio, authored as readily by an AI agent as by a "
            "person, and verifiable the way code is.")
    cx = W / 2
    # thesis
    f.add(text(cx, 138, "A production audio engine where every asset is a",
               15, 400, INK_SOFT, "middle"))
    f.add(text(cx, 162, "reproducible build, not a one-off session.",
               16, 600, INK, "middle"))
    # pipeline spine
    y = 210
    bw, bh, gap = 236, 66, 60
    x0 = (W - (3 * bw + 2 * gap)) / 2
    xs = [x0 + i * (bw + gap) for i in range(3)]
    labels = [("SOURCE", "the .af language + JSON IR", "contract", PRIMARY),
              ("ENGINE", "seeded synthesis · sampling · mastering", "wave", AMBER),
              ("ASSET", "WAV + manifest, sha-256 verified", "check", TEAL)]
    for (x, (t, sub, ic, col)) in zip(xs, labels):
        f.add(_node(x, y, bw, bh, t, sub, PAPER, HAIR2, col, 15, ic))
    for i in range(2):
        f.add(arrow(xs[i] + bw + 6, y + bh / 2, xs[i + 1] - 6, y + bh / 2,
                    SLATE, 1.6, 6))
    # verify loop
    f.add(path(f"M{xs[2]+bw/2},{y+bh} C{xs[2]+bw/2},{y+bh+52} "
               f"{xs[0]+bw/2},{y+bh+52} {xs[0]+bw/2},{y+bh}",
               "none", VIOLET, 1.6, dash="2 5"))
    f.add(text(cx, y + bh + 48, "verify — re-render and compare bytes", 11,
               500, VIOLET, "middle"))
    # three properties
    py = 372
    props = [("Deterministic", "same source, same engine → the same bytes, "
              "forever. Entropy is seeded from the contract hash.", "hash", PRIMARY, PRIMARY_T),
             ("Inspectable", "intent expands into explicit data anyone — or any "
              "agent — can read, diff, and trust before it plays.", "eye", AMBER, AMBER_T),
             ("Agent-native", "authored and mutated through a structured "
              "contract, with no UI standing between intent and output.", "agent", VIOLET, VIOLET_T)]
    pw, pgap = 300, 20
    px0 = (W - (3 * pw + 2 * pgap)) / 2
    for i, (t, d, ic, col, tint) in enumerate(props):
        x = px0 + i * (pw + pgap)
        f.add(card(x, py, pw, 92, fill=tint, stroke="none", rx=10))
        f.add(icon(ic, x + 18, py + 18, 24, col, 1.8))
        f.add(text(x + 54, py + 34, t, 14.5, 600, INK))
        ps, _ = paragraph(x + 18, py + 58, d, 10.4, pw - 36, 400, INK_SOFT, 1.42)
        f.add(ps)
    # audiences
    ay = 486
    f.add(text(PAD, ay, "BUILT FOR", 10, 600, SLATE, spacing=1.5))
    auds = ["Production teams", "Pipeline engineers", "AI agents & their builders"]
    ax = PAD + 92
    for a in auds:
        p, w_ = _pill(ax, ay - 15, a, PANEL, INK_SOFT, 10.5, 24, 14, 500)
        f.add(p)
        ax += w_ + 12
    return f


# --------------------------------------------------------------------------- #
# V2 — Problem → value map
# --------------------------------------------------------------------------- #
def v2():
    f = Fig("V2", "From broken promise to build artifact",
            "Each failure of today's workflow, and the mechanism that resolves it into value",
            560,
            "The through-line: opacity becomes an inspectable contract, leaked "
            "randomness becomes seeded lineage, and unverifiable output becomes "
            "a gate — turning fragile sessions into trustworthy deliveries.")
    colw = 292
    xs = [PAD, (W - colw) / 2, W - PAD - colw]
    heads = [("THE PROBLEM", DANGER), ("THE MECHANISM", PRIMARY), ("THE VALUE", TEAL)]
    for x, (h, c) in zip(xs, heads):
        f.add(rect(x, 108, colw, 22, fill="none"))
        f.add(text(x, 122, h, 10.5, 700, c, spacing=1.2))
    rows = [
        ("Sessions no one can repeat; hidden plugin and tool state.",
         "The IR is truth — intent compiles to explicit, diffable data.",
         "Every render reproducible and reviewable from its source."),
        ("Randomness leaks from clocks and global RNG.",
         "All entropy is seeded from the contract hash.",
         "Declared, traceable variation instead of accidental drift."),
        ("“What changed, and does it still match intent?” goes unanswered.",
         "A manifest records the spec hash and output checksum.",
         "Diffable provenance; drift caught by a byte-compare gate."),
        ("Agents emit opaque blobs no pipeline can check.",
         "Validation binds resources: valid means render-ready.",
         "Agent output is verified before it enters production."),
    ]
    y = 142
    rh = 84
    for i, (p, m, v) in enumerate(rows):
        yy = y + i * rh
        f.add(card(xs[0], yy, colw, rh - 14, fill=PAPER, stroke=HAIR, sw=1.2,
                   rx=8, accent=DANGER, accent_w=2.6))
        f.add(card(xs[1], yy, colw, rh - 14, fill=PRIMARY_T, stroke="none", rx=8))
        f.add(card(xs[2], yy, colw, rh - 14, fill=TEAL_T, stroke="none", rx=8))
        for x, tx_, col in ((xs[0], p, INK_SOFT), (xs[1], m, INK),
                            (xs[2], v, INK)):
            ps, _ = paragraph(x + 15, yy + 24, tx_, 10.6, colw - 30, 400, col, 1.42)
            f.add(ps)
        if i < len(rows):
            for gx in (xs[0] + colw, xs[1] + colw):
                f.add(arrow(gx + 3, yy + (rh - 14) / 2, gx + (xs[1] - xs[0] - colw) - 3,
                            yy + (rh - 14) / 2, FAINT, 1.4, 5))
    return f


# --------------------------------------------------------------------------- #
# V3 — Operating-model diagram
# --------------------------------------------------------------------------- #
def v3():
    f = Fig("V3", "The pipeline, end to end",
            "How a source becomes a verified, reproducible asset",
            560,
            "Compilation fixes intent as a hashed contract; validation proves it "
            "render-ready; the plan records every routing decision; the render is "
            "fully seeded; the manifest carries provenance; verify closes the loop.")
    stages = [
        (".af source", "human & agent authoring", AMBER, "contract"),
        ("compile → IR", "macros expand to explicit data", PRIMARY, "layers"),
        ("validate", "bind resources · render-ready", PRIMARY, "check"),
        ("render plan", "route decisions + policy gates", VIOLET, "branch"),
        ("render", "seeded synth · sample · mix · master", AMBER, "wave"),
        ("WAV + manifest", "sha-256 · loudness · markers", TEAL, "box"),
    ]
    bw, bh = 150, 74
    gap = (W - 2 * PAD - 6 * bw) / 5
    y = 150
    xs = [PAD + i * (bw + gap) for i in range(6)]
    for x, (t, sub, col, ic) in zip(xs, stages):
        f.add(card(x, y, bw, bh, fill=PAPER, stroke=HAIR2, sw=1.3, rx=9, accent=col))
        f.add(icon(ic, x + 14, y + 12, 20, col, 1.7))
        f.add(text(x + 14, y + 48, t, 11.6, 600, INK))
        ps, _ = paragraph(x + 14, y + 62, sub, 8.6, bw - 24, 400, SLATE, 1.3)
        f.add(ps)
    for i in range(5):
        f.add(arrow(xs[i] + bw + 2, y + bh / 2, xs[i + 1] - 2, y + bh / 2,
                    SLATE, 1.5, 5))
    # hash lineage band
    hy = y + bh + 46
    f.add(rect(xs[1], hy, xs[4] + bw - xs[1], 40, fill=PRIMARY_T, rx=8))
    f.add(icon("hash", xs[1] + 12, hy + 9, 22, PRIMARY, 1.7))
    f.add(text(xs[1] + 44, hy + 18, "SEED LINEAGE", 9.5, 700, PRIMARY_D, spacing=1))
    f.add(text(xs[1] + 44, hy + 32,
               "the contract hash roots every random path — noise, dither, "
               "round-robins, reverb tails — so nothing leaks from the clock",
               9.4, 400, INK_SOFT))
    for i in (1, 4):
        f.add(line(xs[i] + bw / 2, y + bh, xs[i] + bw / 2, hy, PRIMARY, 1.1,
                   dash="2 4"))
    # verify loop
    vy = hy + 74
    f.add(path(f"M{xs[5]+bw/2},{y+bh} C{xs[5]+bw/2},{vy} {xs[2]+bw/2},{vy} "
               f"{xs[2]+bw/2},{y+bh}", "none", VIOLET, 1.6, dash="2 5"))
    lp, lw = _pill(0, 0, "verify: re-render → byte-compare", VIOLET_T,
                   VIOLET, 10.5, 24, 14, 600)
    f.add(_pill(W / 2 - lw / 2, vy - 12, "verify: re-render → byte-compare",
                VIOLET_T, VIOLET, 10.5, 24, 14, 600)[0])
    return f


# --------------------------------------------------------------------------- #
# V4 — Capability map
# --------------------------------------------------------------------------- #
def v4():
    import math
    f = Fig("V4", "Capabilities compose around one contract",
            "Every capability reads from and writes to the same inspectable IR",
            650,
            "Nothing acts on private state. Generation, expression, mixing, "
            "variation, interop and delivery all resolve into the same explicit "
            "IR — which is exactly why they compose without surprises.")
    cx, cy = W / 2, 322
    f.add(circle(cx, cy, 74, fill=PRIMARY_T, stroke=PRIMARY, sw=1.6))
    f.add(icon("contract", cx - 15, cy - 26, 30, PRIMARY, 1.8))
    f.add(text(cx, cy + 20, "IR", 17, 700, PRIMARY_D, "middle"))
    f.add(text(cx, cy + 36, "the contract", 9.5, 500, PRIMARY, "middle"))
    caps = [
        ("Determinism", "seed lineage · no wall clock", "hash", PRIMARY),
        ("Verification", "validate · plan · verify gate", "check", VIOLET),
        ("Sound generation", "synthesis + hashed sampling", "wave", AMBER),
        ("Expression", "groove · dynamics · legato", "gauge", AMBER),
        ("Mix · space · master", "buses · rooms · loudness", "layers", TEAL),
        ("Variation at scale", "variants · cutdowns · lineage", "branch", TEAL),
        ("Interop", "MIDI · MusicXML · round-trip", "swap", PRIMARY),
        ("Delivery", "presets · tagged distributables", "box", AMBER),
    ]
    n = len(caps)
    R = 202
    bw, bh = 210, 58
    for i, (t, sub, ic, col) in enumerate(caps):
        ang = -math.pi / 2 + i * 2 * math.pi / n
        nx, ny = cx + R * math.cos(ang), cy + R * math.sin(ang)
        # connector
        ex, ey = cx + 74 * math.cos(ang), cy + 74 * math.sin(ang)
        f.add(line(ex, ey, nx - (bw / 2 - 40) * 0 + (nx - cx) * 0.0, ny,
                   HAIR2, 1.2))
        bx, by = nx - bw / 2, ny - bh / 2
        f.add(card(bx, by, bw, bh, fill=PAPER, stroke=HAIR2, sw=1.2, rx=8, accent=col))
        f.add(icon(ic, bx + 13, by + bh / 2 - 11, 20, col, 1.7))
        f.add(text(bx + 42, by + bh / 2 - 2, t, 11.8, 600, INK))
        f.add(text(bx + 42, by + bh / 2 + 13, sub, 9, 400, SLATE))
    return f


# --------------------------------------------------------------------------- #
# V5 — Dual-experience diptych
# --------------------------------------------------------------------------- #
def v5():
    f = Fig("V5", "Two hands on the same contract",
            "How an AI agent and a human operator each work the system",
            600,
            "Both meet at the IR and its verification layer. The agent reads and "
            "writes the contract directly; the operator shapes intent and holds "
            "the gates — neither depends on a UI to absorb ambiguity.")
    colw = 430
    lx, rx = PAD, W - PAD - colw
    f.add(card(lx, 104, colw, 400, fill=VIOLET_T, stroke="none", rx=12))
    f.add(card(rx, 104, colw, 400, fill=AMBER_T, stroke="none", rx=12))
    f.add(icon("agent", lx + 22, 122, 26, VIOLET, 1.8))
    f.add(text(lx + 58, 134, "THE AI AGENT", 12, 700, VIOLET, spacing=1))
    f.add(text(lx + 58, 150, "authors and repairs without a screen", 10, 400, INK_SOFT))
    f.add(icon("person", rx + 22, 122, 26, AMBER, 1.8))
    f.add(text(rx + 58, 134, "THE HUMAN OPERATOR", 12, 700, "#9A6A1E", spacing=1))
    f.add(text(rx + 58, 150, "directs intent and holds the gates", 10, 400, INK_SOFT))
    left = [("Perceive", "reads the IR, the capability manifest, structured "
             "line-cited diagnostics, and the render plan's evidence."),
            ("Act", "emits or mutates the contract; schema-checked edits never "
             "raise — every problem returns as structured feedback."),
            ("Verify", "treats its own output as untrusted; “valid” is a true "
             "predicate for “will render”.")]
    right = [("Direct", "writes austere intent — emotion, intensity, motifs, "
              "style — that expands into explicit, reviewable IR."),
             ("Oversee", "reads manifests, markers and loudness reports; diffs "
              "two renders; gates drift in CI."),
             ("Deliver", "renders presets, campaigns and variants, then packages "
              "tagged distributables with provenance intact.")]
    for col, x, data, col_c in ((0, lx, left, VIOLET), (1, rx, right, AMBER)):
        y = 176
        for j, (t, d) in enumerate(data):
            f.add(circle(x + 30, y + 12, 12, fill=PAPER, stroke=col_c, sw=1.6))
            f.add(text(x + 30, y + 16, str(j + 1), 11, 700, col_c, "middle"))
            f.add(text(x + 52, y + 10, t, 13, 600, INK))
            ps, h = paragraph(x + 52, y + 27, d, 10.2, colw - 74, 400, INK_SOFT, 1.42)
            f.add(ps)
            if j < len(data) - 1:
                f.add(line(x + 30, y + 26, x + 30, y + 66, col_c, 1.2, dash="2 4"))
            y += 78
    # shared spine
    f.add(text(W / 2, 476, "both resolve to →", 9.5, 500, SLATE, "middle"))
    p, w_ = _pill(0, 0, "the IR + verification layer", PRIMARY, PAPER, 10.5, 24, 14, 600)
    f.add(_pill(W / 2 - w_ / 2, 484, "the IR + verification layer", PRIMARY,
                PAPER, 10.5, 24, 14, 600)[0])
    return f


# --------------------------------------------------------------------------- #
# V6 — Design-principles board
# --------------------------------------------------------------------------- #
def v6():
    f = Fig("V6", "The beliefs the system is built on",
            "Eight principles that decide every tradeoff",
            628,
            "When two options conflict, these rank the decision. Reproducibility "
            "and loud failure outrank convenience; explicit data outranks clever "
            "implicit behavior.")
    items = [
        ("The IR is truth", "authoring is sugar; the contract is the data that renders.", "contract", PRIMARY),
        ("Reproducibility is a feature", "byte-identical, or the asset isn't done.", "hash", PRIMARY),
        ("Declared over accidental", "variation is seeded and traceable, never leaked.", "branch", TEAL),
        ("Fail loud and local", "missing or unsupported → line-cited errors, never silent swaps.", "shield", DANGER),
        ("LLM output is untrusted", "verification is a first-class design concern.", "check", VIOLET),
        ("Explicit over implicit", "every render-affecting choice is visible in the IR.", "eye", AMBER),
        ("Determinism is checked", "cross-environment identity is proven by a gate, not assumed.", "gauge", VIOLET),
        ("Scope is a choice", "non-vocal by design — depth over surface area.", "scope", SLATE),
    ]
    cw, ch, gx, gy = 314, 96, 20, 18
    x0 = (W - (2 * cw + gx)) / 2
    y0 = 112
    for i, (t, d, ic, col) in enumerate(items):
        r, c = divmod(i, 2)
        x = x0 + c * (cw + gx)
        y = y0 + r * (ch + gy)
        f.add(card(x, y, cw, ch, fill=PAPER, stroke=HAIR, sw=1.2, rx=10, accent=col))
        f.add(rect(x + 18, y + 18, 34, 34, fill=PAPER, stroke="none"))
        f.add(icon(ic, x + 18, y + 18, 30, col, 1.8))
        f.add(text(x + 64, y + 34, t, 13.5, 600, INK))
        ps, _ = paragraph(x + 64, y + 54, d, 10, cw - 84, 400, INK_SOFT, 1.4)
        f.add(ps)
        f.add(text(x + cw - 20, y + 30, f"{i+1:02d}", 10, 700, HAIR2, "end", mono=True))
    return f


# --------------------------------------------------------------------------- #
# V7 — Implementation & evolution roadmap
# --------------------------------------------------------------------------- #
def v7():
    f = Fig("V7", "A path that stays verifiable at every step",
            "Near-, mid- and long-term direction over a single spine",
            600,
            "The contract, determinism and the render-ready gate come first "
            "because everything later leans on them. Each phase ships whole and "
            "stays reproducible; nothing is deferred into an unverifiable future.")
    phases = [
        ("NEAR", "Foundation", PRIMARY, PRIMARY_T,
         ["IR schema + canonical hashing", "seed lineage; no ambient entropy",
          "validate = render-ready", "core seeded synthesis"]),
        ("MID", "Depth", AMBER, AMBER_T,
         ["content-addressed sampling", "performance & dynamics model",
          "mix · rooms · loudness targeting", "variation at scale + interop"]),
        ("LONG", "Reach", VIOLET, VIOLET_T,
         ["recorded material as hashed layers", "richer spatialization & rooms",
          "lossless delivery inside provenance", "deeper agent analyze→repair loops"]),
    ]
    colw = (W - 2 * PAD - 2 * 24) / 3
    y = 128
    spine = y + 20
    f.add(line(PAD + 10, spine, W - PAD - 10, spine, HAIR2, 1.6))
    for i, (tag, name, col, tint, items) in enumerate(phases):
        x = PAD + i * (colw + 24)
        f.add(circle(x + 18, spine, 7, fill=col, stroke=PAPER, sw=2))
        p, w_ = _pill(x + 34, spine - 12, f"{tag} · {name}", col, PAPER, 10.5, 24, 13, 600)
        f.add(p)
        by = spine + 30
        f.add(card(x, by, colw, 250, fill=tint, stroke="none", rx=11))
        yy = by + 30
        for it in items:
            f.add(circle(x + 24, yy - 4, 2.6, fill=col))
            ps, h = paragraph(x + 38, yy, it, 11, colw - 56, 500, INK, 1.35)
            f.add(ps)
            yy += max(28, h + 12)
    # architecture posture footer
    ay = spine + 300
    f.add(rect(PAD, ay, W - 2 * PAD, 40, fill=PANEL, rx=8))
    f.add(text(PAD + 16, ay + 17, "ARCHITECTURE POSTURE", 9.5, 700, SLATE, spacing=1))
    f.add(text(PAD + 16, ay + 31,
               "a pure, layered compiler + engine around a strict central schema; "
               "deterministic kernels; content-addressed stores; policy-gated plan; "
               "manifest-driven provenance.", 9.8, 400, INK_SOFT))
    return f


# --------------------------------------------------------------------------- #
# V8 — Risk & tradeoff matrix
# --------------------------------------------------------------------------- #
def v8():
    f = Fig("V8", "Honest boundaries, and how each is held",
            "The constraints that shape the system — and the deliberate response to each",
            578,
            "None of these are hidden. Each limit is met by making the boundary "
            "explicit and auditable rather than papering over it — the same loud-"
            "failure stance the whole system is built on.")
    rows = [
        ("Cross-platform float identity", "reproducibility can vary by environment",
         "the verify gate proves identity per environment, rather than assuming it", VIOLET),
        ("Loudness & limiting", "production-consistent, not a certified meter",
         "manifests record measured values for reference against compliant meters", PRIMARY),
        ("Finite sampled sustains", "held notes can outrun a non-looping sample",
         "the plan detects the gap and warns or refuses, per policy", DANGER),
        ("Native DSP kernels", "some voices/effects need a compiler",
         "they fail loud — never a silent substitution of different audio", DANGER),
        ("Lossy delivery (MP3)", "sits outside the byte-hash guarantee",
         "provenance is carried in the file's metadata instead", AMBER),
        ("Non-vocal scope", "voice and lyrics are out of scope",
         "a deliberate boundary — depth of craft over breadth of surface", SLATE),
    ]
    # header
    cols = [(PAD, 250, "CONSTRAINT"), (PAD + 262, 226, "THE LIMIT"),
            (PAD + 262 + 238, W - PAD - (PAD + 262 + 238), "HOW IT'S HELD")]
    y = 112
    for x, w_, h in cols:
        f.add(text(x + (14 if h != "CONSTRAINT" else 0), y + 12, h, 10, 700, SLATE, spacing=1))
    y = 132
    rh = 62
    for i, (c, limit, mit, col) in enumerate(rows):
        yy = y + i * rh
        if i % 2 == 0:
            f.add(rect(PAD, yy, W - 2 * PAD, rh - 8, fill=PANEL, rx=7, opacity=0.55))
        f.add(rect(PAD + 4, yy + 12, 3, rh - 32, fill=col, rx=1.5))
        ps, _ = paragraph(PAD + 18, yy + 24, c, 11.4, 232, 600, INK, 1.3)
        f.add(ps)
        ps2, _ = paragraph(cols[1][0] + 14, yy + 22, limit, 10, 210, 400, INK_SOFT, 1.32)
        f.add(ps2)
        ps3, _ = paragraph(cols[2][0] + 14, yy + 22, mit, 10, cols[2][1] - 18, 400, INK, 1.32)
        f.add(ps3)
        f.add(line(PAD, yy + rh - 8, W - PAD, yy + rh - 8, HAIR, 0.8))
    return f


BUILDERS = {"V1": v1, "V2": v2, "V3": v3, "V4": v4,
            "V5": v5, "V6": v6, "V7": v7, "V8": v8}

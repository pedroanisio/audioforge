"""Author the concept paper: dense 12-section prose paginated to A4 with the
eight vector figures embedded, assembled to a single vector PDF (cairosvg per
page, merged with pdfunite). Pure vector throughout.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import diagrams as D
import kit as K
from kit import (AMBER, HAIR, HAIR2, INK, INK_SOFT, PANEL, PAPER, PRIMARY,
                 PRIMARY_D, PRIMARY_T, SLATE, TEAL, VIOLET, circle, line,
                 measure, paragraph, rect, svg_doc, text, wrap)

CW = K.CONTENT_W                 # 654
LX = K.MARGIN_X                  # 70
TOP = K.MARGIN_TOP               # 74
BOT = K.PAGE_H - K.MARGIN_BOT    # 1057
BODY = 10.8
LEAD = 1.6

# --------------------------------------------------------------------------- #
# content — the twelve sections. blocks: (kind, *args)
# --------------------------------------------------------------------------- #
SECTIONS = [
 ("Core concept", [
   ("lead", "AudioForge is a production audio engine in which sound is "
    "compiled, not recorded: every asset is a build artifact, reproducible "
    "byte-for-byte from an inspectable contract, and authored as readily by "
    "an AI agent as by a person."),
   ("p", "Most generated audio arrives as an opaque file — the end of a "
    "session that lived in someone's memory and one particular arrangement of "
    "tools. AudioForge replaces that with a pipeline that behaves like a "
    "compiler. A concise source language states intent; it compiles to a JSON "
    "intermediate representation — the IR — that is the single, explicit "
    "ground truth for what will be produced. The engine renders that IR to a "
    "WAV file and a manifest recording the source's content hash and the "
    "output's checksum. Given the same source and the same engine, the same "
    "bytes come out every time."),
   ("p", "The move is small to state and large in consequence. When the "
    "artifact is a build, everything that follows from build systems becomes "
    "available to sound: diffs, review, provenance, caching, regression gates, "
    "and machine authorship. Creative intent stays first-class — but intent "
    "must become explicit data before it can play, so nothing that affects the "
    "result stays hidden. The scope is deliberately non-vocal: music, sound "
    "design, effects, ambience, loops, cues, and sonic identity, rather than "
    "voice or lyrics."),
   ("fig", "V1"),
 ]),
 ("The problem", [
   ("p", "Production audio is trusted to a process that cannot keep its "
    "promises. A finished sound is the residue of a manual session — plugin "
    "states, tool versions, hand-tuned moves, and a good deal of memory. "
    "Reproducing it later is a negotiation, not a guarantee. When an asset "
    "must change, the team cannot answer the questions that matter: what "
    "changed, why, and whether the new version still matches the original "
    "intent."),
   ("p", "Two forces make this worse. First, randomness leaks. Noise, reverb "
    "tails, dither, and plugin entropy are typically drawn from the wall clock "
    "or a global generator, so “the same project” produces different bytes on "
    "different runs. Variation that should be a deliberate, traceable choice "
    "arrives instead as drift no one asked for. Second, the producer is "
    "increasingly not a person. AI agents now generate content directly, but "
    "they have no structured, inspectable, verifiable surface for audio — they "
    "are left driving interfaces built for humans or emitting blobs no "
    "pipeline can check."),
   ("p", "That last point compounds the rest. Models of this class produce "
    "errors as a statistical property, not an exception: omissions, "
    "misreadings, silent partial failures. A pipeline that consumes model "
    "output without verifying it has not made a small oversight; it has left "
    "out a load-bearing layer. The problem is urgent now because the volume of "
    "generated audio, the number of non-human producers, and the demand for "
    "provenance are all rising at once."),
   ("fig", "V2"),
 ]),
 ("Intended users", [
   ("p", "AudioForge serves three audiences whose needs converge on the same "
    "properties from different directions."),
   ("h2", "Production teams"),
   ("p", "People responsible for delivering audio assets at volume and "
    "standing behind them. They need outputs they can reproduce on demand, "
    "stems they can re-mix, manifests they can audit, and a way to prove a "
    "delivery still matches what was approved. Their enemy is silent change."),
   ("h2", "Developers and pipeline engineers"),
   ("p", "People who wire audio into build systems, content pipelines, and "
    "games. They want sound to behave like every other build output: "
    "deterministic, cacheable, diffable, and guarded by tests. Their enemy is "
    "non-determinism that cannot be gated."),
   ("h2", "AI agents and their builders"),
   ("p", "Autonomous producers and the teams who deploy them. They need a "
    "surface they can read and write directly — a contract with explicit "
    "fields, structured diagnostics, and a validation step that means “this "
    "will render.” Their enemy is ambiguity with no human present to absorb "
    "it."),
 ]),
 ("Value proposition", [
   ("p", "The same guarantee pays out differently to each audience."),
   ("kv", "For production teams", "Trust becomes mechanical. Every delivery "
    "carries a hash of its source and a checksum of its output; two renders "
    "compare byte-for-byte; variants and cutdowns inherit a documented "
    "lineage. “Reproduce the approved version” is a command, not an "
    "archaeology project."),
   ("kv", "For engineers", "Audio joins the build. A verify step re-renders "
    "from source and compares bytes, turning drift into a failing check rather "
    "than a late surprise. Determinism holds within an environment and is "
    "proven across environments by that same gate, so audio can live in CI "
    "beside code."),
   ("kv", "For agents", "The surface is safe to author against. The contract "
    "is explicit and diffable; validation binds real resources and returns a "
    "true render-ready predicate; every problem comes back as structured, "
    "line-cited feedback rather than a crash. An agent can propose, inspect, "
    "and verify its own output before anything reaches production."),
   ("call", "The common thread: the file stops being the source of truth. "
    "The contract is."),
 ]),
 ("Operating model", [
   ("p", "The system runs as a chain of explicit stages, each producing an "
    "artifact the next stage — and any reviewer — can inspect."),
   ("ol", [
     ("Author", "a concise language expresses intent for people and agents; "
      "high-level ideas are permitted, but only as sugar."),
     ("Compile", "sugar expands into explicit parameters and the IR is "
      "canonically hashed, with the engine version folded in, so any change "
      "that could alter the bytes changes the identity."),
     ("Validate", "beyond a shape check, validation binds every resource the "
      "render will touch; a pass is a true statement that the asset will "
      "render, and problems return as line-cited diagnostics."),
     ("Plan", "a render plan records each routing decision, the evidence "
      "behind it, and any policy gates — a reviewable account of intent before "
      "action."),
     ("Render", "synthesis, sampling, performance, mixing, space, and "
      "mastering run as deterministic computation, every random path seeded "
      "from the contract hash."),
     ("Deliver & verify", "the output is a WAV plus a manifest of hashes, "
      "loudness, and markers; verification re-renders and compares bytes — the "
      "gate against stale or drifted results."),
   ]),
   ("fig", "V3"),
 ]),
 ("Key capabilities", [
   ("p", "The capabilities are not a feature list bolted together; they "
    "compose because they all read from and write to the same contract. Each "
    "resolves into the explicit IR, which is exactly why combining them "
    "produces no surprises."),
   ("ul", [
     "The contract — macros, emotional targets, motifs, and style resolve at "
     "compile time into explicit parameters, so the IR always says exactly "
     "what will render.",
     "Determinism — one seed lineage rooted in the contract hash makes noise, "
     "dither, round-robins, and reverb tails reproducible.",
     "Verification — validation-as-render-ready, the render plan, and the "
     "byte-compare gate, with policy controls that warn or refuse at a "
     "boundary.",
     "Sound generation — seeded synthesis alongside a content-addressed "
     "sampler that pins instrument libraries by hash.",
     "Expression — groove, humanization, dynamics-as-timbre, legato, and "
     "section ensembles, all expanded into inspectable values.",
     "Mix, space, and master — buses with shared processing, sidechain "
     "control, equalization, loudness targeting, and physically-motivated "
     "rooms.",
     "Variation at scale — seeded variants, structural choice sets, campaign "
     "cutdowns, and intensity ladders, each hash-tracked with lineage.",
     "Interoperation and delivery — standard interchange in and out, a "
     "round-trip back to source, and presets that package tagged "
     "distributables.",
   ]),
   ("fig", "V4"),
 ]),
 ("Experience for AI agents", [
   ("p", "For an agent, AudioForge is an environment designed to be perceived, "
    "acted upon, and trusted without a human in the loop."),
   ("h2", "Perceive"),
   ("p", "The agent reads the IR directly and consults a capability manifest "
    "that enumerates the available primitives and their parameters. "
    "Diagnostics are structured and cite exact source locations; the render "
    "plan exposes every routing decision and its evidence; the manifest can "
    "carry analysis features and recommendations that feed a critique loop."),
   ("h2", "Act"),
   ("p", "The agent authors the source or emits the IR outright, and mutates "
    "it through schema-checked edits. Authoring never raises on imperfect "
    "input — every issue returns as a structured diagnostic — so the agent "
    "iterates against feedback instead of exceptions."),
   ("h2", "Verify and benefit"),
   ("p", "Because model output is treated as untrusted by default, the "
    "agent's work passes through the same validation and byte-compare gate as "
    "anyone's. The payoff is a closed loop — propose, inspect, verify, repair "
    "— a way to produce audio that is safe to drop into a pipeline precisely "
    "because its correctness is checked, not assumed."),
 ]),
 ("Experience for human operators", [
   ("p", "For a person, the system trades the reassurance of a familiar "
    "interface for something more durable: control that leaves a record."),
   ("h2", "Direct"),
   ("p", "Operators write austere, high-level intent — emotional targets, "
    "intensity shapes, motifs, style — and watch it expand into explicit, "
    "reviewable parameters. Nothing meaningful happens off the page."),
   ("h2", "Oversee"),
   ("p", "Manifests, markers, and loudness reports make each render legible; "
    "two renders can be diffed; the verify gate guards deliveries in "
    "continuous integration. Oversight is reading and comparing artifacts, not "
    "trusting a memory."),
   ("h2", "Work with"),
   ("p", "A software interface and command surface cover validation, "
    "compilation, rendering, batching, campaigns, and verification, alongside "
    "preview and delivery presets. The operator's role shifts from performing "
    "a session to directing and reviewing a build."),
   ("fig", "V5"),
 ]),
 ("Design principles", [
   ("p", "A handful of beliefs decide the tradeoffs, and they are ranked so "
    "conflicts resolve predictably — reproducibility and loud failure outrank "
    "convenience; explicit data outranks clever implicit behavior."),
   ("ul", [
     "The IR is truth — authoring is convenience; the contract is the data "
     "that renders.",
     "Reproducibility is a product feature — an output is not finished until "
     "it can be recreated and verified.",
     "Declared variation beats accidental drift — every stochastic element is "
     "seeded and traceable.",
     "Failure is loud and local — missing resources, ambiguity, and "
     "unsupported requests produce line-cited errors, never a silent swap.",
     "Model output is untrusted by default — verification is a first-class "
     "design concern, on par with input validation.",
     "Explicit over implicit — every choice that affects the result is "
     "visible in the contract.",
     "Determinism is checked, not assumed — cross-environment identity is "
     "proven by a gate.",
     "Scope is a decision — non-vocal by design, depth of craft over breadth "
     "of surface.",
   ]),
   ("fig", "V6"),
 ]),
 ("Implementation direction", [
   ("p", "The architecture posture is a pure, layered compiler and engine "
    "organized around a strict central schema. Authoring surfaces sit at the "
    "top; a canonical, hashed IR sits at the center; deterministic "
    "signal-processing kernels sit below, with any that require native "
    "compilation failing loudly rather than substituting different audio. "
    "Resources — samples, instrument libraries, impulse responses — live in "
    "content-addressed stores whose hashes participate in the asset's "
    "identity. A policy-gated render plan sits between validation and "
    "rendering; a manifest carries provenance out the other side."),
   ("p", "Sequencing follows dependency, not appetite. The contract, the "
    "determinism guarantee, and render-ready validation come first, because "
    "everything later leans on them. Sampling and libraries, the performance "
    "and dynamics model, mixing, rooms, loudness, variation at scale, and "
    "interoperation build on that base. Broader palette, richer "
    "spatialization, lossless delivery inside a provenance envelope, and "
    "deeper agent loops come last. Each phase ships as a whole and stays "
    "reproducible; nothing is postponed into an unverifiable future."),
   ("fig", "V7"),
 ]),
 ("Risks, constraints, tradeoffs", [
   ("p", "The boundaries are stated plainly, because hiding them would violate "
    "the system's own stance."),
   ("ul", [
     "Cross-platform floating-point identity can vary by environment — proven "
     "per environment with the verify gate rather than assumed universally.",
     "Loudness measurement and limiting are production-consistent "
     "approximations, not certified metering — manifests record measured "
     "values for checking against compliant meters.",
     "Sampled sustains are finite; a held note can outrun a non-looping "
     "sample — the render plan detects the gap and, by policy, warns or "
     "refuses rather than emitting unintended silence.",
     "Some voices and effects depend on native kernels that need a compiler — "
     "they fail loudly rather than silently substituting different audio.",
     "Lossy delivery formats sit outside the byte-hash guarantee — provenance "
     "is carried in the delivered file's metadata instead.",
     "The non-vocal scope is a deliberate constraint — it concentrates craft "
     "rather than spreading it thin.",
   ]),
   ("call", "Every limit is met the same way: make the boundary explicit and "
    "auditable, rather than papering over it."),
   ("fig", "V8"),
 ]),
 ("Evolution paths", [
   ("p", "The concept has room to grow without loosening its guarantees."),
   ("ul", [
     "Recorded material enters cleanly as content-addressed sample layers, "
     "bringing field recordings and live takes under the same hash discipline.",
     "Spatialization deepens toward full-sphere formats and a wider library "
     "of measured rooms.",
     "Delivery gains lossless, encoder-independent paths wrapped in a "
     "provenance envelope, extending trust beyond the raw byte hash.",
     "Agent loops grow richer — analysis, targeted repair, and multi-asset "
     "campaigns — turning the critique cycle into a standing capability.",
     "A shared capability and interchange vocabulary lets independent tools "
     "and agents cooperate around the same contract.",
   ]),
   ("call", "In every direction the invariant holds: whatever is added must "
    "remain inspectable, seeded, and verifiable. That constraint is not a "
    "limit on the idea — it is the idea."),
 ]),
]


# --------------------------------------------------------------------------- #
# block height + render
# --------------------------------------------------------------------------- #
def _wraph(s, size, w, weight=400, italic=False, lead=LEAD):
    return len(wrap(s, size, w, weight, italic)) * size * lead


def block_height(b) -> float:
    k = b[0]
    if k == "lead":
        return _wraph(b[1], 14.5, CW, 500, lead=1.5) + 18
    if k == "p":
        return _wraph(b[1], BODY, CW) + 11
    if k == "h2":
        return 30
    if k == "kv":
        return max(_wraph(b[2], BODY, CW - 150) + 6, 24) + 16
    if k == "call":
        return _wraph(b[1], 12.5, CW - 60, 500, italic=True, lead=1.5) + 34
    if k == "ul":
        return sum(_wraph("• " + it, BODY, CW - 22) + 8 for it in b[1]) + 6
    if k == "ol":
        return sum(max(_wraph(d, BODY, CW - 132) + 6, 22) + 12 for _, d in b[1]) + 4
    if k == "fig":
        fig = D.BUILDERS[b[1]]()
        return CW * fig.H / D.W + 16
    return 0


def render_block(b, x, y) -> tuple[str, float]:
    k = b[0]
    if k == "lead":
        s, h = paragraph(x, y + 13, b[1], 14.5, CW, 500, INK, 1.5)
        bar = rect(x - 14, y + 1, 3.5, h - 2, fill=PRIMARY, rx=1.5)
        return bar + s, h + 18
    if k == "p":
        s, h = paragraph(x, y + 11, b[1], BODY, CW, 400, INK_SOFT, LEAD)
        return s, h + 11
    if k == "h2":
        return (text(x, y + 20, b[1], 13, 600, PRIMARY_D)
                + line(x, y + 26, x + CW, y + 26, HAIR, 0.8)), 30
    if k == "kv":
        lbl = text(x, y + 18, b[1], 11, 600, INK)
        s, h = paragraph(x + 150, y + 12, b[2], BODY, CW - 150, 400, INK_SOFT, LEAD)
        return lbl + s, max(h, 24) + 16
    if k == "call":
        inner = _wraph(b[1], 12.5, CW - 60, 500, italic=True, lead=1.5)
        box = rect(x, y + 6, CW, inner + 26, fill=PRIMARY_T, rx=9)
        bar = rect(x, y + 6, 3.5, inner + 26, fill=PRIMARY)
        s, _ = paragraph(x + 26, y + 26, b[1], 12.5, CW - 60, 500, PRIMARY_D,
                         1.5, italic=True)
        return box + bar + s, inner + 26 + 16
    if k == "ul":
        out, yy = [], y + 4
        for it in b[1]:
            out.append(circle(x + 4, yy + BODY * 0.42, 2.1, fill=PRIMARY))
            s, h = paragraph(x + 18, yy + BODY, it, BODY, CW - 22, 400, INK_SOFT, LEAD)
            out.append(s)
            yy += h + 8
        return "".join(out), yy - y + 2
    if k == "ol":
        out, yy = [], y + 2
        for i, (t, d) in enumerate(b[1]):
            out.append(circle(x + 9, yy + 9, 9.5, fill=PRIMARY_T, stroke=PRIMARY, sw=1.3))
            out.append(text(x + 9, yy + 12.5, str(i + 1), 9.5, 700, PRIMARY_D, "middle"))
            out.append(text(x + 26, yy + 12.5, t, BODY, 600, INK))
            s, h = paragraph(x + 26, yy + 12.5 + 15, d, BODY, CW - 132, 400, INK_SOFT, 1.5)
            out.append(s)
            yy += max(h + 15, 22) + 12
        return "".join(out), yy - y + 2
    if k == "fig":
        fig = D.BUILDERS[b[1]]()
        scale = CW / D.W
        h = fig.H * scale
        nested = (f'<svg x="{x}" y="{y+8}" width="{CW}" height="{h:.1f}" '
                  f'viewBox="0 0 {D.W} {fig.H}">{fig.render()}</svg>')
        return nested, h + 16
    return "", 0


# --------------------------------------------------------------------------- #
# page chrome
# --------------------------------------------------------------------------- #
def page_chrome(pageno, running):
    s = [line(LX, TOP - 20, K.PAGE_W - LX, TOP - 20, HAIR, 1)]
    s.append(text(LX, TOP - 27, "AUDIOFORGE", 8.4, 700, PRIMARY, spacing=1.4))
    s.append(text(LX + measure("AUDIOFORGE", 8.4, 700, spacing=1.4) + 8,
                  TOP - 27, "· CONCEPT PAPER", 8.4, 500, SLATE, spacing=1.4))
    s.append(text(K.PAGE_W - LX, TOP - 27, running, 8.4, 500, SLATE, "end",
                  spacing=0.6))
    s.append(line(LX, BOT + 22, K.PAGE_W - LX, BOT + 22, HAIR, 1))
    s.append(text(K.PAGE_W - LX, BOT + 36, f"{pageno:02d}", 9, 600, SLATE, "end",
                  mono=True))
    s.append(text(LX, BOT + 36, "Sound, compiled — not recorded", 8.6, 400,
                  K.FAINT, italic=True))
    return "".join(s)


def section_header(x, y, num, title):
    s = rect(x, y, 26, 26, fill=PRIMARY, rx=7)
    s += text(x + 13, y + 18, f"{num}", 13, 700, PAPER, "middle", mono=True)
    s += text(x + 38, y + 13, "SECTION", 8, 600, SLATE, spacing=1.6)
    s += text(x + 38, y + 26, title, 17.5, 600, INK)
    s += line(x, y + 40, x + CW, y + 40, HAIR2, 1.2)
    return s, 58


# --------------------------------------------------------------------------- #
# cover
# --------------------------------------------------------------------------- #
def cover_page() -> str:
    s = [rect(0, 0, K.PAGE_W, K.PAGE_H, fill=PAPER)]
    # top hairline band
    s.append(rect(0, 0, K.PAGE_W, 8, fill=PRIMARY))
    s.append(text(LX, 96, "CONCEPT PAPER", 11, 700, PRIMARY, spacing=3))
    s.append(text(LX, 120, "Non-vocal audio · deterministic · agent-native",
                  11, 400, SLATE, spacing=0.5))
    # title
    s.append(text(LX, 240, "AudioForge", 62, 600, INK))
    s.append(text(LX, 288, "Sound, compiled — not recorded.", 22, 400, PRIMARY_D))
    # thesis
    th, _ = paragraph(LX, 350, "A production audio engine in which every asset "
                      "is a build artifact — reproducible byte-for-byte from an "
                      "inspectable contract, and authored as readily by an AI "
                      "agent as by a person.", 15, CW - 40, 400, INK_SOFT, 1.6)
    s.append(th)
    # embed V1 keyframe as the cover hero
    fig = D.v1()
    scale = CW / D.W
    s.append(f'<svg x="{LX}" y="452" width="{CW}" height="{fig.H*scale:.1f}" '
             f'viewBox="0 0 {D.W} {fig.H}">{fig.render()}</svg>')
    # meta strip
    my = 452 + fig.H * scale + 40
    for i, (k, v) in enumerate([("PIPELINE", ".af → IR → WAV + manifest"),
                                ("GUARANTEE", "same source + engine → same bytes"),
                                ("FOR", "teams · engineers · AI agents")]):
        cx = LX + i * (CW / 3)
        s.append(text(cx, my, k, 8.5, 700, PRIMARY, spacing=1.4))
        s.append(text(cx, my + 16, v, 10.5, 400, INK_SOFT))
    s.append(line(LX, my + 34, K.PAGE_W - LX, my + 34, HAIR, 1))
    s.append(text(LX, my + 54, "A crystallized concept — problem, model, "
                  "capabilities, experience, principles, direction.", 10.5, 400,
                  SLATE, italic=True))
    s.append(text(K.PAGE_W - LX, K.PAGE_H - 40,
                  "eight vector figures · V1–V8", 9, 500, SLATE, "end", mono=True))
    return svg_doc(K.PAGE_W, K.PAGE_H, "".join(s), bg=None)


# --------------------------------------------------------------------------- #
# paginate + build
# --------------------------------------------------------------------------- #
def build(outdir: Path):
    svgdir = outdir / "svg"
    svgdir.mkdir(parents=True, exist_ok=True)
    pages: list[str] = []
    body: list[str] = []
    y = TOP
    running = "Overview"

    def flush():
        nonlocal body
        if body:
            pages.append("".join(body))
            body = []

    for num, (title, blocks) in enumerate(SECTIONS, 1):
        hh = 58
        # keep section header with its first block
        first_h = block_height(blocks[0]) if blocks else 0
        if y + hh + min(first_h, 120) > BOT:
            flush()
            y = TOP
        if not body:
            body.append("__CHROME__")
        running = f"{num:02d} · {title}"
        hdr, dh = section_header(LX, y, num, title)
        body.append(hdr)
        y += dh + 6
        for b in blocks:
            h = block_height(b)
            if y + h > BOT and b[0] != "h2":
                flush()
                y = TOP
                body.append("__CHROME__")
                # repeat a light running header only (no section title reprint)
            elif y + h > BOT:
                flush()
                y = TOP
                body.append("__CHROME__")
            svg, used = render_block(b, LX, y)
            body.append(svg)
            y += used
        y += 16
    flush()

    # stamp chrome with page numbers + running titles
    part_pdfs = []
    cov = svgdir / "audioforge-concept-paper-cover.svg"
    cov.write_text(cover_page())
    cpdf = svgdir / "_p00.pdf"
    K.to_pdf(cov, cpdf)
    part_pdfs.append(cpdf)

    for i, pg in enumerate(pages, 1):
        run = "Concept paper"
        pg = pg.replace("__CHROME__", page_chrome(i + 1, run), 1)
        pg = pg.replace("__CHROME__", page_chrome(i + 1, run))
        doc = svg_doc(K.PAGE_W, K.PAGE_H, pg, bg=PAPER)
        p = svgdir / f"_page{i:02d}.svg"
        p.write_text(doc)
        pdf = svgdir / f"_p{i:02d}.pdf"
        K.to_pdf(p, pdf)
        part_pdfs.append(pdf)

    out_pdf = outdir / "AudioForge-Concept-Paper.pdf"
    K.merge_pdfs(part_pdfs, out_pdf)
    # tidy temp
    for p in svgdir.glob("_p*.pdf"):
        p.unlink()
    for p in svgdir.glob("_page*.svg"):
        p.unlink()
    (svgdir / "audioforge-concept-paper-cover.svg").unlink(missing_ok=True)
    return out_pdf, len(pages) + 1


if __name__ == "__main__":
    out = Path(__file__).resolve().parent
    pdf, npages = build(out)
    print(f"built {pdf.name}: {npages} pages")

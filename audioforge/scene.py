"""scene-render integration: AudioForge as the resolver for generated audio.

The scene-render format (`<scene version="1.1">`, rendered by the Python, Rust, C
and JS scene engines) declares provider-made media as a `<generated>` asset. The
renderer never calls a provider: it reads `@cache` and refuses unless the file's
SHA-256 equals `@cacheSha256`; "a separate resolve step may fill the cache". This
module is that step for `provider="audioforge"`:

    <generated id="mus-bed" kind="music" provider="audioforge"
               model="bed/documentary-airy" prompt="duration=auto bpm=96 key='A minor'"
               seed="7" cache="assets/audio/gen/bed.wav" cacheSha256="0000…0000"/>

`resolve_scene()` renders each such asset's cue (`@model`, parameters from
`@prompt`, `@seed` as the performance seed) into `@cache`, then writes the file's
SHA-256 into `@cacheSha256` — editing only that attribute, so the rest of the
document (comments, layout) is untouched. `duration=auto` (or no duration at all
for beds and ambience) sizes the cue to the project: project duration minus the
start of the `audioTrack` that plays it. Sample rate and bit depth follow the
scene's `audioMix`. Re-running is incremental: an asset whose cache, provenance
sidecar and hash already agree is skipped. `check=True` reports stale assets
without rendering (for CI).
"""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .cues import (CueError, get_cue, params_hash, parse_params, render_cue,
                   resolve_params, sidecar_path)
from .version import ENGINE_VERSION

PROVIDER = "audioforge"
SCENE_COMMANDS = ("resolve", "add")                              # `audioforge scene <cmd>`
_AUTO_CATEGORIES = ("bed", "ambience")


class SceneError(ValueError):
    """The scene document cannot be resolved as written."""


@dataclass
class Resolution:
    asset_id: str
    cue: str
    cache: str
    status: str                     # rendered | pinned | up-to-date | stale | error
    params: dict = field(default_factory=dict)
    sha256: str | None = None
    message: str = ""

    def as_dict(self) -> dict:
        return {"asset": self.asset_id, "cue": self.cue, "cache": self.cache,
                "status": self.status, "params": self.params, "sha256": self.sha256,
                "message": self.message}


def _resolve_path(base: Path, src: str) -> Path:
    if src.startswith("file:"):
        return Path(unquote(urlsplit(src).path))
    if urlsplit(src).scheme:
        raise SceneError(f"cache {src!r}: only local paths can be written")
    p = Path(src)
    return p if p.is_absolute() else (base / p)


def _seconds(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:              # expressions / timecodes: not resolvable here
        return None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _request(root: ET.Element, asset: ET.Element) -> tuple:
    """(cue, resolved params, sample_rate, bit_depth) for one generated asset."""
    cue = get_cue(asset.get("model", ""))
    params = parse_params(asset.get("prompt") or "")
    if "seed" not in params and asset.get("seed") is not None:
        params["seed"] = asset.get("seed")
    if "duration" not in params and asset.get("duration") is not None:
        params["duration"] = asset.get("duration")
    if params.get("duration") in (None, "auto"):
        if params.get("duration") == "auto" or cue.category in _AUTO_CATEGORIES:
            params["duration"] = _auto_duration(root, asset.get("id", ""))
        else:
            params.pop("duration", None)        # the cue's own default length
    resolved = resolve_params(cue, params)
    mix = root.find("audioMix")
    sr = int(mix.get("sampleRate", "48000")) if mix is not None else 48000
    bits = int(mix.get("bitDepth", "24")) if mix is not None else 24
    return cue, resolved, sr, (16 if bits == 16 else 24)


def _auto_duration(root: ET.Element, asset_id: str) -> float:
    project = root.find("project")
    total = _seconds(project.get("duration")) if project is not None else None
    if not total:
        raise SceneError(f"{asset_id}: duration=auto needs <project duration=...>")
    start = 0.0
    for track in root.iter("audioTrack"):
        if track.get("asset") == asset_id:
            s = _seconds(track.get("start", "0"))
            clip_in = _seconds(track.get("clipIn", "0")) or 0.0
            start = (s or 0.0) - clip_in
            break
    return round(max(0.05, total - max(0.0, start)), 4)


def generated_assets(scene_path: str | Path) -> list[ET.Element]:
    """The `<generated provider="audioforge">` audio assets of a scene document."""
    root = ET.parse(scene_path).getroot()
    return [a for a in root.iter("generated")
            if a.get("provider") == PROVIDER and a.get("kind") in ("music", "sound-effect")]


def _set_attr(text: str, asset_id: str, name: str, value: str) -> str:
    """Set one attribute on the `<generated id="asset_id">` start tag in place."""
    tag_re = re.compile(r"<generated\b[^>]*?\bid\s*=\s*([\"'])" + re.escape(asset_id)
                        + r"\1[^>]*?/?>", re.S)
    m = tag_re.search(text)
    if not m:
        raise SceneError(f"{asset_id}: <generated> start tag not found for rewriting")
    tag = m.group(0)
    attr_re = re.compile(r"(\s" + re.escape(name) + r"\s*=\s*)([\"'])[^\"']*\2")
    if attr_re.search(tag):
        new_tag = attr_re.sub(lambda a: f'{a.group(1)}{a.group(2)}{value}{a.group(2)}', tag, 1)
    else:
        end = len(tag) - (2 if tag.endswith("/>") else 1)
        new_tag = tag[:end].rstrip() + f' {name}="{value}"' + tag[end:]
    return text[:m.start()] + new_tag + text[m.end():]


def _up_to_date(cache: Path, want_sha: str, p_hash: str) -> str | None:
    side = sidecar_path(cache)
    if not cache.is_file() or not side.is_file():
        return None
    try:
        info = json.loads(side.read_text())
    except (OSError, ValueError):
        return None
    digest = _sha256(cache)
    if (info.get("params_hash") == p_hash and info.get("engine_version") == ENGINE_VERSION
            and info.get("sha256") == digest):
        return digest if digest == want_sha else digest + ":attr"
    return None


def resolve_scene(scene_path: str | Path, *, check: bool = False,
                  force: bool = False) -> list[Resolution]:
    """Render missing/stale AudioForge cues of a scene and pin their hashes.

    check=True renders nothing and changes nothing; it reports `stale` for any
    asset whose cache, provenance or `cacheSha256` does not match its request."""
    scene_path = Path(scene_path)
    text = scene_path.read_text(encoding="utf-8")
    root = ET.fromstring(text.encode("utf-8"))
    base = scene_path.parent
    results: list[Resolution] = []
    new_text = text
    for asset in root.iter("generated"):
        if asset.get("provider") != PROVIDER or asset.get("kind") not in ("music", "sound-effect"):
            continue
        aid = asset.get("id", "")
        res = Resolution(aid, asset.get("model", ""), asset.get("cache", ""), "error")
        results.append(res)
        try:
            if not asset.get("cache"):
                raise SceneError(f"{aid}: @cache is required")
            cue, resolved, sr, bits = _request(root, asset)
            res.params = resolved
            cache = _resolve_path(base, asset.get("cache"))
            want = (asset.get("cacheSha256") or "").lower()
            p_hash = params_hash(cue, {**resolved, "_sr": sr, "_bits": bits})
            current = None if force else _up_to_date(cache, want, p_hash)
            if current and not current.endswith(":attr"):
                res.status, res.sha256 = "up-to-date", current
                continue
            if check:
                res.status = "stale"
                res.message = ("cacheSha256 differs from the cache" if current
                               else "cache missing or built from different parameters/engine")
                continue
            if current:                          # cache fine, attribute stale
                digest = current.split(":")[0]
            else:
                render_cue(cue.id, resolved, cache, sample_rate=sr, bit_depth=bits)
                side = sidecar_path(cache)
                info = json.loads(side.read_text())
                info["params_hash"] = p_hash       # request identity incl. format
                side.write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")
                digest = info["sha256"]
            new_text = _set_attr(new_text, aid, "cacheSha256", digest)
            res.status, res.sha256 = "rendered" if not current else "pinned", digest
        except (CueError, SceneError) as exc:
            res.status, res.message = "error", str(exc)
    if new_text != text and not check:
        ET.fromstring(new_text.encode("utf-8"))          # still well-formed
        tmp = scene_path.with_name(scene_path.name + ".tmp")
        tmp.write_text(new_text, encoding="utf-8")
        tmp.replace(scene_path)
    return results


# ------------------------------------------------------------------ snippets
def _xml_attr(value) -> str:
    return (str(value).replace("&", "&amp;").replace('"', "&quot;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def generated_snippet(cue_id: str, params: str | dict | None = None, *,
                      asset_id: str | None = None, cache: str | None = None,
                      sha256: str | None = None) -> str:
    """A `<generated provider="audioforge">` element for a scene's `<assets>`."""
    cue = get_cue(cue_id)
    given = parse_params(params)
    seed = given.pop("seed", None)
    if cue.category in _AUTO_CATEGORIES and "duration" not in given:
        given["duration"] = "auto"
    prompt = " ".join(f"{k}={_quote(v)}" for k, v in given.items())
    aid = asset_id or cue.id.replace("/", "-")
    path = cache or f"assets/audio/audioforge/{aid}.wav"
    attrs = [("id", aid), ("kind", cue.kind), ("provider", PROVIDER), ("model", cue.id)]
    if prompt:
        attrs.append(("prompt", prompt))
    if seed is not None:
        attrs.append(("seed", seed))
    attrs += [("cache", path), ("cacheSha256", sha256 or "0" * 64),
              ("license", f"Original; generated by AudioForge {ENGINE_VERSION} ({cue.id} v{cue.version})")]
    return "<generated " + " ".join(f'{k}="{_xml_attr(v)}"' for k, v in attrs) + "/>"


def _quote(v) -> str:
    s = str(v)
    return f"'{s}'" if " " in s else s


def audio_snippet(info: dict, *, asset_id: str, src: str) -> str:
    """An `<audio>` asset element for a WAV rendered by `render_cue` (plain file path)."""
    attrs = [("id", asset_id), ("src", src), ("duration", info["duration_s"]),
             ("sampleRate", info["sample_rate"]), ("channels", info["channels"])]
    if info.get("category") == "bed" and "bpm" in info.get("params", {}):
        attrs.append(("bpm", info["params"]["bpm"]))
    attrs.append(("license", f"Original; generated by AudioForge {info['engine_version']} "
                             f"({info['cue']} v{info['cue_version']}, sha256 {info['sha256'][:12]})"))
    return "<audio " + " ".join(f'{k}="{_xml_attr(v)}"' for k, v in attrs) + "/>"


def track_snippet(cue_id: str, asset_id: str) -> str:
    """A sensible `<audioTrack>` for the cue's role (music beds duck under VO buses)."""
    cue = get_cue(cue_id)
    role = {"bed": "music", "sting": "music", "ambience": "ambience"}.get(cue.category, "effects")
    attrs = [("id", f"trk-{asset_id}"), ("asset", asset_id), ("role", role), ("start", "0")]
    if cue.category == "bed":
        attrs += [("fadeIn", "1"), ("fadeOut", "2"), ("fadeCurve", "equal-power")]
    return "<audioTrack " + " ".join(f'{k}="{v}"' for k, v in attrs) + "/>"


# ------------------------------------------------------------------ editing
def add_cue(scene_path: str | Path, cue_id: str, params: str | dict | None = None, *,
            asset_id: str | None = None, cache: str | None = None,
            start: float = 0.0, gain_db: float | None = None, bus: str | None = None,
            duck_under: str | None = None, resolve: bool = True) -> list[Resolution]:
    """Insert a cue into a scene: a `<generated>` asset plus an `<audioTrack>`.

    Text is inserted before `</assets>` and `</audioMix>` (an `<audioMix>` is
    created before `</scene>` when the scene has none), matching the indentation
    of the closing tag; nothing else in the document changes. With resolve=True
    the new cue is rendered and its hash pinned right away."""
    scene_path = Path(scene_path)
    text = scene_path.read_text(encoding="utf-8")
    root = ET.fromstring(text.encode("utf-8"))
    cue = get_cue(cue_id)
    aid = asset_id or cue.id.replace("/", "-")
    if any(el.get("id") == aid for el in root.iter()):
        raise SceneError(f"id {aid!r} already exists in {scene_path.name}; pass another asset id")
    if root.find("assets") is None:
        raise SceneError(f"{scene_path.name} has no <assets> element")
    given = parse_params(params)
    if cue.category not in _AUTO_CATEGORIES:
        resolve_params(cue, given)                      # fail early on bad params
    asset_xml = generated_snippet(cue.id, given, asset_id=aid, cache=cache)
    track = track_snippet(cue.id, aid)
    extra = [f'start="{round(float(start), 4)}"']
    if gain_db is not None:
        extra.append(f'gain="{round(float(gain_db), 2)}"')
    if bus:
        extra.append(f'bus="{_xml_attr(bus)}"')
    if duck_under:
        extra.append(f'duckUnder="{_xml_attr(duck_under)}"')
    track = track.replace('start="0"', " ".join(extra))

    text = _insert_before_close(text, "assets", asset_xml)
    if root.find("audioMix") is not None:
        text = _insert_before_close(text, "audioMix", track)
    else:
        text = _insert_before_close(
            text, "scene", f'<audioMix sampleRate="48000" channels="2">\n    {track}\n  </audioMix>')
    ET.fromstring(text.encode("utf-8"))                  # still well-formed
    tmp = scene_path.with_name(scene_path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(scene_path)
    return resolve_scene(scene_path) if resolve else []


def _insert_before_close(text: str, tag: str, fragment: str) -> str:
    m = None
    for m in re.finditer(r"(?m)^([ \t]*)</" + tag + r"\s*>", text):
        pass
    if m is None:                                  # closing tag not at line start
        idx = text.rfind(f"</{tag}")
        if idx < 0:
            raise SceneError(f"</{tag}> not found")
        return text[:idx] + fragment + text[idx:]
    indent = m.group(1)
    child = indent + ("  " if "\t" not in indent else "\t")
    return text[:m.start()] + child + fragment + "\n" + text[m.start():]

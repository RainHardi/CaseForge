"""Brand kit: the brand rules a report must follow — colours, fonts, logo, layout habits and tone.

A kit can be typed in, loaded from a preset (brands/*.json), or pulled out of a brand-guidelines
document. Whatever the source, a person confirms it before it is used, and the report is checked
against it (contrast, banned words, sentence length).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .config import ROOT
from .llm import LLM

FONT_DIR = Path(__file__).parent / "render" / "fonts"
BUNDLED_FONTS = {
    "Manrope": "manrope", "Plus Jakarta Sans": "plus-jakarta-sans", "Inter": "inter",
    "Source Serif 4": "source-serif-4", "IBM Plex Sans": "ibm-plex-sans", "Space Grotesk": "space-grotesk",
    "DM Sans": "dm-sans",
}
PRESET_DIR = ROOT / "brands"


class Colors(BaseModel):
    primary: str = "#1B2A41"   # the brand colour: big numbers, accent shapes
    accent: str = "#E8A317"    # highlights, small marks
    ink: str = "#14161A"       # body text
    paper: str = "#FFFFFF"     # page background
    surface: str = "#F4F4F2"   # cards / panels
    muted: str = "#5F6470"     # captions, labels
    dark: str = "#111111"      # dark panels (cover band, conclusion)


class BrandKit(BaseModel):
    name: str = "Default"
    company: str = ""                     # who publishes the case study
    logo: str = ""                        # filename of an uploaded logo ('' = text wordmark)
    colors: Colors = Field(default_factory=Colors)
    heading_font: str = "Inter"
    body_font: str = "Inter"
    motif: Literal["hexagon", "circle", "bars", "none"] = "none"
    accent_bar: Literal["left", "top", "none"] = "none"
    logo_position: Literal["top-right", "top-left"] = "top-right"
    page_numbers: bool = True
    voice: Literal["we", "third person"] = "we"
    banned_words: list[str] = Field(default_factory=list)
    max_sentence_words: int = 28
    cta_text: str = ""                    # closing call to action, only if the guidelines give one
    rules: list[str] = Field(default_factory=list)  # other do/don't rules, shown to the reviewer

    def font_path(self, family: str) -> Path | None:
        slug = BUNDLED_FONTS.get(family)
        return FONT_DIR / slug if slug and (FONT_DIR / slug).exists() else None


# ------------------------------------------------------------------ presets
def presets() -> dict[str, BrandKit]:
    out = {}
    for p in sorted(PRESET_DIR.glob("*.json")):
        try:
            out[p.stem] = BrandKit.model_validate_json(p.read_text(encoding="utf-8"))
        except Exception:
            continue
    return out


def load(name_or_path: str) -> BrandKit:
    p = Path(name_or_path)
    if not p.exists():
        p = PRESET_DIR / f"{name_or_path}.json"
    return BrandKit.model_validate_json(p.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ from a guidelines document
EXTRACT_SYSTEM = """You read a company's brand guidelines and fill in a brand kit.
Only use what the guidelines say. Colours as #RRGGBB hex. Fonts: the family names as written.
primary = the main brand colour; accent = a secondary highlight colour; ink = body text colour;
paper = page background; surface = light card/panel colour; muted = caption colour; dark = darkest
brand colour for dark panels. If something is not stated, leave the default.
banned_words = words or phrases the guidelines say not to use. rules = other short do/don't rules.
cta_text = an official call to action or sign-off line, if one is given."""


def from_guidelines(text: str, llm: LLM | None, name: str = "Imported brand") -> BrandKit:
    if llm:
        kit = llm.generate_json(EXTRACT_SYSTEM, f"BRAND GUIDELINES:\n<<<\n{text[:20000]}\n>>>", BrandKit)
        kit.name = kit.name if kit.name not in ("", "Default") else name
        return kit
    return _offline_guidelines(text, name)


_ROLES = [("primary", r"primary|main|brand colou?r"), ("accent", r"accent|secondary|highlight"),
          ("ink", r"text|ink|body"), ("paper", r"background|paper|page"), ("dark", r"dark|black"),
          ("surface", r"surface|card|panel"), ("muted", r"muted|caption|grey|gray")]


def _offline_guidelines(text: str, name: str) -> BrandKit:
    kit = BrandKit(name=name)
    for line in text.splitlines():
        m = re.search(r"#[0-9a-fA-F]{6}\b", line)
        if not m:
            continue
        for role, pat in _ROLES:
            if re.search(pat, line, re.I):
                setattr(kit.colors, role, m.group(0).upper())
                break
    for fam in BUNDLED_FONTS:
        if re.search(rf"\b{re.escape(fam)}\b", text, re.I):
            if re.search(rf"(head|title|display)[^\n]*{re.escape(fam)}|{re.escape(fam)}[^\n]*(head|title|display)", text, re.I):
                kit.heading_font = fam
            if re.search(rf"(body|text|copy)[^\n]*{re.escape(fam)}|{re.escape(fam)}[^\n]*(body|text|copy)", text, re.I):
                kit.body_font = fam
    for line in text.splitlines():
        if re.search(r"\b(don't|do not|never|avoid)\s+(use|say|write)\b", line, re.I):
            quoted = re.findall(r"[\"“]([^\"”]+)[\"”]", line)
            kit.banned_words += [q.strip() for q in quoted][:8]
    return kit


# ------------------------------------------------------------------ checks
def _lum(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def readable_on(bg: str) -> str:
    """Black or white, whichever reads better on this background."""
    return "#111111" if contrast("#111111", bg) >= contrast("#FFFFFF", bg) else "#FFFFFF"


def kit_warnings(kit: BrandKit) -> list[str]:
    c, out = kit.colors, []
    if contrast(c.ink, c.paper) < 4.5:
        out.append(f"Body text {c.ink} on {c.paper} is hard to read (contrast {contrast(c.ink, c.paper):.1f}:1, needs 4.5).")
    if contrast(c.muted, c.paper) < 4.5:
        out.append(f"Caption colour {c.muted} is too light on {c.paper} ({contrast(c.muted, c.paper):.1f}:1).")
    if not kit.logo:
        out.append("No logo uploaded — the report uses the company name as a text logo.")
    for fam in {kit.heading_font, kit.body_font}:
        if fam not in BUNDLED_FONTS:
            out.append(f"Font '{fam}' isn't bundled; it loads from Google Fonts when online, else a fallback is used.")
    return out


def text_warnings(kit: BrandKit, texts: list[tuple[str, str]]) -> list[str]:
    """Tone rules on the report's words: banned words, sentence length, voice."""
    out = []
    for where, t in texts:
        low = t.lower()
        for w in kit.banned_words:
            if w and re.search(rf"\b{re.escape(w.lower())}\b", low):
                out.append(f"{where}: uses '{w}', which the brand guidelines ban")
        for s in re.split(r"(?<=[.!?])\s+", t):
            n = len(s.split())
            if n > kit.max_sentence_words:
                out.append(f"{where}: {n}-word sentence (brand limit {kit.max_sentence_words})")
        if kit.voice == "third person" and re.search(r"\b(we|our|us)\b", low):
            out.append(f"{where}: uses 'we' — the brand voice is third person")
    return out


def save(kit: BrandKit, path: Path) -> Path:
    path.write_text(kit.model_dump_json(indent=2), encoding="utf-8")
    return path


def as_dict(kit: BrandKit) -> dict:
    return json.loads(kit.model_dump_json())


# ------------------------------------------------------------------ no brand? an automatic one
# Picked from what the notes are about, so a logistics project and a clinic project don't look alike.
SECTORS = [  # (name, keywords, primary, accent, dark, heading font, body font, motif)
    ("logistics", r"logistic|fleet|freight|warehouse|deliver|route|dispatch|truck|shipping|supply chain",
     "#0F6B70", "#F28C38", "#0B2A33", "Plus Jakarta Sans", "Inter", "bars"),
    ("health", r"clinic|patient|hospital|health|medical|doctor|nurse|pharma|care",
     "#1F7A8C", "#7BC67E", "#0E2F3A", "DM Sans", "Source Serif 4", "circle"),
    ("finance", r"bank|financ|payment|insurance|invoice|accounting|loan|fintech|trading",
     "#1E3A8A", "#D4A017", "#0B1736", "IBM Plex Sans", "Source Serif 4", "bars"),
    ("retail", r"retail|e-?commerce|shop|store|customer|inventory|restaurant|menu|noodle|food",
     "#C2410C", "#FBBF24", "#2A1408", "Space Grotesk", "DM Sans", "circle"),
    ("education", r"student|school|universit|course|teacher|learning|education|campus",
     "#6D28D9", "#F59E0B", "#1E1035", "Manrope", "Source Serif 4", "hexagon"),
    ("industry", r"factory|manufactur|plant|energy|machine|sensor|production|maintenance",
     "#15803D", "#FACC15", "#0B2614", "Space Grotesk", "Inter", "bars"),
]
DEFAULT_SECTOR = ("technology", "", "#4F46E5", "#22D3EE", "#111633", "Inter", "Inter", "circle")


def _mix(hex_a: str, hex_b: str, t: float) -> str:
    a = [int(hex_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(hex_b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(a, b))


def _kit(name: str, company: str, primary: str, accent: str, dark: str, hf: str, bf: str, motif: str) -> BrandKit:
    return BrandKit(name=name, company=company,
                    colors=Colors(primary=primary, accent=accent, ink="#14161A", paper="#FFFFFF",
                                  surface=_mix(primary, "#FFFFFF", .92), muted="#5B6472", dark=dark),
                    heading_font=hf, body_font=bf, motif=motif, accent_bar="left" if motif == "hexagon" else "top")


def auto_brand(notes: str, company: str = "") -> BrandKit:
    """A tasteful look chosen from the notes' subject, for people who have no brand kit."""
    text = notes.lower()
    best = max(SECTORS, key=lambda s: len(re.findall(s[1], text)))
    sector = best if re.search(best[1], text) else DEFAULT_SECTOR
    name, _, p, a, d, hf, bf, motif = sector
    return _kit(f"Auto · {name}", publisher(company), p, a, d, hf, bf, motif)


def publisher(company: str) -> str:
    """The company name to print on a report — or "" when there is none. An account that never gave a
    company gets a workspace called "<person>'s workspace"; that is a label for the app, not a publisher,
    and a person's name must not end up in the corner of a client document."""
    c = (company or "").strip()
    return "" if re.search(r"['’]s workspace$", c, re.I) or c.lower() in ("your company", "my company") else c


def from_logo(data: bytes, name: str, company: str = "") -> BrandKit:
    """Upload a logo, get a brand kit: the logo's main colours become primary and accent."""
    from io import BytesIO
    import colorsys

    from PIL import Image

    img = Image.open(BytesIO(data)).convert("RGBA")
    img.thumbnail((96, 96))
    counts: dict[tuple[int, int, int], int] = {}
    sums: dict[tuple[int, int, int], list[int]] = {}
    pixels = img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata()
    for r, g, b, alpha in pixels:
        if alpha < 128:
            continue
        h, l, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        if sat < 0.25 or l > 0.92 or l < 0.08:   # skip white background, black text, greys
            continue
        key = (r // 24 * 24, g // 24 * 24, b // 24 * 24)
        counts[key] = counts.get(key, 0) + 1
        acc = sums.setdefault(key, [0, 0, 0])
        acc[0] += r; acc[1] += g; acc[2] += b  # noqa: E702
    ranked = [c for c, _ in sorted(counts.items(), key=lambda kv: -kv[1])]
    hexes = ["#%02X%02X%02X" % tuple(round(v / counts[c]) for v in sums[c]) for c in ranked]  # true colour, not bucket
    if not hexes:  # a black / grey logo: keep it sober
        return _kit(name, company or name, "#1F2937", "#E8A317", "#111827", "Inter", "Inter", "none")

    def hue(hx: str) -> float:
        return colorsys.rgb_to_hls(*(int(hx[i:i + 2], 16) / 255 for i in (1, 3, 5)))[0]

    primary = hexes[0]
    accent = next((x for x in hexes[1:] if min(abs(hue(x) - hue(primary)), 1 - abs(hue(x) - hue(primary))) > .08),
                  _mix(primary, "#FFFFFF", .45))
    dark = _mix(primary, "#000000", .78)
    kit = _kit(name, company or name, primary, accent, dark, "Inter", "Inter", "none")
    kit.accent_bar = "top"
    return kit

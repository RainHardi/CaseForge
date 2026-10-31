"""Website portfolio page (Target T-11): one self-contained HTML file, images embedded."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from jinja2 import Environment, select_autoescape

from ..models import SECTION_TITLES, ProjectRecord
from . import BRAND, require_approved

TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }}</title>
<style>
:root{--ink:{{ b.ink }};--accent:{{ b.accent }};--muted:{{ b.muted }};--soft:{{ b.soft }};--line:{{ b.line }};--bg:#fff}
@media (prefers-color-scheme: dark){:root{--ink:#E9ECF1;--muted:#A7B0BD;--soft:#1F2733;--line:#2E3845;--bg:#121820}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif}
header{background:{{ b.ink }};color:#fff;padding:56px 16px 40px;border-bottom:4px solid var(--accent)}
.wrap{max-width:820px;margin:0 auto;padding:0 16px}
.kicker{color:var(--accent);font-weight:700;letter-spacing:.12em;font-size:12px;text-transform:uppercase}
h1{font-size:clamp(28px,5vw,42px);line-height:1.15;margin:10px 0 12px}
.client{color:#C9D1DC}
.summary{background:var(--soft);border-left:4px solid var(--accent);padding:18px 20px;font-size:18px;margin:32px 0}
h2{font-size:20px;margin:36px 0 10px;padding-left:12px;border-left:3px solid var(--accent)}
.chips{display:flex;flex-wrap:wrap;gap:8px;padding:0;list-style:none}
.chips li{background:var(--soft);border:1px solid var(--line);border-radius:999px;padding:4px 12px;font-size:14px}
figure{margin:20px 0}figure img{max-width:100%;height:auto;border-radius:6px;border:1px solid var(--line)}
figcaption{color:var(--muted);font-size:14px;font-style:italic;margin-top:6px}
footer{color:var(--muted);font-size:13px;border-top:1px solid var(--line);margin:48px 0 32px;padding-top:16px}
.draft{background:#B3261E;color:#fff;text-align:center;padding:8px;font-weight:700}
</style></head><body>
{% if draft %}<div class="draft">DRAFT — NOT APPROVED — DO NOT PUBLISH</div>{% endif %}
<header><div class="wrap"><div class="kicker">Case study</div><h1>{{ title }}</h1>
<div class="client">Client: {{ client }}</div></div></header>
<main class="wrap">
{% if summary %}<p class="summary">{{ summary }}</p>{% endif %}
{% for s in sections %}
<section><h2>{{ s.title }}</h2>
{% if s.key == 'tools' %}<ul class="chips">{% for t in s.texts %}<li>{{ t }}</li>{% endfor %}</ul>
{% elif s.key in ('challenges','results') %}<ul>{% for t in s.texts %}<li>{{ t }}</li>{% endfor %}</ul>
{% else %}<p>{{ s.texts|join(' ') }}</p>{% endif %}
{% for img in s.images %}<figure><img src="{{ img.src }}" alt="{{ img.caption or 'Project image' }}">
{% if img.caption %}<figcaption>{{ img.caption }}</figcaption>{% endif %}</figure>{% endfor %}
</section>{% endfor %}
<footer>{{ footer }}</footer></main></body></html>"""


def _data_uri(path: Path) -> str | None:
    if not path.exists():
        return None
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def render_portfolio_page(record: ProjectRecord, image_dir: Path, out: Path, draft: bool = False) -> Path:
    require_approved(record, draft)
    sections = []
    for key in ["client_problem", "work_done", "technical_approach", "tools", "challenges", "results"]:
        texts = [c.text for c in record.active_claims(key)]
        if not texts:
            continue
        imgs = []
        for img in record.input.images:
            if img.section == key:
                src = _data_uri(image_dir / img.filename)
                if src:
                    imgs.append({"src": src, "caption": img.caption})
        sections.append({"key": key, "title": SECTION_TITLES[key], "texts": texts, "images": imgs})
    footer = (
        "Draft for review." if draft
        else f"Reviewed and approved by {record.approved_by} on {record.approved_at[:10]}."
    )
    html = Environment(autoescape=select_autoescape(default=True)).from_string(TEMPLATE).render(
        b=BRAND, draft=draft, title=record.input.title or "Untitled project",
        client=record.input.client_name or "Client confidential",
        summary=" ".join(c.text for c in record.active_claims("summary")),
        sections=sections, footer=footer,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out

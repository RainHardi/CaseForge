"""The proof sheet as a printable page (A4) — every sentence quoted from an approved case study."""

from __future__ import annotations

from datetime import date

from jinja2 import Environment, select_autoescape

from .verified import qr_svg

TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relevant work{% if s.query %}: {{ s.query }}{% endif %}</title>
<style>
@page{size:A4;margin:16mm 15mm}
:root{--ink:#14202E;--ink2:#4A5565;--muted:#6B7686;--line:#E3E1DA;--accent:#E8A33D;--soft:#F6F5F1;--ok:#1F7A4D}
*{box-sizing:border-box}
body{margin:0;background:#fff;color:var(--ink);font:10.5pt/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:180mm;margin:0 auto;padding:0 4mm}
header{border-bottom:3px solid var(--accent);padding:6mm 0 4mm;margin-bottom:5mm}
.kicker{font-size:8pt;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:700}
h1{font-size:20pt;line-height:1.15;margin:2mm 0 1mm}
.lead{color:var(--ink2);margin:0}
.case{display:grid;grid-template-columns:1fr 26mm;gap:5mm;padding:4mm 0 5mm;border-bottom:1px solid var(--line);break-inside:avoid}
.case:last-of-type{border-bottom:0}
h2{font-size:13pt;margin:0 0 1mm}
.meta{font-size:8.5pt;color:var(--muted);margin:0 0 2mm}
ul{margin:0;padding-left:5mm}li{margin:1.2mm 0}
li.metric{font-weight:650}
.tag{display:inline-block;font-size:7.5pt;font-weight:700;color:var(--ok);margin-left:1.5mm;white-space:nowrap}
.qr{text-align:center;font-size:7pt;color:var(--muted)}
.qr svg{width:24mm;height:24mm;display:block;margin:0 auto 1mm}
footer{margin-top:6mm;font-size:8.5pt;color:var(--muted);border-top:1px solid var(--line);padding-top:3mm}
@media screen{body{background:#e9e9e6}.wrap{background:#fff;padding:8mm 10mm;margin:16px auto;box-shadow:0 6px 24px rgba(0,0,0,.15)}}
@media screen and (max-width:640px){.wrap{margin:0;padding:16px}.case{grid-template-columns:1fr}.qr{text-align:left}.qr svg{margin:0 0 4px}}
</style></head><body data-ready="1"><div class="wrap">
<header><div class="kicker">Relevant work{% if who %} · {{ who }}{% endif %}</div>
  <h1>{% if s.query %}{{ s.query }}{% else %}Selected case studies{% endif %}</h1>
  <p class="lead">{{ s.projects|length }} case stud{{ 'ies' if s.projects|length != 1 else 'y' }} that match. Every sentence below is quoted word for word from a case study that was fact-checked against the project notes and approved by a person.</p></header>
{% for b in s.projects %}<section class="case"><div>
  <h2>{{ b.title }}</h2>
  <p class="meta">{% if b.client %}{{ b.client }} · {% endif %}approved by {{ b.approved_by }} on {{ b.approved_on }}</p>
  <ul>{% for x in b.sentences %}<li class="{{ 'metric' if x.metric }}">{{ x.text }}{% if x.confirmed %}<span class="tag">✓ confirmed by the client</span>{% endif %}</li>{% endfor %}</ul>
</div>
<div class="qr">{% if b.verified_url %}{{ qr(b.verified_url)|safe }}Scan to check<br>every sentence{% endif %}</div></section>{% endfor %}
<footer>Made {{ today }} with CaseForge. Nothing on this page was written for it: each line comes from an approved case study{% if any_links %}, and the QR codes open the evidence behind it{% endif %}.</footer>
</div></body></html>"""


def proof_sheet_html(s: dict, who: str = "") -> str:
    env = Environment(autoescape=select_autoescape(default=True))
    return env.from_string(TEMPLATE).render(s=s, who=who, today=date.today().isoformat(),
                                            any_links=any(b["verified_url"] for b in s["projects"]),
                                            qr=lambda u: qr_svg(u))

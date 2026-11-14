"""Designed report renderer: branded HTML/CSS pages printed to PDF by headless Chromium.

Why a browser engine: real typography, SVG charts and diagrams, and exact layout control — the
level of finish consulting publications have, which a drawing library can't reach.

Layout intelligence lives here:
- the page order, cover and block shapes come from caseforge.layout (chosen from the content);
- big numbers, a process diagram and a before/after chart are generated from the checked plan;
- brand colours are applied with contrast rules (a pale brand colour never becomes text);
- a fit-to-page pass shrinks a crowded page a little at a time instead of spilling onto a 6th page.
"""

from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path

from jinja2 import Environment, select_autoescape

from ..brandkit import BrandKit, contrast, publisher, readable_on
from ..models import ProjectRecord
from ..layout import compose
from ..report import ReportDesign, report_ready
from . import ExportBlocked

TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{{ p.title }}</title>
{% if google_fonts %}<link href="https://fonts.googleapis.com/css2?{{ google_fonts }}&display=swap" rel="stylesheet">{% endif %}
<style>
{{ font_faces|safe }}
@page { size: A4; margin: 0 }
:root{
  --pri: {{ c.primary }}; --acc: {{ c.accent }}; --ink: {{ c.ink }}; --paper: {{ c.paper }};
  --surface: {{ c.surface }}; --muted: {{ c.muted }}; --dark: {{ c.dark }};
  --pri-ink: {{ pri_ink }}; --pri-on-dark: {{ pri_on_dark }}; --on-pri: {{ on_pri }}; --on-dark: {{ on_dark }}; --acc-on-dark: {{ acc_on_dark }};
  --hf: {{ hf|safe }}; --bf: {{ bf|safe }};
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:#d9d9d9}
body{font-family:var(--bf);color:var(--ink);-webkit-print-color-adjust:exact;print-color-adjust:exact}
.page{width:210mm;height:297mm;background:var(--paper);position:relative;overflow:hidden;margin:0 auto 12px;page-break-after:always;--s:1;--g:1}
.page:last-child{page-break-after:auto}
@media print{html,body{background:var(--paper)} .page{margin:0}}
.bar-left{position:absolute;left:0;top:0;bottom:0;width:9px;background:var(--pri)}
.bar-top{position:absolute;left:0;right:0;top:0;height:7px;background:var(--pri)}
.head{position:absolute;top:34px;left:58px;right:52px;display:flex;justify-content:space-between;align-items:center;
  font-size:10.5px;color:var(--muted);{% if b.logo_position == 'top-left' %}flex-direction:row-reverse{% endif %}}
.logo img{height:26px;display:block}
.wordmark{font-family:var(--hf);font-weight:800;font-size:17px;color:var(--ink);letter-spacing:-.02em;display:flex;align-items:center;gap:7px}
.wordmark i{display:inline-block;width:13px;height:13px;background:var(--pri);border-radius:{{ '3px' if b.motif != 'circle' else '50%' }};
  {% if b.motif == 'hexagon' %}clip-path:polygon(25% 5%,75% 5%,100% 50%,75% 95%,25% 95%,0 50%);border-radius:0{% endif %}}
.foot{position:absolute;bottom:26px;left:58px;right:52px;display:flex;justify-content:space-between;font-size:9.5px;color:var(--muted);border-top:1px solid color-mix(in srgb,var(--ink) 12%,transparent);padding-top:9px}
.body{position:absolute;top:92px;bottom:70px;left:58px;right:52px;display:flex;flex-direction:column;gap:calc(24px*var(--s)*var(--g));overflow:hidden}
h1,h2,h3{font-family:var(--hf);letter-spacing:-.025em;line-height:1.05}
h2{font-size:calc(40px*var(--s));font-weight:800}
h2 em{font-style:normal;color:var(--pri-ink)}
.lede{font-size:calc(16.5px*var(--s));line-height:1.5;max-width:46em;color:var(--ink)}
.kicker{font-family:var(--hf);font-weight:700;font-size:calc(11px*var(--s));color:var(--muted);letter-spacing:.01em}
.muted{color:var(--muted)}
.body>*{flex-shrink:0}
.card{background:var(--surface);border-radius:14px;padding:calc(18px*var(--s)) calc(20px*var(--s))}
/* ------------ cover */
.cover .motif{position:absolute;right:-40px;top:70px;width:520px;height:520px}
.cover .ttl{position:absolute;left:58px;right:60px;bottom:172px}
.cover .ttl .kicker{margin-bottom:16px}
.cover h1{font-size:52px;font-weight:800;line-height:1.02;max-width:15em}
.cover .sub{font-size:17px;line-height:1.45;color:var(--muted);margin-top:18px;max-width:32em}
.cover .tags{display:flex;flex-wrap:wrap;gap:7px;margin-top:22px}
.cover .tags span{font-size:10.5px;font-weight:600;border:1px solid color-mix(in srgb,var(--ink) 22%,transparent);border-radius:999px;padding:5px 11px}
.cover .band{position:absolute;left:0;right:0;bottom:0;height:120px;background:var(--dark);color:var(--on-dark);display:flex;align-items:center;justify-content:space-between;padding:0 52px 0 58px}
.cover .band .client{font-family:var(--hf);font-size:15px;font-weight:700;max-width:30em}
.cover .band .client small{display:block;font-family:var(--bf);font-weight:400;font-size:11px;opacity:.75;margin-bottom:5px}
.cover .band .stamp{font-size:10.5px;opacity:.85;text-align:right;line-height:1.5}
.cover .band .stamp b{color:var(--acc-on-dark)}
/* ------------ challenge */
.client-card{display:flex;gap:14px;align-items:center}
.client-card .dot{width:38px;height:38px;border-radius:10px;background:var(--pri);flex:none}
.client-card b{font-family:var(--hf);font-size:calc(15px*var(--s))}
.chall{display:grid;grid-template-columns:62px 1fr;gap:6px 14px;padding:calc(16px*var(--s)) 0;border-top:1px solid color-mix(in srgb,var(--ink) 12%,transparent)}
.chall .n{font-family:var(--hf);font-weight:800;font-size:calc(34px*var(--s));color:var(--pri-ink);line-height:1}
.chall h3{font-size:calc(17px*var(--s));font-weight:700;margin-bottom:4px}
.chall p{font-size:calc(13.5px*var(--s));line-height:1.5;color:var(--muted)}
.brief{background:var(--dark);color:var(--on-dark);border-radius:16px;padding:calc(26px*var(--s)) calc(28px*var(--s));position:relative;overflow:hidden}
.brief .kicker{color:var(--acc-on-dark);margin-bottom:10px}
.brief p{font-family:var(--hf);font-weight:700;font-size:calc(25px*var(--s));line-height:1.2;letter-spacing:-.015em;max-width:20em}
/* ------------ solution */
.pillars{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:calc(12px*var(--s))}
.pillar{background:var(--surface);border-radius:14px;padding:calc(16px*var(--s)) calc(18px*var(--s))}
.pillar .ic{width:26px;height:26px;margin-bottom:10px}
.pillar h3{font-size:calc(15.5px*var(--s));font-weight:700;margin-bottom:5px}
.pillar p{font-size:calc(13px*var(--s));line-height:1.48;color:var(--muted)}
.flow{position:relative;display:grid;grid-template-columns:repeat({{ p.steps|length or 1 }},1fr);gap:10px;margin-top:4px}
.flow::before{content:"";position:absolute;left:calc(50%/{{ p.steps|length or 1 }});right:calc(50%/{{ p.steps|length or 1 }});top:calc(19px*var(--s));height:2px;background:color-mix(in srgb,var(--pri) 55%,transparent)}
.step{text-align:center;position:relative}
.step .n{width:calc(38px*var(--s));height:calc(38px*var(--s));border-radius:50%;margin:0 auto 10px;background:var(--pri);color:var(--on-pri);display:flex;align-items:center;justify-content:center;font-family:var(--hf);font-weight:800;font-size:15px;border:4px solid var(--paper)}
.step h3{font-size:calc(13.5px*var(--s));font-weight:700;margin-bottom:4px}
.step p{font-size:calc(11.5px*var(--s));line-height:1.4;color:var(--muted)}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chips span{font-size:calc(11.5px*var(--s));font-weight:600;background:var(--surface);border-radius:6px;padding:calc(6px*var(--s)) calc(11px*var(--s))}
/* ------------ results */
.metrics{display:grid;grid-template-columns:1fr 1fr;gap:calc(14px*var(--s))}
.metric{border-top:3px solid var(--pri);padding-top:calc(12px*var(--s))}
.metric .v{font-family:var(--hf);font-weight:800;font-size:calc(58px*var(--s));letter-spacing:-.04em;line-height:1;color:var(--pri-ink)}
.metric .v small{font-size:.42em;letter-spacing:0;margin-left:3px}
.metric p{font-size:calc(13px*var(--s));line-height:1.45;color:var(--ink);margin-top:8px;max-width:22em}
.est{display:inline-block;font-size:9px;font-weight:700;letter-spacing:.04em;border:1.5px solid var(--ink);border-radius:4px;padding:2px 6px;margin-left:8px;vertical-align:6px;color:var(--ink);font-family:var(--bf)}
.chart{background:var(--surface);border-radius:14px;padding:calc(18px*var(--s)) calc(20px*var(--s))}
.chart .legend{display:flex;gap:16px;font-size:calc(10.5px*var(--s));color:var(--muted);margin-top:calc(10px*var(--s))}
.bars{display:flex;flex-direction:column;gap:calc(14px*var(--s))}
.bars .bl{font-family:var(--hf);font-weight:700;font-size:calc(13px*var(--s));margin-bottom:calc(6px*var(--s))}
.bars .bl .est{vertical-align:1px}
.bars .bt{display:flex;align-items:center;gap:8px;height:calc(15px*var(--s));margin-bottom:calc(4px*var(--s))}
.bars .bt i{display:block;height:100%;border-radius:3px;min-width:3px;background:color-mix(in srgb,var(--ink) 22%,transparent)}
.bars .bt.after i{background:var(--pri)}
.bars .bt span{font-size:calc(11.5px*var(--s));color:var(--muted);white-space:nowrap}
.bars .bt.after span{font-weight:800;color:var(--ink);font-size:calc(12.5px*var(--s))}
.t-dark .bars .bt.after i{background:var(--pri-on-dark)}
/* columns: vertical before/after pairs */
.colchart{display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:calc(22px*var(--s));align-items:end}
.colchart .pair{display:flex;align-items:flex-end;justify-content:center;gap:calc(14px*var(--s));height:calc(170px*var(--s));
  border-bottom:2px solid color-mix(in srgb,var(--ink) 22%,transparent);padding-top:calc(24px*var(--s))}
.colchart .col{position:relative;width:calc(58px*var(--s));min-height:4px;border-radius:5px 5px 0 0;background:color-mix(in srgb,var(--ink) 22%,transparent)}
.colchart .col.after{background:var(--pri)}
.t-dark .colchart .col.after{background:var(--pri-on-dark)}
.colchart .col span{position:absolute;left:50%;bottom:100%;transform:translateX(-50%);white-space:nowrap;margin-bottom:5px;
  font-size:calc(12px*var(--s));color:var(--muted)}
.colchart .col.after span{font-family:var(--hf);font-weight:800;font-size:calc(15px*var(--s));color:var(--ink)}
.colchart .bl{font-family:var(--hf);font-weight:700;font-size:calc(13px*var(--s));text-align:center;margin-top:calc(9px*var(--s));line-height:1.3}
/* slope: before and after as two dots on one line */
.slope{display:flex;flex-direction:column;gap:calc(20px*var(--s))}
.slope .bl{font-family:var(--hf);font-weight:700;font-size:calc(13px*var(--s))}
.slope .track{position:relative;height:calc(46px*var(--s));margin:0 calc(26px*var(--s))}
.slope .track::before{content:"";position:absolute;left:0;right:0;top:50%;height:2px;background:color-mix(in srgb,var(--ink) 14%,transparent)}
.slope .ln{position:absolute;top:calc(50% - 3px);height:8px;border-radius:4px;background:color-mix(in srgb,var(--pri) 38%,transparent)}
.slope b{position:absolute;top:50%;width:calc(16px*var(--s));height:calc(16px*var(--s));border-radius:50%;transform:translate(-50%,-50%);
  background:color-mix(in srgb,var(--ink) 34%,var(--surface))}
.slope b.d1{background:var(--pri);width:calc(20px*var(--s));height:calc(20px*var(--s))}
.t-dark .slope b.d1{background:var(--pri-on-dark)}
.slope span{position:absolute;transform:translateX(-50%);white-space:nowrap;font-size:calc(11.5px*var(--s));color:var(--muted);top:0;line-height:1}
.slope span.t1{top:auto;bottom:0;font-family:var(--hf);font-weight:800;font-size:calc(13.5px*var(--s));color:var(--ink)}
/* rings: percentages that are shares of a whole */
.rings{display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:calc(18px*var(--s))}
.ring{text-align:center}
.ring .dial{position:relative;width:calc(128px*var(--s));height:calc(128px*var(--s));margin:0 auto}
.ring svg{width:100%;height:100%;display:block}
.ring .tr{fill:none;stroke:color-mix(in srgb,var(--ink) 12%,transparent);stroke-width:11}
.ring .fg{fill:none;stroke:var(--pri);stroke-width:11;stroke-linecap:round}
.t-dark .ring .fg{stroke:var(--pri-on-dark)}
.ring .v{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-family:var(--hf);font-weight:800;
  font-size:calc(27px*var(--s));letter-spacing:-.03em;color:var(--ink)}
.ring .v small{font-size:.5em;margin-left:1px}
.ring p{font-size:calc(13px*var(--s));line-height:1.4;margin-top:calc(10px*var(--s))}
.ring .est{margin:6px 0 0;vertical-align:0}
.chart .legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}
.chart .legend i.a{background:var(--pri)} .t-dark .chart .legend i.a{background:var(--pri-on-dark)}
/* ------------ close */
.quote{position:relative;padding-top:calc(34px*var(--s))}
.quote .qm{position:absolute;left:0;top:0;width:calc(34px*var(--s));height:calc(26px*var(--s));color:var(--pri-ink)}
.quote p{font-family:var(--hf);font-size:calc(23px*var(--s));font-weight:600;line-height:1.3;letter-spacing:-.01em}
.quote cite{display:block;font-style:normal;font-size:calc(11.5px*var(--s));color:var(--muted);margin-top:12px}
.outcomes{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:calc(16px*var(--s))}
.outcome{display:flex;gap:12px}
.outcome .ck{width:24px;height:24px;border-radius:50%;background:var(--pri);color:var(--on-pri);flex:none;display:flex;align-items:center;justify-content:center}
.outcome h3{font-size:calc(14.5px*var(--s));font-weight:700;margin-bottom:3px}
.outcome p{font-size:calc(13px*var(--s));line-height:1.45;color:var(--muted)}
.closing{background:var(--dark);color:var(--on-dark);border-radius:16px;padding:calc(26px*var(--s)) calc(28px*var(--s));display:flex;flex-direction:column;gap:14px}
.closing p.big{font-family:var(--hf);font-weight:700;font-size:calc(24px*var(--s));line-height:1.22;letter-spacing:-.015em}
.closing .cta{align-self:flex-start;background:var(--pri);color:var(--on-pri);font-weight:700;font-size:12px;border-radius:8px;padding:9px 14px}
.verify{display:grid;grid-template-columns:30px 1fr;gap:12px;font-size:calc(10px*var(--s));line-height:1.5;color:var(--muted);border:1px solid color-mix(in srgb,var(--ink) 14%,transparent);border-radius:12px;padding:14px 16px;margin-top:auto}
.verify b{color:var(--ink)}
/* ------------ content-driven variants */
.sec{display:flex;flex-direction:column;gap:calc(18px*var(--s)*var(--g))}
.sec>*{flex-shrink:0}
.sec:last-child{flex:1}
.sec.next{border-top:2px solid color-mix(in srgb,var(--ink) 10%,transparent);padding-top:calc(22px*var(--s)*var(--g))}
.sec.next h2{font-size:calc(30px*var(--s))}
.sec-k{color:var(--pri-ink);text-transform:uppercase;letter-spacing:.08em;margin-bottom:-6px}
h2.hl{font-size:calc(31px*var(--s));line-height:1.12;max-width:17em}
.sec.next h2.hl{font-size:calc(25px*var(--s))}
.push{margin-top:auto}
.statement{border-left:5px solid var(--pri);padding:calc(6px*var(--s)) 0 calc(6px*var(--s)) calc(22px*var(--s))}
.statement p{font-family:var(--hf);font-weight:700;font-size:calc(25px*var(--s));line-height:1.25;letter-spacing:-.015em}
.pillars.cols1{grid-template-columns:minmax(0,1fr)}.pillars.cols3{grid-template-columns:repeat(3,minmax(0,1fr))}
.pillars.cols1 .pillar{display:grid;grid-template-columns:26px 1fr;column-gap:14px;align-items:start}
.pillars.cols1 .pillar .ic{grid-row:span 2;margin:2px 0 0}
.flow{grid-template-columns:repeat(var(--n),1fr)}
.flow::before{left:calc(50%/var(--n));right:calc(50%/var(--n))}
.vsteps{display:flex;flex-direction:column;position:relative}
.vsteps::before{content:"";position:absolute;left:calc(17px*var(--s));top:12px;bottom:12px;width:2px;background:color-mix(in srgb,var(--pri) 45%,transparent)}
.vs{display:grid;grid-template-columns:calc(36px*var(--s)) 1fr;gap:16px;padding:calc(8px*var(--s)) 0;position:relative}
.vs .n{width:calc(36px*var(--s));height:calc(36px*var(--s));border-radius:50%;background:var(--pri);color:var(--on-pri);display:flex;align-items:center;justify-content:center;font-family:var(--hf);font-weight:800;font-size:14px;border:4px solid var(--paper)}
.vs h3{font-size:calc(14.5px*var(--s));font-weight:700;margin-bottom:3px}
.vs p{font-size:calc(12.5px*var(--s));line-height:1.45;color:var(--muted);padding-top:calc(7px*var(--s))}
.vs h3+p{padding-top:0}
.tl-h{display:grid;grid-template-columns:repeat(var(--n),1fr);gap:12px;position:relative}
.tl-h::before{content:"";position:absolute;left:0;right:0;top:calc(30px*var(--s));height:2px;background:color-mix(in srgb,var(--ink) 14%,transparent)}
.tl-h .when{font-family:var(--hf);font-weight:800;font-size:calc(13px*var(--s));color:var(--pri-ink);height:calc(22px*var(--s))}
.tl-h i{display:block;width:14px;height:14px;border-radius:50%;background:var(--pri);border:3px solid var(--paper);margin:calc(1px*var(--s)) 0 10px;position:relative}
.tl-h p{font-size:calc(11.5px*var(--s));line-height:1.42;color:var(--ink)}
.tl-v{display:flex;flex-direction:column;position:relative}
.tl-v::before{content:"";position:absolute;left:calc(132px*var(--s) + 6px);top:8px;bottom:8px;width:2px;background:color-mix(in srgb,var(--ink) 14%,transparent)}
.tl-v .ev{display:grid;grid-template-columns:calc(132px*var(--s)) 14px 1fr;gap:14px;padding:calc(8px*var(--s)) 0;align-items:start}
.tl-v .when{font-family:var(--hf);font-weight:800;font-size:calc(14px*var(--s));color:var(--pri-ink);text-align:right}
.tl-v i{width:14px;height:14px;border-radius:50%;background:var(--pri);border:3px solid var(--paper);position:relative;margin-top:2px}
.tl-v p{font-size:calc(13px*var(--s));line-height:1.45}
.metrics.hero{grid-template-columns:1fr}.metrics.hero .v{font-size:calc(118px*var(--s))}.metrics.hero p{font-size:calc(17px*var(--s));max-width:26em}
.metrics.pair .v{font-size:calc(64px*var(--s))}.metrics.pair p{font-size:calc(14px*var(--s))}
.metrics.row{grid-template-columns:1fr 1fr 1fr}.metrics.row .v{font-size:calc(42px*var(--s))}.metrics.row .est{display:table;margin:6px 0 0}
.fromto .row{display:flex;align-items:center;gap:calc(22px*var(--s));margin:10px 0 4px}
.fromto .before,.fromto .after{font-family:var(--hf);font-weight:800;font-size:calc(72px*var(--s));letter-spacing:-.04em;line-height:1}
.fromto .before{color:var(--muted)} .fromto .after{color:var(--pri-ink)}
.fromto small{font-size:.42em;margin-left:3px}
.fromto .arrow{width:calc(64px*var(--s));height:auto;color:var(--pri-ink)}
.fromto .legend{display:flex;gap:calc(150px*var(--s));font-size:10.5px;color:var(--muted)}
.outcomes.list{grid-template-columns:1fr}
.quote.hero p{font-size:calc(29px*var(--s))}
/* covers */
.cover .motif-small{position:absolute;right:-30px;top:60px;width:260px;height:260px;opacity:.95}
.cover .hero{position:absolute;left:58px;right:60px;top:150px}
.cover .hero .v{font-family:var(--hf);font-weight:800;font-size:178px;letter-spacing:-.05em;line-height:.9;color:var(--pri-ink)}
.cover .hero .v small{font-size:.38em;letter-spacing:0;margin-left:6px}
.cover .hero p{font-size:19px;line-height:1.4;max-width:24em;margin-top:18px;color:var(--ink)}
.cover .ft .row{display:flex;align-items:center;gap:26px;margin-top:14px}
.cover .ft .before{font-family:var(--hf);font-weight:800;font-size:96px;letter-spacing:-.04em;color:var(--muted);line-height:1}
.cover .ft .before small{font-size:.4em;margin-left:4px}
.cover .ft .v{font-size:150px}
.cover .ft .arrow{width:70px;color:var(--pri-ink)}
.cover .ft .kicker{font-size:14px}
.cover .hq .qm{width:58px;height:44px;color:var(--pri-ink);margin-bottom:22px}
.cover .hq p{font-family:var(--hf);font-weight:700;font-size:34px;line-height:1.22;letter-spacing:-.02em;max-width:17em}
.cover .hq cite{display:block;font-style:normal;color:var(--muted);font-size:14px;margin-top:16px}
.cover-hero-number .ttl h1,.cover-from-to .ttl h1,.cover-quote .ttl h1{font-size:40px}
/* ------------ frames: how a page is built */
/* sidebar: a full-height column with the key facts */
.f-sidebar .side-bg{position:absolute;left:0;top:0;bottom:0;width:286px;background:var(--surface)}
.f-sidebar .body:not(.wide){display:grid;grid-template-columns:206px minmax(0,1fr);column-gap:50px;align-items:start}
.f-sidebar .side{display:flex;flex-direction:column;gap:calc(22px*var(--s)*var(--g));padding-top:calc(6px*var(--s))}
.f-sidebar .side .card{padding:calc(14px*var(--s)) calc(16px*var(--s))}
.f-sidebar .side .client-card b{font-size:calc(14px*var(--s));line-height:1.3;display:block}
.f-sidebar .main{display:flex;flex-direction:column;gap:calc(22px*var(--s)*var(--g));min-height:100%}
.f-sidebar .side .card{background:var(--paper)}
.f-sidebar .side .chips span{background:var(--paper)}
.f-sidebar .side .quote p{font-size:calc(15px*var(--s))}
.mband.side{display:flex;flex-direction:column;gap:calc(16px*var(--s))}
.mband.side .mb{border-top:3px solid var(--pri);padding-top:8px}
.mband.side .v{font-family:var(--hf);font-weight:800;font-size:calc(38px*var(--s));letter-spacing:-.03em;line-height:1;color:var(--pri-ink)}
.mband .v small{font-size:.42em;margin-left:2px}
.mband.side p{font-size:calc(11px*var(--s));line-height:1.4;margin-top:5px;color:var(--muted)}
/* magazine: two text columns, run-in titles, a band of figures, a pull quote */
.f-magazine h2,.f-magazine h2.hl{font-size:calc(44px*var(--s));line-height:1.02}
.f-magazine .lede{font-size:calc(18px*var(--s));line-height:1.55}
.f-magazine .lede::first-letter{float:left;font-family:var(--hf);font-weight:800;font-size:3.3em;line-height:.82;margin:.06em .08em 0 0;color:var(--pri-ink)}
.cols{column-count:2;column-gap:28px;column-rule:1px solid color-mix(in srgb,var(--ink) 12%,transparent)}
.cols p,.cols li{font-size:calc(12.5px*var(--s));line-height:1.6;margin:0 0 calc(10px*var(--s));break-inside:avoid}
.cols b{font-family:var(--hf)}
ol.run{padding-left:1.2em} ol.run li::marker{font-family:var(--hf);font-weight:800;color:var(--pri-ink)}
.mband.band{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;border-top:2px solid var(--ink);border-bottom:1px solid color-mix(in srgb,var(--ink) 20%,transparent)}
.mband.band .mb{padding:calc(14px*var(--s)) 14px;border-left:1px solid color-mix(in srgb,var(--ink) 14%,transparent)}
.mband.band .mb:first-child{border-left:0;padding-left:0}
.mband.band .v{font-family:var(--hf);font-weight:800;font-size:calc(44px*var(--s));letter-spacing:-.03em;line-height:1;color:var(--pri-ink)}
.mband.band p{font-size:calc(11.5px*var(--s));line-height:1.4;margin-top:6px}
.quote.pull{text-align:center;border-top:3px solid var(--pri);border-bottom:1px solid color-mix(in srgb,var(--ink) 20%,transparent);padding:calc(26px*var(--s)) 8%}
.quote.pull .qm{position:static;margin:0 auto 10px;display:block}
.quote.pull p{font-style:italic;font-size:calc(24px*var(--s))}
/* dashboard: everything is a tile on a 6-column grid */
.f-dashboard h2,.f-dashboard h2.hl{font-size:calc(28px*var(--s))}
.tiles{display:grid;grid-template-columns:repeat(6,1fr);gap:calc(12px*var(--s))}
.tile{grid-column:span 3;background:var(--surface);border-radius:14px;padding:calc(16px*var(--s))}
.tile>.card,.tile .chart,.tile .pillar{background:transparent;padding:0}
.tile.k-metrics,.tile.k-comparison,.tile.k-brief,.tile.k-closing,.tile.k-verify,.tile.k-timeline,.tile.k-tech,.tile.k-client{grid-column:span 6}
.tile.k-metrics,.tile.k-brief,.tile.k-closing,.tile.k-verify{background:transparent;padding:0}
.tile.k-steps,.tile.k-pillars,.tile.k-quote,.tile.k-challenges,.tile.k-outcomes{grid-column:span 6}
.tile.k-challenges.v-numbered>div{display:grid;grid-template-columns:repeat(auto-fit,minmax(0,1fr));gap:14px;align-items:start}
.tile.k-challenges .chall{grid-template-columns:1fr;border-top:0;padding:0}
.tile.k-challenges .chall .n{font-size:calc(26px*var(--s))}
.tile.k-challenges .statement{border:0;padding:0}
.tile.k-outcomes .outcomes{grid-template-columns:repeat(auto-fit,minmax(0,1fr))}
.tile.k-pillars .pillars{gap:8px}
.f-dashboard .metric{background:var(--surface);border-radius:14px;padding:calc(16px*var(--s));border-top:0}
.f-dashboard .metrics.row,.f-dashboard .metrics.grid{grid-template-columns:repeat(auto-fit,minmax(0,1fr))}
.f-dashboard .metrics .v{font-size:calc(40px*var(--s))}
/* split: each section opens with a full-width colour panel */
.f-split .body{overflow:visible}  /* let the colour panel bleed to the page edges (the page still clips) */
.f-sidebar .head,.f-sidebar .foot{z-index:2}
.f-sidebar .side .client-card{flex-direction:column;align-items:flex-start;gap:8px}
.f-split .sechead{margin:-92px -52px 0 -58px;padding:calc(110px*var(--s)) 52px calc(30px*var(--s)) 58px;background:var(--dark);color:var(--on-dark);
  display:flex;flex-direction:column;gap:calc(14px*var(--s))}
.t-dark.f-split .sechead{background:color-mix(in srgb,var(--on-dark) 9%,var(--dark));color:var(--on-dark);
  border-bottom:3px solid var(--pri-on-dark)}
.f-split .sechead h2 em{color:var(--acc-on-dark)} .f-split .sechead .sec-k{color:var(--acc-on-dark)}
.f-split .sechead .lede{color:var(--on-dark);opacity:.9}
.f-split .sec.next .sechead{margin:0 -52px 0 -58px;padding-top:calc(28px*var(--s))}
.f-split .sec.next{border-top:0;padding-top:0}
.f-split .head{z-index:2;color:color-mix(in srgb,var(--on-dark) 70%,transparent)}
.f-split .head .wordmark{color:var(--on-dark)}
/* ------------ themes (chosen from the content, or asked for in the report chat) */
/* dark: every page on the brand's dark colour */
.t-dark .page{--paper:var(--dark);--ink:var(--on-dark);--muted:color-mix(in srgb,var(--on-dark) 68%,transparent);
  --surface:color-mix(in srgb,var(--on-dark) 8%,transparent);--pri-ink:var(--pri-on-dark)}
.t-dark .page,.t-bold .cover{color:var(--ink)}  /* re-resolve text colour inside the themed page */
.t-dark .chips span{color:var(--ink)}
.t-dark .brief,.t-dark .closing{background:color-mix(in srgb,var(--on-dark) 10%,transparent)}
.t-dark .cover .band{background:color-mix(in srgb,#000 30%,var(--dark))}
.t-dark .step .n,.t-dark .vs .n,.t-dark .tl-h i,.t-dark .tl-v i{border-color:var(--dark)}
/* bold: full-bleed brand colour cover, big numbers on colour blocks */
.t-bold .cover{background:var(--pri);--ink:var(--on-pri);--muted:color-mix(in srgb,var(--on-pri) 72%,transparent);--pri-ink:var(--on-pri)}
.t-bold .cover .tags span{border-color:color-mix(in srgb,var(--on-pri) 35%,transparent)}
.t-bold .cover .motif,.t-bold .cover .motif-small{opacity:.22;filter:grayscale(1) brightness(3)}
.t-bold .cover .bar-left,.t-bold .cover .bar-top{display:none}
.t-bold .metric{background:var(--pri);color:var(--on-pri);border:0;border-radius:14px;padding:calc(16px*var(--s)) calc(18px*var(--s))}
.t-bold .metric .v{color:var(--on-pri)} .t-bold .metric p{color:var(--on-pri);opacity:.9}
.t-bold .metric .est{border-color:var(--on-pri);color:var(--on-pri)}
.t-bold h2 em{background:var(--pri);color:var(--on-pri);padding:0 .15em;border-radius:.12em}
/* editorial: magazine feel — no shapes, big type, thin rules, generous white space */
.t-editorial .cover .motif,.t-editorial .cover .motif-small{display:none}
.t-editorial h1,.t-editorial h2,.t-editorial h3{font-family:var(--bf);font-weight:600;letter-spacing:-.015em}
.t-editorial h2{font-size:calc(42px*var(--s))} .t-editorial h2 em{font-style:italic;color:var(--ink)}
.t-editorial .sec{border-top:1px solid var(--ink);padding-top:calc(14px*var(--s))}
.t-editorial .card,.t-editorial .pillar,.t-editorial .chart{background:transparent;border:1px solid color-mix(in srgb,var(--ink) 18%,transparent)}
.t-editorial .brief,.t-editorial .closing{background:transparent;color:var(--ink);border-left:4px solid var(--pri);border-radius:0;padding-left:calc(22px*var(--s))}
.t-editorial .brief .kicker{color:var(--pri-ink)}
.t-editorial .cover .band{background:transparent;color:var(--ink);border-top:1px solid var(--ink);height:96px}
.t-editorial .cover .band .stamp b{color:var(--pri-ink)}
/* statement cover: the title is the cover */
.cover-statement .ttl{top:300px;bottom:auto}
.cover-statement .ttl h1{font-size:66px;line-height:1;max-width:11em}
.cover-statement .ttl .sub{font-size:20px;max-width:26em}
.cover-statement .rule{position:absolute;left:58px;width:120px;height:8px;top:268px;background:var(--pri)}
/* density */
.d-compact .page{--s:1}
.draft{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none;z-index:9}
.draft span{transform:rotate(-30deg);font-family:var(--hf);font-weight:800;font-size:120px;color:rgba(200,30,30,.10);letter-spacing:.05em}
</style></head><body class="t-{{ L.theme }} f-{{ L.frame }} d-{{ L.density }}">

{% macro chrome(n) %}
  {% if b.accent_bar == 'left' %}<div class="bar-left"></div>{% elif b.accent_bar == 'top' %}<div class="bar-top"></div>{% endif %}
  <div class="head"><span>Case study{% if short_title %} · {{ short_title }}{% endif %}</span><span class="logo">{{ logo|safe }}</span></div>
  <div class="foot"><span>{{ who }}</span><span>{{ footer_note }}</span>{% if b.page_numbers %}<span>{{ '%02d' % n }}</span>{% endif %}</div>
  {% if draft %}<div class="draft"><span>DRAFT</span></div>{% endif %}
{% endmacro %}

{% macro heading(sec, first) %}
  {% set hl = p.headlines[sec.key] if sec.key in ['challenge','solution','results','journey','close'] else '' %}
  {% if hl %}<div class="kicker sec-k">{{ sec.label }}</div><h2 class="hl">{{ hl }}</h2>
  {% else %}{% set w = sec.label.rsplit(' ', 1) %}<h2>{{ w[0] }} <em>{{ w[1] }}</em></h2>{% endif %}
{% endmacro %}

{% macro block(bk) %}{% set k = bk.kind %}{% set v = bk.variant %}
{% if k == 'lede' %}<p class="lede">{{ p[bk.field] }}</p>
{% elif k == 'client' %}<div class="card client-card"><span class="dot"></span><div><div class="kicker">The client</div><b>{{ p.client_line }}</b></div></div>
{% elif k in ['challenges', 'pillars', 'outcomes'] and v == 'prose' %}<div class="cols">{% for it in p[k] %}<p>{% if it.title %}<b>{{ it.title }}.</b> {% endif %}{{ it.text }}</p>{% endfor %}</div>
{% elif k == 'steps' and v == 'prose' %}<div>{% if bk.title %}<div class="kicker" style="margin-bottom:10px">How it works</div>{% endif %}<ol class="cols run">{% for st in p.steps %}<li>{% if st.title %}<b>{{ st.title }}.</b> {% endif %}{{ st.text }}</li>{% endfor %}</ol></div>
{% elif k == 'metrics' and v in ['band', 'side'] %}<div class="mband {{ v }}">{% for m in shown_metrics %}<div class="mb"><div class="v">{{ m.value }}<small>{{ m.unit|trim }}</small>{% if m.estimate %}<span class="est">ESTIMATED</span>{% endif %}</div><p>{{ m.label }}</p></div>{% endfor %}</div>
{% elif k == 'challenges' %}
  {% if v == 'statement' %}{% set it = p.challenges[0] %}<div class="statement">{% if it.title %}<div class="kicker">{{ it.title }}</div>{% endif %}<p>{{ it.text }}</p></div>
  {% else %}<div>{% for it in p.challenges %}<div class="chall"><div class="n">{{ '%02d' % loop.index }}</div><div>{% if it.title %}<h3>{{ it.title }}</h3>{% endif %}<p>{{ it.text }}</p></div></div>{% endfor %}</div>{% endif %}
{% elif k == 'brief' %}<div class="brief"><div class="kicker">The brief</div><p>{{ p.brief }}</p></div>
{% elif k == 'pillars' %}<div class="pillars {{ v }}">{% for it in p.pillars %}<div class="pillar">{{ icon|safe }}{% if it.title %}<h3>{{ it.title }}</h3>{% endif %}<p>{{ it.text }}</p></div>{% endfor %}</div>
{% elif k == 'steps' %}<div>{% if bk.title %}<div class="kicker" style="margin-bottom:14px">How it works</div>{% endif %}
  {% if v == 'vertical' %}<div class="vsteps">{% for st in p.steps %}<div class="vs"><div class="n">{{ loop.index }}</div><div>{% if st.title %}<h3>{{ st.title }}</h3>{% endif %}<p>{{ st.text }}</p></div></div>{% endfor %}</div>
  {% else %}<div class="flow" style="--n:{{ p.steps|length }}">{% for st in p.steps %}<div class="step"><div class="n">{{ loop.index }}</div>{% if st.title %}<h3>{{ st.title }}</h3>{% endif %}<p>{{ st.text }}</p></div>{% endfor %}</div>{% endif %}</div>
{% elif k == 'tech' %}<div class="push"><div class="kicker" style="margin-bottom:8px">Built with</div><div class="chips">{% for t in p.tech %}<span>{{ t }}</span>{% endfor %}</div></div>
{% elif k == 'timeline' %}
  {% if v == 'horizontal' %}<div class="tl-h" style="--n:{{ p.timeline|length }}">{% for e in p.timeline %}<div class="ev"><div class="when">{{ e.when }}</div><i></i><p>{{ e.text }}</p></div>{% endfor %}</div>
  {% else %}<div class="tl-v">{% for e in p.timeline %}<div class="ev"><div class="when">{{ e.when }}</div><i></i><p>{{ e.text }}</p></div>{% endfor %}</div>{% endif %}
{% elif k == 'metrics' and v == 'rings' %}<div class="rings" style="--n:{{ shown_metrics|length }}">{% for m in shown_metrics %}<div class="ring">
    <div class="dial"><svg viewBox="0 0 120 120" aria-hidden="true"><circle class="tr" cx="60" cy="60" r="52"/><circle class="fg" cx="60" cy="60" r="52" stroke-dasharray="{{ ring_arc[loop.index0] }} 327" transform="rotate(-90 60 60)"/></svg>
    <div class="v">{{ m.value }}<small>%</small></div></div><p>{{ m.label }}</p>{% if m.estimate %}<span class="est">ESTIMATED</span>{% endif %}</div>{% endfor %}</div>
{% elif k == 'metrics' %}<div class="metrics {{ v }}">{% for m in shown_metrics %}<div class="metric"><div class="v">{{ m.value }}<small>{{ m.unit|trim }}</small>{% if m.estimate %}<span class="est">ESTIMATED</span>{% endif %}</div><p>{{ m.label }}</p></div>{% endfor %}</div>
{% elif k == 'comparison' %}
  {% if v == 'from-to' %}{% set r = p.comparisons[0] %}<div class="fromto card"><div class="kicker">{{ r.label }}{% if r.estimate %}<span class="est">ESTIMATED</span>{% endif %}</div><div class="row"><span class="before">{{ '%g' % r.before }}<small>{{ r.unit|trim }}</small></span>{{ arrow|safe }}<span class="after">{{ '%g' % r.after }}<small>{{ r.unit|trim }}</small></span></div><div class="legend"><span>Before</span><span>After</span></div></div>
  {% elif v == 'columns' %}<div class="chart"><div class="kicker" style="margin-bottom:6px">Before and after</div>
    <div class="colchart" style="--n:{{ bars|length }}">{% for r in bars %}<div><div class="pair">
      <div class="col" style="height:{{ r.bh }}%"><span>{{ r.before }}</span></div><div class="col after" style="height:{{ r.ah }}%"><span>{{ r.after }}</span></div></div>
      <div class="bl">{{ r.label }}{% if r.estimate %}<br><span class="est" style="margin:5px 0 0">ESTIMATED</span>{% endif %}</div></div>{% endfor %}</div>
    <div class="legend"><span><i style="background:color-mix(in srgb,var(--ink) 22%,transparent)"></i>Before</span><span><i class="a"></i>After</span></div></div>
  {% elif v == 'slope' %}<div class="chart"><div class="kicker" style="margin-bottom:12px">Before and after</div>
    <div class="slope">{% for r in bars %}<div><div class="bl">{{ r.label }}{% if r.estimate %}<span class="est">ESTIMATED</span>{% endif %}</div>
      <div class="track"><i class="ln" style="left:{{ r.lo }}%;width:{{ r.span }}%"></i><b style="left:{{ r.bx }}%"></b><b class="d1" style="left:{{ r.ax }}%"></b>
        <span style="left:{{ r.bx }}%">{{ r.before }}</span><span class="t1" style="left:{{ r.ax }}%">{{ r.after }}</span></div></div>{% endfor %}</div>
    <div class="legend"><span><i style="background:color-mix(in srgb,var(--ink) 34%,var(--surface));border-radius:50%"></i>Before</span><span><i class="a" style="border-radius:50%"></i>After</span></div></div>
  {% else %}<div class="chart"><div class="kicker" style="margin-bottom:12px">Before and after</div>
    <div class="bars">{% for r in bars %}<div><div class="bl">{{ r.label }}{% if r.estimate %}<span class="est">ESTIMATED</span>{% endif %}</div>
      <div class="bt"><i style="width:{{ r.bw }}%"></i><span>{{ r.before }}</span></div>
      <div class="bt after"><i style="width:{{ r.aw }}%"></i><span>{{ r.after }}</span></div></div>{% endfor %}</div>
    <div class="legend"><span><i style="background:color-mix(in srgb,var(--ink) 22%,transparent)"></i>Before</span><span><i class="a"></i>After</span></div></div>{% endif %}
{% elif k == 'outcomes' %}<div class="outcomes {{ v }}">{% for it in p.outcomes %}<div class="outcome"><span class="ck"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></span><div>{% if it.title %}<h3>{{ it.title }}</h3>{% endif %}<p>{{ it.text }}</p></div></div>{% endfor %}</div>
{% elif k == 'quote' %}<div class="quote {{ v }}">{{ qmark|safe }}<p>{{ p.quote.text }}</p>{% if p.quote.who %}<cite>{{ p.quote.who }}</cite>{% endif %}</div>
{% elif k == 'closing' %}<div class="closing"><p class="big">{{ p.conclusion }}</p>{% if b.cta_text %}<span class="cta">{{ b.cta_text }}</span>{% endif %}</div>
{% elif k == 'verify' %}<div class="verify"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/></svg>
      <div><b>How this report was checked.</b> CaseForge matched every statement in this report — {{ n_checked }} in total — against the original project notes{% if n_sources %} ({{ n_sources }} source{{ 's' if n_sources != 1 }}){% endif %}. Numbers marked ESTIMATED are estimates in the source. {% if approved_by %}Approved for publication by {{ approved_by }} on {{ approved_on }}.{% else %}Not yet approved for publication.{% endif %}</div></div>
{% endif %}{% endmacro %}

<section class="page cover cover-{{ L.cover }}">
  {% if b.accent_bar == 'left' %}<div class="bar-left"></div>{% elif b.accent_bar == 'top' %}<div class="bar-top"></div>{% endif %}
  <div class="head"><span></span><span class="logo">{{ logo|safe }}</span></div>
  {% if L.cover == 'hero-number' %}{% set m = p.metrics[L.hero_metric] %}
    {{ motif_small|safe }}
    {% set n = (m.value|length) + (m.unit|trim|length) * 0.38 %}<div class="hero"><div class="v" style="font-size:{{ [178, (800 / n)|int]|min }}px">{{ m.value }}<small>{{ m.unit|trim }}</small></div><p>{{ m.label }}</p></div>
  {% elif L.cover == 'from-to' %}{% set r = p.comparisons[0] %}
    {{ motif_small|safe }}
    <div class="hero ft"><div class="kicker">{{ r.label }}{% if r.estimate %}<span class="est">ESTIMATED</span>{% endif %}</div><div class="row"><span class="before">{{ '%g' % r.before }}<small>{{ r.unit|trim }}</small></span>{{ arrow|safe }}<span class="v">{{ '%g' % r.after }}<small>{{ r.unit|trim }}</small></span></div></div>
  {% elif L.cover == 'quote' %}
    {{ motif_small|safe }}
    <div class="hero hq">{{ qmark|safe }}<p>{{ p.quote.text }}</p>{% if p.quote.who %}<cite>{{ p.quote.who }}</cite>{% endif %}</div>
  {% elif L.cover == 'statement' %}<div class="rule"></div>
  {% else %}{{ motif|safe }}{% endif %}
  <div class="ttl">
    <div class="kicker">Case study{% if p.tags %} · {{ p.tags[0] }}{% endif %}</div>
    <h1>{{ p.title }}</h1>
    {% if p.subtitle %}<p class="sub">{{ p.subtitle }}</p>{% endif %}
    {% if p.tags|length > 1 %}<div class="tags">{% for t in p.tags[1:] %}<span>{{ t }}</span>{% endfor %}</div>{% endif %}
  </div>
  <div class="band">
    <div class="client">{% if p.client_line or client %}<small>Client</small>{{ p.client_line or client }}{% elif who %}<small>Published by</small>{{ who }}{% endif %}</div>
    <div class="stamp">{% if approved_by %}<b>Fact-checked</b> against the project notes<br>Approved by {{ approved_by }} · {{ approved_on }}{% else %}<b>Draft</b> — not approved yet{% endif %}</div>
  </div>
  {% if draft %}<div class="draft"><span>DRAFT</span></div>{% endif %}
</section>

{% for pg in L.pages %}
<section class="page">{{ chrome(loop.index + 1) }}
  {% if L.frame == 'sidebar' and pg.side %}<div class="side-bg"></div>{% endif %}
  <div class="body{% if L.frame == 'sidebar' and not pg.side %} wide{% endif %}">
  {% if L.frame == 'sidebar' and pg.side %}
    <aside class="side">{% for sec in pg.sections %}{% for bk in sec.blocks %}{% if bk.slot == 'side' %}{{ block(bk) }}{% endif %}{% endfor %}{% endfor %}</aside>
    <div class="main">{% for sec in pg.sections %}<div class="sec{% if not loop.first %} next{% endif %}">{{ heading(sec) }}
      {% for bk in sec.blocks %}{% if bk.slot != 'side' %}{{ block(bk) }}{% endif %}{% endfor %}</div>{% endfor %}</div>
  {% else %}
    {% for sec in pg.sections %}<div class="sec{% if not loop.first %} next{% endif %}">
      {% set lead = (sec.blocks|selectattr('kind', 'equalto', 'lede')|list or [None])[0] %}
      {% if L.frame == 'split' %}<div class="sechead">{{ heading(sec) }}{% if lead %}{{ block(lead) }}{% endif %}</div>
      {% else %}{{ heading(sec) }}{% if lead %}{{ block(lead) }}{% endif %}{% endif %}
      {% if L.frame == 'dashboard' %}<div class="tiles">{% for bk in sec.blocks %}{% if bk is not sameas lead %}<div class="tile k-{{ bk.kind }} v-{{ bk.variant }}">{{ block(bk) }}</div>{% endif %}{% endfor %}</div>
      {% else %}{% for bk in sec.blocks %}{% if bk is not sameas lead %}{{ block(bk) }}{% endif %}{% endfor %}{% endif %}
    </div>{% endfor %}
  {% endif %}
  </div>
</section>
{% endfor %}

<script>
/* fit-to-page. 1) every page finds the largest type size at which it fits; 2) the sizes are pulled
   together so the report reads as one document (no page more than ~10 % larger than the fullest one,
   unless that would go below normal size); 3) a page with room left opens up its spacing. */
document.fonts.ready.then(function(){
  var bodies=[].slice.call(document.querySelectorAll('.page .body')), fit=[];
  function over(b){return b.scrollHeight>b.clientHeight+1;}
  function set(b,s,g){var p=b.parentElement;p.style.setProperty('--s',s.toFixed(2));p.style.setProperty('--g',g.toFixed(2));}
  bodies.forEach(function(b){
    var s=1.5; set(b,s,1);
    while(over(b)&&s>0.74){s-=0.02;set(b,s,1);}
    fit.push(s);
  });
  var low=Math.min.apply(null,fit), cap=Math.max(1,low*1.1);
  bodies.forEach(function(b,i){
    var s=Math.min(fit[i],cap), g=1; set(b,s,g);
    while(!over(b)&&g<2.2){g+=0.1;set(b,s,g);}
    if(over(b)){g-=0.1;set(b,s,g);}
  });
  document.body.setAttribute('data-ready','1');
});
</script>
</body></html>"""


# ------------------------------------------------------------------ generated graphics
ARROW = ('<svg class="arrow" viewBox="0 0 64 24" aria-hidden="true"><path d="M2 12h56M46 3l12 9-12 9" fill="none" '
         'stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/></svg>')
QMARK = ('<svg class="qm" viewBox="0 0 34 26" aria-hidden="true"><path fill="currentColor" d="M0 26V15C0 6.5 4.6 1.4 13 0l1.6 '
         '4.2C9.9 5.7 7.6 8.6 7.4 13H14v13zm19 0V15c0-8.5 4.6-13.6 13-15l1.6 4.2c-4.7 1.5-7 4.4-7.2 8.8H33v13z"/></svg>')
def _motif(b: BrandKit) -> str:
    c = b.colors
    if b.motif == "hexagon":
        def hexa(cx, cy, r, fill, op=1.0):
            pts = " ".join(f"{cx + r * x:.1f},{cy + r * y:.1f}" for x, y in
                           [(1, 0), (.5, .866), (-.5, .866), (-1, 0), (-.5, -.866), (.5, -.866)])
            return f'<polygon points="{pts}" fill="{fill}" opacity="{op}"/>'
        shapes = [hexa(300, 230, 150, c.primary), hexa(150, 110, 70, c.accent, .9), hexa(440, 420, 78, c.surface),
                  hexa(130, 380, 46, c.dark), hexa(470, 120, 40, c.surface)]
    elif b.motif == "circle":
        shapes = [f'<circle cx="300" cy="240" r="170" fill="{c.primary}"/>',
                  f'<circle cx="140" cy="120" r="70" fill="{c.accent}" opacity=".9"/>',
                  f'<circle cx="430" cy="420" r="60" fill="{c.surface}"/>']
    elif b.motif == "bars":
        hs = [180, 300, 230, 380, 270, 440]
        shapes = [f'<rect x="{40 + i * 78}" y="{470 - h}" width="54" height="{h}" rx="6" '
                  f'fill="{c.primary if i % 2 else c.surface}" opacity="{1 if i % 2 else .95}"/>' for i, h in enumerate(hs)]
        shapes.append(f'<rect x="{40 + 3 * 78}" y="{470 - 380 - 26}" width="54" height="16" rx="4" fill="{c.accent}"/>')
    else:
        return ""
    return f'<svg class="motif" viewBox="0 0 520 520" aria-hidden="true">{"".join(shapes)}</svg>'


def _icon(b: BrandKit) -> str:
    c = b.colors
    if b.motif == "hexagon":
        return (f'<svg class="ic" viewBox="0 0 26 26"><polygon points="6.5,2 19.5,2 26,13 19.5,24 6.5,24 0,13" '
                f'fill="{c.primary}"/></svg>')
    if b.motif == "circle":
        return f'<svg class="ic" viewBox="0 0 26 26"><circle cx="13" cy="13" r="12" fill="{c.primary}"/></svg>'
    return (f'<svg class="ic" viewBox="0 0 26 26"><rect x="1" y="10" width="6" height="15" rx="1.5" fill="{c.primary}"/>'
            f'<rect x="10" y="4" width="6" height="21" rx="1.5" fill="{c.primary}"/>'
            f'<rect x="19" y="13" width="6" height="12" rx="1.5" fill="{c.accent}"/></svg>')


def _pct(value: str) -> float:
    try:
        return max(0.0, float(value.replace(",", "")))
    except ValueError:
        return 0.0


def _bars(plan) -> list[dict]:
    """Before/after bars. Each pair is scaled to its own larger value — pairs can have different units."""
    out = []
    for r in plan.comparisons:
        hi = max(abs(r.before), abs(r.after)) or 1
        unit = r.unit if r.unit.strip() != "%" else "%"
        bx, ax = round(100 * abs(r.before) / hi, 1), round(100 * abs(r.after) / hi, 1)
        out.append({"label": r.label, "estimate": getattr(r, "estimate", False),
                    "bw": round(80 * abs(r.before) / hi, 1), "aw": round(80 * abs(r.after) / hi, 1),
                    "bh": bx, "ah": ax, "bx": bx, "ax": ax, "lo": min(bx, ax), "span": round(abs(bx - ax), 1),
                    "before": f"{r.before:g}{unit}", "after": f"{r.after:g}{unit}"})
    return out


def _family(name: str) -> str:
    """CSS font stack; the name is sanitised because it is written into a <style> block."""
    clean = re.sub(r"[^A-Za-z0-9 \-]", "", name)[:60] or "Inter"
    serif = "Georgia, serif" if "serif" in clean.lower() and "sans" not in clean.lower() else "system-ui, sans-serif"
    return f"'{clean}', 'Inter', {serif}"


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ------------------------------------------------------------------ fonts + logo
def _font_faces(b: BrandKit) -> tuple[str, str]:
    css, google = [], []
    for fam in dict.fromkeys([b.heading_font, b.body_font, "Inter"]):
        folder = b.font_path(fam)
        if folder:
            for f in sorted(folder.glob("*.woff2")):
                data = base64.b64encode(f.read_bytes()).decode()
                css.append(f"@font-face{{font-family:'{re.sub(r'[^A-Za-z0-9 -]', '', fam)}';font-weight:{f.stem};font-style:normal;"
                           f"src:url(data:font/woff2;base64,{data}) format('woff2')}}")
        else:
            google.append("family=" + fam.replace(" ", "+") + ":wght@400;600;700;800")
    return "\n".join(css), "&".join(google)


def _who(b: BrandKit) -> str:
    """The publisher's name as printed, or "" — never a placeholder, an auto-kit label or "<person>'s workspace"."""
    name = publisher(b.company)
    if not name and not b.company and not b.name.startswith("Auto ·") and "from your logo" not in b.name:
        name = publisher(b.name)      # a hand-made brand kit is named after its company
    return name


def _logo(b: BrandKit, logo_dir: Path | None) -> str:
    if b.logo and logo_dir and (logo_dir / b.logo).exists():
        p = logo_dir / b.logo
        mime = mimetypes.guess_type(p.name)[0] or "image/png"
        return f'<img src="data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}" alt="{_esc(_who(b))}">'
    return f'<span class="wordmark"><i></i>{_esc(_who(b))}</span>' if _who(b) else ""


# ------------------------------------------------------------------ build
def report_html(record: ProjectRecord, design: ReportDesign, logo_dir: Path | None = None, draft: bool = True) -> str:
    b, p, c = design.brand, design.plan, design.brand.colors
    faces, google = _font_faces(b)
    pri_ink = c.primary if contrast(c.primary, c.paper) >= 3 else c.ink   # pale brand colours never become text
    acc_on_dark = c.accent if contrast(c.accent, c.dark) >= 3 else readable_on(c.dark)
    pri_on_dark = (c.primary if contrast(c.primary, c.dark) >= 3 else
                   c.accent if contrast(c.accent, c.dark) >= 3 else readable_on(c.dark))
    short = p.title.split(":")[0]
    short = "" if short.strip().lower() in ("case study", "") else (short if len(short) <= 56 else short[:56].rsplit(" ", 1)[0] + "…")
    L = design.layout if design.layout.pages else compose(p, design.prefs)
    shown = [x for i, x in enumerate(p.metrics) if i != L.hero_metric]
    env = Environment(autoescape=select_autoescape(default=True))
    sources = record.input.source_text().count("--- from ") + (1 if record.input.raw_notes.strip() else 0)
    return env.from_string(TEMPLATE).render(
        hf=_family(b.heading_font), bf=_family(b.body_font), p=p, b=b, c=c, pri_ink=pri_ink, on_pri=readable_on(c.primary), on_dark=readable_on(c.dark),
        acc_on_dark=acc_on_dark, pri_on_dark=pri_on_dark, font_faces=faces, google_fonts=google, motif=_motif(b), icon=_icon(b),
        # the pair on a from-to cover is not drawn a second time in the chart (each fact once)
        bars=_bars(p)[1:] if L.cover == "from-to" and len(p.comparisons) > 1 else _bars(p), ring_arc=[round(326.7 * min(100.0, _pct(x.value)) / 100, 1) for x in shown],
        logo=_logo(b, logo_dir) if "brand" not in design.prefs.hide else "",
        who=_who(b) if "brand" not in design.prefs.hide else "", short_title=short, client=record.input.client_name,
        approved_by=design.approved_by if not draft else "", approved_on=design.approved_at[:10],
        n_checked=len(design.elements), n_sources=sources, draft=draft, L=L, shown_metrics=shown,
        motif_small=_motif(b).replace('class="motif"', 'class="motif-small"'), arrow=ARROW, qmark=QMARK,
        footer_note="Fact-checked case study" if not draft else "Draft for review",
    )


def render_report(record: ProjectRecord, out: Path, logo_dir: Path | None = None, draft: bool = False) -> Path:
    design = record.report
    if design is None:
        raise ExportBlocked("Design the report first.")
    if not draft and not report_ready(record):
        raise ExportBlocked("Export blocked: the designed report isn't approved, or something changed since. "
                            "Review it and approve it first.")
    html = report_html(record, design, logo_dir, draft=draft)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix == ".html":
        out.write_text(html, encoding="utf-8")
        return out
    html_to_pdf(html, out)
    return out


def html_to_pdf(html: str, out: Path) -> Path:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="load", timeout=30000)
            page.wait_for_selector("body[data-ready='1']", timeout=15000)
            page.pdf(path=str(out), format="A4", print_background=True, prefer_css_page_size=True)
        finally:
            browser.close()
    return out

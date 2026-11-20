"""The public Verified page: the approved case study, where every sentence opens its evidence."""

from __future__ import annotations

import segno
from jinja2 import Environment, select_autoescape

TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{{ v.title }} · Verified case study</title>
<meta property="og:title" content="{{ v.title }} · CaseForge Verified">
<meta property="og:description" content="Every sentence in this case study is traced to the project notes and was approved by {{ v.approved_by }}.">
<style>
:root{--bg:#F6F5F1;--paper:#FFFFFF;--ink:#14202E;--ink2:#4A5565;--muted:#6B7686;--line:#E3E1DA;--accent:#E8A33D;
  --ok:#1F7A4D;--ok-soft:#E4F2EA;--warn:#9A5B00;--warn-soft:#FBF0DC;--bad:#B3261E;--hl:#FFF3D6}
@media (prefers-color-scheme: dark){:root{--bg:#0F151D;--paper:#16202B;--ink:#E9EDF2;--ink2:#BAC3CF;--muted:#8D98A7;
  --line:#26313E;--ok:#5FD39A;--ok-soft:#173326;--warn:#F2B661;--warn-soft:#3A2C14;--bad:#FF8A80;--hl:#3A2F14}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.65 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:inherit}
.top{background:var(--paper);border-bottom:1px solid var(--line)}
.wrap{max-width:1120px;margin:0 auto;padding:0 16px}
.bar{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 0;font-size:14px;color:var(--muted)}
.brand{display:flex;align-items:center;gap:8px;font-weight:700;color:var(--ink);text-decoration:none}
.brand i{width:18px;height:18px;border-radius:5px;background:var(--accent);display:inline-block}
.badge{display:inline-flex;align-items:center;gap:6px;background:var(--ok-soft);color:var(--ok);font-weight:700;font-size:13px;
  padding:5px 11px;border-radius:999px;white-space:nowrap}
.badge.bad{background:color-mix(in srgb,var(--bad) 14%,transparent);color:var(--bad)}
.hero{padding:44px 0 30px}
.kicker{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:700}
h1{font-size:clamp(28px,4.6vw,44px);line-height:1.12;margin:10px 0 10px;letter-spacing:-.01em}
.client{color:var(--ink2)}
.how{margin-top:18px;font-size:15px;color:var(--ink2);max-width:62ch}
.how b{color:var(--ink)}
.grid{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:32px;padding-top:28px;padding-bottom:60px;align-items:start}
main section{margin-bottom:30px}
h2{font-size:21px;margin:0 0 10px}
p.txt{margin:0}
.s{cursor:pointer;border-radius:4px;padding:1px 2px;margin:0 -2px;box-decoration-break:clone;-webkit-box-decoration-break:clone;
  background-image:linear-gradient(transparent calc(100% - 2px),color-mix(in srgb,var(--ok) 45%,transparent) 2px);transition:background-color .15s}
.s.est{background-image:linear-gradient(transparent calc(100% - 2px),color-mix(in srgb,var(--warn) 60%,transparent) 2px)}
.s:hover,.s:focus-visible{background-color:var(--hl)}
.s:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.s.on{background-color:var(--hl)}
ul.list{margin:0;padding-left:20px} ul.list li{margin:4px 0}
aside{position:sticky;top:16px}
.panel{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:18px 18px 16px}
.panel h3{margin:0 0 6px;font-size:13px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.panel .said{font-weight:600;margin:0 0 14px;line-height:1.5}
.panel .empty{color:var(--muted);font-size:15px}
.ev{border-left:3px solid var(--ok);background:var(--bg);border-radius:0 8px 8px 0;padding:10px 12px;margin:0 0 10px;font-size:15px;line-height:1.55}
.ev .src{display:block;color:var(--muted);font-size:12.5px;margin-top:6px}
.chip{display:inline-block;font-size:12.5px;font-weight:700;padding:3px 9px;border-radius:999px;background:var(--ok-soft);color:var(--ok);margin:0 6px 10px 0}
.chip.est{background:var(--warn-soft);color:var(--warn)}
.chip.man{background:var(--bg);color:var(--ink2)}
.close{all:unset;display:none;position:absolute;right:14px;top:8px;cursor:pointer;font-size:24px;line-height:1;color:var(--muted);padding:4px 8px}
.panel{position:relative}
.seal{margin-top:14px;font-size:13.5px;color:var(--ink2);border-top:1px solid var(--line);padding-top:12px}
.seal code{font-size:12.5px;background:var(--bg);padding:1px 5px;border-radius:4px}
.note{background:var(--warn-soft);color:var(--warn);border-radius:10px;padding:10px 14px;font-size:14.5px;margin:0 0 18px}
.note.bad{background:color-mix(in srgb,var(--bad) 12%,transparent);color:var(--bad)}
footer{border-top:1px solid var(--line);color:var(--muted);font-size:13.5px;padding:18px 0 40px}
@media (max-width:860px){
  .grid{grid-template-columns:1fr;gap:0}
  aside{position:fixed;left:0;right:0;bottom:0;top:auto;z-index:5;transform:translateY(105%);transition:transform .22s ease;padding:0 10px 10px}
  aside.open{transform:none}
  .panel{max-height:62vh;overflow:auto;box-shadow:0 -8px 30px rgba(0,0,0,.18)}
  .close{display:block}
  .panel .hint-desk{display:none}
}
</style></head><body>
<div class="top"><div class="wrap bar">
  <a class="brand" href="/" target="_blank" rel="noopener"><i></i>CaseForge</a>
  {% if v.intact %}<span class="badge"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/></svg>Verified case study</span>
  {% else %}<span class="badge bad">Not verified</span>{% endif %}
</div></div>
<div class="wrap">
  <div class="hero">
    <div class="kicker">Case study</div>
    <h1>{{ v.title }}</h1>
    {% if v.client %}<div class="client">Client: {{ v.client }}</div>{% endif %}
    <p class="how"><b>Click any sentence to see where it comes from.</b> Each of the {{ v.n_sentences }} sentences was matched
      against the original project notes{% if v.n_sources %} ({{ v.n_sources }} source{{ 's' if v.n_sources != 1 }}){% endif %}
      and approved by {{ v.approved_by }} on {{ v.approved_on }}.{% if v.evidence == 'masked' %} Details the sentence doesn't mention are hidden as ███.{% endif %}</p>
  </div>
</div>
<div class="wrap grid">
<main>
  {% if not v.intact %}<p class="note bad">This copy no longer matches the version that was approved, so it is not verified.</p>
  {% elif v.newer_version %}<p class="note">The team has changed this case study since. This page shows the version approved on {{ v.approved_on }}.</p>{% endif %}
  {% for sec in v.sections %}<section><h2>{{ sec.title }}</h2>
    {% if sec.key in ('challenges','results','objectives','lessons','tools') %}<ul class="list">{% for s in sec.sentences %}<li>{{ sent(s) }}</li>{% endfor %}</ul>
    {% else %}<p class="txt">{% for s in sec.sentences %}{{ sent(s) }} {% endfor %}</p>{% endif %}
  </section>{% endfor %}
</main>
<aside id="side" aria-live="polite"><div class="panel">
  <button class="close" id="x" aria-label="Close">×</button>
  <div id="show"><h3>Evidence</h3><p class="empty"><span class="hint-desk">Click a sentence on the left.</span> The quote from the project notes behind it appears here.</p></div>
  <div class="seal">{% if v.intact %}Approved by <b>{{ v.approved_by }}</b> on {{ v.approved_on }}. Unchanged since approval:
    fingerprint <code title="SHA-256 of the approved text">{{ v.hash_short }}…</code>{% else %}Fingerprint check failed.{% endif %}</div>
</div></aside>
</div>
{% for sec in v.sections %}{% for s in sec.sentences %}<template id="e-{{ s.id }}">
  <h3>Evidence</h3><p class="said">{{ s.text }}</p>
  {% if s.manual and not s.n_facts %}<span class="chip man">Added by the reviewer</span>
  {% else %}<span class="chip">{{ s.label_text }}</span>{% if s.estimate %}<span class="chip est">Estimate in the notes</span>{% endif %}{% endif %}
  {% for e in s.evidence %}<div class="ev">“{{ e.quote }}”{% if e.source %}<span class="src">{{ e.source }}</span>{% endif %}</div>{% endfor %}
  {% if v.evidence == 'labels' and s.n_facts %}<p class="empty">Checked against {{ s.n_facts }} fact{{ 's' if s.n_facts != 1 }} in the notes. The owner chose not to show the quotes.</p>{% endif %}
</template>{% endfor %}{% endfor %}
<div class="wrap"><footer>Published {{ v.published_on }} with CaseForge, case studies where every sentence is traced to the project notes and approved by a person.</footer></div>
<script>
(function(){
  var side=document.getElementById("side"),show=document.getElementById("show"),seen={},cur=null;
  function open(b){
    if(cur)cur.classList.remove("on");cur=b;b.classList.add("on");
    var t=document.getElementById("e-"+b.dataset.id);show.innerHTML="";show.appendChild(t.content.cloneNode(true));
    side.classList.add("open");
    if(!seen[b.dataset.id]){seen[b.dataset.id]=1;try{navigator.sendBeacon(location.pathname.replace(/\\/$/,"")+"/check")}catch(e){}}
  }
  document.querySelectorAll(".s").forEach(function(b){b.addEventListener("click",function(){open(b)});b.addEventListener("keydown",function(e){if(e.key==="Enter"||e.key===" "){e.preventDefault();open(b)}})});
  document.getElementById("x").addEventListener("click",function(){side.classList.remove("open");if(cur)cur.classList.remove("on")});
  document.addEventListener("keydown",function(e){if(e.key==="Escape")side.classList.remove("open")});
})();
</script>
</body></html>"""

SENTENCE = """{% macro sent(s) %}<span class="s{{ ' est' if s.estimate }}" data-id="{{ s.id }}" role="button" tabindex="0" title="Show where this comes from">{{ s.text }}</span>{% endmacro %}"""

GONE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>Link not available</title>
<style>:root{--bg:#F6F5F1;--ink:#14202E;--muted:#6B7686}@media (prefers-color-scheme: dark){:root{--bg:#0F151D;--ink:#E9EDF2;--muted:#8D98A7}}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.6 system-ui,sans-serif;display:grid;place-items:center;min-height:100vh;padding:16px}
div{max-width:440px;text-align:center}p{color:var(--muted)}</style></head>
<body><div><h1>This link isn't available</h1><p>The case study was unpublished by its owner, or the link is wrong.</p></div></body></html>"""


def verified_page(view: dict) -> str:
    env = Environment(autoescape=select_autoescape(default=True))
    return env.from_string(SENTENCE + TEMPLATE).render(v=view)


def qr_svg(url: str, dark: str = "#14202E", standalone: bool = False) -> str:
    """A QR code as SVG with no white box, so it sits on any light background.

    standalone=True adds the xmlns so the SVG also works as its own file (an <img src>)."""
    import io

    if not standalone:
        return segno.make(url, error="m").svg_inline(scale=4, dark=dark, light=None, border=0)
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="svg", scale=4, dark=dark, light="#FFFFFF", border=2,
                                    xmldecl=False, svgns=True)
    return buf.getvalue().decode()

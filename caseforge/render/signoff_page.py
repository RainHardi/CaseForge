"""The client's sign-off page: no account, works on a phone, one answer per sentence."""

from __future__ import annotations

from jinja2 import Environment, select_autoescape

from ..models import SECTION_TITLES

TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Confirm: {{ r.title }}</title>
<style>
:root{--bg:#F6F5F1;--paper:#FFFFFF;--ink:#14202E;--ink2:#4A5565;--muted:#6B7686;--line:#E3E1DA;--accent:#E8A33D;--accent-ink:#14202E;
  --ok:#1F7A4D;--ok-soft:#E4F2EA;--warn:#9A5B00;--warn-soft:#FBF0DC;--bad:#B3261E;--bad-soft:#FBE9E7}
@media (prefers-color-scheme: dark){:root{--bg:#0F151D;--paper:#16202B;--ink:#E9EDF2;--ink2:#BAC3CF;--muted:#8D98A7;--line:#26313E;
  --ok:#5FD39A;--ok-soft:#173326;--warn:#F2B661;--warn-soft:#3A2C14;--bad:#FF8A80;--bad-soft:#3A1B19}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:720px;margin:0 auto;padding:0 16px}
.top{background:var(--paper);border-bottom:1px solid var(--line)}
.bar{display:flex;align-items:center;gap:8px;padding:12px 0;font-weight:700}
.bar i{width:18px;height:18px;border-radius:5px;background:var(--accent);display:inline-block}
h1{font-size:clamp(24px,5vw,34px);line-height:1.15;margin:28px 0 8px}
.lead{color:var(--ink2);margin:0 0 22px}
.card{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:16px;margin:0 0 14px}
.sec{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:700;margin:0 0 4px}
fieldset.card{min-width:0}fieldset.card legend{float:left;width:100%;padding:0}
.said{clear:both;margin:0 0 12px;font-weight:600}
.opts{display:flex;flex-wrap:wrap;gap:8px}
.opt{position:relative}
.opt input{position:absolute;opacity:0;pointer-events:none}
.opt span{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:8px 14px;font-size:15px;cursor:pointer;background:var(--bg);min-height:40px}
.opt input:focus-visible+span{outline:2px solid var(--accent);outline-offset:2px}
.opt input:checked+span{font-weight:700}
.opt.c input:checked+span{background:var(--ok-soft);border-color:var(--ok);color:var(--ok)}
.opt.f input:checked+span{background:var(--warn-soft);border-color:var(--warn);color:var(--warn)}
.opt.r input:checked+span{background:var(--bad-soft);border-color:var(--bad);color:var(--bad)}
textarea,input[type=text]{width:100%;font:inherit;color:inherit;background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
textarea{margin-top:10px;min-height:5.5em;resize:vertical}
textarea:focus,input[type=text]:focus{outline:0;border-color:var(--accent)}
.fixhint{font-size:14px;color:var(--muted);margin:6px 0 0}
h2{font-size:19px;margin:28px 0 10px}
.dec label{display:flex;gap:10px;align-items:flex-start;padding:10px 0;cursor:pointer}
.dec input{margin-top:5px;accent-color:var(--accent)}
.dec small{display:block;color:var(--muted)}
.go{display:flex;flex-direction:column;gap:10px;margin:22px 0 50px}
button.send{font:inherit;font-weight:700;border:0;border-radius:12px;padding:14px 18px;background:var(--accent);color:var(--accent-ink);cursor:pointer}
button.send:disabled{opacity:.6;cursor:default}
.err{color:var(--bad);font-weight:600;min-height:1.6em}
.small{font-size:14px;color:var(--muted)}
.msg{text-align:center;padding:60px 0}
.msg .big{font-size:44px;line-height:1}
</style></head><body>
<div class="top"><div class="wrap bar"><i></i>CaseForge</div></div>
<div class="wrap">
{% if state != 'open' %}
  <div class="msg">
    <div class="big">{{ '✓' if state == 'answered' else '!' }}</div>
    <h1>{{ {'answered': 'Thank you, your answers were sent', 'expired': 'This link has expired', 'changed': 'This case study has changed'}[state] }}</h1>
    <p class="lead">{{ {'answered': 'The team will see what you confirmed and what you asked to change.',
                         'expired': 'Ask the team for a new link.',
                         'changed': 'The team edited it after sending this link. Ask them for a new one so you confirm the current text.'}[state] }}</p>
  </div>
{% else %}
<form id="f" novalidate>
  <h1>Please confirm the case study about {{ r.client or 'your project' }}</h1>
  <p class="lead">{% if r.contact %}{{ r.contact }}, the{% else %}The{% endif %} team wrote a case study, <b>{{ r.title }}</b>. These {{ r['items']|length }} sentences mention your numbers, your words or your company. For each one: confirm it, suggest a fix, or ask to remove it. No account needed. About 2 minutes.</p>
  {% for it in r['items'] %}
  <fieldset class="card" data-id="{{ it.id }}">
    <legend class="sec">{{ titles.get(it.section, '') }}</legend>
    <p class="said">{{ it.text }}</p>
    <div class="opts" role="radiogroup" aria-label="Your answer">
      <label class="opt c"><input type="radio" name="a-{{ it.id }}" value="confirm"><span>Confirm</span></label>
      <label class="opt f"><input type="radio" name="a-{{ it.id }}" value="fix"><span>Suggest a fix</span></label>
      <label class="opt r"><input type="radio" name="a-{{ it.id }}" value="remove"><span>Remove</span></label>
    </div>
    <div class="fix" hidden><textarea name="t-{{ it.id }}" aria-label="What it should say">{{ it.text }}</textarea>
      <p class="fixhint">Change the sentence to what it should say.</p></div>
  </fieldset>
  {% endfor %}
  <h2>Can your company be named?</h2>
  <div class="card dec">
    <label><input type="radio" name="decision" value="named"><span><b>Yes, publish with our name</b><small>{{ r.client or 'Your company' }} appears in the case study.</small></span></label>
    <label><input type="radio" name="decision" value="anonymous"><span><b>No, keep us anonymous</b><small>Your name is hidden everywhere it is published.</small></span></label>
  </div>
  <h2>Your name</h2>
  <input type="text" name="signed_by" autocomplete="name" placeholder="e.g. Dana Lee, Operations Manager" aria-label="Your name">
  <div class="go">
    <div class="err" id="err" role="alert"></div>
    <button class="send" type="submit">Send my answers</button>
    <span class="small">Your answers and the date are saved with the case study, so readers can see what you confirmed.</span>
  </div>
</form>
{% endif %}
</div>
<script>
(function(){
  var f=document.getElementById("f"); if(!f)return;
  f.addEventListener("change",function(e){
    if(e.target.name&&e.target.name.indexOf("a-")===0){
      var card=e.target.closest("fieldset"),fix=card.querySelector(".fix");fix.hidden=e.target.value!=="fix";
      if(!fix.hidden)fix.querySelector("textarea").focus();
    }
  });
  f.addEventListener("submit",function(e){
    e.preventDefault();
    var err=document.getElementById("err"),btn=f.querySelector(".send"),answers={},missing=0;
    f.querySelectorAll("fieldset[data-id]").forEach(function(c){
      var id=c.dataset.id,pick=c.querySelector("input[type=radio]:checked");
      if(!pick){missing++;return}
      answers[id]={action:pick.value,text:pick.value==="fix"?c.querySelector("textarea").value:""};
    });
    var dec=f.querySelector("input[name=decision]:checked"),name=f.signed_by.value.trim();
    if(missing){err.textContent=missing+" sentence"+(missing>1?"s are":" is")+" still unanswered.";return}
    if(!dec){err.textContent="Choose whether your company can be named.";return}
    if(!name){err.textContent="Type your name.";return}
    err.textContent="";btn.disabled=true;btn.textContent="Sending…";
    fetch(location.pathname,{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({answers:answers,decision:dec.value,signed_by:name})})
    .then(function(r){return r.json().then(function(d){return [r.ok,d]})})
    .then(function(x){if(x[0]){location.reload()}else{err.textContent=(x[1]&&x[1].detail)||"Couldn't send. Try again.";btn.disabled=false;btn.textContent="Send my answers"}})
    .catch(function(){err.textContent="Couldn't send. Check your connection and try again.";btn.disabled=false;btn.textContent="Send my answers"});
  });
})();
</script>
</body></html>"""


def signoff_page(req: dict, state: str) -> str:
    env = Environment(autoescape=select_autoescape(default=True))
    return env.from_string(TEMPLATE).render(r=req, state=state, titles=SECTION_TITLES)

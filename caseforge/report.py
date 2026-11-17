"""The designed report: plan → check → approve (Target: publishable output).

1. PLAN   — the planner turns the APPROVED case study into content: headlines written from the facts,
            big numbers, before/after pairs, process steps, milestones, a quote. Every element has a
            length budget and cites the approved sentences it uses.
   LAYOUT — caseforge.layout picks the story, page order and block shapes from that content, so a
            report about a timeline looks different from a report about three big numbers.
2. CHECK  — every text element goes through the same checker as the case study (rules + model),
            plus report-level checks: each fact shown once, estimates still labelled, length
            budgets, brand tone rules.
3. APPROVE — a person approves the designed report itself; any later change withdraws it.
"""

from __future__ import annotations

import hashlib
import json
import re

from pydantic import BaseModel, Field

from .brandkit import BrandKit, text_warnings
from .layout import COVERS, FRAMES, HIDEABLE, SECTION_KEYS, STORIES, THEMES, VARIANTS, Layout, Prefs, compose
from .checker import label_claims
from .llm import LLM, LLMError
from .models import Claim, Label, ProjectRecord, now, worst
from .review import ReviewError, can_export
from .textutil import (_NUM_RE, _spots, _unit, content_words, hedged_in_source, is_hedged, normalize, number_is_hedged,
                       numbers_in, quote_in_source, split_sentences, term_in_source, unwrap)


# ------------------------------------------------------------------ the plan
class Item(BaseModel):
    title: str = ""
    text: str = ""
    cites: list[str] = Field(default_factory=list)


class Metric(BaseModel):
    value: str            # "11.8"  — exactly as in the notes
    unit: str = ""        # "%", " min", "s", "€" …
    label: str            # what it measures, one short line
    estimate: bool = False
    cites: list[str] = Field(default_factory=list)


class Comparison(BaseModel):
    label: str            # "Late deliveries"
    before: float
    after: float
    unit: str = ""
    estimate: bool = False  # either value is an estimate in the notes
    cites: list[str] = Field(default_factory=list)


class Quote(BaseModel):
    text: str = ""        # verbatim or near-verbatim from the notes
    who: str = ""
    cites: list[str] = Field(default_factory=list)


class Event(BaseModel):
    when: str             # "March 2024", "Week 3" — exactly as in the notes
    text: str
    cites: list[str] = Field(default_factory=list)


class Headlines(BaseModel):
    """Section headlines written from the facts ("Routes 4 % shorter in 12 weeks"), not generic labels."""
    challenge: str = ""
    solution: str = ""
    results: str = ""
    journey: str = ""
    close: str = ""


class ReportPlan(BaseModel):
    title: str
    subtitle: str = ""
    tags: list[str] = Field(default_factory=list)
    client_line: str = ""
    challenge_intro: str = ""
    challenges: list[Item] = Field(default_factory=list)
    brief: str = ""
    solution_intro: str = ""
    pillars: list[Item] = Field(default_factory=list)
    steps: list[Item] = Field(default_factory=list)
    tech: list[str] = Field(default_factory=list)
    metrics: list[Metric] = Field(default_factory=list)
    comparisons: list[Comparison] = Field(default_factory=list)
    outcomes: list[Item] = Field(default_factory=list)
    quote: Quote = Field(default_factory=Quote)
    conclusion: str = ""
    timeline: list[Event] = Field(default_factory=list)
    headlines: Headlines = Field(default_factory=Headlines)
    cites: dict[str, list[str]] = Field(default_factory=dict)  # citations for the plain-string fields


class FieldCite(BaseModel):
    field: str            # "subtitle", "headlines.results" …
    ids: list[str] = Field(default_factory=list)


class PlanOut(ReportPlan):
    """What the model returns. The Gemini Developer API rejects free-form maps (open JSON objects),
    so citations come back as a list and are turned into the dict here."""
    cites: list[FieldCite] = Field(default_factory=list)  # type: ignore[assignment]
    art: Prefs = Field(default_factory=Prefs)              # the art director's layout choice

    def to_plan(self) -> ReportPlan:
        data = self.model_dump()
        data["cites"] = {c.field: c.ids for c in self.cites}
        return ReportPlan.model_validate(data)


class ChatMsg(BaseModel):
    role: str             # "user" | "ai"
    text: str
    at: str = Field(default_factory=now)


class ChatOp(BaseModel):
    op: str               # text | remove | layout | color | estimate
    target: str = ""      # element path, layout key or colour role
    value: str = ""


class ChatOut(BaseModel):
    reply: str
    ops: list[ChatOp] = Field(default_factory=list)


# length budgets in characters — short, sharp copy (mentor point 2)
BUDGET = {"title": 72, "subtitle": 140, "client_line": 90, "challenge_intro": 220, "brief": 140,
          "solution_intro": 220, "conclusion": 170, "item.title": 46, "item.text": 140,
          "step.title": 32, "step.text": 90, "metric.label": 70, "quote": 220, "tag": 26,
          "headline": 60, "event.when": 18, "event.text": 90}
LIMITS = {"tags": 5, "challenges": 3, "pillars": 4, "steps": 6, "tech": 10, "metrics": 4,
          "comparisons": 3, "outcomes": 3, "timeline": 7}


class ReportDesign(BaseModel):
    brand: BrandKit
    plan: ReportPlan
    elements: list[Claim] = Field(default_factory=list)  # every checked text element
    warnings: list[str] = Field(default_factory=list)    # layout / repeat / brand findings
    layout: Layout = Field(default_factory=Layout)       # chosen from the content, with reasons
    prefs: Prefs = Field(default_factory=Prefs)          # art direction + reviewer's chat requests
    chat: list["ChatMsg"] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)       # how it was made (e.g. "AI was busy — rules were used")
    round: int = 0                                       # how many times this project has been (re)designed
    based_on_hash: str = ""                              # the case-study approval it was built from
    created_at: str = Field(default_factory=now)
    approved_by: str = ""
    approved_at: str = ""
    approved_hash: str = ""

    def design_hash(self) -> str:
        payload = {"plan": self.plan.model_dump(), "brand": self.brand.model_dump()}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    @property
    def blocking(self) -> list[Claim]:
        return [e for e in self.elements if e.blocking]


# ------------------------------------------------------------------ planning
SYSTEM = """You are the editor of a professional consulting-style case study (think Accenture or McKinsey
publications). You turn APPROVED sentences into a tight 5-page layout plan.
Rules:
- Use ONLY the numbered approved sentences. Every element cites the ids it is based on.
- Never add a number, name, tool, date or outcome that is not in the cited sentences.
- Each fact appears ONCE in the whole report. Do not repeat a number or claim in two places.
- Estimates stay estimates: set metric.estimate=true and keep words like "estimated" or "about"
  whenever the sentence says so.
- Short, sharp copy. Respect the character budgets. No filler, no hype words, no intensifiers
  ("significantly", "greatly", "dramatically", "seamless", "robust") unless the sentence itself uses them.
- Reuse the wording of the sentences. Do not summarise into a claim the sentences don't make
  (no "streamlining operations" if they only say invoices were approved faster).
- subtitle, brief, challenge_intro, solution_intro, conclusion: plain restatements of cited sentences.
  The subtitle is a full statement of what was built or what changed ("A booking portal and
  reminder service that cut missed appointments from about 12 % to 5 %"), never a slogan and never an "-ing" phrase
  ("Reducing missed appointments for …").
- Headlines state the fact without a degree: "Missed appointments reduced", never "reduced significantly".
- Titles of items and steps: 1–4 words in sentence case ("Constraint handling", not "Constraint Handling"),
  using words that appear in the cited sentences where possible.
- metrics: the 2–4 strongest measured results, STRONGEST FIRST (the first one may go on the cover);
  value is the number exactly as written, unit separate; label is a short caption, not a sentence.
- comparisons: before/after pairs that share a unit (e.g. error rate 9 % → 2.5 %), for a chart.
  Set estimate=true when either value is an estimate in the sentence ("about 40 hours").
  A number used in a comparison is not repeated as a metric.
- steps: how the solution works, in order, 3–6 short steps (this becomes a process diagram).
- tech: names of tools and technologies only — never people, companies, places or the client.
- quote: only if a person is quoted or paraphrased in the sentences; say who.
- tags: 3–5 short topic labels.
- timeline: only if the sentences give dates or periods (month, year, week); `when` exactly as written.
  Leave empty otherwise — never invent dates.
- headlines: one per section, max 60 characters, sentence case, written FROM THE FACTS so a reader gets
  the point from the headline alone (e.g. "Invoices approved in minutes instead of by email").
  NO numbers in headlines — neither digits nor numbers written as words; the numbers belong to the
  metrics. Leave a headline empty if nothing specific fits.
- Every text is a complete phrase or sentence. Never end with "…" and never cut a sentence short to fit;
  pick a shorter fact or rephrase within the budget instead.
- conclusion: ONE approved sentence about the result or what came next (client feedback, a follow-up
  contract), kept close to its wording. No verdicts ("a success", "proved", "set a new standard"), no
  lessons learned, no promises about the future, no summary of several sentences.
- Fill only what the sentences support. Empty fields are fine — the layout adapts to what exists.
- art: you are also the art director. Choose a layout that fits THIS project's content and mood:
  story (impact | transformation | journey | people | build), cover (hero-number | from-to | quote |
  statement | motif), frame — how pages are BUILT (dashboard = tiles for number-heavy work, magazine = text
  columns and pull quotes for story-led work, sidebar = side column of key facts, split = colour panel opening
  each section, stack = classic), theme (light | dark | bold | editorial), order (section keys from challenge, solution,
  journey, results, close), variants like "metrics=row" or "steps=vertical", density (airy | compact), and a
  one-sentence reason. You also choose the GRAPHS through variants, from what the numbers are:
  "comparison=columns" (vertical before/after columns — best for 2 pairs), "comparison=bars" (horizontal
  pairs — best for 3), "comparison=slope" (dot-to-dot on a line — good when all pairs are percentages),
  "comparison=from-to" (one big pair), "metrics=rings" (percentages drawn as rings — only when they are
  shares of a whole, like "92 % of staff"), "timeline=horizontal" or "timeline=vertical". Pick what the content earns: a hero number only if one result clearly stands out, a
  timeline story only with dates, editorial for people- or story-led projects, bold for strong numbers,
  dark for technical transformations. Two different projects should not look the same.
Voice: {voice}. Words never to use: {banned}."""

PROMPT = """Project: {title}
Client: {client}

Character budgets: {budgets}
Max items: {limits}

APPROVED SENTENCES:
{claims}

Return the report plan as JSON. For the plain string fields (title, subtitle, client_line,
challenge_intro, brief, solution_intro, conclusion) and the headlines put their citations in `cites`
as a list of {{"field": ..., "ids": [...]}} ("headlines.results" for a headline)."""


def build_report(record: ProjectRecord, brand: BrandKit, llm: LLM | None) -> ReportDesign:
    if not can_export(record):
        raise ReviewError("Approve the case study first — the report is designed only from approved text.")
    approved = record.active_claims()
    prev, art, plan, notes = record.report, Prefs(), None, []
    rules_plan = _offline_plan(record)       # always made: it is the safety net under the model's plan
    if llm:
        last = ("" if prev is None else
                f"\n\nPREVIOUS DESIGN of this report: frame={prev.layout.frame}, theme={prev.layout.theme}, "
                f"cover={prev.layout.cover}, story={prev.layout.story}. The reviewer asked for a NEW design: "
                "choose a clearly different frame and theme, and a different cover if the content allows.")
        system = SYSTEM.format(voice=brand.voice, banned=", ".join(brand.banned_words) or "none")
        prompt = PROMPT.format(title=record.input.title or "(untitled)", client=record.input.client_name or "the client",
                               budgets=json.dumps(BUDGET), limits=json.dumps(LIMITS),
                               claims="\n".join(f"{c.id} [{c.section}]: {c.text}" for c in approved)) + last
        try:
            out = llm.generate_json(system, prompt, PlanOut)
            if _thin(out, rules_plan):   # seen live: a title, a subtitle and nothing else — ask once more
                record.log("report plan was thin", "asked the model again")
                again = llm.generate_json(system, prompt + THIN_RETRY, PlanOut)
                if _parts(again) > _parts(out):
                    out = again
            art, plan = out.art, out.to_plan()
        except LLMError as e:
            notes.append("The AI designer was busy, so this report was laid out by rules from your approved "
                         f"sentences. Press Redesign to try the AI again. ({str(e)[:90]})")
        record.llm_calls = llm.calls
    if plan is None:
        plan = rules_plan
    else:
        filled = _backfill(plan, rules_plan)
        if filled:
            notes.append("The AI left these parts empty, so they were filled by rules from your approved "
                         "sentences: " + ", ".join(filled) + ".")
    plan = _trim(polish(plan, record.input.source_text()))
    rnd = prev.round + 1 if prev else 0
    design = ReportDesign(brand=brand, plan=plan, based_on_hash=record.approved_hash, notes=notes, round=rnd,
                          prefs=vary(art, plan, prev, rnd))
    check_report(record, design, llm)
    repair_framing(record, design, rules_plan, llm)
    record.report = design
    record.log("report designed", f"{len(design.elements)} elements, {len(design.blocking)} flagged, "
               f"{len(design.warnings)} warnings, brand {brand.name}")
    return design


_PARTS = ("challenges", "pillars", "steps", "outcomes", "metrics", "comparisons", "timeline", "tech")

THIN_RETRY = """

Your previous answer left most of the plan empty. The approved sentences above support far more:
fill metrics, comparisons, challenges, pillars, steps, outcomes, tech, the quote, the timeline (when dates
are given) and one headline per section — every part the sentences support."""


def _parts(plan: ReportPlan) -> int:
    return sum(bool(getattr(plan, g)) for g in _PARTS) + bool(plan.quote.text.strip())


def _thin(plan: ReportPlan, rules: ReportPlan) -> bool:
    """The model filled less than half of what the rule planner shows the approved text supports."""
    return _parts(plan) * 2 < _parts(rules)


def _backfill(plan: ReportPlan, rules: ReportPlan) -> list[str]:
    """A small model sometimes returns a thin plan — a title and two lines — although the approved text
    is full of results. Every part the model left EMPTY is filled from the rule-based plan (whole
    approved sentences), skipping anything the model already used. Nothing the model wrote is changed."""
    cited = {x for g in ("challenges", "pillars", "steps", "outcomes", "metrics", "comparisons", "timeline")
             for it in getattr(plan, g) for x in it.cites} | {x for ids in plan.cites.values() for x in ids} \
        | set(plan.quote.cites)
    shown = {q for p, t, _ in elements_of(plan) if p != "subtitle" for q in _quantities(t)}
    filled = []

    def fresh(items):
        return [it for it in items if not set(it.cites) & cited]

    for g, name in (("challenges", "challenges"), ("pillars", "what was built"), ("outcomes", "outcomes"),
                    ("timeline", "milestones")):
        if not getattr(plan, g) and fresh(getattr(rules, g)):
            setattr(plan, g, fresh(getattr(rules, g)))
            cited.update(x for it in getattr(plan, g) for x in it.cites)
            filled.append(name)
    if not plan.comparisons:
        pairs = [k for k in rules.comparisons
                 if not _repeats({(_fmt(k.before), _u(k.unit)), (_fmt(k.after), _u(k.unit))}, shown)]
        if pairs:
            plan.comparisons = pairs
            filled.append("before/after chart")
            shown |= {(_fmt(v), _u(k.unit)) for k in pairs for v in (k.before, k.after)}
    if not plan.metrics:
        nums = [m for m in rules.metrics if not _repeats({(m.value.replace(",", ""), _u(m.unit))}, shown)]
        if nums:
            plan.metrics = nums
            filled.append("key numbers")
    if not plan.tech and rules.tech:
        plan.tech, plan.cites["tech"] = rules.tech, rules.cites.get("tech", [])
        filled.append("tools")
    if not plan.quote.text.strip() and rules.quote.text:
        plan.quote = rules.quote
        filled.append("quote")
    return filled


# Frames and themes that suit each story. Which one a project gets depends on its own content (so two
# projects don't look alike) and on how many times it has been redesigned (so Redesign gives a new look).
SUITS = {"impact": (["dashboard", "split", "sidebar", "stack"], ["bold", "dark", "light"]),
         "transformation": (["split", "stack", "dashboard", "sidebar"], ["light", "dark", "bold"]),
         "journey": (["sidebar", "magazine", "stack", "split"], ["editorial", "light", "dark"]),
         "people": (["magazine", "stack", "split"], ["editorial", "light", "bold"]),
         "build": (["sidebar", "stack", "split", "magazine"], ["light", "dark", "editorial", "bold"])}


def vary(art: Prefs, plan: ReportPlan, prev: "ReportDesign | None", rnd: int) -> Prefs:
    """The art direction for this design. The art director's choices are kept; what it left open is
    chosen from the frames and themes that suit the story, by the content and the redesign count —
    and a redesign never repeats the look it replaces."""
    P = art.model_copy(deep=True)
    story = compose(plan, P).story
    frames, themes = SUITS[story]
    if len(plan.metrics) + len(plan.comparisons) < 3:
        frames = [f for f in frames if f != "dashboard"]          # tiles need numbers
    seed = int(hashlib.sha256(f"{plan.title}|{len(plan.metrics)}|{len(plan.timeline)}|{len(plan.steps)}|"
                              f"{bool(plan.quote.text)}".encode()).hexdigest()[:8], 16)
    if P.frame not in FRAMES:
        P.frame = frames[(seed + rnd) % len(frames)]
    if P.theme not in THEMES:
        P.theme = themes[(seed // 7 + rnd) % len(themes)]
    if prev is not None and (P.frame, P.theme) == (prev.layout.frame, prev.layout.theme):
        P.frame = next(f for f in frames + list(FRAMES) if f != prev.layout.frame)
        P.theme = next(t for t in themes + list(THEMES) if t != prev.layout.theme)
    _vary_graph(P, plan, seed + rnd, rnd)
    return P


def _vary_graph(P: Prefs, plan: ReportPlan, n: int, rnd: int) -> None:
    """Which graph draws the before/after pairs. The first design uses the one the numbers call for
    (layout.compose decides); a redesign moves on to the next style that can show the same pairs."""
    styles = {2: ["columns", "slope", "bars"]}.get(len(plan.comparisons), ["bars", "slope"] if len(plan.comparisons) > 2 else [])
    if rnd and styles and not any(v.startswith("comparison=") for v in P.variants):
        P.variants = P.variants + [f"comparison={styles[rnd % len(styles)]}"]


def _trim(plan: ReportPlan) -> ReportPlan:
    for key, n in LIMITS.items():
        setattr(plan, key, getattr(plan, key)[:n])
    plan.tags = [t for t in plan.tags if t.strip()]
    return plan


_PERSON = re.compile(
    r"\b([A-Z][a-z]+) ([A-Z][a-z]+)(?=,? \(|'s\b|,? (?:the )?(?:project|product|backend|frontend|qa|ux|ui|devops|"
    r"operations|finance|team|tech|engineering|design|account|managing|sales|marketing)\b)", re.I)


def people_in(source: str) -> set[str]:
    """First and last names of people the notes mention with a role ("Priya Raman, project manager",
    "Tomas Ferreira's notebook (backend lead)"). Used to keep people out of the list of tools."""
    out: set[str] = set()
    for m in _PERSON.finditer(source):
        a, b = m.group(1), m.group(2)
        if a[0].isupper() and b[0].isupper() and a[1:].islower() and b[1:].islower():
            out |= {a, b}
    return out


_INTENSIFIERS = ("significantly", "dramatically", "drastically", "greatly", "massively", "hugely", "vastly",
                 "substantially", "considerably", "tremendously", "remarkably", "immensely", "radically")
_INTENSE = re.compile(r",?\s+\b(" + "|".join(_INTENSIFIERS) + r")\b|\b(" + "|".join(_INTENSIFIERS) + r")\b\s+", re.I)


def _calm(text: str, src_words: set[str]) -> str:
    """Drops a degree word the notes never use ("reduced significantly" → "reduced"). The sentence keeps
    its facts and loses only the claim about how much."""
    def cut(m):
        return m.group(0) if (m.group(1) or m.group(2)).lower() in src_words else ""
    return _INTENSE.sub(cut, text).strip() if text else text


def polish(plan: ReportPlan, source: str) -> ReportPlan:
    """Tidy-up every plan goes through, whoever wrote it (model or offline rules). It only removes or
    trims — it never adds words, so nothing here can introduce an unchecked fact.
    - text is stripped; empty items go
    - the tools list holds tools only: no people, no duplicates, no part of a longer name ("ECS" next to "ECS Fargate")
    - each fact once: an item that repeats another element word for word is dropped, and a big number
      that is already one side of a before/after pair is dropped (the chart shows it)
    - degree words the notes never use ("significantly") are taken out"""
    for f in ("title", "subtitle", "client_line", "challenge_intro", "brief", "solution_intro", "conclusion"):
        setattr(plan, f, " ".join(getattr(plan, f).split()))
    plan.title = plan.title or "Case study"
    src_words = set(normalize(source).split())
    calm = lambda t: _calm(t, src_words)  # noqa: E731
    for f in ("title", "subtitle", "challenge_intro", "brief", "solution_intro", "conclusion"):
        setattr(plan, f, calm(getattr(plan, f)))
    for k, v in plan.headlines.model_dump().items():
        setattr(plan.headlines, k, calm(v))
    for g in ("challenges", "pillars", "steps", "outcomes"):
        for it in getattr(plan, g):
            it.title, it.text = calm(it.title), calm(it.text)
    for m in plan.metrics:
        m.label = calm(m.label)
    for g in ("challenges", "pillars", "steps", "outcomes"):
        items = getattr(plan, g)
        for it in items:
            it.title, it.text = " ".join(it.title.split()).rstrip(".:"), " ".join(it.text.split())
        setattr(plan, g, [it for it in items if it.text or it.title])
    plan.timeline = [e for e in plan.timeline if e.when.strip() and e.text.strip()]
    plan.metrics = [m for m in plan.metrics if m.value.strip() and re.search(r"\d", m.value)]
    for x in [*plan.metrics, *plan.comparisons]:   # "11.8 percent" prints as "11.8%"
        if re.fullmatch(r"\s*(per ?cent|pct)\s*", x.unit, re.I):
            x.unit = "%"
    # tools only
    people = people_in(source)
    seen: dict[str, str] = {}
    for t in (" ".join(x.split()).strip(" ,.;") for x in plan.tech):
        if t and t not in people and not all(w in people for w in t.split()):
            seen.setdefault(t.lower(), t)
    names = list(seen.values())
    plan.tech = [t for t in names if not any(t != o and re.search(rf"(?<![\w-]){re.escape(t)}(?![\w-])", o) for o in names)]
    # each fact once
    # (the cover subtitle is a summary line and may restate one item)
    said = {normalize(getattr(plan, f)) for f in ("challenge_intro", "brief", "solution_intro", "conclusion")}
    said.discard("")
    for g in ("challenges", "pillars", "steps", "outcomes"):
        keep = []
        for it in getattr(plan, g):
            key = normalize(it.text or it.title)
            if key and key in said:
                continue
            said.add(key)
            keep.append(it)
        setattr(plan, g, keep)
    pairs = {(_fmt(v), k.unit.strip()) for k in plan.comparisons for v in (k.before, k.after)}
    plan.metrics = [m for m in plan.metrics if (m.value.replace(",", ""), m.unit.strip()) not in pairs]
    _drop_repeats(plan)
    for e in plan.timeline:   # "9 February 2024: Contract signed 9 February 2024." → "…: Contract signed."
        e.text = _undated(e.text, e.when)
    return plan


_UNIT_ALIAS = {"s": "seco", "sec": "seco", "secs": "seco", "min": "minu", "mins": "minu", "h": "hour", "hr": "hour",
               "hrs": "hour", "ms": "mill", "k": "thou", "m": "mill", "pct": "%", "perc": "%"}


def _u(unit: str) -> str:
    unit = unit.strip().lower()
    return "%" if unit.startswith(("%", "percent")) else _UNIT_ALIAS.get(unit, unit[:4])


def _quantities(text: str) -> set[tuple[str, str]]:
    """The numbers in a text that are facts worth showing once, with what they count:
    {("14", "%")} for "from 14 percent", {("14", "ware")} for "14 warehouses". Dates, years and
    single digits are left out — "3 rounds", "2024" and "18 November" may appear anywhere."""
    out = set()
    for m in _NUM_RE.finditer(text):
        n = m.group(1).replace(",", "") + (f".{m.group(2)}" if m.group(2) else "")
        unit = _unit(text, m)
        if unit == "date" or (len(n) == 1 and n != "0") or re.fullmatch(r"(19|20)\d\d", n):
            continue
        out.add((n, _u(unit)))
    return out


def _shown_numbers(plan: ReportPlan) -> set[tuple[str, str]]:
    """What the big numbers and the chart already show."""
    q = {(m.value.replace(",", ""), _u(m.unit)) for m in plan.metrics}
    q |= {(_fmt(v), _u(k.unit)) for k in plan.comparisons for v in (k.before, k.after)}
    return q


def _repeats(q: set[tuple[str, str]], shown: set[tuple[str, str]]) -> set[tuple[str, str]]:
    """The quantities in q already shown: same number, and the same unit (or one side gives none)."""
    return {(n, u) for n, u in q for sn, su in shown if n == sn and (u == su or not u or not su)}


def _drop_repeats(plan: ReportPlan) -> None:
    """Each number once. The big numbers and the chart own their numbers; the brief and conclusion are
    dropped when they only restate numbers shown elsewhere; an item loses the clause that repeats a
    number ("1,340 routes planned and 96.2 percent logged in" → "1,340 routes planned" when 96.2 % is a
    big number), and goes when nothing new is left. Only removes text, never adds any."""
    shown = _shown_numbers(plan)
    cover = _quantities(plan.subtitle)
    for f in ("brief", "conclusion"):
        q = _quantities(getattr(plan, f))
        if q and not q - _repeats(q, shown | cover):
            setattr(plan, f, "")
            plan.cites.pop(f, None)
    for f in ("challenge_intro", "solution_intro", "brief", "conclusion"):
        shown |= _quantities(getattr(plan, f))
    for g in ("challenges", "pillars", "outcomes"):
        keep = []
        for it in getattr(plan, g):
            if _repeats(_quantities(it.text), shown):
                parts = [p.strip(" ,.;") for p in re.split(r";\s+|,?\s+and\s+(?=\S+\s+\S+)", it.text)]
                parts = [p for p in parts if len(p.split()) >= 3 and not _repeats(_quantities(p), shown)]
                if not parts or not any(_quantities(p) for p in parts) and _quantities(it.text):
                    continue          # nothing new left (or only the words around a repeated number)
                it.text = " and ".join(parts)
            shown |= _quantities(it.text)
            keep.append(it)
        setattr(plan, g, keep)
    # a milestone that only repeats a result ("February 2025: fuel consumption down 9.4 percent") goes
    plan.timeline = [e for e in plan.timeline if not _repeats(_quantities(_DATE.sub(" ", e.text)), shown)]


_DATE_TAIL = r"(?:\s+(?:was|were|is|on|in|by|at|of))*"


def _undated(text: str, when: str) -> str:
    """Takes the date out of a timeline line that already sits next to it. Only removes words."""
    if not when.strip() or when.lower() not in text.lower():
        return text
    out = re.sub(_DATE_TAIL + r"\s*\b" + re.escape(when) + r"\b[\s,.:;]*", " ", text, flags=re.I)
    out = re.sub(r"(?:\s+(?:was|were|is|on|in|by|at|of))+\s*$", "", out.strip(" ,.;:"), flags=re.I).strip(" ,.;:")
    if len(out.split()) < 1 or not re.search(r"[A-Za-z]{3}", out):
        return text
    return out[0].upper() + out[1:] + "."


# ------------------------------------------------------------------ checking
def elements_of(plan: ReportPlan) -> list[tuple[str, str, list[str]]]:
    """(path, text, cites) for every piece of text that will be printed."""
    c = plan.cites
    out: list[tuple[str, str, list[str]]] = []
    for f in ("title", "subtitle", "client_line", "challenge_intro", "brief", "solution_intro", "conclusion"):
        v = getattr(plan, f)
        if v.strip():
            out.append((f, v, c.get(f, [])))
    for k, v in plan.headlines.model_dump().items():
        if v.strip():
            out.append((f"headlines.{k}", v, c.get(f"headlines.{k}", [])))
    for i, e in enumerate(plan.timeline):
        out.append((f"timeline.{i}", f"{e.when}: {e.text}", e.cites))
    for group in ("challenges", "pillars", "steps", "outcomes"):
        for i, it in enumerate(getattr(plan, group)):
            out.append((f"{group}.{i}", f"{it.title}. {it.text}".strip(". "), it.cites))
    for i, m in enumerate(plan.metrics):
        txt = f"{m.value}{_spaced(m.unit)} {m.label}" + (" (estimated)" if m.estimate else "")
        out.append((f"metrics.{i}", txt, m.cites))
    for i, k in enumerate(plan.comparisons):
        u = " percent" if k.unit.strip() == "%" else _spaced(k.unit)  # written the way notes write it
        out.append((f"comparisons.{i}", f"{k.label}: from {_fmt(k.before)}{u} to {_fmt(k.after)}{u}"
                    + (" (estimated)" if k.estimate else ""), k.cites))
    if plan.quote.text.strip():
        out.append(("quote", f"{plan.quote.text} — {plan.quote.who}".strip(" —"), plan.quote.cites))
    if plan.tech:
        out.append(("tech", ", ".join(plan.tech), c.get("tech", [])))
    return out


def _clip(text: str, n: int) -> str:
    """Shorten at a word boundary — never cut a word (a cut word looks like a new, unchecked name)."""
    if len(text) <= n:
        return text
    return text[:n].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"


def _fmt(x: float) -> str:
    return f"{x:g}"


def _spaced(unit: str) -> str:
    """A unit that is a word gets a space before it ("18 minutes"); a sign does not ("14%")."""
    u = unit.strip()
    return f" {u}" if u[:1].isalpha() else unit


def check_report(record: ProjectRecord, design: ReportDesign, llm: LLM | None) -> None:
    """Checks every element; text that is unchanged since the last check keeps its verdict
    (so an edit or a layout change costs one small model call, not a full re-check)."""
    plan, known = design.plan, {c.id for c in record.active_claims()}
    prev = {e.text: e for e in design.elements if e.label is not None}
    els = []
    for path, text, cites in elements_of(plan):
        # a model sometimes cites an id that does not exist (a fact id instead of a sentence id): drop it
        cl = Claim(id=path, section="summary", text=text, fact_ids=[x for x in cites if x in known])
        if path in ("title", "tech", "client_line") or path.startswith(("steps.", "headlines.")):
            cl.manual = True  # headings/labels: rules + model still apply, no citation needed
        els.append(cl)
    src = record.input.source_text()
    _auto_cite(els, record)
    for cl in els:
        # Every element is checked against the NOTES by the rules and the model. The citation only says
        # which approved sentence it came from; a missing one must not fail a line the notes back.
        if not cl.fact_ids:
            cl.manual = True
    todo = []
    for cl in els:
        old = prev.get(cl.text)
        if old is not None:
            for f in ("label", "model_label", "reason", "evidence", "rule_flags", "fact_ids"):
                setattr(cl, f, getattr(old, f))
        else:
            todo.append(cl)
    try:
        label_claims(todo, src, known, llm, system=REPORT_CHECK_SYSTEM)
    except LLMError as e:
        label_claims(todo, src, known, None)
        note = ("The AI checker was busy: new text was checked by the rules only (numbers, names, wording, "
                "word overlap with your notes). Press Redesign later for the full check.")
        if note not in design.notes:
            design.notes.append(note)
        record.log("report check fell back to rules", str(e)[:160])
    _forgive_title_case(todo, plan)
    _estimate_tag_is_right(todo, plan, src)
    norm = normalize(src)
    for cl in els:  # a tech list is a set of names: each name must be in the notes, wherever it is
        if cl.id == "tech":
            missing = [t for t in plan.tech if not term_in_source(t, norm)]
            cl.label = Label.unsupported if missing else Label.supported
            cl.reason = (f"not in your notes: {', '.join(missing)}" if missing
                         else "every tool name appears in your notes")
    design.elements = els
    design.warnings = design.notes + report_warnings(plan, design.brand, src)
    design.layout = compose(plan, design.prefs)


REPORT_CHECK_SYSTEM = """You are a strict fact-checker for a designed, client-facing report. You did NOT write
the elements below and you have no reason to defend them.
The elements are short pieces of a page layout: headlines, labels, titles, big numbers with a caption,
"Label: from X to Y" pairs, "date: event" lines, short statements. They are condensed on purpose.
Compare each one ONLY against the SOURCE text and label it:
- supported: the source states it
- reworded: the same facts as the source, only condensed, reordered or phrased more professionally.
  A headline or title that names or sums up what the source says, without adding anything, is reworded.
  Dropping details is fine; a label like "Error rate: from 9 percent to 2.5 percent" is supported
  when the source gives both values for that thing.
- unsupported: it adds something the source does not state — a number, name, tool, date, client detail,
  outcome, cause ("because", "thanks to"), comparison or degree ("faster", "most", "significantly"),
  or it presents an estimate, plan or opinion in the source as a measured fact
- contradicted: it goes against the source
- "(estimated)" at the end of an element is the report's ESTIMATED tag. It is correct whenever the
  source hedges that number or either value of the pair in any wording ("about 40 hours", "roughly",
  "around", "estimate", "not verified"). Never fail an element for carrying the tag in that case.
  Fail it only when the source gives the values as exact, measured numbers.
- A subtitle, brief or headline describes the project in a few words. It is reworded when everything
  it mentions — who, what was done, what changed — is stated in the source. "The source does not
  phrase it that way" or "not written as a subtitle" is never a reason to fail it.
Being short is never a reason to fail an element; adding or changing a fact always is.
When unsure whether a fact was added, choose unsupported. `evidence` = the source text that supports or
contradicts it ("" if none). `reason` = one short sentence. Return one verdict for every element id."""


_TAG_REASON = re.compile(r"estimat|\btag\b|\blabel", re.I)


def _estimate_tag_is_right(els: list[Claim], plan: ReportPlan, source: str) -> None:
    """Whether a number is an estimate in the notes is a question the rules answer exactly (is there
    "about", "roughly", "estimate", "not verified" next to it?). So when the model fails a number ONLY
    for carrying the ESTIMATED tag, and the rules find that hedge in the notes — and found nothing else
    wrong — the tag stands. Any other objection from the model still blocks."""
    sents = re.split(r"(?<=[.!?])\s+", unwrap(source))
    for cl in els:
        head, _, idx = cl.id.partition(".")
        if head not in ("metrics", "comparisons") or cl.rule_flags or cl.label not in (Label.unsupported, Label.contradicted):
            continue
        model_reason = cl.reason.split(" | ")[-1]
        if not _TAG_REASON.search(model_reason):
            continue
        item = getattr(plan, head)[int(idx)]
        if not item.estimate:
            continue
        nums = [item.value.replace(",", "")] if head == "metrics" else [_fmt(item.before), _fmt(item.after)]
        holders = [s for s in sents if all(n in numbers_in(s) for n in nums)]
        hedge = next((s for s in holders if any(number_is_hedged(s, n) for n in nums)), None)
        if hedge:
            cl.label, cl.evidence = Label.reworded, hedge.strip()
            cl.reason = "the notes give this number as an estimate, so the ESTIMATED tag is right"


def repair_framing(record: ProjectRecord, design: "ReportDesign", rules: ReportPlan, llm: LLM | None) -> None:
    """Right after a report is designed: framing lines the checker rejected are not left for the reviewer.
    A rejected headline gives way to the plain section label; a rejected subtitle or brief is replaced by
    an approved sentence (the rule planner's pick) or dropped. Only approved text comes in, and it is
    checked again. Facts, numbers and items that fail are NOT touched — those stay red for a person."""
    plan, changed = design.plan, []
    for e in list(design.blocking):
        head, _, key = e.id.partition(".")
        if head == "headlines" or e.id in ("subtitle", "brief", "challenge_intro", "solution_intro", "conclusion"):
            record.log("report framing rejected", f"{e.id}: \"{e.text}\" — {e.reason[:200]}")  # to tune the prompts
        if head == "headlines":
            setattr(plan.headlines, key, "")
            changed.append(f"the {key} headline")
        elif e.id == "subtitle":
            plan.subtitle = rules.subtitle if rules.subtitle and rules.subtitle != plan.subtitle else ""
            plan.cites["subtitle"] = rules.cites.get("subtitle", []) if plan.subtitle else []
            changed.append("the subtitle")
        elif e.id in ("brief", "challenge_intro", "solution_intro", "conclusion"):
            setattr(plan, e.id, "")          # an intro line restates the items under it; the items stay
            changed.append("the " + e.id.replace("_", " "))
    if changed:
        design.notes.append("The checker rejected " + ", ".join(changed) + " as written by the AI, so "
                            + ("they were" if len(changed) > 1 else "it was")
                            + " replaced by plain labels or approved sentences. Type in the chat to word them yourself.")
        check_report(record, design, llm)
        record.log("report framing auto-repaired", ", ".join(changed))


def redesign(record: ProjectRecord, by: str = "") -> ReportDesign:
    """A different look for the same report: new page structure, theme, cover and graph style. The
    wording does not change, so nothing has to be checked again and nothing new can turn red."""
    d = _design(record)
    _apply_op(d, ChatOp(op="layout", target="shuffle"))
    d.prefs.reason = ""   # the art director's reason was about the look this one replaces
    _withdraw(d)
    check_report(record, d, None)
    record.log("report redesigned", f"{d.layout.frame}, {d.layout.theme}, {d.layout.cover} cover", by)
    return d


def _auto_cite(els: list[Claim], record: ProjectRecord) -> None:
    """An element the planner forgot to cite gets the approved sentences it overlaps most with.
    (It is still checked against the notes on its own; this keeps every element traceable.)"""
    approved = record.active_claims()
    for cl in els:
        if cl.fact_ids or cl.manual:
            continue
        cw = content_words(cl.text)
        scored = sorted(((len(cw & content_words(c.text)) / max(1, len(cw)), c.id) for c in approved), reverse=True)
        cl.fact_ids = [cid for sc, cid in scored[:2] if sc >= 0.25]


def _forgive_title_case(els: list[Claim], plan: ReportPlan) -> None:
    """'Constraint Integration' in a step title is title case, not a product name. The name rule is
    dropped for plain Capitalised words that appear only in a heading; the model check still applies."""
    heads: dict[str, str] = {"title": plan.title}
    heads.update({f"headlines.{k}": v for k, v in plan.headlines.model_dump().items()})
    for g in ("challenges", "pillars", "steps", "outcomes"):
        for i, it in enumerate(getattr(plan, g)):
            heads[f"{g}.{i}"] = it.title
    for cl in els:
        head = heads.get(cl.id, "")
        if not head or not cl.rule_flags:
            continue
        words = {w for w in re.findall(r"[A-Za-z]+", head) if w[0].isupper() and w[1:].islower()}
        keep = [f for f in cl.rule_flags if not (f.startswith("name '") and f[6:f.index("'", 6)] in words)]
        if len(keep) == len(cl.rule_flags):
            continue
        cl.rule_flags = keep
        model = cl.model_label
        cl.label = worst(Label.unsupported if keep else None, model)
        mreason = cl.reason.split(" | ", 1)[-1] if " | " in cl.reason else ""
        cl.reason = ("; ".join(keep) + (f" | {mreason}" if mreason else "")) if keep else mreason


def report_warnings(plan: ReportPlan, brand: BrandKit, source: str) -> list[str]:
    w: list[str] = []
    # each fact once: the same number printed in two different places
    # (the 18 in "18 November" is not the 18 in "18 minutes", and "14 warehouses" is not "14 percent")
    seen: dict[tuple[str, str], str] = {}
    for path, text, _ in elements_of(plan):
        if path.startswith("steps.") or path in ("tech", "subtitle"):
            continue   # the cover subtitle may restate the headline result
        for q in sorted(_quantities(_DATE.sub(" ", text))):
            hit = next((p for k, p in seen.items() if _repeats({q}, {k}) and p.split(".")[0] != path.split(".")[0]), None)
            if hit:
                w.append(f"'{q[0]}' appears twice ({hit} and {path}) — show each fact once")
            seen.setdefault(q, path)
    # estimates must stay labelled on the big numbers too
    sents = split_sentences(source)
    for i, m in enumerate(plan.metrics):
        n, shown = m.value.replace(",", ""), f"{m.value} {m.unit}".strip()
        units = {_unit(shown, x) for x in _spots(shown, n)} - {""}
        if not m.estimate and hedged_in_source(n, sents, units):
            w.append(f"metrics.{i}: '{m.value}{m.unit}' is an estimate in the notes — mark it ESTIMATED")
    # length budgets
    def over(path: str, text: str, key: str):
        if len(text) > BUDGET[key]:
            w.append(f"{path}: {len(text)} characters (budget {BUDGET[key]}) — the layout will shrink it")
    for f in ("title", "subtitle", "client_line", "challenge_intro", "brief", "solution_intro", "conclusion"):
        over(f, getattr(plan, f), f)
    for g in ("challenges", "pillars", "outcomes"):
        for i, it in enumerate(getattr(plan, g)):
            over(f"{g}.{i}", it.text, "item.text")
    for i, s in enumerate(plan.steps):
        over(f"steps.{i}", s.text, "step.text")
    for k, v in plan.headlines.model_dump().items():
        over(f"headlines.{k}", v, "headline")
    for i, e in enumerate(plan.timeline):
        over(f"timeline.{i}", e.text, "event.text")
    if not plan.metrics:
        w.append("No measured result to show as a big number — the results page uses outcomes only")
    w += text_warnings(brand, [(p, t) for p, t, _ in elements_of(plan)])
    return w


# ------------------------------------------------------------------ editing + approval
def edit_element(record: ProjectRecord, path: str, text: str, llm: LLM | None, by: str = "") -> None:
    """Edit the words of one element (title/text of an item, a string field, a metric label)."""
    d = _design(record)
    text = " ".join(text.split())
    _set_text(d.plan, path, text)
    _withdraw(d)
    check_report(record, d, llm)
    record.log("report edited", f"{path}: {text}", by)


def _set_text(plan: ReportPlan, path: str, text: str) -> None:
    head, _, idx = path.partition(".")
    if head in ("title", "subtitle", "client_line", "challenge_intro", "brief", "solution_intro", "conclusion"):
        setattr(plan, head, text)
    elif head in ("challenges", "pillars", "steps", "outcomes"):
        it = getattr(plan, head)[int(idx)]
        t, sep, rest = text.partition(". ")
        it.title, it.text = (t, rest) if sep else ("", text)
    elif head == "metrics":
        plan.metrics[int(idx)].label = text
    elif head == "quote":
        plan.quote.text = text
    elif head == "headlines":
        setattr(plan.headlines, idx, text)
    elif head == "timeline":
        ev = plan.timeline[int(idx)]
        when, sep, rest = text.partition(": ")
        ev.when, ev.text = (when, rest) if sep else (ev.when, text)
    else:
        raise ReviewError(f"Can't edit {path!r}")


def remove_element(record: ProjectRecord, path: str, by: str = "") -> None:
    d = _design(record)
    _remove(d, path)
    _withdraw(d)
    check_report(record, d, None)  # removal adds no text; the rest keep their verdicts
    record.log("report element removed", path, by)


def _remove(d: ReportDesign, path: str) -> None:
    head, _, idx = path.partition(".")
    if head in ("challenges", "pillars", "steps", "outcomes", "metrics", "comparisons", "timeline"):
        getattr(d.plan, head).pop(int(idx))
    elif head == "headlines":
        setattr(d.plan.headlines, idx, "")
    elif head == "quote":
        d.plan.quote = Quote()
    elif head == "tech":
        d.plan.tech = []
    elif head in ("subtitle", "client_line", "challenge_intro", "brief", "solution_intro", "conclusion"):
        setattr(d.plan, head, "")
    else:
        raise ReviewError(f"Can't remove {path!r}")


def set_metric_estimate(record: ProjectRecord, index: int, estimate: bool, llm: LLM | None, by: str = "") -> None:
    d = _design(record)
    d.plan.metrics[index].estimate = estimate
    _withdraw(d)
    check_report(record, d, llm)
    record.log("report metric relabelled", f"metrics.{index} estimate={estimate}", by)


# ------------------------------------------------------------------ report chat ("make the cover dark")
CHAT_SYSTEM = """You edit a designed case-study report for a reviewer who types requests in plain words.
You return a short friendly reply and a list of operations. Operations:
- {{"op":"text","target":"<element path>","value":"<new text>"}}  rewrite one element. New text may ONLY use
  facts from the APPROVED SENTENCES — no new numbers, names or outcomes. If the reviewer asks for a fact
  that is not there, say so in the reply and do not invent it.
- {{"op":"remove","target":"<element path>"}}
- {{"op":"layout","target":"story|cover|frame|theme|density|order|variant|hide|show|hero","value":"..."}}
  story: impact, transformation, journey, people, build · cover: hero-number, from-to, quote, statement, motif
  frame (page structure): dashboard, magazine, sidebar, split, stack
  theme: light, dark, bold, editorial · density: airy, compact · order: comma list of challenge, solution,
  journey, results, close · variant: e.g. metrics=row, metrics=hero, steps=vertical, steps=flow,
  pillars=cols3, outcomes=list, timeline=vertical, comparison=bars, quote=hero · hide/show: one of
  {hideable} · hero: index of the metric to put on the cover
- {{"op":"color","target":"primary|accent|ink|paper|surface|muted|dark","value":"#RRGGBB"}}
- {{"op":"estimate","target":"metrics.<i>","value":"true|false"}}
- {{"op":"brand","target":"name","value":"<company name>"}}  the publisher's name printed in the top corner
  and the footer of every page. To REMOVE that name or logo from the pages ("remove the header",
  "take my name off"), use {{"op":"layout","target":"hide","value":"brand"}}; "show" brings it back.
  The header name is not one of the report elements below — it is the brand, and you can change it.
- {{"op":"layout","target":"shuffle","value":""}}  a different design: new frame, theme and cover
- {{"op":"note","target":"","value":"<the fact>"}}  the reviewer tells you a NEW fact that is not in the
  approved sentences ("add that we trained 30 people", "the client is Acme Clinics"). Copy the fact from the
  reviewer's message in their own words — do not add to it. It is saved to the project notes under the
  reviewer's name, and you may then use it in a text operation in the same reply.
Charts are variants: comparison=bars (horizontal pairs), comparison=columns (vertical pairs),
comparison=slope (dot-to-dot), comparison=from-to (one big pair); metrics=rings draws percentages as rings.
Element paths look like: title, subtitle, brief, headlines.results, metrics.0, steps.2, outcomes.1, quote.
Do only what was asked. If a request is unclear or impossible, explain in the reply and return no ops.
Words never to use: {banned}."""

CHAT_PROMPT = """APPROVED SENTENCES (the only facts allowed):
{claims}

CURRENT REPORT ELEMENTS:
{elements}

CURRENT LAYOUT: story={story}, cover={cover}, frame={frame}, theme={theme}, density={density}, pages={pages}
CURRENT COLOURS: {colors}

RECENT CHAT:
{history}

REVIEWER: {message}"""

_HEX = re.compile(r"#[0-9a-fA-F]{6}\b")


def chat_report(record: ProjectRecord, message: str, llm: LLM | None, by: str = "") -> str:
    """Apply a plain-words request to the designed report. New text is checked like everything else;
    the reply says what changed and what got flagged. Any change withdraws the report's approval."""
    d = _design(record)
    message = message.strip()[:600]
    if not message:
        raise ReviewError("Type what you'd like to change.")
    d.chat.append(ChatMsg(role="user", text=message))
    L = d.layout
    busy_note = False
    if llm:
        try:
            out = llm.generate_json(
                CHAT_SYSTEM.format(hideable=", ".join(HIDEABLE), banned=", ".join(d.brand.banned_words) or "none"),
                CHAT_PROMPT.format(
                    claims="\n".join(f"{c.id}: {c.text}" for c in record.active_claims()),
                    elements="\n".join(f"{e.id}: {e.text}" for e in d.elements),
                    story=L.story, cover=L.cover, frame=L.frame, theme=L.theme, density=L.density or "normal",
                    pages=" | ".join(" + ".join(x.key for x in pg.sections) for pg in L.pages),
                    colors=", ".join(f"{k} {v}" for k, v in d.brand.colors.model_dump().items()),
                    history="\n".join(f"{m.role}: {m.text}" for m in d.chat[-7:-1]) or "(none)",
                    message=message),
                ChatOut)
        except LLMError:
            out = _offline_chat(message, d)   # the AI is busy: simple requests still work
            out.reply = ("The AI is busy right now, so I only did the simple parts. " + out.reply) if not out.ops else ""
            busy_note = True
        record.llm_calls = llm.calls
    else:
        out = _offline_chat(message, d)
    before = {e.id: e.label for e in d.elements}
    done, failed, text_changed = [], [], False
    for op in sorted(out.ops[:12], key=lambda o: o.op.strip().lower() != "note"):   # notes first: text may use them
        try:
            if op.op.strip().lower() == "note":
                fact = " ".join(op.value.split())
                if not fact or not quote_in_source(fact, message, 0.8):
                    raise ValueError("a note has to be the reviewer's own words")
                record.input.reviewer_additions.append(f"Added by {by or 'the reviewer'} in the report chat: {fact}")
                record.log("note added in report chat", fact, by)
                done.append("saved your note")
                text_changed = True
                continue
            what = _apply_op(d, op)
            if what:
                done.append(what)
                text_changed |= op.op == "text"
        except (ReviewError, ValueError, IndexError, KeyError) as e:
            failed.append(f"{op.op} {op.target}: {e}")
    if done:
        _withdraw(d)
        check_report(record, d, llm if text_changed else None)
    reply = out.reply.strip() or ("Done — " + ", ".join(done) + "." if done else "I couldn't change anything for that request.")
    flagged = [e for e in d.elements if e.blocking and before.get(e.id) != e.label]
    if flagged:
        reply += " Heads up: " + "; ".join(f"{e.id} isn't backed by your notes ({e.reason.split(' | ')[0]})"
                                          for e in flagged[:3]) + " — it's marked red, edit or remove it."
    if busy_note and done:
        reply = "The AI is busy right now, so I only did the simple parts. " + reply
    if failed and not done:
        reply += " (Nothing changed.)"
    d.chat.append(ChatMsg(role="ai", text=reply))
    d.chat = d.chat[-40:]
    record.log("report chat", f"{message} → {', '.join(done) or 'no change'}", by)
    return reply


def _apply_op(d: ReportDesign, op: ChatOp) -> str:
    P, kind, t, v = d.prefs, op.op.strip().lower(), op.target.strip(), op.value.strip()
    if kind == "text":
        if not v:
            raise ValueError("empty text")
        _set_text(d.plan, t, " ".join(v.split()))
        return f"rewrote {t}"
    if kind == "remove":
        _remove(d, t)
        return f"removed {t}"
    if kind == "estimate":
        d.plan.metrics[int(t.split(".")[1])].estimate = v.lower() in ("true", "yes", "1")
        return f"{t} estimate={v}"
    if kind == "color":
        if t not in type(d.brand.colors).model_fields or not _HEX.fullmatch(v):
            raise ValueError("needs a colour role and a #RRGGBB value")
        setattr(d.brand.colors, t, v.upper())
        return f"{t} colour {v}"
    if kind == "brand":
        if not v:
            raise ValueError("needs a company name")
        d.brand.company = " ".join(v.split())[:80]
        P.hide = [x for x in P.hide if x != "brand"]
        return f"company name on the pages: {d.brand.company}"
    if kind != "layout":
        raise ValueError("unknown operation")
    allowed = {"story": STORIES, "cover": COVERS, "frame": FRAMES, "theme": THEMES, "density": ("airy", "compact", "normal")}
    if t in allowed:
        if v not in allowed[t]:
            raise ValueError(f"{t} must be one of {', '.join(allowed[t])}")
        setattr(P, t, "" if v == "normal" else v)
        return f"{t} → {v}"
    if t == "order":
        keys = [k.strip() for k in v.split(",") if k.strip() in SECTION_KEYS]
        if not keys:
            raise ValueError("no known sections")
        P.order = keys
        return "order → " + ", ".join(keys)
    if t == "variant":
        k, _, val = v.partition("=")
        if val not in VARIANTS.get(k, ()):
            raise ValueError("unknown variant")
        P.variants = [x for x in P.variants if not x.startswith(k + "=")] + [v]
        return f"{k} shown as {val}"
    if t in ("hide", "show"):
        if v not in HIDEABLE:
            raise ValueError("can't hide that")
        P.hide = [x for x in P.hide if x != v] + ([v] if t == "hide" else [])
        return ("company name and logo taken off the pages" if t == "hide" else "company name and logo back on the pages") \
            if v == "brand" else f"{t} {v}"
    if t == "hero":
        P.hero_metric, P.cover = int(v), "hero-number"
        return f"cover number → metrics.{v}"
    if t == "shuffle":
        L = d.layout
        frames, themes = SUITS.get(L.story, (list(FRAMES), list(THEMES)))
        opts = [f for f in frames if f != L.frame] or [f for f in FRAMES if f != L.frame]
        P.frame = opts[d.round % len(opts)]
        opts = [x for x in themes if x != L.theme] or [x for x in THEMES if x != L.theme]
        P.theme = opts[d.round % len(opts)]
        covers = [c for c in COVERS if c != L.cover and compose(d.plan, P.model_copy(update={"cover": c})).cover == c]
        if covers:
            P.cover = covers[d.round % len(covers)]
        d.round += 1
        P.variants = [x for x in P.variants if not x.startswith("comparison=")]
        _vary_graph(P, d.plan, d.round, d.round)
        return f"new design: {P.frame}, {P.theme}"
    raise ValueError("unknown layout setting")


_OFFLINE_WORDS = [  # (pattern, op) — enough to demo without a model; Gemini understands anything
    (r"\bdark\b", ChatOp(op="layout", target="theme", value="dark")),
    (r"\blight\b|\bwhite\b", ChatOp(op="layout", target="theme", value="light")),
    (r"\bbold\b|\bcolou?rful\b", ChatOp(op="layout", target="theme", value="bold")),
    (r"\beditorial\b|\bminimal\w*\b|\belegant\b", ChatOp(op="layout", target="theme", value="editorial")),
    (r"\bmagazine\b|\b(text|two) columns\b|\barticle\b", ChatOp(op="layout", target="frame", value="magazine")),
    (r"\bdashboard\b|\btiles?\b|\bkpi\b", ChatOp(op="layout", target="frame", value="dashboard")),
    (r"\bsidebar\b|side column", ChatOp(op="layout", target="frame", value="sidebar")),
    (r"\bsplit\b|colou?r (panel|band|block)s?", ChatOp(op="layout", target="frame", value="split")),
    (r"\bclassic\b|\bsimple\b|\bplain\b", ChatOp(op="layout", target="frame", value="stack")),
    (r"(results|numbers) first|start with the (results|numbers)", ChatOp(op="layout", target="order", value="results,challenge,solution")),
    (r"compact|fewer pages|shorter", ChatOp(op="layout", target="density", value="compact")),
    (r"more space|airy|breath", ChatOp(op="layout", target="density", value="airy")),
    (r"cover.*(number|metric)|(number|metric).*cover", ChatOp(op="layout", target="cover", value="hero-number")),
    (r"cover.*quote|quote.*cover", ChatOp(op="layout", target="cover", value="quote")),
    (r"cover.*(title|text|typograph)", ChatOp(op="layout", target="cover", value="statement")),
    (r"vertical (steps|process)|(steps|process).*vertical", ChatOp(op="layout", target="variant", value="steps=vertical")),
    (r"\b(different|another|new|fresh|other)\b.*\b(design|layout|look|style)\b|\bshuffle\b|\bredesign\b|surprise me",
     ChatOp(op="layout", target="shuffle")),
    (r"\brings?\b|\bdonuts?\b|\bgauges?\b", ChatOp(op="layout", target="variant", value="metrics=rings")),
    (r"\bcolumns?\b.*\b(chart|graph)|\b(chart|graph)\b.*\bcolumns?\b|vertical bars?\b",
     ChatOp(op="layout", target="variant", value="comparison=columns")),
    (r"\bslope\b|\bdot (chart|plot)|\bdumbbell\b", ChatOp(op="layout", target="variant", value="comparison=slope")),
    (r"\b(bar|horizontal) (chart|graph)\b", ChatOp(op="layout", target="variant", value="comparison=bars")),
]
_HIDE_WORDS = {"timeline": "timeline", "quote": "quote", "tools": "tech", "tech": "tech", "chart": "comparison",
               "comparison": "comparison", "brief": "brief", "outcome": "outcomes", "client": "client",
               "header": "brand", "workspace": "brand", "logo": "brand", "company name": "brand", "my name": "brand",
               "watermark name": "brand"}


def _offline_chat(message: str, d: ReportDesign) -> ChatOut:
    m = message.lower()
    ops = [op for pat, op in _OFFLINE_WORDS if re.search(pat, m)]
    if re.search(r"\b(remove|hide|drop|delete|without|no)\b", m):
        ops += [ChatOp(op="layout", target="hide", value=k) for w, k in _HIDE_WORDS.items() if w in m]
    elif re.search(r"\b(show|bring back|add back)\b", m):
        ops += [ChatOp(op="layout", target="show", value=k) for w, k in _HIDE_WORDS.items() if w in m]
    note = re.match(r"\s*(?:add (?:a |this |the )?(?:note|fact)|note|add that|fact)\s*[:\-]?\s*(.{8,})", message, re.I)
    if note:
        ops.append(ChatOp(op="note", value=note.group(1).strip()))
    hexes = _HEX.findall(message)
    if hexes:
        ops.append(ChatOp(op="color", target="accent" if "accent" in m else "primary", value=hexes[0]))
    reply = ("" if ops else   # (with ops the reply lists what actually changed)
             "Without the AI I understand: a different design, dark / bold / editorial / light, magazine / "
             "dashboard / sidebar / split, results first, fewer pages, rings or a column chart, a #hex colour, "
             "hide the timeline or quote, and \"note: <a fact to add>\". With Gemini on you can ask in any words "
             "and I can rewrite text too.")
    return ChatOut(reply=reply, ops=ops)


def set_brand(record: ProjectRecord, brand: BrandKit, by: str = "") -> None:
    d = _design(record)
    d.brand = brand
    _withdraw(d)
    check_report(record, d, None)  # same text → verdicts reused; brand word rules re-run
    record.log("report brand changed", brand.name, by)


def approve_report(record: ProjectRecord, reviewer: str) -> None:
    d = _design(record)
    problems = report_blockers(record)
    if problems:
        raise ReviewError("Cannot approve the report:\n- " + "\n- ".join(problems))
    d.approved_by, d.approved_at, d.approved_hash = reviewer.strip(), now(), d.design_hash()
    record.log("report approved", d.approved_hash[:12], reviewer)


def report_blockers(record: ProjectRecord) -> list[str]:
    d = record.report
    if d is None:
        return ["no report designed yet"]
    out = []
    if not can_export(record) or d.based_on_hash != record.approved_hash:
        out.append("the case study changed since the report was designed — design it again")
    out += [f"{e.id} is {e.label.value if e.label else 'unchecked'}: {e.text}" for e in d.blocking]
    return out


def report_ready(record: ProjectRecord) -> bool:
    d = record.report
    return bool(d and d.approved_hash and d.approved_hash == d.design_hash() and not report_blockers(record))


def _design(record: ProjectRecord) -> ReportDesign:
    if record.report is None:
        raise ReviewError("Design the report first.")
    return record.report


def _withdraw(d: ReportDesign) -> None:
    d.approved_by = d.approved_at = d.approved_hash = ""


# ------------------------------------------------------------------ offline planner (no model)
# Without a model nothing is rewritten: the planner PICKS approved sentences (or a whole clause of one)
# and gives each a place. Rules decide what is a result, a before/after pair, a milestone, a tool.
_HEDGE = r"(?:about|around|roughly|approximately|nearly|almost|approx\.?|~)\s*"
_NUM = r"(\d[\d,]*(?:\.\d+)?)"
_UNITW = (r"percent|%|minutes?|mins?|seconds?|secs?|hours?|hrs?|days?|weeks?|months?|milliseconds?|ms|euros?|€|"
          r"dollars?|usd|eur|km|times")
_UNITS = {"percent": "%", "%": "%", "minute": " min", "minutes": " min", "min": " min", "mins": " min",
          "second": " s", "seconds": " s", "sec": " s", "secs": " s", "hour": " h", "hours": " h", "hr": " h",
          "hrs": " h", "day": " days", "days": " days", "week": " weeks", "weeks": " weeks", "month": " months",
          "months": " months", "ms": " ms", "millisecond": " ms", "milliseconds": " ms", "euro": " €",
          "euros": " €", "€": " €", "eur": " €", "dollar": " $", "dollars": " $", "usd": " $", "km": " km",
          "times": "×"}
_SCALE = {"million": "M", "billion": "B", "thousand": "k"}
_MEASURE = re.compile(rf"(?<![\w.,/-])({_HEDGE})?{_NUM}\s*(million|billion|thousand)?\s*({_UNITW})(?![\w])", re.I)
_FROMTO = re.compile(rf"\bfrom\s+({_HEDGE})?{_NUM}\s*({_UNITW})?\s*to\s+({_HEDGE})?{_NUM}\s*({_UNITW})?(?![\w])", re.I)
_WASTO = re.compile(rf"\b(?:was|were)\s+({_HEDGE})?{_NUM}\s*({_UNITW})?[^.;]{{0,48}}?\b(?:reduced|cut|down|dropped|"
                    rf"fell|rose|up|increased|improved|grew)\s+to\s+({_HEDGE})?{_NUM}\s*({_UNITW})?(?![\w])", re.I)
_CHANGE = re.compile(r"\b(reduc\w*|down|dropp\w*|fell|cut|sav\w*|improv\w*|rose|increas\w*|grew|faster|fewer|"
                     r"shorter|lower|higher|up)\b", re.I)
_PAIN = re.compile(r"\b(complain\w*|outdated|out of date|incomplete|delay\w*|hardest|hard|difficult|manual\w*|by hand|"
                   r"spreadsheets?|problems?|bugs?|incidents?|nobody|couldn't|could not|no way to|slow|errors?|"
                   r"needed|wanted|forgot|missed|every (?:morning|day|week|friday))\b", re.I)
_BUILT = re.compile(r"\b(built|build|wrote|written|created|added|developed|implemented|designed|deployed|uses|"
                    r"supports?|chose|made|set up|we did|migrated|automated|integrated|introduced|replaced|trained|ranks?|sends?|"
                    r"reads?|shows?|links?|scans?|answers?|alerts?)\b", re.I)
_GOOD = re.compile(r"\b(feedback|said|award\w*|asked to keep|adopt\w*|rolled out|went live|live|launched|now|"
                   r"happy|keep using|uses? it|will use|faster|fewer|less)\b", re.I)
_GOOD_ANYWHERE = re.compile(r"\b(award\w*|follow-up|asked to keep|feedback|phase 2|training sessions?|"
                            r"staff (?:were )?trained)\b", re.I)
_MILESTONE = re.compile(r"\b(signed|kick-?off|live|launch\w*|releas\w*|award\w*|start\w*|complet\w*|deliver\w*|"
                        r"review|retrospective|pilot|handover|rolled out|moved|built|tested|trained|opened|migrat\w*)\b", re.I)
_VERBS = {"reduced", "cut", "fell", "dropped", "went", "down", "up", "rose", "increased", "decreased", "improved",
          "moved", "changed", "grew", "shrank", "and", "the", "was", "were", "from", "by", "a", "an", "of", "is", "has"}
_CONTRAST = re.compile(r"^\W*(but|although|though|however|except|yet|despite)\b", re.I)
_BREAK = re.compile(r"[,;:]\s+|\s+[—–-]\s+|\s+(?=(?:because|so that|which|while|after|when|although|but)\b)")


def shorten(text: str, n: int) -> str:
    """Fit a sentence into a budget by ending it at a clause boundary. Never mid-phrase, never "…".
    Returns "" when there is no honest cut: the rest carries a "but", or the estimate wording."""
    text = text.strip()
    if len(text) <= n:
        return text
    # never at a colon: "Two production incidents in the first month: …" — the part before it is a heading
    cut = max((m.start() for m in _BREAK.finditer(text)
               if max(24, n * 0.25) <= m.start() < n and text[m.start()] != ":"), default=-1)
    if cut < 0:
        return ""
    head, tail = text[:cut].rstrip(" ,;:—–-"), text[cut:].lstrip(" ,;:—–-")
    if _CONTRAST.match(tail) or head.count("(") != head.count(")"):
        return ""
    if not is_hedged(head):  # the estimate wording must not be cut away from the number it belongs to
        nums = numbers_in(head)
        if any(number_is_hedged(text, x) for x in nums) or (not nums and is_hedged(tail)):
            return ""
    return head + "."


def _clauses(text: str) -> list[str]:
    return [c.strip(" .") for c in re.split(r"[,;:]\s+|\s+and\s+(?=[a-z])|\s+but\s+", text) if c.strip(" .")]


def _subject(text: str, start: int) -> str:
    """What a "from X to Y" change measures: the words just before it in the same clause."""
    before = re.split(r"[,;:]\s+|\s+and\s+|\s+but\s+", text[:start])[-1]
    words = re.findall(r"[A-Za-z0-9][\w\-/]*", before)
    while words and words[-1].lower() in _VERBS:
        words.pop()
    while words and words[0].lower() in ("the", "a", "an", "our", "their"):
        words.pop(0)
    if len(words) > 8:
        words = words[-5:]
    label = " ".join(words)
    return label[0].upper() + label[1:] if label else "Before and after"


_TECH = ["React Native", "Google OR-Tools", "OR-Tools", "ECS Fargate", "GitHub Actions", "Google Cloud", "Power BI",
         "SAP S/4HANA", "Node.js", "Next.js", "Vue.js", "scikit-learn", "Python", "JavaScript", "TypeScript", "Java",
         "Kotlin", "Swift", "Rust", "Golang", "PHP", "Ruby", "C#", "C++", "SQL", "React", "Vue", "Angular", "Svelte",
         "Django", "Flask", "FastAPI", "Spring", "Rails", "Laravel", "Flutter", "PostgreSQL", "Postgres", "PostGIS",
         "MySQL", "SQLite", "MongoDB", "Redis", "Elasticsearch", "Kafka", "RabbitMQ", "AWS", "Azure", "GCP", "Docker",
         "Kubernetes", "Terraform", "GitHub", "GitLab", "Jenkins", "Grafana", "Prometheus", "PagerDuty", "Figma",
         "Playwright", "Selenium", "pytest", "PyTorch", "TensorFlow", "pandas", "NumPy", "OpenAI", "Gemini",
         "Streamlit", "Excel", "Tableau", "Twilio", "Stripe", "Firebase", "Supabase", "HTMX", "Tailwind", "LangChain",
         "OpenCV", "GraphQL", "Nginx", "Android", "iOS", "Zapier", "Airtable", "Notion", "Slack", "WhatsApp"]
_TECH_RE = re.compile(r"(?<![\w.#+-])(" + "|".join(re.escape(t) for t in sorted(_TECH, key=len, reverse=True))
                      + r")(?![\w#+]|\.\w|-\w)", re.I)
_CANON = {t.lower(): t for t in _TECH}


_AMBIGUOUS = {"spring", "swift", "rust", "rails", "notion", "slack", "gemini", "vue", "flask", "java", "ruby",
              "excel", "android", "kafka", "stripe", "tableau", "selenium", "angular", "docker"}  # also plain words


def tools_in(texts: list[str]) -> list[str]:
    """Known tool names found in the sentences, in the notes' own spelling (lower-case notes are capitalised)."""
    seen: dict[str, str] = {}
    for text in texts:
        for m in _TECH_RE.finditer(text):
            raw = m.group(1)
            if raw.islower() and raw in _AMBIGUOUS and raw not in ("excel", "android", "docker", "flask", "kafka"):
                continue  # "the spring intake" is not the Spring framework
            name = raw if not raw.islower() else raw.upper() if len(raw) <= 3 else raw.capitalize()
            seen.setdefault(raw.lower(), name)
    return list(seen.values())


_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
           "november", "december"]
_DATE = re.compile(r"\b(?:(\d{1,2}) )?(January|February|March|April|May|June|July|August|September|October|"
                   r"November|December) ((?:19|20)\d{2})\b|\b(Q[1-4]) ((?:19|20)\d{2})\b", re.I)
_SAID = re.compile(r"(?:from|of|by)\s+(?:the (?:email|message|letter|note) of\s+)?"
                   r"(?P<who>[A-Z][a-z]+(?: (?:de|van|von|der|den|al|bin|di|da|la|le))*(?: [A-Z][a-z]+)+)"
                   r"(?:,\s*(?P<role>[a-z][^,:]{3,60}?))?(?:,[^:]{0,40})?:\s*(?:he|she|they) said\s+(?:that\s+)?(?P<text>[^.!?]{20,240}[.!?]?)")
_DIRECT = re.compile(r"[\"“]([^\"”]{20,220})[\"”]\s*(?:[-—–,]\s*|said\s+)([A-Z][\w .]{2,50}?)(?=[.,;\n]|$)")


def _offline_plan(record: ProjectRecord) -> ReportPlan:
    src = record.input.source_text()
    claims = [c for c in record.active_claims() if c.section != "summary"]
    sec = lambda *keys: [c for c in claims if c.section in keys]  # noqa: E731
    used: set[str] = set()
    p = ReportPlan(title=record.input.title or "Case study", client_line=record.input.client_name)

    # ---- results: before/after pairs and big numbers, found clause by clause
    scored: list[tuple[int, int, Metric]] = []
    for order, c in enumerate(claims):
        pair_spans = []
        for rx in (_FROMTO, _WASTO):
            for m in rx.finditer(c.text):
                unit = _UNITS.get((m.group(3) or m.group(6) or "").lower(), "")
                same = not (m.group(3) and m.group(6)) or _UNITS.get(m.group(3).lower()) == _UNITS.get(m.group(6).lower())
                if not same or any(a <= m.start() < b for a, b in pair_spans):
                    continue
                pair_spans.append(m.span())
                p.comparisons.append(Comparison(
                    label=_subject(c.text, m.start()), before=float(m.group(2).replace(",", "")),
                    after=float(m.group(5).replace(",", "")), unit=unit,
                    estimate=bool(m.group(1) or m.group(4)), cites=[c.id]))
                used.add(c.id)
        pos = 0
        for clause in _clauses(c.text):
            at = c.text.find(clause, pos)
            pos = at + len(clause) if at >= 0 else pos
            if any(a < at + len(clause) and at < b for a, b in pair_spans) or not 3 <= len(clause.split()) <= 18:
                continue
            m = _MEASURE.search(clause)
            if not m:
                continue
            unit = _UNITS.get(m.group(4).lower(), "")
            hedged = bool(m.group(1)) or is_hedged(clause) or (is_hedged(c.text) and len(_clauses(c.text)) <= 2)
            score = (3 if _CHANGE.search(clause) else 0) + (2 if unit == "%" else 0) + (1 if c.section == "results" else 0) \
                - (3 if hedged else 0)   # a measured result beats an estimate for a big number
            if score < 3:
                continue
            label = clause[0].upper() + clause[1:]
            scored.append((-score, order, Metric(value=m.group(2), unit=_SCALE.get((m.group(3) or "").lower(), "") + unit
                                                 if m.group(3) else unit, label=label, estimate=hedged, cites=[c.id])))
    p.comparisons.sort(key=lambda k: 0 if any(c.id in k.cites and c.section == "results" for c in claims) else 1)
    p.comparisons = p.comparisons[:LIMITS["comparisons"]]
    shown_pairs = {(_fmt(v), k.unit) for k in p.comparisons for v in (k.before, k.after)}
    for _, _, m in sorted(scored, key=lambda x: (x[0], x[1])):
        if (m.value.replace(",", ""), m.unit) not in shown_pairs and len(p.metrics) < LIMITS["metrics"] \
                and m.value not in {x.value for x in p.metrics}:
            p.metrics.append(m)
            used.update(m.cites)

    # ---- a quote: "… from the email of Henrik de Vries, operations director: he said …" or "…" — Name
    for m in _DIRECT.finditer(src):
        p.quote = Quote(text=m.group(1).strip(), who=m.group(2).strip())
        break
    if not p.quote.text:
        m = _SAID.search(unwrap(src))
        if m and len(m.group("text")) <= BUDGET["quote"]:
            text = m.group("text").strip()
            who = m.group("who") + (f", {m.group('role').strip()}" if m.group("role") else "")
            p.quote = Quote(text=text[0].upper() + text[1:], who=who)
    if p.quote.text:
        key = normalize(p.quote.text)[:50]
        p.quote.cites = [c.id for c in claims if key and key in normalize(c.text)][:1]
        used.update(p.quote.cites)

    # ---- milestones: clauses that carry a full date, in time order
    events: dict[tuple, Event] = {}
    for c in claims:
        whole = len(c.text) <= BUDGET["event.text"] and len(_DATE.findall(c.text)) == 1
        for clause in [c.text.strip(" .")] if whole else re.split(r"[,;:]\s+|\s+but\s+", c.text):
            clause = shorten(clause.strip(" ."), BUDGET["event.text"]).strip(" .")
            d = _DATE.search(clause)
            if not d or len(clause.split()) < 3 or not _MILESTONE.search(clause):
                continue
            if d.group(4):
                key = (int(d.group(5)), int(d.group(4)[1]) * 3 - 2, 0)
            else:
                key = (int(d.group(3)), _MONTHS.index(d.group(2).lower()) + 1, int(d.group(1) or 0))
            text = clause[0].upper() + clause[1:] + "."
            events.setdefault(key, Event(when=d.group(0), text=text, cites=[c.id]))
    keys = sorted(events)
    if len(keys) > 6:  # keep the first, the last and an even spread between them
        keys = [keys[round(i * (len(keys) - 1) / 5)] for i in range(6)]
    p.timeline = [events[k] for k in keys] if len(keys) >= 3 else []
    used.update(x for e in p.timeline for x in e.cites)

    def pick(pool, rx, n, budget, bonus=None):
        """Up to n sentences from the pool that match rx, in the notes' order, each fitted to its budget."""
        out = []
        ranked = sorted(pool, key=lambda c: -(len(rx.findall(c.text)) + (1 if bonus and c.section in bonus else 0)))
        for c in ranked:
            if c.id in used or not rx.search(c.text) or re.match(r"(?:he|she)\b", c.text, re.I):
                continue  # ("He also said …" has lost the person it is about)
            text = shorten(c.text, budget)
            if text and len(out) < n:
                out.append((claims.index(c), Item(text=text, cites=[c.id])))
                used.add(c.id)
        return [it for _, it in sorted(out, key=lambda x: x[0])]

    # ---- the cover line: what was built, in the notes' own sentence
    for rx in (re.compile(r"\b(?:we|team)\s+(?:built|made|did|developed|created|designed)\b", re.I),
               re.compile(r"\b(?:is written|was built|built|developed|made)\b", re.I)):
        lead = next((c for c in sec("work_done", "technical_approach", "tools") if rx.search(c.text)
                     and len(c.text) <= BUDGET["subtitle"]), None)
        if lead:
            break
    lead = lead or next((c for c in sec("client_problem", "work_done") if len(c.text) <= BUDGET["subtitle"]), None)
    if lead:
        p.subtitle, p.cites["subtitle"] = lead.text, [lead.id]
        used.add(lead.id)

    p.challenges = pick(sec("client_problem", "challenges") + [c for c in claims if c.section not in ("client_problem", "challenges")],
                        _PAIN, LIMITS["challenges"], BUDGET["item.text"], bonus=("client_problem", "challenges"))
    p.pillars = pick(sec("work_done", "technical_approach", "tools"), _BUILT, LIMITS["pillars"], BUDGET["item.text"])
    p.outcomes = pick(sec("results"), _GOOD, LIMITS["outcomes"], BUDGET["item.text"])
    if len(p.outcomes) < LIMITS["outcomes"]:
        p.outcomes += pick([c for c in claims if c.section != "results"], _GOOD_ANYWHERE,
                           LIMITS["outcomes"] - len(p.outcomes), BUDGET["item.text"])

    # ---- tools: known names only, never people
    people = people_in(src)
    by_section = sec("tools") + sec("technical_approach") + [c for c in claims if c.section not in ("tools", "technical_approach")]
    p.tech = [t for t in tools_in([c.text for c in by_section]) if t not in people][:LIMITS["tech"]]
    if p.tech:
        p.cites["tech"] = [c.id for c in claims if any(t.lower() in c.text.lower() for t in p.tech)][:6]

    return p

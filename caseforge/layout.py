"""Content-driven layout: the notes decide the story, the page order and the shape of every block.

No two reports need the same template. The composer reads the checked report plan and decides:

1. the STORY — what leads the report:
   impact          several measured results            → cover carries the strongest number, results come first
   transformation  before/after pairs                  → cover shows "from → to", a comparison chart leads results
   journey         dated milestones                    → a timeline page tells it in order
   people          a strong quote, few numbers         → cover and close are built around the quote
   build           mostly method and approach          → the process diagram is the centrepiece
2. the BLOCK VARIANT from how much content there is (1 metric = one hero number, 4 = a grid;
   a short process = horizontal flow, a long one = vertical steps; one challenge = a big statement …)
3. the PAGES — sections are weighed and sparse neighbours share a page, so the report is 3–5 pages
   with no half-empty ones.

Every decision is written to `notes` in plain words, so a reviewer can see why the report looks as it does.
The composer is deterministic: same content → same layout. Different content → a different layout.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

CAPACITY = 100        # content units that fit on one A4 page body
MAX_PAGES = 4         # inner pages after the cover (so 5 pages at most)


class Block(BaseModel):
    kind: str                      # lede, client, challenges, brief, pillars, steps, tech, metrics,
    variant: str = ""              # comparison, timeline, quote, outcomes, closing, verify
    field: str = ""                # which plan field the block shows (for ledes: the field name)
    slot: str = "main"             # main | side (sidebar frame)
    title: bool = True             # show the block's own small heading ("How it works")


class Section(BaseModel):
    key: str                       # challenge, solution, results, journey, close, glance
    label: str                     # small kicker: "The challenge"
    blocks: list[Block] = Field(default_factory=list)
    weight: int = 0


class LayoutPage(BaseModel):
    sections: list[Section] = Field(default_factory=list)
    side: bool = False             # sidebar frame: this page has facts for the side column


STORIES = ("impact", "transformation", "journey", "people", "build")
COVERS = ("motif", "hero-number", "from-to", "quote", "statement")
THEMES = ("light", "dark", "bold", "editorial")
FRAMES = ("stack", "sidebar", "magazine", "dashboard", "split")   # how a page is built, not just its colours
DEFAULT_FRAME = {"impact": "dashboard", "transformation": "split", "journey": "sidebar", "people": "magazine",
                 "build": "sidebar"}
SECTION_KEYS = ("challenge", "solution", "journey", "results", "close")
VARIANTS = {"metrics": ("hero", "pair", "row", "grid", "band", "side", "rings"), "steps": ("flow", "vertical", "prose"),
            "challenges": ("statement", "numbered", "prose"), "pillars": ("cols1", "cols2", "cols3", "prose"),
            "outcomes": ("list", "grid", "prose"), "timeline": ("horizontal", "vertical"),
            "comparison": ("bars", "from-to", "columns", "slope"), "quote": ("inline", "hero", "pull")}
HIDEABLE = ("client", "brief", "pillars", "steps", "tech", "timeline", "comparison", "quote", "outcomes", "closing",
            "challenges", "metrics", "brand")   # brand = the company name / logo in the corner and footer of every page
DEFAULT_THEME = {"impact": "bold", "transformation": "light", "journey": "editorial", "people": "editorial",
                 "build": "light"}


class Prefs(BaseModel):
    """Layout choices that override the rules — from the AI art director at design time, or from the
    reviewer in the report chat ("make the cover dark", "results first"). Impossible choices are ignored:
    a hero-number cover needs a measured result, a timeline needs dates."""
    story: str = ""
    cover: str = ""
    theme: str = ""
    frame: str = ""
    order: list[str] = Field(default_factory=list)
    hero_metric: int = -1
    variants: list[str] = Field(default_factory=list)   # "metrics=row", "steps=vertical"
    hide: list[str] = Field(default_factory=list)       # block kinds to leave out
    density: str = ""                                    # "airy" | "compact"
    reason: str = ""


class Layout(BaseModel):
    story: str = "build"
    theme: str = "light"
    frame: str = "stack"
    density: str = ""
    cover: str = "motif"           # motif | hero-number | from-to | quote | statement
    hero_metric: int = -1          # index of the metric shown on the cover (it is then not repeated)
    pages: list[LayoutPage] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def _len(s: str) -> int:
    return len(s or "")


def _lines(text: str, per_line: int = 85) -> int:
    return max(1, -(-_len(text) // per_line))


def _num(v: str) -> float:
    try:
        return float(v.replace(",", ""))
    except ValueError:
        return 0.0


def _feasible_story(st: str, plan) -> bool:
    return {"impact": bool(plan.metrics), "transformation": bool(plan.comparisons),
            "journey": len(getattr(plan, "timeline", [])) >= 2, "people": bool(plan.quote.text.strip()),
            "build": True}.get(st, False)


def compose(plan, prefs: Prefs | None = None) -> Layout:
    P = prefs or Prefs()
    L = Layout()
    m, comp, tl = plan.metrics, plan.comparisons, getattr(plan, "timeline", [])
    hard = [i for i, x in enumerate(m) if not x.estimate]
    quote = plan.quote.text.strip() if "quote" not in P.hide else ""
    if P.reason:
        L.notes.append(f"Art direction: {P.reason}")

    # ---------------------------------------------------------------- 1. the story
    if P.story in STORIES and _feasible_story(P.story, plan):
        L.story = P.story
        L.notes.append(f"Story: {P.story} (chosen for this content).")
    elif len(m) >= 3 or (len(m) >= 2 and comp):
        L.story = "impact"
        L.notes.append(f"Results lead: the notes have {len(m)} measured results"
                       + (f" and {len(comp)} before/after pair(s)" if comp else "") + ".")
    elif comp:
        L.story = "transformation"
        L.notes.append(f"Told as a before → after change: the notes compare {len(comp)} value(s) before and after.")
    elif len(tl) >= 3:
        L.story = "journey"
        L.notes.append(f"Told as a timeline: the notes give {len(tl)} dated milestones.")
    elif quote and len(m) <= 1:
        L.story = "people"
        L.notes.append("Built around the quote: there are few numbers, but a person speaks about the result.")
    else:
        L.story = "build"
        L.notes.append(f"Built around the method: {len(plan.steps)} steps and {len(plan.pillars)} parts of the work, "
                       f"{len(m)} measured result(s).")

    # ---------------------------------------------------------------- 2. the cover
    want = P.cover if P.cover in COVERS else ""
    if want == "hero-number" and not hard:
        want = ""
    if want == "from-to" and not comp:
        want = ""
    if want == "quote" and not quote:
        want = ""
    if want:
        L.cover = want
        if want == "hero-number":
            L.hero_metric = P.hero_metric if P.hero_metric in hard else _strongest(m, hard)
            L.notes.append(f"Cover shows {m[L.hero_metric].value}{m[L.hero_metric].unit.strip()}; it is not repeated inside.")
        else:
            L.notes.append(f"Cover: {want.replace('-', ' ')}.")
    elif L.story == "impact" and hard:
        best = _strongest(m, hard)
        L.cover, L.hero_metric = "hero-number", best
        L.notes.append(f"Cover shows {m[best].value}{m[best].unit.strip()} — the strongest measured result; "
                       "it is not repeated inside (each fact once).")
    elif L.story == "transformation":
        L.cover = "from-to"
        L.notes.append(f"Cover shows the change in {comp[0].label.lower()}; the chart inside shows the detail.")
    elif L.story == "people" and quote:
        L.cover = "quote"
        L.notes.append("Cover carries the quote; it is not repeated at the end.")
    elif L.story == "journey":
        L.cover = "statement"
        L.notes.append("Cover leads with the title — the story is told in time, not in one number.")
    else:
        L.notes.append("Cover uses the brand shapes — no single number is strong enough to lead.")
    L.theme = P.theme if P.theme in THEMES else DEFAULT_THEME[L.story]
    if P.frame in FRAMES:
        L.frame = P.frame
    else:
        L.frame = DEFAULT_FRAME[L.story]
        if L.frame == "dashboard" and len(m) + len(comp) < 3:
            L.frame = "sidebar"
        if L.frame == "sidebar" and not (plan.tech or plan.client_line or m):
            L.frame = "magazine"
    L.notes.append({
        "dashboard": "Pages are built as tiles, like a KPI board — the notes are mostly numbers.",
        "magazine": "Pages read like a magazine: two text columns, a pull quote, numbers in a band — the notes tell a story.",
        "sidebar": "A side column carries the key facts (client, numbers, tools); the main column tells how it was done.",
        "split": "Each section opens with a full-width colour panel — a clear before → after story.",
        "stack": "Classic stacked pages.",
    }[L.frame])
    L.density = P.density if P.density in ("airy", "compact") else ""

    # ---------------------------------------------------------------- 3. sections with block variants
    S: dict[str, Section] = {}

    # challenge
    s = Section(key="challenge", label="The challenge")
    if plan.challenge_intro:
        s.blocks.append(Block(kind="lede", field="challenge_intro"))
    if plan.client_line:
        s.blocks.append(Block(kind="client"))
    if len(plan.challenges) == 1:
        s.blocks.append(Block(kind="challenges", variant="statement"))
    elif plan.challenges:
        s.blocks.append(Block(kind="challenges", variant="numbered"))
    if plan.brief:
        s.blocks.append(Block(kind="brief"))
    S["challenge"] = s

    # solution
    s = Section(key="solution", label="The solution")
    if plan.solution_intro:
        s.blocks.append(Block(kind="lede", field="solution_intro"))
    if plan.pillars:
        s.blocks.append(Block(kind="pillars", variant=f"cols{2 if len(plan.pillars) in (2, 4) else min(3, len(plan.pillars))}"))
    if plan.steps:
        longest = max(_len(x.text) for x in plan.steps)
        vertical = len(plan.steps) >= 6 or longest > 75 or (L.story == "build" and len(plan.steps) >= 4)
        s.blocks.append(Block(kind="steps", variant="vertical" if vertical else "flow"))
    if plan.tech:
        s.blocks.append(Block(kind="tech"))
    S["solution"] = s

    # journey (timeline gets its own section only when it is the story; otherwise it joins the solution)
    if tl:
        tb = Block(kind="timeline", variant="vertical" if len(tl) > 5 else "horizontal")
        if L.story == "journey":
            S["journey"] = Section(key="journey", label="How it unfolded", blocks=[tb])
        else:
            S["solution"].blocks.insert(1 if plan.solution_intro else 0, tb)

    # results
    s = Section(key="results", label="The results")
    shown = [i for i in range(len(m)) if i != L.hero_metric]
    n = len(shown)
    if n:
        # the graph follows the numbers: percentages that are shares of a whole ("96 % of drivers") are rings
        pct = [m[i] for i in shown if m[i].unit.strip() == "%" and 0 < _num(m[i].value) <= 100]
        rings = 2 <= n <= 4 and len(pct) == n and all(_SHARE.search(x.label) for x in pct)
        s.blocks.append(Block(kind="metrics", variant="rings" if rings else {1: "hero", 2: "pair", 3: "row"}.get(n, "grid")))
    if comp:
        if L.cover == "from-to" and len(comp) == 1:
            pass  # already on the cover
        elif len(comp) == 1:
            s.blocks.append(Block(kind="comparison", variant="from-to" if not n else "slope"))
        else:   # two pairs stand side by side as columns; three or more read better as rows
            s.blocks.append(Block(kind="comparison", variant="columns" if len(comp) == 2 else "bars"))
        L.notes.append({1: "One before/after pair: shown as a single change.",
                        2: "Two before/after pairs: drawn as columns side by side."}.get(
                            len(comp), f"{len(comp)} before/after pairs: drawn as rows of bars."))
    if plan.outcomes and L.story != "people":
        s.blocks.append(Block(kind="outcomes", variant="list" if len(plan.outcomes) <= 2 else "grid"))
    S["results"] = s

    # close
    s = Section(key="close", label="What it delivered" if L.story != "people" else "In their words")
    if quote and L.cover != "quote":
        s.blocks.append(Block(kind="quote", variant="hero" if L.story == "people" else "inline"))
    if plan.outcomes and L.story == "people":
        s.blocks.append(Block(kind="outcomes", variant="grid"))
    if plan.conclusion:
        s.blocks.append(Block(kind="closing"))
    if not quote and L.story != "people":
        # without a quote the close would be a lonely panel; the outcomes are what it delivered
        moved = [b for b in S["results"].blocks if b.kind == "outcomes"]
        S["results"].blocks = [b for b in S["results"].blocks if b.kind != "outcomes"]
        s.blocks[0:0] = moved
        if moved:
            L.notes.append("Outcomes sit on the closing page — there is no quote to carry it.")
    s.blocks.append(Block(kind="verify"))
    S["close"] = s

    order = {"impact": ["results", "challenge", "solution", "close"],
             "transformation": ["challenge", "results", "solution", "close"],
             "journey": ["challenge", "journey", "solution", "results", "close"],
             "people": ["challenge", "solution", "results", "close"],
             "build": ["challenge", "solution", "results", "close"]}[L.story]
    if L.story == "impact":
        S["results"].label = "At a glance"
    # the frame reshapes blocks: prose for magazines, side slots for the sidebar, tiles for dashboards
    frame_variants = {
        "magazine": {"challenges": "prose", "pillars": "prose", "outcomes": "prose", "steps": "prose",
                     "metrics": "band", "quote": "pull"},
        "sidebar": {"metrics": "side", "steps": "vertical", "challenges": "numbered", "timeline": "vertical",
                    "pillars": "cols1" if len(plan.pillars) <= 2 else "cols2"},
        "dashboard": {"steps": "flow", "outcomes": "grid", "pillars": "cols2"},
        "split": {}, "stack": {},
    }[L.frame]
    side_kinds = {"client", "metrics", "tech", "quote"} if L.frame == "sidebar" else set()
    for sec in S.values():
        for b in sec.blocks:
            if b.kind in frame_variants and not (b.kind == "challenges" and b.variant == "statement" and L.frame != "magazine"):
                b.variant = frame_variants[b.kind]
            if b.kind in side_kinds:
                b.slot = "side"
                if b.kind == "quote":
                    b.variant = "inline"
        # a section must keep something in the main column — a heading over nothing looks broken
        if sec.blocks and all(b.slot == "side" or b.kind == "verify" for b in sec.blocks):
            for b in sec.blocks:
                if b.slot == "side":
                    b.slot = "main"
                    if b.kind == "metrics":
                        b.variant = {1: "hero", 2: "pair", 3: "row"}.get(len(shown), "grid")
    # reviewer / art-director overrides: hide blocks, force variants, reorder sections
    for sec in S.values():
        sec.blocks = [b for b in sec.blocks if b.kind not in P.hide or b.kind == "verify"]
        for b in sec.blocks:
            for v in P.variants:
                k, _, val = v.partition("=")
                if k == b.kind and val in VARIANTS.get(k, ()):
                    b.variant = val
    # a ring can only show a percentage: asked for anything else, the numbers go back to plain figures
    ring_ok = bool(shown) and all(m[i].unit.strip() == "%" and 0 < _num(m[i].value) <= 100 for i in shown)
    for sec in S.values():
        for b in sec.blocks:
            if b.kind == "metrics" and b.variant == "rings" and not ring_ok:
                b.variant = {1: "hero", 2: "pair", 3: "row"}.get(len(shown), "grid")
            if b.kind == "comparison" and b.variant == "from-to" and len(comp) > 1:
                b.variant = "bars"   # one big pair cannot show three
    if P.order:
        wanted = [k for k in P.order if k in order]
        order = wanted + [k for k in order if k not in wanted and k != "close"] + (["close"] if "close" not in wanted else [])
    sections = [S[k] for k in order if k in S and any(b.kind != "verify" for b in S[k].blocks) or k == "close"]
    for sec in sections:
        sec.weight = _weigh(sec, plan, L)
    # a long solution is told in two parts, so its second half can share a page with a lighter neighbour
    for i, sec in enumerate(sections):
        tail = [b for b in sec.blocks if b.kind in ("steps", "tech") and b.slot == "main"]
        head = [b for b in sec.blocks if b not in tail]
        if sec.key == "solution" and sec.weight > 66 and any(b.kind == "steps" for b in tail) and \
                any(b.kind != "lede" for b in head):
            for b in tail:
                b.title = b.kind != "steps"
            how = Section(key="how", label="How it works", blocks=tail)
            sec.blocks = head
            sec.weight, how.weight = _weigh(sec, plan, L), _weigh(how, plan, L)
            sections.insert(i + 1, how)
            break

    # ---------------------------------------------------------------- 4. pack sections into pages
    # every way of cutting the section list into pages is scored: nothing may overflow, and the
    # pages should carry about the same load — so no page ends up half empty beside a crowded one
    cap = {"airy": 85, "compact": 118}.get(L.density, CAPACITY)
    groups = _paginate(sections, cap)
    # a closing page with almost nothing on it: the outcomes move there ("What it delivered" is where
    # they belong), which also takes weight off the results page
    last = groups[-1] if groups else []
    res = next((x for x in sections if x.key == "results"), None)
    if len(last) == 1 and last[0].key == "close" and last[0].weight < 45 and res is not None:
        moved = [b for b in res.blocks if b.kind == "outcomes" and b.slot == "main"]
        if moved and any(b.kind != "outcomes" for b in res.blocks):
            res.blocks = [b for b in res.blocks if b not in moved]
            last[0].blocks = moved + last[0].blocks
            res.weight, last[0].weight = _weigh(res, plan, L), _weigh(last[0], plan, L)
            groups = _paginate(sections, cap)
    pages = [LayoutPage(sections=g) for g in groups]
    for pg in pages:
        pg.side = any(b.slot == "side" for x in pg.sections for b in x.blocks)
    L.pages = pages
    merged = [" + ".join(x.label.lower() for x in p.sections) for p in pages if len(p.sections) > 1]
    L.notes.append(f"{len(pages) + 1} pages: " + ", ".join(
        " + ".join(x.label for x in p.sections) for p in pages) + ".")
    if merged:
        L.notes.append("Short sections share a page (" + "; ".join(merged) + ") so no page is half empty.")
    return L


import re  # noqa: E402

_SHARE = re.compile(r"\bof\b|\brate\b|\bshare\b|\bcoverage\b|\bcompletion\b|\badoption\b|\blogged in\b", re.I)


def _strongest(m, hard: list[int]) -> int:
    """The number for the cover: the planner lists results strongest first, and a percentage reads
    best at poster size — so the first measured percentage, else the first measured result."""
    return next((i for i in hard if "%" in m[i].unit), hard[0])


GAP = 6               # space between two sections that share a page


def _load(group: list[Section]) -> int:
    return sum(x.weight for x in group) + GAP * (len(group) - 1)


def _paginate(sections: list[Section], cap: int) -> list[list[Section]]:
    n = len(sections)
    if n <= 1:
        return [sections] if sections else []
    best, best_score = None, None
    for mask in range(1 << (n - 1)):                      # bit i set = page break after section i
        if bin(mask).count("1") + 1 > MAX_PAGES:
            continue
        groups, cur = [], [sections[0]]
        for i in range(1, n):
            if mask >> (i - 1) & 1:
                groups.append(cur)
                cur = []
            cur.append(sections[i])
        groups.append(cur)
        loads = [_load(g) for g in groups]
        over = sum(max(0, x - cap) for x in loads)        # the fit pass can absorb a little, not a lot
        thin = sum(max(0, 58 - x) for x in loads)         # a page under ~60 % full looks unfinished
        score = (over * 6 + thin * 2 + (max(loads) - min(loads)) * 0.5 + len(groups) * 4)
        if len(groups) == 1:
            score += 400      # a report is a cover and at least two pages; one page is a one-pager
        if best_score is None or score < best_score:
            best, best_score = groups, score
    return best


BODY_H = 960          # px of an A4 page between the header and the footer
WIDTH = {"stack": 684, "split": 684, "magazine": 684, "dashboard": 684, "sidebar": 428}   # px of the text column


def _rows(text: str, width: float, size: float) -> int:
    """How many lines a text takes in a box `width` px wide at `size` px type (average glyph ≈ 0.5 em)."""
    per_line = max(8, width / (size * 0.5))
    return max(1, -(-_len(text) // int(per_line)))


def _weigh(sec: Section, plan, L: Layout) -> int:
    """Estimated height of a section, in hundredths of a page, at normal type size. The numbers mirror
    the CSS in render/report_pdf.py; the fit pass in the template absorbs what the estimate misses."""
    W, fr = WIDTH.get(L.frame, 684), L.frame
    tile = 32 if fr == "dashboard" else 0            # a dashboard tile's own padding
    head = getattr(plan.headlines, sec.key, "") if sec.key in SECTION_KEYS else ""
    hsize = {"magazine": 44, "dashboard": 28}.get(fr, 31 if head else 40)
    if L.theme == "editorial" and not head:
        hsize = 42
    px = (17 if head else 0) + _rows(head or sec.label, min(W, hsize * 8.5 if head else W), hsize) * hsize * 1.1
    if fr == "split":
        px += 56
    if L.theme == "editorial":
        px += 14
    blocks = [b for b in sec.blocks if b.slot != "side"]
    for b in blocks:
        k, v = b.kind, b.variant
        h = 0.0
        if k == "lede":
            size = 18 if fr == "magazine" else 16.5
            h = _rows(getattr(plan, b.field), min(W, size * 46), size) * size * 1.5
        elif k == "client":
            h = 46 + 20 * _rows(plan.client_line, W - 100, 15) + tile
        elif v == "prose":
            items = {"challenges": plan.challenges, "pillars": plan.pillars, "outcomes": plan.outcomes,
                     "steps": plan.steps}[k]
            lines = sum(_rows(f"{x.title} {x.text}", W / 2 - 30, 12.5) for x in items)
            h = (lines * 20 + len(items) * 10) / 2 + 12 + (22 if k == "steps" and b.title else 0)
        elif k == "challenges":
            if v == "statement":
                h = 12 + 31 * _rows(plan.challenges[0].text, W - 27, 25) + (16 if plan.challenges[0].title else 0) + tile
            elif fr == "dashboard":
                n = len(plan.challenges)
                h = 30 + max((22 if x.title else 0) + 20 * _rows(x.text, W / n - 30, 13.5) for x in plan.challenges) + tile
            else:
                h = sum(32 + max(34, (22 if x.title else 0) + 20 * _rows(x.text, W - 76, 13.5)) for x in plan.challenges)
        elif k == "brief":
            h = 74 + 30 * _rows(plan.brief, min(W - 56, 500), 25)
        elif k == "pillars":
            cols = int(v[-1]) if v[-1:].isdigit() else 2
            cw = (W - 12 * (cols - 1)) / cols - 36 - (40 if cols == 1 else 0)
            per = [32 + (0 if cols == 1 else 36) + (21 if x.title else 0) + 19.2 * _rows(x.text, cw, 13) for x in plan.pillars]
            rows = [max(per[i:i + cols]) for i in range(0, len(per), cols)]
            h = sum(rows) + 12 * (len(rows) - 1) + tile
        elif k == "steps":
            n = max(1, len(plan.steps))
            if v == "vertical":
                h = sum(16 + max(36, (18 if x.title else 7) + 18 * _rows(x.text, W - 52, 12.5)) for x in plan.steps)
            else:
                h = 52 + max((18 if x.title else 0) + 16 * _rows(x.text, W / n - 10, 11.5) for x in plan.steps)
            h += (25 if b.title else 0) + tile
        elif k == "tech":
            chars = sum(len(t) * 6.2 + 28 for t in plan.tech)
            h = 22 + 34 * max(1, -(-int(chars) // int(W - tile))) + tile
        elif k == "timeline":
            tl = plan.timeline
            if v == "vertical":
                h = sum(16 + 19 * _rows(e.text, W - 160, 13) for e in tl)
            else:
                h = 50 + 16.5 * max(_rows(e.text, W / max(1, len(tl)) - 12, 11.5) for e in tl)
            h += tile
        elif k == "metrics":
            shown = [x for i, x in enumerate(plan.metrics) if i != L.hero_metric]
            n = max(1, len(shown))
            pad = 34 if (L.theme == "bold" or fr == "dashboard") else 12
            if v == "band":
                h = 78 + 16 * max(_rows(x.label, W / n - 28, 11.5) for x in shown or plan.metrics)
            elif v == "rings":
                h = 36 + 128 + 19 * max(_rows(x.label, W / n - 30, 13) for x in shown or plan.metrics)
            elif v == "hero":
                h = pad + 126 + 25 * _rows(shown[0].label if shown else "", 440, 17)
            else:
                cols = n if (fr == "dashboard" or v == "row") else 2
                big = 40 if fr == "dashboard" else {"pair": 64, "row": 42}.get(v, 58)
                per = [pad + big + 8 + 19 * _rows(x.label, min(W / cols - 36, 290), 13)
                       + (18 if x.estimate and (v == "row" or fr == "dashboard") else 0) for x in shown or plan.metrics]
                rows = [max(per[i:i + cols]) for i in range(0, len(per), cols)]
                h = sum(rows) + 14 * (len(rows) - 1)
        elif k == "comparison":
            nk = len(plan.comparisons)
            h = {"from-to": 170, "columns": 36 + 26 + 190 + 40 + 20, "slope": 36 + 26 + 84 * nk + 8}.get(
                v, 36 + 26 + 74 * nk + 20)
        elif k == "outcomes":
            cols = 1 if v == "list" else (len(plan.outcomes) if fr == "dashboard" else 2)
            cols = max(1, min(cols, len(plan.outcomes)))
            per = [max(24, (19 if x.title else 0) + 19 * _rows(x.text, W / cols - 44, 13)) for x in plan.outcomes]
            rows = [max(per[i:i + cols]) for i in range(0, len(per), cols)]
            h = sum(rows) + 16 * (len(rows) - 1) + tile
        elif k == "quote":
            q = plan.quote
            if v == "pull":
                h = 100 + 31 * _rows(q.text, W * 0.84, 24) + (28 if q.who else 0)
            else:
                size = 29 if v == "hero" else 23
                h = 34 + size * 1.3 * _rows(q.text, W - tile, size) + (28 if q.who else 0) + tile
        elif k == "closing":
            h = 52 + 29.5 * _rows(plan.conclusion, W - 56, 24) + 47
        elif k == "verify":
            h = 30 + 15 * _rows("x" * 300, W - 78, 10)
        px += h + 18
    return max(6, round(px / BODY_H * 100))

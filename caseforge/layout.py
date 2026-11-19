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
3. the PAGES — the standard case-study structure (summary, introduction, challenge, objectives, approach,
   solution, implementation, technology, results, client voice, lessons, project facts). Sections are
   weighed; sparse neighbours share a page and long ones continue on the next, so small notes give 4–5
   pages and big notes as many as they need, with no half-empty ones.

Every decision is written to `notes` in plain words, so a reviewer can see why the report looks as it does.
The composer is deterministic: same content → same layout. Different content → a different layout.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

CAPACITY = 100        # content units that fit on one A4 page body
MAX_PAGES = 4         # inner pages for a small report; big notes get more (see compose)
PAGE_CEILING = 16     # never more inner pages than this


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
SECTION_KEYS = ("summary", "intro", "challenge", "objectives", "approach", "solution", "implementation",
                "technology", "results", "close", "lessons", "journey")
ORDER = ["summary", "intro", "challenge", "objectives", "approach", "solution", "implementation", "technology",
         "results", "close", "lessons"]
VARIANTS = {"metrics": ("hero", "pair", "row", "grid", "band", "side", "rings"), "steps": ("flow", "vertical", "prose"),
            "challenges": ("statement", "numbered", "prose"), "pillars": ("cols1", "cols2", "cols3", "prose"),
            "outcomes": ("list", "grid", "prose"), "timeline": ("horizontal", "vertical", "gantt"),
            "objectives": ("list", "grid", "prose"), "lessons": ("list", "grid", "prose"),
            "comparison": ("bars", "from-to", "columns", "slope"), "quote": ("inline", "hero", "pull")}
HIDEABLE = ("client", "brief", "pillars", "steps", "tech", "timeline", "comparison", "quote", "outcomes", "closing",
            "challenges", "metrics", "brand", "objectives", "lessons", "team", "budget", "architecture", "facts")   # brand = the company name / logo in the corner and footer of every page
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
    shown = [i for i in range(len(m)) if i != L.hero_metric]
    n = len(shown)
    txt = lambda f: getattr(plan, f, "") or ""  # noqa: E731

    # executive summary: the short version, with the key numbers
    s = Section(key="summary", label="At a glance")
    if txt("summary"):
        s.blocks.append(Block(kind="lede", field="summary"))
    if n:
        # the graph follows the numbers: percentages that are shares of a whole ("96 % of drivers") are rings
        pct = [m[i] for i in shown if m[i].unit.strip() == "%" and 0 < _num(m[i].value) <= 100]
        rings = 2 <= n <= 4 and len(pct) == n and all(_SHARE.search(x.label) for x in pct)
        s.blocks.append(Block(kind="metrics", variant="rings" if rings else {1: "hero", 2: "pair", 3: "row"}.get(n, "grid")))
    S["summary"] = s

    # introduction: the client and the context
    s = Section(key="intro", label="About the client")
    if txt("intro"):
        s.blocks.append(Block(kind="lede", field="intro"))
        if plan.client_line:
            s.blocks.append(Block(kind="client"))
    S["intro"] = s

    # challenge
    s = Section(key="challenge", label="The challenge")
    if plan.challenge_intro:
        s.blocks.append(Block(kind="lede", field="challenge_intro"))
    if plan.client_line and not txt("intro"):
        s.blocks.append(Block(kind="client"))
    if len(plan.challenges) == 1:
        s.blocks.append(Block(kind="challenges", variant="statement"))
    elif plan.challenges:
        s.blocks.append(Block(kind="challenges", variant="numbered"))
    if plan.brief:
        s.blocks.append(Block(kind="brief"))
    S["challenge"] = s

    # objectives
    obj = getattr(plan, "objectives", [])
    S["objectives"] = Section(key="objectives", label="What we set out to do",
                              blocks=[Block(kind="objectives", variant="list" if len(obj) <= 2 else "grid")] if obj else [])

    # approach: how we worked
    s = Section(key="approach", label="Our approach")
    if txt("approach_intro"):
        s.blocks.append(Block(kind="lede", field="approach_intro"))
    if plan.steps:
        longest = max(_len(x.text) for x in plan.steps)
        vertical = len(plan.steps) >= 6 or longest > 75 or (L.story == "build" and len(plan.steps) >= 4)
        s.blocks.append(Block(kind="steps", variant="vertical" if vertical else "flow", title=False))
    S["approach"] = s

    # solution: what we delivered
    s = Section(key="solution", label="The solution")
    if plan.solution_intro:
        s.blocks.append(Block(kind="lede", field="solution_intro"))
    if plan.pillars:
        s.blocks.append(Block(kind="pillars", variant=f"cols{2 if len(plan.pillars) in (2, 4) or len(plan.pillars) > 6 else min(3, len(plan.pillars))}"))
    S["solution"] = s

    # implementation: how the project ran — timeline as a Gantt when the dates allow, team, budget
    s = Section(key="implementation", label="How it unfolded" if L.story == "journey" else "How it was delivered")
    if txt("implementation_intro"):
        s.blocks.append(Block(kind="lede", field="implementation_intro"))
    if tl:
        dated = [month_index(e.when) for e in tl]
        gantt = sum(x is not None for x in dated) >= 3 and len({round(x) for x in dated if x is not None}) >= 2
        s.blocks.append(Block(kind="timeline", variant="gantt" if gantt else "vertical" if len(tl) > 5 else "horizontal"))
        if gantt:
            L.notes.append(f"The {len(tl)} dated milestones are drawn on a time axis (Gantt), "
                           "with any delay against the plan shown.")
    if len(getattr(plan, "team", [])) >= 2:
        s.blocks.append(Block(kind="team"))
        L.notes.append("Team size over time is drawn as a chart.")
    if getattr(plan, "budget", []):
        s.blocks.append(Block(kind="budget"))
        L.notes.append("Budget figures are drawn as bars on one scale.")
    S["implementation"] = s

    # technology: an architecture diagram when there is a stack to draw, else the list of tools
    s = Section(key="technology", label="The technology")
    if getattr(plan, "architecture", []):
        s.blocks.append(Block(kind="architecture"))
        L.notes.append(f"The tools are drawn as a {len(plan.architecture)}-layer architecture diagram.")
    elif plan.tech:
        s.blocks.append(Block(kind="tech"))
    S["technology"] = s

    # results
    s = Section(key="results", label="The results")
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

    # close: the client's voice
    s = Section(key="close", label="In their words")
    if quote and L.cover != "quote":
        s.blocks.append(Block(kind="quote", variant="hero" if L.story == "people" else "inline"))
    if plan.outcomes and L.story == "people":
        s.blocks.append(Block(kind="outcomes", variant="grid"))
    if plan.conclusion:
        s.blocks.append(Block(kind="closing"))
    S["close"] = s

    # lessons and what comes next
    les = getattr(plan, "lessons", [])
    S["lessons"] = Section(key="lessons", label="Lessons and next steps",
                           blocks=[Block(kind="lessons", variant="list" if len(les) <= 2 else "grid")] if les else [])

    order = list(ORDER)
    # the frame reshapes blocks: prose for magazines, side slots for the sidebar, tiles for dashboards
    frame_variants = {
        "magazine": {"challenges": "prose", "pillars": "prose", "outcomes": "prose", "steps": "prose",
                     "objectives": "prose", "lessons": "prose", "metrics": "band", "quote": "pull"},
        "sidebar": {"metrics": "side", "steps": "vertical", "challenges": "numbered", "timeline": "vertical",
                    "pillars": "cols1" if len(plan.pillars) <= 2 else "cols2"},
        "dashboard": {"steps": "flow", "outcomes": "grid", "pillars": "cols2"},
        "split": {}, "stack": {},
    }[L.frame]
    side_kinds = {"client", "metrics", "tech", "quote"} if L.frame == "sidebar" else set()
    for sec in S.values():
        for b in sec.blocks:
            if b.kind in frame_variants and not (b.kind == "challenges" and b.variant == "statement" and L.frame != "magazine")                     and not (b.kind == "timeline" and b.variant == "gantt"):
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
    if P.order:   # the reviewer reorders the middle; the summary and introduction always open the report
        wanted = [k for k in P.order if k in order and k not in ("summary", "intro")]
        order = ["summary", "intro"] + wanted + [k for k in order if k not in wanted and k not in ("summary", "intro")]
    sections = [S[k] for k in order if k in S and S[k].blocks]
    # every approved sentence that no designed element tells: the Project facts table, page by page
    facts = getattr(plan, "facts", [])
    if facts and "facts" not in P.hide:
        sections += _fact_sections(facts, WIDTH.get(L.frame, 684) if L.frame != "sidebar" else 684)
        L.notes.append(f"{len(facts)} approved sentence(s) not shown on the designed pages are listed under "
                       "Project facts, so nothing from the notes is left out.")
    if not sections:
        sections = [Section(key="close", label="In their words")]
    sections[-1].blocks.append(Block(kind="verify"))
    cap = {"airy": 85, "compact": 118}.get(L.density, CAPACITY)
    for sec in sections:
        sec.weight = _weigh(sec, plan, L)
    # a section too long for one page continues on the next ("The solution (continued)")
    sections = [part for sec in sections for part in _split(sec, plan, L, cap)]

    # ---------------------------------------------------------------- 4. pack sections into pages
    # every way of cutting the section list into pages is scored: nothing may overflow, and the
    # pages should carry about the same load — so no page ends up half empty beside a crowded one
    total = sum(x.weight for x in sections) + GAP * (len(sections) - 1)
    max_pages = max(MAX_PAGES, min(PAGE_CEILING, -(-total // int(cap * 0.78)) + 1))
    groups = _paginate(sections, cap, max_pages)
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
            groups = _paginate(sections, cap, max_pages)
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


def _page_cost(load: int, cap: int) -> float:
    return max(0, load - cap) * 6 + max(0, 58 - load) * 2 + 4


def _paginate(sections: list[Section], cap: int, max_pages: int = MAX_PAGES) -> list[list[Section]]:
    n = len(sections)
    if n <= 1:
        return [sections] if sections else []
    if n > 13:   # long reports: the best split by dynamic programming (every cut is a page break)
        best = [0.0] + [float("inf")] * n
        cut = [0] * (n + 1)
        for j in range(1, n + 1):
            for i in range(max(0, j - 6), j):
                c = best[i] + _page_cost(_load(sections[i:j]), cap)
                if c < best[j]:
                    best[j], cut[j] = c, i
        groups, j = [], n
        while j > 0:
            groups.insert(0, sections[cut[j]:j])
            j = cut[j]
        return groups
    best, best_score = None, None
    for mask in range(1 << (n - 1)):                      # bit i set = page break after section i
        if bin(mask).count("1") + 1 > max_pages:
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
            items = getattr(plan, k)
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
            if v == "gantt":
                h = 46 + 31 * len(tl) + 30
            elif v == "vertical":
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
        elif k in ("outcomes", "objectives", "lessons"):
            its = getattr(plan, k)
            cols = 1 if v == "list" else (min(3, len(its)) if fr == "dashboard" else 2)
            cols = max(1, min(cols, len(its)))
            per = [max(24, (19 if x.title else 0) + 19 * _rows(x.text, W / cols - 44, 13)) for x in its]
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
        elif k == "team":
            h = 36 + 196 + 34 + tile
        elif k == "budget":
            h = 36 + 50 * len(plan.budget) + 10 + tile
        elif k == "architecture":
            nl = len(plan.architecture)
            h = 26 + 66 * nl + 12 * (nl - 1) + tile
        elif k == "facts":
            a_, b_ = (int(x) for x in b.field.split(":"))
            h = 8 + sum(12 + 15 * _rows(it.text, 684 - 196, 10.5) for it in plan.facts[a_:b_])
        elif k == "verify":
            h = 30 + 15 * _rows("x" * 300, W - 78, 10)
        px += h + 18
    return max(6, round(px / BODY_H * 100))


def _fact_sections(facts, width: int) -> list[Section]:
    """The Project facts table, cut into page-sized parts."""
    out, start, px = [], 0, 0.0
    room = BODY_H * 0.86
    for i, it in enumerate(facts):
        h = 12 + 15 * _rows(it.text, width - 196, 10.5)
        if px + h > room and i > start:
            out.append((start, i))
            start, px = i, 0.0
        px += h
    out.append((start, len(facts)))
    return [Section(key="facts" if j == 0 else "facts+", label="Project facts" if j == 0 else "Project facts (continued)",
                    blocks=[Block(kind="facts", field=f"{a}:{b}")]) for j, (a, b) in enumerate(out)]


def _split(sec: Section, plan, L: Layout, cap: int) -> list[Section]:
    """A section that would overflow its page continues on the next one, block by block."""
    main = [b for b in sec.blocks if b.slot != "side"]
    if sec.weight <= cap * 1.05 or len(main) < 2 or sec.key.startswith("facts"):
        return [sec]
    parts, cur = [], []
    for b in sec.blocks:
        trial = Section(key=sec.key, label=sec.label, blocks=cur + [b])
        if cur and _weigh(trial, plan, L) > cap and b.slot != "side":
            parts.append(cur)
            cur = [b]
        else:
            cur.append(b)
    parts.append(cur)
    out = []
    for j, blocks in enumerate(parts):
        x = Section(key=sec.key if j == 0 else sec.key + "+", label=sec.label if j == 0 else sec.label + " (continued)",
                    blocks=blocks)
        x.weight = _weigh(x, plan, L)
        out.append(x)
    return out


_MONTHS = {m: i for i, m in enumerate(("january", "february", "march", "april", "may", "june", "july", "august",
                                       "september", "october", "november", "december"))}
_WHEN = re.compile(r"\b(?:(\d{1,2})\s+)?(january|february|march|april|may|june|july|august|september|october|november|"
                   r"december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\.?\s+((?:19|20)\d\d)\b|\b(q[1-4])\s+((?:19|20)\d\d)\b"
                   r"|^\s*((?:19|20)\d\d)\s*$", re.I)


def month_index(when: str) -> float | None:
    """'9 February 2024' → months since year 0 (fractional), for a time axis. None when it isn't a date."""
    mt = _WHEN.search(when or "")
    if not mt:
        return None
    if mt.group(2):
        name = mt.group(2).lower()
        mon = next(i for k, i in _MONTHS.items() if k.startswith(name[:3]))
        return int(mt.group(3)) * 12 + mon + (int(mt.group(1)) - 1) / 31 if mt.group(1) else int(mt.group(3)) * 12 + mon
    if mt.group(4):
        return int(mt.group(5)) * 12 + (int(mt.group(4)[1]) - 1) * 3
    return int(mt.group(6)) * 12

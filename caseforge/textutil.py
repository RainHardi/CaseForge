"""Deterministic text helpers. No model involved — these are the rules that never get tired."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

_WS = re.compile(r"\s+")
_FILE_MARKER = re.compile(r"^\s*-{2,}\s*from .+?-{2,}\s*$", re.I)
_PUNCT = re.compile(r"[^\w%+#.\-/ ]+")


def normalize(text: str) -> str:
    text = text.lower().replace("’", "'").replace("–", "-").replace("—", "-")
    text = _PUNCT.sub(" ", text)
    return _WS.sub(" ", text).strip()


_BULLET = re.compile(r"^\s*(?:[-*•>]+\s|\d+[.)]\s|\[[^\]]*\]|[A-Z][A-Za-z .]{0,24}:\s)")
_ENDS = re.compile(r"[.!?:;][\"')\]]*\s*$")


def unwrap(text: str) -> str:
    """Rejoin hard-wrapped paragraphs (text copied from a PDF or an email breaks every ~90 characters,
    in the middle of sentences). A line is joined to the next one when it runs to about the full line
    width and does not end a sentence, and the next line is not a bullet, a speaker or a file marker.
    Short lines — lists, chat messages, headings — are left alone."""
    lines = text.splitlines()
    lens = sorted(len(x.rstrip()) for x in lines if x.strip())
    if len(lens) < 4:
        return text
    width = lens[int(len(lens) * 0.9)]
    if not 50 <= width <= 160:   # short lines, or one paragraph per line: nothing is wrapped
        return text
    out: list[str] = []
    last = ""                    # the previous physical line
    for i, line in enumerate(lines):
        if not line.strip() and last.strip() and i + 1 < len(lines) and lines[i + 1][:1].islower() \
                and len(last.rstrip()) >= 0.72 * width and not _ENDS.search(last.rstrip()):
            continue             # a page break in the middle of a sentence
        prev = last.rstrip()
        cont = prev.endswith(("/", ",", " -", " –", " &"))
        if (out and prev.strip() and line.strip() and not _FILE_MARKER.match(prev) and not _FILE_MARKER.match(line)
                and not _BLOCK_HEAD.match(prev) and not _BULLET.match(line) and not _ENDS.search(prev)
                and (len(prev) >= 0.72 * width or (cont and len(prev) >= 0.5 * width))):
            out[-1] = out[-1].rstrip() + " " + line.strip()
        else:
            out.append(line)
        last = line
    return "\n".join(out)


_BLOCK_HEAD = re.compile(r"^\s*\[[^\]]+\]\s*$")


def split_sentences(text: str) -> list[str]:
    """Split notes into sentence-like units: lines, bullets and sentences."""
    out: list[str] = []
    for line in unwrap(text).splitlines():
        if _FILE_MARKER.match(line):
            continue  # "--- from report.docx ---" marks where uploaded text came from
        line = re.sub(r"^\s*(?:[-*•>]+|\d+[.)])\s*", "", line).strip()
        if not line:
            continue
        for part in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", line):
            part = part.strip()
            if len(part) > 2:
                out.append(part)
    return out


def tidy_sentence(text: str) -> str:
    text = _WS.sub(" ", text).strip(" -–—•*")
    if not text:
        return text
    text = text[0].upper() + text[1:]
    if text[-1] not in ".!?":
        text += "."
    return text


# ---------------------------------------------------------------- grounding
def quote_in_source(quote: str, source: str, threshold: float = 0.85) -> bool:
    """Is this quote really in the input? Exact match after normalising, else fuzzy."""
    q, s = normalize(quote), normalize(source)
    if not q:
        return False
    if q in s:
        return True
    m = SequenceMatcher(None, s, q, autojunk=False).find_longest_match(0, len(s), 0, len(q))
    if m.size / len(q) >= threshold:
        return True
    # fuzzy: compare against windows of the source of similar length
    words, qn = s.split(), len(q.split())
    for i in range(0, max(1, len(words) - qn + 1)):
        window = " ".join(words[i : i + qn + 2])
        if SequenceMatcher(None, window, q, autojunk=False).ratio() >= threshold:
            return True
    return False


# ---------------------------------------------------------------- numbers
_NUM_RE = re.compile(r"(?<![\w])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(\s*(?:%|percent|x\b|times\b))?", re.I)
_NUMBER_WORDS = {
    "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
    "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "fifteen": "15",
    "twenty": "20", "thirty": "30", "forty": "40", "fifty": "50", "sixty": "60",
    "seventy": "70", "eighty": "80", "ninety": "90", "hundred": "100", "thousand": "1000",
    "million": "1000000", "billion": "1000000000", "twice": "2", "double": "2",
    "doubled": "2", "triple": "3", "tripled": "3", "half": "0.5", "halved": "0.5",
    "quarter": "0.25", "dozen": "12", "dozens": "12",
}
# "one" is left out on purpose: "one of the", "one page" would flag everything.


def numbers_in(text: str) -> set[str]:
    found: set[str] = set()
    for m in _NUM_RE.finditer(text):
        whole = m.group(1).replace(",", "")
        found.add(whole + (f".{m.group(2)}" if m.group(2) else ""))
    for word in re.findall(r"[a-z]+", text.lower()):
        if word in _NUMBER_WORDS:
            found.add(_NUMBER_WORDS[word])
    return found


# ---------------------------------------------------------------- named terms
_COMMON_CAPS = {
    "we", "our", "the", "a", "an", "this", "that", "these", "it", "its", "they", "their",
    "in", "on", "for", "to", "with", "by", "as", "at", "and", "but", "or", "after", "before",
    "when", "while", "using", "during", "because", "from", "each", "every", "all", "both",
    "i", "summary", "results", "challenge", "client", "team", "project", "case", "study",
    # everyday abbreviations: ordinary vocabulary, not the name of a product, company or person.
    # ("UI" for the notes' "interface" or "layout" is a rewording. Real technology — API, GPS, SMS — is
    # NOT here: writing one of those adds a claim, so it must be in the notes.)
    "ui", "ux", "id", "ok", "faq", "vs",
}
_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]*[A-Za-z0-9+#]|[A-Z]")


def named_terms(text: str) -> set[str]:
    """Product, tool, company and people names: anything capitalised mid-sentence,
    CamelCase, ALLCAPS, or letter+digit like GPT-4."""
    terms: set[str] = set()
    for sentence in re.split(r"(?<=[.!?:;])\s+|\n", text):
        tokens = list(_TOKEN.finditer(sentence))
        for idx, m in enumerate(tokens):
            tok = m.group(0).strip(".-")
            if len(tok) < 2 or tok.lower() in _COMMON_CAPS:
                continue
            camel = bool(re.search(r"[a-z][A-Z]", tok))
            allcaps = tok.isupper() and len(tok) >= 2
            alnum = bool(re.search(r"[A-Za-z]", tok) and re.search(r"\d", tok))
            capital_mid = tok[0].isupper() and idx > 0
            if camel or allcaps or alnum or capital_mid:
                terms.add(tok)
    return terms


def term_in_source(term: str, source_norm: str) -> bool:
    t = normalize(term)
    if not t:
        return True
    # a name may sit after a digit or slash inside a product code ("S/4HANA", "Python3.11"),
    # but not inside a longer word ("Java" must not match "javascript")
    if re.search(rf"(?<![a-z]){re.escape(t)}(?![a-z0-9])", source_norm):
        return True
    # tolerate simple plural/possessive differences ("APIs" vs "API")
    return t.endswith("s") and re.search(rf"(?<![a-z]){re.escape(t[:-1])}(?![a-z0-9])", source_norm) is not None


# ---------------------------------------------------------------- exaggeration
INFLATED_WORDS = {
    "significantly", "significant", "dramatically", "dramatic", "drastically", "massively",
    "massive", "revolutionary", "revolutionized", "revolutionised", "transformative",
    "transformed", "world-class", "best-in-class", "industry-leading", "cutting-edge",
    "state-of-the-art", "seamless", "seamlessly", "unprecedented", "exponential",
    "exponentially", "huge", "hugely", "tremendous", "tremendously", "greatly", "vastly",
    "substantially", "outstanding", "remarkable", "remarkably", "game-changing",
    "groundbreaking", "flawless", "flawlessly", "perfect", "perfectly", "always", "never",
    "guaranteed", "fully", "completely", "entirely",
    # quality judgements the writer adds on its own ("a robust app", "strict testing")
    "robust", "strict", "rigorous", "comprehensive", "innovative", "powerful", "high-quality", "sophisticated",
}


# judgements about delivery that must come from the notes, never from the writer ("on time", "within budget")
VERDICT_PHRASES = re.compile(
    r"\b(on time|on schedule|ahead of schedule|on budget|under budget|within (?:the |an |a |our )?(?:agreed |planned |original )?"
    r"(?:time ?frame|timeline|schedule|budget|time and budget|timeframe and budget|scope)|as planned|"
    r"successfully delivered|delivered successfully|without (?:any )?(?:delays?|issues|problems))\b", re.I)


def verdict_phrases(text: str, source: str) -> list[str]:
    """Phrases like "within the agreed timeframe and budget" that the notes don't use."""
    src = " ".join(source.lower().split())
    return [m.group(0) for m in VERDICT_PHRASES.finditer(text) if m.group(0).lower() not in src]


def inflated_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z\-]*", text.lower()) if w in INFLATED_WORDS}


# ---------------------------------------------------------------- overlap
_STOP = _COMMON_CAPS | {"is", "was", "were", "be", "been", "are", "of", "so", "has", "had", "have", "which", "who"}


def content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9%+#]+", text.lower()) if w not in _STOP and len(w) > 1}


def best_overlap(claim: str, sentences: list[str]) -> tuple[float, str]:
    cw = content_words(claim)
    if not cw:
        return 1.0, ""
    best, best_s = 0.0, ""
    for s in sentences:
        score = len(cw & content_words(s)) / len(cw)
        if score > best:
            best, best_s = score, s
    return best, best_s


# ---------------------------------------------------------------- estimates
_HEDGES = re.compile(
    r"\b(estimat\w*|est\.|approx\w*|about|around|roughly|nearly|near|almost|up to|projected|"
    r"expected|forecast\w*|target\w*|predicted|likely|probably|i think|not verified|unverified|"
    r"not been verified|preliminary|indicative)\b|~", re.I)


def is_hedged(text: str) -> bool:
    return bool(_HEDGES.search(text))


_NEAR = re.compile(r"(?:\b(?:approx\w*|about|around|roughly|nearly|near|almost|up to|close to|some)|~)\W*$", re.I)
_WIDE = re.compile(r"\b(estimat\w*|est\.|projected|expected|forecast\w*|target\w*|predicted|likely|probably|"
                   r"i think|not verified|unverified|not been verified|preliminary|indicative)\b", re.I)
_CLAUSE_CUT = re.compile(r"[,;:]\s+|\s+and\s+|\s+but\s+")


_MONTHS = re.compile(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?$", re.I)


def _spots(text: str, n: str) -> list[re.Match]:
    return [m for m in _NUM_RE.finditer(text)
            if m.group(1).replace(",", "") + (f".{m.group(2)}" if m.group(2) else "") == n]


def _unit(text: str, m: re.Match) -> str:
    """What a number counts, so "about 18 minutes" and "18 November" are not the same 18:
    '%' for percentages, 'date' for a day of a month, else the first letters of the next word."""
    if m.group(3):
        return "x" if m.group(3).strip().lower() in ("x", "times") else "%"
    before = re.findall(r"[A-Za-z]+\.?", text[max(0, m.start() - 12):m.start()])
    after = re.match(r"\s*([A-Za-z]+)", text[m.end():])
    if (after and _MONTHS.match(after.group(1))) or (before and _MONTHS.match(before[-1])):
        return "date"
    return after.group(1).lower()[:4] if after else ""


def number_is_hedged(sentence: str, n: str, units: set[str] | None = None) -> bool:
    """Is THIS number an estimate in this sentence? Long notes pack several facts into one sentence
    ("1,340 routes planned, 96.2 percent logged in, planning time down from about 18 minutes to 3"),
    so the hedge has to sit with the number: right before it ("about 18"), or in the same clause
    ("the estimate … was 1.1 million", "I think the final count was 9").
    `units` limits the check to the spots that count the same thing ("18 minutes", not "18 November")."""
    spots = _spots(sentence, n)
    if units:
        spots = [m for m in spots if _unit(sentence, m) in units] or spots
    if not spots:
        return is_hedged(sentence)
    for m in spots:
        cuts = [0] + [c.end() for c in _CLAUSE_CUT.finditer(sentence)] + [len(sentence)]
        start = max(c for c in cuts if c <= m.start())
        end = min(c for c in cuts if c > m.start())
        clause = sentence[start:end]
        if not (_NEAR.search(sentence[max(0, m.start() - 22):m.start()]) or _WIDE.search(clause)):
            return False
    return True


def estimate_flags(claim_text: str, source: str) -> list[str]:
    """A number that is only ever stated as an estimate in the notes must stay labelled as one.
    The hedge has to sit with that number in the claim too: "from about 18 minutes to 3" keeps 18
    labelled, "Cutting planning from 18 minutes to 3" drops it."""
    sentences = split_sentences(unwrap(source))
    plain = claim_text.replace(",", "")
    flags = []
    for n in sorted(x for x in numbers_in(claim_text) if x in plain):  # skip "million" -> 1000000
        if number_is_hedged(claim_text, n):
            continue
        units = {_unit(claim_text, m) for m in _spots(claim_text, n)} - {""}
        if units == {"date"}:
            continue   # "3 March 2025" is a date, never an estimate — even when its sentence has one
        if hedged_in_source(n, sentences, units):
            flags.append(f"'{n}' is an estimate in your notes — keep it labelled as an estimate")
    return flags


def hedged_in_source(n: str, sentences: list[str], units: set[str] | None = None) -> bool:
    """True when every place the notes give this number (counting the same thing) hedges it.
    "about 18 minutes" stays an estimate even though the notes also say "18 November"."""
    holders = [s for s in sentences if n in numbers_in(s)]
    if units:
        same = [s for s in holders if any(_unit(s, m) in units for m in _spots(s, n))]
        holders = same or holders
    if units != {"date"}:   # a date never decides whether a quantity is an estimate
        holders = [s for s in holders if not (_spots(s, n) and all(_unit(s, m) == "date" for m in _spots(s, n)))]
    return bool(holders) and all(number_is_hedged(s, n, units) for s in holders)


# ---------------------------------------------------------------- where a quote came from
_BLOCK = re.compile(r"^\s*(?:\[(?P<sec>[^\]]+)\]|-{2,}\s*from\s+(?P<file>.+?)\s*-{2,})\s*$", re.I)


def locate_quote(quote: str, source: str) -> str:
    """'report.pdf, line 12' / 'Raw notes, line 4' — or '' if the quote can't be pinned down."""
    q = normalize(quote)[:60]
    if not q:
        return ""
    block, line_no = "notes", 0
    lines = source.splitlines()
    for i, line in enumerate(lines):
        m = _BLOCK.match(line)
        if m:
            block = m.group("file") or m.group("sec") or "notes"
            line_no = 0
            continue
        line_no += 1
        if q[:40] and q[:40] in normalize(line):
            return f"{block}, line {line_no}"
        # a quote that starts near the end of a hard-wrapped line continues on the next one
        nxt = lines[i + 1] if i + 1 < len(lines) and not _BLOCK.match(lines[i + 1]) else ""
        if nxt and q[:40] in normalize(line + " " + nxt) and q[:12] in normalize(line):
            return f"{block}, line {line_no}"
    return ""

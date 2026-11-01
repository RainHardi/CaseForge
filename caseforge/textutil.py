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


def split_sentences(text: str) -> list[str]:
    """Split notes into sentence-like units: lines, bullets and sentences."""
    out: list[str] = []
    for line in text.splitlines():
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
}


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

"""Planted-claim test for the faithfulness checker (Test Plan §3 Step 2, test T-05, task BT-4).

Plants 20 unsupported claims (5 each: invented number, invented tool, invented client detail,
exaggerated outcome) across the sample drafts, runs the checker, and reports:
  catch rate      = planted claims labelled unsupported/contradicted   (target >= 18/20)
  false-flag rate = genuine draft claims wrongly labelled unsupported/contradicted

Usage:
  python eval/planted_claims.py                 # uses Gemini if GEMINI_API_KEY is set
  CASEFORGE_LLM_MODE=offline python eval/planted_claims.py
  python eval/planted_claims.py --repeats 3 samples/my_input.json ...
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from caseforge.checker import check_claims  # noqa: E402
from caseforge.cli import load_input  # noqa: E402
from caseforge.llm import get_llm  # noqa: E402
from caseforge.models import BLOCKING_LABELS, Claim  # noqa: E402
from caseforge.pipeline import generate  # noqa: E402
from caseforge.store import Store  # noqa: E402

PLANTED = {
    "invented number": [
        ("results", "Processing time fell by 40% after launch."),
        ("results", "Active users grew to 1,200 within a month."),
        ("results", "Error rates dropped by 35 percent."),
        ("work_done", "The project was delivered 3 weeks ahead of schedule."),
        ("results", "Support requests were cut in half."),
    ],
    "invented tool": [
        ("tools", "We deployed the system on Kubernetes."),
        ("technical_approach", "All data was stored in MongoDB."),
        ("technical_approach", "We trained the model with TensorFlow."),
        ("tools", "The front end was built in Angular."),
        ("technical_approach", "Monitoring ran on Datadog."),
    ],
    "invented client detail": [
        ("client_problem", "The client is a Fortune 500 company operating in twelve countries."),
        ("client_problem", "The client's CTO personally led the rollout."),
        ("client_problem", "The client employs more than 300 people."),
        ("work_done", "The project was funded by a government innovation grant."),
        ("results", "The client signed a multi-year support contract after delivery."),
    ],
    "exaggerated outcome": [
        ("results", "The tool dramatically transformed daily operations."),
        ("results", "The rollout was seamless."),
        ("results", "The team delivered a world-class system."),
        ("results", "Staff productivity improved significantly."),
        ("results", "The new process completely eliminated manual work."),
    ],
}

DEFAULT_INPUTS = [
    ROOT / "samples" / "01_clean_form" / "input.json",
    ROOT / "samples" / "02_rough_notes" / "notes.txt",
    ROOT / "samples" / "03_pasted_chat" / "chat.txt",
]


def run(inputs: list[Path], repeats: int) -> str:
    llm = get_llm()
    engine = llm.name if llm else "offline rules"
    store = Store(Path(tempfile.mkdtemp()) / "projects")
    planted = [(kind, sec, text) for kind, items in PLANTED.items() for sec, text in items]

    rows, caught_total, planted_total, ff_total, genuine_total = [], 0, 0, 0, 0
    per_kind: dict[str, list[int]] = {k: [0, 0] for k in PLANTED}
    misses: list[str] = []
    for rep in range(1, repeats + 1):
        for i, path in enumerate(inputs):
            rec = store.create(load_input(path))
            generate(rec, llm)
            genuine_ids = {c.id for c in rec.active_claims()}
            mine = planted[i::len(inputs)]  # spread the 20 claims across the inputs
            pid: dict[str, str] = {}
            for kind, sec, text in mine:
                cite = next((c.fact_ids for c in rec.active_claims(sec) if c.fact_ids), None) or \
                    (rec.facts[0:1] and [rec.facts[0].id]) or []
                c = Claim(id=rec.next_id("C", [x.id for x in rec.claims]), section=sec, text=text, fact_ids=list(cite))
                rec.claims.append(c)
                pid[c.id] = kind
            check_claims(rec, llm)  # re-check everything, as the reviewer would see it
            caught = 0
            for c in rec.active_claims():
                flagged = c.label in BLOCKING_LABELS
                if c.id in pid:
                    per_kind[pid[c.id]][1] += 1
                    if flagged:
                        caught += 1
                        per_kind[pid[c.id]][0] += 1
                    else:
                        misses.append(f"run {rep} · {path.parent.name} · {pid[c.id]}: “{c.text}” → {c.label.value if c.label else '?'}")
                elif c.id in genuine_ids and flagged:
                    ff_total += 1
            caught_total += caught
            planted_total += len(pid)
            genuine_total += len(genuine_ids)
            rows.append(f"| {rep} | {path.parent.name}/{path.name} | {len(genuine_ids)} | {len(pid)} | {caught} |")

    rate = caught_total / planted_total if planted_total else 0
    ff = ff_total / genuine_total if genuine_total else 0
    lines = [
        f"# Planted-claim test — {datetime.now():%Y-%m-%d %H:%M}",
        "",
        f"- Engine: **{engine}**",
        f"- Inputs: {len(inputs)} · repeats: {repeats}",
        f"- **Catch rate: {caught_total}/{planted_total} ({rate:.0%})** — provisional target 90% (Q-T01)",
        f"- **False-flag rate: {ff_total}/{genuine_total} ({ff:.0%})** of genuine draft claims",
        "",
        "| Run | Input | Genuine claims | Planted | Caught |",
        "|---|---|---|---|---|",
        *rows,
        "",
        "| Planted type | Caught |",
        "|---|---|",
        *[f"| {k} | {v[0]}/{v[1]} |" for k, v in per_kind.items()],
        "",
        "## Missed planted claims",
        *(["- " + m for m in misses] or ["- none"]),
        "",
        "> Inputs are team-constructed and fictional. The human review step stays mandatory whatever this score is.",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="*", type=Path)
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--out", type=Path, default=ROOT / "eval" / "results")
    a = ap.parse_args()
    report = run(a.inputs or DEFAULT_INPUTS, a.repeats)
    a.out.mkdir(parents=True, exist_ok=True)
    path = a.out / f"planted_{datetime.now():%Y%m%d_%H%M}.md"
    path.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nsaved: {path}")


if __name__ == "__main__":
    main()

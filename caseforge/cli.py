"""Command-line interface.  Run `python -m caseforge --help`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import review
from .config import get_settings
from .llm import get_llm
from .models import SECTION_TITLES, ImageRef, ProjectInput, ProjectRecord
from .pipeline import generate
from .render import ExportBlocked
from .render.html import render_portfolio_page
from .render.pdf import export_name, render_case_study, render_one_pager
from .store import Store

COLOR = sys.stdout.isatty()


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if COLOR else text


LABEL_COLOR = {"supported": "32", "reworded": "36", "unsupported": "31;1", "contradicted": "35;1"}


def load_input(path: Path) -> ProjectInput:
    """A .json file in ProjectInput shape, or any .txt/.md file treated as raw notes."""
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("_note", None)
        return ProjectInput.model_validate(data)
    return ProjectInput(title="", raw_notes=path.read_text(encoding="utf-8"))


def cmd_new(args, store: Store) -> None:
    path = Path(args.file)
    inp = load_input(path)
    if args.title:
        inp.title = args.title
    images = list(inp.images)
    inp.images = []
    rec = store.create(inp)
    for img in images:  # image paths in a JSON input are relative to that file
        src = (path.parent / img.filename).resolve()
        if src.exists():
            name = store.add_image(rec.id, src=src)
            rec.input.images.append(ImageRef(filename=name, caption=img.caption, section=img.section))
    for spec in args.image or []:
        file, _, rest = spec.partition(":")
        section, _, caption = rest.partition(":")
        name = store.add_image(rec.id, src=Path(file))
        rec.input.images.append(ImageRef(filename=name, caption=caption, section=section or "work_done"))
    store.save(rec)
    print(rec.id)


def cmd_list(args, store: Store) -> None:
    for r in store.list():
        print(f"{r.id:45} {r.status:9} {len(r.active_claims()):3} claims  {r.input.title}")


def cmd_generate(args, store: Store) -> None:
    rec = store.load(args.id)
    llm = get_llm()
    print(f"Generating with {llm.name if llm else 'offline rules (no GEMINI_API_KEY)'} ...")
    generate(rec, llm)
    store.save(rec)
    show(rec)


def show(rec: ProjectRecord) -> None:
    print(_c(f"\n{rec.input.title or '(untitled)'}  —  {rec.status}  [{rec.engine}]", "1"))
    print(f"client: {rec.input.client_name or '(not given)'}   facts: {len(rec.facts)}"
          f"   dropped facts: {len(rec.dropped_facts)}")
    current = None
    for c in rec.claims:
        if c.section != current:
            current = c.section
            print(_c(f"\n## {SECTION_TITLES[c.section]}", "1"))
        label = c.label.value if c.label else "unchecked"
        tag = _c(f"[{label}]", LABEL_COLOR.get(label, "33"))
        extra = " (deleted)" if c.deleted else " (edited)" if c.edited else " (manual)" if c.manual else ""
        print(f"{c.id:>4} {tag} {c.text}{extra}")
        if c.label and c.label.value in ("unsupported", "contradicted") and not c.deleted:
            print(f"       ↳ {c.reason}")
    if rec.gaps:
        print(_c("\n## Missing information", "1"))
        for g in rec.gaps:
            state = "resolved: " + g.resolution if g.resolved else ("BLOCKING" if g.blocking else "warning")
            print(f"{g.id:>4} [{state}] {g.message}")
    if rec.brand_warnings:
        print(_c("\n## Brand warnings", "1"))
        for w in rec.brand_warnings:
            print("     " + w)
    problems = review.blockers(rec)
    if review.can_export(rec):
        print(_c(f"\nApproved by {rec.approved_by} at {rec.approved_at} — ready to export.", "1"))
        return
    print(_c("\nReady to approve." if not problems else f"\n{len(problems)} thing(s) block approval:", "1"))
    for p in problems:
        print("   - " + p)


def cmd_show(args, store: Store) -> None:
    show(store.load(args.id))


def _mutate(args, store: Store, fn) -> None:
    rec = store.load(args.id)
    try:
        fn(rec)
    except (review.ReviewError, KeyError) as e:
        sys.exit(f"error: {e}")
    store.save(rec)
    show(rec)


def cmd_edit(args, store):
    _mutate(args, store, lambda r: review.edit_claim(r, args.claim, args.text, get_llm(), args.by))


def cmd_delete(args, store):
    _mutate(args, store, lambda r: review.delete_claim(r, args.claim, args.by))


def cmd_add(args, store):
    _mutate(args, store, lambda r: review.add_claim(r, args.section, args.text, get_llm(), args.by))


def cmd_add_source(args, store):
    _mutate(args, store, lambda r: review.add_to_source(r, args.text, get_llm(), args.field, args.by))


def cmd_resolve(args, store):
    _mutate(args, store, lambda r: review.resolve_gap(r, args.gap, args.note, args.by))


def cmd_approve(args, store):
    _mutate(args, store, lambda r: review.approve(r, args.by))


def cmd_reject(args, store):
    _mutate(args, store, lambda r: review.reject(r, args.by, args.reason))


def cmd_export(args, store: Store) -> None:
    rec = store.load(args.id)
    out = Path(args.out)
    img_dir = store.image_dir(rec.id)
    try:
        a = render_case_study(rec, img_dir, out / export_name(rec, "case-study", args.draft), draft=args.draft)
        b = render_one_pager(rec, img_dir, out / export_name(rec, "one-pager", args.draft), draft=args.draft)
        c = render_portfolio_page(rec, img_dir, out / export_name(rec, "portfolio", args.draft).replace(".pdf", ".html"),
                                  draft=args.draft)
    except ExportBlocked as e:
        sys.exit(str(e) + "\n" + "\n".join("  - " + p for p in review.blockers(rec)))
    rec.log("exported", f"{a.name}, {b.name}, {c.name}")
    store.save(rec)
    for p in (a, b, c):
        print(p)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="caseforge", description="Faithful case studies from messy project notes.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("new", help="create a project from a .json input or a .txt of rough notes")
    s.add_argument("file")
    s.add_argument("--title", default="")
    s.add_argument("--image", action="append", help="path:section:caption (repeatable)")
    s.set_defaults(fn=cmd_new)

    sub.add_parser("list", help="list projects").set_defaults(fn=cmd_list)

    for name, fn, hlp in [("generate", cmd_generate, "extract facts, write, check"),
                          ("show", cmd_show, "show claims, labels, gaps and blockers")]:
        s = sub.add_parser(name, help=hlp)
        s.add_argument("id")
        s.set_defaults(fn=fn)

    s = sub.add_parser("edit", help="rewrite one claim (it is re-checked)")
    s.add_argument("id"); s.add_argument("claim"); s.add_argument("text"); s.add_argument("--by", default="")
    s.set_defaults(fn=cmd_edit)

    s = sub.add_parser("delete", help="remove a claim")
    s.add_argument("id"); s.add_argument("claim"); s.add_argument("--by", default="")
    s.set_defaults(fn=cmd_delete)

    s = sub.add_parser("add", help="add your own sentence to a section (it is checked)")
    s.add_argument("id"); s.add_argument("section", choices=list(SECTION_TITLES)); s.add_argument("text")
    s.add_argument("--by", default="")
    s.set_defaults(fn=cmd_add)

    s = sub.add_parser("add-source", help="add a confirmed fact to the source notes, then re-check")
    s.add_argument("id"); s.add_argument("text")
    s.add_argument("--field", default="work_done",
                   choices=["client_problem", "work_done", "technical_approach", "tools", "challenges", "results"])
    s.add_argument("--by", default="")
    s.set_defaults(fn=cmd_add_source)

    s = sub.add_parser("resolve-gap", help="acknowledge a missing-information flag")
    s.add_argument("id"); s.add_argument("gap"); s.add_argument("note"); s.add_argument("--by", default="")
    s.set_defaults(fn=cmd_resolve)

    s = sub.add_parser("approve", help="approve (only works with zero blockers)")
    s.add_argument("id"); s.add_argument("--by", required=True)
    s.set_defaults(fn=cmd_approve)

    s = sub.add_parser("reject", help="reject a draft")
    s.add_argument("id"); s.add_argument("--by", required=True); s.add_argument("--reason", default="")
    s.set_defaults(fn=cmd_reject)

    s = sub.add_parser("export", help="write PDF case study, one-pager and portfolio page")
    s.add_argument("id"); s.add_argument("--out", default="exports")
    s.add_argument("--draft", action="store_true", help="watermarked preview, allowed before approval")
    s.set_defaults(fn=cmd_export)

    args = p.parse_args(argv)
    store = Store(get_settings().data_dir)
    args.fn(args, store)


if __name__ == "__main__":
    main()

"""CaseForge web interface.   Run:  streamlit run app.py

The screen always answers two questions for the user: "what just happened?" and "what do I do next?"
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import streamlit as st

from caseforge import review
from caseforge.config import ROOT, get_settings
from caseforge.ingest import ALL_TYPES, IngestError, extract_text, is_image
from caseforge.llm import LLMError, get_llm
from caseforge.models import FIELD_KEYS, INPUT_FIELDS, SECTION_TITLES, ImageRef, ProjectInput, ProjectRecord
from caseforge.pipeline import generate
from caseforge.render import ExportBlocked
from caseforge.render.html import render_portfolio_page
from caseforge.render.pdf import export_name, render_case_study, render_one_pager
from caseforge.store import Store

st.set_page_config(page_title="CaseForge", page_icon="📄", layout="wide")

# Plain-language labels for the checker's verdicts
VERDICT = {
    "supported": ("#1E7B4F", "✓ In your notes"),
    "reworded": ("#22648F", "✓ Reworded from your notes"),
    "unsupported": ("#B3261E", "✗ NOT in your notes"),
    "contradicted": ("#7B1FA2", "✗ CONTRADICTS your notes"),
    None: ("#8A6D00", "… not checked yet"),
}
STATUS = {"input": "📝 Draft not made yet", "drafted": "🔎 Waiting for your review",
          "approved": "✅ Approved — ready to download", "rejected": "⛔ Rejected"}
HELP = {
    "client_problem": "What the client needed, or what was going wrong before.",
    "work_done": "What your team built or delivered.",
    "technical_approach": "How you built it — architecture, method, process.",
    "tools": "Languages, frameworks, services, hardware.",
    "challenges": "What was hard and how you got through it.",
    "results": "What changed. Numbers only if you really measured them.",
}
GAP_PLACEHOLDER = {
    "client_problem": "e.g. Stock was tracked in Excel and nobody trusted the numbers",
    "work_done": "e.g. We built a stock dashboard with barcode scanning",
    "technical_approach": "e.g. Scans are queued offline and synced later",
    "tools": "e.g. Python, React, PostgreSQL",
    "challenges": "e.g. Product codes were different in every file",
    "results": "e.g. Friday stock count went from 3 hours to 1 hour",
}
SAMPLES = {
    "🍜 Messy notes": ROOT / "samples" / "02_rough_notes" / "notes.txt",
    "💬 Pasted chat": ROOT / "samples" / "03_pasted_chat" / "chat.txt",
    "🦷 Clean form": ROOT / "samples" / "01_clean_form" / "input.json",
}

st.markdown("""<style>
.cf-step{display:flex;gap:6px;flex-wrap:wrap;margin:4px 0 14px}
.cf-step span{padding:4px 12px;border-radius:999px;font-size:.85rem;border:1px solid rgba(128,128,128,.35)}
.cf-step .done{background:rgba(30,123,79,.18);border-color:rgba(30,123,79,.5)}
.cf-step .now{background:#E8A317;color:#111;font-weight:700;border-color:#E8A317}
.cf-badge{color:#fff;border-radius:4px;padding:2px 8px;font-size:.75rem;font-weight:600;white-space:nowrap}
.cf-src{opacity:.65;font-size:.82rem;margin:-4px 0 0 2px}
</style>""", unsafe_allow_html=True)


@st.cache_resource
def _store() -> Store:
    return Store(get_settings().data_dir)


store = _store()
settings = get_settings()
try:
    llm, llm_error = get_llm(), None
except LLMError as e:
    llm, llm_error = None, str(e)


def save(rec: ProjectRecord) -> None:
    store.save(rec)


def reviewer() -> str:
    return st.session_state.get("reviewer", "").strip() or "reviewer"


def run(fn, *args) -> bool:
    try:
        fn(*args)
        return True
    except (review.ReviewError, LLMError, KeyError) as e:
        st.error(str(e))
        return False


def stepper(current: int) -> None:
    names = ["1 · Your notes", "2 · AI draft", "3 · You review", "4 · Download"]
    html = "".join(
        f"<span class='{'done' if i < current else 'now' if i == current else ''}'>"
        f"{'✓ ' if i < current else ''}{n}</span>" for i, n in enumerate(names)
    )
    st.markdown(f"<div class='cf-step'>{html}</div>", unsafe_allow_html=True)


# ============================================================== sidebar
with st.sidebar:
    st.title("📄 CaseForge")
    st.caption("Turns messy project notes into a case study PDF — without inventing anything.")
    with st.expander("How it works", expanded=False):
        st.markdown(
            "1. **Upload files or paste notes** — PDF, Word, Excel, PowerPoint, text. Messy is fine.\n"
            "2. **AI writes a draft** using only what your notes say.\n"
            "3. **Every sentence is checked** against your notes. Anything not in them is marked "
            "red and must be fixed.\n"
            "4. **You approve**, then download the PDF.\n\n"
            "Nothing can be downloaded until a person approves it."
        )
    if llm:
        st.success(f"AI connected · `{settings.gemini_model}`")
    else:
        st.warning("AI not connected — running in **offline mode** (sentences copied from your notes). "
                   "Add `GEMINI_API_KEY` to `.env`." + (f"\n\n{llm_error}" if llm_error else ""))
    st.divider()
    if st.button("➕ New case study", width="stretch", type="primary"):
        st.session_state["project_id"] = None
        st.rerun()
    records = store.list()
    if records:
        st.caption("Your case studies")
        for r in records:
            icon = {"input": "📝", "drafted": "🔎", "approved": "✅", "rejected": "⛔"}[r.status]
            here = st.session_state.get("project_id") == r.id
            label = f"{'▶ ' if here else ''}{icon} {(r.input.title or 'Untitled')[:34]}"
            if st.button(label, key=f"open-{r.id}", width="stretch"):
                st.session_state["project_id"] = r.id
                st.rerun()


# ============================================================== 1. new project
def load_sample(path: Path) -> None:
    for k in ["f_title", "f_client", "f_raw", *[f"f_{k}" for k in FIELD_KEYS]]:
        st.session_state[k] = ""
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        st.session_state["f_title"] = data.get("title", "")
        st.session_state["f_client"] = data.get("client_name", "")
        for k in FIELD_KEYS:
            st.session_state[f"f_{k}"] = data.get(k, "")
        st.session_state["show_form"] = True
    else:
        st.session_state["f_raw"] = path.read_text(encoding="utf-8")


def page_new() -> None:
    stepper(0)
    st.header("Add your project notes")
    st.write("Upload files or paste text — or both. Messy is fine. CaseForge only uses what's here, "
             "and tells you what's missing.")

    cols = st.columns(len(SAMPLES) + 1)
    cols[0].caption("No notes handy? Try an example →")
    for col, (label, path) in zip(cols[1:], SAMPLES.items()):
        if path.exists() and col.button(label, width="stretch"):
            load_sample(path)
            st.rerun()

    # --- file upload: text is pulled out and put into the notes box, so the user sees exactly what is used
    done: dict[str, str] = st.session_state.setdefault("ingested", {})
    pending: dict[str, bytes] = st.session_state.setdefault("pending_images", {})
    uploads = st.file_uploader(
        "📎 Upload files — PDF, Word (.docx), Excel (.xlsx), PowerPoint (.pptx), text (.txt, .md, .csv) or images",
        type=ALL_TYPES, accept_multiple_files=True, key=f"up-{st.session_state.get('up_n', 0)}",
    )
    for f in uploads or []:
        k = f"{f.name}:{f.size}"
        if k in done:
            continue
        if is_image(f.name):
            pending[f.name] = f.getvalue()
            done[k] = "🖼 added as an image"
            continue
        try:
            text = extract_text(f.name, f.getvalue())
            current = st.session_state.get("f_raw", "").rstrip()
            st.session_state["f_raw"] = (current + f"\n\n--- from {f.name} ---\n" + text).strip()
            done[k] = f"✅ {len(text.split())} words added to the notes below"
        except IngestError as e:
            done[k] = f"⚠️ {e}"
    for k, v in done.items():
        st.caption(f"**{k.rsplit(':', 1)[0]}** — {v}")

    c1, c2 = st.columns(2)
    title = c1.text_input("Project name (optional)", key="f_title", placeholder="e.g. Inventory dashboard")
    client = c2.text_input("Client name (optional — only if you have permission)", key="f_client",
                           placeholder="Leave blank to write 'the client'")
    raw = st.text_area("Your notes (text from uploaded files appears here — delete anything confidential)",
                       key="f_raw", height=280,
                       placeholder="- client tracked stock in 3 excel files\n- we built a dashboard, python + react\n"
                                   "- manager said the friday count is way faster now")
    values: dict[str, str] = {}
    with st.expander("Prefer a form? Fill in the sections instead (optional)",
                     expanded=st.session_state.get("show_form", False)):
        fc = st.columns(2)
        for i, (key, label) in enumerate(INPUT_FIELDS):
            values[key] = fc[i % 2].text_area(label, key=f"f_{key}", help=HELP[key], height=100)

    if not st.button("✨ Write my case study", type="primary"):
        return
    inp = ProjectInput(title=title, client_name=client, raw_notes=raw, **values)
    if not inp.source_text().strip():
        st.error("Upload a file or paste some notes first.")
        return
    rec = store.create(inp)
    for fname, data in pending.items():
        name = store.add_image(rec.id, name=fname, data=data)
        rec.input.images.append(ImageRef(filename=name, section="results"))
    with st.status("Working on it…", expanded=True) as status:
        st.write("① Reading your notes and pulling out the facts…")
        st.write("② Writing the case study from those facts only…")
        st.write("③ Checking every sentence against your notes…")
        try:
            generate(rec, llm)
            status.update(label="Draft ready", state="complete")
        except LLMError as e:
            status.update(label="The AI request failed", state="error")
            st.error(f"{e}\n\nTry again in a minute, or switch GEMINI_MODEL in .env.")
    save(rec)
    for k in ["f_title", "f_client", "f_raw", "ingested", "pending_images", *[f"f_{k}" for k in FIELD_KEYS]]:
        st.session_state.pop(k, None)
    st.session_state["up_n"] = st.session_state.get("up_n", 0) + 1  # empties the upload box
    st.session_state["project_id"] = rec.id
    st.session_state["just_generated"] = True
    st.rerun()


# ============================================================== 3. review
def next_step_box(rec: ProjectRecord) -> None:
    bad = [c for c in rec.active_claims() if c.blocking]
    gaps = [g for g in rec.gaps if g.blocking and not g.resolved]
    if review.can_export(rec):
        st.success("✅ **Approved.** Open the **Download** tab to get your PDF.")
    elif bad:
        st.error(f"**Next step:** {len(bad)} sentence{'s are' if len(bad) > 1 else ' is'} **not in your notes** "
                 f"(red below). Fix or delete {'them' if len(bad) > 1 else 'it'} — the AI may have made it up.")
    elif gaps:
        st.warning(f"**Next step:** answer {len(gaps)} question{'s' if len(gaps) > 1 else ''} about missing "
                   "information (just below).")
    else:
        st.info("**Next step:** read the draft. If you're happy, scroll to the bottom, type your name and "
                "click **Approve**.")


def summary_box(rec: ProjectRecord) -> None:
    active = rec.active_claims()
    ok = sum(1 for c in active if not c.blocking)
    bad = len(active) - ok
    msg = (f"CaseForge read your notes, pulled out **{len(rec.facts)} facts**, wrote **{len(active)} sentences** "
           f"from them, and checked each one against your notes: **{ok} are backed by your notes**")
    msg += f" and **{bad} are not**." if bad else " — nothing was invented. 🎉"
    st.markdown(msg)


def gap_box(rec: ProjectRecord) -> None:
    must = [g for g in rec.gaps if g.blocking and not g.resolved]
    optional = [g for g in rec.gaps if not g.blocking and not g.resolved]
    for g in must:
        with st.container(border=True):
            st.markdown(f"**❓ {g.message}**")
            if g.field in FIELD_KEYS:
                text = st.text_input("Add it here, in your own words", key=f"gap-{g.id}",
                                     placeholder=GAP_PLACEHOLDER.get(g.field, ""))
                a, b, _ = st.columns([1, 1, 3])
                if a.button("Add to case study", key=f"gapadd-{g.id}", type="primary") and text.strip():
                    if run(review.add_to_source, rec, text, llm, g.field, reviewer()):
                        review.add_claim(rec, g.field, text, llm, reviewer())
                        review.refresh_gaps(rec)
                        save(rec); st.rerun()
                if b.button("Leave it out", key=f"gapskip-{g.id}"):
                    review.resolve_gap(rec, g.id, "Left out — not in the notes", reviewer())
                    save(rec); st.rerun()
    if optional:
        with st.expander(f"💡 {len(optional)} optional suggestion{'s' if len(optional) > 1 else ''} to make it stronger"):
            for g in optional:
                st.markdown(f"- {g.message}")
            st.caption("These don't block approval. Add info with **Add your own sentence** below, "
                       "or images in the **Details** tab.")


def claim_row(rec: ProjectRecord, c) -> None:
    color, label = VERDICT[c.label.value if c.label else None]
    left, right = st.columns([14, 2])
    left.markdown(f"<span class='cf-badge' style='background:{color}'>{label}</span>&nbsp; {c.text}",
                  unsafe_allow_html=True)
    if c.blocking:
        left.markdown(f"<div style='color:#E5534B;font-size:.85rem'>Why: {c.reason}</div>", unsafe_allow_html=True)
    elif c.evidence:
        left.markdown(f"<div class='cf-src'>📎 from your notes: “{c.evidence[:200]}”</div>", unsafe_allow_html=True)
    with right.popover("Fix" if c.blocking else "Edit", width="stretch"):
        new = st.text_area("Change the sentence", value=c.text, key=f"txt-{c.id}")
        if st.button("Save and re-check", key=f"ed-{c.id}", type="primary"):
            if run(review.edit_claim, rec, c.id, new, llm, reviewer()):
                review.refresh_gaps(rec); save(rec); st.rerun()
        if st.button("🗑 Delete this sentence", key=f"del-{c.id}"):
            review.delete_claim(rec, c.id, reviewer())
            review.refresh_gaps(rec); save(rec); st.rerun()
        if c.blocking:
            st.divider()
            st.caption("It's true, just not in your notes? Confirm it as a fact. "
                       "This is logged with your name.")
            if st.button("✔ It's true — add it to my notes", key=f"src-{c.id}"):
                field = c.section if c.section in FIELD_KEYS else "work_done"
                if run(review.add_to_source, rec, c.text, llm, field, reviewer()):
                    save(rec); st.rerun()


def page_review(rec: ProjectRecord) -> None:
    if st.session_state.pop("just_generated", False):
        summary_box(rec)
    next_step_box(rec)
    gap_box(rec)

    st.subheader("Your draft")
    st.caption("Each sentence shows whether it's backed by your notes. Click **Edit** or **Fix** to change one.")
    for key, title in SECTION_TITLES.items():
        claims = rec.active_claims(key)
        if not claims:
            continue
        st.markdown(f"**{title}**")
        for c in claims:
            claim_row(rec, c)
        st.write("")

    with st.expander("➕ Add your own sentence"):
        sec = st.selectbox("Section", [k for k in SECTION_TITLES], format_func=SECTION_TITLES.get, key="add-sec")
        text = st.text_area("Sentence", key="add-text")
        if st.button("Add and check it") and text.strip():
            if run(review.add_claim, rec, sec, text, llm, reviewer()):
                review.refresh_gaps(rec); save(rec); st.rerun()

    deleted = [c for c in rec.claims if c.deleted]
    if deleted:
        with st.expander(f"🗑 Deleted sentences ({len(deleted)})"):
            for c in deleted:
                a, b = st.columns([8, 1])
                a.markdown(f"<s>{c.text}</s>", unsafe_allow_html=True)
                if b.button("Undo", key=f"res-{c.id}"):
                    review.restore_claim(rec, c.id, llm, reviewer()); review.refresh_gaps(rec); save(rec); st.rerun()

    if rec.brand_warnings:
        with st.expander(f"✍️ Style tips ({len(rec.brand_warnings)})"):
            for w in rec.brand_warnings:
                st.write("• " + w)

    st.divider()
    st.subheader("Approve")
    problems = review.blockers(rec)
    if review.can_export(rec):
        st.success(f"Approved by **{rec.approved_by}**. Go to the **Download** tab.")
        return
    if problems:
        st.markdown("🔒 **Locked.** Fix these first:")
        for p in problems:
            st.markdown(f"- {p}")
    else:
        st.markdown("Everything is backed by your notes. Approving means **you** confirm it's correct "
                    "and can be sent to clients.")
    a, b, c = st.columns([3, 1.3, 1])
    a.text_input("Your name", key="reviewer", placeholder="e.g. Abdulaziz")
    named = bool(st.session_state.get("reviewer", "").strip())
    b.write(""); b.write("")
    if b.button("✅ Approve", type="primary", disabled=bool(problems) or not named, width="stretch"):
        if run(review.approve, rec, st.session_state["reviewer"].strip()):
            save(rec); st.rerun()
    c.write(""); c.write("")
    with c.popover("Reject", width="stretch"):
        reason = st.text_input("Why?")
        if st.button("Reject draft"):
            review.reject(rec, reviewer(), reason); save(rec); st.rerun()
    if not problems and not named:
        st.caption("Type your name to enable Approve.")


# ============================================================== 4. download
def build_outputs(rec: ProjectRecord, draft: bool) -> list[tuple[str, str, str, bytes, str]]:
    img_dir = store.image_dir(rec.id)
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        for label, desc, fn, kind, mime in [
            ("📄 Case study (PDF)", "The full write-up, several pages if needed.", render_case_study, "case-study", "application/pdf"),
            ("📃 One-page summary (PDF)", "Everything on one page, for quick sharing.", render_one_pager, "one-pager", "application/pdf"),
            ("🌐 Portfolio web page (HTML)", "Ready to put on a website.", render_portfolio_page, "portfolio", "text/html"),
        ]:
            name = export_name(rec, kind, draft)
            if mime == "text/html":
                name = name.replace(".pdf", ".html")
            path = fn(rec, img_dir, t / name, draft=draft)
            out.append((label, desc, name, path.read_bytes(), mime))
    return out


def page_download(rec: ProjectRecord) -> None:
    if review.can_export(rec):
        st.success(f"✅ Approved by **{rec.approved_by}**. Your documents are ready.")
        try:
            files = build_outputs(rec, draft=False)
        except ExportBlocked as e:
            st.error(str(e)); return
        for col, (label, desc, name, data, mime) in zip(st.columns(3), files):
            with col.container(border=True):
                st.markdown(f"**{label}**")
                st.caption(desc)
                if st.download_button("Download", data, file_name=name, mime=mime, type="primary",
                                      key=f"dl-{name}", width="stretch"):
                    rec.log("exported", name, reviewer()); save(rec)
        return
    st.info("🔒 **Downloads unlock after you approve** the draft in the **Review** tab. "
            "That's on purpose: nothing goes to a client without a person checking it.")
    if rec.claims:
        with st.expander("Peek at a draft preview (stamped DRAFT, not for sending)"):
            for label, desc, name, data, mime in build_outputs(rec, draft=True):
                st.download_button(f"Preview — {label}", data, file_name=name, mime=mime, key=f"pv-{name}")


# ============================================================== details
def page_details(rec: ProjectRecord) -> None:
    st.markdown("Behind the scenes — useful for checking and for the demo.")
    with st.expander("📝 Your original notes (the only source of truth)", expanded=True):
        st.code(rec.input.source_text() or "(empty)", language=None, wrap_lines=True)
    with st.expander(f"🧩 Facts the AI found in your notes ({len(rec.facts)})"):
        st.caption("Every fact must quote your notes word for word. Facts whose quote isn't in your notes "
                   "are thrown away before writing.")
        st.dataframe([{"fact": f.statement, "quote from your notes": f.quote, "topic": f.field} for f in rec.facts],
                     width="stretch", hide_index=True)
        if rec.dropped_facts:
            st.warning(f"{len(rec.dropped_facts)} fact(s) were thrown away because their quote wasn't in your notes:")
            st.dataframe([{"fact": f.statement, "claimed quote": f.quote} for f in rec.dropped_facts],
                         width="stretch", hide_index=True)

    with st.expander(f"🖼 Images ({len(rec.input.images)})", expanded=not rec.input.images):
        up = st.file_uploader("Add an image", type=["png", "jpg", "jpeg"], key="img-up")
        if up and st.button("Upload image"):
            name = store.add_image(rec.id, name=up.name, data=up.getvalue())
            rec.input.images.append(ImageRef(filename=name, section="results"))
            review._touch(rec); review.refresh_gaps(rec); save(rec); st.rerun()
        sections = [k for k in SECTION_TITLES if k != "summary"]
        for i, img in enumerate(rec.input.images):
            a, b = st.columns([1, 2])
            path = store.image_path(rec.id, img.filename)
            if path.exists():
                a.image(str(path))
            sec = b.selectbox("Show it next to", sections, index=sections.index(img.section) if img.section in sections else 1,
                              format_func=SECTION_TITLES.get, key=f"isec-{i}")
            cap = b.text_input("Caption (printed as written — keep it factual)", value=img.caption, key=f"icap-{i}")
            x, y = b.columns(2)
            if x.button("Save", key=f"isave-{i}"):
                img.section, img.caption = sec, cap
                review._touch(rec); save(rec); st.rerun()
            if y.button("Remove", key=f"irm-{i}"):
                rec.input.images.pop(i)
                review._touch(rec); review.refresh_gaps(rec); save(rec); st.rerun()

    with st.expander("🕓 History (every edit, approval and download)"):
        st.caption(f"AI engine: {rec.engine} · AI calls: {rec.llm_calls}")
        st.dataframe([e.model_dump() for e in reversed(rec.history)], width="stretch", hide_index=True)

    st.divider()
    a, b = st.columns(2)
    if a.button("🔁 Rewrite the draft from scratch", help="Your edits will be lost."):
        with st.spinner("Rewriting…"):
            try:
                generate(rec, llm); save(rec); st.rerun()
            except LLMError as e:
                st.error(str(e))
    with b.popover("🗑 Delete this case study"):
        if st.button("Yes, delete it for good"):
            store.delete(rec.id)
            st.session_state["project_id"] = None
            st.rerun()


# ============================================================== main
pid = st.session_state.get("project_id")
if not pid:
    page_new()
else:
    try:
        rec = store.load(pid)
    except FileNotFoundError:
        st.session_state["project_id"] = None
        st.rerun()
    step = 3 if review.can_export(rec) else 2 if rec.claims else 1
    stepper(step)
    st.header(rec.input.title or "Untitled case study")
    st.caption(f"{STATUS[rec.status]} · client: {rec.input.client_name or 'not named'}")
    if not rec.claims:
        st.warning("No draft yet.")
        if st.button("✨ Write the draft", type="primary"):
            with st.spinner("Working…"):
                try:
                    generate(rec, llm); save(rec); st.rerun()
                except LLMError as e:
                    st.error(str(e))
    tab_review, tab_download, tab_details = st.tabs(["🔎 Review", "⬇️ Download", "⚙️ Details"])
    with tab_review:
        page_review(rec)
    with tab_download:
        page_download(rec)
    with tab_details:
        page_details(rec)

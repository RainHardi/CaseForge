# Running and hosting the CaseForge website

| | |
|---|---|
| **Website code** | `web/main.py` (FastAPI server), `web/static/` (landing page + app) |
| **Cost** | ₩0 — Render free web service + Neon free Postgres + Gemini free tier |
| **Last updated** | 9 November 2026 |

There are three ways to run it. Start with **A**, use **B** for a quick demo link from your laptop, and **C** for a link that works even when your laptop is off.

---

## A. On your laptop

```bash
pip install -r requirements.txt
playwright install --with-deps chromium   # once: the browser that turns designed reports into PDFs
uvicorn web.main:app --reload
```

On Windows run `playwright install chromium` (no `--with-deps`). Without Chromium everything works except **Download PDF** on the *Designed report* tab.

Open **http://localhost:8000** → landing page. **Start free** → create an account → you're in.

- With no `DATABASE_URL`, data is saved in `data/caseforge.db` (git-ignored).
- Set `SECRET_KEY` in `.env`, otherwise everyone is logged out each time the server restarts.
- The old Streamlit screen still works (`streamlit run app.py`) but the website is the main interface now.

---

## B. Share your laptop with a public link — Dev Tunnels (free)

The link works **only while your laptop is on and the server is running**. Good for a demo or the classmate test.

1. Install once (Windows): `winget install Microsoft.devtunnel` (Mac: `brew install --cask devtunnel`).
2. Log in once: `devtunnel user login` (Microsoft or GitHub account).
3. Start the website: `uvicorn web.main:app --port 8000`
4. In a second terminal:

   ```bash
   devtunnel host -p 8000 --allow-anonymous
   ```

5. It prints a link like `https://abc123-8000.asse.devtunnels.ms` — anyone can open it.

Notes:
- Visitors the first time see a Dev Tunnels warning page; they click **Continue**.
- Without `--allow-anonymous`, only people logged in with your account can open it.
- In VS Code you can do the same from the **Ports** tab → Forward port 8000 → set visibility to **Public**.
- Everyone uses **your** Gemini key; the daily limit per user (`DAILY_AI_LIMIT`) protects it.

---

## C. Host it for free — Render + Neon

Render runs the website; Neon keeps the data. Render's free tier **wipes local files on every restart**, so the database must be Neon (Render's own free database is deleted after 30 days).

### 1. Database — Neon (5 minutes)
1. Sign up at **neon.com** (GitHub login works) → **Create project** → name `caseforge`, region closest to Korea (e.g. Singapore).
2. Copy the **connection string** (`postgresql://…neon.tech/neondb?sslmode=require`).

Free plan: 0.5–1 GB storage, the database sleeps after 5 minutes idle and wakes on the next request. Data is not deleted.

### 2. Website — Render (10 minutes)
1. Push the code to GitHub (the repo must include `render.yaml` and `Dockerfile`).
2. Sign up at **render.com** with GitHub → **New** → **Blueprint** → pick the `CaseForge` repo. Render reads `render.yaml` and builds the `Dockerfile` (a Playwright image that already has Chromium, so PDF reports work online).
3. It asks for the values marked `sync: false`:
   - `DATABASE_URL` → the Neon connection string
   - `GEMINI_API_KEY` → your key
4. **Apply**. The first build takes 5–10 minutes (the image is large). You get a link like `https://caseforge-xxxx.onrender.com`.

Free plan limits:
- The site **sleeps after 15 minutes** without visitors; the next visit waits about a minute. Open it a few minutes before a demo.
- 750 free hours a month — enough for one always-available service.
- 512 MB memory: enough for one PDF at a time. If a report download fails with "out of memory" during the demo, retry once.

**Already set up the old (Python) service?** Change it to Docker: Render dashboard → the service → **Settings** → *Runtime* can't be switched, so delete the service and create the Blueprint again (the Neon data stays).

### 3. Check it
- `https://<your-app>.onrender.com/healthz` → `{"ok": true}`
- Create an account, run the **Messy notes** example, approve, download the PDF.
- **Designed report** tab → pick *Northwind* → **Design the report** → approve → **Download final PDF**.

---

## Settings (environment variables)

| Name | What it does | Default |
|---|---|---|
| `GEMINI_API_KEY` | Gemini key. Empty = offline mode (no AI, sentences copied from notes) | — |
| `GEMINI_MODEL` | Pinned model id | `gemini-3.5-flash-lite` |
| `DATABASE_URL` | Postgres connection string (Neon). Empty = local SQLite file | `data/caseforge.db` |
| `SECRET_KEY` | Signs login cookies. Must stay the same between restarts | random each start |
| `DAILY_AI_LIMIT` | Drafts, formats, report designs and guideline imports each user can run per day | `30` |
| `NOTION_CLIENT_ID`, `NOTION_CLIENT_SECRET` | Turn on **Connect Notion**. From a public integration at notion.so/profile/integrations (OAuth, "Any workspace", Read content). Empty = only the paste-a-secret import | — |
| `NOTION_REDIRECT_URI` | Must match the redirect URI in the Notion integration exactly | `<site>/api/notion/callback` |

Connect Notion tokens are encrypted with a key derived from `SECRET_KEY`. If `SECRET_KEY` changes, existing connections can't be read and users simply connect again.

## Before you share the link

- Tell people **not to upload confidential client data** — text goes to Google's Gemini API (Question Log Q-002). The landing page footer says so too.
- Each workspace only sees its own case studies; teammates join with the invite code on the **Team** page.
- Passwords are stored as scrypt hashes, never in plain text. Login is locked for 15 minutes after 10 wrong passwords.

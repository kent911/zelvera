# Zelvera — Local AI Medical Assistant

**Languages:** [Русский](README.md) · English

A fully functional local application: AI chat, lab-result recognition
(photo/PDF/DOCX), a personal medical record, long-term assistant memory (L0–L3),
a scientific article database with RAG search, notes, health profiles,
reminders and an optional Telegram bot. All data stays local.
The assistant does not make diagnoses and does not replace a doctor.

## Tech stack

- Backend: Python 3.11+ / FastAPI + Uvicorn
- AI: Ollama (local, default) or any OpenAI-compatible API
- Frontend: HTML/CSS/JS without a bundler (wrapped into a desktop app via pywebview)
- Storage: SQLite (medical record, notes, audit, profiles, L0–L3 memory) + ChromaDB (articles)

## Getting started

### 1. Local model (Ollama)

```bash
# install Ollama: https://ollama.com
ollama pull gemma4:26b
ollama serve
```

Default models (configurable in `backend/.env`):
- chat and vision-based photo recognition: `gemma4:26b`
- embeddings for articles: `nomic-embed-text` (`ollama pull nomic-embed-text`)

The model is kept in Ollama memory for 30 minutes (`OLLAMA_KEEP_ALIVE`,
default `30m`); otherwise the first request after idle pays the cold load
(~20 s for a 26b model).

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 3. Start

```bash
python run.py
```

Open http://127.0.0.1:8000 in your browser.

`run.py` listens on `0.0.0.0:8000` and does **not** enable auto-reload — this
is the safe mode for a service (a reload during a bot answer loses the
message). For development enable it with `ZELVERA_DEV=1 python run.py`.
Host and port are set via `ZELVERA_HOST` and `ZELVERA_PORT`.

## Desktop window (Step 6, pywebview)

```bash
cd backend
pip install -r requirements-desktop.txt
cd ..
python desktop.py
```

Starts a local server in a background thread and opens a native window.
If no GUI backend is available, opens the app in the browser (fallback).

Platform requirements for the window:

- **Windows**: Microsoft Edge WebView2 (preinstalled on Win10/11).
- **macOS**: `pip install pyobjc`.
- **Linux (Debian/Ubuntu)**:
  ```bash
  sudo apt install libgirepository1.0-dev gir1.2-gtk-3.0 gir1.2-webkit2-4.1 python3-gi
  ```

## Windows build (.exe) and CI

A single executable for Windows is built with PyInstaller (`zelvera.spec`).

```bat
build_windows.bat
```

The script checks for Python 3.11+, installs dependencies from
`backend\requirements-desktop.txt` and builds the app into `dist\Zelvera\`.

GitHub Actions (`.github/workflows/build-windows.yml`) repeats the same build
on `windows-latest`, verifies that `Zelvera.exe` exists and uploads the
`Zelvera-windows` artifact — runs on push/PR or manually
(workflow_dispatch).

A separate workflow `.github/workflows/tests.yml` on `ubuntu-latest` runs
`pytest` (folder `backend/tests`): marker catalog, reference norms, Wikipedia
help cache and grounding, marker extraction, long-term memory L0–L3. Locally:

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -q
```

## Using an OpenAI-compatible API (optional)

In **AI settings** choose backend **OpenAI / llama-server**, set the address
(e.g. `http://192.168.1.100:8080` — `/v1` is appended automatically) and the
model name (`bonsai2-27B`). A key is not required for a local llama-server.

The same can be set in `backend/.env`:

```env
LLM_BACKEND=openai
USER_LLM_BASE_URL=http://192.168.1.100:8080/v1
USER_LLM_API_KEY=local
USER_LLM_MODEL=bonsai2-27B
```

The key is stored only locally. Article embeddings still go through Ollama.

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Status and active model |
| GET | `/api/config` | Current backend/model for the UI |
| POST | `/api/chat` | Chat; the reply streams via SSE (`data: {content}`) |
| POST | `/api/documents/extract` | Photo/PDF/DOCX → recognized text + health markers (JSON) |
| POST | `/api/records` | Save a lab-result record (markers) to the medical record |
| GET | `/api/records` | List of record cards (`?profile_id=` — profile only, `critical_count`) |
| GET | `/api/records/trends` | Marker dynamics over dates (`?profile_id=`), including the norm corridor `ref_low`/`ref_high` |
| GET | `/api/records/compare` | Compare two records (`?a=&b=`) — per-marker changes |
| GET | `/api/records/longterm` | Per-year marker summary for a period (`?from=&to=`) |
| POST | `/api/records/longterm/report` | AI health report for the period based on the yearly summary (SSE stream) |
| GET | `/api/records/export.pdf` | Export the medical record to PDF (`?profile_id=`) |
| GET | `/api/records/{id}` | Record with markers (critical ones have the `critical` field) |
| DELETE | `/api/records/{id}` | Delete a record from the card |
| POST | `/api/articles` | Upload a scientific article (PDF/DOCX/TXT) → chunks + embeddings + summary |
| GET | `/api/articles` | List of articles |
| POST | `/api/articles/search` | Semantic search across all articles |
| POST | `/api/articles/{id}/search` | Search inside one article (for "Discuss with AI") |
| DELETE | `/api/articles/{id}` | Delete an article |
| POST | `/api/analysis` | Analytical report "labs ↔ articles" (SSE streaming, `?profile_id=`) |
| GET | `/api/settings` | Current models (Ollama) |
| POST | `/api/settings` | Save selected models |
| POST | `/api/settings/ollama-models` | List of models from a running Ollama |
| POST | `/api/settings/openai-models` | List of models from an OpenAI-compatible API (llama-server) |
| POST | `/api/settings/ollama-pull` | Download a model into Ollama (`ollama pull`, background task) |
| GET | `/api/settings/ollama-pull/{model}` | Model download status |
| POST | `/api/settings/telegram-test` | Validate the Telegram bot token (`getMe`) |
| GET | `/api/settings/telegram-status` | Telegram bot status: configured/running, STT/TTS |
| GET | `/api/logs` | Latest lines of the app log |
| GET | `/api/logs/download` | Download the log (.log) |
| POST | `/api/logs/client` | Write a frontend error into the log/audit |
| GET | `/api/notes` | List of notes (AI takeaways) |
| POST | `/api/notes` | Save a note (can be linked to an article) |
| DELETE | `/api/notes/{id}` | Delete a note |
| GET | `/api/memory` | Long-term memory snapshot (facts, recaps, portrait) |
| POST | `/api/memory/facts` | Add/update a fact (L1) |
| DELETE | `/api/memory/facts/{id}` | Delete a fact |
| DELETE | `/api/memory` | Clear profile memory (L0–L3) |
| GET | `/api/notes/export.pdf` | Export notes to PDF |
| GET | `/api/profiles` | List of profiles + current (single profile) |
| PATCH | `/api/profiles/{id}` | Update a profile (name, birth_year, height_cm, weight_kg, blood_type) |
| POST | `/api/profiles/{id}/activate` | Make a profile current |
| GET | `/api/profiles/current` | Current profile |
| GET | `/api/reminders` | List of reminders (`?profile_id=`) |
| POST | `/api/reminders` | Create a lab-retest reminder |
| DELETE | `/api/reminders/{id}` | Delete a reminder |
| GET | `/api/audit` | Audit log of actions (with type filter) |
| DELETE | `/api/audit` | Clear the audit log |
| GET | `/api/backup/export` | Download a ZIP archive of all data (DB, articles, settings) |
| POST | `/api/backup/import` | Restore data from a ZIP archive |

## Backup

In the settings ("Ollama Settings") there is a "Backup" section:

- **Save a copy** — downloads a ZIP archive with all data: `medical.db`
  (medical record, articles, notes, profile, reminders, audit, L0–L3 memory),
  `settings.json` and the vector article database `chroma/`;
- **Restore from a copy** — uploads the ZIP archive; the data is fully
  replaced (with confirmation). The archive is validated for integrity and the
  presence of `medical.db`;
- all actions are written to the audit log (`backup_export`, `backup_import`).

## Step 2 — document processing

The "Lab photo" and "Document (PDF/DOCX)" buttons in the chat:

- **Images**: a vision model recognizes the form text (OCR).
- **PDF/DOCX**: text is extracted locally (PyMuPDF / python-docx), form tables are read row by row.
- Then the LLM extracts health markers into JSON: `{name, value, unit, reference_range, status}`.
- The result is shown as a table in the UI; the "Ask AI" button sends the parse into the chat.
- The prompt includes the catalog of known markers (canonical names and
  synonyms/abbreviations grouped by category), so the model maps `HGB`, `WBC`,
  `ALT` to canonical names right away. If a marker is not in the catalog, its
  name is kept as in the form (no substitution).
- If a marker name is not found in the catalog (new/unfamiliar/garbled
  marker), the app looks it up in the offline Wikipedia (Kiwix) and refines
  the parse; a "Refined via Wikipedia" block with article links appears under
  the table. If Kiwix is unavailable, the original parse is kept.

Photo recognition requires a vision model in Ollama:

```bash
ollama pull gemma4:26b   # supports images
```

## Step 3 — personal medical record (SQLite)

Recognized markers are automatically saved into `data/medical.db` (excluded from git):

- Table `records` — date, source, summary.
- Table `markers` — name, value, unit, reference range, deviation.

The "My medical card" tab shows lab history: date, source, number of markers,
summary. Records expand into a marker table and can be deleted with the
"Delete" button.

The "Trends" button shows a chart per marker with the norm corridor (dashed
bounds and a shaded band), dates and value points. The "Compare" button opens
a panel: pick two tests (earlier/later) and get a table of changes — increase,
decrease, appeared/disappeared marker and status change.

The "Multi-year report" button collects all tests for the selected period
(e.g. 2018-2025; years are entered manually, defaulting to the earliest and
latest record) into a marker-by-year table: median, measurement count and a
row assessment (persistently above/below norm, improving, worsening,
fluctuating). The "Generate AI report" button builds an overall health text for
the period from that summary; the report is informational and does not replace
a doctor.

### Critical deviations (alarms)

Some markers have critical thresholds (for example, hemoglobin below
70 g/L, glucose above 27.8 mmol/L, platelets below 20, potassium below/above
2.5/6.5 mmol/L, etc.):

- in the marker table critical values are highlighted with a pulsing
  red "⚠ Critical!" badge;
- in the record list a "⚠ N crit." badge appears;
- the `get_medical_card` AI tool prints a "WARNING: CRITICAL deviations that
  require immediate medical attention" block at the start of a reply;
- the thresholds and synonyms database lives in `backend/app/services/critical.py`,
  while canonical marker names and synonyms live in
  `backend/app/services/marker_catalog.py`.

## Marker catalog and Wikipedia help

The single marker catalog (`backend/app/services/marker_catalog.py`) contains
51 markers, 16 categories and 242 synonyms (Russian/English names and
abbreviations). It is used everywhere a marker name needs to be matched:

- name normalization when writing to the medical card ("Hb", "HGB" and
  "Hemoglobin" are the same);
- the document-recognition prompt — the model maps synonyms and abbreviations
  from the form to canonical names right away;
- grouping dynamics in trends and labels in alarms/reminders;
- the `GET /api/markers/catalog` API — the full list for the UI.

If a marker is missing from the catalog, the app queries the offline Wikipedia
through Kiwix and caches the found help in the `wiki_cache` table (SQLite) for
7 days — including the negative "not found" result, to avoid repeating the
search. The help is used:

- when parsing documents (an extra LLM pass + a sources block in the UI);
- in the `get_medical_card`, `get_marker_trends` and `check_marker_norm` chat
  tools — the model gets help for unfamiliar markers.

Any Kiwix, network or timeout failure does not affect the main answer: the help
is simply omitted.

## AI settings menu

The "AI settings" button in the side menu:

- backend: Ollama or an OpenAI-compatible API (llama-server);
- Ollama and/or llama-server address (`http://192.168.1.100:8080`, `/v1` is appended);
- "Refresh model list" — fetches models from the selected backend;
- choose the chat model, vision model and embedding model (can be typed manually);
- the choice survives restarts (`data/settings.json`); takes priority over `.env`.

## Step 4 — scientific article database (ChromaDB / RAG)

In the "Article database" tab:

- Upload PDF/DOCX/TXT → text is extracted, split into overlapping chunks,
  embeddings are computed per chunk (Ollama `nomic-embed-text`
  or OpenAI `text-embedding-3-small`), the LLM writes a short summary.
- Chunks are stored in ChromaDB (`data/chroma`, cosine metric), article
  metadata in SQLite.
- Semantic search: the query is embedded and matched against all chunks,
  returning relevant fragments with their closeness. Each fragment can be
  discussed with the AI.

Required local Ollama models:

```bash
ollama pull nomic-embed-text
```

## Step 5 — analytical report "labs ↔ articles"

The "Analytical report" button in the chat:

1. Takes the current markers from the medical record (latest value of each marker).
2. Embeds them and finds relevant scientific fragments in ChromaDB.
3. The LLM composes a personalized report: marker overview → comparison with
   scientific data → what to track → disclaimer.

The assistant does not make diagnoses and does not prescribe treatment; every
report ends with a disclaimer about consulting a doctor.

## Notes — AI takeaways on articles

The AI in chat is a language model; it does not write to the database itself.
Saving is done by the UI:

- In the chat press "Save takeaway" — a window with the latest AI reply opens,
  choose an article (optional) and save it to the database.
- The "Notes" tab in the side menu — all saved takeaways with a date
  and article binding; they can be deleted.
- A note is bound to an article automatically if the dialog was started with
  the "Discuss with AI" or "Ask AI about this fragment" button.

## AI tools (function calling)

The chat supports tool calls. Most tools only read data; writes to the
database are limited to `save_analysis_to_card` and `save_memory_fact`:

- `search_articles(query, limit)` — semantic search over the scientific article database;
- `list_articles()` — list of uploaded articles;
- `get_medical_card(days)` — current markers from the active profile's
  medical record (optionally — for the last N days);
- `get_profile()` — profile details: name, birth year and age, blood type,
  height, weight (also injected into the chat system context);
- `get_marker_trends(marker, days)` — marker dynamics over dates,
  number of measurements and trend direction;
- `check_marker_norm(marker, value, unit, sex, age)` — checks a value against
  the reference-norms reference (sex- and age-aware);
- `save_analysis_to_card(markers, date)` — saves discussed markers to the
  medical card as a single record;
- `search_wikipedia(query, limit)` and `list_kiwix_books()` — search in the
  offline Wikipedia (Kiwix);
- `search_memory(query)` / `list_memory()` — long-term memory facts for the profile;
- `save_memory_fact(category, key, value)` — remember a fact when the user
  explicitly asks (not one-off lab numbers).

The record-reading tools (`get_medical_card`, `get_marker_trends`,
`check_marker_norm`) automatically add Wikipedia help for markers missing from
the catalog (see the section above).

Tools work with the single health profile: edit the profile in the header
(pencil button) and the AI will answer based on that profile's data.

Supported by both backends: Ollama (`tools`) and the OpenAI-compatible API
(`tools`). If the model does not support tools or they are unavailable,
the chat automatically falls back to a plain answer without tools.

## Long-term assistant memory (L0–L3)

A local analogue of hierarchical agent memory. Everything lives in
`data/medical.db`, no cloud:

- **L0** — raw dialogue turns (`memory_messages`);
- **L1** — lasting facts: allergies, habits, complaints, medications
  (`memory_facts`); one-off lab numbers are not stored here — they belong
  in the medical card;
- **L2** — compressed recaps of recent dialogues (`memory_summaries`);
- **L3** — a short profile portrait (`memory_profile`).

After a chat reply (web and Telegram) facts are extracted in the background.
Relevant L1–L3 facts are injected into the system context of the next question.
The "Memory" tab shows facts and the portrait; they can be edited by hand.

## Action audit

The "Action audit" tab in the "Logs and errors" window shows the history of
user actions (SQLite, table `audit_log`):

- chat queries and the analytical report;
- document recognition (photo/PDF/DOCX) and adding records to the card;
- article upload/deletion and searching them;
- saving/deleting/exporting notes;
- editing the health profile (name, birth year, height, weight, blood type);
- creating/deleting lab-retest reminders;
- changing settings and downloading models;
- AI tool calls (function calling);
- exporting the medical record to PDF;
- frontend errors.

Filtering by action type and full log cleanup are available.

## Health profile

The app works with a single profile — for one person. The header on the left
shows the profile name; the pencil button opens editing:

- profile fields: name, birth year, height, weight, blood type;
- all data (medical record, reminders, L0–L3 memory, AI tools) is tied to this profile;
- the blood type is stored normalized, e.g. `A(II) Rh+`;

## Lab-retest reminders

In the "My medical card" tab:

- add a reminder: a marker plus an interval in days (for example, "Hemoglobin,
  every 30 days");
- when a new record with this marker appears, the reminder records the
  date (`last_reported` updates automatically);
- the reminder tells you in how many days the test should be retaken
  (or flags an overdue item).

## Telegram bot

An optional long-polling bot (no public HTTPS or webhooks required). It
starts together with the server when a token and a list of allowed Telegram
IDs are set.

Setup:

1. Create a bot via `@BotFather` and get the token.
2. In "Settings" → "Telegram bot" paste the token and your Telegram ID
   (get your ID via `@userinfobot`) and press "Check token".
3. Choose whether you need voice messages and re-test reminders, then save.

Features: text chat with the AI (using your medical card, articles and long-term memory),
a photo of a lab report with recognition and confirmation before saving to
the card (send it as a photo or as an image file — files are not compressed
and are recognized more accurately), voice messages (recognition via
faster-whisper, spoken answers via
edge-tts, packages from `backend/requirements-voice.txt`) and push reminders.
L0–L3 facts are shared with the web Memory tab: `/memory` lists them,
`/reset` clears only the Telegram dialog history.

The bot replies only to users on the allow-list. The token is stored in
`backend/.env` or the data folder (never committed to git).

If the container has no direct access to `api.telegram.org` (requests time
out), set an HTTP/SOCKS proxy in the "Proxy for Telegram" field or via the
`TELEGRAM_PROXY` variable (e.g. `socks5h://host:10808`). When
`TELEGRAM_PROXY` is unset, the system proxy from `HTTPS_PROXY`/`ALL_PROXY`
is used (the systemd unit reads `/etc/environment`; local addresses from
`NO_PROXY` go direct). SOCKS proxies require the `socksio` package (already
in `requirements.txt`). A common cause of timeouts is unreachable IPv6 while
`api.telegram.org` has an AAAA record: by default the bot connects over IPv4
only (the "Connect over IPv4 only" setting, `TELEGRAM_FORCE_IPV4`).

If the bot answers only every other message, check whether two processes poll
the same bot at once (`pgrep -af uvicorn`, `systemctl status zelvera`):
Telegram delivers updates to only one of them. The bot holds a lock file
`data/telegram.lock` and a second instance will not start polling; the log
will show "another process is already polling the bot".

## Voice input

The chat has a microphone button — speech recognition via
`webkitSpeechRecognition` (available in Chrome/Edge). The recognized text is
inserted into the input field. If the browser does not support recognition,
the button is hidden.

## Quick suggestions (onboarding)

At the start of a new dialog, chips with example questions appear under the
greeting ("Show my latest lab results", "How has my cholesterol changed over
the last month?", etc.). Clicking a chip sends the question to the chat. The
chips disappear after the first message and reappear when "New dialog" is pressed.

## Roadmap (next steps)

Implemented:

- MVP with chat, photo/PDF/DOCX processing and a personal medical record (SQLite);
- scientific article database with RAG search (ChromaDB) and the analytical report;
- notes (AI takeaways) with PDF export;
- health profiles and lab-retest reminders;
- AI tools (function calling: reading the card/articles/memory, writing lab records and memory facts)
  over the active profile's data;
- backup: ZIP export and restore (`medical.db`, `settings.json`, `chroma/`);
- marker catalog with name normalization, parse refinement and chat help via
  the offline Wikipedia (with caching), pytest tests in CI;
- marker trend charts with a norm corridor and two-record comparison;
- long-term report: per-year marker summary and an AI health assessment for a period;
- Telegram bot: text chat, lab-report photos into the card, voice messages, reminders;
- action audit, logs, desktop window (pywebview), Windows build (PyInstaller + CI);
- long-term assistant memory L0–L3 (facts, recaps, portrait) locally in SQLite.

Possible next steps (not prioritized):

- "Monthly summary" auto-digest — an LLM summary of marker dynamics over 30 days;
- notifications for reminders on app startup;
- mobile UI adaptation.

## Structure

```
backend/app/
  main.py            # FastAPI, serves the frontend
  config.py          # settings from .env
  routes/chat.py     # POST /api/chat (SSE streaming)
  routes/documents.py# POST /api/documents/extract (photo/PDF/DOCX)
  routes/records.py  # CRUD of the medical record (SQLite)
  routes/articles.py # article upload/search (RAG)
  routes/analysis.py # analytical report "labs ↔ articles"
  routes/settings.py # Ollama model settings
  routes/notes.py    # notes (AI takeaways on articles) + PDF export
  routes/profiles.py # health profiles (CRUD + current profile)
  routes/reminders.py# lab-retest reminders
  routes/backup.py    # ZIP backup export/import
  routes/kiwix.py     # offline Wikipedia status and search
  routes/logs.py      # application log
  services/telegram_bot.py # Telegram bot: chat, lab-report photos, reminders, memory
  services/voice.py  # optional STT/TTS for Telegram (faster-whisper, edge-tts)
  services/llm.py    # Ollama / OpenAI client + function calling
  services/tools.py  # AI tools (articles, card, memory; writes labs and facts)
  services/audit.py  # user action audit
  services/document.py   # text extraction from PDF/DOCX + chunking
  services/extractor.py  # LLM extraction of health markers into JSON
  services/marker_catalog.py # marker catalog: categories and synonyms
  services/critical.py   # critical marker thresholds (alarms)
  services/norms.py      # reference-norms reference (sex/age)
  services/kiwix.py      # offline Wikipedia (Kiwix) client
  services/wiki_lookup.py# Wikipedia help for a marker + SQLite cache
  services/i18n.py       # RU/EN localization
  services/memory.py     # long-term memory L0–L3 (facts, recaps, portrait)
  routes/memory.py       # GET/POST/DELETE /api/memory
  services/database.py   # SQLite: records, markers, articles, profiles, reminders, memory
  services/embeddings.py # embeddings via Ollama / OpenAI
  services/articles_db.py# ChromaDB: article chunks and semantic search
  services/settings_store.py # runtime model settings (data/settings.json)
  services/pdf_export.py # medical card and notes export to PDF (DejaVu Sans)
backend/tests/         # pytest: catalog, norms, cache/grounding, extraction, memory
frontend/
  index.html         # chat UI, recognition panel, profiles, reminders, memory
  css/style.css
  js/app.js          # response streaming, document uploads, voice input, Memory tab
data/                # databases (SQLite, ChromaDB) — not in git
```

## Security

- The app runs only locally.
- Medical data in `data/` is excluded from git.
- Do not use public Wi-Fi networks when working with lab results without encryption.

## License

Copyright (c) 2026 Chernomurov Egor Mikhailovich. All rights reserved.

The software, its source code and documentation are the exclusive property of
the rights holder (Chernomurov Egor Mikhailovich). Copying, modification,
distribution and commercial use without written permission are prohibited. See
`LICENSE.txt` for details.

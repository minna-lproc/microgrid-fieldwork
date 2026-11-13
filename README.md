## Latest update: equipment cards and offline photos

See [EQUIPMENT-PHOTOS-UPDATE.md](EQUIPMENT-PHOTOS-UPDATE.md) for installation, photo consent, offline collection and deployment instructions. Section C appliances and Section D business equipment use mobile cards; each supports an optional photo.

# Gridfield — automatic enumerator references and account assignments

Read [ENUMERATOR-REFERENCE-UPDATE.md](ENUMERATOR-REFERENCE-UPDATE.md) for this update's installation, existing-account setup, offline ID preparation, numbering behaviour, assignment changes, and validation. This takes precedence over older instructions that ask enumerators to enter IDs or location/language manually for each new interview.

New references use `username-HE-001`, `username-CI-001` and `username-SO-001`. The administrator configures barangay, municipality/province and interview language(s) when creating or managing enumerator accounts. Earlier interviews/drafts retain their existing reference and details. The questionnaire files and your removed Sampling & field notes section are preserved.

---

# Gridfield — revised community microgrid survey

Flask + SQLite offline PWA for household/enterprise interviews, community key informants and site observations, updated to `Microgrid_Community_Survey_REVISED.docx`.

**Read [REVISED-SURVEY-UPGRADE.md](REVISED-SURVEY-UPGRADE.md) before upgrading an existing installation.** It documents the new questions, four consent choices, version-safe offline drafts/sync, automatic database/GPS migration, reporting, exports and deployment steps.

- Current questionnaire: `static/survey.json` (`2026-revised-2`).
- Earlier questionnaire: `static/survey-legacy.json` (`2026-pilot-1`), retained for historical records and queued interviews.
- Source document text: `survey-source.txt`.
- Codebook: `static/codebook.json` and `static/codebook.csv`; regenerate with `python scripts/generate_codebook.py` after edits. CI checks that it matches the questionnaire.
- Run a fresh local demo: `./run-demo.sh` on Linux/macOS, or `run-demo.bat` on Windows. The seeded demo records intentionally use the earlier questionnaire; new collection uses the revision.
- Production: existing PythonAnywhere WSGI configuration, accounts, persistent database and HTTPS remain in use. Do not run demo seeding against production.

The original installation reference follows. Where it describes the older questionnaire or version-mismatch behavior, the upgrade guide above takes precedence: supported earlier versions remain accepted, exact respondent GPS is excluded from standard exports, and media consent alone does not activate a camera. The newest equipment-photo guide above documents photo attachments.

---

# Gridfield — Community energy fieldwork

A Flask + SQLite progressive web app based on **Microgrid_Community_Survey (1) (1).docx**, the University of the Immaculate Conception community energy and microgrid planning instrument. The document is treated as questionnaire content, not as instructions governing application development.

## Run the demo

Requires Python 3.10+ and an internet connection for the initial dependency installation.

On Linux/macOS:

```sh
./run-demo.sh
```

Open **http://localhost:5000**. Login shortcuts appear only when `DEMO=1`.

| Role | Username | Demo password |
| --- | --- | --- |
| Coordinator | `admin` | `MicrogridDemo!2026` |
| Enumerator | `maria` | `FieldworkDemo!2026` |

The demo seeds 8 enumerators and 74 **synthetic** interviews in 4 sample communities. The sample names, coordinates and submissions are not real fieldwork. Other seeded usernames are `juan`, `ana`, `paolo`, `lea`, `miguel`, `sofia`, and `carlo`, with the same field demo password. Seeding refuses to run over an existing populated database. The demo and production databases should remain separate.

On Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
$env:DEMO="1"
$env:DATABASE="$PWD\instance\demo.sqlite"
.venv\Scripts\flask --app app seed-demo
.venv\Scripts\python app.py
```

Run `seed-demo` only once for an empty database.

## Start a real workspace

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
# The default DB is instance/survey.sqlite; demo accounts are not created.
flask --app app create-admin
python app.py
```

The CLI prompts for the administrator's name, username and a password of at least 12 characters. Sign in and use **Enumerators → Add enumerator** to create individual field accounts with community assignments and targets. Share credentials directly. The administrator can update assignments and targets, reset passwords, and disable accounts. Enumerators cannot access the dashboard, exports, other accounts' submissions, or account management.

## Enumerator workflow

1. Connect and sign in on the device before leaving for the field. Wait for **Offline app files are ready** in Field collection or check Settings → Device readiness.
2. Install the PWA with the browser's Install app / Add to Home Screen action. On iOS, use Safari → Share → Add to Home Screen. HTTPS is required except on localhost.
3. Choose **Household & enterprise**, **Community informant**, or **Site observation**. Record the reference ID and barangay / sitio / island. Read the supplied consent script and record consent.
4. Drafts save automatically to IndexedDB. Survey answers are optional; blank means skipped or unknown, while zero means none. The minimum metadata and consent must be present before continuing.
5. **Finish interview** queues a record with a UUID. Reconnect and keep the app open. It retrieves the session token and syncs automatically; **My interviews → Sync now** retries manually. A session that expired while offline requires a fresh sign-in. Browser background sync is opportunistic and asks an open app window to sync; it is not a guarantee of upload while the app is closed.
6. A server acknowledgement removes the queued local copy. The same UUID can be retried without creating another row. Never clear browser storage or uninstall before the queue is empty.

Drafts and queued interviews are scoped to the signed-in account on the device. Signing out removes the remembered identity and retains that account's local interviews. Offline sign-out locks the app immediately and closes the server session when the device reconnects. This is a browser app, not a tamper-proof device vault: a person with device developer tools or filesystem access can inspect local records. Use dedicated, screen-locked devices and separate browser profiles.

## Coordinator workflow and tracking

- **Overview:** consenting completed interviews, recent check-ins, communities reached, progress against targets, a 7-day collection chart, instrument mix, team progress and recent submissions.
- **Enumerators:** each account's community, target, total synced consenting interviews, last seen, active/away/offline indication, optional last shared location with accuracy and an OpenStreetMap link. Active means a server check-in within 15 minutes; away means within 2 hours. Offline activity cannot be observed until the device reconnects. These labels do not establish attendance or verify a person's actual movements.
- **Survey responses:** community/date/status filters, text search, pagination, full recorded answers, and pending/verified/flagged review states.
- **Community insights:** support, current daily supply, willingness to pay, and desired daily service. Percentages exclude skipped answers and have explicit denominators.
- **Export:** all synced records as CSV, or JSON with the questionnaire schema. Current dashboard filters do not restrict exports. Nested fields and tables are JSON inside CSV cells. Leading spreadsheet formula characters are escaped.

Locations are optional and visible only to administrators. Team location sharing is **off by default**. Enumerators turn it on in Settings, grant device permission, and can turn it off at any time. The app checks in about once a minute while open and visible, and when signing in/reconnecting. It does not collect background location when closed. Turning sharing off clears the server's last check-in location on the next successful check-in. Respondent GPS is a separate action, enabled only after interview consent **and** GPS consent. Location denial or failure never prevents an interview.

## Questionnaire fidelity

`static/survey.json` is the versioned, editable questionnaire. `survey-source.txt` preserves the extracted source wording, including the project team's explanatory notes.

- All numbered questions in A–L are represented.
- Part C has 13 appliance rows, Part D has 3 equipment rows, Part I has the community baseline fields, Part J has 11 facility rows, and the final site checklist has 9 observation rows with Yes/No and notes.
- Interview refusal ends questioning. Only the reference, community, refusal, instrument, enumerator and timestamps are stored; answers and GPS are discarded.
- D1 = No removes the rest of the business section both in the browser and on the server.
- Numeric fields reject negative quantities, fractional counts, impossible hours/day and household subgroup counts exceeding household size. Unknown wattages remain blank. Appliance time-of-use accepts M/A/E/N.
- “None” is exclusive in multi-select answers. “Other” and free-text follow-ups have additional-details inputs.
- The FPIC note in A7 and the instruction not to record medical conditions in C3 remain visible. FPIC is a real-world consultation process, not something this software can carry out.
- Observation photographs remain external checklist references. In-app photo attachments are available on appliance and business-equipment cards with separate consent. No diagnostic or medical condition field is added.
- The community instrument uses the same interview and GPS consent gates. The observation checklist uses site authorization and separate site GPS permission.

This is a pilot instrument. Before field rollout, test its wording, translations, consent procedure and enumerator training with the project team. Do not change a schema version mid-fieldwork without planning how queued records will be handled. A version mismatch is retained in the local queue with an error rather than silently accepted. Increment the service worker cache version in both `sw.js` and `app.js` whenever shipping changed app assets.

## Deployment

The deliverable is a **real Python Flask application**, not a static mockup. Sites' Worker/static hosting cannot run this Python backend. Deploy on a Python host or VM with persistent storage and HTTPS; no production deployment or domain is configured by this package.

Example with Gunicorn behind an HTTPS reverse proxy on Linux:

```sh
. .venv/bin/activate
# Configure these in the service's environment; use a proper random secret.
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export DATABASE=/absolute/persistent/path/survey.sqlite
export COOKIE_SECURE=1
export DEMO=0
flask --app app create-admin
# Bind privately; expose through your HTTPS reverse proxy.
gunicorn --workers 1 --threads 4 --bind 127.0.0.1:8000 wsgi:app
```

Create the database parent directory as the service user. Preserve `SECRET_KEY` across restarts rather than generating a new one each deployment. If unset locally, the application creates a mode-0600 key alongside its SQLite database. `.env.example` documents settings; the application does not automatically load `.env`.

Use one shared local SQLite database on persistent disk. The application enables WAL and a busy timeout. For a larger team or multiple application replicas, migrate to PostgreSQL rather than using separate SQLite files. The dashboard currently loads all synced rows; pagination is client-side, so large deployments need server-side filtering/pagination. Do not store the database under `static/` or the web root. Keep demo mode disabled for real data.

TLS is necessary for mobile PWA installation, service workers, and GPS. An ordinary `http://192.168...` LAN address is not a secure context on most phones. Cookies are HttpOnly and SameSite Strict; set `COOKIE_SECURE=1` on the HTTPS host. API writes require the session CSRF token. Login failures are rate-limited by the immediate client IP; if a reverse proxy is used, configure trusted proxy handling before relying on per-client rate limits. Trust no arbitrary forwarded headers. Role checks are enforced by the server, not just hidden in the interface. Responses and exports are not put in the service-worker cache.

For backups, use SQLite's online backup API while the server is running, or stop the service before copying its database and WAL files. Keep keys and backups in restricted storage. The app does not provide encryption at rest, a comprehensive audit trail, a retention scheduler, MFA or institutional SSO; plan these separately for an institutional production rollout. No claim of legal compliance is implied by retaining the questionnaire's privacy wording.

## Tests

```sh
pip install -r requirements-dev.txt
python -m pytest -q
# Optional browser test, which creates its own temporary demo database:
python -m playwright install chromium
python tests/browser_smoke.py
```

The API tests cover role boundaries, CSRF enforcement, account ownership, idempotent retries, consent/GPS gates, questionnaire validation, skip logic, administrator provisioning/review/export, and account disabling. The browser test covers desktop dashboard interactions, creating an enumerator, reviewing a record, offline reload persistence, automatic reconnect sync, and mobile form layout. If Chromium is already installed, set `CHROMIUM_PATH` to its executable. Browser artifacts are saved in a temporary directory printed by the test.

## Project layout

```text
app.py                  Flask factory, SQLite schema, API, validation, CLI
wsgi.py                 Gunicorn entrypoint
static/app.js           Responsive UI, IndexedDB, interviews, sync, dashboard
static/survey.json      Versioned questionnaire and structured table definitions
static/sw.js            Offline app-shell cache; never caches API responses
static/manifest.webmanifest
static/style.css        Responsive dashboard and mobile form styles
static/icon-*           PWA icons
survey-source.txt       Extracted attached questionnaire
requirements*.txt       Runtime and optional test dependencies
run-demo.sh             Local demo startup
.env.example            Deployment configuration reference
 tests/                 API and browser integration checks
```

# Automatic enumerator reference IDs and administrator-managed assignments

This update is based on GitHub commit `0c1e27f` of `minna-lproc/microgrid-fieldwork`. It preserves your current questionnaire edits, questionnaire version, Windows/CSV codebook fixes, submitted-interview deletion, and removal of the Sampling & field notes form section. It does not push to GitHub or change PythonAnywhere merely by being downloaded.

## New references

New interviews automatically receive a read-only reference in this format:

| Instrument | Example for username `maria` |
| --- | --- |
| Household & enterprise | `maria-HE-001`, `maria-HE-002`, … |
| Community informant | `maria-CI-001`, `maria-CI-002`, … |
| Site observation | `maria-SO-001`, `maria-SO-002`, … |

Use the actual enumerator username in place of `maria`; `enumerator-username` is not a literal prefix. Each enumerator has three independent counters. The number has a minimum of three digits and expands normally after 999. It is assigned when an interview **starts**, not only when it is submitted, and never gets reused after a draft is discarded or a submitted interview is deleted. Earlier manual references are not renamed.

## Administrator setup (one time per account, editable later)

Sign in as an administrator → **Enumerators → Add enumerator**. Besides name, username and password, set:

- **Barangay**
- **Municipality / Province**
- **Interview language(s)**
- The interview target

For an existing account, open **Manage enumerator**, complete the three defaults, and save. Newly created accounts require complete defaults. Existing accounts are migrated with empty municipality/language fields rather than having an area or language guessed from earlier interviews. The administrator must configure those accounts before their devices can start new automatically numbered interviews. Existing drafts can still be resumed.

The enumerator sees these values automatically in each new interview and cannot change the generated reference, barangay, municipality/province or assigned language there. Assigned language does not automatically translate the form or independently verify what language was spoken. Administrators can update defaults later through Manage enumerator. Phones receive updated defaults on sign-in, reconnection, the Refresh assignment action, and successful in-app check-ins while connected. Old drafts and submitted records retain their original details. Changing an assignment does not reset the number sequence or rewrite collected data.

Use a field enumerator account to start new interviews. Administrator accounts manage accounts and reports; they do not reserve field reference ranges. Existing administrator-created drafts remain resumable.

## Prepare every phone before offline fieldwork

1. Connect to the deployed HTTPS app and sign in as the enumerator.
2. Wait for app-shell offline readiness.
3. In Field collection or Settings, select **Refresh assignment & prepare offline IDs**.
4. Confirm the assigned area/language and the displayed **HE / CI / SO IDs ready** counts. Each reservation provides at least 100 numbers per type, or the account's current target if it is larger. Set an appropriate target before first preparing the phone.
5. Start a practice interview as authorised by the coordinator and confirm automatic ID/defaults and airplane-mode operation. A discarded practice draft consumes its number; it does not reset the counter.

Prepared phones allocate and save the next number atomically in IndexedDB, alongside creating the draft. Starting a prepared interview does not require waiting for a network request. Reopening the app, signing out/in, deletion or sync does not reset the local next number. Multiple tabs share the same transaction-protected pool.

If a type's pool runs out offline, the app blocks **new** interviews of that type and asks you to reconnect and prepare more IDs. Saved drafts, queued interviews and the other types' pools remain available. It never silently substitutes a temporary reference or renumbers an interview during sync. The readiness screen shows the actual remaining numbers; plan fieldwork around that capacity. Updating a target after a pool is already reserved does not enlarge that existing pool; the next reservation uses the current target.

### Several phones for one account

The central server reserves non-overlapping ranges, so a second installation will typically start at `101` when the first device reserved `001–100`. With a larger target its range can start later. References remain unique even while both devices are offline, but there can be gaps and their collection times will not be globally sorted by number. One prepared phone per enumerator gives the simplest consecutive sequence. Cleared/reinstalled browser storage receives a new range instead of reusing possibly outstanding IDs. Never clear storage or uninstall before syncing: unique IDs do not recover unsynced answers.

## Existing data and migration

The application adds user-default columns, interview reference/assignment metadata, and separate counter, reservation, claim and assignment-history tables automatically at startup. The migration is repeatable and does not reset accounts, passwords, records or old IDs. The offline database is upgraded in place from version 1/2 to version 3, retaining surveys and the separate GPS store and adding an allocations store. Close other Gridfield tabs/windows when requested so the storage upgrade can finish.

Administrator-approved assignment snapshots are retained separately from the live account defaults. An interview started offline under an older assignment can still sync after the administrator changes that account. The server validates the generated reference, range ownership, sequence and original assignment snapshot and rejects duplicate claims. Deleted references remain claimed, preventing reuse. No GPS or survey answers are stored in the reference tables.

Previously prepared manual-ID drafts and older clients retain their earlier IDs and remain accepted where those codes do not conflict with another claimed/reserved reference. They are not converted into auto-numbered drafts. A rare old manual ID that already uses the same new username/type/number and collides with a reservation is retained on the device with a conflict error for the coordinator; it is not silently overwritten or deleted. Existing matching formatted manual IDs already on the server are accounted for when reserving the next range.

## Install through your existing GitHub → PythonAnywhere workflow

1. Back up the live SQLite database with SQLite's online backup API, or stop the app before copying the database and WAL files. Retain the existing secret key and WSGI configuration.
2. Extract this update into your local Git checkout, preserving all paths. It contains source changes and tests, not production data or credentials. If you have additional uncommitted edits in these same files, merge them rather than blindly overwriting. A Git patch is included as an alternative; apply only after `git apply --check` succeeds.
3. Your survey JSON files are deliberately not changed. Run the generator against your local questionnaire to keep the included codebook descriptions and current question text in sync:

```powershell
python scripts/generate_codebook.py
python scripts/generate_codebook.py --check
python -m pytest -q
```

4. Commit **all update files** and push to `main`, for example:

```powershell
git add app.py static/app.js static/style.css static/sw.js static/codebook.json static/codebook.csv tests README.md ENUMERATOR-REFERENCE-UPDATE.md
git commit -m "Add offline-safe enumerator IDs and administrator assignments"
git push origin main
```

5. Wait for GitHub Actions to finish deployment and the PythonAnywhere reload. No dependency change, database reset, new administrator or demo seeding is needed. Keep `PYTHONANYWHERE_PROJECT_DIR` at your existing correct app folder.
6. As administrator, complete the new defaults for every existing enumerator account.
7. Have each enumerator reopen the updated app online with their own account, refresh assignments and prepare IDs, then verify offline readiness before departure. Do not clear browser data; old drafts/queues are retained. During migration, prefer coordinating an update after a normal sync where possible.

This changes field assignment/ID behaviour, not the questionnaire's scientific content or its version. The separate app-cache version is refreshed by your normal deployment workflow. Historical questionnaire-version support remains as in the baseline repository.

## Checks

The API suite covers administrator-only defaults, validation, independent counters, idempotent retries, existing formatted references, two concurrent devices, tamper/duplicate rejection, assignment history, deletion without reuse and repeatable database migration. Browser suites cover desktop/mobile forms, readonly defaults, new IDs, refresh/relogin persistence, local deletion without reuse, a repeated late reservation response, simultaneous tabs, a second device, another account on the same installation, offline allocation and exhaustion, changed assignments, older offline drafts and later sync. Tests use isolated temporary databases; no live interviews are changed.

Optional browser commands (Playwright/Chromium required):

```sh
python tests/browser_smoke.py
python tests/browser_revised.py
python tests/browser_reference_ids.py
```

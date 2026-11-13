# Gridfield revised survey upgrade

Source: `Microgrid_Community_Survey_REVISED.docx`, supplied by the project team. Its content is implemented as questionnaire wording, data fields and enumerator guidance, not as instructions to the development agent. This is still labelled a draft for pilot testing and ethics review; the software does not certify an ethics review, engineering study, FPIC process, or tariff approval.

## Apply through GitHub and PythonAnywhere

This update is based on `minna-lproc/microgrid-fieldwork` commit `2aa8591271a3364a03223731f62e58dd42d122d8`. It preserves the existing administrator/field accounts and individual-interview deletion feature. A download does not change the GitHub repository or live PythonAnywhere site by itself.

1. Back up the deployed SQLite database using SQLite's online backup API (or stop the app before copying it and its WAL files). Retain the secret key and existing deployment configuration. Prefer having enumerators sync before a coordinated rollout; earlier queued interviews are still supported if they cannot sync first.
2. Extract the update into your **local Git checkout**. Preserve paths. It contains changed source files and new version/codebook/test files; no production database, accounts, secret key or credentials. If you have additional local edits, use the included Git patch with `git apply --check` and merge conflicts rather than overwriting them.
3. Review the changes, run the tests, and commit and push to `main`. The existing workflow deploys `app.py`, `static/` and `templates/` and requests a reload. Its `PYTHONANYWHERE_PROJECT_DIR` remains `/home/kadlaon/microgrid-fieldwork`. Dependencies have not changed. Include all new files, especially `static/survey-legacy.json`, when committing.
4. Watch GitHub Actions until deployment completes, then open the site online. Application startup adds the new columns and location table and moves legacy dwelling GPS into the location table. This migration is additive and repeatable; it does not relabel old records, reset accounts, or reseed the database.
5. On each phone, close other Gridfield tabs and reopen the app online to install the updated app shell. Wait for offline readiness, then test airplane mode before departure. **Do not clear browser data** if unsynced interviews exist. IndexedDB is upgraded in place and earlier locations are moved to a separate local store.

Typical local commands, after reviewing/copying the update:

```powershell
python -m pytest -q
python scripts/generate_codebook.py --check
git add app.py static survey-source.txt tests scripts/generate_codebook.py .github/workflows/deploy-pythonanywhere.yml README.md REVISED-SURVEY-UPGRADE.md
git commit -m "Implement revised microgrid survey with version-safe offline sync"
git push origin main
```

The optional patch applies to tracked source files. New files are present in the ZIP and must also be copied/staged. A full source ZIP is offered separately for a fresh local installation, not for replacing live server data.

## What changed

- 100 numbered questions A1–L13, plus the household, business, community baseline, facility, stakeholder and observation inventories, using the revised source wording. Parts A–L retain their original IDs; new interviews use `2026-revised-2`.
- Interview metadata: municipality/province, language, authenticated enumerator and start time. Sampling-frame reference, selection method, target sample, household replacement and reason, field notes, and the full sampling/enumerator protocol are available.
- Four independent consent choices: interview/site authorization, GPS, photographs and audio. Refusal ends questioning. An earlier response is never retrospectively assigned photo/audio permission. Permission capture does **not** activate photo/audio recording or uploads: the app has no media-capture, media-attachment, or household-list upload feature. Approved external files can be referred to in notes without embedding private lists in answers.
- B5 total outage hours, B10 power quality, B11 predictability, C4 suppressed demand. Appliance inventory now captures ES/DF/DI load classification, seasonal months, motor/compressor starting current and evidence/source codes.
- Productive-use options and equipment output, operating times, peak/lean output and market access, constraints and daytime scheduling (D5–D8). D1=No removes every remaining business answer, including details and tables.
- Essential loads and emergency supply needs (E6–E7), seasonal income/coping (F8–F9), and separate F10 scenario terms, lifeline threshold and Yes/Depends/No response for all four scenarios. No rates or promises are invented. Project-team terms must be recorded before a scenario response is accepted.
- H8–H12 benefit sharing, jobs, ownership, grievance confidence and accountability. H5 explicitly addresses paid work. IPMR and customary governance, legal/customary/household consent, stakeholder contacts, inclusion and role remuneration are distinct fields in L.
- I4 sampling-list availability, expanded J critical-circuit/source/backup fields, and repeatable named facility-equipment inventories with five rows each (up to 50 groups; add another named table for a large facility).
- K9–K13 seasonal resource gaps, competing/ecological uses, environmental sensitivity/water, cumulative impacts and end-of-life management. The site checklist contains all 15 revised observations, with Yes/No, measured/descriptive value and notes.
- Version-aware administrator detail views and filters. Revised indicators cover power quality/predictability, essential/emergency loads, affordability stress and seasonal income, benefits/ownership, grievances, resources and participation. F10 reports are grouped by exact scenario terms/threshold so different prices are not silently pooled. Descriptive survey responses are not an engineering design or verified financial affordability analysis.
- Standard CSV/JSON exports include questionnaire version, metadata, separate consent choices, structured/new answers and additional details. JSON includes both questionnaire schemas. Codebook downloads are in Settings and are generated from the deployed schema.

## Earlier records and offline phones

`static/survey-legacy.json` archives the questionnaire from the baseline GitHub commit, identified as `2026-pilot-1`. It is cached alongside the revision. Existing local drafts reopen using that earlier schema and original question types; old queued submissions validate against it and retain their version. They do not get new answers or permissions filled in. Old records are visible in the dashboard and exports with their version. New interview starts always use the revised version.

This cannot guarantee that an unversioned historical wording change made before this upgrade is recoverable: the archive reflects the baseline repository's pilot schema. Do not edit that archive to reflect future questionnaires. For a future breaking change, add another preserved schema and explicit registry support rather than replacing the meanings of existing records.

## Dwelling GPS handling

Exact dwelling/site GPS is stored in `survey_locations`, separately from survey answers and informant names. The server migrates existing coordinates out of the old `surveys.location` field and leaves that field null for compatibility. New browser storage similarly separates coordinates into an IndexedDB `locations` store. This is logical separation, not encryption at rest or a separate security principal; use device locks and restricted backups.

The normal dashboard and standard exports contain only a **0.01-degree approximate grid** and a flag that a location exists. It is an approximate grid, not an anonymisation guarantee for a sparsely populated area. Only authenticated administrators can request exact coordinates through the explicit **View restricted exact GPS** control in interview details. That API uses no-store responses. Do not publish precise points, names or stakeholder contacts. Team check-in locations are separate from respondent dwelling consent and remain optional while the app is open.

Deleting an individual interview also deletes its separate GPS entry. Minimal deletion IDs/timestamps remain to prevent delayed sync retries recreating it. Previously downloaded exports, external media and backups are not rewritten by this upgrade or by record deletion.

## Validation and limits

Run:

```sh
python -m pytest -q
python scripts/generate_codebook.py --check
node --check static/app.js
# Optional with Playwright + Chromium installed:
python tests/browser_smoke.py
python tests/browser_revised.py
```

Tests cover questionnaire completeness, numeric/source codes, consent/refusal and replacement rules, all business skips, repeated facility inventories, old-version submissions, additive/idempotent SQLite migration, GPS separation/access/export coarsening and deletion. Browser checks cover household/community/observation collection, new fields, mobile tables, consented GPS, revised reporting, migration of the old one-store IndexedDB, an old queued record and an old draft completed offline and synced later.

The interface is English; recording interview language does not provide an approved translation. Team-specific rates, sampling frames, translations, contact permissions, ethics processes and engineering measurements must come from the project team. Exact GPS and offline answers are not encrypted by the application. No media uploading is introduced. Continue to back up data and test your actual phones before fieldwork.

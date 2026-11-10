# Delete individual submitted interviews

This update is based on `minna-lproc/microgrid-fieldwork` main commit `36481c050afc02e6648da9f8c12c2faf21994c86`. It is prepared and tested; downloading it does not change GitHub or your live PythonAnywhere site.

## Install through your existing automatic deployment

1. Extract the ZIP on Windows.
2. Copy the included `app.py`, `static/` files and `tests/` files into your existing local GitHub repository, preserving paths. If you have edited these same files since the base commit, merge the changes rather than blindly overwriting them. A patch is included as an alternative (see below). The package does not include your survey JSON, database, keys, or account credentials.
3. In your repository's terminal, run:

```powershell
git add app.py static/app.js static/sw.js static/style.css tests/test_app.py tests/browser_smoke.py
git commit -m "Allow administrators to delete individual interviews"
git push origin main
```

4. Wait for the existing PythonAnywhere deployment workflow to finish successfully. Its `PYTHONANYWHERE_PROJECT_DIR` variable should point to `/home/kadlaon/microgrid-fieldwork`, as configured during setup. No dependency install or database reset is needed. The new deletion-metadata table is created automatically when Flask starts.
5. Reopen/refresh the app online. If you still see an old installed PWA screen, close all app windows and reopen it online so the service worker can install the updated app shell. Do not clear browser data if a device has unsynced interviews.

Alternative patch method, from your local Git repository, after placing the included patch there:

```powershell
git apply --check delete-submitted-interviews.patch
git apply delete-submitted-interviews.patch
```

Only apply if `--check` succeeds. If it fails, merge the update with your current files rather than forcing it. Then commit and push the six changed files shown above. The patch does not need to be committed.

## Use it

Sign in as an administrator → Survey responses → open the respondent ID → **Delete interview** → type the displayed respondent ID exactly → **Delete permanently**. **Keep interview**, Escape, or closing the dialog cancels before the final request. An internet connection is required; deletion is not queued offline.

Deleting removes one synced record, including its answers and respondent location, from the active survey table. It disappears from dashboard totals, the enumerator's synced history, and future CSV/JSON exports. Existing downloaded files and backups are not altered. Other interviews and enumerator accounts remain intact.

The server checks administrator permissions, CSRF tokens, and the exact respondent-code confirmation. It records only the deleted UUID, submitting user ID, deleting administrator ID, and deletion timestamp in `survey_deletions`. No answers, GPS coordinates, or respondent code are kept in that table. A later sync retry for that UUID is acknowledged as deleted and cannot recreate the interview; the retrying device removes it from its queue.

## Validation

11 API/deployment tests passed. The Chromium smoke test passed: dashboard and review, cancellation, incorrect confirmation, permanent deletion of the selected record, mobile dialog layout, offline reload, reconnect sync, and role access. The API tests also confirm that exports, counts, and history update, other records remain, and an offline retry does not resurrect a deleted record. No live interviews were deleted during testing; tests used isolated temporary databases.

Changed files: `app.py`, `static/app.js`, `static/style.css`, `static/sw.js`, `tests/test_app.py`, and `tests/browser_smoke.py`.

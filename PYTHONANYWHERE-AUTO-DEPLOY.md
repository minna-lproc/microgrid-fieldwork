# Automatic deployment for kadlaon

Repository: https://github.com/minna-lproc/microgrid-fieldwork
Website: https://kadlaon.pythonanywhere.com
PythonAnywhere service: www.pythonanywhere.com (US)

The included workflow tests pushes to `main`, uploads application files through PythonAnywhere's Files API, and requests a web-app reload. It does not use SSH or depend on an open Bash console. A manual Actions → Run workflow is also available. PythonAnywhere's account quotas and web-app expiry still apply. We cannot verify your account's token/API permissions until you configure and run it.

## One-time setup

1. Confirm the deployed Flask app already works, its packages are installed in the configured virtualenv, and `requirements.txt` exists alongside `app.py` on the server. This workflow does not create a web app or run pip on PythonAnywhere.
2. In PythonAnywhere → Web, note the exact **Source code** path and confirm the WSGI file imports `app.py` from that directory. Do not guess a directory from the GitHub repository name. If the Web tab's source directory is blank or points elsewhere, correct it first. Leave the server's WSGI configuration and DATABASE/SECRET_KEY settings intact.
3. In PythonAnywhere → Account → API Token, create/copy a token. Do not put it in source code, your YAML, a screenshot, a commit, or chat.
4. In the GitHub repository → Settings → Secrets and variables → Actions → Secrets, add a **repository secret** named `PYTHONANYWHERE_API_TOKEN` containing that token.
5. On the **Variables** tab, add a **repository variable** named `PYTHONANYWHERE_PROJECT_DIR` containing the exact source path from step 2, `/home/kadlaon`, the Source code path you supplied. The preflight also requires `app.py` and `requirements.txt` there; if your WSGI file imports them from a subfolder, use that actual folder and update the Web tab Source code field to match.
6. Add these two files to your local GitHub checkout, preserving their paths:
   - `.github/workflows/deploy-pythonanywhere.yml`
   - `scripts/deploy_pythonanywhere.py`
   Also add `tests/test_deployment.py` if you want the deployment safety checks in CI. `PYTHONANYWHERE-AUTO-DEPLOY.md` is this guide.
7. Commit and push the files to `main`. GitHub → Actions → **Test and deploy to PythonAnywhere** shows test and deployment results. The deployment job starts only after the tests pass. You can alternatively trigger it with **Run workflow**.

Example commands in your local repository:

```powershell
git add .github/workflows/deploy-pythonanywhere.yml scripts/deploy_pythonanywhere.py tests/test_deployment.py PYTHONANYWHERE-AUTO-DEPLOY.md
git commit -m "Add tested PythonAnywhere automatic deployment"
git push origin main
```

No account credentials are included in this package. It does not push to GitHub or deploy to PythonAnywhere by itself. The workflow becomes active only once you add these files to your repository and configure the secret and variable.

## Future updates

Edit and test locally, commit, then push to `main`. The workflow deploys only relevant app changes. It can also be triggered manually. Editing a file on your PC without pushing does not publish it. Workflow runs are serialized, with no cancellation of a deployment in progress. Do not edit the live PythonAnywhere source directory while CI is uploading files.

Uploads are deliberately limited to `app.py`, `static/`, and `templates/`, and never traverse symbolic links. `instance/`, SQLite databases, secret keys, `.env`, `.git`, virtualenvs and tests are excluded. Remote files are not deleted. Server WSGI configuration, credentials and existing data remain on the server. Keep `DATABASE` configured to your existing persistent database path and retain regular SQLite online backups.

The deployment changes both matching `gridfield-shell-*` cache names in the uploaded `app.js` and `sw.js` to a per-commit name, so connected phones can receive a new app shell. Offline phones keep their current installed version until reconnecting. This handles static assets only: changing questions, the questionnaire version, the database structure or answer formats still requires a compatibility/migration plan for queued interviews. The current app rejects schema versions it does not recognize; those interviews remain queued for attention.

## Dependency changes

Before uploading anything, deployment compares `requirements.txt` in GitHub with the copy in your configured PythonAnywhere source directory (ignoring line endings and comments). A mismatch stops deployment rather than publishing code against uninstalled packages. To intentionally update dependencies:

1. Back up and plan the update.
2. Update the server's `requirements.txt` from the reviewed new requirements.
3. Run `pip install -r requirements.txt` using the virtualenv configured for the web app.
4. Rerun the workflow for the intended commit.

Do not include database-reset or demo-seeding commands in CI. The workflow never seeds accounts or resets records.

## Failure and rollback

An upload is not an atomic release: if the network fails midway, some files may already have changed. Fix the reported error and rerun the same commit before inviting enumerators to reconnect. The reload is requested only after all file uploads succeed, but an old worker can still serve an updated static file during the upload. Plan deployments between fieldwork sessions where possible. To roll back code, revert the problematic commit and push the revert; databases are not rolled back automatically. A successful reload response means the request was accepted; check the website and PythonAnywhere error log afterwards.

An HTTP 401/403 means token or account API access needs checking; 404 can mean an incorrect source path or domain. Do not paste API response bodies or tokens into public issues. Update GitHub's secret if the token is rotated.

## References

- Official API documentation: https://help.pythonanywhere.com/pages/API/
- Current free-account features: https://help.pythonanywhere.com/pages/FreeAccountsFeatures/

"""Upload app source using PA's API without SSH, a running console, or data resets."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def prepare_files(root, revision):
    """Allowlist app files; never traverse instance/, Git metadata, or secrets."""
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('GITHUB_SHA must be a full Git commit SHA.')
    paths = [root / 'app.py']
    for directory in ['static', 'templates']:
        paths.extend(sorted((root / directory).rglob('*')))
    files = {}
    for path in paths:
        if path.is_symlink():
            raise ValueError('Deployment does not accept symbolic links.')
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if any(p.startswith('.') or p in ['instance', '__pycache__', 'node_modules'] for p in Path(relative).parts):
            continue
        if path.suffix.lower() not in {'.py', '.html', '.css', '.js', '.json', '.webmanifest', '.svg', ".csv", '.png', '.jpg', '.jpeg', '.webp', '.ico', '.woff', '.woff2', '.ttf'}:
            raise ValueError('Review this new deployment file type: ' + relative)
        files[relative] = path.read_bytes()
    # Both files currently use the same cache name. Generate one per commit so
    # returning phones update their offline shell after a successful deployment.
    for name in ['static/app.js', 'static/sw.js']:
        text = files[name].decode('utf-8')
        text, count = re.subn(r'gridfield-shell-[A-Za-z0-9_-]+', 'gridfield-shell-' + revision[:16], text)
        if not count:
            raise ValueError('PWA cache convention changed; review deployment cache handling.')
        files[name] = text.encode('utf-8')
    if 'app.py' not in files or 'templates/index.html' not in files:
        raise ValueError('Missing Flask app or app shell.')
    return files


def requirements_signature(content):
    lines = []
    for line in content.decode('utf-8-sig').splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            lines.append(line)
    return hashlib.sha256('\n'.join(lines).encode()).hexdigest()


def main():
    token = os.environ.get('PYTHONANYWHERE_API_TOKEN', '')
    user = os.environ.get('PYTHONANYWHERE_USERNAME', 'kadlaon')
    host = os.environ.get('PYTHONANYWHERE_HOST', 'www.pythonanywhere.com')
    domain = os.environ.get('PYTHONANYWHERE_DOMAIN', 'kadlaon.pythonanywhere.com')
    project = os.environ.get('PYTHONANYWHERE_PROJECT_DIR', '').rstrip('/')
    revision = os.environ.get('GITHUB_SHA', '')
    if not token:
        raise ValueError('Add the GitHub Actions secret PYTHONANYWHERE_API_TOKEN first.')
    p = PurePosixPath(project)
    if (project != '/home/' + user and not project.startswith('/home/' + user + '/')) or '..' in p.parts or len(p.parts) < 3:
        raise ValueError('Set GitHub variable PYTHONANYWHERE_PROJECT_DIR to the existing application directory under /home/' + user + '/.')
    if host != 'www.pythonanywhere.com' or user != 'kadlaon' or domain != 'kadlaon.pythonanywhere.com':
        raise ValueError('This workflow is configured only for kadlaon on the US PythonAnywhere service.')
    files = prepare_files(ROOT, revision)
    base = 'https://' + host + '/api/v0/user/' + quote(user, safe='')

    def api(method, endpoint, body=None, content_type=None):
        headers = {'Authorization': 'Token ' + token}
        if content_type:
            headers['Content-Type'] = content_type
        request = Request(base + endpoint, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=90) as response:
                return response.read()
        except HTTPError as error:
            # Never print response bodies: they can contain account details.
            raise RuntimeError(f'PythonAnywhere returned HTTP {error.code} for {method} {endpoint}. Check account API access, source path, quota, and token.') from None
        except URLError:
            raise RuntimeError('Could not connect to the PythonAnywhere API. No further files were uploaded.') from None

    def file_endpoint(relative):
        return '/files/path' + quote(project + '/' + relative, safe='/')

    # Read-only preflight: fail before any writes if domain or dependencies differ.
    config = json.loads(api('GET', '/webapps/' + quote(domain, safe='') + '/'))
    configured_source = str(config.get('source_directory') or '').rstrip('/')
    if configured_source and configured_source != project:
        raise ValueError('The web app Source code directory differs from PYTHONANYWHERE_PROJECT_DIR. Confirm the directory used by your WSGI configuration before deploying.')
    server_app = api('GET', file_endpoint('app.py'))
    if b'def create_app(' not in server_app or b'Flask(' not in server_app:
        raise ValueError('The configured directory does not contain the expected Flask app.py. Check the project path used by the server WSGI configuration. No files were uploaded.')
    remote_requirements = api('GET', file_endpoint('requirements.txt'))
    if requirements_signature(remote_requirements) != requirements_signature((ROOT / 'requirements.txt').read_bytes()):
        raise ValueError('requirements.txt differs on the server. Install the new requirements in the app virtualenv, update the server requirements.txt, then rerun. No app files were uploaded.')
    print('Preflight passed. Uploading allowlisted app files; databases and secrets are excluded.')
    # App code last; retain files not in this deployment rather than deleting them.
    order = sorted(files, key=lambda name: (name == 'app.py', name == 'static/sw.js', name))
    for relative in order:
        boundary = 'gridfield-' + revision
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="content"; filename="upload"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + files[relative] + f'\r\n--{boundary}--\r\n'.encode())
        api('POST', file_endpoint(relative), body, 'multipart/form-data; boundary=' + boundary)
        print('Uploaded ' + relative)
    api('POST', '/webapps/' + quote(domain, safe='') + '/reload/', b'')
    print('Reload request accepted for https://' + domain + ' at commit ' + revision)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, KeyError, OSError) as error:
        print('Deployment stopped: ' + str(error), file=sys.stderr)
        sys.exit(1)

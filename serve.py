#!/usr/bin/env python3
"""Local OpenSpec Workbench with persistent Git connections."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse, hashlib, json, os, secrets, subprocess, threading
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('OPENSPEC_WORKBENCH_DATA', str(Path.home() / '.openspec-workbench'))).expanduser()
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.RLock()

def git(args, cwd=None):
    try:
        result = subprocess.run(['git', '-c', 'core.hooksPath=', *args], cwd=cwd,
            capture_output=True, text=True, timeout=90,
            env={**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GIT_SSH_COMMAND': 'ssh -o BatchMode=yes'})
    except FileNotFoundError:
        raise ValueError('Git is not installed. Install Git and restart the app.')
    except subprocess.TimeoutExpired:
        raise ValueError('Git timed out. Check network access and Git authentication in your terminal.')
    if result.returncode:
        raise ValueError('Git operation failed. Check the URL and branch, and authenticate using your Git credential helper or SSH key in your terminal. For Pull, commit or stash local changes first. No password or token should be entered in the URL.')
    return result.stdout.strip()

def read_specs(base):
    base = Path(base).resolve()
    spec = base / 'openspec'
    if not spec.is_dir() or spec.is_symlink():
        raise ValueError('No regular openspec folder found at the repository root.')
    files = []
    for path in sorted(spec.rglob('*.md')):
        if not path.resolve().is_relative_to(spec.resolve()):
            continue
        if any(p.is_symlink() for p in [path, *path.parents] if p != base and p.is_relative_to(base)):
            continue
        if len(files) >= 400 or path.stat().st_size > 1_000_000:
            raise ValueError('OpenSpec limit: 400 Markdown files, up to 1 MB each.')
        files.append({'name': path.name, 'path': path.parent.relative_to(base).as_posix(), 'content': path.read_text(encoding='utf-8'), 'repoFile': True})
    return files

def registry():
    p = DATA / 'connections.json'
    return json.loads(p.read_text()) if p.exists() else {}

def connection_info(identifier, item):
    base = Path(item['folder'])
    return {'id': identifier, 'source': item['source'], 'folder': str(base), 'branch': git(['branch', '--show-current'], base), 'managed': item['managed']}

def connect(source, branch=''):
    if branch.startswith('-') or len(branch) > 200:
        raise ValueError('Invalid branch name.')
    remote = source.startswith(('https://', 'ssh://', 'git@'))
    if remote:
        if source.startswith('https://'):
            url = urlparse(source)
            if not url.hostname or url.username or url.password or url.query or url.fragment:
                raise ValueError('Use a repository URL without embedded credentials, query, or fragment.')
        elif source.startswith('ssh://'):
            url = urlparse(source)
            if not url.hostname or url.password or url.query or url.fragment:
                raise ValueError('Invalid SSH repository URL.')
        identifier = hashlib.sha256((source + '\n' + branch).encode()).hexdigest()[:24]
        base = DATA / 'repos' / identifier
        if not base.exists():
            base.parent.mkdir(parents=True, exist_ok=True)
            args = ['clone']
            if branch:
                args += ['--branch', branch, '--single-branch']
            try:
                git([*args, '--', source, str(base)])
            except ValueError:
                import shutil
                if base.exists():
                    shutil.rmtree(base)
                raise
    else:
        base = Path(source).expanduser().resolve()
        if not (base / '.git').exists():
            raise ValueError('Choose the root folder of an existing Git checkout.')
        identifier = hashlib.sha256(str(base).encode()).hexdigest()[:24]
    files = read_specs(base)
    item = {'folder': str(base), 'source': source, 'managed': remote}
    info = connection_info(identifier, item)
    DATA.mkdir(parents=True, exist_ok=True)
    entries = registry()
    entries[identifier] = item
    temporary = DATA / 'connections.tmp'
    temporary.write_text(json.dumps(entries))
    temporary.replace(DATA / 'connections.json')
    return {'connection': info, 'files': files}

def operate(data, action):
    identifier = data.get('connectionId')
    item = registry().get(identifier)
    if not item:
        raise ValueError('Connection not found on this computer. Reconnect the repository.')
    base = Path(item['folder']).resolve()
    if action == 'pull':
        if git(['status', '--porcelain'], base):
            raise ValueError('Commit or stash local changes before pulling. Refresh can still read your working files.')
        git(['pull', '--ff-only'], base)
    if action == 'write':
        relative = Path(data.get('path', ''))
        target = base / relative
        if relative.is_absolute() or '..' in relative.parts or not relative.parts or relative.parts[0] != 'openspec' or relative.suffix != '.md':
            raise ValueError('Only existing Markdown files inside openspec can be saved.')
        if not target.resolve().is_relative_to(base / 'openspec') or any(p.is_symlink() for p in [target, *target.parents] if p.is_relative_to(base)):
            raise ValueError('Symlink paths cannot be edited.')
        original = target.read_text(encoding='utf-8')
        if original != data.get('original'):
            raise ValueError('This file changed on disk. Refresh before editing to avoid overwriting changes.')
        content = data.get('content')
        if not isinstance(content, str) or len(content.encode()) > 1_000_000:
            raise ValueError('Invalid file content or file exceeds 1 MB.')
        target.write_text(content, encoding='utf-8')
    return {'connection': connection_info(identifier, item), 'files': read_specs(base)}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)
    def valid_host(self):
        return self.headers.get('Host') in {f'localhost:{self.server.server_port}', f'127.0.0.1:{self.server.server_port}'}
    def reply(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def do_GET(self):
        if not self.valid_host():
            return self.reply(403, {'error': 'Invalid host'})
        if self.path == '/api/session':
            return self.reply(200, {'token': TOKEN})
        return super().do_GET()
    def do_POST(self):
        origin = self.headers.get('Origin')
        if not self.valid_host() or self.headers.get('X-Workspace-Token') != TOKEN or origin not in {None, f'http://{self.headers.get("Host")}'}:
            return self.reply(403, {'error': 'Unauthorized request'})
        endpoints = {'/api/connect-git': 'connect', '/api/refresh-git': 'refresh', '/api/pull-git': 'pull', '/api/write-git': 'write'}
        action = endpoints.get(self.path)
        if not action:
            return self.reply(404, {'error': 'Unknown endpoint'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size < 1 or size > 8_000_000:
                raise ValueError('Invalid request size')
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError('Invalid request')
            with LOCK:
                if action == 'connect':
                    source, branch = data.get('source', '').strip(), data.get('branch', '').strip()
                    if not source:
                        raise ValueError('Enter a Git URL or checkout folder.')
                    result = connect(source, branch)
                else:
                    result = operate(data, action)
            self.reply(200, result)
        except (ValueError, OSError, TypeError, AttributeError) as error:
            self.reply(400, {'error': str(error)})

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    except OSError as error:
        parser.exit(1, f'Could not start: {error}\nTry --port 8766\n')
    print(f'Open http://localhost:{args.port} in your browser.\nPress Ctrl+C to stop.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
    finally:
        server.server_close()

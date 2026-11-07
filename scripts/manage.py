"""Cross-platform project commands, without changing PowerShell execution policy."""
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(args, cwd=ROOT):
    result = subprocess.run(args, cwd=cwd, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)


def python_executable():
    for candidate in [ROOT / '.venv/Scripts/python.exe', ROOT / '.venv/bin/python', ROOT / '.tools/python/tools/python.exe']:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def setup():
    target = ROOT / '.env'
    if not target.exists():
        content = (ROOT / '.env.example').read_text(encoding='utf-8')
        for key in ['POSTGRES_PASSWORD', 'MONGO_PASSWORD', 'RABBIT_PASSWORD', 'S3_SECRET_KEY', 'JWT_SECRET', 'INTERNAL_SECRET']:
            content = re.sub(r'^' + key + r'=.*$', key + '=' + secrets.token_hex(24), content, flags=re.MULTILINE)
        target.write_text(content, encoding='utf-8')
        print('Created .env with project-specific secrets. Demo password: see DEMO_PASSWORD.', flush=True)
    require_docker()
    run(['docker', 'compose', 'config', '--quiet'])
    run(['docker', 'compose', 'up', '--build', '-d', '--wait', '--wait-timeout', '240'])
    print('Central: http://localhost:8080 | DONG: 8101 | TAY: 8102 | NAM: 8103 | BAC: 8104')


def require_docker():
    if not shutil.which('docker'):
        raise SystemExit('Docker is not installed or not on PATH. Install/start Docker Desktop with Linux containers, then rerun this command.')


def check():
    # Keep pytest away from stale/locked directories in the shared Windows temp folder.
    test_root = (ROOT / '.tools').resolve()
    if not test_root.is_relative_to(ROOT.resolve()):
        raise SystemExit('Test temporary files must stay inside the project workspace.')
    test_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pytest-', dir=test_root) as test_tmp:
        run([python_executable(), '-X', 'utf8', '-m', 'pytest', '-q', '--basetemp', test_tmp], ROOT / 'backend')
    npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
    if not npm:
        raise SystemExit('Node.js/npm is required for the frontend build.')
    run([npm, 'run', 'test:preview'], ROOT / 'frontend')
    run([npm, 'run', 'build'], ROOT / 'frontend')


def preview():
    npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
    if not npm:
        raise SystemExit('Install Node.js 22.18+ or 24 first, then rerun this command.')
    if not (ROOT / 'frontend/node_modules/vite/bin/vite.js').exists():
        raise SystemExit('Frontend dependencies are missing. Run: cd frontend, then npm.cmd ci on Windows (npm ci on other systems).')
    print('UI preview only: http://127.0.0.1:5173 | admin / ToyChainDemo2026! | Ctrl+C to stop', flush=True)
    try:
        run([npm, 'run', 'preview:ui'], ROOT / 'frontend')
    except KeyboardInterrupt:
        print('\nPreview stopped.')


def integration():
    require_docker()
    run(['docker', 'compose', 'exec', '-T', 'api-central', 'python', '-m', 'integration.scenario'])
    # Stop/start the entire cluster without removing containers or named volumes.
    # This includes the databases, RabbitMQ and S3, not only the branch processes.
    run(['docker', 'compose', 'stop'])
    run(['docker', 'compose', 'up', '-d', '--wait', '--wait-timeout', '240'])
    run(['docker', 'compose', 'exec', '-T', 'api-central', 'python', '-m', 'integration.scenario', '--check-persistence'])


if __name__ == '__main__':
    commands = {'setup': setup, 'check': check, 'preview': preview, 'integration': integration}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        raise SystemExit('Usage: python scripts/manage.py {setup|check|preview|integration}')
    commands[sys.argv[1]]()

"""Start the MCP with an isolated environment; never install during MCP startup."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from runtime import APP_DIR

ROOT = Path(__file__).resolve().parent
MODULES = ('mcp', 'requests', 'playwright', 'faster_whisper', 'av')


def environment_python(directory):
    return directory / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def missing_modules(python):
    probe = ('import importlib.util,json; print(json.dumps([m for m in '
             + repr(MODULES) + ' if importlib.util.find_spec(m) is None]))')
    result = subprocess.run([str(python), '-I', '-c', probe], check=True,
                            capture_output=True, text=True, timeout=30)
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--setup', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    installed = ROOT / '.runtime'
    if not environment_python(installed).is_file():
        installed = ROOT.parent.parent / '.runtime'
    default = installed if environment_python(installed).is_file() else APP_DIR / 'venv'
    directory = Path(os.environ.get('SSU_LMS_ENV', str(default)))
    python = environment_python(directory)
    if args.setup:
        subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(directory)], check=True)
        # The bundled Python's ensurepip subprocess can fail inside the host sandbox.
        import importlib.util
        if importlib.util.find_spec('pip') is not None:
            pip = [sys.executable, '-m', 'pip', '--python', str(python)]
        else:
            subprocess.run([str(python), '-m', 'ensurepip', '--upgrade'], check=True)
            pip = [str(python), '-m', 'pip']
        subprocess.run(pip + ['install', '--disable-pip-version-check', '--retries', '1',
                             '--timeout', '15', '-r', str(ROOT / 'requirements.txt')],
                       check=True, stdout=sys.stderr)
    selected = python if python.is_file() else Path(sys.executable)
    missing = missing_modules(selected)
    if args.check:
        print(json.dumps({'python': str(selected), 'missing_modules': missing,
                          'ready': not missing}, ensure_ascii=False))
        return 1 if missing else 0
    if missing:
        print('Missing packages: ' + ', '.join(missing)
              + '. Run start.ps1 -Setup first (Internet access required).', file=sys.stderr)
        return 1
    return subprocess.call([str(selected), '-u', str(ROOT / 'server.py')], cwd=ROOT)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        print('LMS startup/setup failed: ' + str(error), file=sys.stderr)
        sys.exit(1)

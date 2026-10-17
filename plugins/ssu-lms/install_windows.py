"""Configure the Windows plugin using a verified Python, without Node or PATH edits."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

MODULES = ('mcp', 'requests', 'playwright', 'faster_whisper', 'av')

def configuration(root, python):
    root, python = Path(root).resolve(), Path(python).resolve()
    if not (root/'server.py').is_file() or not python.is_file():
        raise ValueError('Plugin server or Python executable is missing.')
    return {'mcpServers':{'ssu-lms':{'type':'stdio','command':str(python),
        'args':['-u',str(root/'server.py')],'cwd':str(root)}}}

def configure(root, config):
    for name in ('.mcp.json','mcp.json'):
        target = root/name
        backup = root/(name+'.before-windows-setup')
        if target.exists() and not backup.exists():
            backup.write_bytes(target.read_bytes())
        temporary = target.with_name(target.name+'.new')
        temporary.write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
        temporary.replace(target)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plugin-root',type=Path)
    parser.add_argument('--configure',action='store_true')
    args=parser.parse_args()
    here=Path(__file__).resolve().parent
    root=args.plugin_root or (here/'plugins/ssu-lms' if (here/'plugins/ssu-lms/server.py').is_file() else here)
    config=configuration(root,sys.executable)
    probe='import importlib.util,json;print(json.dumps([m for m in '+repr(MODULES)+' if importlib.util.find_spec(m) is None]))'
    result=subprocess.run([sys.executable,'-I','-c',probe],check=True,capture_output=True,text=True,timeout=30)
    missing=json.loads(result.stdout)
    report={'python':sys.executable,'plugin_root':str(root),'missing_modules':missing,
            'ready':not missing,'configured':False,'live_mcp_verified':False}
    if args.configure and not missing:
        configure(root,config)
        report['configured']=True
    print(json.dumps(report,ensure_ascii=True))
    return 1 if missing else 0

if __name__=='__main__':
    try:
        sys.exit(main())
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        print('Windows configuration failed: '+type(error).__name__,file=sys.stderr)
        sys.exit(1)

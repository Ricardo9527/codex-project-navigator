"""Install the user-owned library manager; launchd restarts it after a crash."""
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LABEL = 'local.codex.project-library'
DESTINATION = Path.home()/'Library/LaunchAgents'/f'{LABEL}.plist'
domain = f'gui/{os.getuid()}'
target = f'{domain}/{LABEL}'

if '--uninstall' in sys.argv:
    loaded = subprocess.run(['launchctl', 'print', target], capture_output=True).returncode == 0
    if loaded:
        subprocess.run(['launchctl', 'bootout', target], check=True)
    DESTINATION.unlink(missing_ok=True)
    print('已移除自动接入；资料库数据保留在项目 data 目录。')
else:
    node = shutil.which('node') or '/opt/homebrew/bin/node'
    if not Path(node).is_file():
        raise RuntimeError('未找到 Node.js。')
    (ROOT/'data/logs').mkdir(parents=True, exist_ok=True)
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    config = dict(Label=LABEL, ProgramArguments=[node,str(ROOT/'scripts/manager.mjs')],
                  WorkingDirectory=str(ROOT),RunAtLoad=True,KeepAlive=True,ThrottleInterval=5,
                  EnvironmentVariables={'PROJECT_HUB_PYTHON':sys.executable},
                  StandardOutPath=str(ROOT/'data/logs/manager.log'),
                  StandardErrorPath=str(ROOT/'data/logs/error.log'))
    payload=plistlib.dumps(config)
    changed=not DESTINATION.exists() or DESTINATION.read_bytes()!=payload
    if changed:
        DESTINATION.write_bytes(payload)
    loaded=subprocess.run(['launchctl','print',target],capture_output=True).returncode==0
    if loaded and changed:
        subprocess.run(['launchctl','bootout',target],check=True);loaded=False
    if not loaded:
        subprocess.run(['launchctl','bootstrap',domain,str(DESTINATION)],check=True)
    print('资料库自动接入已启用。')

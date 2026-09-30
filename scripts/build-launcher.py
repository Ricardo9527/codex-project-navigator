"""Build the local macOS launcher using the installed Codex icon."""
from pathlib import Path
import plistlib
import json
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / 'Codex 资料库.app'
runtime = json.loads((ROOT/'data/install.json').read_text())
app_info=plistlib.loads((Path(runtime['app'])/'Contents/Info.plist').read_bytes())
icon_name=app_info['CFBundleIconFile']
ICON = Path(runtime['app'])/'Contents/Resources'/(icon_name if icon_name.endswith('.icns') else icon_name+'.icns')
if not ICON.is_file():
    raise SystemExit(f'找不到 Codex 图标：{ICON}')

with tempfile.TemporaryDirectory(prefix='codex-library-launcher-') as temporary:
    stage = Path(temporary)
    bundle = stage / APP.name
    source = stage/'launcher.applescript'
    node = runtime['node'].replace('\\', '\\\\').replace(chr(34), '\\'+chr(34))
    source.write_text((ROOT/'scripts/launcher.applescript').read_text().replace('__NODE_PATH__',node))
    subprocess.run(['osacompile', '-o', str(bundle), str(source)], check=True)
    shutil.copy2(ICON,bundle/'Contents/Resources/library.icns')
    info = bundle / 'Contents/Info.plist'
    metadata = plistlib.loads(info.read_bytes())
    metadata.update(CFBundleIdentifier='local.codex.project-library.launcher', CFBundleName='Codex 资料库', CFBundleDisplayName='Codex 资料库', CFBundleIconFile='library.icns')
    metadata.pop('CFBundleIconName', None)
    info.write_bytes(plistlib.dumps(metadata))
    subprocess.run(['codesign', '--force', '--sign', '-', str(bundle)], check=True)
    shutil.copytree(bundle, APP, dirs_exist_ok=True)
APP.touch()
print(f'已构建：{APP}')

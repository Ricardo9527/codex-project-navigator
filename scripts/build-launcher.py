"""Build the local macOS launcher using the installed Codex icon."""
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / 'Codex 资料库.app'
ICON = Path('/Applications/ChatGPT.app/Contents/Resources/icon-codex-dark-color.png')
if not ICON.is_file():
    raise SystemExit(f'找不到 Codex 图标：{ICON}')

with tempfile.TemporaryDirectory(prefix='codex-library-launcher-') as temporary:
    stage = Path(temporary)
    bundle = stage / APP.name
    subprocess.run(['osacompile', '-o', str(bundle), str(ROOT / 'scripts/launcher.applescript')], check=True)
    iconset = stage / 'library.iconset'
    iconset.mkdir()
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            suffix = '@2x' if scale == 2 else ''
            destination = iconset / f'icon_{size}x{size}{suffix}.png'
            subprocess.run(['sips', '-z', str(size * scale), str(size * scale), str(ICON), '--out', str(destination)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(['iconutil', '-c', 'icns', str(iconset), '-o', str(bundle / 'Contents/Resources/library.icns')], check=True)
    info = bundle / 'Contents/Info.plist'
    metadata = plistlib.loads(info.read_bytes())
    metadata.update(CFBundleIdentifier='local.codex.project-library.launcher', CFBundleName='Codex 资料库', CFBundleDisplayName='Codex 资料库', CFBundleIconFile='library.icns')
    metadata.pop('CFBundleIconName', None)
    info.write_bytes(plistlib.dumps(metadata))
    subprocess.run(['codesign', '--force', '--sign', '-', str(bundle)], check=True)
    shutil.copytree(bundle, APP, dirs_exist_ok=True)
APP.touch()
print(f'已构建：{APP}')

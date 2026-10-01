"""Build the macOS launcher and its bundled Dock animation."""
from pathlib import Path
import argparse
import json
import plistlib
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=ROOT / 'Codex 资料库.app')
args = parser.parse_args()
app = args.output.resolve()
runtime = json.loads((ROOT/'data/install.json').read_text())
assets = ROOT / 'assets/launcher'
manifest = json.loads((assets / 'animation.json').read_text())
for index in range(manifest['frameCount']):
    frame = assets / 'frames' / f'frame-{index:03d}.png'
    if not frame.is_file():
        raise SystemExit(f'缺少动画帧：{frame}')

with tempfile.TemporaryDirectory(prefix='codex-library-launcher-') as temporary:
    stage = Path(temporary)
    bundle = stage / app.name
    contents = bundle / 'Contents'
    resources = contents / 'Resources'
    executable = contents / 'MacOS/launcher'
    executable.parent.mkdir(parents=True)
    resources.mkdir(parents=True)
    subprocess.run(['swiftc', '-O', '-module-cache-path', str(stage / 'module-cache'), str(ROOT / 'scripts/launcher.swift'), '-o', str(executable)], check=True)
    shutil.copytree(assets / 'frames', resources / 'frames')
    shutil.copy2(assets / 'animation.json', resources / 'animation.json')
    iconset = stage / 'library.iconset'
    iconset.mkdir()
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            suffix = '@2x' if scale == 2 else ''
            destination = iconset / f'icon_{size}x{size}{suffix}.png'
            subprocess.run(['sips', '-z', str(size * scale), str(size * scale), str(assets / 'frames/frame-000.png'), '--out', str(destination)], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(['iconutil', '-c', 'icns', str(iconset), '-o', str(resources / 'library.icns')], check=True)
    metadata = dict(CFBundleIdentifier='local.codex.project-library.launcher', CFBundleName='Codex 资料库', CFBundleDisplayName='Codex 资料库', CFBundleIconFile='library.icns', CFBundleExecutable='launcher', CFBundlePackageType='APPL', CFBundleVersion='2', CFBundleShortVersionString='0.2', LauncherNodePath=runtime['node'], NSHighResolutionCapable=True, LSMinimumSystemVersion='13.0')
    (contents / 'Info.plist').write_bytes(plistlib.dumps(metadata))
    subprocess.run(['codesign', '--force', '--sign', '-', str(bundle)], check=True)
    helper = ROOT / 'data/bin/play-codex-icon'
    helper.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['swiftc', '-O', '-module-cache-path', str(stage / 'module-cache'), str(ROOT / 'scripts/play-codex-icon.swift'), '-o', str(helper)], check=True)
    # Preserve the existing bundle directory so pinned Dock entries keep their path.
    app.mkdir(parents=True, exist_ok=True)
    if (app / 'Contents').exists():
        shutil.rmtree(app / 'Contents')
    shutil.copytree(contents, app / 'Contents')
    setter = stage / 'set-launcher-icon'
    subprocess.run(['swiftc', '-module-cache-path', str(stage / 'module-cache'), str(ROOT / 'scripts/set-launcher-icon.swift'), '-o', str(setter)], check=True)
    subprocess.run([str(setter), str(app), str(assets / 'frames/frame-000.png')], check=True)
app.touch()
print(f'已构建：{app}')

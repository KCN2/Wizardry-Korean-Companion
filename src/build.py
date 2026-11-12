r"""
build.py - Wizardry_Korean_Companion PyInstaller build.

    python build.py            developer exe -> dist\Wizardry_Korean_Companion.exe
    python build.py --release  release exe   -> release\ (exe + README + font license)

The release build sets wiz_build_flags.RELEASE = True while it builds, so the
exe writes no developer logs or memory dumps, then puts the flag file back.
"""

import os
import shutil
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))
build_tools = os.path.join(base_dir, '.build-tools')

if os.path.exists(build_tools):
    sys.path.insert(0, build_tools)

import PyInstaller.__main__

FLAGS = os.path.join(base_dir, 'wiz_build_flags.py')
RELEASE_DOCS = os.path.join(base_dir, 'docs', 'release')


def build(release):
    spec_path = os.path.join(base_dir, 'Wizardry_Korean_Companion.spec')
    args = [spec_path, '--noconfirm']
    if release:
        args += ['--distpath', os.path.join(base_dir, 'release'),
                 '--workpath', os.path.join(base_dir, 'build', 'release')]
    print(f"[*] PyInstaller {'release ' if release else ''}build: {spec_path}")
    PyInstaller.__main__.run(args)


if __name__ == '__main__':
    if '--release' not in sys.argv:
        build(False)
        sys.exit(0)
    with open(FLAGS, encoding='utf-8') as f:
        original = f.read()
    try:
        with open(FLAGS, 'w', encoding='utf-8') as f:
            f.write(original.replace('RELEASE = False', 'RELEASE = True'))
        build(True)
    finally:
        with open(FLAGS, 'w', encoding='utf-8') as f:
            f.write(original)
    out = os.path.join(base_dir, 'release')
    # A test run of the release exe leaves its settings (local paths) and map
    # records here; the package holds only the exe and the release documents.
    keep = {'Wizardry_Korean_Companion.exe', *os.listdir(RELEASE_DOCS)}
    for name in os.listdir(out):
        path = os.path.join(out, name)
        if name not in keep and os.path.isfile(path):
            os.remove(path)
            print(f"[*] Removed from the package: {name}")
    for name in os.listdir(RELEASE_DOCS):
        shutil.copy2(os.path.join(RELEASE_DOCS, name), os.path.join(out, name))
    print(f"[*] Release files: {out}")

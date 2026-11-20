#!/usr/bin/env python3
"""Build a ZIP for the current operating system using PyInstaller."""
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = 'PowerballGenerator'
SYSTEM = platform.system()
if SYSTEM not in ('Darwin', 'Windows'):
    raise SystemExit('Build macOS packages on macOS and Windows packages on Windows.')
command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed', '--onedir', '--name', NAME]
if SYSTEM == 'Darwin':
    command += ['--osx-bundle-identifier', 'com.powerballgenerator.app']
command += ['powerball_generator.py']
subprocess.run(command, cwd=ROOT, check=True)
dist = ROOT / 'dist'
package = dist / (NAME + '.app' if SYSTEM == 'Darwin' else NAME)
if SYSTEM == 'Darwin':
    archive = dist / (NAME + '-macOS.zip')
    subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(package), str(archive)], check=True)
else:
    archive = Path(shutil.make_archive(str(dist / (NAME + '-Windows')), 'zip', dist, package.name))
print(f'Created {archive}')

#!/usr/bin/env python3
"""Restore pinned upstream repositories and the workspace's saved changes."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check existing dependencies without changing files')
    args = parser.parse_args()
    lock = json.loads((ROOT / 'dependencies/lock.json').read_text())
    # Check existing repositories before making any changes.
    for name, spec in lock.items():
        repo = ROOT / name
        if repo.exists():
            if git(repo, 'rev-parse', '--show-toplevel') != str(repo):
                raise SystemExit(f'{repo}: expected a separate dependency repository')
            if git(repo, 'rev-parse', 'HEAD') != spec['commit']:
                raise SystemExit(f'{repo}: unexpected commit; preserve your changes before restoring')
        elif args.check:
            raise SystemExit(f'Missing dependency: {name}')
        for rel, expected in spec['overlays'].items():
            saved = ROOT / 'dependencies/overlays' / name / rel
            if hashlib.sha256(saved.read_bytes()).hexdigest() != expected:
                raise SystemExit(f'Saved overlay checksum mismatch: {saved}')
            dest = repo / rel
            if dest.exists() and dest.read_bytes() != saved.read_bytes():
                # Replacing the original tracked file is expected on a fresh clone.
                original = subprocess.run(['git', '-C', str(repo), 'show', f"{spec['commit']}:{rel}"], capture_output=True)
                if args.check or original.returncode or dest.read_bytes() != original.stdout:
                    raise SystemExit(f'{dest}: has additional local changes; refusing to overwrite')
            elif args.check and not dest.exists():
                raise SystemExit(f'Missing overlay: {dest}')
    for name, spec in lock.items():
        repo = ROOT / name
        if not repo.exists():
            subprocess.run(['git', 'clone', '--filter=blob:none', '--no-checkout', spec['url'], str(repo)], check=True)
            subprocess.run(['git', '-C', str(repo), 'checkout', '--detach', spec['commit']], check=True)
        if not args.check:
            for rel in spec['overlays']:
                dest = repo / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / 'dependencies/overlays' / name / rel, dest)
        print(f"{name}: {spec['commit']} ({len(spec['overlays'])} local files)")


if __name__ == '__main__':
    main()

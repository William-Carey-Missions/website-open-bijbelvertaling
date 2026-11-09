"""Install explicit public audio release packages; never delete existing audio."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import urllib.request


def command(args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def build_chapter(task):
    root, edition, book, chapter, files = task
    number = chapter['number']
    directory = root / edition / book
    concat = directory / f'{number}-m.concat.txt'
    concat.write_text('\n'.join("file '" + str(root / f['path']).replace("'", "'\\''") + "'" for f in files))
    pending = directory / f'{number}-m.pending.mp3'
    command(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(concat), '-c:a', 'copy', str(pending)])
    info = json.loads(command(['ffprobe', '-v', 'error', '-show_format', '-of', 'json', str(pending)]))
    expected = sum(f['seconds'] for f in files)
    if abs(float(info['format']['duration']) - expected) > .25:
        raise RuntimeError(f'Chapter duration mismatch: {edition}/{book}/{number}')
    pending.replace(directory / f'{number}-m.mp3')
    elapsed, timing = 0, []
    for f in files:
        timing.append({'v': f['verse'], 't': round(elapsed, 3)})
        elapsed += f['seconds']
    (directory / f'{number}-m.json').write_text(json.dumps(timing))
    concat.unlink()
    return edition, book, number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets-json', required=True, type=Path)
    parser.add_argument('--root', required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    assets = json.loads(args.assets_json.read_text())
    packages = []
    count = 0
    for asset in assets:
        if not asset['name'].endswith('.tar'):
            continue
        if not re.fullmatch(r'(nl-ov|nl-et-basis|nl-opv)-[a-z0-9]+\.tar', asset['name']):
            raise ValueError('Unexpected package name')
        url = asset['browser_download_url']
        if not url.startswith('https://github.com/William-Carey-Missions/website-open-bijbelvertaling/releases/download/higgs-audio-'):
            raise ValueError('Unexpected asset URL')
        print('Download:', asset['name'], flush=True)
        manifest = None
        with urllib.request.urlopen(url, timeout=120) as response:
            with tarfile.open(fileobj=response, mode='r|') as archive:
                for member in archive:
                    path = PurePosixPath(member.name)
                    if not member.isfile() or path.is_absolute() or '..' in path.parts or not re.fullmatch(r'(nl-ov|nl-et-basis|nl-opv)/[a-z0-9]+/(?:\d+/m/v\d+\.mp3|_manifest\.json)', member.name):
                        raise ValueError('Invalid archive member')
                    target = root / member.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    data = archive.extractfile(member).read()
                    if target.name == '_manifest.json':
                        manifest = json.loads(data)
                    pending = target.with_suffix(target.suffix + '.pending')
                    pending.write_bytes(data)
                    pending.replace(target)
        if manifest is None:
            raise ValueError('Missing book manifest')
        for file in manifest['files']:
            target = root / file['path']
            if target.stat().st_size != file['bytes'] or hashlib.sha256(target.read_bytes()).hexdigest() != file['sha256']:
                raise RuntimeError('Audio checksum mismatch: ' + file['path'])
        count += len(manifest['files'])
        packages.append(manifest)
        print('Verified:', len(manifest['files']), 'verses', flush=True)
    tasks = []
    for package in packages:
        for chapter in package['chapters']:
            if chapter['complete']:
                files = sorted([f for f in package['files'] if f['chapter'] == chapter['number']], key=lambda f: f['verse'])
                tasks.append((root, package['edition'], package['book'], chapter, files))
    catalog = {'credit': 'BosonAI Higgs TTS 3', 'verseCount': count, 'editions': {}}
    with ThreadPoolExecutor(max_workers=4) as executor:
        for edition, book, number in executor.map(build_chapter, tasks):
            catalog['editions'].setdefault(edition, {}).setdefault(book, {}).setdefault('m', []).append(number)
    catalog['chapterCount'] = len(tasks)
    pending = root / 'catalogus.pending.json'
    pending.write_text(json.dumps(catalog, ensure_ascii=False, separators=(',', ':')))
    pending.replace(root / 'catalogus.json')
    (root / 'audiocredit.txt').write_text('AI-voorlezing met BosonAI Higgs TTS 3. Open Vertaling, Open Parafrase Weergave en afzonderlijke Ethiopische basisvertaling.\n')
    print('PUBLISHED:', count, 'verses;', len(tasks), 'complete chapters', flush=True)


if __name__ == '__main__':
    main()

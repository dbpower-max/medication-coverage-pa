"""Prevent new interface releases from reusing an older cached clinical dataset."""
import gzip
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / '_site'
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()[:12]
script = (root / 'app.js').read_text()
assert f"fetch('./data.json.gz?v={digest(root / 'data.json.gz')}')" in script
html = (root / 'index.html').read_text()
for name in ('app.js', 'styles.css'):
    assert './' + name + '?v=' + digest(root / name) in html
data = json.loads(gzip.decompress((root / 'data.json.gz').read_bytes()))
for url in data.get('planDataFiles', {}).values():
    path, version = url.split('?v=')
    assert version == digest(root / path.removeprefix('./'))
print('PASS: interface, main clinical data and lazy plan data use matching content hashes')

"""NLM names must retain exact product identity and every source attribute."""
import copy
import gzip
import json
import re
from pathlib import Path
from rxnorm_display_names import attach_rxnorm_display_names, canonical_name

root = Path(__file__).resolve().parents[1]
data = json.loads(gzip.decompress((root / '_site/data.json.gz').read_bytes()))
registry = json.loads(gzip.decompress((root / 'tools/reference/rxnorm_names_202611.json.gz').read_bytes()))
rows = [r for r in data['medications'] if r.get('rxnormId')]
assert len(rows) == 4454
assert data['medicationNamingInfo']['matched'] == 4451
assert data['medicationNamingInfo']['psns'] == 4447
assert data['medicationNamingInfo']['structuredFallbacks'] == 4
assert set(data['medicationNamingInfo']['unmatchedIds']) == {'1251398', '210072', '210140'}
packs = 0
for row in rows:
    reference = registry['names'].get(row['rxnormId'])
    if not reference:
        assert not row.get('standardName'), 'Unverified name mapping invented'
        continue
    assert row['standardNameProvenance']['rxcui'] == row['rxnormId']
    assert canonical_name(row['name']) == canonical_name(reference['fullName'])
    assert row['standardName'] and row['standardName'] != 'NA'
    assert not re.match(r'^\d', row['standardName']), 'A quantity still precedes the drug name'
    if row['standardNameType'] == 'RxNorm PSN':
        assert row['standardName'] == reference['psn'], 'PSN was rewritten heuristically'
    else:
        assert row['standardName'].startswith(reference['displayName'])
    if row['name'].startswith('{'):
        packs += 1
        assert not re.search(r'[{}\[\]]|\d{7,}', row['standardName']), 'Raw package syntax/concentration remains in title'
assert packs == 375
by_id = {r['rxnormId']:r for r in rows}
assert by_id['314006']['standardName'] == 'glipiZIDE 5 MG 24HR Extended Release Oral Tablet'
assert by_id['2272630']['standardName'] == 'VALTOCO 5 MG Dose Kit'
assert by_id['2630863']['standardName'] == 'ZOLGENSMA KIT 19.6 - 20.0 KG (Pack)'
assert by_id['2634817']['standardName'].startswith('Acetaminophen/')
# Attaching names must never modify names, IDs, PA, preference, source, etc.
original = copy.deepcopy(data)
for row in original['medications']:
    for key in ('standardName', 'standardNameType', 'standardNameProvenance'):
        row.pop(key, None)
original.pop('medicationNamingInfo', None)
decorated = copy.deepcopy(original)
attach_rxnorm_display_names(decorated)
for before, after in zip(original['medications'], decorated['medications']):
    for key, value in before.items():
        assert after[key] == value, 'Name annotation changed source/clinical field: ' + key
print('PASS: 4,451 exact RxCUI/source-name matches; 4,447 official PSNs + 4 structured NLM fallbacks; 375 readable packs; original IDs, clinical rules and names unchanged')

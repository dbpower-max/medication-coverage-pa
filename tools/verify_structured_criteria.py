"""Verify complete clinical text/metadata transcription, including edge cases."""
import gzip
import hashlib
import json
import re
from pathlib import Path
from structured_statewide_criteria import structure_policy, validate_structure

root = Path(__file__).resolve().parents[1]
data = json.loads(gzip.decompress((root / '_site/data.json.gz').read_bytes()))
reviewed = {g['policyCode'] for g in data['statewideClinicalGuidance']}
release = json.loads((root / 'tools/structured_criteria_release.json').read_text())
expected = reviewed | set(release['additionalPolicyCodes'])
assert len(data['statewidePaCriteria']) == 481
all_structured = {}
for policy in data['statewidePaCriteria']:
    source = (root / '_site' / policy['sourceTextUrl'].removeprefix('./')).read_text()
    structured = structure_policy(policy, source)
    all_structured[policy['policyCode']] = structured
    # This independent comparison covers every printed field, not just
    # selected source-check phrases or successful JSON generation.
    assert len(structured['branches']) == len(re.findall(r'^[\t ]*Product Name:', source, re.M))
    for branch in structured['branches']:
        original = source[branch['start']:branch['end']]
        for key in ('Diagnosis', 'Approval Length', 'Therapy Stage', 'Guideline Type'):
            assert bool(re.search(r'^[\t ]*' + key + r'[\t ]*$', original, re.M)) == (key in branch['fields'])
        assert not re.search(r'\d+\s*\.\s*Revision History', ' '.join(x['text'] for x in branch['criteria']))
    if policy['policyCode'] not in expected:
        assert not policy.get('structuredCriteriaUrl')
        continue
    url = policy['structuredCriteriaUrl']
    target = root / '_site' / url.split('?')[0].removeprefix('./')
    payload = target.read_bytes()
    assert url.endswith('?v=' + hashlib.sha256(payload).hexdigest()[:12])
    published = json.loads(payload)
    assert published == structured, 'Published criteria differ: ' + policy['policyCode']
    validate_structure(published, source)

assert data['structuredCriteriaCount'] == len(expected)
assert sum(len(x['branches']) for x in all_structured.values()) == 1596
# Administrative dose denial is not converted into an approval/renewal rule.
apap = all_structured['GL-144743']['branches'][0]
assert apap['fields']['Guideline Type']['text'] == 'DUR Reject 88'
assert 'Approval Length' not in apap['fields'] and 'Therapy Stage' not in apap['fields']
assert 'should be denied' in apap['criteria'][0]['text']
act = all_structured['GL-99673']['branches']
assert len(act) == 8
assert sum(b['fields']['Therapy Stage']['text'] == 'Reauthorization' for b in act) == 4
assert any('positive clinical response' in b['criteria'][0]['text'] for b in act)
cgm = all_structured['GL-553392']
assert len(cgm['branches']) == 4
assert cgm['branches'][-1]['fields']['Approval Length']['text'] == '1 Time(s)'
assert 'United Community Plan' in cgm['supplement']['verbatim']
assert not any(x['text'].startswith('646-4633') for b in cgm['branches'] for x in b['criteria']), 'Wrapped phone number mistaken for a numbered criterion'
adakveo = all_structured['GL-226191']['branches'][0]
assert [x['text'] for x in adakveo['criteria'] if x['kind'] == 'connector'] == ['AND', 'OR', 'AND', 'AND']
assert any('2.1 BOTH' in x['text'] for x in adakveo['criteria'])
assert any('hydroxyurea' in x['text'] for x in adakveo['criteria'])
print(f'PASS: {len(expected)}/481 structured policies published; all 481 policies / 1,596 branches source-validated; exact criteria, notes, fields, dates and hashes preserved')

"""Check indication branches, renewal provenance, and coverage preservation."""
import json,sqlite3,subprocess,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1]
d=json.loads((R/'dist/data.json').read_text());base=json.loads(subprocess.check_output(['git','show','367ebf6ada48e18188dcffae5ff4e2d6de8d4b4d:dist/data.json'],cwd=R))
strip=lambda m:{k:v for k,v in m.items() if k!='approvalGuideIds'}
assert list(map(strip,d['medications']))==base['medications']
assert [p for p in d['policies'] if not p.get('guide')]==base['policies']
g={p['id'].removeprefix('banner-guide-'):p for p in d['policies'] if p.get('guide')}
assert len(g)==17
assert len([m for m in d['medications'] if m.get('approvalGuideIds')])==15
assert '≥10' in ' '.join(g['glp-preferred']['guide']['requirements'])
assert '≥18' in ' '.join(g['glp-nonpreferred-injection']['guide']['requirements'])
assert len(g['glp-oral']['guide']['branches'][0]['options'])==2
assert 'ALL' in g['glp-oral']['guide']['branches'][0]['options'][1]
assert 'preserved EF' in g['farxiga']['guide']['branches'][0]['options'][1]
assert 'preserved EF' not in g['xigduo']['guide']['branches'][0]['options'][1]
assert '≥12' in g['triple-asthma']['guide']['requirements'][1] and '≥18' in g['triple-asthma']['guide']['requirements'][1]
assert '30-day' in g['triple-copd']['guide']['requirements'][1] and 'used in combination' in g['triple-copd']['guide']['requirements'][1]
assert g['ics-nonpreferred']['guide']['ambiguity'] and not g['ics-preferred']['guide']['ambiguity']
assert len([p for p in g.values() if p['guide']['renewal']])==4
assert g['soliqua']['guide']['renewal']==g['xultophy']['guide']['renewal']
assert not g['glp-preferred']['guide']['renewal']
assert len(g['u500']['guide']['branches'][0]['options'])==2
assert not next(m for m in d['medications'] if m['planId']=='banner-ufc' and m['brand']=='HUMALOG KWIKPEN').get('approvalGuideIds')
for p in g.values():
 assert p['sourceEffective']=='2026-11-01' and p['pa']=='not_specified'
 assert p['validation']=='source_reviewed_summary_not_clinician_approved'
 assert (R/'dist'/p['sourceTextUrl'].lstrip('/')).is_file()
 for page in p['sourcePages']:assert p['guide']['sourceSectionFirstPage']<=page<=p['guide']['sourceSectionLastPage']
for m in d['medications']:
 for gid in m.get('approvalGuideIds',[]):assert gid in {p['id'] for p in g.values()}
con=sqlite3.connect(R/'data/medication_coverage_v0.26.sqlite');assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert not con.execute('PRAGMA foreign_key_check').fetchall()
assert con.execute('select count(*) from banner_approval_guides').fetchone()[0]==17
assert hashlib.sha256((R/'data/medication_coverage_v0.25.sqlite').read_bytes()).digest()==hashlib.sha256(subprocess.check_output(['git','show','HEAD:data/medication_coverage_v0.25.sqlite'],cwd=R)).digest()
print('Passed: 17 guides, 15 product links, indication/renewal guards, SQLite integrity, and all prior coverage records unchanged.')

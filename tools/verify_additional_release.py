"""Source integrity, conservative flags, plan boundaries and database projection checks."""
import json,re,sqlite3,hashlib,gzip
from pathlib import Path
from guide_codes import guide_codes
ROOT=Path(__file__).resolve().parents[1]
d=json.loads((ROOT/'dist/data.json').read_text());registry=json.loads((ROOT/'audits/additional_guides/source_registry.json').read_text());db=sqlite3.connect(ROOT/'data/medication_coverage_v0.29.sqlite')
assert guide_codes('uhc-commercial-reference','PA, QL, ST')=={'PA','QL','ST'}
assert guide_codes('ambetter-az-essential-rx','Smart PA; QL(1 EA daily)')=={'PA','QL'}
assert guide_codes('azblue-standardized','AI (covered with no PA); QL (1 per day)')=={'QL'}
counts={}
for s in registry:
 assert hashlib.sha256((ROOT/'dist'/s['archivedFormulary'].lstrip('/')).read_bytes()).hexdigest()==s['sha256']
 pid=s['planId'];rows=json.loads((ROOT/'dist/data'/f'{pid}.json').read_text());counts[pid]=len(rows)
 assert len(rows)==s['releaseCount']
 for r in rows:
  assert r['planId']==pid and r['coverage']=='listed';codes=guide_codes(pid,r['rawRestrictions'])
  expected='required' if 'PA'in codes else 'conditional' if 'H-PA'in codes else 'not_specified'
  if expected=='required' and re.search(r'\b(no PA|without PA|PA (?:is )?not required)\b',r['rawRestrictions'],re.I):expected='conditional'
  assert r['pa']==expected
  assert r['step']==('specified' if 'ST'in codes else 'not_specified')
  rid=int(r['id'].removeprefix('guide-'));sql=db.execute('SELECT raw_drug_name,pa_status,pa_text,step_status,ql_amount FROM formulary_entries WHERE id=?',(rid,)).fetchone();assert tuple(sql)==(r['name'],r['pa'],r['paText'],r['step'],r['qlAmount'])
  if pid=='uhc-commercial-reference':assert r['listingLabel']=='In commercial PDL reference' and r['coverageCaveat']
  if pid=='azblue-standardized' and r['tier']=='MB':assert 'Medical benefit' in r['coverageCaveat']
allrows=d['medications'][:]
for f in d['planDataFiles'].values():allrows+=json.loads((ROOT/'dist'/f.removeprefix('./')).read_text())
assert len(allrows)==62183==d['meta']['recordCount']
assert len({r['id'] for r in allrows+d['policies']})==len(allrows)+len(d['policies'])
assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not db.execute('PRAGMA foreign_key_check').fetchall()
def digest(f):
 h=hashlib.sha256()
 while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
with gzip.open(ROOT/'data/medication_coverage_v0.29.sqlite.gz','rb') as f,(ROOT/'data/medication_coverage_v0.29.sqlite').open('rb') as g:assert digest(f)==digest(g)
print('Passed additional guide release:',counts,'Total medication/formulary records:',len(allrows))

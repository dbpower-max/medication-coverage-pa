"""Check plan separation, source integrity, status mapping, and prior-data preservation."""
import json,sqlite3,hashlib,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
d=json.loads((ROOT/'dist/data.json').read_text());base=json.loads(subprocess.check_output(['git','show','63267f8413aac7f18cc7a90465c7fda9d017fd1d:dist/data.json'],cwd=ROOT))
assert d['medications']==base['medications'];assert d['policies']==base['policies']
allrows=list(d['medications']);counts={}
registry=json.loads((ROOT/'audits/aetna_guides/source_registry.json').read_text())
assert len(registry)==13 and len(d['planDataFiles'])>=13
for s in registry:
 pid=s['planId'];p=ROOT/'dist'/d['planDataFiles'][pid].removeprefix('./');rows=json.loads(p.read_text());counts[pid]=len(rows)
 assert rows and all(r['planId']==pid for r in rows)
 assert len(rows)==s['releasedProducts']
 assert hashlib.sha256((ROOT/'dist'/s['archivedFormulary'].lstrip('/')).read_bytes()).hexdigest()==s['sha256']
 for r in rows:
  tier=r['tier'];raw=r['rawRestrictions'];codes=set(re.findall(r'(?:^|;\s*)(PA|ST|QL|QLR|AL|IBC|SPC|N10)(?=\s|;|$|\()',raw))
  assert r['coverage']==('explicit_not_covered' if tier=='NF' else 'listed')
  assert r['preferred']==('preferred' if tier in ['PG','PB','PSP','PBSP'] else 'non_preferred' if tier in ['NP','NPB','NPSP'] else 'not_specified')
  assert r['pa']==('required' if 'PA'in codes else 'not_specified')
  assert r['step']==('specified' if 'ST'in codes else 'not_specified')
  assert r['sourceEffective']=='2026-10-01' and r['validation']=='source_verified_independent_cells'
  assert r['sourcePage']>=21
 allrows.extend(rows)
assert len(allrows)==53610
assert len(d['medications'])+sum(len(json.loads((ROOT/'dist'/f.removeprefix('./')).read_text())) for f in d['planDataFiles'].values())==d['meta']['recordCount']
assert len({r['id'] for r in allrows+d['policies']})==len(allrows)+len(d['policies'])
assert all(p.stat().st_size<25*1024*1024 for p in (ROOT/'dist').rglob('*') if p.is_file())
con=sqlite3.connect(ROOT/'data/medication_coverage_v0.28.sqlite');assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert not con.execute('PRAGMA foreign_key_check').fetchall()
assert con.execute('SELECT count(*) FROM commercial_formulary_metadata').fetchone()[0]==46570
print('Passed: 46,570 Aetna product/formulary records; 13 distinct plans; every source hash, tier and PA/ST mapping checked; all prior records preserved.')

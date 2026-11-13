"""Verify release scope, sources, status semantics, history and SQLite roundtrip."""
import json,re,sqlite3,subprocess,hashlib,gzip
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'dist'
def read(p):return json.loads(gzip.decompress(p.read_bytes()).decode() if p.suffix=='.gz' else p.read_text())
d=read(D/'data.json');base=json.loads(subprocess.check_output(['git','show','e7bad015f4db61db48c9043f198c161e9f3ad443:dist/data.json'],cwd=ROOT));allmed=d['medications'][:]
for pid,f in d['planDataFiles'].items():
 rows=read(D/f.removeprefix('./'));assert all(r['planId']==pid for r in rows);allmed+=rows
assert len(allmed)==d['meta']['recordCount']==37084
assert len(d['policies'])==d['meta']['policyCount']==2906
assert len({r['id'] for r in allmed+d['policies']})==len(allmed)+len(d['policies'])
for pid,f in base['planDataFiles'].items():
 before=subprocess.check_output(['git','show',f'e7bad015f4db61db48c9043f198c161e9f3ad443:dist/{f.removeprefix("./")}'],cwd=ROOT)
 current=D/d['planDataFiles'][pid].removeprefix('./') if pid in d['planDataFiles'] else ROOT/'data/commercial-archive'/Path(f).name.replace('.json','.json.gz')
 assert (gzip.decompress(current.read_bytes()) if current.suffix=='.gz' else current.read_bytes())==before,pid
for r in allmed+d['policies']:
 for field in ['sourceUrl','sourceTextUrl']:
  u=r.get(field,'')
  if u.startswith('/'):assert (D/u.lstrip('/').split('#')[0]).is_file(),(r['id'],u)
 assert r.get('pa')!='not_required'
for p in D.rglob('*'):
 if p.is_file():assert p.stat().st_size<25*1024*1024,p
uhc=[r for r in allmed if r['planId']=='uhc-community-az'];assert len(uhc)==3921
assert all(r['sourceEffective']=='2026-10-01' for r in uhc)
assert not any(r['name'].lower().startswith('covered cholestyramine') for r in uhc)
assert not any(r['planId']=='ahcccs-statewide' for r in d['policies'])
u=[r for r in d['policies'] if r['planId']=='uhc-community-az'];assert len(u)==449 and all(r['sourceEffective']=='2026-11-01' for r in u)
assert all(r['sourceUrl']=='/sources/uhc-az-clinical-pharmacy-2026-11-01.pdf' for r in u)
for pid in ['banner-ufc','banner-altcs']:
 rs=[r for r in allmed if r['planId']==pid];issues=[r for r in rs if r['recordType']=='source_issue'];assert len(rs)==1453 and not issues
 corrected=[r for r in rs if r.get('brand') in ['HUMULIN N KWIKPEN','LANTUS SOLOSTAR']];assert len(corrected)==2
 for r in corrected:
  assert r['descriptionCorrection']['payerConfirmed'] is False and r['rawSourceRow']['page']==11
  assert r['coverage']=='listed' and r['preferred']=='preferred' and r['pa']=='not_specified'
  assert r['brandGenericNotes']=='BRAND ONLY' and not r.get('suppressCoverageAndPaBadges')
  assert r['name']=={'HUMULIN N KWIKPEN':'INSULIN NPH SUSPENSION','LANTUS SOLOSTAR':'INSULIN GLARGINE SOLUTION'}[r['brand']]
 for name in ['CLONIDINE HCL (ADHD) TABLET 12-HOUR','MEDROXYPROGESTERONE ACETATE TABLETS','PROGESTERONE MICRONIZED CAPSULES','PIMECROLIMUS CREAM']:
  assert next(r for r in rs if r['name']==name)['preferred']=='not_specified'
for pid,count in [('ahcccs-ffs-aihp',1810),('ahcccs-ffs-dual',328),('mercy-altcs',5106),('mercy-dd',5106),('mercy-dcs',5106),('az-complete-health-bh-only',262)]:
 assert len([r for r in allmed if r['planId']==pid])==count
for pid in ['az-complete-health','az-complete-health-rbha']:
 p=next(p for p in d['plans'] if p['id']==pid);assert p['status']=='mandated_minimum_incomplete'
 overlay=[r for r in allmed if r['planId']==pid and r.get('statewideReference')];assert len(overlay)==1449
 assert all(r['step']=='not_specified' and not r['qlAmount'] and 'not' in r['notes'].lower() for r in overlay)
# Every published clinical field matches the current structured master and payload.
c=sqlite3.connect(ROOT/'data/medication_coverage_v0.31.sqlite');assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert not c.execute('PRAGMA foreign_key_check').fetchall()
assert c.execute('SELECT count(*) FROM medications').fetchone()[0]==92227
assert c.execute('SELECT count(*) FROM medications m JOIN app_plan_visibility v ON v.plan_id=m.plan_id WHERE v.active=1').fetchone()[0]==len(allmed)
archive=read(ROOT/'data/commercial-archive/catalog.json');assert len(archive['plans'])==16
assert not {p['id'] for p in archive['plans']} & {p['id'] for p in d['plans']}
assert [p['id'] for p in d['plans'][:3]]==['az-complete-health','banner-ufc','uhc-community-az']
for pid,item in archive['datasets'].items():
 path=ROOT/item['path'];assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256']
 rows=read(path);assert len(rows)==item['records']
 assert all(json.loads(c.execute('SELECT payload FROM medications WHERE id=?',(r['id'],)).fetchone()[0])==r for r in rows)
for r in allmed:
 row=c.execute('SELECT payload,coverage,preferred,pa_status,pa_text,step_status,ql_amount,ql_days FROM medications WHERE id=?',(r['id'],)).fetchone()
 assert json.loads(row[0])==r
 assert row[1:]==(r['coverage'],r['preferred'],r['pa'],r['paText'],r['step'],r['qlAmount'],r['qlDays'])
assert c.execute('SELECT count(*) FROM policy_sections').fetchone()[0]==2906
for m in allmed:
 for gid in m.get('approvalGuideIds',[]):assert any(p['id']==gid and p['planId']==m['planId'] for p in d['policies'])
html=(D/'index.html').read_text();assert 'scope-alert' not in html and html.index('id="medicationInput"')<html.index('id="planInput"')
print('PASS: 37,084 active medication/source records; 2,906 current policy records; 55,143 commercial records archived unchanged; clinician corrections, priority plans, source links and complete SQLite projection verified.')

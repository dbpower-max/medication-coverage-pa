"""Release checks for source boundaries, conflicts, held rows, history, and policy links."""
import hashlib,json,sqlite3,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
d=json.loads((ROOT/'dist/data.json').read_text());a=json.loads((ROOT/'audits/banner_full/audit.json').read_text())
b=[m for m in d['medications'] if m['planId']=='banner-ufc']
assert len(b)==1448 and len(d['medications'])==5563
assert a['printed_product_positions']==a['released_positions']+len(a['held'])==1489
assert len(a['held'])==5 and len(a['conflicts'])==6
assert len({m['id'] for m in d['medications']+d['policies']})==len(d['medications'])+len(d['policies'])
old=json.loads((ROOT/'audits/banner_full/prior_133_records.json').read_text());assert len(old)==133
baseline=json.loads(subprocess.check_output(['git','show','be70ab177eebe4ab5bf3d2069016994d6caedc17:dist/data.json'],cwd=ROOT))
assert [m for m in d['medications'] if m['planId']!='banner-ufc']==[m for m in baseline['medications'] if m['planId']!='banner-ufc']
assert [p for p in d['policies'] if p['planId']!='banner-ufc']==baseline['policies']
get=lambda brand:next(m for m in b if m['brand']==brand)
assert get('HUMATIN')['coverage']=='explicit_not_covered'
for brand in ['HUMULIN N KWIKPEN','LANTUS SOLOSTAR','GLUCATROL XL','CRESTOR','OMNIFLEX DIAPHRAGM']:assert not any(m['brand']==brand for m in b)
assert get('TILIA FE')['name']=='NORETHINDRONE ACETATE-ETHINYL ESTRADIOL-FE TABLET'
for name in ['MORPHINE SULFATE TABLETS','ALPRAZOLAM TAB 0.5 MG','LORAZEPAM TAB 2 MG','LURASIDONE HCL TABS','ARIPIPRAZOLE TABLET','LOXAPINE SUCCINATE CAPSULES']:
 m=next(m for m in b if m['name']==name);assert 'PA REQUIRED' in m['paText'] and m['pa']=='conditional'
assert '37.5mg: 90 75mg: 90 150mg: 30'==get('EFFEXOR XR')['qlAmount']
assert 'ONLY' in get('HUMALOG KWIKPEN')['notes'] and get('HUMALOG KWIKPEN')['name'].endswith('100/ML')
assert all(m['preferred']!='preferred' for m in b if m['name']=='PIMECROLIMUS CREAM')
assert next(m for m in b if m['name']=='CLONIDINE HCL (ADHD) TABLET 12-HOUR')['preferred']=='non_preferred'
assert next(m for m in b if m['name']=='MEDROXYPROGESTERONE ACETATE TABLETS')['preferred']=='non_preferred'
assert get('RANEXA')['policySources'][0]['firstPage']==1439
assert not get('HUMALOG KWIKPEN').get('policySources')
assert not any(m['pa']=='not_required' for m in b)
for s in a['sources']:
 p=ROOT/'dist'/s['url'].lstrip('/');assert hashlib.sha256(p.read_bytes()).hexdigest()==s['sha256']
for p in [p for p in d['policies'] if p['planId']=='banner-ufc']:
 f=ROOT/'dist'/p['sourceTextUrl'].lstrip('/');assert f.is_file() and f.stat().st_size>0
 assert p['sourceEffective']==('2026-06-15' if p['subcategory']=='Banner internal criteria' else '2026-11-01')
assert len([p for p in d['policies'] if p['planId']=='banner-ufc'])==493
assert len([e for e in d['planEvidence'] if e['id']=='banner-internal-june2026'])==1
con=sqlite3.connect(ROOT/'data/medication_coverage_v0.25.sqlite');assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert not con.execute('PRAGMA foreign_key_check').fetchall()
assert con.execute('SELECT count(*) FROM formulary_entries WHERE plan_id=3').fetchone()[0]==1448
assert con.execute('SELECT count(*) FROM banner_source_pages').fetchone()[0]==4368
print('Banner release checks passed: 1,448 products; 5 held; 6 conservative conflicts; 493 source sections; non-Banner records preserved.')

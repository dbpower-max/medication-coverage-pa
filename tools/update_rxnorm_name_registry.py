"""Filter the official RxTerms release to existing RxCUIs; no medication import.
Run after a site build: python tools/update_rxnorm_name_registry.py /path/to/RxTerms202611.zip
"""
import argparse,csv,gzip,hashlib,io,json,re,zipfile
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('archive',type=Path);zpath=parser.parse_args().archive;
z=zipfile.ZipFile(zpath);lookup={}
for file in ['RxTermsArchive202611.txt','RxTerms202611.txt']:
 for r in csv.DictReader(io.StringIO(z.read(file).decode()),delimiter='|'):
  r['releaseFile']=file;lookup[r['RXCUI']]=r
source=json.loads(gzip.decompress(Path('_site/data.json.gz').read_bytes()))
ids={r['rxnormId'] for r in source['medications'] if r.get('rxnormId')}
names={}
for id in sorted(ids):
 r=lookup.get(id)
 if not r:continue
 names[id]={'fullName':r['FULL_NAME'],'psn':r['PSN'] if r['PSN'] not in ('NA','') else None,'displayName':r['DISPLAY_NAME'],'strength':r['STRENGTH'],'doseForm':r['NEW_DOSE_FORM'],'route':r['ROUTE'],'type':r['TTY'],'genericRxcui':r['GENERIC_RXCUI'],'retired':bool(r['IS_RETIRED']),'sourceFile':r['releaseFile']}
registry={'release':'202611','sourceUrl':'https://data.lhncbc.nlm.nih.gov/public/rxterms/release/RxTerms202611.zip','sourceSha256':hashlib.sha256(zpath.read_bytes()).hexdigest(),'names':names}
p=Path('tools/reference/rxnorm_names_202611.json.gz');p.write_bytes(gzip.compress(json.dumps(registry,ensure_ascii=False,separators=(',',':')).encode(),mtime=0))
print({'entries':len(names),'PSNs':sum(bool(r['psn']) for r in names.values()),'RxTermsFallbacks':sum(not r['psn'] for r in names.values()),'unmatched':sorted(ids-names.keys()),'fileBytes':p.stat().st_size})

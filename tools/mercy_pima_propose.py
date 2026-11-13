"""Project independently verified Mercy source rows without inventing preference or PA exemptions."""
import json,re,hashlib,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'audits/mercy_pima_2026_11_12'
a=json.loads((OUT/'extracted.json').read_text());assert not a['independent_mismatches'] and not a['fragments']
groups=collections.defaultdict(list)
for r in a['rows']:groups[(r['cells'][0].lower(),r['cells'][1].lower())].append(r)
records=[];conflicts=[]
for key,rs in groups.items():
 name,brand=rs[0]['cells'][:2];texts=list(dict.fromkeys(r['cells'][2] for r in rs));raw=' || '.join(texts);pa_texts=[]
 for text in texts:
  clauses=[x.strip() for x in text.split(';')]
  positive=bool(re.search(r'\bPA REQUIRED\b|\bREQUIRES? (?:PRIOR AUTHORIZATION|PA)\b',text,re.I)) or any(p=='PA' for p in clauses)
  if positive:pa_texts.append(text)
 pa='not_specified'
 if pa_texts:
  pa='conditional' if any(re.search(r'PA REQUIRED\s+for|\b(?:unless|when|years? of age|Ages?\s*[<>])\b|Prior Authorization is not',t,re.I) for t in pa_texts) else 'required'
 preferences={bool(re.search(r'\bBrand Preferred\b',t,re.I)) for t in texts}
 preferred='preferred' if preferences=={True} else 'not_specified'
 step=any(re.search(r'(?:^|;\s*)ST(?:\s|;|$|\()',t) for t in texts)
 qls=list(dict.fromkeys(c.strip() for t in texts for c in t.split(';') if c.strip().startswith('QLL')))
 note='Mercy Care integrated PDL shared explicitly by LTC, DD and DCS CHP. F means formulary, not preferred. Detailed PA and step criteria must be read separately. Blank fields do not establish no PA.'
 generic=bool(name and name[0].islower())
 if brand and generic:note+=' Reference column names the brand for this generic; the source states reference brands are not covered when a generic equivalent is available. This row does not establish separate coverage for the reference brand.'
 conflict=''
 if len(texts)>1:
  conflict='Printed duplicate rows have differing restrictions; all positive restrictions retained and both rows exposed. Omitted fields remain unspecified.';conflicts.append(dict(name=name,reference=brand,rows=rs));note+=' '+conflict
 record=dict(id='mercy-common-'+hashlib.sha256((name+'\0'+brand).encode()).hexdigest()[:18],recordType='formulary',planId='mercy-common',name=name,brand=brand,notes=note,category='Other',subcategory=rs[0]['class_name'],coverage='listed',preferred=preferred,pa=pa,paText=' || '.join(pa_texts),step='specified' if step else 'not_specified',stepText='ST printed; read applicable step-therapy criteria.' if step else '',qlAmount='; '.join(qls),qlDays='',conditions=[],ageLimited=bool(re.search(r'\bAges?\b|years? of age',raw,re.I)),maintenance=bool(re.search('Maintenance Drug',raw,re.I)),rawRestrictions=raw,sourceTitle='Mercy Care Integrated Preferred Drug List — October 2026',sourceEffective='2026-10-01',sourcePage=rs[0]['page'],sourcePages=sorted({r['page'] for r in rs}),sourceUrl='/sources/mercy-integrated-2026-10-01.pdf',validation='source_table_verified_independent_text',sourceRows=[dict(page=r['page'],table=r['table'],row=r['row'],cells=r['cells']) for r in rs],sourceConflict=conflict)
 if generic and brand:record['brandReferenceOnly']=True;record['coverageCaveat']='Reference brand is not a separate listing'
 records.append(record)
(OUT/'proposed_common_records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
audit=dict(source=a['source'],table_pages=list(range(7,240)),printed_product_positions=len(a['rows']),class_heading_positions=len(a['headings']),distinct_products=len(records),identical_duplicate_groups=sum(len(v)>1 and len({r['cells'][2] for r in v})==1 for v in groups.values()),differing_duplicate_groups=conflicts,independent_cell_differences=0,unresolved_fragments=0,pa_counts=dict(collections.Counter(r['pa'] for r in records)),preference_counts=dict(collections.Counter(r['preferred'] for r in records)),source_position_accounting=sum(len(r['sourceRows']) for r in records))
assert audit['source_position_accounting']==5110
(OUT/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in audit.items() if k not in ['differing_duplicate_groups','source','table_pages']},indent=2))

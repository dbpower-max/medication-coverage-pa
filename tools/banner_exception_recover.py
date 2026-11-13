"""Restore literal Banner exception rows and policy Product Name search fields."""
import json,re,hashlib,fitz,pdfplumber
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'audits/banner_exception_review_2026_11_12';OUT.mkdir(parents=True,exist_ok=True)
def clean(x):return ' '.join(x.split())
def main():
 d=json.loads((ROOT/'dist/data.json').read_text());audit=json.loads((ROOT/'audits/banner_full/audit.json').read_text());proposed=[];corrections=[]
 for r in d['medications']:
  if r['planId']=='banner-ufc' and r.get('sourceConflict') and r['preferred']=='non_preferred' and any(x.get('preference')=='Preferred not shown' for x in r.get('sourceRows',[])):
   corrections.append(dict(record_id=r['id'],name=r['name'],current=r['preferred'],proposed='not_specified',reason='One duplicate shows PREFERRED DRUG and another is blank. Blank does not establish nonpreferred status.',sourceRows=r['sourceRows']))
 assert len(corrections)==4
 pdf=fitz.open(ROOT/'dist/sources/bufc_formulary_eff10012026_en.pdf')
 with pdfplumber.open(ROOT/'dist/sources/bufc_formulary_eff10012026_en.pdf') as independent:
  for h in audit['held']:
   pn=h['page'];raw=h['cells'];tables=pdf[pn-1].find_tables();table=tables.tables[h['table']-1];i=h['row']-1
   assert list(map(lambda v:clean(v or ''),table.extract()[i]))==raw
   words=independent.pages[pn-1].extract_words(x_tolerance=1,y_tolerance=2)
   cells=[]
   for bound in table.rows[i].cells:
    if not bound:cells.append('');continue
    x0,y0,x1,y1=bound;ws=[w for w in words if x0<(w['x0']+w['x1'])/2<x1 and y0<(w['top']+w['bottom'])/2<y1];lines=[]
    for w in sorted(ws,key=lambda w:(w['top'],w['x0'])):
     if not lines or abs(w['top']-lines[-1][0]['top'])>2:lines.append([w])
     else:lines[-1].append(w)
    cells.append(clean(' '.join(w['text'] for l in lines for w in sorted(l,key=lambda w:w['x0']))))
   assert [re.sub(r'\s+','',v) for v in cells]==[re.sub(r'\s+','',v) for v in raw],(h,cells)
   r=dict(id=f'banner-source-review-{pn}-{h["table"]}-{h["row"]}',recordType='formulary',planId='banner-ufc',name=raw[0],brand=raw[1],notes='',subcategory=h['class'],coverage='listed',preferred='preferred' if raw[3]=='PREFERRED DRUG' else 'not_specified',pa='not_specified',paText=raw[4],step='not_specified',stepText=raw[5],qlAmount=raw[6],qlDays=raw[7],conditions=[],sourceTitle='Banner - University Family Care Acute–Long Term Care Drug List',sourceEffective='2026-10-01',sourcePage=pn,sourceUrl='/sources/bufc_formulary_eff10012026_en.pdf',rawSourceRow=h,validation='verbatim_source_row_independently_verified')
   if raw[1] in ['HUMULIN N KWIKPEN','LANTUS SOLOSTAR']:
    r.update(recordType='source_issue',coverage='unresolved_identity',preferred='not_specified',sourceIssue='Drug identity requires payer clarification',listingLabel='Unresolved source identity',suppressCoverageAndPaBadges=True,validation='source_identity_unresolved')
    r['notes']='The source drug name and reference-brand/formulation cells conflict. Do not interpret this row as coverage for either inferred insulin product; payer clarification is required.'
   elif raw[1]=='GLUCATROL XL':
    r['searchAliases']=['GLUCOTROL XL','glipizide extended release'];r['notes']='Verbatim generic identity is clear. Banner prints GLUCATROL XL; the manufacturer identifies GLUCOTROL XL as glipizide extended-release tablets. The lookup alias does not change payer source text.';r['identityCorroboration']={'url':'https://labeling.pfizer.com/showlabeling.aspx?id=585','fact':'GLUCOTROL XL is glipizide extended-release tablets.'}
   elif raw[1]=='CRESTOR':
    r['searchAliases']=['ROSUVASTATIN TABLETS'];r['notes']='Banner prints ROUVASTATIN TABLETS beside CRESTOR. FDA labeling identifies CRESTOR as rosuvastatin tablets; retain source spelling and expose the documented lookup alias.';r['identityCorroboration']={'url':'https://www.accessdata.fda.gov/drugsatfda_docs/label/2026/021366s048lbl.pdf','fact':'CRESTOR is rosuvastatin tablets.'}
   else:r['notes']='Verbatim source row. The +A1294 spreadsheet-reference artifact remains in the source name; reference brand explicitly identifies OMNIFLEX DIAPHRAGM. No strength or additional restriction is inferred.';r['searchAliases']=['DIAPHRAGMS - OTHER','OMNIFLEX DIAPHRAGM']
   proposed.append(r)
 (OUT/'proposed_source_rows.json').write_text(json.dumps(proposed,ensure_ascii=False,indent=2))
 policy_fields=[];total=0
 for p in [x for x in d['policies'] if x['planId']=='banner-ufc' and x['recordType']=='policy_index']:
  text=(ROOT/'dist'/p['sourceTextUrl'].lstrip('/')).read_text();fields=[];aliases=[]
  pattern=r'(?im)^\s*Product\s+Name\s*:\s*(.*?)(?=^\s*(?:Diagnosis|Approval\s+Length|Therapy\s+Stage|Guideline\s+Type|Approval\s+Criteria|Initial Approval Criteria|>\d+ years[^\n]*|Notes)\s*:?\s*\n)'
  for m in re.finditer(pattern,text,re.S|re.M):
   raw=m.group(1);pages=re.findall(r'=== PDF PAGE (\d+) ===',text[:m.start()]);first=int(pages[-1]) if pages else p['sourcePage'];inside=re.findall(r'=== PDF PAGE (\d+) ===',raw);last=int(inside[-1]) if inside else first
   value=clean(re.sub(r'(?m)^\s*(?:=== PDF PAGE \d+ ===|Page \d+)\s*$','',raw));fields.append(dict(rawText=raw,text=value,firstPage=first,lastPage=last));total+=1
   for token in re.split(r'[,;]',value):
    token=re.sub(r'^(?:Preferred\*?|Non-Preferred\*?|Brand|Generic)\s*:?\s*','',token.strip(),flags=re.I).strip()
    if len(token)>2 and re.search('[A-Za-z]',token):aliases.append(token)
  policy_fields.append(dict(policy_id=p['id'],name=p['name'],fields=fields,searchAliases=sorted(set(aliases)),searchTerms=' | '.join(dict.fromkeys(f['text'] for f in fields))))
 (OUT/'policy_product_name_search_terms.json').write_text(json.dumps(policy_fields,ensure_ascii=False,indent=2))
 summary=dict(source_positions=1489,prior_released_positions=1484,proposed_identifiable_rows=3,unresolved_identity_positions=2,independent_exception_cell_differences=0,preference_conflict_corrections=corrections,policy_records=len(policy_fields),policies_with_product_name=sum(bool(p['fields']) for p in policy_fields),product_name_fields=total,alias_count=sum(len(p['searchAliases']) for p in policy_fields))
 (OUT/'summary.json').write_text(json.dumps(summary,indent=2));print(summary)
if __name__=='__main__':main()

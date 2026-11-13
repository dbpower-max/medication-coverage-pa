"""Suggest related-criteria links from explicit product-name/header identity only.
Candidates expose source scope; they do not infer PA, approval, indication or dose applicability.
"""
from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'audits/november_policy_index_2026_11_12'
def primary_name(value):return re.split(r'\s*\((?:generic|brand) for\b',value,flags=re.I)[0].strip()
def words(value):return re.sub(r'[^a-z0-9]+',' ',value.lower()).strip()
def aliases(section):
 result=[]
 for product in section['products']:
  value=product['text']
  # Preserve whole explicit header identity; parenthetical ingredient aliases stay
  # separate candidates only when they are short literal names, not clinical prose.
  options=[value]
  if '(' in value:options.append(value.split('(')[0].strip());options+=re.findall(r'\(([^()]*)\)',value)
  for option in options:
   option=option.strip().rstrip('*').strip()
   if 5<=len(option)<=90 and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9'’ -]*(?:[®™])?",option) and 1<=len(option.split())<=4:
    result.append(dict(alias=option,sourcePage=product['page'],field='Product Name'))
 return result

def candidates(records,source_key):
 sections=json.loads((OUT/source_key/'sections.json').read_text());matches=[]
 for record in records:
  identity=words(primary_name(record['name']));brand=words(record.get('brand',''))
  for section in sections:
   seen=set()
   for alias in aliases(section):
    term=words(alias['alias'])
    if not term or term in seen:continue
    seen.add(term)
    # Literal prefix means the actual named product; do not use reference-brand
    # parentheticals or names mentioned only as prerequisite alternatives.
    if identity==term or identity.startswith(term+' ') or (brand and brand!='various' and brand==term):
     matches.append(dict(recordId=record['id'],recordName=record['name'],policyId=source_key+'-policy-'+section['guidelineId'].lower(),policyTitle=section['title'],policyFirstPage=section['firstPage'],policyLastPage=section['lastPage'],sourceProductFieldPage=alias['sourcePage'],sourceProductAlias=alias['alias'],matchBasis='Literal actual product/brand identity prefix in explicit Product Name field',status='Related source section candidate; confirm formulation, indication and branch before applying criteria'))
     break
 return matches
if __name__=='__main__':
 data=json.loads((ROOT/'dist/data.json').read_text());records=[r for r in data['medications'] if r['planId']=='uhc-community-az' and r.get('sourceEffective')=='2026-10-01']
 links=candidates(records,'uhc-nov2026');(OUT/'uhc-nov2026'/'related_policy_candidates_current_records.json').write_text(json.dumps(links,ensure_ascii=False,indent=2));print(len(links),'links for',len({r['recordId'] for r in links}),'current records')

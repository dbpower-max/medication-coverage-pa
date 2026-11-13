#!/usr/bin/env python3
"""Import the November 2026 AHCCCS statewide table as a separate source version.

Exact name and reference-brand duplicates are collapsed conservatively. Each
printed row remains in raw_row_json and the site links every source page.
No machine-extracted clinical conditions are released by this importer.
"""
import collections
import hashlib
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path

import pdfplumber
import fitz

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT.parent/'work'
PDF=WORK/'ahcccs_drug_list_2026-11-01.pdf'
ARCHIVE=ROOT/'dist/sources/ahcccs-drug-list-2026-11-01.pdf'
OLD=WORK/'medication_coverage_v0.23.sqlite'
NEW=WORK/'medication_coverage_v0.24.sqlite'
DATA=ROOT/'dist/data.json'
AUDIT=WORK/'ahcccs_november_import_audit_2026-11-10.json'
HASH='54714cef12bff4d4f6f2f8de4b1231a5f6b68b6af7d186ed1ea57f54650c0643'
OFFICIAL='https://www.azahcccs.gov/Resources/Downloads/PharmacyUpdates/2026/AHCCCSDrugListEffective2026-11-01.pdf'

sys.path.insert(0,str(ROOT/'tools'))
from export_data import category_for
import import_ahcccs_october as prior

def clean(value):
    return ' '.join((value or '').split())

def parse():
    groups=collections.OrderedDict()
    held=[]
    current_class=''
    with pdfplumber.open(PDF) as pdf:
        assert len(pdf.pages)==35
        assert 'Effective Date: November 1, 2026' in fitz.open(PDF)[0].get_text()
        for page_no,page in enumerate(pdf.pages,1):
            tables=page.extract_tables()
            assert len(tables)==1 and len(tables[0][0])==8
            for row_no,row in enumerate(tables[0][1:],2):
                cells=[clean(v) for v in row]
                if not cells[0]:
                    held.append({'page':page_no,'row':row_no,'cells':cells,'reason':'name missing'})
                    continue
                if cells[0].startswith('PULMONARY HYPERTENSION - PHOSPHODIESTERASE INHIBIT'):
                    current_class=cells[0]
                    continue
                if not any(cells[1:]):
                    current_class=cells[0]
                    continue
                name,brand,notes,pref,pa,step,ql,days=cells
                if (name,brand) in {
                    ('INSULIN REGULAR (HUMAN) SOLUTION PEN INJECTION','HUMULIN N KWIKPEN'),
                    ('INSULIN GLARGINE SUSPENSION','LANTUS SOLOSTAR'),
                }:
                    held.append({'page':page_no,'row':row_no,'cells':cells,
                                 'reason':'printed drug name and reference brand/formulation mismatch; identity review'})
                    continue
                if not brand and name!='COVID AT-HOME TEST KITS':
                    held.append({'page':page_no,'row':row_no,'cells':cells,'reason':'no reference brand; identity review'})
                    continue
                key=(name,brand)
                groups.setdefault(key,[]).append({'page':page_no,'row':row_no,
                    'class':current_class,'cells':cells})
    return groups,held

def restrictive(rows):
    fields=[r['cells'] for r in rows]
    # A blank preference cell is an unresolved status, even if another row says preferred.
    preferred='preferred' if all('PREFERRED DRUG' in c[3].upper() for c in fields) else 'not_specified'
    pa_texts=list(dict.fromkeys(c[4] for c in fields if c[4]))
    pa_text=' | '.join(pa_texts)
    if pa_text:
        pa_status='conditional' if re.search(r'ages?|years?|\bfor\b|\bonly\b|\b>\b|\b<\b',pa_text,re.I) else 'required'
    else:pa_status='not_specified'
    step_text=' | '.join(dict.fromkeys(c[5] for c in fields if c[5]))
    limits=[(c[6],c[7]) for c in fields if c[6] or c[7]]
    if limits:
        # Choose the strictest comparable numeric amount per day. Preserve every
        # printed limit in the source rows when units/periods are incomparable.
        def rank(x):
            a=re.search(r'\d+(?:\.\d+)?',x[0]);d=re.search(r'\d+(?:\.\d+)?',x[1])
            if a and d and float(d.group())>0:return float(a.group())/float(d.group())
            return float('inf')
        ql,days=min(limits,key=rank)
    else:ql=days=''
    notes=' | '.join(dict.fromkeys(c[2] for c in fields if c[2]))
    statuses={(c[2],c[3],c[4],c[5],c[6],c[7]) for c in fields}
    conflict=len(statuses)>1
    return preferred,pa_status,pa_text,step_text,ql,days,notes,conflict

def main():
    assert hashlib.sha256(PDF.read_bytes()).hexdigest()==HASH
    groups,held=parse()
    assert len(held)==3 and {h['cells'][1] for h in held}=={'TILIA FE','HUMULIN N KWIKPEN','LANTUS SOLOSTAR'}
    assert sum(map(len,groups.values()))==1486
    old_groups,_=prior.parse()
    assert set(groups)==set(old_groups)
    changed=[{'name':name,'brand':brand,'old':prior.restrictive(old_groups[(name,brand)]),
              'new':restrictive(rows),'page':rows[0]['page']}
             for (name,brand),rows in groups.items()
             if restrictive(rows)!=prior.restrictive(old_groups[(name,brand)])]
    assert len(changed)==2 and all(c['brand']=='VRAYLAR' for c in changed)
    shutil.copy2(OLD,NEW)
    shutil.copy2(PDF,ARCHIVE)
    db=sqlite3.connect(NEW)
    db.execute('PRAGMA foreign_keys=ON')
    sid=db.execute('''INSERT INTO sources(kind,filename,sha256,official_url,effective_date,retrieved_at,ingested_at,scope,page_count)
      VALUES ('drug_list',?,?,?,?,datetime('now'),datetime('now'),'AHCCCS statewide reference',35)''',
      (PDF.name,HASH,OFFICIAL,'2026-11-01')).lastrowid
    db.execute("INSERT INTO plan_sources(plan_id,source_id,role) VALUES(1,?,'statewide_reference')",(sid,))
    data=json.loads(DATA.read_text())
    data['medications']=[m for m in data['medications'] if m['planId']!='ahcccs-statewide']
    conflict_audit=[]
    for (name,brand),rows in groups.items():
        pref,pa,pa_text,step_text,ql,days,notes,conflict=restrictive(rows)
        conservative_pref=('non_preferred' if conflict and pref=='not_specified'
            and any('PREFERRED DRUG' in r['cells'][3].upper() for r in rows) else pref)
        key=json.dumps([name,brand,notes.upper()],ensure_ascii=False)
        existing=db.execute('SELECT id FROM drugs WHERE normalized_key=?',(key,)).fetchone()
        if existing:drug_id=existing[0]
        else:drug_id=db.execute('INSERT INTO drugs(drug_name,reference_brand,notes,normalized_key) VALUES (?,?,?,?)',
            (name,brand,notes,key)).lastrowid
        first=rows[0]
        raw={'rows':rows,'duplicate_review':'conservative_union' if conflict else 'identical_or_unique',
             'resolved_preferred_status':conservative_pref}
        eid=db.execute('''INSERT INTO formulary_entries(plan_id,source_id,drug_id,source_page,source_row,class_name,
            raw_drug_name,raw_brand,raw_notes,coverage_status,preferred_status,pa_status,pa_text,
            step_status,step_text,ql_amount,ql_days,raw_row_json)
            VALUES (1,?,?,?,?,?,?,?,?,'listed',?,?,?,?,?,?,?,?)''',
            (sid,drug_id,first['page'],first['row'],first['class'],name,brand,notes,pref,pa,pa_text,
             'specified' if step_text else 'not_specified',step_text,ql,days,json.dumps(raw))).lastrowid
        record={'id':f'formulary-{eid}','recordType':'formulary','planId':'ahcccs-statewide',
            'name':name,'brand':brand,'notes':notes,
            'category':category_for(first['class'],name,brand),
            'subcategory':first['class'] or 'Unclassified formulary row',
            'coverage':'listed','preferred':conservative_pref,'pa':pa,'paText':pa_text,
            'step':'specified' if step_text else 'not_specified','stepText':step_text,
            'qlAmount':ql,'qlDays':days,'conditions':[],
            'sourceTitle':'AHCCCS Acute - Long Term Care Drug List',
            'sourceEffective':'2026-11-01','sourcePage':first['page'],
            'sourceUrl':'/sources/ahcccs-drug-list-2026-11-01.pdf',
            'sourcePages':sorted(set(r['page'] for r in rows)),
            'sourceRows':([{'page':r['page'],'row':r['row'],'preference':r['cells'][3] or 'Preferred not shown',
                            'pa':r['cells'][4],'step':r['cells'][5],
                            'quantity':f"{r['cells'][6]} per {r['cells'][7]} days" if r['cells'][6] else ''}
                           for r in rows] if conflict else []),
            'sourceConflict':('Conflicting duplicate listings; least favorable preference and combined restrictions shown.' if conflict else ''),
            'validation':'source_table_reviewed'}
        data['medications'].append(record)
        if conflict: conflict_audit.append({'name':name,'brand':brand,'rows':rows,
            'result':{'preferred':conservative_pref,'pa':pa,'step':step_text,'ql':ql,'days':days}})
    db.commit()
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
    assert db.execute('SELECT count(*) FROM formulary_entries WHERE source_id=?',(sid,)).fetchone()[0]==len(groups)
    db.close()
    data['meta']['drugListEffective']='2026-11-01'
    data['meta']['asOf']='2026-11-10'
    data['meta']['recordCount']=len(data['medications'])
    plan=next(p for p in data['plans'] if p['id']=='ahcccs-statewide')
    plan['detail']=(f'{len(groups):,} distinct November 2026 statewide drug-list products, with '
      f'{len(conflict_audit)} differing duplicate listings resolved conservatively. '
      'This is a statewide reference, not an exact Banner or other managed-care benefit.')
    plan['effective']='2026-11-01'
    az_plan=next(p for p in data['plans'] if p['id']=='az-complete-health')
    az_plan['detail']=('November 2026 AHCCCS statewide reference and dated plan notices are linked below. '
      'The preserved 2022 JSON is historical, and update notices are not exhaustive. '
      'Eleven plan policy sources are indexed, but no complete current exact-plan medication coverage is loaded.')
    for evidence in data['planEvidence']:
        if evidence['id']=='identified-6':
            evidence['topic']='AHCCCS statewide drug list · November 2026'
            evidence['evidence']='Dated November 2026 AHCCCS statewide reference. Search it separately; it is not proof of this plan’s exact benefit.'
            evidence['sourceEffective']='2026-11-01'
            evidence['sourceUrl']=OFFICIAL
    for evidence in data['planEvidence']:
        if evidence['id']=='ahcccs-october-source':
            evidence['topic']='Archived October 2026 statewide drug list'
            evidence['notes']='Historical comparison; November edition is the current statewide reference.'
    data['planEvidence']=[e for e in data['planEvidence'] if e['id']!='ahcccs-november-source']
    data['planEvidence'].append({'id':'ahcccs-november-source','planId':'ahcccs-statewide',
      'topic':'Official November 2026 statewide drug list',
      'evidence':f'{len(groups):,} distinct source-table products imported. Three ambiguous PDF positions remain under review; duplicate rows retain every printed source page.',
      'sourcePage':1,'sourceEffective':'2026-11-01','sourceUrl':OFFICIAL,
      'notes':'Statewide reference only; exact member-plan benefit requires plan-specific confirmation.'})
    DATA.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
    audit={'pdf_sha256':HASH,'source_id':sid,'physical_pages':35,'printed_positions':1489,
       'distinct_products':len(groups),'changed_from_october':changed,
       'conflicting_duplicate_groups':conflict_audit,
       'held':held,'total_site_medications':len(data['medications'])}
    AUDIT.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    print({k:len(v) if isinstance(v,list) else v for k,v in audit.items() if k!='pdf_sha256'})

if __name__=='__main__':main()

#!/usr/bin/env python3
"""Add visually reviewed Banner UFC October diabetes rows to the static release.

This is a selected source-page transcription, not a complete Banner import.
The official PDF is linked per row. Blank cells remain unspecified.
"""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'dist' / 'data.json'
SOURCE = ('https://www.bannerhealth.com/bhpprovider/-/media/files/project/bufc/'
          'pharmacy/bufc_formulary_eff10012026_en.pdf')
PA_SOURCE = ('https://www.bannerhealth.com/bhpprovider/-/media/files/project/bhpprovider/'
             'pharmacy/medicaid/prov-bufc_pharmacy-pa-criteria_v2_eff10012026_en.pdf')

# page, printed drug name, reference brand, preferred, PA, step, QL amount, QL days, notes
# A blank status is deliberately not inferred from the document's general preface.
ROWS = [
 (10,'PRAMLINTIDE ACETATE SOLUTION PEN INJECTION','SYMLINPEN 60',1,1,0,'','',''),
 (10,'ALOGLIPTIN-METFORMIN','VARIOUS',1,0,1,'','',''),
 (10,'ALOGLIPTIN-PIOGLITAZONE','VARIOUS',1,0,1,'','',''),
 (10,'DAPAGLIFLOZIN FREE BASE-METFORMIN HCL TABLET ER 24HR','XIGDUO XR',1,0,1,'','','Brand only'),
 (10,'EMPAGLIFLOZIN-LINAGLIPTIN-METFORMIN','TRIJARDY XR',1,0,1,'','','Brand only'),
 (10,'EMPAGLIFLOZIN-METFORMIN HCL','SYNJARDY',1,0,1,'','','Brand only'),
 (10,'LINAGLIPTIN-METFORMIN HCL TABLETS','JENTADUETO',1,0,1,'','','Brand only'),
 (10,'PIOGLITAZONE HCL-METFORMIN HCL TABLETS','ACTOPLUS MET',0,0,0,'','',''),
 (10,'SITAGLIPTIN-METFORMIN HCL TABLETS','JANUMET',1,0,1,'','','Brand only'),
 (10,'SITAGLIPTIN-METFORMIN HCL TABLET 24-HOUR','JANUMET XR',1,0,1,'','','Brand only'),
 (10,'METFORMIN HCL TABLETS','GLUCOPHAGE',0,0,0,'','',''),
 (10,'METFORMIN HCL TABLET 24-HOUR (GENERIC OF GLUCOPHAGE XR ONLY- 500MG & 750MG)','VARIOUS',0,1,0,'','','PA required for osmotic and modified release products; verify presentation'),
 (10,'DASIGLUCAGON HCL SOLN AUTO-INJ','ZEGALOGUE',1,0,0,'1','30','Brand only'),
 (10,'DASIGLUCAGON HCL SOLN PREF SYR','ZEGALOGUE',1,0,0,'2','30','Brand only'),
 (10,'DIAZOXIDE SUSPENSION','PROGLYCEM',1,0,0,'','','Brand only'),
 (10,'GLUCAGON POWDER','BAQSIMI',1,0,0,'2','30','Brand only'),
 (10,'GLUCAGON SOLUTION RECONSTITUTED','GLUCAGON EMERGENCY KIT',1,0,0,'2','30',''),
 (10,'MIFEPRISTONE (HYPERGLYCEMIA) TABLET','KORLYM',0,1,0,'','',''),
 (10,'ALOGLIPTIN BENZOATE TABLETS','NESINA',1,0,1,'','',''),
 (10,'LINAGLIPTIN TABLETS','TRADJENTA',1,0,1,'','','Brand only'),
 (10,'SITAGLIPTIN PHOSPHATE TABLETS','JANUVIA',1,0,1,'','','Brand only'),
 (11,'DULAGLUTIDE SOLUTION PEN-INJECTION','TRULICITY',1,1,0,'','',''),
 (11,'LIRAGLUTIDE SOLN PEN-INJ','VICTOZA',1,1,0,'','','Brand and generic'),
 (11,'TIRZEPATIDE SOLN AUTO-INJ','MOUNJARO',0,1,0,'','','Preferred status not specified in this row'),
 (11,'PRAMLINTIDE','SYMLIN PEN',1,1,0,'','',''),
 (11,'INSULIN DEGLUDEC SOLUTION','TRESIBA',0,0,0,'','','Brand only'),
 (11,'INSULIN DEGLUDEC SOLN PEN-INJ','TRESIBA',0,0,0,'','','Brand only'),
 (11,'INSULIN LISPRO (HUMAN) SOLUTION','HUMALOG',1,0,0,'','','Authorized generic only'),
 (11,'INSULIN NPH ISOPHANE & REG (HUMAN) SUSPENSION','HUMULIN 70/30',1,0,0,'','','Brand only'),
 (11,'INSULIN NPH (HUMAN) (ISOPHANE) SUSPENSION','HUMULIN N',1,0,0,'','','Brand only'),
 (11,'INSULIN REGULAR (HUMAN) SOLUTION','HUMULIN R U-500 (CONCENTRATED)',1,1,0,'','','Brand only; specific U-500 product'),
 (11,'INSULIN GLARGINE SOLUTION','LANTUS',1,0,0,'','','Brand only'),
 (11,'INSULIN GLARGINE SUSPENSION','LANTUS SOLOSTAR',1,0,0,'','','Brand only'),
 (11,'INSULIN GLARGINE-YFGN SOLN PEN-INJ','SEMGLEE',1,0,0,'','','Brand only'),
 (11,'INSULIN ASPART SOLUTION','NOVOLOG',1,0,0,'','',''),
 (11,'INSULIN ASPART SOLUTION PEN-INJECTION','NOVOLOG FLEXPEN',1,0,0,'','',''),
 (11,'DAPAGLIFLOZIN TABLET','FARXIGA',1,0,1,'','','Brand only'),
 (11,'EMPAGLIFLOZIN','JARDIANCE',1,0,1,'','',''),
]

def main():
    data = json.loads(DATA.read_text())
    data['medications'] = [m for m in data['medications'] if not m['id'].startswith('banner-oct26-')]
    for i,(page,name,brand,preferred,pa,step,ql,days,notes) in enumerate(ROWS,1):
        if i==1 or i==25: subcategory='Diabetic miscellaneous agents'
        elif 2<=i<=10: subcategory='Antidiabetic combinations'
        elif 11<=i<=12: subcategory='Biguanides'
        elif 13<=i<=18: subcategory='Diabetic other'
        elif 19<=i<=21: subcategory='DPP-4 inhibitors'
        elif 22<=i<=24: subcategory='GLP-1 receptor agonists'
        elif 26<=i<=27: subcategory='Insulin sensitizing agents'
        elif 28<=i<=36: subcategory='Insulins'
        else: subcategory='SGLT2 inhibitors'
        data['medications'].append({
            'id': f'banner-oct26-{i:03d}', 'recordType':'formulary',
            'planId':'banner-ufc', 'name':name, 'brand':brand,
            'notes': notes, 'category':'Diabetes', 'subcategory':subcategory,
            'coverage':'listed', 'preferred':'preferred' if preferred else 'not_specified',
            'pa':'conditional' if i==12 else ('required' if pa else 'not_specified'),
            'paText': ('PA required for osmotic and modified release products; verify the exact presentation' if i==12 else ('PA required' if pa else '')),
            'step':'specified' if step else 'not_specified',
            'stepText':'Step through metformin' if step else '',
            'qlAmount':ql, 'qlDays':days, 'conditions':[],
            'sourceTitle':'Banner - University Family Care Acute–Long Term Care Drug List',
            'sourceEffective':'2026-10-01', 'sourcePage':page,
            'sourceUrl':SOURCE, 'validation':'visually_reviewed_source_page',
        })
    plan = next(p for p in data['plans'] if p['id']=='banner-ufc')
    plan.update(status='selected_records_loaded', effective='Selected rows effective 2026-10-01',
        detail=f'{len(ROWS)} diabetes medication rows visually checked against the October 1, 2026 Banner drug list. Other classes and products are not yet imported. A blank preference or PA cell is displayed as unspecified, not as a negative determination.')
    data['planEvidence'] = [e for e in data['planEvidence'] if e['id'] not in ('banner-oct26-formulary','banner-oct26-pa')]
    data['planEvidence'] += [
      {'id':'banner-oct26-formulary','planId':'banner-ufc','topic':'October 2026 Banner - University Family Care drug list',
       'evidence':'Selected diabetes rows on PDF pages 10–11 were visually checked. This is a partial import; the entire drug list is not searchable here.',
       'sourcePage':10,'sourceEffective':'2026-10-01','sourceUrl':SOURCE,'notes':'Official provider page lists this drug list for Banner - University Family Care.'},
      {'id':'banner-oct26-pa','planId':'banner-ufc','topic':'October 2026 pharmacy PA criteria',
       'evidence':'Official current criteria source identified; detailed approval criteria have not been structured or clinician reviewed in this app.',
       'sourcePage':None,'sourceEffective':'2026-10-01','sourceUrl':PA_SOURCE,'notes':'Source link for manual policy review.'},
    ]
    data['meta']['asOf']='2026-10-26'
    data['meta']['recordCount']=len(data['medications'])
    DATA.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
    print({'bannerRows':len(ROWS),'medications':len(data['medications'])})

if __name__=='__main__': main()

#!/usr/bin/env python3
"""Correct and extend selected Banner UFC/ACC October PDF rows.

Every added name, brand, and displayed restriction is transcribed from an
identified physical PDF page. This is intentionally a partial selection.
"""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'dist/data.json'
AUDIT=ROOT.parent/'work/banner_acc_pcp_expansion_audit_2026-11-10.json'
SOURCE=('https://www.bannerhealth.com/medicaid/acc/-/media/files/project/bufc/pharmacy/'
        'bufc_formulary_eff10012026_en.pdf?hash=E6E8559DA44F17F2D8DF87A0931DB5B7&sc_lang=en')
PA_SOURCE=('https://www.bannerhealth.com/bhpprovider/-/media/files/project/bhpprovider/'
           'pharmacy/medicaid/prov-bufc_pharmacy-pa-criteria_eff11012026_en.pdf?hash=383206F074F0B301767EC09CEC9F35FA&sc_lang=en')

def main():
    data=json.loads(DATA.read_text())
    meds=data['medications']
    old=[m for m in meds if m['planId']=='banner-ufc']
    assert len(old)==38
    by_id={m['id']:m for m in old}
    corrections=[]
    for i in range(22,29):
        m=by_id[f'banner-oct26-{i:03d}']
        assert m['sourcePage']==11
        m['sourcePage']=10
        corrections.append({'id':m['id'],'change':'PDF page 11 to 10'})
    for i in (15,34):
        m=by_id[f'banner-oct26-{i:03d}']
        assert m['preferred']=='preferred'
        m['preferred']='not_specified'
        corrections.append({'id':m['id'],'change':'preferred to unspecified; printed cell blank'})
    mismatch=by_id['banner-oct26-033']
    assert mismatch['brand']=='LANTUS SOLOSTAR' and mismatch['name']=='INSULIN GLARGINE SUSPENSION'
    meds.remove(mismatch)
    corrections.append({'id':mismatch['id'],'change':'held printed solution/suspension identity mismatch'})
    for m in old:
        if m is not mismatch:
            m['sourceUrl']=SOURCE
            m['validation']='official_acc_pdf_text_reviewed'

    added=[]
    def add(page,category,subcategory,name,brand,preferred='not_specified',pa='not_specified',
            ql='',days='',notes='',pa_text=''):
        added.append({'id':f'banner-pcp-nov10-{len(added)+1:03d}','recordType':'formulary',
          'planId':'banner-ufc','name':name,'brand':brand,'notes':notes,
          'category':category,'subcategory':subcategory,'coverage':'listed',
          'preferred':preferred,'pa':pa,'paText':pa_text or ('PA required' if pa=='required' else ''),
          'step':'not_specified','stepText':'','qlAmount':ql,'qlDays':days,'conditions':[],
          'sourceTitle':'Banner - University Family Care Acute–Long Term Care Drug List',
          'sourceEffective':'2026-10-01','sourcePage':page,'sourceUrl':SOURCE,
          'validation':'official_acc_pdf_text_reviewed'})
    def batch(page,category,subcategory,pairs,preferred='not_specified',pa='not_specified',ql='',days='',notes=''):
        for name,brand in pairs: add(page,category,subcategory,name,brand,preferred,pa,ql,days,notes)

    # PDF pages 10–11: diabetes rows omitted from the initial selection.
    add(10,'Diabetes','Alpha-glucosidase inhibitors','ACARBOSE TABLETS','PRECOSE')
    add(10,'Diabetes','GLP-1 receptor agonists','EXENATIDE SOLN PEN-INJ','BYETTA','preferred','required',notes='Brand only')
    add(10,'Diabetes','Insulin sensitizing agents','PIOGLITAZONE HCL TABLETS','ACTOS')
    batch(10,'Diabetes','Insulins',[
      ('INSULIN LISPRO (HUMAN) SOLUTION PEN INJECTION 100/ML','HUMALOG JUNIOR KWIKPEN'),
      ('INSULIN LISPRO (HUMAN) SOLUTION PEN INJECTION 100/ML','HUMALOG KWIKPEN')],
      preferred='preferred',notes='Authorized generic only')
    batch(11,'Diabetes','Insulins',[
      ('INSULIN NPH ISOPHANE & REG (HUMAN) SUSPENSION','HUMULIN 70/30 KWIKPEN'),
      ('INSULIN REGULAR (HUMAN) SOLUTION','HUMULIN R U-100'),
      ('INSULIN NPH ISOPHANE & REG (HUMAN) SUSPENSION','NOVOLIN 70/30'),
      ('INSULIN NPH (HUMAN) (ISOPHANE) SUSPENSION','NOVOLIN N'),
      ('INSULIN REGULAR (HUMAN) SOLUTION','NOVOLIN R')],preferred='preferred',notes='Brand only')
    add(11,'Diabetes','Insulins','INSULIN REGULAR (HUMAN) SOLUTION PEN-INJECTION','HUMULIN R U-500 KWIKPEN','preferred','required',notes='Brand only')
    batch(11,'Diabetes','Insulins',[
      ('INSULIN ASPART PROTAMINE & ASPART (HUMAN) SUSPENSION (70/30)','NOVOLOG MIX 70/30'),
      ('INSULIN ASPART PROTAMINE & ASPART (HUMAN) SUSPENSION PEN INJECTION (70/30)','NOVOLOG MIX 70/30 FLEXPEN'),
      ('INSULIN ASPART SOLUTION CARTRIDGE','NOVOLOG PENFILL')],preferred='preferred')
    batch(11,'Diabetes','Meglitinides',[
      ('NATEGLINIDE TABLETS','STARLIX'),('REPAGLINIDE TABLETS','PRANDIN')])
    batch(11,'Diabetes','Sulfonylureas',[
      ('GLIMEPIRIDE TABLETS (1MG, 2MG, 4MG)','AMARYL'),
      ('GLIPIZIDE TABLET (EXCLUDING 15MG)','GLUCOTROL'),
      ('GLYBURIDE MICRONIZED TABLETS','GLYNASE'),('GLYBURIDE TABLETS','DIABETA')])

    # PDF pages 6–7: selected asthma/COPD rows with unambiguous table fields.
    batch(6,'Respiratory / Allergy','Bronchodilators - anticholinergics',[
      ('IPRATROPIUM BROMIDE HFA AEROSOL','ATROVENT HFA'),
      ('IPRATROPIUM BROMIDE SOLUTION','IPRATROPIUM BROMIDE'),
      ('TIOTROPIUM BROMIDE MONOHYDRATE AEROSOL SOLUTION','SPIRIVA RESPIMAT'),
      ('TIOTROPIUM BROMIDE MONOHYDRATE CAPSULES','SPIRIVA HANDIHALER'),
      ('UMECLIDINIUM BROMIDE ARSL PWDR-BREATH ACTIVATE','INCRUSE')],preferred='preferred')
    add(6,'Respiratory / Allergy','Leukotriene modifiers','MONTELUKAST SODIUM CHEWABLE TABLETS','SINGULAIR','preferred',ql='30',days='30')
    add(6,'Respiratory / Allergy','Leukotriene modifiers','MONTELUKAST SODIUM TABLETS','SINGULAIR','preferred',ql='30',days='30')
    batch(6,'Respiratory / Allergy','Steroid inhalants',[
      ('BECLOMETHASONE DIPROPIONATE','QVAR REDIHALER'),
      ('BUDESONIDE (INHALATION) SUSPENSION 0.25MG, 0.50MG & 1.0MG','PULMICORT'),
      ('BUDESONIDE INHALATION POWDER','PULMICORT FLEXHALER'),
      ('FLUTICASONE PROPIONATE HFA AERO','VARIOUS'),
      ('MOMETASONE FUROATE HFA','ASMANEX HFA')],preferred='preferred')
    batch(7,'Respiratory / Allergy','Sympathomimetics',[
      ('ALBUTEROL SULFATE NEBULIZED','ALBUTEROL SULFATE'),
      ('ALBUTEROL SULFATE SYRUP','ALBUTEROL SULFATE'),
      ('IPRATROPIUM-ALBUTEROL AEROSOL','COMBIVENT RESPIMAT'),
      ('IPRATROPIUM-ALBUTEROL SOLUTION','DUONEB')],preferred='preferred')
    add(7,'Respiratory / Allergy','Sympathomimetics','BUDESONIDE-FORMOTEROL FUMARATE DIHYDRATE AEROSOL','SYMBICORT','preferred',ql='6',days='90',notes='Authorized generic only')
    add(7,'Respiratory / Allergy','Sympathomimetics','FLUTICASONE-SALMETEROL AEROSOL','AIRDUO RESPICLICK','preferred',ql='6',days='90',notes='Authorized generic only')
    add(7,'Respiratory / Allergy','Sympathomimetics','FLUTICASONE-SALMETEROL AEROSOL','ADVAIR HFA','preferred',ql='3',days='90',notes='Brand only')
    add(7,'Respiratory / Allergy','Sympathomimetics','MOMETASONE FUROATE-FORMOTEROL FUMARATE DIHYDRATE AEROSOL','DULERA','preferred',ql='6',days='90',notes='Brand only')
    add(7,'Respiratory / Allergy','Sympathomimetics','TIOTROPIUM BROMIDE-OLODATEROL HCL AEROSOL SOLUTION','STIOLTO RESPIMAT','preferred','required',ql='1',days='30')
    add(7,'Respiratory / Allergy','Sympathomimetics','UMECLIDINIUM-VILANTEROL AEROSOL POWDER','ANORO ELLIPTA','preferred','required',ql='1',days='30')

    # PDF page 12: lipids. One misspelled rosuvastatin row is held.
    batch(12,'Hypertension / Cardiovascular','HMG CoA reductase inhibitors',[
      ('ATORVASTATIN CALCIUM TABLETS','LIPITOR'),('LOVASTATIN TABLETS','MEVACOR'),
      ('PRAVASTATIN SODIUM TABLETS','PRAVACOL'),('SIMVASTATIN TABLETS','ZOCOR')],
      preferred='preferred',ql='30',days='30')
    add(12,'Hypertension / Cardiovascular','Cholesterol absorption inhibitors','EZETIMIBE TABLETS','ZETIA','preferred','required')

    # PDF page 13: ACE inhibitors and ARBs. Blank preference/PA stays unspecified.
    batch(13,'Hypertension / Cardiovascular','ACE inhibitors',[
      ('BENAZEPRIL HCL TABLETS','BENAZEPRIL HCL'),('ENALAPRIL MALEATE SOLUTION','EPANED'),
      ('ENALAPRIL MALEATE TABLETS','VARIOUS'),('LISINOPRIL TABLETS','ZESTRIL'),
      ('RAMIPRIL CAPSULES','ALTACE')])
    batch(13,'Hypertension / Cardiovascular','Angiotensin II receptor antagonists',[
      ('IRBESARTAN TABLETS','AVAPRO'),('LOSARTAN POTASSIUM TABLETS','COZAAR'),
      ('TELMISARTAN TABLET','MICARDIS'),('VALSARTAN TABLETS','DIOVAN')])

    # PDF pages 20–21: common beta and calcium-channel blockers.
    batch(20,'Hypertension / Cardiovascular','Beta blockers',[
      ('CARVEDILOL TABLETS','COREG'),('LABETALOL HCL TABLETS','TRANDATE'),
      ('ATENOLOL TABLETS','TENORMIN'),('METOPROLOL TARTRATE TABLETS','VARIOUS'),
      ('METOPROLOL SUCCINATE TABLET XL 24-HOUR','VARIOUS'),
      ('PROPRANOLOL HCL TABLETS','VARIOUS')],preferred='preferred')
    add(20,'Hypertension / Cardiovascular','Calcium channel blockers','AMLODIPINE BESYLATE','VARIOUS','preferred',ql='30',days='30')
    batch(20,'Hypertension / Cardiovascular','Calcium channel blockers',[
      ('DILTIAZEM CAPSULE ER','VARIOUS'),('DILTIAZEM TABLETS','VARIOUS')],preferred='preferred')
    add(21,'Hypertension / Cardiovascular','Calcium channel blockers','NIFEDIPINE TABLET ER 24-HOUR','VARIOUS','preferred',ql='30',days='30')
    add(21,'Hypertension / Cardiovascular','Calcium channel blockers','VERAPAMIL HCL CAPSULE SR','VARIOUS','preferred',ql='30',days='30')

    # PDF page 7: selected oral anticoagulants.
    add(7,'Anticoagulation','Coumarin anticoagulants','WARFARIN SODIUM TABLETS','VARIOUS','preferred')
    add(7,'Anticoagulation','Direct factor Xa inhibitors','APIXABAN TABLET','ELIQUIS','preferred',ql='180',days='90',notes='Brand only')
    add(7,'Anticoagulation','Direct factor Xa inhibitors','RIVAROXABAN TABLET','XARELTO','preferred',ql='180',days='90',notes='Brand only')
    add(7,'Anticoagulation','Thrombin inhibitors','DABIGATRAN ETEXILATE MESYLATE CAPSULES','PRADAXA','preferred',ql='60',days='30',notes='Brand only')

    existing={(m['name'],m['brand']) for m in meds if m['planId']=='banner-ufc'}
    assert len(added)==71 and len({(m['name'],m['brand']) for m in added})==len(added)
    assert all((m['name'],m['brand']) not in existing for m in added)
    meds.extend(added)
    total=sum(m['planId']=='banner-ufc' for m in meds)
    assert total==108
    plan=next(p for p in data['plans'] if p['id']=='banner-ufc')
    plan['detail']=(f'{total} selected October 2026 Banner ACC drug-list rows across diabetes, respiratory, '
      'cardiovascular, lipids, and anticoagulation. The full formulary is not imported. '
      'Blank preference or PA cells remain unspecified; exact member benefits still require confirmation.')
    data['planEvidence']=[e for e in data['planEvidence'] if e['id']!='banner-nov26-pa']
    for e in data['planEvidence']:
        if e['id']=='banner-oct26-formulary':
            e['evidence']=(f'{total} selected rows from PDF pages 6–7, 10–13, and 20–21. '
              'The entire drug list is not searchable here; ambiguous insulin and rosuvastatin rows are held.')
            e['sourceUrl']=SOURCE
        if e['id']=='banner-oct26-pa':
            e['topic']='Archived October 2026 pharmacy PA criteria'
            e['evidence']='Historical source; November 2026 criteria are now linked separately and not yet structured.'
    data['planEvidence'].append({'id':'banner-nov26-pa','planId':'banner-ufc',
      'topic':'November 2026 pharmacy PA criteria',
      'evidence':'Official November 1 criteria source identified. Detailed approval and reauthorization criteria are not yet structured or clinician reviewed in this app.',
      'sourcePage':None,'sourceEffective':'2026-11-01','sourceUrl':PA_SOURCE,
      'notes':'Source link for manual policy review.'})
    data['meta']['asOf']='2026-11-10'
    data['meta']['recordCount']=len(meds)
    DATA.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
    AUDIT.write_text(json.dumps({'source':SOURCE,'selection':'partial exact ACC PDF rows',
      'old_rows':38,'corrected':corrections,'added_rows':added,'new_banner_rows':total,
      'held':[{'name':'INSULIN GLARGINE SUSPENSION','brand':'LANTUS SOLOSTAR','page':11},
              {'name':'INSULIN REGULAR (HUMAN) SOLUTION PEN INJECTION','brand':'HUMULIN N KWIKPEN','page':11},
              {'name':'ROUVASTATIN TABLETS','brand':'CRESTOR','page':12},
              {'name':'GLIPIZIDE TABLET 24-HOUR','brand':'GLUCATROL XL','page':11}]},indent=2)+'\n')
    print({'added':len(added),'banner':total,'site':len(meds),'corrections':len(corrections)})

if __name__=='__main__':main()

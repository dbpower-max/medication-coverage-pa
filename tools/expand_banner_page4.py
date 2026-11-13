"""Verified partial Banner ACC October 2026 release, physical PDF page 4.

Transcribed against the ACC-linked PDF text and visually checked in the PDF
viewer on 2026-11-10. Blank cells stay unspecified. No state-list carry-forward.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ('https://www.bannerhealth.com/medicaid/acc/-/media/files/project/bufc/pharmacy/'
          'bufc_formulary_eff10012026_en.pdf?hash=E6E8559DA44F17F2D8DF87A0931DB5B7&sc_lang=en')
PA = ('PA REQUIRED for Ages < 6 years. PA REQUIRED for > 1 Anxiolytic '
      'Medication in a 30-day time period.')

def main():
    path = ROOT / 'dist/data.json'
    data = json.loads(path.read_text())
    before = json.loads(path.read_text())
    added = []

    def add(category, subcategory, name, brand, pa='not_specified', ql='', days='', pa_text=''):
        added.append(dict(id=f'banner-page4-nov10-{len(added)+1:03d}',
            recordType='formulary', planId='banner-ufc', name=name, brand=brand,
            notes='', category=category, subcategory=subcategory, coverage='listed',
            preferred='not_specified', pa=pa, paText=pa_text or ('PA REQUIRED' if pa=='required' else ''),
            step='not_specified', stepText='', qlAmount=ql, qlDays=days, conditions=[],
            sourceTitle='Banner - University Family Care Acute–Long Term Care Drug List',
            sourceEffective='2026-10-01', sourcePage=4, sourceUrl=SOURCE,
            validation='official_acc_pdf_text_and_visual_reviewed'))

    for name, brand, sub in [
        ('HYDROCORTISONE (INTRARECTAL) ENEMA','COLOCORT','Intrarectal steroids'),
        ('HYDROCORTISONE ACETATE (INTRARECTAL) FOAM','CORTIFOAM','Intrarectal steroids'),
        ('HYDROCORTISONE (RECTAL) CREAM','VARIOUS','Rectal steroids')]:
        add('Gastrointestinal', sub, name, brand)
    for name, brand, pa in [
        ('ALBENDAZOLE TABLETS','ALBENZA','required'),
        ('IVERMECTIN TABLETS','STROMECTOL','required'),
        ('PRAZIQUANTEL TABLETS','BILTRICIDE','not_specified')]:
        add('Infectious Disease','Anthelmintics',name,brand,pa)
    add('Hypertension / Cardiovascular','Antianginals - other',
        'RANOLAZINE TABLET 12-HOUR','RANEXA','required')
    for name, brand in [
        ('ISOSORBIDE DINITRATE CAPSULE CONTROLLED RELEASE','DILATRATE SR'),
        ('ISOSORBIDE DINITRATE SUBLINGUAL','ISOSORBIDE DINITRATE'),
        ('ISOSORBIDE DINITRATE TABLETS','ISORDIL TITRADOSE'),
        ('ISOSORBIDE DINITRATE TABLET CONTROLLED RELEASE','ISOSORBIDE DINITRATE ER'),
        ('ISOSORBIDE MONONITRATE TABLETS','ISOSORBIDE MONONITRATE'),
        ('ISOSORBIDE MONONITRATE TABLET 24-HOUR','IMDUR'),
        ('NITROGLYCERIN CAPSULE CONTROLLED RELEASE','NITRO-TIME'),
        ('NITROGLYCERIN OINTMENT','NITRO-BID'),
        ('NITROGLYCERIN PATCH 24-HOUR','NITRO-DUR'),
        ('NITROGLYCERIN SUBLINGUAL','NITROSTAT')]:
        add('Hypertension / Cardiovascular','Nitrates',name,brand)
    for strength, ql in [('5','120'),('7.5','120'),('10','120'),('15','120'),('30','60')]:
        add('Mental Health / Neurology','Antianxiety agents - misc.',
            f'BUSPIRONE HCL TAB {strength} MG','BUSPIRONE HCL','conditional',ql,'30',PA)
    for name, brand, ql in [
        ('HYDROXYZINE HCL SYRUP','HYDROXYZINE SYRUP','300'),
        ('HYDROXYZINE HCL TABLETS','HYDROXYZINE TABLETS','240'),
        ('HYDROXYZINE PAMOATE CAPSULES','VISTARIL','120')]:
        add('Mental Health / Neurology','Antianxiety agents - misc.',name,brand,ql=ql,days='30')

    old = [m for m in data['medications'] if m['planId']=='banner-ufc']
    assert len(old)==108 and len(added)==25
    existing = {(m['name'],m['brand']) for m in old}
    assert all((m['name'],m['brand']) not in existing for m in added)
    assert len({(m['name'],m['brand']) for m in added})==25
    data['medications'].extend(added)
    total = 133
    plan = next(p for p in data['plans'] if p['id']=='banner-ufc')
    plan['detail']=(f'{total} selected October 2026 Banner ACC drug-list rows across diabetes, respiratory, '
        'cardiovascular, lipids, anticoagulation, gastrointestinal, infectious disease, and anxiety medications. '
        'The full formulary is not imported. Blank preference or PA cells remain unspecified; '
        'exact member benefits still require confirmation.')
    evidence = next(e for e in data['planEvidence'] if e['id']=='banner-oct26-formulary')
    evidence['evidence']=(f'{total} selected rows from PDF pages 4, 6–7, 10–13, and 20–21. '
        'The entire drug list is not searchable here; ambiguous insulin, rosuvastatin, and glipizide rows remain held. '
        'Page 4 release preserves conditional PA and quantity limits; blank cells are unspecified.')
    data['meta']['recordCount']=len(data['medications'])
    for m in added:
        if m['subcategory'] not in data['subcategories'][m['category']]:
            data['subcategories'][m['category']].append(m['subcategory'])
            data['subcategories'][m['category']].sort()
    assert data['medications'][:len(before['medications'])]==before['medications']
    assert data['policies']==before['policies']
    assert len(data['medications'])==4248
    assert len({m['id'] for m in data['medications']})==4248
    path.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
    audit={'date':'2026-11-10','source':SOURCE,'effective':'2026-10-01','revised':'2026-10-06',
        'source_page':4,'verification':'ACC member-page link, PDF text, and visual PDF table review',
        'archive_status':'Direct download HTTP 403; archive and SHA-256 pending',
        'old_banner_rows':108,'new_banner_rows':133,'added_count':25,'site_medication_count':4248,
        'existing_medications_preserved':True,'blank_cells':'not_specified, never no-PA',
        'conflict_review':'Ingredient searches found no differing exact-product listings for this selection; distinct formulations retained separately.',
        'conflict_rule':'Least favorable coverage/preference, higher tier, union of restrictions; link all differing listings.',
        'held_prior_rows_unchanged':['LANTUS SOLOSTAR formulation mismatch','HUMULIN N KWIKPEN formulation mismatch',
            'ROUVASTATIN TABLETS spelling','GLUCATROL XL reference-brand spelling'],
        'added_rows':added}
    out=ROOT/'audits/banner_acc_page4_batch_2026-11-10.json'
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    print({'added':25,'banner':133,'site':4248,'preserved':len(before['medications'])})

if __name__=='__main__':
    main()

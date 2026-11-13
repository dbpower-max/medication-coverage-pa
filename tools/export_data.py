#!/usr/bin/env python3
"""Export the source-linked SQLite prototype into a browser-safe static dataset."""

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = Path('/workspace/scratch/1bb2343635da/ahcccs_importer/medication_coverage_v0.11.sqlite')
OUT = ROOT / 'dist' / 'data.json'

# Reviewed title/section matches only. Links expose an exact-plan policy source,
# not structured or clinician-approved approval criteria.
UHC_POLICY_TARGETS = (
    ('GLP-1 Agonists', 'GL-631216', '2026-07-01', ('TRULICITY', 'OZEMPIC', 'VICTOZA')),
    ('SGLT-2 Inhibitors', 'GL-604198', '2026-06-01', ('JARDIANCE', 'FARXIGA')),
    ('Continuous Blood Glucose Monitoring Devices (CGM)', 'GL-503307', '2026-02-01', ('FREESTYLE LIBRE', 'DEXCOM G6', 'DEXCOM G7')),
    ('Breztri, Trelegy Ellipta', 'GL-647200', '2026-08-01', ('BREZTRI AEROSPHERE', 'TRELEGY ELLIPTA')),
    ('Inhaled Corticosteroids', 'GL-605215', '2026-06-01', ('ALVESCO',)),
    ('Wegovy (semaglutide)', 'GL-523190', '2026-03-01', ('WEGOVY',)),
)


CATEGORY_RULES = [
    ('Diabetes', (
        'ANTIDIABETIC', 'BIGUANIDE', 'DIPEPTIDYL', 'DPP-4', 'SGLT', 'INCRETIN',
        'SULFONYLUREA', 'ALPHA-GLUCOSIDASE', 'MEGLITINIDE', 'INSULIN SENSITIZING',
        'DIABETIC ', 'INSULIN', 'GLP-1', 'CONTINUOUS GLUCOSE', 'CGM',
    )),
    ('Anticoagulation', (
        'ANTICOAGUL', 'DIRECT FACTOR XA', 'HEPARIN', 'THROMBIN INHIBITOR',
        'COUMARIN', 'PLATELET AGGREGATION',
    )),
    ('Lipid Management', (
        'HMG COA', 'BILE ACID SEQUESTRANT', 'FIBRIC ACID', 'NICOTINIC ACID',
        'CHOLESTEROL ABSORPTION', 'LIPID',
    )),
    ('Hypertension / Cardiovascular', (
        'ACE INHIBITOR', 'ANGIOTENSIN', 'BETA BLOCKER', 'CALCIUM CHANNEL',
        'DIURETIC', 'ALDOSTERONE', 'ANTIHYPERTENSIVE', 'ANTIARRHYTH', 'ANTIANGINAL',
        'CARDIAC GLYCOSIDE', 'NITRATE', 'VASODILATOR', 'ALPHA-BETA',
        'PULMONARY HYPERTENSION', 'CARDIOVASCULAR', 'MACE', 'HEART FAILURE',
    )),
    ('Respiratory / Allergy', (
        'ASTHMA', 'BRONCHODILATOR', 'STEROID INHALANT', 'LEUKOTRIENE',
        'SYMPATHOMIMETIC', 'ANTIHISTAMINE', 'COUGH', 'EXPECTORANT', 'ANTITUSSIVE',
        'NASAL ', 'ANAPHYLAXIS', 'PULMONARY FIBROSIS', 'CYSTIC FIBROSIS',
        'RESPIRATORY', 'BREZTRI', 'TRELEGY', 'INHALER',
    )),
    ('Gastrointestinal', (
        'PROTON PUMP', 'H-2 ', 'ANTI-ULCER', 'LAXATIVE', 'GASTRO', 'INFLAMMATORY BOWEL',
        'IRRITABLE BOWEL', 'ANTIPERISTALTIC', 'DIGESTIVE ENZYME', 'GALLSTONE',
        'BILE ', 'INTRARECTAL', 'RECTAL STEROID', 'ANTIEMETIC', '5-HT3', 'NK1',
    )),
    ('Genitourinary', (
        'URINARY', 'PROSTATIC', 'INTERSTITIAL CYSTITIS', 'PHOSPHATE BINDER',
        'POTASSIUM REMOVING',
    )),
    ('Thyroid / Endocrine', (
        'THYROID', 'ANTITHYROID', 'GROWTH HORMONE', 'PITUITARY', 'ANDROGEN',
        'MINERALOCORTICOID', 'SOMATOMEDIN', 'METABOLIC MODIFIER',
    )),
    ('Mental Health / Neurology', (
        'ANTIDEPRESS', 'SSRI', 'SNRI', 'TRICYCLIC', 'BENZODIAZEPINE', 'ANTIANXIETY',
        'ANTIPSYCHOTIC', 'ANTIMANIC', 'ADHD', 'AMPHETAMINE', 'STIMULANT',
        'ANTICONVULSANT', 'HYDANTOIN', 'VALPROIC', 'SUCCINIMIDE', 'GABA',
        'BARBITURATE', 'HYPNOTIC', 'PARKINSON', 'ANTIDEMENTIA', 'MULTIPLE SCLEROSIS',
        'MIGRAINE', 'CGRP', 'SEROTONIN', 'NMDA', 'FRIEDRICH',
    )),
    ('Infectious Disease', (
        'ANTIBIOTIC', 'AMINOGLYCOSIDE', 'PENICILLIN', 'CEPHALOSPORIN', 'AZITHROMYCIN',
        'CLARITHROMYCIN', 'TETRACYCLINE', 'SULFONAMIDE', 'OXAZOLIDINONE',
        'FLUOROQUINOLONE', 'FIDAXOMICIN', 'ANTI-INFECTIVE', 'ANTIVIRAL', 'HERPES',
        'INFLUENZA', 'HEPATITIS', 'CMV', 'ANTIRETROVIRAL', 'ANTIFUNGAL',
        'ANTIMALARIAL', 'ANTHELMINTIC', 'LEPROSTATIC', 'MYCOBACTERIAL',
    )),
    ('Pain / Musculoskeletal', (
        'ANALGESIC', 'NSAID', 'NONSTEROIDAL ANTI-INFLAMMATORY', 'OPIOID',
        'MUSCLE RELAXANT', 'GOUT', 'URICOSURIC', 'SALICYLATE', 'BONE DENSITY',
        'ANTIRHEUMATIC',
    )),
    ('Dermatology', (
        'TOPICAL', 'ACNE', 'ECZEMA', 'ROSACEA', 'ANTISEBORRHEIC', 'KERATOLYTIC',
        'SCABICIDE', 'PEDICULICIDE', 'BURN PRODUCT',
    )),
    ('Reproductive Health', (
        'CONTRACEPT', 'ESTROGEN', 'PROGESTIN', 'OXYTOCIC', 'VAGINAL', 'PRENATAL',
        'HORMONE RECEPTOR', 'LHRH', 'GNRH',
    )),
    ('Hematology / Oncology', (
        'ANTINEOPLAST', 'ALKYLATING', 'ANTIMETABOLITE', 'MITOTIC', 'CHEMOTHERAPY',
        'HEMATOPOIETIC', 'HEMOSTATIC', 'SICKLE CELL', 'IMMUNE GLOBULIN',
    )),
    ('Ophthalmic / Otic', ('OPHTHALMIC', 'OTIC ', 'MIOTIC', 'CYCLOPLEGIC')),
    ('Immunology / Specialty', (
        'IMMUNOMODULATOR', 'IMMUNOSUPPRESS', 'MONOCLONAL', 'INTERLEUKIN',
        'CYTOKINE', 'ROCK2', 'HEREDITARY ANGIOEDEMA', 'GAUCHER',
    )),
]


def category_for(*values):
    text = ' '.join(str(v or '') for v in values).upper()
    for category, tokens in CATEGORY_RULES:
        if any(token in text for token in tokens):
            return category
    return 'Other'


def rows_as_dicts(cursor):
    return [dict(row) for row in cursor.fetchall()]


def main():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row

    sources = {r['id']: dict(r) for r in db.execute('SELECT * FROM sources')}
    latest = db.execute("""SELECT id,effective_date FROM sources
        WHERE kind='drug_list' ORDER BY effective_date DESC,id DESC LIMIT 1""").fetchone()

    conditions = {}
    for row in db.execute('SELECT * FROM formulary_conditions'):
        conditions.setdefault(row['formulary_entry_id'], []).append({
            'type': row['condition_type'],
            'operator': row['comparison_operator'],
            'threshold': row['threshold_value'],
            'unit': row['threshold_unit'],
            'action': row['action'],
            'sourceText': row['source_text'],
            'validation': row['validation_status'],
        })

    medications = []
    query = """SELECT f.* FROM formulary_entries f
        WHERE f.source_id=? ORDER BY f.raw_drug_name,f.raw_brand,f.source_page,f.source_row"""
    for row in db.execute(query, (latest['id'],)):
        subcategory = row['class_name'] or 'Unclassified formulary row'
        category = category_for(subcategory, row['raw_drug_name'], row['raw_brand'])
        source = sources[row['source_id']]
        medications.append({
            'id': f"formulary-{row['id']}",
            'recordType': 'formulary',
            'planId': 'ahcccs-statewide',
            'name': row['raw_drug_name'],
            'brand': row['raw_brand'] or '',
            'notes': row['raw_notes'] or '',
            'category': category,
            'subcategory': subcategory,
            'coverage': row['coverage_status'],
            'preferred': row['preferred_status'],
            'pa': row['pa_status'],
            'paText': row['pa_text'] or '',
            'step': row['step_status'],
            'stepText': row['step_text'] or '',
            'qlAmount': row['ql_amount'] or '',
            'qlDays': row['ql_days'] or '',
            'conditions': conditions.get(row['id'], []),
            'sourceTitle': 'AHCCCS Acute - Long Term Care Drug List',
            'sourceEffective': source['effective_date'],
            'sourcePage': row['source_page'],
            'sourceUrl': source['official_url'],
            'validation': 'source_row',
        })

    uhc_plan = db.execute("SELECT id FROM plans WHERE name='UnitedHealthcare Community Plan - Arizona'").fetchone()['id']
    uhc_guideline = next(s for s in sources.values() if s['kind'] == 'plan_pa_guidelines'
                         and s['scope'] == 'UnitedHealthcare Community Plan of Arizona Medicaid')
    uhc_sections = {r['title']: dict(r) for r in db.execute(
        'SELECT * FROM policy_sections WHERE source_id=?', (uhc_guideline['id'],))}
    assert all(title in uhc_sections for title, _, _, _ in UHC_POLICY_TARGETS)

    def exact_plan_policy(name):
        upper = name.upper()
        for title, code, effective, prefixes in UHC_POLICY_TARGETS:
            if any(upper.startswith(prefix) for prefix in prefixes):
                section = uhc_sections[title]
                return {'title': title, 'policyCode': code, 'effective': effective,
                        'firstPage': section['first_page'], 'lastPage': section['last_page'],
                        'url': uhc_guideline['official_url']}
        return None

    query = """SELECT f.*,m.listing_group,m.tier,m.diagnosis_required,m.specialty,
        m.age_limited,m.quantity_limited,m.raw_restrictions,m.extraction_status
        FROM formulary_entries f JOIN formulary_plan_metadata m ON m.formulary_entry_id=f.id
        WHERE f.plan_id=? AND m.extraction_status='source_verified'
        ORDER BY f.raw_drug_name,f.source_page,f.source_row"""
    for row in db.execute(query, (uhc_plan,)):
        subcategory = row['class_name'] or 'Selected exact-plan record'
        category = category_for(subcategory, row['raw_drug_name'])
        source = sources[row['source_id']]
        conflict = json.loads(row['raw_row_json']).get('source_conflict', '')
        medications.append({
            'id': f"uhc-formulary-{row['id']}",
            'recordType': 'formulary',
            'planId': 'uhc-community-az',
            'name': row['raw_drug_name'],
            'brand': row['raw_brand'] or '',
            'notes': row['raw_notes'] or '',
            'category': category,
            'subcategory': subcategory,
            'coverage': row['coverage_status'],
            'preferred': 'not_specified' if conflict else row['listing_group'],
            'sourceConflict': conflict,
            'policySource': exact_plan_policy(row['raw_drug_name']),
            'tier': row['tier'] or '',
            'pa': row['pa_status'],
            'paText': row['pa_text'] or '',
            'step': 'not_specified' if conflict else row['step_status'],
            'stepText': '' if conflict else row['step_text'] or '',
            'qlAmount': '' if conflict else row['ql_amount'] or '',
            'qlDays': '' if conflict else row['ql_days'] or '',
            'ageLimited': bool(row['age_limited']),
            'specialty': bool(row['specialty']),
            'diagnosisRequired': bool(row['diagnosis_required']),
            'rawRestrictions': row['raw_restrictions'],
            'conditions': [],
            'sourceTitle': 'UnitedHealthcare Community Plan of Arizona Preferred Drug List',
            'sourceEffective': source['effective_date'],
            'sourcePage': row['source_page'],
            'sourceUrl': source['official_url'],
            'validation': row['extraction_status'],
        })

    policies = []
    for row in db.execute('SELECT * FROM validated_policy_summaries ORDER BY policy_title,first_page,stage'):
        source = sources[row['guideline_source_id']]
        category = category_for(row['policy_title'], row['product_scope'], row['indication'], row['search_terms'])
        policies.append({
            'id': f"policy-{row['id']}",
            'recordType': 'policy',
            'planId': 'ahcccs-statewide',
            'name': row['product_scope'],
            'brand': '',
            'category': category,
            'subcategory': row['policy_title'],
            'coverage': 'explicit_not_covered' if row['indication'] == 'Weight loss' else 'policy_only',
            'preferred': 'not_specified',
            'pa': 'required',
            'paText': row['criteria_summary'],
            'step': 'not_specified',
            'stepText': '',
            'qlAmount': '',
            'qlDays': '',
            'indication': row['indication'] or '',
            'stage': row['stage'],
            'approvalDuration': row['approval_duration'] or '',
            'conditions': [],
            'sourceTitle': row['policy_title'],
            'sourceEffective': row['policy_effective_date'],
            'sourcePage': row['first_page'],
            'sourceLastPage': row['last_page'],
            'sourceUrl': source['official_url'],
            'validation': row['validation_status'],
        })

    uhc_count = sum(record['planId'] == 'uhc-community-az' for record in medications)
    uhc_guideline = db.execute("""SELECT s.* FROM sources s
        JOIN plan_sources ps ON ps.source_id=s.id
        WHERE ps.plan_id=? AND ps.role='exact_plan_policy_index'""", (uhc_plan,)).fetchone()
    for row in db.execute('SELECT * FROM policy_sections WHERE source_id=? ORDER BY title', (uhc_guideline['id'],)):
        category = category_for(row['title'])
        policies.append({
            'id': f"uhc-policy-index-{row['id']}",
            'recordType': 'policy_index',
            'planId': 'uhc-community-az',
            'name': row['title'],
            'brand': '',
            'category': category,
            'subcategory': 'Clinical pharmacy policy index',
            'coverage': 'policy_index',
            'preferred': 'not_specified',
            'tier': '',
            'pa': 'not_specified',
            'paText': 'An exact-plan policy section is indexed. Detailed criteria are not yet structured or clinician-reviewed in this application.',
            'step': 'not_specified',
            'stepText': '',
            'qlAmount': '',
            'qlDays': '',
            'conditions': [],
            'sourceTitle': f"UnitedHealthcare Community Plan of Arizona clinical guideline: {row['title']}",
            'sourceEffective': '',
            'sourcePage': row['first_page'],
            'sourceLastPage': row['last_page'],
            'sourceUrl': uhc_guideline['official_url'],
            'validation': 'source_index',
        })

    azch_plan = db.execute(
        "SELECT id FROM plans WHERE name='Arizona Complete Health - Complete Care'"
    ).fetchone()['id']
    for row in db.execute(
        'SELECT * FROM plan_policy_index WHERE plan_id=? ORDER BY title', (azch_plan,)
    ):
        category = category_for(row['title'])
        policies.append({
            'id': f"azch-policy-index-{row['id']}",
            'recordType': 'policy_index',
            'planId': 'az-complete-health',
            'name': row['title'],
            'brand': '',
            'category': category,
            'subcategory': 'Plan-specific policy index',
            'coverage': 'policy_index',
            'preferred': 'not_specified',
            'tier': '',
            'pa': 'not_specified',
            'paText': 'Official plan-specific policy source identified. Detailed criteria are not yet structured or clinician-reviewed. This does not establish medication coverage.',
            'step': 'not_specified',
            'stepText': '',
            'qlAmount': '',
            'qlDays': '',
            'conditions': [],
            'sourceTitle': f"{row['policy_code']} · {row['title']}",
            'sourceEffective': row['review_date'] or '',
            'sourcePage': 1,
            'sourceLastPage': row['page_count'],
            'sourceUrl': row['official_url'],
            'validation': 'source_index',
        })

    plan_name_to_id = {
        'Arizona Complete Health - Complete Care': 'az-complete-health',
        'Banner-University Family Care - ACC': 'banner-ufc',
        'UnitedHealthcare Community Plan - Arizona': 'uhc-community-az',
        'Banner Medicare Advantage Dual HMO D-SNP': 'banner-medicare-dual-dsnp',
    }
    evidence = []
    for row in db.execute('''SELECT e.*,p.name plan_name,s.effective_date,s.official_url
        FROM plan_evidence e JOIN plans p ON p.id=e.plan_id JOIN sources s ON s.id=e.source_id
        ORDER BY p.name,e.source_page'''):
        evidence.append({
            'id': row['id'],
            'planId': plan_name_to_id[row['plan_name']],
            'topic': row['topic'],
            'evidence': row['evidence_text'],
            'sourcePage': row['source_page'],
            'sourceEffective': row['effective_date'],
            'sourceUrl': row['official_url'],
            'notes': row['notes'],
        })

    evidence.extend([
        {
            'id': 'uhc-exact-formulary-release',
            'planId': 'uhc-community-az',
            'topic': 'Selected exact-plan medication records',
            'evidence': f'{uhc_count:,} selected source-row-verified entries are loaded from the July 1, 2026 Arizona Medicaid drug list. This includes 638 additional complete rows independently checked and four wrapped presentations visually checked for exact column, tier, and restrictions. Other wrapped and complex entries remain unimported, so this is not the complete UHC formulary.',
            'sourcePage': 1,
            'sourceEffective': '2026-07-01',
            'sourceUrl': sources[next(r['source_id'] for r in db.execute("SELECT source_id FROM plan_sources WHERE plan_id=? AND role='exact_plan_formulary'", (uhc_plan,)))]['official_url'],
            'notes': 'Selected direct source rows; not a patient-specific benefit check.',
        },
        {
            'id': 'uhc-machine-readable-inventory',
            'planId': 'uhc-community-az',
            'topic': '2026 machine-readable drug inventory · comparison source',
            'evidence': 'UHC publishes RxNorm-coded drug and plan records. Its PA and step-therapy flags conflict with the dated PDF for some products, including Tezspire. These JSON records are not presented here as verified coverage.',
            'sourcePage': None,
            'sourceEffective': '',
            'sourceUrl': 'https://legacy.providerlookuponline.com/mrf/optumrx/drugs/2877216/JSON_Drugs_UHCCPAZ.json',
            'notes': 'Candidate inventory only; not a member-specific benefit or PA result.',
        },
        {
            'id': 'uhc-policy-index-release',
            'planId': 'uhc-community-az',
            'topic': 'Full clinical-policy index',
            'evidence': '444 exact-plan policy sections are searchable by title. Detailed criteria remain unstructured and are not presented as coverage determinations.',
            'sourcePage': 1,
            'sourceEffective': '',
            'sourceUrl': uhc_guideline['official_url'],
            'notes': 'Policy discovery only.',
        },
    ])
    evidence_by_kind = {
        'formulary_machine_readable': 'Historical 2022 snapshot (4,454 records). Not valid as current plan coverage; no 2026 medication rows imported from it.',
        'statewide_reference': 'Dated September 2026 AHCCCS statewide reference. Search it separately; it is not proof of this plan’s exact benefit.',
        'plan_update_notice': 'Dated plan update notice. Notices highlight selected changes and do not form a complete change feed.',
        'behavioral_health_special_scope': 'Special-scope behavioral health list; eligibility-specific, not the general Complete Care formulary.',
        'pharmacy_source_hub': 'Official plan pharmacy source hub. Check current sources and verify patient-specific benefits.',
    }
    for row in db.execute('''SELECT i.*,p.name plan_name FROM identified_plan_sources i
        JOIN plans p ON p.id=i.plan_id ORDER BY p.name,
        CASE i.kind WHEN 'statewide_reference' THEN 0 WHEN 'plan_update_notice' THEN 1
        WHEN 'behavioral_health_special_scope' THEN 2 WHEN 'pharmacy_source_hub' THEN 3 ELSE 4 END,
        i.effective_date DESC'''):
        evidence.append({
            'id': f"identified-{row['id']}",
            'planId': plan_name_to_id[row['plan_name']],
            'topic': row['title'],
            'evidence': evidence_by_kind.get(row['kind'], 'Official source identified; medication records are not yet imported.'),
            'sourcePage': None,
            'sourceEffective': row['effective_date'] or '',
            'sourceUrl': row['official_url'],
            'notes': row['notes'],
        })

    plans = [
        {
            'id': 'ahcccs-statewide',
            'name': 'AHCCCS statewide reference',
            'market': 'Arizona Medicaid',
            'status': 'loaded',
            'detail': 'Full statewide drug-list rows plus the source-verified priority PA summaries.',
        },
        {
            'id': 'az-complete-health',
            'name': 'Arizona Complete Health - Complete Care',
            'market': 'AHCCCS managed care',
            'status': 'policy_sources_indexed',
            'detail': 'September 2026 statewide reference and dated plan notices are linked below. The preserved 2022 JSON is historical, and the update notices are not exhaustive. Eleven plan policy sources are indexed, but no complete current exact-plan medication coverage is loaded.',
        },
        {
            'id': 'banner-ufc',
            'name': 'Banner - University Family Care ACC',
            'market': 'AHCCCS managed care',
            'status': 'partial',
            'detail': 'Only CGM preferred-product evidence is loaded. Full plan coverage is not loaded.',
        },
        {
            'id': 'uhc-community-az',
            'name': 'UnitedHealthcare Community Plan - Arizona',
            'market': 'AHCCCS managed care',
            'status': 'selected_records_loaded',
            'detail': f'{uhc_count:,} selected PDF-verified medication entries and the 444-section policy index are searchable. Four exact wrapped presentations have been visually checked. UHC’s 2026 JSON is a comparison source; its PA flags differ from the PDF for some drugs and are not used for coverage answers. Other wrapped or complex PDF rows are still missing. This is not the complete formulary.',
            'effective': 'Selected drug-list rows effective 2026-07-01',
        },
        {
            'id': 'banner-medicare-dual-dsnp',
            'name': 'Banner Medicare Advantage Dual HMO D-SNP',
            'market': 'Medicare Advantage prescription drug · Pima County',
            'status': 'source_identified',
            'detail': 'Official September 2026 formulary, prior-authorization, and step-therapy sources are identified. Medication records are not yet loaded.',
            'effective': 'Official sources effective 2026-09-01',
        },
        {
            'id': 'medicare',
            'name': 'Medicare - exact Part D or MA-PD plan required',
            'market': 'Medicare',
            'status': 'not_loaded',
            'detail': 'Medicare is not one formulary. Exact Part D or Medicare Advantage prescription-plan data must be loaded before coverage can be verified.',
        },
    ]

    all_records = medications + policies
    categories = sorted({record['category'] for record in all_records})
    subcategories = {
        category: sorted({record['subcategory'] for record in all_records if record['category'] == category})
        for category in categories
    }
    payload = {
        'meta': {
            'title': 'Medication Coverage Search',
            'asOf': '2026-09-24',
            'drugListEffective': latest['effective_date'],
            'recordCount': len(medications),
            'policyCount': len(policies),
            'scopeWarning': 'Static source reference only. Confirm the exact plan and current benefit before making a prescribing decision.',
        },
        'plans': plans,
        'categories': categories,
        'subcategories': subcategories,
        'medications': medications,
        'policies': policies,
        'planEvidence': evidence,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')))
    print(json.dumps({
        'output': str(OUT),
        'medications': len(medications),
        'policies': len(policies),
        'categories': len(categories),
        'planEvidence': len(evidence),
    }))


if __name__ == '__main__':
    main()

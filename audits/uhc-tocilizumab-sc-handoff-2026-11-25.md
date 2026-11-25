# UHC exact-plan tocilizumab SC evidence handoff — 2026-11-25

**Read-only evidence batch, not a production change or clinical approval.** DEC-05/12/13/14/19/20; DEC-07/09 and DATA-01 preview-only gate preserved. Base main 42a5ed637c9413de631039a86c0dc60edc6db3ca. Other worker holds shared ledger and Banner release; this branch is disjoint. Coordinator must reconcile before changing shared rows and remove/archive this handoff after incorporation. No release, renderer test, or payer adjudication claimed.

## Exact records

| Audit row | Record ID | October 1, 2026 UHC PDL | Scoped evidence |
|---|---|---|---|
| RFA6660 | uhc-oct-complete-6e31fd16d0c3fee4 | ACTEMRA SUBCUTANEOUS, p170, source position 2438, Tier 2; PA; SP; QL; nonpreferred in scoped data | GL-565279 expressly names Actemra SC and Actemra Actpen. Preserve SC route and keep 162 mg/0.9 mL syringe vs ACTPen device separately identifiable; do not attach IV criteria. Nonpreferred biosimilar-failure condition applies to this row's recorded preference; verify current exact device/package preference before splitting. |
| RFA7033 | uhc-oct-complete-2e1049037c5dbd67 | AVTOZMA SUBCUTANEOUS, p182, source position 2724, Tier 2; PA; SP; QL; preferred in scoped data | GL-565279 expressly names Avtozma SC, added in 2026-04-06 revision, effective 2026-05-01. Preserve preferred status and omit nonpreferred-only failure criterion from preferred branch. Keep exact device/package coverage unresolved. |

PDL source: https://dbpower-max.github.io/medication-coverage-pa/sources/uhc-az-medicaid-pdl-2026-10-01.pdf#page=170 and #page=182. Archived exact November 1, 2026 guideline index: `audits/november_policy_index_2026_11_12/uhc-nov2026/sections.json`, blob 31b87d0ec1dff42946623a96b918e4128f536fc9. Exact plan Arizona Medicaid – Community & State. Named guideline: https://dbpower-max.github.io/medication-coverage-pa/sources/uhc-az-clinical-pharmacy-2026-11-01.pdf#page=1728 ; text `dist/policy-text/uhc-nov2026/gl-565279.txt`, blob 8cb7ed0a4683c8f333ef66aa5729f3bb232602ae. Supersedes the earlier RFA6660 candidate GL-512191, not a retroactive assertion about that older policy.

## Seven source branches (each names SC products)

All seven: 12 months; preferred authorization group AZTOCILIZU; for nonpreferred also GPI-12 product authorization. These are payer rules, not a claim that a particular NDC or patient is approved. Nonpreferred branch additionally requires failure of all preferred tocilizumab biosimilars. Keep QL and therapeutic-duplication review separate; GL-140667 is administrative override criteria, not a numeric QL.

- RA initial pp1728–1729: medical records or paid claims establish moderate–severe active RA and a 3-month nonbiologic DMARD trial at maximum indicated dose in past 6 months, unless contraindicated or clinically significant adverse effects; rheumatologist involvement.
- PJIA initial pp1729–1730: moderate–severe active PJIA, at least 6 weeks of leflunomide or methotrexate at maximum tolerated dosage with failure/contraindication/intolerance; rheumatologist involvement.
- SJIA initial pp1730–1731: active SJIA and failure/contraindication/intolerance of one conventional therapy, at maximum tolerated dosage: methotrexate (3 months), NSAID (1 month), or systemic glucocorticoid (2 weeks); rheumatologist involvement.
- GCA initial pp1731–1732: GCA and glucocorticoid failure/contraindication/intolerance; rheumatologist involvement.
- RA/PJIA/SJIA/GCA renewal pp1732–1733: chart evidence of positive clinical response and rheumatologist involvement.
- SSc-ILD initial pp1733–1734: chart evidence of active systemic sclerosis with proximal finger skin thickening OR two specified systemic sclerosis findings (finger skin thickening, fingertip lesions, telangiectasia, abnormal nailfold capillaries, PAH, Raynaud's, or relevant autoantibodies), AND HRCT fibrosis involving at least 10% of lungs, with pulmonologist involvement.
- SSc-ILD renewal pp1734–1735: chart evidence of positive response and pulmonologist involvement.

## Label / device safeguards

- Actemra label dated Dec 19, 2025, version 53: https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=2e5365ff-cb2a-4b16-b2c7-e35c6bf2de13&version=53 ; 162 mg/0.9 mL SC prefilled syringe SCD 1441527 / SBD 1441530; ACTPen SCD 2106073 / SBD 2106075. SSc-ILD adult SC dosing is labeled, but ACTPen use has not been studied for this indication and IV is not approved for SSc-ILD.
- Avtozma (tocilizumab-anoh) current SPL indications section dated Oct 7, 2026: https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=581c288f-8015-40ef-a4c3-683c96db193d ; 162 mg/0.9 mL SC syringe SCD 2705425 / SBD 2705432; autoinjector SCD 2705435 / SBD 2705439. SC package family 72606-045 (label association only; payer NDC coverage unverified). Label lists RA, GCA, PJIA, SJIA, CRS and COVID-19, NOT SSc-ILD. Display SSc-ILD as named payer pathway, explicitly not labeled for Avtozma; do not transfer Actemra label indications to biosimilar. CRS/COVID-19 IV-only, not SC. No automatic product substitution or clinical approval. RxCUIs are SPL-linked; current NLM status independent check remains outstanding if required for catalog migration.

## Acceptance / reconciliation

1. Read current RFA6660 and RFA7033 before edits. If still unresolved, add exact named policy and page links, distinguish each stage, record label limitation, maintain raw flags, nonpreferred/preferred difference, and QL unknown. Leave exact payer device/package and patient-specific approval unresolved. Two possible literal unresolved-criteria reductions only after workbook readback; do not decrement before incorporation.
2. Render both records under UHC: each relevant named stage, exact source links, route, distinct label safeguards; Actemra nonpreferred prerequisite present and preferred Avtozma prerequisite absent; administrative QL remains distinct. Check nearest IV and other plan cards unchanged. Use existing tests and exact deployment verification. No DEC-07/09 or DATA-01 rollout.
3. Further archive index screen (449 sections, title/guideline name/printed product field, not exhaustive clinical source audit): no named match for Accrufer/ferric maltol RFA6637, Angeliq/drospirenone-estradiol RFA6851, Annovera/segesterone RFA6852, Apidra/glulisine RFA6926/6927, Reyataz/atazanavir RFA7000, Avlayah/tividenofusp RFA7030, Azasite/azithromycin RFA7037, Edarbi/azilsartan RFA7045, Baraclude/entecavir RFA7081. Do not mark payer criteria complete or infer no PA. Existing GL-231255 nonpreferred administrative scope (effective 2025-05-01, pp1202–1205), GL-545275 preferred nonsolid administrative scope (effective 2026-04-12, pp1357–1360), and GL-140667 quantity override (effective 2020-12-15, pp702–705) retained as broader references only. Avlayah statewide GL-620189 is reference only, not UHC exact-plan criteria. Next verify any current exact-plan source or documented external hold, then proceed to remaining UHC RFA rows; do not repeat same archive-name screen without new evidence.

## Release status

At entry PR103 open and main 42a5ed6. Push workflow 45576085793 attempt 2 in progress, not verified deployed. Public app endpoint could not be independently accessed. No changes to main, production, shared workbook, or ledger from this handoff. 

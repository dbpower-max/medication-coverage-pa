# GitHub publication status

## Overnight correction ledger — November 15–16, 2026

- Baseline: `aebad20` (Batch 45), Pages run `43798489045` succeeded. Existing 239 structured guides / 202 policy sections and 481 statewide source sections retained. Older ledger entries below are historical.
- Priority queue: (1) PA-column misclassifications and conditional wording; (2) existing criteria access; (3) policy/admin records in medication search; (4) targeted production regression/mobile checks.
- Batch 46: nine source-reviewed products corrected: Humatin/Alkeran/Eulexin explicitly excluded; Lagevrio/Paxlovid age rules; Singulair granules/Likmez/nadolol/Synagis exemptions without inferring PA outside the exemption. November AHCCCS and October Banner PDFs checked; original values/text retained. All 205 remaining conditional statewide panels preserve source wording instead of asserting unconditional PA. Targeted PA tests and existing grouping/provider checks passed; production verification pending at commit time.
- Batch 47: medication results/autocomplete accept formulary records only and name/brand/medication aliases only. All 239 existing structured guides and 970 selected-plan policy records remain accessible in the separate criteria library; source-only matches open that panel, without creating medication cards. Added conditional PA filter and plan-isolation/search regressions. Guide verification reuses the per-plan mapping instead of recomputing it for every guide. Targeted checks passed; production verification pending at commit time.

Updated November 13, 2026 (Arizona).

Public repository: https://github.com/dbpower-max/medication-coverage-pa
Public app: https://dbpower-max.github.io/medication-coverage-pa/

GitHub Pages is enabled using GitHub Actions. Deployment run 43531033481, attempt 2, succeeded. The build passed JavaScript syntax validation and verified 969 linked local assets; its scoped dataset contains 6,998 medication records and 970 policy records. Large Banner November PA criteria link to the exact official payer PDF; indexed full policy text is bundled.

The deployed app includes only Arizona Complete Health — Complete Care, Banner — University Family Care ACC, and UnitedHealthcare — AHCCCS Complete Care. Provider interface, coverage/preference/restrictions, PA criteria and linked sources are the only future upload scope. No further audit, raw projection, historical database, commercial, Medicare or other-plan uploads are planned. Existing repository archives are excluded from the deployed package.

Live browser checks passed for the exact three-plan selector, Banner Jardiance results, UHC Jardiance results, Arizona Complete Health Mounjaro results, clear-filter reset, and opening full Banner policy text at the GitHub project-relative URL.

Internal evidence badges requested for removal are filtered in commit 658cc7332f615fc7c69e0fdc6797471d940fbc3f. Clinical data and source conflicts remain preserved. ACH additional-plan data and unresolved source identity conflicts remain incomplete; publication does not establish patient-specific benefits or complete all payer research.

Build: python tools/build_provider_site.py
Local server: python -m http.server 8000 --directory _site
Deployment workflow: .github/workflows/pages.yml

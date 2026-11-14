# GitHub publication status

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

# GitHub publication status

Updated November 13, 2026.

## Authorized scope going forward

Provider-facing insurance information for exactly these three plans:
- AHCCCS: Arizona Complete Health — Complete Care (`az-complete-health`)
- AHCCCS: Banner — University Family Care ACC (`banner-ufc`)
- AHCCCS: UnitedHealthcare — AHCCCS Complete Care (`uhc-community-az`)

Only the interface, these plans' medication coverage/preference/restrictions, PA criteria and linked provider sources are in scope for future uploads. Stop further audit, raw projection, historical database, commercial, Medicare, FFS, ALTCS, DD and other plan uploads. Previously uploaded archive material has not been deleted.

## Verified publication

The existing repository contains the application interface, core compressed dataset, Banner/UHC policy text, ACH policy PDFs, Banner formulary/internal criteria and current UHC PDL/clinical pharmacy PDFs. No further bulk archive uploads are required for this narrowed scope.

Provider interface now filters plan selections, medication records, policies, evidence and lazy dataset mappings to the three allowed plan IDs. Clear filters returns to Arizona Complete Health. Removed navigation to the separate statewide reference. Header identifies three AHCCCS Complete Care plans. Underlying clinical source assertions are unchanged.

JavaScript syntax check passed. Both changed interface files were fetched from GitHub and matched the intended contents exactly after commit 3e3eda6c1f540f96da248010f658715472d1e859.

GitHub source publication is verified. Live hosting/browser verification remains unconfirmed; do not claim that the existing hosted Site has been updated by these GitHub commits.

# Current November 2026 policy indexes

- UHC AZ: 449 chapters, PDF pages 17–2018; applies to AHCCCS Complete Care, DD and ALTCS per the official provider hub.
- AHCCCS FFS: 481 chapters, PDF pages 18–2147; FFS/AIHP applicability only. Do not assign this wholesale to managed-care plans.
- Every chapter start agrees across bookmarks, printed TOC, the complete Guideline ID first-page scan, and an independent pdfplumber header extraction (Guideline Name, Guideline ID, individual effective date).
- Every criteria page after the TOC is assigned to exactly one contiguous section. No missing/nonbookmarked Guideline ID start pages were found; zero boundary holds.
- UHC Lumizyme GL-140652 (pages1084–1085) has a blank individual Effective Date in the source. The index flags this; no policy date is invented. Both documents are the officially identified November1,2026 snapshots.
- Verbatim text is retained with PDF-page markers. This is source retrieval, not a generated approval algorithm or clinical sign-off.

## Integrate

1. Copy the original PDF files from `audits/current_ahcccs_2026_11_12/` to `dist/sources/` retaining their date-bearing filenames.
2. Copy `uhc-nov2026/text/` to `dist/policy-text/uhc-nov2026/`, and `ahcccs-ffs-nov2026/text/` to `dist/policy-text/ahcccs-ffs-nov2026/`.
3. Use each `proposed_policy_records.json`, changing only the destination planId if the FFS plan ID differs from `ahcccs-ffs-aihp`. UHC duplicate product views (ALTCS/DD) may share source references where the hub explicitly confirms applicability.
4. Replace444 old current UHC index records and stale medrecord `policySource` links (their mutable official URL now serves the November PDF at different page offsets). Preserve their historical source records separately.
5. Archive/reclassify17 old FFS structured summaries currently labeled `ahcccs-statewide`; the new FFS index does not validate carrying September approval summaries forward as currentNovember rules or applying them to every MCO.
6. `related_policy_candidates_current_records.json` contains163 exact literal Product Name field matches for163 currently released UHC October records. These are related-section candidates, not a guarantee the formulation/indication branch applies. `november_policy_index_candidates.candidates(records, source_key)` can be rerun for the final new med datasets. It deliberately avoids names that appear only in prerequisite/alternative-drug prose.

## Reproduce

Use the primary runtime Python to run `tools/november_policy_index_build.py`, followed by `tools/november_policy_index_candidates.py`. The scripts write only this audit directory. Original PDFs are read from `audits/current_ahcccs_2026_11_12/`.

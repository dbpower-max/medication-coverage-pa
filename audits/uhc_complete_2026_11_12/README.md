# Complete UHC Arizona Medicaid October 2026 source audit

- `proposed_medications.json`: 3,921 current exact-name products, without obsolete July policy pointers.
- `source_position_projection.json`: all 3,946 printed Tier-marked product positions mapped to their released product IDs.
- `validated.json`: each complete name/tier/restriction rectangle independently reproduced with pdfplumber; zero mismatches.
- `duplicate_groups.json`: 25 differing duplicate groups. Explicit positive PA/ST/QL flags are not canceled by another row's omitted field. Different preferred columns remain unspecified; differing numeric tiers remain unset in the projected single tier.
- `historical_july_reconciliation.json`: all 137 prior July records preserved outside the current dataset. No full exact-name October identity match was established. Broader/narrower candidate names are not treated as verified identities.
- `official_machine_readable.json` and `machine_readable_metadata.json`: official supplementary machine-readable feed and its schema/version limitations. It contains Medicaid and Part D variants, no NDC identifiers or clinical effective date, and contradictory variants for the same RxNorm and plan. Do not use false flags to negate the dated PDF or describe duplicate differences as NDC-specific.

The parser respects complete wrapped names, exact Tier delimiters, continuation restriction prose and explicit code-list endings. The two bulk-container-only restrictions without trailing codes require the exact printed phrase `Individual packets are not covered` as the complete restriction ending; the next line begins a separate product. This prevents the prior malformed `covered cholestyramine ...` identity.

All positive PA fields require an explicit printed PA flag or conditional PA prose. Behavioral-health prescriber exceptions from the source legend remain explicit. Minimum/maximum age statements without PA language do not invent a PA requirement. Blank fields stay unspecified.

The dated PDF's front matter includes legacy administrative/step-therapy examples with 2020 footer text. Current November clinical policy criteria must be separately linked; no old front-matter example was converted into a current structured approval rule.

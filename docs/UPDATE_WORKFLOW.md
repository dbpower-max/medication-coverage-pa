# Medication Coverage App — Controlled Update Workflow

Version: 1.0 | Established: 2026-11-16 | Owner: Medication Coverage/PA project

## Objective

Update the provider-facing Arizona AHCCCS medication search app in small, source-verifiable changes, while preserving the last known-good public release. This is an operational procedure; it does **not** authorize unattended clinical assertions or automatic publication of newly scraped payer data.

Current live scope: Arizona Complete Health ACC, Banner–University Family Care ACC, and UnitedHealthcare Community Plan ACC. Keep other plan/product datasets archived unless explicitly approved for release.

## Update tracks

| Track | Scope | Key safeguard |
| --- | --- | --- |
| A — Formulary | Drug list, covered/listed status, preference, explicit PA, step therapy, quantity limits | Preserve exact plan, formulation, strength, NDC and effective-date scope |
| B — PA policy | Policy text, product/diagnosis/stage branches, approval requirements | Preserve every printed AND/OR, exception, numeric threshold, duration and source reference |
| C — Architecture | RxNorm/NDC mapping, HL7 Da Vinci FHIR compatibility, database schema, import/export | Run old and new models in parallel; prove no unintended coverage changes |
| D — Interface | Search, filtering, grouping, dose disclosures, links | Do not alter clinical status calculations or source identities |

Do not combine a clinical-policy update with unrelated interface/schema changes in one batch.

## 1. Intake and source registration

For each source, record:
- Exact carrier, insurance product, benefit, plan ID, and geographic scope.
- Official source URL and filename, payer/publisher, policy or formulary ID, effective date, retrieval date, and file SHA-256.
- Applicable drug identity and any brand/generic, form, route, strength, NDC, RxCUI, age, diagnosis, or stage restrictions.
- Original text and page/section citation, previous source version, and whether the new source **replaces**, **supplements**, or **conflicts** with prior evidence.
- Review state: not reviewed / mechanically validated / clinician reviewed / payer confirmed. Never label mechanically extracted content as clinician-approved.

Official payer material is authoritative for plan-specific coverage. A statewide AHCCCS baseline cannot silently replace an exact-plan policy. A policy document is not, by itself, evidence that every related product requires PA. Unknown is not no-PA.

## 2. Create a bounded batch

- Create a branch from the latest verified \`main\`, using \`update/<track>-<source-or-feature>-YYYY-MM-DD\`.
- Capture baseline commit, public Pages build, original record counts, source/criteria versions, and affected medication record IDs.
- Limit routine batches to **one plan and one coherent drug class/policy group**, generally 10–25 records or one policy. Use smaller batches for high-risk policies, NDC discrepancies, insulin/device formulations, or broad shared rules.
- Architecture changes are separate batches with no production drug changes.
- Change only documented source-backed fields; preserve raw records and all previous versions.

## 3. Import, compare, and validate

### Automated checks (mandatory)

1. Rebuild the provider site using \`python tools/build_provider_site.py\`.
2. Run the same clinical, provenance, grouping, medication-card, and source-link checks used by the production Pages workflow; the PR workflow must stay in parity with the Pages workflow.
3. Check schema and SQLite integrity, unique record IDs, and referential integrity where a master database changes.
4. Produce a machine-readable **before/after diff** with added, modified, removed, and unchanged record IDs and each altered clinical field.
5. Verify that every changed PA/preference/ST/QL/coverage field is linked to the correct **exact-plan** official source and source page or policy section.
6. Assert that records outside the declared batch remain unchanged. Any count change or removed source linkage must be explained, not silently accepted.
7. Check exact product-branch matching across brand/generic, RxCUI/NDC, form, route, strength, and indication/stage. Do not conflate source policy text with a coverage determination.
8. Run affected-medication UI checks at desktop and 360px mobile width; verify no blank criteria panel, broken link, spurious PA flag, or cross-plan leak.

Existing test assertions may use fixed counts. If an approved source update legitimately changes counts, update assertions **with an itemized explanation and source proof**, never by simply weakening a test.

### Clinical evidence rules

- Display a PA-needed indicator **only** when a payer explicitly requires it for that exact applicable product/situation; conditional triggers must stay conditional.
- Preserve unknown and conflicting source statuses in backend data. The UI can omit unsupported PA badges but must never transform absence of a badge into a verified no-PA claim.
- Retain original policy wording, AND/OR logic, quantity units/days, stage, and exceptions.
- Do not infer a numeric QL from an unspecified restriction or apply generic criteria to an NDC-specific item without verification.
- Do not promote a mechanically parsed or source-transcribed summary to clinician-reviewed status.

## 4. Pull request review gate

Every batch PR must state:
- Track and scope; old vs new source effective dates.
- Baseline and candidate commit IDs; exact changed record IDs and count.
- Source links, hashes and cited excerpts/pages.
- Automated checks run (pass/fail) and a 3-plan regression statement.
- One or more real, affected medication cards manually inspected.
- Outstanding uncertainties, especially any unverified PA/QL/formulation mapping.
- Rollback commit and reviewer decision.

**Stop conditions:** missing primary source; unresolvable product mapping; unexplained changes outside batch; dropped policy branches; misleading PA/coverage assertion; broken links or failed validation. Keep the issue open and do not merge. A working branch is not a verified release.

## 5. Publish and verify

1. Merge only after the review gate is satisfied. The existing \`.github/workflows/pages.yml\` publishes on pushes to \`main\`.
2. Verify the exact deployed commit and a successful GitHub Pages run, not only a successful GitHub file write.
3. Open the public site at https://dbpower-max.github.io/medication-coverage-pa/ and test an affected medication under the correct plan, an unaffected medication, and plan switching.
4. Check displayed PA/QL and the real linked policy in the public build.
5. Record release date, commit, Pages run, test sample, evidence version, changed IDs, unresolved issues and rollback reference in the running publication ledger (\`PUBLICATION_STATUS.md\`).

If the deployment fails or verification finds a regression, revert the offending merge/change to a known-good commit and verify the rollback deployment before proceeding. Preserve both versions for audit.

## 6. HL7 Da Vinci compatibility — separate incremental sequence

Use the [HL7 Da Vinci Drug Formulary reference server](https://github.com/HL7-DaVinci/drug-formulary-ri) as a **model/interoperability reference**, not a replacement server. Our live app is a Python-built static GitHub Pages app with a SQLite master.

- **C1:** Document mapping: local plan -> FHIR \`InsurancePlan\`, local medication/RxNorm concept -> \`MedicationKnowledge\`, plan-product coverage -> \`Basic\` FormularyItem. Document unsupported information such as complete clinical PA criteria, provenance and NDC-package restrictions as local additions, not falsely standard HL7 fields.
- **C2:** Export a tiny, read-only FHIR JSON example from existing data for a single verified medication and plan. No live changes.
- **C3:** Validate IDs, profile usage, coverage flags and source references; round-trip back to a local representation and compare each original field byte-for-byte or semantically as applicable.
- **C4:** Expand one class/plan at a time only after successful equivalence checks. Keep the current renderer and original SQLite data as authoritative until a separately approved migration.

A full Java/HAPI server, hosting change, patient authentication, or live API is **out of scope** for this workflow.

## Batch acceptance checklist

Copy this checklist into each PR or audit record. Keep it in GitHub so it remains available across chats/devices.

- [ ] Source is official, in scope, dated, hashed and cited.
- [ ] Baseline commit and public deployment identified.
- [ ] Batch contains only declared record IDs/features.
- [ ] All changed clinical claims match the exact plan/product/source.
- [ ] Original policy branches, uncertainty labels and raw evidence preserved.
- [ ] Build, full regression suite and before/after diff pass.
- [ ] Affected and unaffected cards checked, including mobile and plan switch.
- [ ] PR reviewed; unresolved limitations explicitly documented.
- [ ] GitHub Pages deployment succeeded at the intended commit.
- [ ] Live medication/criteria links verified and release ledger updated.

## Working rule for repeated ChatGPT update sessions

At the start of each session, read \`PUBLICATION_STATUS.md\` and the latest repo/Pages status. Recommend the next smallest batch rather than asking the user to choose medications. Complete one batch -> validate -> report its precise status -> move to the next eligible batch only if the preceding batch passed. Do not claim autonomous background execution after the conversation ends.

# Provider build data and historical database snapshots

For the current three-plan provider build, use the [build instructions](../README.md#run-locally) and [build script](../tools/build_provider_site.py). The script reads `dist/data.json.gz`, applies the repository’s reviewed source updates, and writes the provider site to `_site`. Use the [project records](../AGENTS.md) for current source decisions and the [Pages runs](https://github.com/dbpower-max/medication-coverage-pa/actions/workflows/pages.yml?query=branch%3Amain) for deployment status.

## Archived v0.29 commercial-guide snapshot

`medication_coverage_v0.29.sqlite.gz` was the SQLite master for the additional commercial-guide release. The historical restoration command was `gzip -dk medication_coverage_v0.29.sqlite.gz` for a local copy of the snapshot. That release used `dist/data.json` plus the per-plan files listed in `planDataFiles`. Medication counts include distinct product/formulary pairs, not unique ingredients.

## Archived v0.31 AHCCCS snapshot — November 12, 2026

The November 12 release used `medication_coverage_v0.31.sqlite.gz`. Schema version 31 preserved 92,227 medication/source records and added `app_plan_visibility` to distinguish active plans from archived commercial plans. That release exposed 37,084 active medication records and 2,906 policy records. The two Banner insulin descriptions were corrected by Dr. Brower on November 12; original payer wording and the v0.30 master remain unchanged. These are clinician corrections, not payer-issued revisions. The November 12 rebuild used `tools/import_ahcccs_complete_release.py`, `tools/register_ahcccs_sources.py`, `tools/compress_browser_data.py`, `tools/apply_clinician_preferences.py` and `tools/verify_ahcccs_release.py`. Reproducing that snapshot requires the archived commercial payloads at the importer's expected paths before compression. Source-data completeness gaps remain explicit in the plan catalog.

`commercial-archive/catalog.json` retains all 16 commercial plan definitions, their evidence, and exact dataset paths/hashes. The adjacent compressed datasets preserve all 55,143 commercial medication records for later restoration; they are excluded from the active plan catalog and deployment. Original uncompressed browser JSON and source PDFs remain preserved in the repository. The archive restoration procedure copied its dataset to `dist/data`, restored the catalog and evidence entries and `planDataFiles` mapping, and updated `app_plan_visibility`.

For that release, `tools/compress_browser_data.py` compressed plan datasets and retained the original bytes in `data/browser-json`. The browser handled gzip assets and already-decoded responses within the hosting service’s 256 MiB expanded-asset limit.

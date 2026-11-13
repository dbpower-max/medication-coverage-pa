
## Current database master

`medication_coverage_v0.29.sqlite.gz` contains the full SQLite master through the additional commercial-guide release. It is compressed to fit repository object limits. Restore it with Python gzip or `gzip -dk medication_coverage_v0.29.sqlite.gz`; the uncompressed working copy is ignored by git. Earlier masters remain preserved. The browser uses `dist/data.json` plus the per-plan files listed in `planDataFiles`. Medication counts include distinct product/formulary pairs, not unique ingredients.

## November 12 current AHCCCS release

Current master: `medication_coverage_v0.31.sqlite.gz`. Schema user_version31 preserves all 92,227 medication/source records and adds app_plan_visibility to distinguish active plans from archived commercial plans. The browser exposes 37,084 active medication records and 2,906 policy records. The two Banner insulin descriptions were corrected by Dr. Brower on November 12; original payer wording and the v0.30 master remain unchanged. These are clinician corrections, not payer-issued revisions. Rebuild with tools/import_ahcccs_complete_release.py, tools/register_ahcccs_sources.py, tools/compress_browser_data.py, tools/apply_clinician_preferences.py, then tools/verify_ahcccs_release.py. For a fresh full rebuild, restore archived commercial payloads to the dist paths expected by the importer before compression. Source-data completeness gaps remain explicit in the plan catalog.

`commercial-archive/catalog.json` retains all 16 commercial plan definitions, their evidence, and exact dataset paths/hashes. The adjacent compressed datasets preserve all 55,143 commercial medication records for later restoration; they are excluded from the active plan catalog and deployment. Original uncompressed browser JSON and source PDFs remain preserved in the repository. To restore a plan later, copy its dataset back to dist/data, restore its catalog/evidence entries and planDataFiles mapping, and update app_plan_visibility. Do not rerun the legacy exporter to restore an archived plan.

After rebuilding, run tools/compress_browser_data.py to deploy gzip plan datasets while retaining exact uncompressed bytes in data/browser-json. The browser handles gzip assets and already-decoded responses; the hosting bundle stays below its256MiBexpandedassetlimit.

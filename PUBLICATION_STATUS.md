# GitHub publication progress

Source archive: Medication_Coverage_Full_Archive_2026-11-13.tar.gz
Archive SHA-256: ec3185e7c1b02cef86c8f36220cd2cf08230e7c861e9b8ef8bd399157303fd1a

1. App interface: included in this commit. Requested display labels removed; underlying data unchanged.
2. AHCCCS datasets: included in this commit; 37,084 medication/source records and 2,906 policy/source records. Core JSON is losslessly gzip-compressed; loader updated. Policy text and source PDFs remain pending.
3. Commercial datasets: included in this commit; 16 distinct archived plan/reference datasets, 55,143 records. All catalog SHA-256 values, record counts, plan identities and unique IDs verified. Archived visibility preserved.
4. Policies/supporting data: included in this commit; 1,446 policy text files and 2 historical JSON files. All 1446 distinct local policy-text targets in active records resolve. Hash verification required before reporting success.
5. Split into smaller uploads because the remaining source/audit/database material exceeds 500 MB. 5A: 42 importer/validation tools and 19 source registries/audit summaries included in this commit. Remaining PDFs, detailed audits, database archives and raw projections: pending.
6. Hosting and live verification: pending.

This partial repository cannot run until the required datasets are uploaded. No live deployment is claimed.

Verification: compare all uploaded Git blob hashes against local file bytes and confirm main points to this commit.

5B: 29 source PDFs under 1 MB included in this commit (320 PDF pages); larger PDFs, detailed audits and database archives remain pending.

5C: Three additional source PDFs included: UHC commercial September 2026 reference, Banner October 2026 formulary, and Mercy integrated October 2026 formulary. Larger PDFs, detailed audits, database archives and hosting verification remain pending.

5D: Ten additional audit/supporting text and JSON files uploaded (26,603 bytes). Git blob hashes verified against archived source bytes. Remaining source PDFs, detailed audits, database archives and hosting verification remain pending.

5E: Twenty additional audit/policy text and JSON files uploaded (202,324 bytes). All source blob hashes verified. Remaining source PDFs, detailed audits, database archives and hosting verification remain pending.

5F: Twenty additional audit/policy text and JSON files uploaded (220,202 bytes). All source blob hashes verified. Remaining source PDFs, detailed audits, database archives and hosting verification remain pending.

5G: Twenty additional November AHCCCS FFS policy audit text files uploaded (31,628 bytes). All source blob hashes verified. Remaining source PDFs, detailed audits, database archives and hosting verification remain pending.

5H: Twenty additional November AHCCCS FFS policy audit text files uploaded (57,666 bytes). All source blob hashes verified. Remaining source PDFs, detailed audits, database archives and hosting verification remain pending.

5I: Twenty additional November AHCCCS FFS policy audit text files uploaded (44,496 bytes). All source blob hashes verified. Audit files still missing from the archived audits directory: 957. Remaining source PDFs, database archives and hosting verification are separate pending work.

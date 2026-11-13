# GitHub publication progress

Source archive: Medication_Coverage_Full_Archive_2026-11-13.tar.gz
Archive SHA-256: ec3185e7c1b02cef86c8f36220cd2cf08230e7c861e9b8ef8bd399157303fd1a

1. App interface: included in this commit. Requested display labels removed; underlying data unchanged.
2. AHCCCS datasets: included in this commit; 37,084 medication/source records and 2,906 policy/source records. Core JSON is losslessly gzip-compressed; loader updated. Policy text and source PDFs remain pending.
3. Commercial datasets: included in this commit; 16 distinct archived plan/reference datasets, 55,143 records. All catalog SHA-256 values, record counts, plan identities and unique IDs verified. Archived visibility preserved.
4. Policies/supporting data: included in this commit; 1,446 policy text files and 2 historical JSON files. All 1446 distinct local policy-text targets in active records resolve. Hash verification required before reporting success.
5. Sources, audits, database archives and importer tools: pending.
6. Hosting and live verification: pending.

This partial repository cannot run until the required datasets are uploaded. No live deployment is claimed.

Verification: compare all uploaded Git blob hashes against local file bytes and confirm main points to this commit.

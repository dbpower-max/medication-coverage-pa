# RxNorm identifier / monthly diff pilot — not deployed

This isolated pilot defines **30 fixed internal demonstration IDs**, each paired with a brand-name lookup target. It does **not** yet assign IDs to real source/product records and is **not** a completed medication crosswalk.

## Data model and policy

- medicationId: stable app-owned pilot identifier (rxp-*), independent of RxNorm numbering.
- lookupName, expectedTty=BN: exact brand-level query, not a strength/route-specific drug product.
- candidateRxcui: an NLM RxNorm concept only after a unique exact BN match is returned.
- status: always requires review. Ambiguous or missing matches have candidateRxcui=null.
- candidates: RxNorm properties, permitting review of changed/retired/replaced RxCUIs.
- snapshot.json: last downloaded release candidates; intentionally empty before first network run.
- report.md: additions, removals and changes between releases.

**Never merge two products solely because they share a BN RxCUI or ingredient RxCUI.** A brand identity does not establish equivalent ingredient combination, dose, strength, route, device, release type or package. Payer policies, PA requirements and coverage remain independent.

## Run with internet access

    python -m unittest discover -s tools -p test_rxnorm_pilot.py -v
    cp data/rxnorm-pilot/snapshot.json /tmp/rxnorm-before.json
    python tools/rxnorm_pilot.py refresh --targets data/rxnorm-pilot/targets.json --output data/rxnorm-pilot/snapshot.json
    python tools/rxnorm_pilot.py diff --previous /tmp/rxnorm-before.json --current data/rxnorm-pilot/snapshot.json --report data/rxnorm-pilot/report.md

NLM RxNav API endpoints: /REST/version.json, /REST/rxcui.json?search=0, /REST/rxcui/{id}/properties.json.
API failure aborts before writing any new snapshot.

## Monthly review-only automation

After merging this pilot, the workflow runs on the 10th of each month, 15:00 UTC (08:00 Arizona), after typical first-week RxNorm releases. It tests, refreshes and diffs the candidate mappings, then opens a PR with ONLY snapshot and report. It never auto-merges or changes the live app.

## Later work not yet implemented

1. Crosswalk the existing active source records to product-specific RxCUIs/NDCs with evidence and approved mappings.
2. Resolve retired/remapped/ambiguous concepts with manual review.
3. Integrate identity-based grouping in small tested batches without losing source/plan/PA distinctions.
4. Verify live interface before publishing.

No automatic update is clinically approved merely because tests pass.

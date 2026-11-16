"""Attach NLM display names by verified existing RxCUI; never change identity."""
import gzip
import json
import re
from pathlib import Path


def canonical_name(value):
    # The payer JSON replaces commas with spaces; no clinical tokens change.
    return re.sub(r'[\s,]+', '', value).casefold()


def attach_rxnorm_display_names(data):
    path = Path(__file__).parent / 'reference/rxnorm_names_202611.json.gz'
    registry = json.loads(gzip.decompress(path.read_bytes()))
    matched = psns = 0
    unmatched = []
    for record in data['medications']:
        rxcui = str(record.get('rxnormId') or '')
        if not rxcui:
            continue
        standard = registry['names'].get(rxcui)
        if not standard:
            unmatched.append(rxcui)
            continue
        assert canonical_name(record['name']) == canonical_name(standard['fullName']), 'RxCUI/source name mismatch: ' + rxcui
        psn = standard['psn']
        assert psn not in ('NA', ''), 'Placeholder used as a clinical name'
        # A day/night combination pack's PSN starts with a package count.
        # Use its NLM-supplied drug-name-first display field instead.
        if psn and re.match(r'^\d+\s+(?:daytime|nighttime)\b', psn, re.I):
            psn = None
        label = psn or standard['displayName']
        if not psn and standard['strength'] and standard['strength'].lower() != 'mixed':
            label += ' — ' + standard['strength'] + ' ' + standard['doseForm']
        record['standardDisplayName'] = standard['displayName']
        record['standardName'] = label
        record['standardNameType'] = 'RxNorm PSN' if psn else 'RxTerms display fields'
        record['standardNameProvenance'] = {'rxcui': rxcui, 'release': registry['release'], 'sourceFile': standard['sourceFile'], 'retired': standard['retired']}
        matched += 1
        psns += bool(psn)
    data['medicationNamingInfo'] = {key: value for key, value in registry.items() if key != 'names'}
    data['medicationNamingInfo'].update(matched=matched, psns=psns, structuredFallbacks=matched-psns, unmatchedIds=unmatched)
    assert matched == 4451 and psns == 4447 and len(unmatched) == 3
    return matched

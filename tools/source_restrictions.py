"""Interpret reviewed non-PA statements in the printed PA-status column.

Keep the original text and values. A minimum age or an exemption does not
establish a PA requirement outside the stated population.
"""
import re


def correct_source_restrictions(records):
    changed = 0
    for record in records:
        source = record.get('sourceUrl', '')
        if not source.endswith(('ahcccs-drug-list-2026-11-01.pdf',
                                'bufc_formulary_eff10012026_en.pdf')):
            continue
        text = record.get('paText', '')
        if re.match(r'Not covered through AHCCCS\.', text, re.I):
            fields = dict(coverage='explicit_not_covered', pa='not_specified',
                          coverageText=text)
        elif re.fullmatch(r'Minimum Patient Age of (18|12) Years', text, re.I):
            fields = dict(pa='not_specified', ageLimited=True, ageRestrictionText=text)
        elif re.match(r'PA (?:IS )?NOT REQUIRED\b', text, re.I):
            fields = dict(pa='not_specified', paExceptionText=text)
        else:
            continue
        if all(record.get(key) == value for key, value in fields.items()):
            continue
        record.setdefault('restrictionCorrection', {
            'originalCoverage': record.get('coverage'),
            'originalPa': record.get('pa'),
            'reason': 'Reviewed printed PA-column statement; no positive PA requirement.'
        })
        record.update(fields)
        changed += 1
    return changed

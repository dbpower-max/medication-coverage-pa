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
        reason = 'Reviewed printed PA-column statement; no positive PA requirement.'
        if re.fullmatch(r'PA REQUIRED \((?:3%|1\.8% & 3\.5%) Only\)', text, re.I):
            fields = dict(pa='conditional')
            reason = 'Printed PA requirement applies only to the specified concentrations.'
        elif re.match(r'PA REQUIRED\s+(?:if|unless|when)\b', text, re.I):
            fields = dict(pa='conditional')
            reason = 'Printed PA requirement has an explicit condition; retain the complete source condition.'
        elif re.match(r'Not covered through AHCCCS\.', text, re.I):
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
            'reason': reason
        })
        record.update(fields)
        changed += 1
    return changed


def correct_source_conflicts(records):
    """A blank conflicting row is neither nonpreferred nor confirmed no-PA."""
    changed = 0
    for record in records:
        source = record.get('sourceUrl', '')
        fields = {}
        rows = record.get('sourceRows', [])
        if source.endswith(('ahcccs-drug-list-2026-11-01.pdf',
                            'bufc_formulary_eff10012026_en.pdf')) and record.get('sourceConflict') and len(rows) > 1:
            if record.get('preferred') == 'non_preferred' and not any(
                re.search(r'non[- ]?preferred', row.get('preference', ''), re.I) for row in rows
            ):
                fields.update(preferred='not_specified',
                    preferenceUncertaintyReason='Printed preference fields differ; blank does not establish nonpreferred status.')
            pa = [row.get('pa', '').strip() for row in rows]
            if record.get('pa') == 'required' and any(pa) and not all(pa):
                fields.update(pa='not_specified', paText='',
                    paUncertaintyReason='Printed source rows disagree on PA; applicability to the selected product is unresolved.')
        if source.endswith('uhc-az-medicaid-pdl-2026-10-01.pdf'):
            variants = record.get('conflictSources', [])
            flags = [bool(re.search(r'(^|;)\s*PA\s*(;|$)', row.get('codes', ''))) for row in variants]
            if record.get('pa') == 'required' and flags and any(flags) and not all(flags):
                fields.update(pa='not_specified', paText='',
                    paUncertaintyReason='PA is printed in only some conflicting product listings; universal applicability is not established.')
            for code, field in [('ST', 'step'), ('QL', 'qlAmount'), ('AL', 'ageLimited'),
                                ('SP', 'specialty'), ('DX2RX', 'diagnosisRequired')]:
                flags = [bool(re.search(r'(^|;)\s*' + code + r'\s*(;|$)', row.get('codes', ''))) for row in variants]
                if not flags or not any(flags) or all(flags):
                    continue
                if code == 'ST' and record.get('step') == 'specified':
                    fields.update(step='not_specified', stepText='',
                        stepUncertaintyReason='Step therapy appears in only some conflicting product listings.')
                elif code == 'QL' and (record.get('qlAmount') or record.get('quantityLimited')):
                    fields.update(qlAmount='', qlDays='', quantityLimited=False,
                        quantityUncertaintyReason='Quantity restrictions differ between printed product listings.')
                elif code in ('AL', 'SP', 'DX2RX') and record.get(field):
                    fields[field] = False
                    fields[field + 'UncertaintyReason'] = 'Flag appears in only some conflicting product listings.'
        if source.endswith(('ahcccs-drug-list-2026-11-01.pdf', 'bufc_formulary_eff10012026_en.pdf')) and len(rows) > 1:
            quantities = [row.get('quantity', '').strip() for row in rows]
            if any(quantities) and not all(quantities) and (record.get('qlAmount') or record.get('quantityLimited')):
                fields.update(qlAmount='', qlDays='', quantityLimited=False,
                    quantityUncertaintyReason='Quantity limit appears in only some conflicting printed rows.')
        if not fields:
            continue
        record.setdefault('sourceConflictCorrection', {
            'originalPreferred': record.get('preferred'), 'originalPa': record.get('pa'),
            'originalPaText': record.get('paText'), 'originalConflict': record.get('sourceConflict')
        })
        for key in ('step', 'stepText', 'qlAmount', 'qlDays', 'quantityLimited', 'ageLimited', 'specialty', 'diagnosisRequired'):
            record['sourceConflictCorrection'].setdefault('original' + key[0].upper() + key[1:], record.get(key))
        record.update(fields)
        if 'paUncertaintyReason' in fields:
            record['sourceConflict'] = fields['paUncertaintyReason']
        elif 'preferenceUncertaintyReason' in fields:
            record['sourceConflict'] = fields['preferenceUncertaintyReason']
        changed += 1
    return changed

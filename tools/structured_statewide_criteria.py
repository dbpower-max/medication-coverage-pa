"""Source-faithful clinical fields; never infer applicability or Boolean logic.

Each displayed field is a contiguous source span. Page furniture is removed
only when formatting, and all spans (including the original policy context)
are checked against the unchanged source before publishing.
"""
import hashlib
import json
import re

PRODUCT = re.compile(r'^[\t ]*Product Name:', re.M)
FIELD = re.compile(r'^[\t ]*(Product Name:|Diagnosis|Approval Length|Therapy Stage|Guideline Type)[\t ]*(?=\n|\S)', re.M)
FURNITURE = re.compile(r'^\s*(?:--- PDF page \d+ ---|Page \d+)\s*$')
REVISION = re.compile(r'^\s*\d+\s*\.\s*Revision History\s*$', re.M)
BACKGROUND = re.compile(r'^\s*\d+\s*\.\s*Background\s*$', re.M)


def text_value(raw):
    return ' '.join(line.strip() for line in raw.splitlines()
                    if line.strip() and not FURNITURE.fullmatch(line))


def span(source, start, end):
    return {'start': start, 'end': end, 'text': text_value(source[start:end])}


def blocks(source, start, end):
    """Break only at printed numbered rules, bullets, and logical connectors.

    No ALL/ANY meaning is supplied by this parser. Source numbering and
    connectors are retained, including unusual/mixed connectors and notes.
    """
    lines = list(re.finditer(r'[^\n]*(?:\n|$)', source[start:end]))
    offsets = []
    for line in lines:
        value = line.group().strip()
        if not value or FURNITURE.fullmatch(value):
            continue
        if not offsets or re.match(r'^(?:\d+\s+-\s+|\d+\.\d+(?:\.\d+)*\s+|[•●▪]|AND$|OR$|AND/OR$)', value):
            offsets.append(start + line.start())
    result = []
    for i, offset in enumerate(offsets):
        item = span(source, offset, offsets[i + 1] if i + 1 < len(offsets) else end)
        item['kind'] = 'connector' if item['text'] in ('AND', 'OR', 'AND/OR') else 'requirement'
        result.append(item)
    return result


def structure_policy(policy, source):
    positions = [m.start() for m in PRODUCT.finditer(source)]
    assert positions, 'No named product: ' + policy['policyCode']
    revision = REVISION.search(source, positions[-1])
    history_start = revision.start() if revision else len(source)
    background = BACKGROUND.search(source, positions[-1], history_start)
    end = background.start() if background else history_start
    result = {
        'schemaVersion': 1, 'policyCode': policy['policyCode'],
        'title': policy['name'], 'sourceEffective': policy['sourceEffective'],
        'sourcePage': policy['sourcePage'], 'sourceLastPage': policy['sourceLastPage'],
        'sourceSha256': hashlib.sha256(source.encode()).hexdigest(),
        'editorialStatus': 'Source-transcribed clinical fields; clinician approval pending',
        'context': span(source, 0, positions[0]), 'branches': [],
        'supplement': {**span(source, end, history_start), 'verbatim': source[end:history_start]},
        'history': span(source, history_start, len(source)),
    }
    for i, start in enumerate(positions):
        stop = positions[i + 1] if i + 1 < len(positions) else end
        approval = re.search(r'^\s*Approval Criteria[\t ]*$', source[start:stop], re.M)
        assert approval, 'Missing criteria: ' + policy['policyCode']
        header_end = start + approval.start()
        criteria_start = start + approval.end()
        fields = list(FIELD.finditer(source, start, header_end))
        branch = {'start': start, 'end': stop, 'fields': {}, 'criteria': [], 'notes': []}
        for j, field in enumerate(fields):
            field_end = fields[j + 1].start() if j + 1 < len(fields) else header_end
            label = field[1].rstrip(':')
            assert label not in branch['fields'], 'Repeated metadata field: ' + policy['policyCode']
            branch['fields'][label] = span(source, field.end(), field_end)
        assert branch['fields'].get('Product Name', {}).get('text')
        notes = re.search(r'^[\t ]*Notes[\t ]*$', source[criteria_start:stop], re.M)
        criteria_end = criteria_start + notes.start() if notes else stop
        branch['criteria'] = blocks(source, criteria_start, criteria_end)
        assert branch['criteria'], 'Empty criteria: ' + policy['policyCode']
        if notes:
            branch['notes'] = blocks(source, criteria_start + notes.end(), stop)
        result['branches'].append(branch)
    validate_structure(result, source)
    return result


def validate_structure(policy, source):
    assert hashlib.sha256(source.encode()).hexdigest() == policy['sourceSha256']
    # Full clinical span is covered by ordered branches; no branch is omitted.
    assert policy['context']['end'] == policy['branches'][0]['start']
    assert policy['branches'][-1]['end'] == policy['supplement']['start']
    assert policy['supplement']['end'] == policy['history']['start']
    for previous, following in zip(policy['branches'], policy['branches'][1:]):
        assert previous['end'] == following['start']
    for branch in policy['branches']:
        for field in list(branch['fields'].values()) + branch['criteria'] + branch['notes']:
            assert field['text'] == text_value(source[field['start']:field['end']])
            assert branch['start'] <= field['start'] <= field['end'] <= branch['end']
        # Compare entire clinical body, preserving every word/number/connector.
        region = source[branch['start']:branch['end']]
        raw_body = re.split(r'^\s*Approval Criteria[\t ]*$', region, maxsplit=1, flags=re.M)[1]
        displayed = ' '.join(item['text'] for item in branch['criteria'] + branch['notes'])
        canonical = re.sub(r'\s+', '', text_value(re.sub(r'^[\t ]*Notes[\t ]*$', '', raw_body, count=1, flags=re.M)))
        assert re.sub(r'\s+', '', displayed) == canonical, 'Clinical text lost: ' + policy['policyCode']


def publish_structured_criteria(policies, source_dir, output_dir, codes):
    count = 0
    for policy in policies:
        if policy['policyCode'] not in codes:
            continue
        source = (source_dir / policy['sourceTextUrl'].lstrip('/')).read_text()
        structured = structure_policy(policy, source)
        payload = json.dumps(structured, ensure_ascii=False, separators=(',', ':')).encode()
        path = 'clinical-criteria/' + policy['policyCode'].lower() + '.json'
        target = output_dir / path
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(payload)
        policy['structuredCriteriaUrl'] = './' + path + '?v=' + hashlib.sha256(payload).hexdigest()[:12]
        policy['structuredBranchCount'] = len(structured['branches'])
        count += 1
    assert count == len(codes), 'Release includes a missing/duplicate policy code'
    return count

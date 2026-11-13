"""Apply reviewed insulin descriptions and archive commercial plans outside search.

Run after the current AHCCCS importer, source registry and browser compression.
Original payer rows and v0.30 remain unchanged; v0.31 retains every record.
"""
import copy, gzip, hashlib, json, shutil, sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'
OUT = ROOT / 'audits/clinician_preferences_2026_11_12'
OUT.mkdir(exist_ok=True)
ARCHIVE = ROOT / 'data/commercial-archive'
ARCHIVE.mkdir(exist_ok=True)
NAMES = {'HUMULIN N KWIKPEN': 'INSULIN NPH SUSPENSION',
         'LANTUS SOLOSTAR': 'INSULIN GLARGINE SOLUTION'}
PRIORITY = ['az-complete-health', 'banner-ufc', 'uhc-community-az']

def read(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes())

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')))

def main():
    d = read(DIST / 'data.json')
    archived_path = ARCHIVE / 'catalog.json'
    if archived_path.exists():
        archived = read(archived_path)
    else:
        commercial = {p['id'] for p in d['plans'] if p.get('marketGroup') not in ['ahcccs', 'medicare']
                      and not any(t in p.get('market', '').lower() for t in ['medicaid', 'ahcccs', 'medicare'])}
        assert len(commercial) == 16, commercial
        archived = {'archivedAt': '2026-11-12', 'reason': 'User requested commercial plans stored for later use.',
                    **{key: [r for r in d[key] if r.get('planId', r.get('id')) in commercial]
                       for key in ['plans', 'medications', 'policies', 'planEvidence']}, 'datasets': {}}
        for pid in commercial:
            file = d['planDataFiles'].get(pid)
            if not file:
                continue
            src = DIST / file.removeprefix('./')
            target = ARCHIVE / src.name
            shutil.move(src, target)
            archived['datasets'][pid] = {'path': str(target.relative_to(ROOT)),
                                        'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                                        'records': len(read(target))}
        write(archived_path, archived)
    commercial = {p['id'] for p in archived['plans']}
    for key in ['plans', 'medications', 'policies', 'planEvidence']:
        d[key] = [r for r in d[key] if r.get('planId', r.get('id')) not in commercial]
    d['planDataFiles'] = {pid: f for pid, f in d['planDataFiles'].items() if pid not in commercial}
    d['plans'].sort(key=lambda p: (PRIORITY.index(p['id']) if p['id'] in PRIORITY else 3, p['name']))
    corrections = []
    def correct(rows):
        for r in rows:
            if r['planId'] not in ['banner-ufc', 'banner-altcs'] or r.get('brand') not in NAMES:
                continue
            original = copy.deepcopy(r)
            raw = r['rawSourceRow']['cells']
            r['name'] = NAMES[r['brand']]
            r['recordType'] = 'formulary'
            r['coverage'] = 'listed'
            r['preferred'] = 'preferred' if raw[3] == 'PREFERRED DRUG' else 'not_specified'
            r['brandGenericNotes'] = raw[2]
            r['validation'] = 'clinician_corrected_description_original_source_preserved'
            r['descriptionCorrection'] = {'reviewedBy': 'Dr. Danielle Brower', 'date': '2026-11-12',
                                          'original': raw[0], 'corrected': r['name'], 'payerConfirmed': False}
            r['notes'] = (f'Description corrected by Dr. Brower on 2026-11-12. Banner prints "{raw[0]}". '
                          'Original source row retained; this is a clinician correction, not a payer-issued revision.')
            r['searchAliases'] = sorted(set(r.get('searchAliases', []) +
                                           (['insulin isophane human suspension'] if r['brand'] == 'HUMULIN N KWIKPEN' else [])))
            for field in ['sourceIssue', 'listingLabel', 'suppressCoverageAndPaBadges']:
                r.pop(field, None)
            corrections.append({'id': r['id'], 'before': original, 'after': copy.deepcopy(r)})
        return rows
    correct(d['medications'])
    allmed = d['medications'][:]
    for pid, file in d['planDataFiles'].items():
        path = DIST / file.removeprefix('./')
        rows = read(path)
        if pid == 'banner-altcs':
            correct(rows)
            payload = json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode()
            path.write_bytes(gzip.compress(payload, mtime=0))
            (ROOT / 'data/browser-json/banner-altcs.json').write_bytes(payload)
        allmed += rows
    assert len(corrections) == 4
    for p in d['plans']:
        if p['id'] in ['banner-ufc', 'banner-altcs']:
            p['detail'] = ('All 1,489 printed source positions accounted for in 1,453 product records. '
                           'Two insulin descriptions corrected by Dr. Brower; original source wording retained. '
                           'Current PA and internal policy sections remain searchable.')
    for e in d['planEvidence']:
        if e['planId'] in ['banner-ufc', 'banner-altcs'] and e['topic'] == 'Current source scope and verification':
            e['evidence'] = next(p['detail'] for p in d['plans'] if p['id'] == e['planId'])
    d['meta'].update(recordCount=len(allmed), policyCount=len(d['policies']))
    d['categories'] = sorted({r['category'] for r in allmed + d['policies']})
    d['subcategories'] = {cat: sorted({r['subcategory'] for r in allmed + d['policies']
                                     if r['category'] == cat and r.get('subcategory')}) for cat in d['categories']}
    write(DIST / 'data.json', d)
    write(OUT / 'insulin_corrections.json', corrections)
    # Preserve the full master and commercial records, with explicit active-plan visibility.
    dbpath = ROOT / 'data/medication_coverage_v0.31.sqlite'
    dbpath.write_bytes(gzip.decompress((ROOT / 'data/medication_coverage_v0.30.sqlite.gz').read_bytes()))
    db = sqlite3.connect(dbpath)
    db.execute('PRAGMA user_version=31')
    db.execute('CREATE TABLE app_plan_visibility(plan_id TEXT PRIMARY KEY REFERENCES plans(id),active INTEGER NOT NULL)')
    for pid, in db.execute('SELECT id FROM plans').fetchall():
        db.execute('INSERT INTO app_plan_visibility VALUES(?,?)', (pid, int(pid not in commercial)))
    for item in corrections:
        r = item['after']
        db.execute('UPDATE medications SET record_type=?,name=?,coverage=?,preferred=?,payload=? WHERE id=?',
                   (r['recordType'],r['name'],r['coverage'],r['preferred'],json.dumps(r,ensure_ascii=False),r['id']))
    for p in d['plans']:
        db.execute('UPDATE plans SET detail=?,payload=? WHERE id=?', (p['detail'],json.dumps(p),p['id']))
    for pid in ['banner-ufc', 'banner-altcs']:
        row = db.execute('SELECT payload FROM source_registry WHERE plan_id=?', (pid,)).fetchone()
        entry = json.loads(row[0]); entry.update(sourceIdentityExceptions=0, clinicianDescriptionCorrections=2,
                                               originalSourceConflictsPreserved=True, payerCorrectionConfirmed=False)
        db.execute('UPDATE source_registry SET payload=? WHERE plan_id=?', (json.dumps(entry),pid))
    summary = {'activeMedicationRecords': len(allmed), 'activePolicyRecords': len(d['policies']),
               'archivedCommercialPlans': len(commercial),
               'archivedCommercialRecords': sum(f['records'] for f in archived['datasets'].values()),
               'clinicianDescriptionCorrections': 4, 'priorityPlans': PRIORITY}
    db.execute('INSERT OR REPLACE INTO release_audit VALUES(?,?)', ('clinician_preferences_2026_11_12',json.dumps(summary)))
    db.commit()
    assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
    db.close()
    (Path(str(dbpath) + '.gz')).write_bytes(gzip.compress(dbpath.read_bytes(), mtime=0))
    write(OUT / 'summary.json', summary)
    print(json.dumps(summary))

if __name__ == '__main__':
    main()

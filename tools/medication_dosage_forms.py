"""Build a compact RxTerms form index for exact names used by the three plans.

Refresh after a provider build with the same NLM release as the name registry:
    python tools/medication_dosage_forms.py /path/to/RxTerms202611.zip
"""
import csv
import gzip
import hashlib
import io
import json
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'tools/reference/dosage_forms_202611.json'
ROUTES = {'oral', 'topical', 'nasal', 'ophthalmic', 'otic', 'rectal', 'vaginal', 'sublingual'}
ROUTE_SUFFIX = re.compile(r'\s+\(?(' + '|'.join(sorted(ROUTES)) + r')\)?$')


def payer_product(record):
    # Parenthetical cross-references do not identify the generic's formulation.
    name = re.split(r'\s+\((?:brand|generic) for ', record['name'].casefold())[0].strip()
    route = ROUTE_SUFFIX.search(name)
    return (name[:route.start()], route[1]) if route else (name, '')


def attach_dosage_forms(records):
    index = json.loads(REFERENCE.read_text())['names']
    for record in records:
        if record.get('rxnormId'):
            continue  # A strength-specific RxCUI already has a verified source name.
        name, route = payer_product(record)
        match = index.get(name)
        if match and (not route or route in match['form'].lower().split()):
            record['rxTermsForm'] = match


def rebuild(archive):
    metadata = json.loads(gzip.decompress((ROOT / 'tools/reference/rxnorm_names_202611.json.gz').read_bytes()))
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == metadata['sourceSha256']
    data = json.loads(gzip.decompress((ROOT / '_site/data.json.gz').read_bytes()))
    wanted = {payer_product(r)[0] for r in data['medications'] + data['statewideDrugList']}
    seen = defaultdict(set)
    current = defaultdict(set)
    with zipfile.ZipFile(archive) as source:
        def rows(filename):
            return csv.DictReader(io.StringIO(source.read(filename).decode()), delimiter='|')

        ingredients = defaultdict(set)
        for row in rows('RxTermsIngredients202611.txt'):
            ingredients[row['RXCUI']].add(row['INGREDIENT'].casefold())
        for filename in ('RxTermsArchive202611.txt', 'RxTerms202611.txt'):
            for row in rows(filename):
                # Full generic names also identify the substance/salt in historical products.
                # Never assign an ingredient-only form from combination products.
                generic = row['FULL_GENERIC_NAME'].casefold()
                names = set()
                if row['TTY'] in ('SCD', 'SBD') and ' / ' not in generic:
                    ingredient = re.sub(r'^(?:[\d.]+\s+(?:ml|hr|actuat|mg)\s+)+', '', generic)
                    ingredient = re.split(r'\s+\d', ingredient, maxsplit=1)[0]
                    names.add((ingredient, 'ingredient'))
                    active = ingredients.get(row['RXCUI'], set())
                    if len(active) == 1:
                        names.add((next(iter(active)), 'ingredient'))
                if row['BRAND_NAME']:
                    names.add((row['BRAND_NAME'].casefold(), 'brand'))
                for name, kind in names:
                    if name not in wanted:
                        continue
                    seen[name].add((kind, row['RXN_DOSE_FORM']))
                    if filename == 'RxTerms202611.txt' and not row['IS_RETIRED']:
                        if row['TTY'] == ('SBD' if kind == 'brand' else 'SCD'):
                            current[name].add(int(row['RXCUI']))
    result = {}
    for name, ids in sorted(current.items()):
        if len(seen[name]) == 1:
            kind, form = next(iter(seen[name]))
            if form and form not in ('Pack', 'NA'):
                result[name] = {'form': form, 'kind': kind, 'exampleRxcui': min(ids)}
    payload = {'sourceUrl': metadata['sourceUrl'], 'sha256': metadata['sourceSha256'], 'names': result}
    REFERENCE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    rebuild(Path(sys.argv[1]))

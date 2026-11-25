"""Expose existing exact UHC policy branches; never infer PA/coverage status."""
import hashlib
import json
import re
from collections import defaultdict
from structured_statewide_criteria import assign_branch_pages, structure_policy, validate_structure

PLAN = 'uhc-community-az'
DUPLICATION_POLICIES = {'GL-735259', 'GL-733328'}
# GL-722213 names the age-based, nonpreferred and injectable branches separately.
RISPERIDONE_BRANCHES = {
    'ef1b74ce89ce3609': ('Brand Risperdal oral solution', [0, 14]),
    '3a61ac9c932595a2': ('Generic risperidone oral solution', [0, 14]),
    '9218dfef977f1cc2': ('Brand Risperdal tablets 0.5, 1, 2 or 3 mg', [0, 14]),
    **dict.fromkeys(
        ('88dcfe556959a236', '5c298a57a90c3332', 'fce9a9e679b436ee',
         'ed3c9eb0d5ff5667', '41d9e57befa93814'),
        ('Generic risperidone tablets 0.25–3 mg', [0]),
    ),
    **dict.fromkeys(
        ('8e6412598dc3cc82', '86a272013762dd71', '4a432871483f8345', 'e60cf4ef12c45d4c'),
        ('Brand Risperdal Consta', [12]),
    ),
}
# Reviewed October PDL names mapped to the November 2026 named-product branches.
# Match the payer's printed product field when aliases cross brand or release boundaries.
# A generic name shared between two products cannot transfer indication or route.
EXCLUDED_OCTOBER_POLICIES = {
    'soolantra (brand for ivermectin)': 'GL-140680',
    'tadalafil (pah) (generic for alyq)': 'GL-140729',
    'jynarque oral tablet (brand for tolvaptan)': 'GL-140869',
    'jynarque oral tablet therapy pack (brand for tolvaptan)': 'GL-140869',
    'samsca (brand for tolvaptan (hyponatremia))': 'GL-369225',
}

OCTOBER_POLICY_PRODUCTS = {
    'invega (brand for paliperidone er)': ('GL-722213', 'Brand Invega'),
    'clozapine oral tablet (generic for clozaril)': ('GL-722213', 'generic clozapine'),
    'dronabinol oral capsule (generic for marinol)': ('GL-397200', 'generic dronabinol'),
    'forteo (brand for teriparatide)': ('GL-755194', 'Brand Forteo'),
    'trokendi xr (brand for topiramate er)': ('GL-572198', 'Brand Trokendi XR'),
    'topiramate er oral capsule er 24 hour sprinkle': ('GL-572198', 'generic topiramate ER sprinkle'),
    'xeljanz xr (brand for tofacitinib citrate er)': ('GL-657310', 'Brand Xeljanz XR tabs'),
}

DPP4_BRANCHES = {
    'alogliptin benzoate': (0, 'Alogliptin'),
    'januvia (brand for sitagliptin phosphate)': (0, 'Brand Januvia'),
    'janumet (brand for sitagliptin phos-metformin hcl)': (0, 'Brand Janumet'),
    'sitagliptin phos-metformin hcl (generic for janumet)': (1, 'Generic sitagliptin phosphate/metformin'),
    'jentadueto xr': (1, 'Jentadueto XR'),
}

# The October PDL flags and the November policy answer different questions.
# Keep broad formulary flags intact and attach only the named, scoped branches.
ANTIDEPRESSANT_BRANCHES = {
    'sertraline hcl oral concentrate (generic for zoloft)': (
        'Generic sertraline oral solution',
        [(0, 'generic sertraline oral soln'), (1, 'generic sertraline tabs/oral soln')],
    ),
    'sertraline hcl oral tablet (generic for zoloft)': (
        'Generic sertraline tablets', [(1, 'generic sertraline tabs/oral soln')],
    ),
    'desvenlafaxine succinate er (generic for pristiq)': (
        'Generic desvenlafaxine ER', [(1, 'generic desvenlafaxine ER')],
    ),
    'pristiq (brand for desvenlafaxine succinate er)': (
        'Brand Pristiq', [(2, 'Brand Pristiq')],
    ),
}
ANTIDEPRESSANT_SCOPES = (
    'Requests for patients greater than 12 years of age',
    'PREFERRED DRUG Requests for patients 6 years of age or younger',
    'Non-Preferred Drugs',
)

PANTOPRAZOLE_PACKETS = {
    'pantoprazole sodium oral packet (generic for protonix)': (
        'Generic pantoprazole granules (packets)', 'generic pantoprazole suspension packets',
    ),
    'protonix oral packet (brand for pantoprazole sodium)': (
        'Brand Protonix granules (packets)', 'Brand Protonix suspension packets',
    ),
}

TRIAMCINOLONE_LISTINGS = {
    'triamcinolone acetonide suspension 40 mg/ml injection':
        'Triamcinolone acetonide injection (brand unspecified in formulary)',
    'triamcinolone acetonide suspension 40 mg/ml injection (generic for kenalog-40)':
        'Generic for Kenalog-40',
}

MAXALT_PRODUCTS = {
    'maxalt (brand for rizatriptan benzoate)': ('Maxalt tablets', 'Brand Maxalt'),
    'maxalt-mlt (brand for rizatriptan benzoate)': ('Maxalt-MLT ODT', 'Brand Maxalt MLT'),
}

OAB_PRODUCTS = {
    'myrbetriq oral suspension reconstituted er (brand for mirabegron er)': (
        'Myrbetriq ER granules for oral suspension', 'Brand Myrbetriq granules',
    ),
    'myrbetriq oral tablet extended release 24 hour (brand for mirabegron er)': (
        'Myrbetriq ER tablets', 'Brand Myrbetriq tabs',
    ),
    'toviaz (brand for fesoterodine fumarate er)': ('Brand Toviaz', 'Brand Toviaz'),
}

# October ACC rows reconciled against named branches in the November compilation.
# Quantity exceptions are kept separate from initial and renewal PA branches.
PCP_POLICY_ROWS = {
    '900b6f543a871255': ('GL-503307', [0, 1], [], 'all brands'),
    'c48e74b3ca337637': ('GL-503307', [0, 1], [], 'all brands'),
    '7643ae6c318710a6': ('GL-588187', [0, 1], [], 'Omnipod 5'),
    'fcc058d760894f93': ('GL-588187', [0, 1], [2], 'Omnipod 5'),
    '51396cfcdf274256': ('GL-369221', [0], [1], 'Test Strip Products'),
    'a0d828aff68fd9cc': ('GL-369221', [0], [1], 'Test Strip Products'),
    'a7836b3702968dcc': ('GL-714282', [0], [], 'Pradaxa Pellet Packs'),
    '466ed897a555d892': ('GL-689195', [0], [], 'Brand Vyvanse caps/chew tabs'),
    '67b306246b077d76': ('GL-689195', [0], [], 'Brand Vyvanse caps/chew tabs'),
    '4d48c8bd9a3822ca': ('GL-720193', [6, 7, 8, 9], [], 'Nurtec ODT'),
}

FORMS = r'oral|tablet|tablets|capsule|capsules|solution|suspension|injection|injectable|subcutaneous|intravenous|intramuscular|topical|cream|ointment|ophthalmic|otic|nasal|inhalation|inhaler|aerosol|powder|spray|prefilled|syringe|syringes|pen|kit|pack|vial|vials|chewable|disintegrating|hcl|hydrochloride|mg|mcg|ml|unit|units|act|actuat|dose|metered|breath|actuated|hfa|tabs|caps|soln|susp|packet|packets|reconstituted|cartridge|kwikpen|and|external|er|xr|dr|sr|pf|therapy|initiation|pk|titration|patient|month|sprinkle|sprinkles|soluble|dispersible|granules|auto|injector|transdermal|patch|recon|reconstitution|concentrate|intramuscular|patches|odt|for|rebidose|hr|hour|hours'

def identity(value):
    value = re.sub(r'\([^)]*\)|\[[^]]*\]', ' ', str(value).lower())
    value = re.sub(r'\bu[- ](\d+)\b', r'u\1', value)
    value = value.replace('delayed release', '')
    value = re.sub(r'\b\d+(?:\.\d+)?\s*(?:mg|mcg|ml|units?|hr|hours?)\b', ' ', value)
    value = re.sub(r'\b(?:brand|generic|non[- ]?preferred|preferred|drugs?|agents?|products?)\b\s*:?', ' ', value)
    value = re.sub(r'\b(?:' + FORMS + r')\b|\b\d+(?:\.\d+)?\b', ' ', value)
    return ' '.join(re.findall('[a-z][a-z0-9]*', value))

def alias_parts(product):
    product = re.sub(r'\b([A-Za-z][A-Za-z-]+)\s*/\s*\1\b', r'\1, \1', product, flags=re.I)
    product = re.sub(r'Asmanex HFA/Twisthaler', 'Asmanex HFA, Asmanex Twisthaler',product,flags=re.I)
    parts=[]
    for value in re.split(r'[,;]|\b(?:brand|generic)\b', product, flags=re.I):
        value=value.strip()
        if parts and re.fullmatch(r'\d+(?:\.\d+)?\s*(?:(?:mg|mcg|ml|units?|%)(?:\s*/\s*(?:hr|hour|ml))?)?',value,re.I):parts[-1]+=', '+value
        elif value:parts.append(value)
    return [v for v in parts if len(identity(v))>=4]

def aliases(product):
    return {identity(v) for v in alias_parts(product)}

def product_matches(record, product):
    names = [record['name'], record.get('brand',''), record.get('standardDisplayName','')]
    names += re.findall(r'\(\s*(?:brand|generic) for ([^)]+)\)', record['name'], re.I)
    names += re.findall(r'\[([^]]+)\]', record['name'])
    keys = {identity(n) for n in names if identity(n)}
    keys.update(identity(part) for part in alias_parts(record['name']))
    name = record['name'].lower()
    for alias in alias_parts(product):
        if identity(alias) not in keys:continue
        # Validate only the matched product's modifiers, never a different
        # medicine's strength/formulation in a comma-separated heading.
        lower = alias.lower()
        allowed = True
        if re.search(r'\bODT\b',alias,re.I) and not re.search(r'odt|disintegrating|dispersible|solutab',name):allowed=False
        route_patterns = {'oral':r'\boral\b|\b(?:tabs?|tablets?|caps?|capsules?|syrup|elixir|odt)\b', 'ophthalmic':r'ophthalmic', 'otic':r'\botic\b', 'nasal':r'\bnasal\b', 'inhalation':r'inhalation|inhaler|nebuliz', 'topical':r'topical|external|ointment|cream', 'transdermal':r'transdermal|\bpatch(?:es)?\b', 'subcutaneous':r'subcutaneous|\bsc\b', 'intravenous':r'intravenous|\biv\b', 'intramuscular':r'intramuscular|\bim\b'}
        src_routes={k for k,v in route_patterns.items() if re.search(v,lower)}
        dst_routes={k for k,v in route_patterns.items() if re.search(v,name)}
        if src_routes and dst_routes and not src_routes.intersection(dst_routes):allowed=False
        forms={'tablet':r'\b(?:tabs?|tablets?)\b','capsule':r'\b(?:caps?|capsules?)\b','liquid':r'\b(?:soln|solution|syrup|elixir|concentrate)\b','suspension':r'\b(?:susp|suspension)\b','patch':r'\bpatch(?:es)?\b','cream':r'\bcream\b','ointment':r'\bointment\b'}
        src_forms={k for k,v in forms.items() if re.search(v,lower)}
        dst_forms={k for k,v in forms.items() if re.search(v,name)}
        if src_forms and dst_forms and not src_forms.intersection(dst_forms):allowed=False
        for form in ['ointment','cream','ophthalmic','otic','nasal','extended release']:
            if form in lower and form not in name:allowed = False
        source_devices = [f for f in ['pen','syringe','vial','autoinjector'] if re.search(r'\b'+f+r'\b',lower)]
        if 'kwikpen' in lower:source_devices.append('pen')
        if source_devices and not any((f in name or (f=='pen' and 'kwikpen' in name) or (f=='autoinjector' and 'auto-injector' in name)) for f in source_devices):allowed = False
        for unit in ['mg','mcg']:
            source_strengths = {float(n) for n in re.findall(r'\b(\d+(?:\.\d+)?)\s*'+unit+r'\b',alias,re.I)}
            actual = {float(n) for n in re.findall(r'\b(\d+(?:\.\d+)?)\s*'+unit+r'\b',record['name'],re.I)}
            if source_strengths and actual and not actual <= source_strengths:allowed = False
        ratio_pattern=r'\b(\d+(?:\.\d+)?)\s*(mg|mcg)\s*/\s*(\d+(?:\.\d+)?)?\s*ml\b'
        ratios=lambda value:{(unit.lower(),float(n)/float(volume or 1)) for n,unit,volume in re.findall(ratio_pattern,value,re.I)}
        if ratios(alias) and ratios(name) and not ratios(name)<=ratios(alias):allowed=False
        if 'delayed release' in lower or re.search(r'\bDR\b',alias,re.I):
            if not re.search(r'delayed release|\bdr\b',name):allowed=False
        if 'extended release' in lower or re.search(r'\b(?:ER|XR)\b',alias):
            if not re.search(r'extended release|\b(?:er|xr)\b',name):allowed = False
        source_pct = set(re.findall(r'(\d+(?:\.\d+)?)\s*%',alias))
        actual_pct = set(re.findall(r'(\d+(?:\.\d+)?)\s*%',name))
        if source_pct and actual_pct and not actual_pct <= source_pct:allowed = False
        if allowed:return True
    return False

def publish_uhc_policy_access(data, source_dir, output_dir):
    structured = {}
    policies = {p['policyCode']: p for p in data['policies'] if p['planId'] == PLAN}
    for code, policy in policies.items():
        source = (source_dir / policy['sourceTextUrl'].lstrip('./')).read_text()
        if code == 'GL-545275':
            # This source has a Diagnosis heading rather than Product Name.
            # Use its actual source offset; no synthetic clinical text is inserted.
            from structured_statewide_criteria import span, blocks, FIELD, REVISION, BACKGROUND
            start = re.search(r'^Diagnosis\s*$',source,re.M).start()
            end = BACKGROUND.search(source,start).start()
            history = REVISION.search(source,end).start()
            approval = re.search(r'^\s*Approval Criteria[\t ]*$',source[start:end],re.M)
            header_end = start + approval.start(); criteria_start = start + approval.end()
            notes = re.search(r'^[\t ]*Notes[\t ]*$',source[criteria_start:end],re.M)
            criteria_end = criteria_start + notes.start() if notes else end
            fields = list(FIELD.finditer(source,start,header_end))
            branch = {'start':start,'end':end,'fields':{},'criteria':blocks(source,criteria_start,criteria_end),'notes':blocks(source,criteria_start+notes.end(),end) if notes else []}
            for i,f in enumerate(fields):branch['fields'][f[1].rstrip(':')] = span(source,f.end(),fields[i+1].start() if i+1<len(fields) else header_end)
            result = dict(schemaVersion=1,policyCode=code,title=policy['name'],sourceEffective=policy['sourceEffective'],sourcePage=policy['sourcePage'],sourceLastPage=policy['sourceLastPage'],sourceSha256=hashlib.sha256(source.encode()).hexdigest(),editorialStatus='Source-transcribed clinical fields; clinician approval pending',context=span(source,0,start),branches=[branch],supplement={**span(source,end,history),'verbatim':source[end:history]},history=span(source,history,len(source)))
            assign_branch_pages(result, source)
            validate_structure(result,source)
        else:result = structure_policy(policy, source)
        # Repeated PDF running headers are furniture, never a clinical requirement.
        for b in result['branches']:
            for f in list(b['fields'].values()) + b['criteria'] + b['notes']:
                display = re.sub(r'UnitedHealthcare Community Plan of Arizona [–-] Clinical Pharmacy Guidelines\s*', '', f.get('displayText',f['text']))
                if display != f['text']: f['displayText'] = display.strip()
        if code in DUPLICATION_POLICIES:
            assert len(result['branches']) == 1
            fields = result['branches'][0]['fields']
            assert fields['Diagnosis']['text'] == 'DUR: Therapeutic Duplication'
            assert fields['Guideline Type']['text'] == 'Administrative'
        path = 'clinical-criteria/uhc-' + code.lower() + '.json'
        payload = json.dumps(result,ensure_ascii=False,separators=(',',':')).encode()
        (output_dir/path).write_bytes(payload)
        policy['structuredCriteriaUrl'] = './'+path+'?v='+hashlib.sha256(payload).hexdigest()[:12]
        policy['structuredBranchCount'] = len(result['branches'])
        structured[code] = result
    by_key = defaultdict(list)
    for code,p in structured.items():
        if code in {'GL-231255','GL-140667','GL-512232','GL-545275'}:continue
        for i,b in enumerate(p['branches']):
            product = b['fields'].get('Product Name',{}).get('displayText') or b['fields'].get('Product Name',{}).get('text','')
            for key in sorted(aliases(product)):by_key[key].append((code,i,product))
    totals = defaultdict(int); missing = []
    for record in data['medications']:
        if record['planId'] != PLAN or record['recordType'] != 'formulary':continue
        october_name = record['name'].lower() if record.get('sourceEffective') == '2026-10-01' else ''
        if october_name in TRIAMCINOLONE_LISTINGS:
            record['coverageProductLabel'] = TRIAMCINOLONE_LISTINGS[october_name]
        pa = record['pa'] in {'required','conditional'}; ql = bool(record.get('qlAmount') or record.get('qlDays'))
        if not (pa or ql):continue
        bindings = []
        def add(code, indexes, role):
            if not indexes:return
            binding={'policyId':policies[code]['id'],'branchIndexes':indexes,'role':role}
            if role=='product':
                labels={}
                for i in indexes:
                    f=structured[code]['branches'][i]['fields'].get('Product Name',{})
                    product=f.get('displayText') or f.get('text','')
                    for alias in alias_parts(product):
                        if product_matches(record,alias) and re.search(r'\d+|extended release|\b(?:ER|XR)\b',alias,re.I):labels[str(i)]=alias;break
                if labels:binding['branchLabels']=labels
            bindings.append(binding)
        names = [record['name'],record.get('brand',''),record.get('standardDisplayName','')] + re.findall(r'\(\s*(?:brand|generic) for ([^)]+)\)|\[([^]]+)\]',record['name'],re.I)
        keys = {identity(n if isinstance(n,str) else ' '.join(n)) for n in names}
        keys.update(identity(part) for part in alias_parts(record['name']))
        matched = defaultdict(set)
        for key in sorted(keys):
            for code,i,product in by_key.get(key,[]):
                if product_matches(record,product):matched[code].add(i)
        if october_name in {'desmopressin acetate injection (generic for ddavp)',
                            'desmopressin acetate pf (generic for ddavp pf)'}:
            # GL-565277 names tablets, nasal spray and Desmoda oral solution.
            matched.pop('GL-565277', None)
            record['unverifiedPolicyCode'] = 'GL-565277'
        excluded_code = EXCLUDED_OCTOBER_POLICIES.get(october_name)
        if excluded_code:
            matched.pop(excluded_code, None)
            record['excludedPolicyCode'] = excluded_code
            if october_name == 'soolantra (brand for ivermectin)':
                record['unverifiedPolicyCode'] = excluded_code
        exact_product = OCTOBER_POLICY_PRODUCTS.get(october_name)
        if exact_product:
            code, product = exact_product
            indexes = set()
            for i, branch in enumerate(structured[code]['branches']):
                field = branch['fields']['Product Name']
                names = ' '.join(field.get('displayText', field['text']).split()).split(', ')
                if product in names:
                    indexes.add(i)
            assert indexes, (code, product)
            matched[code] = indexes
        # DEC-05/12/13/14/19/20: exact October SC listings only.
        # The named May 2026 guideline includes a conditional nonpreferred rule.
        # Retain the structured source verbatim; scope the clinician rendering.
        sc_reviews = {
            'uhc-oct-complete-6e31fd16d0c3fee4': (
                'actemra subcutaneous', 'Actemra SC', 'non_preferred',
                'Actemra (Tocilizumab) Subcutaneous Injection',
                'FDA label: 162 mg/0.9 mL prefilled syringe or ACTPen. Adult SSc-ILD is labeled for SC use; ACTPen use has not been studied for SSc-ILD. Do not transfer IV criteria. Exact payer device/package and numeric quantity limit are unverified.',
                '2e5365ff-cb2a-4b16-b2c7-e35c6bf2de13'),
            'uhc-oct-complete-2e1049037c5dbd67': (
                'avtozma subcutaneous', 'Avtozma SC', 'preferred',
                'Avtozma (Tocilizumab-anoh) Subcutaneous Injection',
                'FDA label: 162 mg/0.9 mL prefilled syringe or autoinjector. SSc-ILD is a named payer pathway but is not an FDA-labeled Avtozma indication. CRS and COVID-19 are IV-only indications. Exact payer device/package and numeric quantity limit are unverified.',
                '581c288f-8015-40ef-a4c3-683c96db193d'),
            'uhc-oct-complete-4bfb77000b6496ad': (
                'tyenne subcutaneous', 'Tyenne SC', 'preferred',
                'Tyenne (Tocilizumab-aazg) Subcutaneous Injection',
                'FDA label: 162 mg/0.9 mL prefilled syringe or autoinjector. SSc-ILD is a named payer pathway but is not an FDA-labeled Tyenne indication. CRS and COVID-19 are IV-only indications. Boxed warning: serious infections. Exact payer device/package and numeric quantity limit are unverified.',
                '87ac5047-4f2b-4571-a8a8-32e08865f379'),
        }
        sc_review = sc_reviews.get(record['id'])
        if sc_review:
            source_name, product, preference, label, note, label_id = sc_review
            code = 'GL-565279'
            assert october_name == source_name and pa and record['pa'] == 'required'
            assert record['preferred'] == preference
            assert policies[code]['policyEffective'] == '2026-05-01'
            branches = structured[code]['branches']
            assert len(branches) == 7
            assert [branch['sourcePage'] for branch in branches] == list(range(1728, 1735))
            for branch in branches:
                field = branch['fields']['Product Name']
                assert product in ' '.join(field.get('displayText', field['text']).split()).split(', ')
                assert branch['fields']['Guideline Type']['text'] == 'Prior Authorization'
                assert branch['criteria'][-2]['kind'] == 'connector' and branch['criteria'][-2]['text'] == 'AND'
                assert branch['criteria'][-1]['text'].startswith('3 - If the request is non-preferred')
                assert 'tocilizumab biosimilars' in branch['criteria'][-1]['text']
            matched.pop(code, None)
            add(code, list(range(7)), 'product')
            bindings[-1]['productLabel'] = product
            if preference == 'preferred':
                bindings[-1]['omitNonpreferredCondition'] = True
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': label, 'dosageForm': 'subcutaneous injection', 'note': note,
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=' + label_id,
            }
        # DEC-05/12/13/14/19/20: label identity only; no exact UHC named pharmacy criteria.
        if record['id'] == 'uhc-oct-complete-a8d0977aeaff8cc1':
            assert october_name == 'avlayah' and record['pa'] == 'required'
            assert record['preferred'] == 'preferred'
            # The separate AHCCCS FFS/AIHP guideline is not a UHC product binding.
            assert not matched, ('Avlayah: review newly available exact-plan policy before use', matched)
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Avlayah (Tividenofusp alfa-eknm) IV Infusion',
                'dosageForm': 'powder for intravenous infusion',
                'note': 'FDA label: 150 mg lyophilized single-dose vial for IV infusion after preparation; pediatric initiation at 5 kg or more before advanced neurologic impairment. Not recommended with other enzyme replacement therapies for Hunter syndrome. Boxed warning: anaphylaxis. Exact UHC initial/renewal criteria are unverified; statewide criteria are reference only.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=014d92c1-b643-4680-8ca6-f0b3307da915',
            }
        # DEC-05/12/13/14/19/20: exact UHC nonpreferred glucose strip rows.
        # GL-369221 is a class PA/quantity exception; it does not identify a payer NDC or a numeric limit.
        strip_reviews = {
            'uhc-oct-complete-0851f010ae01a71d': (
                'blood glucose test strips (brand for blood glucose test)',
                'Blood Glucose Test Strips (Meter Model Unspecified by UHC)',
                'The payer does not identify a compatible meter model. Use only strips recommended for the actual meter; do not assume interchangeability.',
                'https://www.fda.gov/medical-devices/blood-glucose-monitoring-devices/users-blood-glucose-meters-must-use-only-test-strip-recommended-use-their-meter'),
            'uhc-oct-complete-b500755c2b65a98f': (
                'glucocard expression test (brand for blood glucose test)',
                'GLUCOCARD Expression Blood Glucose Test Strips',
                'Manufacturer specifies GLUCOCARD Expression meter; do not substitute Shine strips.',
                'https://arkrayusa.com/diabetes-management/consumer-healthcare-products/glucocard/glucocard-expression/'),
            'uhc-oct-complete-58ab445334122bcf': (
                'glucocard shine test (brand for blood glucose test)',
                'GLUCOCARD Shine Blood Glucose Test Strips',
                'Manufacturer specifies Shine, Shine XL, Shine Connex and Shine Express meters; distinct from Expression.',
                'https://arkrayusa.com/diabetes-management/consumer-healthcare-products/glucocard/glucocard-shine/'),
            'uhc-oct-complete-9f988a2e077865db': (
                'precision xtra blood glucose strips (brand for blood glucose test)',
                'Precision Xtra Blood Glucose Test Strips',
                'FDA device listing identifies glucose test strips, not ketone strips. Confirm the exact compatible meter and package.',
                'https://www.accessdata.fda.gov/scrIpts/cdrh/cfdocs/cfRL/rl.cfm?lid=787017&lpcd=NBW'),
            'uhc-oct-complete-6176006028f31af2': (
                'relion true metrix test strips (brand for blood glucose test)',
                'ReliOn TRUE METRIX Blood Glucose Test Strips',
                'TRUE METRIX self-monitoring strip family is specified for the TRUE METRIX AIR meter. Confirm the exact branded package; do not infer compatibility with other meter families.',
                'https://www.trividiahealth.com/wp-content/uploads/2024/09/TRUE_METRIX_InstructionsForUse_RF3TVH03r53.pdf'),
        }
        if record['id'] in strip_reviews:
            expected, label, note, source = strip_reviews[record['id']]
            assert october_name == expected and record['pa'] == 'required'
            assert record['preferred'] == 'non_preferred' and ql
            code = 'GL-369221'
            assert policies[code]['policyEffective'] == '2025-09-01'
            branches = structured[code]['branches']
            assert len(branches) == 2
            for i, (product, typ) in enumerate([
                ('Non-preferred Test Strip Products', 'Prior Authorization'),
                ('Preferred or Non-preferred Test Strip Products', 'Quantity Limit'),
            ]):
                fields = branches[i]['fields']
                assert fields['Product Name']['text'] == product
                assert fields['Guideline Type']['text'] == typ
            assert set(matched).issubset({code}), ('Review new named policy', record['id'], matched)
            matched.pop(code, None)
            add(code, [0], 'product')
            bindings[-1]['productLabel'] = label + ' (nonpreferred test strip class)'
            add(code, [1], 'quantity')
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': label, 'dosageForm': 'blood glucose test strips',
                'note': note + ' UHC GL-369221 class criteria apply; authorization stage is not specified. Exact payer package and numeric quantity limit remain unverified.',
                'deviceSourceUrl': source,
            }
        if record['id'] == 'uhc-oct-complete-1c1902ab9f482601':
            assert october_name == 'true metrix air glucose meter kit (brand for blood glucose monitor system)'
            assert record['pa'] == 'required' and record['preferred'] == 'non_preferred' and ql
            # GL-140734 background names the ReliOn-branded kit and requires NDC-level approval.
            # Do not attach that policy to this exact payer row without the product linkage.
            assert set(matched).issubset({'GL-140734'}), ('Review new named policy', matched)
            matched.pop('GL-140734', None)
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'TRUE METRIX AIR Blood Glucose Meter Kit',
                'dosageForm': 'blood glucose meter kit',
                'note': 'Manufacturer specifies TRUE METRIX self-monitoring test strips only. UHC lists this meter as nonpreferred with PA and QL. GL-140734 requires NDC-level approval; exact applicability, package and numeric quantity limit remain unverified.',
                'deviceSourceUrl': 'https://www.trividiahealth.com/wp-content/uploads/2024/01/REA4TVH03-TRUE-METRIX-AIR-Owners-Booklet_012224.pdf',
            }
        # DEC-05/12/13/14/19/20: exact October listing, FDA identity only.
        # GL-231255 and GL-140667 are administrative, not named product criteria.
        label_holds = {
            'uhc-oct-complete-3030be16c6c4522a': (
                "alphagan p (brand for brimonidine tartrate)", "Alphagan P (Brimonidine Tartrate) Ophthalmic Solution", "ophthalmic solution",
                "FDA label: 0.1% and 0.15% ophthalmic solutions; not Mirvaso topical gel. UHC does not specify concentration or package. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                '264c4494-c225-486f-888a-caaf36be46b3', True),
            'uhc-oct-complete-84a578e96b55a0cf': (
                "mirvaso external gel 0.33 % (brand for brimonidine tartrate)", "Mirvaso (Brimonidine) 0.33% Topical Gel", "topical gel",
                "FDA label: 0.33% brimonidine free base (5 mg/g tartrate), for facial erythema of rosacea. Not for ophthalmic, oral or intravaginal use. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                'f6a4353f-ae69-4214-901f-e5d42a6fbde7', True),
            'uhc-oct-complete-c5aa345f96aaec5c': (
                "combigan (brand for brimonidine tartrate-timolol)", "Combigan (Brimonidine Tartrate / Timolol) Ophthalmic Solution", "ophthalmic solution",
                "FDA label: 0.2% brimonidine tartrate / 0.5% timolol; combination, not single-agent brimonidine. Contraindicated in asthma or history of asthma and severe COPD. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                'feaf1480-a4b8-4486-992a-96be3a596243', True),
            'uhc-oct-complete-bec7f75a1db17d2b': (
                "prolensa (brand for bromfenac sodium)", "Prolensa (Bromfenac) Ophthalmic Solution", "ophthalmic solution",
                "FDA label: 0.07% ophthalmic solution, once daily for postoperative cataract inflammation and pain; do not transfer dosing from other bromfenac concentrations. UHC does not specify concentration or package. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                '4e072537-f73c-4a96-a65f-e2805ce112d8', True),
            'uhc-oct-complete-48aa5c3126dac1f1': (
                "besivance (brand for besifloxacin hcl)", "Besivance (Besifloxacin) Ophthalmic Suspension", "ophthalmic suspension",
                "FDA label: 0.6% (6 mg/mL) topical ophthalmic suspension, not for injection into the eye. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                'a3e6d688-7e5e-4ca3-b27e-79756c322a32', True),
            'uhc-oct-complete-ccb3e29f79cd93b8': (
                "bijuva oral capsule 1-100 mg", "Bijuva (Estradiol / Progesterone) 1 mg / 100 mg Oral Capsule", "oral capsule",
                "FDA label: estradiol 1 mg plus progesterone 100 mg, for menopausal vasomotor symptoms in patients with a uterus. UHC row specifies 1 mg / 100 mg; do not transfer its benefits to the 0.5 mg / 100 mg presentation. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                '59eadb88-c9f3-4871-b176-7ddd98faf9bc', True),
            'uhc-oct-complete-c24ea1cc8b559162': (
                "lumigan (brand for bimatoprost)", "Lumigan (Bimatoprost) Ophthalmic Solution", "ophthalmic solution",
                "FDA label: US 0.01% (0.1 mg/mL) ophthalmic solution. Distinct from 0.03% formulations and bimatoprost eyelash treatment. UHC does not specify concentration or package. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                'a5e67c75-db88-4372-bb07-c8dd15c97631', True),
            'uhc-oct-complete-a9f6c2797d55304f': (
                "pylera (brand for bis subcit-metronid-tetracyc)", "Pylera (Bismuth Subcitrate Potassium / Metronidazole / Tetracycline HCl) Oral Capsule", "oral capsule",
                "FDA label: 140 mg / 125 mg / 125 mg per capsule; omeprazole is administered separately and is not included. Contraindicated in pregnancy and severe renal impairment. Exact UHC product-specific initial/renewal criteria are unverified.",
                '5cdacbf5-67be-42eb-bd54-8acc32ea1abc', False),
            'uhc-oct-complete-9248b8305ab77197': (
                'reyataz oral capsule (brand for atazanavir sulfate)', 'Reyataz (Atazanavir) Oral Capsule', 'oral capsule',
                'FDA label: 200 mg or 300 mg capsules; take with food and do not open capsules. Distinct from 50 mg oral powder packets. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.',
                '165cff62-b284-4a27-a65d-9ec8a5bfcdd8', True),
            'uhc-oct-complete-101e5350ddd51acd': (
                'azasite', 'AzaSITE (Azithromycin) Ophthalmic Solution', 'ophthalmic solution',
                'FDA label: 1% (10 mg/mL) ophthalmic solution; for ocular use only, not oral azithromycin. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.',
                '0c5d6f5e-18ea-436f-8c62-bbaf66effe3d', True),
            'uhc-oct-complete-826e676ded0d2967': (
                'edarbi (brand for azilsartan medoxomil)', 'Edarbi (Azilsartan Medoxomil) Oral Tablet', 'oral tablet',
                'FDA label: 40 mg or 80 mg tablets; not the azilsartan/chlorthalidone combination. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.',
                '52b27c75-9f5a-4816-bafd-dace9d7d2063', True),
            'uhc-oct-complete-aa50f2e41f4faa14': (
                'apidra solostar', 'Apidra SoloStar (Insulin Glulisine) Prefilled Pen', 'prefilled pen injection',
                'FDA label: U-100 (100 units/mL), 3 mL single-patient-use prefilled pen for subcutaneous injection only. Not the vial; do not use the pen for IV or pump administration. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.',
                'e7af6a7a-8046-4fb4-9979-4ec4230b23aa', True),
            'uhc-oct-complete-ad3656a231a145e1': (
                'apidra vial', 'Apidra (Insulin Glulisine) Vial for Injection', 'vial injection',
                'FDA label: U-100 (100 units/mL), 10 mL multiple-dose vial; subcutaneous injection or pump, or diluted IV under medical supervision. Distinct from the SoloStar pen. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.',
                'e7af6a7a-8046-4fb4-9979-4ec4230b23aa', True),
            'uhc-oct-complete-b194127f86ac4236': (
                'accrufer', 'Accrufer (Ferric Maltol) Oral Capsule', 'oral capsule',
                'FDA label: 30 mg iron as ferric maltol per capsule; swallow whole. Avoid use during active IBD flare and with IV iron. Not a ferrous salt or IV iron formulation. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.',
                '367ac157-2d25-4f34-99ce-b126e0f03851', True),
            'uhc-oct-complete-d9b404be1858112f': (
                'angeliq', 'Angeliq (Drospirenone / Estradiol) Oral Tablet', 'oral tablet',
                'FDA label: drospirenone/estradiol 0.25/0.5 mg or 0.5/1 mg tablets; menopausal hormone therapy, not contraception. Exact UHC product-specific initial/renewal criteria are unverified.',
                '761834c2-6b61-4583-84c2-f1ca4a97c4f2', False),
            'uhc-oct-complete-ae9928afe2cbe71e': (
                'annovera', 'Annovera (Segesterone Acetate / Ethinyl Estradiol) Vaginal System', 'vaginal system',
                'FDA label: reusable vaginal system releasing an average of 0.15/0.013 mg per day; 21 days in, 7 days out, for 13 cycles. Distinct from monthly replacement rings. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.',
                'eb18194f-2021-41fa-8bdf-31e0c0eb646b', True),
        }
        if record['id'] in label_holds:
            expected, label, form, note, label_id, has_ql = label_holds[record['id']]
            assert october_name == expected and record['pa'] == 'required'
            assert record['preferred'] == 'non_preferred' and bool(ql) == has_ql
            assert not matched, ('Review newly available named criteria before use', record['id'], matched)
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': label, 'dosageForm': form, 'note': note,
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=' + label_id,
            }
        # DEC-05/12/13/14/19/20: UHC Basaglar KwikPen, not a blanket glargine benefit.
        # Preserve therapeutic duplication as an administrative DUR pathway, not a named PA.
        if record['id'] == 'uhc-oct-complete-180f1c7535eea5b2':
            assert october_name == 'basaglar kwikpen' and record['pa'] == 'required'
            assert record['preferred'] == 'non_preferred' and ql
            code = 'GL-735259'
            assert policies[code]['policyEffective'] == '2026-11-01'
            fields = structured[code]['branches'][0]['fields']
            assert 'Basaglar Kwikpen' in ' '.join(fields['Product Name']['text'].split())
            assert fields['Guideline Type']['text'] == 'Administrative'
            assert set(matched).issubset({code}), ('Review new named criteria', matched)
            matched.pop(code, None)
            add(code, [0], 'duplication')
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Basaglar KwikPen (Insulin Glargine) Prefilled Pen',
                'dosageForm': 'prefilled pen injection',
                'note': 'FDA label: 100 units/mL (U-100), 3 mL single-patient-use pen for subcutaneous injection; do not mix or dilute. Distinct from Tempo Pen and U-300 glargine. Therapeutic duplication criteria apply to DUR review, not routine product-specific authorization. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=0ad21db3-2b1c-4ed9-a687-bdd6a74d0aae',
            }
        # DEC-05/12/13/14/19/20: preferred oral solution, not a named PA policy.
        if record['id'] == 'uhc-oct-complete-c80e5c34df4eadf5':
            assert october_name == 'baraclude oral solution' and record['pa'] == 'required'
            assert record['preferred'] == 'preferred' and ql
            assert not matched, ('Review newly available named criteria before use', record['id'], matched)
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Baraclude (Entecavir) Oral Solution',
                'dosageForm': 'oral solution',
                'note': 'FDA label: 0.05 mg/mL oral solution, distinct from tablets; use solution for pediatric patients weighing up to 30 kg. Boxed warnings: hepatitis B exacerbation after stopping therapy, HIV resistance without effective HIV treatment, lactic acidosis and hepatomegaly. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.',
                'labelUrl': 'https://www.accessdata.fda.gov/drugsatfda_docs/label/2026/021797s027lbl.pdf',
            }
        # DEC-05/12/13/14/19/20: exact pharmacy SQ policy; never inherit IV medical-benefit criteria.
        if record['id'] == 'uhc-oct-complete-36c4a27401324b71':
            assert october_name == 'benlysta subcutaneous solution auto-injector'
            assert record['pa'] == 'required' and record['preferred'] == 'non_preferred' and ql
            code = 'GL-140941'
            assert policies[code]['policyEffective'] == '2022-12-01'
            branches = structured[code]['branches']
            assert len(branches) == 3
            assert [b['sourcePage'] for b in branches] == [226, 227, 228]
            for index, (diagnosis, stage) in enumerate([
                ('Systemic Lupus Erythematosus', 'Initial Authorization'),
                ('Active Lupus Nephritis', 'Initial Authorization'),
                ('Systemic Lupus Erythematosus, Active Lupus Nephritis', 'Reauthorization'),
            ]):
                fields = branches[index]['fields']
                assert fields['Product Name']['text'] == 'Benlysta SQ'
                assert fields['Diagnosis']['text'] == diagnosis
                assert fields['Therapy Stage']['text'] == stage
                assert fields['Guideline Type']['text'] == 'Prior Authorization'
            matched.pop(code, None)
            add(code, [0, 1, 2], 'product')
            bindings[-1]['productLabel'] = 'Benlysta SQ (autoinjector)'
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Benlysta (Belimumab) Subcutaneous Autoinjector',
                'dosageForm': 'subcutaneous autoinjector',
                'note': 'FDA label: 200 mg/mL single-dose autoinjector, not the prefilled syringe or IV powder vial. FDA-labeled pediatric SC use is autoinjector-only with weight-based dosing; the prefilled syringe has not been studied under age 18. Exact payer numeric quantity limit is unverified.',
                'labelUrl': 'https://www.accessdata.fda.gov/drugsatfda_docs/label/2026/125370s090lbl.pdf',
            }
        constipation_code = 'GL-720196'
        if october_name.startswith(('lubiprostone capsule ', 'prucalopride succinate (generic for ')):
            # The October 18 policy removed these generics from its PA targets.
            # Keep October 1 PDL flags as source evidence and never bind brand criteria.
            matched.pop(constipation_code, None)
        if october_name == 'linzess':
            # The PDL prints DX2RX and QL. The named policy is independently
            # relevant without turning its existence into a PDL PA flag.
            branches = structured[constipation_code]['branches']
            assert branches[2]['fields']['Product Name']['text'] == 'Linzess'
            assert 'Linzess' in branches[7]['fields']['Product Name']['text'].split(', ')
            matched.pop(constipation_code, None)
            add(constipation_code, [2, 7], 'product')
            bindings[-1]['productLabel'] = 'Linzess oral capsules'
        if october_name in MAXALT_PRODUCTS:
            code = 'GL-742200'
            label, product = MAXALT_PRODUCTS[october_name]
            assert pa and ql and policies[code]['policyEffective'] == '2026-11-01'
            branches = structured[code]['branches']
            assert product in branches[0]['fields']['Product Name']['text'].split(', ')
            assert 'Brand Maxalt and Maxalt MLT' in branches[3]['fields']['Product Name']['text']
            assert branches[3]['fields']['Guideline Type']['text'] == 'Quantity Limit'
            matched.pop(code, None)
            add(code, [0], 'product')
            bindings[-1]['productLabel'] = label
            add(code, [3], 'quantity')
        if october_name == 'sumatriptan succinate oral (generic for imitrex)':
            # The oral listing cannot inherit tablet-, nasal-, or injection-specific exceptions.
            matched.pop('GL-742200', None)
        dpp4 = DPP4_BRANCHES.get(record['name'].lower()) if pa and record.get('sourceEffective') == '2026-10-01' else None
        if dpp4:
            index, label = dpp4
            assert all(policies[code]['policyEffective'] == '2026-11-01' for code in ('GL-752241', 'GL-735259'))
            for code, branch in (('GL-752241', index), ('GL-735259', 0)):
                products = structured[code]['branches'][branch]['fields']['Product Name']['text']
                assert re.search(r'(?<![\w/])' + re.escape(label) + r'(?![\w/-])', ' '.join(products.split()), re.I), (code, label)
                matched.pop(code, None)
            add('GL-752241', [index], 'product')
            bindings[-1]['productLabel'] = label
            add('GL-735259', [0], 'duplication')
        antidepressant = ANTIDEPRESSANT_BRANCHES.get(record['name'].lower()) if record.get('sourceEffective') == '2026-10-01' else None
        if antidepressant:
            code = 'GL-743248'
            label, branches = antidepressant
            assert policies[code]['policyEffective'] == '2026-11-01'
            for index, product in branches:
                fields = structured[code]['branches'][index]['fields']
                products = fields['Product Name'].get('displayText', fields['Product Name']['text'])
                assert product in products.split(', '), (code, index, product)
                assert fields['Diagnosis']['text'] == ANTIDEPRESSANT_SCOPES[index]
                assert fields['Guideline Type']['text'] == 'Prior Authorization'
            matched.pop(code, None)
            add(code, [index for index, _ in branches], 'product' if pa else 'age_scoped')
            bindings[-1]['productLabel'] = label
        packet = PANTOPRAZOLE_PACKETS.get(record['name'].lower()) if record.get('sourceEffective') == '2026-10-01' else None
        if packet:
            code = 'GL-255208'
            label, product = packet
            assert record['pa'] == 'not_specified' and record['ageLimited']
            assert policies[code]['policyEffective'] == '2025-06-01'
            branch, = structured[code]['branches']
            assert product in branch['fields']['Product Name']['text'].split(', ')
            assert branch['fields']['Guideline Type']['text'] == 'Prior Authorization'
            assert branch['criteria'][-2]['kind'] == 'connector'
            assert branch['criteria'][-1]['text'].startswith('2 - If the request is for Brand Nexium')
            add(code, [0], 'packet_reference')
            bindings[-1]['productLabel'] = label
        if record.get('sourceEffective') == '2026-10-01':
            name = record['name'].lower()
            if name == 'fesoterodine fumarate er (generic for toviaz)':
                record['coverageProductLabel'] = 'Generic fesoterodine ER'
            if name in OAB_PRODUCTS:
                code = 'GL-647193'
                label, product = OAB_PRODUCTS[name]
                assert pa and policies[code]['policyEffective'] == '2026-08-01'
                assert matched.pop(code) == {0}
                branch, = structured[code]['branches']
                assert product in branch['fields']['Product Name']['text'].split(', ')
                add(code, [0], 'product')
                bindings[-1]['productLabel'] = label
        risperidone = RISPERIDONE_BRANCHES.get(record['id'].removeprefix('uhc-oct-complete-'))
        if risperidone:
            code = 'GL-722213'
            label, indexes = risperidone
            branches = structured[code]['branches']
            assert october_name and pa and matched.get(code, set()).issuperset(indexes)
            assert branches[0]['fields']['Diagnosis']['text'] == 'Patients Under 6 Years Old'
            assert branches[12]['fields']['Product Name']['text'] == 'Brand Risperdal Consta, Uzedy'
            assert branches[14]['fields']['Diagnosis']['text'] == 'Non-Preferred Drugs**'
            matched.pop(code)
            add(code, indexes, 'product')
            bindings[-1]['productLabel'] = label
        # The October PDL prints only ACTHAR and CORTROPHIN, without a device.
        # The November source retains the vial-only infantile spasms branch
        # separately from the OMS branch; never extend vial criteria to injectors.
        if october_name in {'acthar', 'cortrophin'}:
            code = 'GL-235210'
            expected_ids = {'acthar': '14411026d49668ea', 'cortrophin': '9b40fc8558feebd0'}
            assert record['id'] == 'uhc-oct-complete-' + expected_ids[october_name]
            assert pa and ql and policies[code]['policyEffective'] == '2025-05-01'
            first, second = structured[code]['branches']
            assert first['fields']['Product Name']['text'] == 'Acthar Gel vial'
            assert second['fields']['Product Name']['text'] == 'Acthar Gel, Cortrophin Gel'
            assert 'Infantile spasm' in first['fields']['Diagnosis']['text']
            assert 'Opsoclonus-myoclonus' in second['fields']['Diagnosis']['text']
            matched.pop(code, None)
            indexes = [0, 1] if october_name == 'acthar' else [1]
            add(code, indexes, 'product')
            bindings[-1]['branchLabels'] = (
                {'0': 'Acthar Gel vial only (PDL device unspecified)',
                 '1': 'Acthar Gel - OMS (confirm covered device)'}
                if october_name == 'acthar' else
                {'1': 'Cortrophin Gel - OMS (confirm covered vial or syringe)'})
        reviewed = PCP_POLICY_ROWS.get(record['id'].removeprefix('uhc-oct-complete-'))
        if reviewed and october_name and pa:
            code, pa_indexes, quantity_indexes, product = reviewed
            for index in pa_indexes + quantity_indexes:
                assert product in structured[code]['branches'][index]['fields']['Product Name']['text']
            matched.pop(code, None)
            add(code, pa_indexes, 'product')
            bindings[-1]['productLabel'] = record['name'].split(' (')[0]
            if ql:
                add(code, quantity_indexes, 'quantity')
        for code,indexes in sorted(matched.items()):
            if code in DUPLICATION_POLICIES:
                if pa:add(code,sorted(indexes),'duplication')
                continue
            pa_indexes=[];ql_indexes=[]
            for i in sorted(indexes):
                dx=structured[code]['branches'][i]['fields'].get('Diagnosis',{})
                scope=dx.get('displayText') or dx.get('text','')
                if re.fullmatch(r'Non[- ]?Preferred(?: (?:Drugs|Agents|Products))?',scope,re.I) and record['preferred']!='non_preferred':continue
                if re.fullmatch(r'Preferred(?: (?:Drugs|Agents|Products))?',scope,re.I) and record['preferred']!='preferred':continue
                typ=structured[code]['branches'][i]['fields'].get('Guideline Type',{}).get('text','').lower()
                (ql_indexes if 'quantity' in typ else pa_indexes).append(i)
            if pa:add(code,pa_indexes,'product')
            if ql:add(code,ql_indexes,'quantity')
        text = ' '.join([record['name'],record.get('brand','')]).lower()
        insulin_supply = bool(re.search(r'insulin\s+(?:pen\s+needles?|syr(?:inge)?s?\b)|\bpen\s+needles?\b|\bins\s+syr\b', text))
        if pa and re.search(r'^(?:dexcom g[67]|freestyle libre [23])\b',text):
            add('GL-503307',[0,1],'product')
        if insulin_supply:
            if pa and record['preferred']=='non_preferred':add('GL-512232',[0],'product')
            if ql:
                add('GL-512232',[1],'quantity')
                assert '6 of each per day' in ' '.join(n['text'] for n in structured['GL-512232']['branches'][1]['notes'])
                record['policyQuantityLimit']={'text':'6 pen needles per day and 6 syringes per day.','sourcePolicyId':policies['GL-512232']['id']}

        if pa and record['preferred']=='non_preferred':add('GL-231255',[0],'nonpreferred')
        if pa and record['preferred']=='preferred' and re.search(r'\b(?:oral (?:solution|suspension)|syrup|elixir|nebuliz\w*)\b',text):add('GL-545275',[0],'nonsolid')
        if ql:add('GL-140667',[0],'global_quantity')
        record['uhcClinicalBindings']=bindings
        if pa and not any(b['role'] in {'product','nonpreferred','nonsolid'} for b in bindings):missing.append(record['id'])
        for role in sorted({b['role'] for b in bindings}):totals[role]+=1
    data['uhcClinicalPolicyInfo']={'policies':len(structured),'branches':sum(len(p['branches']) for p in structured.values()),'linkedRecordsByRole':dict(totals),'paCriteriaUnresolvedIds':missing}
    print('UHC policy access:',len(structured),'policies;',dict(totals),'; unresolved PA:',len(missing))

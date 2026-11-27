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
        # DEC-05/12/13/14/19/20: the 300 mg cluster pack is not the migraine presentation.
        if record['id'] == 'uhc-oct-complete-50113fd01abf63b3':
            code = 'GL-720193'
            assert october_name == 'emgality (300 mg dose)' and record['pa'] == 'required'
            assert record['preferred'] == 'non_preferred' and ql
            assert policies[code]['policyEffective'] == '2026-10-18'
            branches = structured[code]['branches']
            for index, stage in [(2, 'Initial Authorization'), (3, 'Reauthorization')]:
                branch = branches[index]
                assert 'Emgality 100 mg/mL' in branch['fields']['Product Name']['text']
                assert 'Episodic Cluster Headaches' in branch['fields']['Diagnosis']['text']
                assert stage == branch['fields']['Therapy Stage']['text']
            matched.pop(code, None)
            add(code, [2, 3], 'product')
            bindings[-1]['productLabel'] = 'Emgality 100 mg/mL (episodic cluster headache)'
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Emgality (Galcanezumab-gnlm) 100 mg/mL Subcutaneous Prefilled Syringe (300 mg Dose)',
                'dosageForm': 'subcutaneous prefilled syringe',
                'note': 'FDA label: 300 mg as three consecutive 100 mg subcutaneous injections for episodic cluster headache; distinct from 120 mg/mL migraine presentations. UHC cluster policy retains migraine-combination restrictions as printed. Exact payer package eligibility and numeric quantity limit remain unverified.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=33a147be-233a-40e8-a55e-e40936e28db0',
            }
        # DEC-05/06/12/13/14/19/20: exact Roxybond short-acting opioid policy.
        # Keep concurrent therapy, MME and quantity exceptions distinct from routine PA.
        if record['id'] == 'uhc-oct-complete-ccae7c796c8a0833':
            code = 'GL-711768'
            assert october_name == 'roxybond oral tablet abuse-deterrent 15 mg, 30 mg, 5 mg'
            assert record['pa'] == 'required' and record['preferred'] == 'non_preferred' and ql
            assert policies[code]['policyEffective'] == '2026-10-01'
            branches = structured[code]['branches']
            assert len(branches) == 9
            def roxy_field(i, name):
                f = branches[i]['fields'].get(name, {})
                return ' '.join((f.get('displayText') or f.get('text', '')).split())
            assert all(re.search(r'\bRoxybond\b', roxy_field(i, 'Product Name')) for i in range(9))
            assert roxy_field(0, 'Guideline Type') == 'DUR'
            assert 'MAT and other Opioids' in roxy_field(0, 'Diagnosis')
            assert roxy_field(1, 'Diagnosis') == 'Non-Preferred'
            assert roxy_field(1, 'Approval Length') == '12 month(s)'
            assert '> 2 Short Acting Opioids' in roxy_field(2, 'Diagnosis')
            assert all(roxy_field(i, 'Guideline Type') == 'Quantity Limit' for i in (3, 4, 5))
            assert '18 years of age and older' in roxy_field(4, 'Diagnosis')
            assert 'under 18 years of age' in roxy_field(5, 'Diagnosis')
            assert all('90 MME Cumulative Threshold' in roxy_field(i, 'Diagnosis') for i in (6, 7, 8))
            assert roxy_field(7, 'Therapy Stage') == 'Initial Authorization'
            assert roxy_field(8, 'Therapy Stage') == 'Reauthorization'
            matched.pop(code, None)
            add(code, [1, 2], 'product')
            add(code, [3, 4, 5], 'quantity')
            add(code, [0], 'concurrent_opioid_dur')
            add(code, [6, 7, 8], 'mme_exception')
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Roxybond (Oxycodone HCl) Immediate-Release Abuse-Deterrent Oral Tablet (5, 15, 30 mg)',
                'dosageForm': 'immediate-release oral tablet',
                'note': 'FDA label: immediate-release, not extended-release; abuse-deterrent does not mean abuse-proof. Boxed opioid safety warnings apply. The October UHC listing names 5, 15 and 30 mg; the labeled 10 mg presentation is not listed in this row. The policy has separate conditional days-supply and MME exceptions; routine numeric tablet quantity limit remains unverified.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=72398542-8e0a-47b2-afeb-9ca5a1f15083',
            }
        # DEC-05/12/13/14/19/20: Inbrija inhalation capsules are not oral capsules.
        if record['id'] == 'uhc-oct-complete-9979c6aa29c27e3e':
            code = 'GL-140661'
            assert october_name == 'inbrija' and record['pa'] == 'required' and ql
            assert record['preferred'] == 'non_preferred'
            assert policies[code]['policyEffective'] == '2021-03-01'
            branches = structured[code]['branches']
            assert len(branches) == 2
            for index, stage, duration in [(0, 'Initial Authorization', '6 month(s)'), (1, 'Reauthorization', '12 month(s)')]:
                fields = branches[index]['fields']
                def inbrija_field(name):
                    field = fields[name]
                    return ' '.join((field.get('displayText') or field['text']).split())
                assert inbrija_field('Product Name') == 'Inbrija'
                assert inbrija_field('Therapy Stage') == stage
                assert inbrija_field('Approval Length').startswith(duration)
                assert inbrija_field('Guideline Type') == 'Prior Authorization'
            matched.pop(code, None)
            add(code, [0, 1], 'product')
            bindings[-1]['productLabel'] = 'Inbrija (levodopa inhalation powder)'
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Inbrija (Levodopa) Inhalation Powder Capsules',
                'dosageForm': 'inhalation powder capsule',
                'note': 'FDA label: 42 mg levodopa per capsule for oral inhalation only with the Inbrija inhaler; do not swallow. Used for intermittent OFF episodes while continuing carbidopa/levodopa, not as a substitute. Nonselective MAO inhibitors within 2 weeks are contraindicated; not recommended in asthma, COPD or other chronic lung disease. UHC initial and renewal criteria are separately linked; exact payer package and numeric quantity limit remain unverified.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=077c0f39-a3a2-4b2b-a184-09131889dcfb',
            }
        # DEC-05/12/13/14/19/20: Increlex is mecasermin, not growth hormone.
        # Retain the ISS exclusion distinctly from the two positive stages.
        if record['id'] == 'uhc-oct-complete-beefc17346ab027f':
            code = 'GL-723191'
            assert october_name == 'increlex' and record['pa'] == 'required'
            assert record['preferred'] == 'preferred'
            assert policies[code]['policyEffective'] == '2026-10-18'
            branches = structured[code]['branches']
            def increlex_field(index, name):
                field = branches[index]['fields'][name]
                return ' '.join((field.get('displayText') or field['text']).split())
            assert 'Increlex' in increlex_field(0, 'Product Name')
            assert increlex_field(0, 'Diagnosis') == 'Idiopathic Short Stature (ISS)'
            assert increlex_field(0, 'Approval Length').startswith('N/A')
            for index, stage in [(21, 'Initial Authorization'), (22, 'Reauthorization')]:
                assert increlex_field(index, 'Product Name') == 'Increlex'
                assert increlex_field(index, 'Diagnosis') == 'Severe Primary IGF-1 Deficiency/Growth Hormone Gene Deletion'
                assert increlex_field(index, 'Therapy Stage') == stage
                assert increlex_field(index, 'Approval Length').startswith('12 month(s)')
            matched.pop(code, None)
            add(code, [0, 21, 22], 'product')
            bindings[-1]['productLabel'] = 'Increlex (mecasermin)'
            bindings[-1]['branchLabels'] = {'0': 'ISS — explicitly excluded, not an approval pathway', '21': 'Increlex initial', '22': 'Increlex renewal'}
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Increlex (Mecasermin) Subcutaneous Injection',
                'dosageForm': 'subcutaneous injection',
                'note': 'FDA label: 10 mg/mL solution in a 4 mL multidose vial, for children age 2 years and older with severe primary IGF-1 deficiency or GH gene deletion with neutralizing antibodies. Not a substitute for growth hormone. Severe hypoglycemia, including seizures: administer within 20 minutes of a meal or snack; omit dose if food is omitted. Contraindicated with closed epiphyses, pediatric malignancy or history of malignancy, or hypersensitivity. UHC explicitly excludes idiopathic short stature (ISS); separate initial and renewal criteria apply to the named IGF-1/GH gene deletion indication. Exact payer package eligibility is unverified.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=d5b2b0e1-c523-468d-9a0b-4ae4e4a8dbce',
            }
        # DEC-05/12/13/14/19/20: exact Ingrezza listing and four named stages.
        if record['id'] == 'uhc-oct-complete-33105a41b749978a':
            code = 'GL-157491'
            assert october_name == 'ingrezza' and record['pa'] == 'required' and ql
            assert record['preferred'] == 'preferred'
            assert policies[code]['policyEffective'] == '2024-11-01'
            branches = structured[code]['branches']
            assert len(branches) == 4
            def ingrezza_field(index, name):
                field = branches[index]['fields'][name]
                return ' '.join((field.get('displayText') or field['text']).split())
            for index, diagnosis, stage, duration in [
                (0, 'Tardive Dyskinesia', 'Initial Authorization', '6 month'),
                (1, 'Tardive Dyskinesia', 'Reauthorization', '12 month'),
                (2, 'Chorea Associated with Huntington', 'Initial Authorization', '6 month'),
                (3, 'Chorea Associated with Huntington', 'Reauthorization', '12 month'),
            ]:
                assert 'Ingrezza' in ingrezza_field(index, 'Product Name')
                assert diagnosis.lower() in ingrezza_field(index, 'Diagnosis').lower()
                assert ingrezza_field(index, 'Therapy Stage') == stage
                assert ingrezza_field(index, 'Approval Length').lower().startswith(duration)
            matched.pop(code, None)
            add(code, [0, 1, 2, 3], 'product')
            bindings[-1]['productLabel'] = 'Ingrezza (valbenazine; exact formulation not specified)'
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Ingrezza (Valbenazine) Oral Capsules',
                'dosageForm': 'oral capsule',
                'note': 'FDA label: conventional and separate Sprinkle capsules, 40, 60 and 80 mg; only Sprinkle may be opened onto soft food. Exact payer eligibility for Sprinkle or kit is unverified. Boxed warning: depression and suicidality in Huntington disease. UHC names separate initial and renewal stages for moderate-to-severe tardive dyskinesia and Huntington chorea; one active PA for one strength, with 80 mg/day policy ceiling. Exact numeric dispensing quantity limit remains unverified.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=4c970164-cafb-421f-9eb5-c226ef0a3417',
            }
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
        # DEC-05/12/13/14/19/20: distinguish ambiguous Gammagard from named S/D.
        # GL-552230 is AZ Medicaid pharmacy guidance, not a medical benefit determination.
        if record['id'] in {'uhc-oct-complete-c5af301ff34ca5f3', 'uhc-oct-complete-c3048c00894b30ac'}:
            sd = record['id'] == 'uhc-oct-complete-c3048c00894b30ac'
            assert october_name == ('gammagard s/d less iga' if sd else 'gammagard')
            assert record['pa'] == 'required' and record['preferred'] == 'preferred' and not ql
            code = 'GL-552230'
            assert policies[code]['policyEffective'] == '2026-04-12'
            assert set(matched).issubset({code}), ('Review newly matched policy', matched)
            matched.pop(code, None)
            if sd:
                reviewed_dx = ('Primary Immunodeficiency Syndromes',
                               'Prevention of infection in B-cell Chronic Lymphocytic Leukemia (CLL)',
                               'Immune thrombocytopenia [Idiopathic thrombocytopenic purpura (ITP)]',
                               'Asthma (severe, persistent, high-dose steroid-dependent)',
                               'Bone Marrow Transplant (BMT)',
                               'Chronic Inflammatory Demyelinating Polyneuropathy',
                               'Dermatomyositis or polymyositis',
                               'Lambert-Eaton Myasthenic Syndrome (LEMS)',
                               'Lennox Gastaut Syndrome',
                               'Multifocal Motor Neuropathy (MMN)',
                               'Prevention of infection in Multiple Myeloma',
                               'Relapsing Multiple Sclerosis',
                               'Neuromyelitis Optica',
                               'Post B-Cell Targeted Therapies',
                               'Rasmussen Syndrome',
                               'Stiff-Person Syndrome',
                               'Thrombocytopenia, secondary to Hepatitis C Virus (HCV), Human Immunodeficiency Virus (HIV), or pregnancy')
                stages = {dx: {} for dx in reviewed_dx}
                for i, b in enumerate(structured[code]['branches']):
                    fields = b['fields']
                    def field(name):
                        f = fields.get(name, {})
                        return ' '.join((f.get('displayText') or f.get('text', '')).split())
                    dx = field('Diagnosis')
                    if dx not in stages:
                        continue
                    assert 'Gammagard S-D' in field('Product Name').split(', ')
                    # Some initial approval lengths span a PDF running header.
                    assert field('Approval Length').startswith('12 month(s)')
                    assert field('Guideline Type') == 'Prior Authorization'
                    stage = field('Therapy Stage')
                    assert stage not in stages[dx]
                    stages[dx][stage] = i
                assert all(set(v) == {'Initial Authorization', 'Reauthorization'} for v in stages.values()), {dx: sorted(v) for dx, v in stages.items()}
                add(code, [stages[dx][stage] for dx in reviewed_dx
                           for stage in ('Initial Authorization', 'Reauthorization')], 'product')
                bindings[-1]['productLabel'] = 'Gammagard S-D (named UHC pharmacy criteria; IV only)'
                label = 'Gammagard S/D Less IgA (Immune Globulin) Powder for IV Infusion'
                form = 'powder for intravenous infusion'
                note = ('FDA label: 5 g or 10 g lyophilized powder for IV use only; not subcutaneous. '
                        'IgA less than 1 mcg/mL in 5% solution does not eliminate anaphylaxis risk. '
                        'Boxed warning: thrombosis, renal dysfunction and acute renal failure. '
                        'UHC pharmacy initial/renewal criteria verified for PI, CLL infection prevention, ITP and the named off-label indications below; '
                        'the nonpreferred condition applies only to nonpreferred requests. '
                        'S/D FDA indications: PI age 2 years or older, CLL infection prevention, adult chronic ITP, pediatric Kawasaki. '
                        'The payer acute ITP branch is not an FDA-labeled S/D indication. '
                        'Asthma, BMT, CIDP, dermatomyositis/polymyositis, LEMS, Lennox-Gastaut syndrome, MMN, multiple myeloma infection prevention, relapsing MS, neuromyelitis optica, post B-cell targeted therapy, Rasmussen syndrome, stiff-person syndrome and specified secondary thrombocytopenia are off-label for S/D; payer criteria are not FDA-approved indications or prescribing instructions. '
                        'Kawasaki criteria held: printed payer dose wording differs from the product label; verify with payer before use. '
                        'Autoimmune bullous disease criteria held: unclear payer dose division; verify with payer. '
                        'Type 1 diabetes, neonatal thrombocytopenia, mixed Graves/GBS and pediatric HIV pathways held for safety or indication clarification. Immune globulin is not a replacement for insulin. '
                        'Myasthenia gravis and posttransfusion purpura pathways held for dose or safety clarification; all-other indications held for explicit diagnosis scope. '
                        'Other indications and medical benefit applicability remain unverified.')
                label_id = 'bf8df9fd-bfdd-47c2-84d2-d91e50947bf6'
            else:
                label = 'Gammagard (Immune Globulin) Infusion (Formulation Unspecified)'
                form = 'infusion (formulation unspecified)'
                note = ('The UHC listing does not identify Liquid, Liquid ERC or S/D formulation or route. '
                        'Liquid 10% is labeled for IV or subcutaneous administration depending on indication; '
                        'S/D is IV only. GL-552230 names the formulations separately; exact product criteria '
                        'and medical benefit applicability remain unverified. The linked Liquid label is a reference, not a payer product match.')
                label_id = '9d42adca-0dd7-4df7-864d-5a7feee52130'
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': label, 'dosageForm': form, 'note': note,
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=' + label_id,
            }
        # DEC-05/12/13/14/19/20: exact October listing, FDA identity only.
        # GL-231255 and GL-140667 are administrative, not named product criteria.
        # DEC-05/06/12/13/14/19/20: the UHC SC listing is not the IV vial.
        if record['id'] == 'uhc-oct-complete-cb36a822ee8dc7d4':
            assert october_name == 'orencia subcutaneous'
            assert record['pa'] == 'required' and record['preferred'] == 'preferred' and ql
            code = 'GL-141021'
            assert policies[code]['policyEffective'] == '2024-01-01'
            branches = structured[code]['branches']
            assert len(branches) == 6
            for i, dx in enumerate(['Rheumatoid Arthritis (RA)', 'Polyarticular Juvenile Idiopathic Arthritis (PJIA)', 'Psoriatic Arthritis (PsA)']):
                for k, stage in enumerate(['Initial Authorization', 'Reauthorization']):
                    fields = branches[i * 2 + k]['fields']
                    def orencia_field(name):
                        f = fields[name]
                        return ' '.join((f.get('displayText') or f['text']).split())
                    assert orencia_field('Product Name') == 'Orencia Clickject, Orencia prefilled syringe'
                    assert orencia_field('Diagnosis') == dx
                    assert orencia_field('Therapy Stage') == stage
                    assert orencia_field('Approval Length') == '12 month(s)'
                    assert orencia_field('Guideline Type') == 'Prior Authorization'
            assert set(matched).issubset({code, 'GL-733328'}), matched
            matched.pop(code, None)
            add(code, list(range(6)), 'product')
            bindings[-1]['productLabel'] = 'Orencia ClickJect and prefilled syringe (subcutaneous)'
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Orencia (Abatacept) Subcutaneous Injection (Device Unspecified)',
                'dosageForm': 'subcutaneous injection',
                'note': 'FDA label: 50 mg/0.4 mL, 87.5 mg/0.7 mL and 125 mg/mL prefilled syringes; 125 mg/mL ClickJect autoinjector. UHC lists SC without specifying device; the named policy applies to both SC devices, not the IV vial. Use labeled age, weight and device eligibility separately from payer criteria. Numeric quantity limit remains unverified.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=0836c6ac-ee37-5640-2fed-a3185a0b16eb',
            }
        # DEC-05/06/12/13/14/19/20: issuer GL-452192 names Simponi SC, not IV Aria.
        if record['id'] == 'uhc-oct-complete-21d7009b80e338fa':
            assert october_name == 'simponi' and pa and ql and record['preferred'] == 'non_preferred'
            code = 'GL-452192'
            assert policies[code]['policyEffective'] == '2025-12-01'
            branches = structured[code]['branches']
            scopes = [('Rheumatoid Arthritis (RA)', 'Initial Authorization'),
                      ('Ankylosing Spondylitis (AS)', 'Initial Authorization'),
                      ('Rheumatoid Arthritis (RA), Ankylosing Spondylitis (AS)', 'Reauthorization'),
                      ('Psoriatic Arthritis (PsA)', 'Initial Authorization'),
                      ('Psoriatic Arthritis (PsA)', 'Reauthorization'),
                      ('Ulcerative Colitis (UC)', 'Initial Authorization'),
                      ('Ulcerative Colitis (UC)', 'Reauthorization')]
            assert len(branches) == len(scopes)
            for i, (dx, stage) in enumerate(scopes):
                fields = branches[i]['fields']
                def sim_field(name):
                    f = fields[name]
                    return ' '.join((f.get('displayText') or f['text']).split())
                assert sim_field('Product Name') == 'Simponi SC'
                assert sim_field('Diagnosis') == dx
                assert sim_field('Therapy Stage') == stage
                assert sim_field('Approval Length') == '12 month(s)'
                assert sim_field('Guideline Type') == 'Prior Authorization'
            assert set(matched).issubset({code, 'GL-733328'}), matched
            matched.pop(code, None)
            add(code, list(range(7)), 'product')
            bindings[-1]['productLabel'] = 'Simponi SC (device unspecified)'
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Simponi (Golimumab) Subcutaneous Injection (Device Unspecified)',
                'dosageForm': 'subcutaneous injection',
                'note': 'FDA label: subcutaneous prefilled syringe or autoinjector, distinct from intravenous Simponi Aria. UHC lists SC without identifying device or strength. Boxed warnings for serious infections and malignancy. Named UC initial criteria require weight at least 15 kg. Device-specific eligibility and numeric quantity limit remain unverified.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=f86cb4a7-c358-4136-ae57-b32bda9bba00',
            }
        # DEC-05/06/12/13/14/19/20: November issuer GL-684216, effective 2026-09-01.
        # Label October 23 adds SC induction for CD; payer initial IBD branches still require IV induction.
        skyrizi_rows = {
            'uhc-oct-complete-51060c1e6747eba6': ('skyrizi pen', 'Skyrizi (Risankizumab-rzaa) Subcutaneous Prefilled Pen', 'subcutaneous prefilled pen', [0, 1, 2, 3],
                '150 mg/1 mL pen. The policy PsO/PsA branches apply to the 150 mg dose; the separately named 55 mg pediatric dose is not this pen. Follow FDA weight-based eligibility. IBD maintenance and induction are not this presentation.'),
            'uhc-oct-complete-9fdaab30a29cac66': ('skyrizi subcutaneous solution cartridge', 'Skyrizi (Risankizumab-rzaa) Subcutaneous Cartridge for On-Body Injector', 'subcutaneous cartridge for on-body injector', [4, 5, 6],
                '180 mg/1.2 mL or 360 mg/2.4 mL cartridge; same concentration, different total dose. Named IBD initial branches require prior IV induction. October 2026 FDA label permits 720 mg SC Crohn induction using two 360 mg cartridges; this is not addressed by the September payer policy. Exact SC induction and kit eligibility remain unverified.'),
            'uhc-oct-complete-f6100e969a589a1d': ('skyrizi subcutaneous solution prefilled syringe 150 mg/ml', 'Skyrizi (Risankizumab-rzaa) 150 mg/mL Subcutaneous Prefilled Syringe', 'subcutaneous prefilled syringe', list(range(7)),
                'The printed concentration matches 150 mg/1 mL or 180 mg/1.2 mL syringes, not the same total dose. PsO/PsA criteria below apply to 150 mg; IBD maintenance criteria to 180 mg only, after IV induction for initial approval. Do not extend to the 55 mg syringe, 360 mg cartridge, pen or IV vial. SC induction eligibility remains unverified.'),
        }
        if record['id'] in skyrizi_rows:
            expected, label, form, indexes, note = skyrizi_rows[record['id']]
            code = 'GL-684216'
            assert october_name == expected and pa and ql and record['preferred'] == 'non_preferred'
            assert policies[code]['policyEffective'] == '2026-09-01'
            branches = structured[code]['branches']
            assert len(branches) == 7
            scopes = [('Plaque Psoriasis (PsO)', 'Initial Authorization'), ('Plaque Psoriasis (PsO)', 'Reauthorization'),
                      ('Psoriatic Arthritis (PsA)', 'Initial Authorization'), ('Psoriatic Arthritis (PsA)', 'Reauthorization'),
                      ("Crohn's Disease (CD)", 'Initial Authorization'), ('Ulcerative Colitis (UC)', 'Initial Authorization'),
                      ("Crohn's Disease (CD), Ulcerative Colitis (UC)", 'Reauthorization')]
            for i, (dx, stage) in enumerate(scopes):
                fields = branches[i]['fields']
                def sky_field(name):
                    f = fields[name]
                    return ' '.join((f.get('displayText') or f['text']).split())
                assert sky_field('Product Name') == ('Skyrizi SC 55 mg*, Skyrizi SC 150 mg*' if i < 4 else 'Skyrizi SC 180 mg*, Skyrizi SC 360 mg*')
                assert sky_field('Diagnosis').replace('’', "'") == dx
                assert sky_field('Therapy Stage') == stage
                assert sky_field('Approval Length') == '12 month(s)'
                assert sky_field('Guideline Type') == 'Prior Authorization'
            assert set(matched).issubset({code, 'GL-733328'}), matched
            matched.pop(code, None)
            add(code, indexes, 'product')
            bindings[-1]['productLabel'] = label
            bindings[-1]['branchLabels'] = {str(i): ('Skyrizi SC 150 mg' if i < 4 else
                ('Skyrizi SC 180 mg (prefilled syringe)' if len(indexes) == 7 else 'Skyrizi SC 180 or 360 mg (on-body injector)')) for i in indexes}
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': label, 'dosageForm': form,
                'note': 'FDA label: ' + note + ' Routine numeric quantity limit remains unverified.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=7148c8eb-b39e-e20a-6494-a6df82392858',
            }
        # DEC-05/06/12/13/14/19/20: exact 12 mg/5 mL listing; June policy names Spinraza.
        if record['id'] == 'uhc-oct-complete-31f36e8df6c98ba4':
            assert october_name == 'spinraza intrathecal solution 12 mg/5ml' and pa and ql and record['preferred'] == 'non_preferred'
            code = 'GL-618190'
            assert policies[code]['policyEffective'] == '2026-06-01'
            branches = structured[code]['branches']
            assert len(branches) == 2
            for i, (stage, length) in enumerate([('Initial Authorization', '3 month(s)'), ('Reauthorization', '12 month(s)')]):
                fields = branches[i]['fields']
                def spin_field(name):
                    f = fields[name]
                    return ' '.join((f.get('displayText') or f['text']).split())
                assert spin_field('Product Name') == 'Spinraza'
                assert spin_field('Therapy Stage') == stage
                assert spin_field('Approval Length') == length
                assert spin_field('Guideline Type') == 'Prior Authorization'
            assert set(matched).issubset({code}), matched
            matched.pop(code, None)
            add(code, [0, 1], 'product')
            bindings[-1]['productLabel'] = 'Spinraza 12 mg/5 mL intrathecal solution'
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Spinraza (Nusinersen) 12 mg/5 mL Intrathecal Solution',
                'dosageForm': 'intrathecal solution',
                'note': 'FDA label: 12 mg/5 mL single-dose intrathecal vial for the low-dose regimen. Distinct from the 28 mg/5 mL and 50 mg/5 mL high-dose presentations. The June payer guideline updated dosing to FDA labeling but the October listing prints only 12 mg/5 mL; high-dose presentation benefit and numeric quantity limit remain unverified. Monitor platelets, coagulation and urine protein as labeled.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=dd70cd5f-b0fc-4ba4-a5ea-89a34778bd94',
            }
        # DEC-05/06/12/13/14/19/20: November issuer GL-713343 names auto-inj only.
        if record['id'] == 'uhc-oct-complete-be7159d568ed9f80':
            assert october_name == 'tezspire subcutaneous solution auto-injector' and pa and ql and record['preferred'] == 'non_preferred'
            code = 'GL-713343'
            assert policies[code]['policyEffective'] == '2026-10-01'
            branches = structured[code]['branches']
            assert len(branches) == 4
            scopes = [('Asthma', 'Initial Authorization', '6 month(s)'),
                      ('Asthma', 'Reauthorization', '12 month(s)'),
                      ('Chronic rhinosinusitis with nasal polyps (CRSwNP)', 'Initial Authorization', '6 month(s)'),
                      ('Chronic rhinosinusitis with nasal polyps (CRSwNP)', 'Reauthorization', '12 month(s)')]
            for i, (dx, stage, length) in enumerate(scopes):
                fields = branches[i]['fields']
                def tez_field(name):
                    f = fields[name]
                    return ' '.join((f.get('displayText') or f['text']).split())
                assert tez_field('Product Name') == 'Tezspire auto-inj'
                assert tez_field('Diagnosis') == dx
                assert tez_field('Therapy Stage') == stage
                assert tez_field('Approval Length') == length
                assert tez_field('Guideline Type') == 'Prior Authorization'
                criteria = ' '.join(c.get('displayText') or c['text'] for c in branches[i]['criteria'])
                assert 'Dupixent' in criteria and 'Xolair' in criteria
                if i < 2:
                    assert 'Fasenra' in criteria
            assert set(matched).issubset({code, 'GL-733328'}), matched
            matched.pop(code, None)
            add(code, [0, 1, 2, 3], 'product')
            bindings[-1]['productLabel'] = 'Tezspire autoinjector (prefilled pen)'
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Tezspire (Tezepelumab-ekko) Subcutaneous Prefilled Pen',
                'dosageForm': 'subcutaneous prefilled pen',
                'note': 'FDA label: 210 mg/1.91 mL single-dose pen; patient or caregiver administration is possible after appropriate training and clinician assessment. Distinct from the healthcare-provider-administered prefilled syringe and vial. October payer criteria name the autoinjector only; numeric quantity limit remains unverified.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=60f0aa03-ad25-4d48-80ce-7fcfa76f325f',
            }
        # DEC-05/06/12/13/14/19/20: Tyvaso kit identity; no extension of general product criteria.
        tyvaso_kits = {
            'uhc-oct-complete-e6ced40cd1e57c05': ("tyvaso dpi maintenance kit inhalation powder 16 mcg, 32 mcg, 48 mcg, 64 mcg", "Tyvaso DPI (Treprostinil) Inhalation Powder Maintenance Kit", "inhalation powder kit", "FDA label: maintenance kits use single-use cartridges with the dedicated DPI inhaler, distinct from titration kits and nebulized solution. UHC lists 16, 32, 48 and 64 mcg; the labeled 80 mcg cartridge is not established by this listing. GL-715293 names the product for PAH, not the exact kit or PH-ILD. Exact kit criteria and numeric quantity limit remain unverified.", "ddc3d400-bcb3-4b09-aae2-0768b10a5b0f", True),
            'uhc-oct-complete-36bba0f4b45c9df3': ("tyvaso dpi titration kit", "Tyvaso DPI (Treprostinil) Inhalation Powder Titration Kit", "inhalation powder kit", "FDA label: distinct 16/32 mcg and 16/32/48 mcg titration packs with dedicated DPI inhalers. The linked GL-715293 PAH stages name Tyvaso DPI generally, not a specific titration kit or PH-ILD. Exact kit criteria and numeric quantity limit remain unverified.", "ddc3d400-bcb3-4b09-aae2-0768b10a5b0f", True),
            'uhc-oct-complete-8dc08b2e585b8095': ("tyvaso refill kit", "Tyvaso (Treprostinil) Inhalation Solution Refill Kit", "inhalation solution kit", "FDA label: 28 ampules of 1.74 mg/2.9 mL (0.6 mg/mL) with accessories, distinct from the starter kit containing the inhalation system and from DPI cartridges. UHC prints Coverable through Medical Benefit; exact kit authorization and benefit routing remain unverified. GL-715293 names Tyvaso for PAH, not this kit or PH-ILD; QL not specified.", "cbc31ab1-a80f-4b50-a3b1-39910b0fb609", False),
            'uhc-oct-complete-4df51b8e7e6b64bc': ("tyvaso starter kit", "Tyvaso (Treprostinil) Inhalation Solution Starter Kit", "inhalation solution kit", "FDA label: patient starter kit includes 28 ampules of 1.74 mg/2.9 mL (0.6 mg/mL) and inhalation system; separate institutional kit contains four ampules. UHC does not establish which exact package. Distinct from refill kit and DPI. UHC prints Coverable through Medical Benefit; exact kit authorization and benefit routing remain unverified. GL-715293 names Tyvaso for PAH, not this kit or PH-ILD; QL not specified.", "cbc31ab1-a80f-4b50-a3b1-39910b0fb609", False),
        }
        if record['id'] in tyvaso_kits:
            expected, label, form, note, label_id, has_ql = tyvaso_kits[record['id']]
            assert october_name == expected and record['pa'] == 'required'
            assert record['preferred'] == 'non_preferred' and bool(ql) == has_ql
            assert set(matched).issubset({'GL-715293'}), ('Review new Tyvaso policy', matched)
            if record['id'] != 'uhc-oct-complete-36bba0f4b45c9df3':
                assert not matched, ('Review newly matched kit policy', record['id'], matched)
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': label, 'dosageForm': form, 'note': note,
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=' + label_id,
            }
        # DEC-05/06/12/13/14/19/20: exact Stelara SC; Yesintek strength-specific scope.
        if record['id'] in {'uhc-oct-complete-001e5ba120fa0c78', 'uhc-oct-complete-4bef2dde256711a9'}:
            stelara = record['id'] == 'uhc-oct-complete-001e5ba120fa0c78'
            assert october_name == ('stelara subcutaneous (brand for ustekinumab)' if stelara else 'yesintek subcutaneous solution prefilled syringe 45 mg/0.5ml')
            assert record['pa'] == 'required' and record['preferred'] == 'non_preferred' and ql
            code = 'GL-745190'
            assert policies[code]['policyEffective'] == '2026-11-01'
            branches = structured[code]['branches']
            scopes = [('Plaque Psoriasis (PsO)', 'Initial Authorization'),
                      ('Plaque Psoriasis (PsO)', 'Reauthorization'),
                      ('Psoriatic Arthritis (PsA)', 'Initial Authorization'),
                      ('Psoriatic Arthritis (PsA)', 'Reauthorization'),
                      ("Crohn's Disease (CD)", 'Initial Authorization'),
                      ('Ulcerative Colitis (UC)', 'Initial Authorization'),
                      ("Crohn's Disease (CD), Ulcerative Colitis (UC)", 'Reauthorization')]
            assert len(branches) == len(scopes)
            for i, (dx, stage) in enumerate(scopes):
                fields = branches[i]['fields']
                def ust_field(name):
                    f = fields[name]
                    return ' '.join((f.get('displayText') or f['text']).split())
                assert ('Stelara SC' if stelara else 'Yesintek SC') in ust_field('Product Name').split(', ')
                assert ust_field('Diagnosis').replace('’', "'") == dx
                assert ust_field('Therapy Stage') == stage
                assert ust_field('Guideline Type') == 'Prior Authorization'
            assert set(matched).issubset({code, 'GL-733328'}), matched
            matched.pop(code, None)
            add(code, list(range(7 if stelara else 4)), 'product')
            bindings[-1]['productLabel'] = 'Stelara SC (device and strength unspecified)' if stelara else 'Yesintek SC 45 mg/0.5 mL syringe (PsO/PsA only)'
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Stelara (Ustekinumab) Subcutaneous Injection (Device and Strength Unspecified)' if stelara else 'Yesintek (Ustekinumab-kfce) 45 mg/0.5 mL Subcutaneous Prefilled Syringe',
                'dosageForm': 'subcutaneous injection' if stelara else 'subcutaneous prefilled syringe',
                'note': ('FDA label updated September 8, 2026: PsO/PsA age 6 and older; CD/UC age 2 and older. SC syringe 45 mg/0.5 mL or 90 mg/mL and 45 mg/0.5 mL vial are distinct from IV induction. UHC November SC policy names Stelara; exact device, strength, age-limit flag details and numeric quantity limit remain unverified.' if stelara else 'FDA label updated March 17, 2026: PsO/PsA age 6 and older, CD/UC adults only. The UHC product-level policy includes CD/UC from age 2 but the labeled adult IBD SC maintenance dose is 90 mg; this 45 mg syringe is not the 90 mg presentation. Only PsO/PsA stages are linked here, for a labeled 45 mg regimen; pediatric weight-based doses below 45 mg require the vial. IBD applicability, age-limit flag details and numeric quantity limit remain unverified.'),
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=' + ('c77a9664-e3bb-4023-b400-127aa53bca2b' if stelara else '12a75613-ee33-d30a-215b-2a51cfa19b00'),
            }
        # DEC-05/06/12/13/14/19/20: GL-500226 exact SC product, strength-scoped branches.
        if record['id'] == 'uhc-oct-complete-8ae98137dd88048f':
            assert october_name == 'tremfya subcutaneous' and pa and ql and record['preferred'] == 'non_preferred'
            code = 'GL-500226'
            assert policies[code]['policyEffective'] == '2026-02-01'
            branches = structured[code]['branches']
            scopes = [('Plaque Psoriasis (PsO)', 'Initial Authorization'),
                      ('Plaque Psoriasis (PsO)', 'Reauthorization'),
                      ('Psoriatic Arthritis (PsA)', 'Initial Authorization'),
                      ('Psoriatic Arthritis (PsA)', 'Reauthorization'),
                      ("Crohn's Disease (CD)", 'Initial Authorization'),
                      ('Ulcerative Colitis (UC)', 'Initial Authorization'),
                      ("Crohn's Disease (CD), Ulcerative Colitis (UC)", 'Reauthorization')]
            assert len(branches) == len(scopes)
            for i, (dx, stage) in enumerate(scopes):
                fields = branches[i]['fields']
                def trem_field(name):
                    f = fields[name]
                    return ' '.join((f.get('displayText') or f['text']).split())
                assert trem_field('Product Name') == ('Tremfya SC 100 mg*' if i < 4 else 'Tremfya SC')
                assert trem_field('Diagnosis').replace('’', "'") == dx
                assert trem_field('Therapy Stage') == stage
                assert trem_field('Approval Length') == '12 month(s)'
                assert trem_field('Guideline Type') == 'Prior Authorization'
                if i in (4, 5):
                    criteria = ' '.join(c.get('displayText') or c['text'] for c in branches[i]['criteria'])
                    assert 'maintenance dose following the intravenous induction doses' in criteria
                    assert 'induction dosing' in criteria
            assert set(matched).issubset({code, 'GL-733328'}), matched
            matched.pop(code, None)
            add(code, list(range(7)), 'product')
            bindings[-1]['productLabel'] = 'Tremfya SC (device and strength unspecified)'
            bindings[-1]['branchLabels'] = {str(i): ('Tremfya SC 100 mg' if i < 4 else 'Tremfya SC (IBD)') for i in range(7)}
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Tremfya (Guselkumab) Subcutaneous Injection (Device and Strength Unspecified)',
                'dosageForm': 'subcutaneous injection',
                'note': 'FDA label: 100 mg/mL syringe, pen or One-Press injector; 200 mg/2 mL syringe or pen. Distinct from 200 mg/20 mL IV vial. PsO/PsA payer branches apply to SC 100 mg only; CD/UC branches name SC and distinguish induction from maintenance after IV induction. Labeled IBD SC induction is 400 mg as two 200 mg injections. UHC listing does not specify device or strength; exact device and strength benefit and numeric quantity limit remain unverified.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=1e6dc9ae-1c4c-42d9-87aa-c315ecc51b56',
            }
        # GL-572198 branch 13 names ONLY topiramate 50 mg sprinkle.
        # Ingredient-only matching can leak this branch to IR tablets or other sprinkle strengths.
        if record['id'] in {'uhc-oct-complete-8e34212b5a29106f', 'uhc-oct-complete-d37573826a734ebb', 'uhc-oct-complete-90702ce4eec9617a'}:
            code = 'GL-572198'
            if code in matched:
                assert policies[code]['policyEffective'] == '2026-05-01'
                assert matched[code] == {13}, (record['id'], matched)
                product = structured[code]['branches'][13]['fields']['Product Name']
                assert ' '.join((product.get('displayText') or product['text']).split()) == 'topiramate 50 mg sprinkle'
                matched.pop(code)
        # DEC-05/06/07/12/13/14/19/20: distinguish conditional brand sprinkle from IR tablet.
        if record['id'] == 'uhc-oct-complete-d37573826a734ebb':
            assert october_name == 'topamax sprinkle (brand for topiramate)'
            assert record['pa'] == 'conditional' and record['preferred'] == 'non_preferred' and ql
            assert not matched, ('Review newly available named criteria before use', record['id'], matched)
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Topamax Sprinkle (Topiramate) Oral Sprinkle Capsule',
                'dosageForm': 'oral sprinkle capsule',
                'note': 'FDA label: 15 and 25 mg immediate-release sprinkle capsules, distinct from 50 mg sprinkle, ER sprinkle and tablets. Capsules may be opened onto soft food and swallowed without chewing. UHC conditional PA applies at age 8 or older, not a labeled indication age. GL-572198 names ER products and 50 mg sprinkle, not this option. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=21628112-0c47-11df-95b3-498d55d89593',
            }
        # DEC-05/06/12/13/14/19/20: exact printed weight-band kit IDs only.
        # FDA label June 16 2026 Table 3 and linked BPCK concepts; no kit-specific claim eligibility or numeric QL inferred.
        zolgensma_kits = {
            'uhc-oct-complete-122631375b25a969': ('10.1-10.5', 0, 7, 2170261),
            'uhc-oct-complete-0213c9a06e7ceeeb': ('10.6-11.0', 2, 6, 2170263),
            'uhc-oct-complete-ff19f0cc1479f5d4': ('11.1-11.5', 1, 7, 2170265),
            'uhc-oct-complete-23163e3715d68ae7': ('11.6-12.0', 0, 8, 2170267),
            'uhc-oct-complete-6e07ada48071efc9': ('12.1-12.5', 2, 7, 2170274),
            'uhc-oct-complete-156d9eb0e3a4501e': ('12.6-13.0', 1, 8, 2170297),
            'uhc-oct-complete-bec695bbe3fb9d86': ('13.1-13.5', 0, 9, 2170257),
            'uhc-oct-complete-4042ef9a85590d2d': ('2.6-3.0', 0, 2, 2170255),
            'uhc-oct-complete-54785c1031f7131a': ('3.1-3.5', 2, 1, 2170247),
            'uhc-oct-complete-52292de6d5e4f7be': ('3.6-4.0', 1, 2, 2170249),
            'uhc-oct-complete-cf41b06d6fd22ae5': ('4.1-4.5', 0, 3, 2170251),
            'uhc-oct-complete-fd57381446d25d5c': ('4.6-5.0', 2, 2, 2170253),
            'uhc-oct-complete-195c447d02e43c25': ('5.1-5.5', 1, 3, 2170289),
            'uhc-oct-complete-295e76d74fbeb575': ('5.6-6.0', 0, 4, 2170291),
            'uhc-oct-complete-9a60913597362b45': ('6.1-6.5', 2, 3, 2170293),
            'uhc-oct-complete-4a226682a344144b': ('6.6-7.0', 1, 4, 2170295),
            'uhc-oct-complete-c94a751831dd15a2': ('7.1-7.5', 0, 5, 2170272),
            'uhc-oct-complete-5954d294b103e821': ('7.6-8.0', 2, 4, 2170276),
            'uhc-oct-complete-4396fa24871642c0': ('8.1-8.5', 1, 5, 2170279),
            'uhc-oct-complete-6fe8632c59acf63d': ('8.6-9.0', 0, 6, 2170282),
            'uhc-oct-complete-0b4dfcf8c2bf84a2': ('9.1-9.5', 2, 5, 2170284),
            'uhc-oct-complete-18cd666810c8003b': ('9.6-10.0', 1, 6, 2170259),
        }
        if record['id'] in zolgensma_kits:
            band, v55, v83, bpck = zolgensma_kits[record['id']]
            assert october_name == 'zolgensma ' + band + ' kg', (record['id'], october_name)
            assert record['pa'] == 'required' and record['preferred'] == 'non_preferred' and ql
            code = 'GL-523191'
            assert policies[code]['policyEffective'] == '2026-03-01'
            branches = structured[code]['branches']
            assert len(branches) == 2
            assert branches[0]['fields']['Product Name']['text'] == 'Zolgensma'
            assert branches[1]['fields']['Product Name']['text'] == 'Itvisma'
            assert branches[0]['fields']['Approval Length']['text'] == '1 Time Authorization in Lifetime'
            assert not matched.get(code, set()) - {0}, (record['id'], matched)
            matched.pop(code, None)
            add(code, [0], 'product')
            bindings[-1]['productLabel'] = 'Zolgensma IV (general product criteria; kit applicability unverified)'
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Zolgensma (Onasemnogene Abeparvovec-xioi) IV Infusion Kit ' + band + ' kg',
                'dosageForm': 'suspension for intravenous infusion',
                'note': f'FDA label: {band} kg patient-weight kit; {v55} x 5.5 mL and {v83} x 8.3 mL vials, each nominally 2.0 x 10^13 vg/mL. Single IV infusion only; not intrathecal Itvisma. Boxed liver injury/failure warning. Kit contents are not dose volume or payer quantity limit. UHC GL-523191 names Zolgensma once per lifetime; exact kit applicability and numeric QL remain unverified.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=68cd4f06-70e1-40d8-bedb-609ec0afa471',
            }
        # DEC-05/06/12/13/14/19/20: exact oncology listing identities; preserve existing payer bindings.
        oncology_label_holds = {
            'uhc-oct-complete-6fdc3ea2abaea52b': (
                'zejula', 'Zejula (Niraparib) Film-Coated Oral Tablet', 'oral tablet',
                'FDA label: 100, 200 and 300 mg tablets. UHC GL-741203 is a named oncology class policy with no separate initial/renewal stages printed for this branch; exact strength/package applicability and numeric quantity limit remain unverified.',
                'b7f675e2-159c-490c-b6f4-3f16d9492b7d', 'GL-741203', {1}),
            'uhc-oct-complete-47dbf4be655ad1a4': (
                'zykadia', 'Zykadia (Ceritinib) Oral Tablet or Capsule (Payer Form Unspecified)', 'oral tablet or capsule',
                'FDA label lists 150 mg tablets and capsules; current SPL product data lists tablets only. The UHC name does not distinguish the forms. Capsule availability and exact payer form applicability are unverified. GL-741203 does not separately identify initial/renewal stages for this branch; numeric quantity limit unverified.',
                'fff5d805-4ffd-4e8e-8e63-6f129697563e', 'GL-741203', {1}),
            'uhc-oct-complete-aa3337eda974b8e5': (
                'yulithira (generic for torpenz)', 'Yulithira (Everolimus; payer reference Torpenz) Oral Tablet', 'oral tablet',
                'FDA label: 2.5, 5, 7.5 and 10 mg conventional tablets, not tablets for oral suspension or transplant-dose everolimus. Do not combine conventional and suspension tablets. Yulithira and Torpenz have separate ANDAs. The payer reference does not establish interchangeability. GL-657254 includes seizure and other broader indications; these are not all labeled for this tablet. Exact product/indication applicability and numeric quantity limit remain unverified.',
                '5e325efa-8ae6-4dac-b59b-d7c74c73186c', 'GL-657254', set(range(15))),
        }
        if record['id'] in oncology_label_holds:
            name, label, form, note, setid, code, indexes = oncology_label_holds[record['id']]
            assert october_name == name, (record['id'], october_name)
            assert record['pa'] == 'required' and record['preferred'] == 'preferred' and ql
            assert matched.get(code) == indexes, (record['id'], matched)
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': label, 'dosageForm': form, 'note': note,
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=' + setid,
            }
        # DEC-05/06/12/13/14/19/20: exact options and source-stage caveats;
        # original flags and product branches remain, with scope explicitly qualified.
        stage_scope_review = {
            'uhc-oct-complete-4bbadb8d1f122e2f': (
                'posaconazole oral tablet delayed release', 'Posaconazole 100 mg Delayed-Release Oral Tablet', 'delayed-release oral tablet',
                'FDA labels identify 100 mg delayed-release tablets, not interchangeable with ordinary oral suspension or PowderMix. Generic FDA labels vary by manufacturer in age and indication; verify the dispensed product label. UHC GL-751212 names generic tablets for prophylaxis (age 2 or older, weight at least 40 kg), invasive aspergillosis treatment (age 2 or older, greater than 40 kg), and other diagnoses. Tablet labeling uses greater than 40 kg for pediatric use, a discrepancy at exactly 40 kg for payer prophylaxis. Other diagnoses require literature support and infectious disease specialist involvement, or inpatient continuation at discharge; provider duration up to 12 months. No initial or renewal stage is specified. Exact manufacturer eligibility and numeric dispensing QL unverified.',
                'd8d8dd03-46b5-bd26-bb27-7ca31d8c3326', 'GL-751212', {8,10,14}, 'preferred', 'Generic delayed-release tablets; verify product-specific FDA labeling'),
            'uhc-oct-complete-50027926c12f2fc5': (
                'accutane (generic for accutane)', 'Isotretinoin Oral Capsule (payer reference Accutane)', 'oral capsule',
                'FDA label: conventional isotretinoin capsules; not milligram-for-milligram substitutable with Absorica LD. Pregnancy contraindication and iPLEDGE REMS apply. UHC GL-288262 includes separate acne initial, post-treatment recurrence and dose-titration stages, plus an off-label oncology branch without a specified stage. Numeric quantity limit remains unverified.',
                '4e8516dc-a3c6-4d8f-aa14-2c37c6c8f6e6', 'GL-288262', {0,1,2,3}, 'preferred', 'Conventional isotretinoin capsule; verify formulation-specific applicability'),
            'uhc-oct-complete-ebfa91d6e2f468c4': (
                'cresemba oral capsule 186 mg', 'Cresemba (Isavuconazonium Sulfate) 186 mg Oral Capsule', 'oral capsule',
                'FDA label: 186 mg isavuconazonium sulfate equals 100 mg isavuconazole. Distinct from 74.5 mg capsules and IV formulation. Labeled oral pediatric use starts at age 6 years and 16 kg; pediatric capsule dosing is weight-specific. UHC GL-751212 gives a broader brand-level minimum age of 6 months; this is not FDA capsule eligibility. Exact 186 mg capsule applicability and numeric quantity limit remain unverified; stages not separately specified.',
                '8f7f73b8-586a-4df0-935f-fecd4696c16c', 'GL-751212', {12,14}, 'non_preferred', 'Cresemba general product criteria (186 mg capsule applicability unverified)'),
            'uhc-oct-complete-9cb53245e3257820': (
                'droxidopa oral capsule 100 mg (generic for northera)', 'Droxidopa 100 mg Oral Capsule (payer reference Northera)', 'oral capsule',
                'FDA label: 100 mg oral capsule; boxed warning for supine hypertension. UHC GL-140900 explicitly names Northera only; the generic listing is PA flagged, but exact generic applicability of the named initial and renewal criteria is unverified. Numeric quantity limit remains unverified.',
                '81b798dc-b8dc-48a5-af46-82bb55f789a8', 'GL-140900', {0,1}, 'non_preferred', 'Northera brand reference only (generic applicability unverified)'),
            'uhc-oct-complete-598734c054ff21fe': (
                'eltrombopag olamine oral tablet (generic for promacta)', 'Eltrombopag Olamine Oral Tablet (payer reference Promacta)', 'oral tablet',
                'FDA label: 12.5, 25, 50 and 75 mg tablets, distinct from powder for oral suspension. Alvaiz (eltrombopag choline) is not milligram-for-milligram substitutable. UHC GL-546252 expressly includes generic eltrombopag tablets in six ITP, severe aplastic anemia and HCV-associated thrombocytopenia initial/renewal branches; nonpreferred-only prerequisite does not apply universally. Numeric quantity limit remains unverified.',
                '5a9ec8c8-3c0b-4f11-848c-c04ccee0d44f', 'GL-546252', {0,1,2,3,4,5}, 'preferred', 'Generic eltrombopag tablets'),
            'uhc-oct-complete-4bab14d7a32ab94a': (
                'plerixafor (generic for mozobil)', 'Plerixafor (Generic Mozobil) Subcutaneous Injection', 'subcutaneous injection',
                'FDA label: 24 mg/1.2 mL (20 mg/mL) single-dose vial for stem-cell mobilization with filgrastim in NHL or multiple myeloma before autologous transplantation. Renal dose reduction is required for creatinine clearance 50 mL/min or less; avoid use in leukemia. UHC GL-140850 explicitly names Mozobil only and requires NHL/MM autologous transplantation, G-CSF and hematology/oncology prescriber or consultation; one course up to four days, stage unspecified. Generic applicability unverified; four-day authorization is not a numeric dispensing QL. Exact payer package eligibility and numeric dispensing QL unverified.',
                '5d670cb4-163e-498c-b5fa-c193ea9d55c0', 'GL-140850', {0}, 'preferred', 'Mozobil brand reference only (generic applicability unverified)'),
        }
        if record['id'] in stage_scope_review:
            name, label, form, note, setid, code, indexes, pref, product_label = stage_scope_review[record['id']]
            assert october_name == name, (record['id'], october_name)
            assert record['pa'] == 'required' and record['preferred'] == pref and ql
            assert matched.get(code) == indexes, (record['id'], matched)
            matched.pop(code)
            add(code, sorted(indexes), 'product')
            bindings[-1]['productLabel'] = product_label
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': label, 'dosageForm': form, 'note': note,
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=' + setid,
            }
        # DEC-05/06/12/13/14/19/20: retain both payer potency rows; factor IX complex is not single-factor IX.
        profilnine_presentations = {
            'uhc-oct-complete-cd6eda95e2025320': ('profilnine intravenous solution reconstituted 1000 unit, 1500 unit', '1000 or 1500 IU', '1000 IU/10 mL or 1500 IU/10 mL'),
            'uhc-oct-complete-11a2edc770cc3549': ('profilnine intravenous solution reconstituted 500 unit', '500 IU', '500 IU/5 mL'),
        }
        if record['id'] in profilnine_presentations:
            name, strength, concentration = profilnine_presentations[record['id']]
            assert october_name == name, (record['id'], october_name)
            assert record['pa'] == 'required' and record['preferred'] == 'preferred' and not ql
            code = 'GL-716187'
            assert matched.get(code) == {18}, (record['id'], matched)
            matched.pop(code)
            add(code, [18], 'product')
            bindings[-1]['productLabel'] = 'Profilnine named policy (authorization stage unspecified)'
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Profilnine (Factor IX Complex) ' + strength + ' Powder for Intravenous Injection',
                'dosageForm': 'powder for intravenous injection',
                'note': 'FDA label (April 2026): nominal ' + concentration + ' after reconstitution; actual factor IX potency is labeled per vial. Plasma-derived complex containing factors II, IX, X and low VII; distinct from single-factor IX products and not indicated for factor VII deficiency. UHC GL-716187 branch 18 specifies hemophilia B with routine prophylaxis or treatment of bleeding episodes, 12 months; authorization stage unspecified. Exact package eligibility unverified; no numeric dispensing limit established by this branch.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=79821042-86a5-4a64-b621-76de0a0bbab2',
            }
        # DEC-05/06/12/13/14/19/20: distinguish route/form and preserve stage ambiguity.
        stage_scope_review_2 = {
            'uhc-oct-complete-a27cea08627d0ce7': (
                'epclusa oral packet', 'Epclusa (Sofosbuvir / Velpatasvir) Oral Pellets Packet', 'oral pellets',
                'FDA label: 150/37.5 mg and 200/50 mg oral pellet packets; distinct from tablets. Pediatric dosing is weight-based; for age under 6 years administer pellets with food. UHC GL-392223 brand-level criteria are retreatment-oriented and include a generic failure, contraindication or intolerance and MedWatch requirement. Exact packet-strength coverage, generic comparator availability, initial-treatment criteria and numeric quantity limit are unverified.',
                '7f30631a-ee3b-4cfe-866b-964df3f0a44f', 'GL-392223', {1}, True, 'Epclusa brand reference (packet applicability and initial stage unverified)'),
            'uhc-oct-complete-da63c83c6a7d29e4': (
                'epclusa oral tablet 200-50 mg', 'Epclusa (Sofosbuvir / Velpatasvir) 200/50 mg Oral Tablet', 'oral tablet',
                'FDA label: 200/50 mg tablet is distinct from oral pellets and 400/100 mg tablets. Pediatric dosing is weight-based. UHC GL-392223 brand-level criteria are retreatment-oriented; generic failure, contraindication or intolerance and MedWatch are required for brand requests. Exact tablet-strength applicability, generic comparator availability, initial-treatment criteria and numeric quantity limit remain unverified.',
                '7f30631a-ee3b-4cfe-866b-964df3f0a44f', 'GL-392223', {1}, True, 'Epclusa brand reference (200/50 mg applicability and initial stage unverified)'),
            'uhc-oct-complete-f7b511540f1cf564': (
                'esperoct intravenous solution reconstituted 1000 unit, 1500 unit, 2000 unit, 3000 unit, 500 unit', 'Esperoct (Turoctocog Alfa Pegol) Powder for Intravenous Injection', 'powder for intravenous injection',
                'FDA label: glycopegylated recombinant factor VIII, supplied as single-dose vial powder for reconstitution. This payer listing specifies 500, 1000, 1500, 2000 and 3000 IU; other labeled vial strengths are not established by this listing. UHC GL-716187 provides a 12-month hemophilia A PA with routine infusion frequency criteria, including a pharmacokinetic exception for patients under age 12. Authorization stage is unspecified; frequency criteria are not a dispensing quantity limit.',
                '562f94e8-825f-4d7f-b93c-b783ac3a43bc', 'GL-716187', {14}, False, 'Esperoct named product (authorization stage unspecified)'),
            'uhc-oct-complete-32c32ab5f5ac35e6': (
                'premarin oral (brand for estrogens conjugated)', 'Premarin (Conjugated Estrogens) Oral Tablet', 'oral tablet',
                'FDA label: oral conjugated estrogen tablets are distinct from vaginal cream. UHC GL-140685 names Premarin without route and lists atrophic vaginitis and kraurosis vulvae, wording corresponding to the vaginal cream indication. Exact oral route applicability is unverified; do not treat this reference as confirmed oral criteria. The explicit oral PA and quantity-limit flags remain; numeric quantity limit and stage-specific oral criteria are unknown.',
                '258e1602-a3cf-4ccc-ca80-73dbbfb812ff', 'GL-140685', {1}, True, 'Premarin brand reference only (oral route applicability unverified)'),
        }
        if record['id'] in stage_scope_review_2:
            name, label, form, note, setid, code, indexes, has_ql, product_label = stage_scope_review_2[record['id']]
            assert october_name == name, (record['id'], october_name)
            assert record['pa'] == 'required' and record['preferred'] == 'non_preferred' and ql == has_ql
            assert matched.get(code) == indexes, (record['id'], matched)
            matched.pop(code)
            add(code, sorted(indexes), 'product')
            bindings[-1]['productLabel'] = product_label
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': label, 'dosageForm': form, 'note': note,
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=' + setid,
            }
        # DEC-05/06/12/13/14/19/20: formulation-specific labels, broad payer branches.
        everolimus_stage_scope = {
            'uhc-oct-complete-b16c95f918a6dc2d': (
                'everolimus oral tablet 10 mg, 2.5 mg, 5 mg, 7.5 mg (generic for torpenz)',
                'Everolimus Oral Tablet (payer reference Torpenz)', 'oral tablet',
                'FDA label: conventional 2.5, 5, 7.5 and 10 mg tablets, swallowed whole. Do not combine conventional and suspension tablets. TSC-associated partial-onset seizures are labeled for the suspension form, not this tablet.'),
            'uhc-oct-complete-c97bdc185635bff6': (
                'everolimus oral tablet soluble (generic for afinitor disperz)',
                'Everolimus Tablet for Oral Suspension (payer reference Afinitor Disperz)', 'tablet for oral suspension',
                'FDA label: 2, 3 and 5 mg tablets for preparation as a suspension, not swallowed whole. Do not combine conventional and suspension tablets. Labeled for TSC-associated SEGA and adjunctive partial-onset seizures; payer oncology criteria are not formulation-specific FDA indications.'),
        }
        if record['id'] in everolimus_stage_scope:
            name, label, form, note = everolimus_stage_scope[record['id']]
            assert october_name == name, (record['id'], october_name)
            assert record['pa'] == 'required' and record['preferred'] == 'preferred' and ql
            code = 'GL-657254'
            indexes = set(range(15))
            assert matched.get(code) == indexes, (record['id'], matched)
            matched.pop(code)
            add(code, sorted(indexes), 'product')
            bindings[-1]['productLabel'] = 'Everolimus named generic formulation (indication-specific applicability unverified)'
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': label, 'dosageForm': form,
                'note': note + ' UHC GL-657254 lists both generic forms, with 14 initial branches and one renewal branch. Prior generic/Yulithira failure, intolerance or contraindication is conditional on brand Afinitor/Disperz or Torpenz requests. Preferred NDC, exact indication applicability and numeric quantity limit are unverified.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=01f7b5fb-be0d-4adf-acd2-6899018de966',
            }
        # DEC-05/06/12/13/14/19/20: Fasenra PEN device and six named authorization stages.
        if record['id'] == 'uhc-oct-complete-991b6422f8bc9a8f':
            assert october_name == 'fasenra pen', (record['id'], october_name)
            assert record['pa'] == 'required' and record['preferred'] == 'preferred' and ql
            code = 'GL-646191'
            indexes = set(range(6))
            assert matched.get(code) == indexes, (record['id'], matched)
            matched.pop(code)
            add(code, sorted(indexes), 'product')
            bindings[-1]['productLabel'] = 'Fasenra named policy (pen-specific eligibility unverified)'
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Fasenra Pen (Benralizumab) Subcutaneous Autoinjector',
                'dosageForm': 'subcutaneous autoinjector',
                'note': 'FDA label (May 2026): 30 mg/1 mL pen; distinct from the healthcare-provider-administered prefilled syringes. For asthma ages 6–11 and weight below 35 kg, the labeled 10 mg dose requires the syringe; at 35 kg or more, the pen is administered only by a caregiver or healthcare provider. HES is labeled from age 12; EGPA in adults. UHC GL-646191 lists asthma, EGPA and HES initial and renewal criteria for Fasenra generally, not pen-specific eligibility. Numeric dispensing QL and exact device eligibility are unverified.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=da6aca1a-19ed-44a4-abb7-696c7d58b784',
            }
        # DEC-05/06/12/13/14/19/20: exact named scope and presentation review; preserve source flags.
        if record['id'] == 'uhc-oct-complete-ed2c1f1831632e6b':
            assert october_name == "fensolvi (6 month)", (record['id'], october_name)
            assert record['pa'] == 'required' and record['preferred'] == 'preferred' and ql
            code = 'GL-752232'
            indexes = set([0,1,5,6,7,8,9])
            assert matched.get(code) == indexes, (record['id'], matched)
            matched.pop(code)
            add(code, sorted(indexes), 'product')
            bindings[-1]['productLabel'] = "Fensolvi named policy (includes under-19 gender dysphoria exclusion; indication-specific)"
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': "Fensolvi (Leuprolide Acetate) Six-Month Subcutaneous Extended-Release Suspension",
                'dosageForm': "subcutaneous extended-release suspension",
                'note': "FDA label: 45 mg six-month subcutaneous extended-release suspension for central precocious puberty in children age 2 years or older; healthcare professional mixes and administers. Not interchangeable with other leuprolide depots. UHC GL-752232 also names adult gender-affirming adjunct and fertility preservation criteria; these are not Fensolvi FDA-labeled indications. Under age 19 gender dysphoria is excluded under the policy, with six-month grandfathering for treatment started on or before October 13, 2026; this is not an approval stage. Nonpreferred-only prerequisites do not automatically apply to this preferred listing. Numeric dispensing QL unverified.",
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=2c311700-edf4-4f2a-a468-9875489a6cc7',
            }
        if record['id'] == 'uhc-oct-complete-90f3ce4ee5762d4c':
            assert october_name == "fibryga intravenous solution reconstituted", (record['id'], october_name)
            assert record['pa'] == 'required' and record['preferred'] == 'preferred' and not ql
            code = 'GL-716187'
            indexes = set([22])
            assert matched.get(code) == indexes, (record['id'], matched)
            matched.pop(code)
            add(code, sorted(indexes), 'product')
            bindings[-1]['productLabel'] = "Fibryga named congenital deficiency policy (acquired indication unverified)"
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': "Fibryga (Fibrinogen Human) Intravenous Solution After Reconstitution",
                'dosageForm': "intravenous solution after reconstitution",
                'note': "FDA label: intravenous fibrinogen concentrate 1 g/50 mL or 2 g/100 mL after reconstitution (20 mg/mL). FDA labeling includes acquired fibrinogen deficiency bleeding; UHC GL-716187 branch 22 specifies congenital fibrinogen deficiency and treatment of bleeding episodes, 12 months, stage unspecified. Acquired indication eligibility is not established by this branch. RxNorm strength discrepancy remains unresolved; no strength-specific payer inference.",
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=e3422d2a-2cb6-6f49-0be7-cb960b3d5bd5',
            }
        if record['id'] == 'uhc-oct-complete-16f1d6bb95149d00':
            assert october_name == "dificid (brand for fidaxomicin)", (record['id'], october_name)
            assert record['pa'] == 'required' and record['preferred'] == 'preferred' and ql
            code = 'GL-390203'
            indexes = set([0])
            assert matched.get(code) == indexes, (record['id'], matched)
            matched.pop(code)
            add(code, sorted(indexes), 'product')
            bindings[-1]['productLabel'] = "Dificid named policy (payer form unverified)"
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': "Dificid (Fidaxomicin) Oral Tablet or Suspension (Payer Form Unverified)",
                'dosageForm': "oral tablet or oral suspension (payer form unverified)",
                'note': "FDA label: 200 mg tablet and 40 mg/mL oral suspension; pediatric patients age 6 months or older require formulation-specific weight and swallowing eligibility. Payer listing does not specify form. UHC GL-390203 requires generic oral vancomycin failure, contraindication or intolerance, or continuation of prior therapy; additional brand tablet failure or intolerance is conditional on generic tablets or brand suspension, not brand tablets. Ten-day authorization is not a numeric dispensing QL. Exact form eligibility unverified.",
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=dd966338-c820-4270-b704-09ef75fa3ceb',
            }
        # DEC-05/06/12/13/14/19/20: exact stage review; retain original payer flags and presentation holds.
        if record['id'] == 'uhc-oct-complete-f00d8199bade0f54':
            assert october_name == "genotropin", (record['id'], october_name)
            assert record['pa'] == 'required' and record['preferred'] == 'preferred' and not ql
            code = 'GL-723191'
            indexes = set([0,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20])
            assert matched.get(code) == indexes, (record['id'], matched)
            matched.pop(code)
            add(code, sorted(indexes), 'product')
            bindings[-1]['productLabel'] = "Genotropin named policy (includes ISS exclusion; device eligibility unverified)"
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': "Genotropin (Somatropin) Powder for Subcutaneous Injection",
                'dosageForm': "powder for subcutaneous injection",
                'note': "FDA label: distinct preserved 5 mg and 12 mg dual-chamber cartridges require matching PEN5/PEN12; MiniQuick is a preservative-free single-dose device. UHC GL-723191 expressly excludes idiopathic short stature despite FDA labeling; this is not an approval stage. Other policy indications are not necessarily FDA-labeled for Genotropin. Nonpreferred-only prerequisite does not apply to this preferred listing. Exact device eligibility unverified; policy supply restrictions are not a numeric dispensing QL.",
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=ffebf88b-d257-4542-9808-74d9b7167765',
            }
        if record['id'] == 'uhc-oct-complete-e48ac36405f1549a':
            assert october_name == "granisetron hcl oral", (record['id'], october_name)
            assert record['pa'] == 'required' and record['preferred'] == 'preferred' and ql
            code = 'GL-632222'
            indexes = set([0,1,2])
            assert matched.get(code) == indexes, (record['id'], matched)
            matched.pop(code)
            add(code, sorted(indexes), 'product')
            bindings[-1]['productLabel'] = "Granisetron HCl Oral Tablet or Solution named policy (payer form unverified)"
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': "Granisetron HCl Oral Tablet or Solution (Payer Form Unverified)",
                'dosageForm': "oral tablet or oral solution (payer form unverified)",
                'note': "FDA labels: 1 mg tablet and Granisol 0.2 mg/mL oral solution are distinct. Payer listing does not specify form. GL-632222 has chemotherapy, radiotherapy and postoperative criteria; postoperative use is not an indication in the reviewed oral tablet label. Inability to swallow solid dosage forms and ondansetron ODT failure, contraindication or intolerance apply to Granisol only, not tablets. Numeric dispensing QL unverified.",
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=df4b6775-4337-41e0-815a-b064d98c3fe1',
            }
        if record['id'] == 'uhc-oct-complete-f23ca72ff27b5a94':
            assert october_name == "hemlibra subcutaneous solution 105 mg/0.7ml, 150 mg/ml, 30 mg/ml", (record['id'], october_name)
            assert record['pa'] == 'required' and record['preferred'] == 'non_preferred' and not ql
            code = 'GL-716187'
            indexes = set([10])
            assert matched.get(code) == indexes, (record['id'], matched)
            matched.pop(code)
            add(code, sorted(indexes), 'product')
            bindings[-1]['productLabel'] = "Hemlibra named policy (routine prophylaxis; stage unspecified)"
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': "Hemlibra (Emicizumab-kxwh) Subcutaneous Solution 105 mg/0.7 mL, 150 mg/mL, 30 mg/mL",
                'dosageForm': "subcutaneous injection solution",
                'note': "FDA label: single-dose vials at 30 mg/mL or 150 mg/mL; do not combine different concentrations in one injection. UHC GL-716187 branch 10 specifies routine hemophilia A prophylaxis and distinct severity/inhibitor criteria, 12 months, stage unspecified. Do not infer coverage for unlisted vial sizes. Nonpreferred rule remains separate; this PDL row has no numeric QL verified.",
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=2483adba-fab6-4d1b-96c5-c195577ed071',
            }
        if record['id'] == 'uhc-oct-complete-16792cef09a93d60':
            assert october_name == "hemlibra subcutaneous solution 60 mg/0.4ml", (record['id'], october_name)
            assert record['pa'] == 'required' and record['preferred'] == 'non_preferred' and ql
            code = 'GL-716187'
            indexes = set([10])
            assert matched.get(code) == indexes, (record['id'], matched)
            matched.pop(code)
            add(code, sorted(indexes), 'product')
            bindings[-1]['productLabel'] = "Hemlibra named policy (routine prophylaxis; stage unspecified)"
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': "Hemlibra (Emicizumab-kxwh) Subcutaneous Solution 60 mg/0.4 mL",
                'dosageForm': "subcutaneous injection solution",
                'note': "FDA label: 60 mg/0.4 mL single-dose vial is 150 mg/mL, not 30 mg/mL; do not combine different concentrations in one injection. UHC GL-716187 branch 10 specifies routine hemophilia A prophylaxis and distinct severity/inhibitor criteria, 12 months, stage unspecified. Nonpreferred rule remains separate. This PDL row has an explicit QL flag; numeric dispensing QL unverified.",
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=2483adba-fab6-4d1b-96c5-c195577ed071',
            }
        # DEC-05/06/12/13/14/19/20: reviewed exact UHC named policy stages, without extending package or quantity eligibility.
        if record['id'] == 'uhc-oct-complete-44a3cc30cacb48e9':
            assert october_name == "humira (2 pen) subcutaneous auto-injector kit 80 mg/0.8ml", (record['id'], october_name)
            assert record['pa'] == 'required' and record['preferred'] == 'non_preferred' and ql
            code = 'GL-541212'
            assert matched.get(code) == set([0,1,2,3,4,5,6,7,8,9,10,11,12,13,14]), (record['id'], matched)
            matched.pop(code)
            add(code, [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14], 'product')
            bindings[-1]['productLabel'] = "Humira named policy (kit eligibility unverified)"
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': "Humira (Adalimumab) Subcutaneous Autoinjector Kit — 2 Pens, 80 mg/0.8 mL",
                'dosageForm': "subcutaneous autoinjector kit",
                'note': "FDA label: two single-dose pens, each 80 mg/0.8 mL (100 mg/mL); not a mixed-strength starter kit. UHC GL-541212 names Humira in 15 indication/stage branches; nonpreferred requests require failure of all preferred adalimumab biosimilars in each branch. Brand-level policy does not establish indication-specific kit eligibility or numeric dispensing QL.",
                'labelUrl': "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=4977567e-3525-44ac-9ff5-f1e74b053950",
            }
        if record['id'] == 'uhc-oct-complete-6f4d72453c49480d':
            assert october_name == "humira (2 syringe) subcutaneous prefilled syringe kit 10 mg/0.1ml, 20 mg/0.2ml, 40 mg/0.4ml", (record['id'], october_name)
            assert record['pa'] == 'required' and record['preferred'] == 'non_preferred' and ql
            code = 'GL-541212'
            assert matched.get(code) == set([0,1,2,3,4,5,6,7,8,9,10,11,12,13,14]), (record['id'], matched)
            matched.pop(code)
            add(code, [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14], 'product')
            bindings[-1]['productLabel'] = "Humira named policy (kit eligibility unverified)"
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': "Humira (Adalimumab) Subcutaneous Prefilled Syringe Kit — 2 Syringes, 10 mg/0.1 mL, 20 mg/0.2 mL, 40 mg/0.4 mL",
                'dosageForm': "subcutaneous prefilled syringe kit",
                'note': "FDA label: two single-dose syringes of the same selected strength, all 100 mg/mL; not a mixed-strength kit or autoinjector. Select the appropriate dose and device for age, weight and indication. UHC GL-541212 names Humira in 15 indication/stage branches; nonpreferred requests require failure of all preferred adalimumab biosimilars in each branch. Brand-level policy does not establish indication-specific kit eligibility or numeric dispensing QL.",
                'labelUrl': "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=4977567e-3525-44ac-9ff5-f1e74b053950",
            }
        if record['id'] == 'uhc-oct-complete-50e68f49403e10e7':
            assert october_name == "hysingla er (brand for hydrocodone bitartrate er)", (record['id'], october_name)
            assert record['pa'] == 'required' and record['preferred'] == 'non_preferred' and ql
            code = 'GL-620192'
            assert matched.get(code) == set([0,2,5,7,9,10,11,8]), (record['id'], matched)
            matched.pop(code)
            add(code, [0,2,5,7,9,10,11], 'product')
            bindings[-1]['productLabel'] = "Brand Hysingla ER named policy (conditional MME/DUR branches)"
            add(code, [8], 'quantity')
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': "Hysingla ER (Hydrocodone Bitartrate) 24-Hour Extended-Release Oral Tablet",
                'dosageForm': "24-hour extended-release oral tablet",
                'note': "FDA label: 24-hour extended-release tablet, not an immediate-release or ER capsule; swallow whole to avoid fatal overdose. UHC GL-620192 includes distinct concurrent MAT/opioid, cancer/hospice, non-cancer initial/renewal and cumulative MME exceptions. The quantity exception addresses requests that cannot be met by a higher strength and are within applicable FDA maximums; numeric dispensing QL unverified. Do not interpret an MME threshold as a dispensing quantity.",
                'labelUrl': "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=b7d23ac2-e776-9f62-3290-c64c2d6eb353",
            }
        # DEC-05/06/12/13/14/19/20: RFA9583 brand OxyContin ER tablet, not generic oxycodone ER.
        if record['id'] == 'uhc-oct-complete-8cd51f6265cf511b':
            assert october_name == 'oxycontin' and record['pa'] == 'required' and record['preferred'] == 'preferred' and ql
            code = 'GL-620192'
            assert matched.get(code) == {0,1,4,7,8,9,10,11}, (record['id'], matched)
            matched.pop(code)
            add(code, [1,4,7], 'product')
            bindings[-1]['productLabel'] = 'Brand OxyContin extended-release tablets'
            add(code, [8], 'quantity')
            add(code, [0], 'concurrent_opioid_dur')
            add(code, [9,10,11], 'mme_exception')
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'OxyContin (Oxycodone Hydrochloride) Extended-Release Oral Tablet',
                'dosageForm': 'extended-release oral tablet',
                'note': 'FDA label: 12-hour ER tablets 10, 15, 20, 30, 40, 60 and 80 mg; swallow intact, not for PRN use. The 60/80 mg tablets and high doses require established opioid tolerance. Pediatric use restricted to opioid-tolerant patients aged 11 or older. UHC GL-620192: brand OxyContin cancer/hospice, non-cancer initial and renewal criteria apply; generic oxycodone ER nonpreferred prerequisites do not apply. Concurrent opioid DUR, cumulative MME and quantity exceptions are distinct. Exact payer strength eligibility and numeric dispensing QL unverified.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=bfdfe235-d717-4855-a3c8-a13d26dadede',
            }
        # DEC-05/06/12/13/14/19/20: RFA9222 generic MS Contin-reference ER tablet, not brand/capsule initial pathways.
        if record['id'] == 'uhc-oct-complete-9db621ca8a237769':
            assert october_name == 'morphine sulfate er (generic for ms contin)' and record['pa'] == 'required' and record['preferred'] == 'preferred' and ql
            code = 'GL-620192'
            assert matched.get(code) == {0,1,2,4,5,7,8,9,10,11}, (record['id'], matched)
            matched.pop(code)
            add(code, [1,4,7], 'product')
            bindings[-1]['productLabel'] = 'Generic morphine sulfate ER tablets'
            add(code, [8], 'quantity')
            add(code, [0], 'concurrent_opioid_dur')
            add(code, [9,10,11], 'mme_exception')
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Morphine Sulfate Extended-Release Oral Tablet (Generic MS Contin)',
                'dosageForm': 'extended-release oral tablet',
                'note': 'FDA label: oral ER tablets 15, 30, 60, 100 and 200 mg; swallow whole, not for PRN use. Higher-strength 100/200 mg tablets require established opioid tolerance. Not ER capsules or beads. UHC GL-620192 generic tablet cancer/hospice, non-cancer initial and renewal criteria apply; brand/capsule-only initial prerequisites do not apply. Concurrent opioid DUR, cumulative MME and quantity exceptions are distinct. Exact payer strength eligibility and numeric dispensing QL unverified.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=533034fd-c8e7-495b-8874-0db41bd1e65a',
            }
        # DEC-05/06/12/13/14/16/19/20: RFA9380 manual prefilled syringe, not Onpro or pediatric vial.
        if record['id'] == 'uhc-oct-complete-279b6a3662f2dc13':
            assert october_name == 'neulasta subcutaneous solution prefilled syringe' and record['pa'] == 'required' and record['preferred'] == 'non_preferred' and not ql
            code = 'GL-648215'
            assert matched.get(code) == set(range(10)), (record['id'], matched)
            matched.pop(code)
            add(code, list(range(10)), 'product')
            bindings[-1]['productLabel'] = 'Neulasta named CSF policy (device and indication eligibility unverified)'
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Neulasta (Pegfilgrastim) 6 mg/0.6 mL Subcutaneous Prefilled Syringe',
                'dosageForm': 'subcutaneous prefilled syringe',
                'note': 'FDA label: manual single-dose syringe has no graduations and cannot deliver pediatric doses below 6 mg; the 4 mg/0.4 mL vial is separate. Onpro co-packaged syringe is ONLY for on-body injector; manual use overdoses, manual syringe in OBI underdoses. FDA label does not indicate use for stem cell mobilization. UHC GL-648215 names Neulasta across ten indication branches, not all FDA indications; stage unspecified, nonpreferred requests require failure, contraindication or intolerance to all preferred colony stimulating factors. Approval durations from policy notes range from 1 to 12 months by indication, not dispensing quantities. Exact package and indication eligibility unverified; no QL printed.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=fdfe5d72-6b80-435a-afa4-c5d74dd852ce',
            }
        # DEC-05/06/12/13/14/16/19/20: RFA9455 bare brand listing; do not assign benefits to each formulation.
        if record['id'] == 'uhc-oct-complete-db87969babd96230':
            assert october_name == 'noxafil' and record['pa'] == 'required' and record['preferred'] == 'non_preferred' and ql
            code = 'GL-751212'
            assert matched.get(code) == {8,9,10,11,14}, (record['id'], matched)
            matched.pop(code)
            add(code, [8,9,10,11,14], 'product')
            bindings[-1]['productLabel'] = 'Noxafil named oral policies (exact payer formulation unverified; not IV criteria)'
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Noxafil (Posaconazole) — Dosage Form Unverified',
                'dosageForm': 'dosage form unverified',
                'note': 'FDA label: four distinct presentations: 100 mg delayed-release oral tablet, 40 mg/mL oral suspension, PowderMix 300 mg packet for delayed-release oral suspension, and 300 mg/16.7 mL IV injection. Ordinary oral suspension is not substitutable for tablets or PowderMix. PowderMix is contraindicated in hereditary fructose intolerance. FDA tablet invasive aspergillosis and prophylaxis labeling requires age 2 or older and weight greater than 40 kg; UHC GL-751212 tablet prophylaxis allows weight at least 40 kg, a discrepancy at exactly 40 kg. PowderMix pediatric use is age 2 or older and 10–40 kg; ordinary suspension is age 13 or older for prophylaxis or oropharyngeal candidiasis (OPC). Named UHC branches 8–11 and 14 apply to specified oral presentations, not injection; OPC requires two listed antifungal failures, contraindications, intolerances or resistance, or inpatient continuation. The bare brand PDL listing does not identify which formulation is covered. Exact formulation eligibility, age-limit flag details and numeric dispensing QL unverified.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=b073b082-7b57-4423-8c06-4fd4263d6f84',
            }
        # DEC-05/06/12/13/14/19/20: RFA9473 oral Nuzyra, not IV; continuation alternatives retained.
        if record['id'] == 'uhc-oct-complete-a8a214653d1ccd59':
            assert october_name == 'nuzyra oral' and record['pa'] == 'required' and record['preferred'] == 'preferred' and ql
            code = 'GL-140701'
            assert matched.get(code) == {0,1,2}, (record['id'], matched)
            matched.pop(code)
            add(code, [0,1,2], 'product')
            bindings[-1]['productLabel'] = 'Nuzyra named policy (oral listing; stage unspecified)'
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Nuzyra (Omadacycline) 150 mg Oral Tablet',
                'dosageForm': 'oral tablet',
                'note': 'FDA label: 150 mg oral tablet is distinct from the 100 mg IV formulation; adult CABP and ABSSSI, labeled 7–14 days. Oral administration has food and polyvalent cation timing requirements. UHC GL-140701: CABP and ABSSSI 14-day authorizations, off-label duration based on provider recommendation up to 6 months; stage unspecified. Hospital discharge or transition from susceptible IV antibiotics are independent continuation alternatives. Otherwise CABP requires susceptible infection and three named prior regimens; ABSSSI has a MRSA pathway requiring linezolid plus one named alternative or a susceptible-organism pathway requiring three named agents; off-label ID specialist consultation is a separate alternative. See policy for full criteria and exact alternative logic. Authorization duration is not a numeric dispensing QL. Exact payer package and numeric QL unverified; no IV benefit inference.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=51591524-4703-44c6-8bde-dce3e6a463d1',
            }
        # DEC-05/06/12/13/14/19/20: RFA9515/9516 distinct strength-specific RA scope and diagnosis exclusion.
        reviewed_olumiant = {
            'uhc-oct-complete-593298d1e2b0b802': ('olumiant oral tablet 1 mg, 2 mg', [0,1,2,3], True, '1 mg, 2 mg', 'RA initial and renewal apply only to 1 mg and 2 mg: initial requires chart notes or claims, the specified nonbiologic DMARD trial and all five listed biologic/JAK prerequisites (preferred adalimumab biosimilar OR Enbrel is one of the five), plus rheumatologist; renewal requires positive response and rheumatologist. Each authorizes 12 months. Numeric dispensing QL unverified.'),
            'uhc-oct-complete-deb365a5276facd9': ('olumiant oral tablet 4 mg', [2,3], False, '4 mg', 'RA initial and renewal name 1 mg and 2 mg only; do not assign those criteria to this 4 mg listing. No QL printed.'),
        }
        if record['id'] in reviewed_olumiant:
            name, indexes, has_ql, strengths, note = reviewed_olumiant[record['id']]
            assert october_name == name, (record['id'], october_name)
            assert record['pa'] == 'required' and record['preferred'] == 'non_preferred' and bool(ql) == has_ql
            code = 'GL-324206'
            assert matched.get(code) == set(indexes), (record['id'], matched)
            matched.pop(code)
            add(code, indexes, 'product')
            bindings[-1]['productLabel'] = 'Olumiant ' + strengths + ' named indication policy'
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Olumiant (Baricitinib) ' + strengths + ' Oral Tablet',
                'dosageForm': 'oral tablet',
                'note': note + ' UHC GL-324206: COVID-19 requires hospitalization and oxygen, ventilation or ECMO, with 14-day authorization; FDA indication is adults. Alopecia areata is a use-specific benefit exclusion, despite FDA labeling for severe alopecia areata from age 12 since September 2026; not a blanket exclusion. COVID-19 and alopecia stages unspecified. GL-733328 therapeutic duplication is a separate administrative review, not routine RA criteria or dispensing quantity.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=866e9f35-9035-4581-a4b1-75a621ab55cf',
            }
        # DEC-05/06/12/13/14/19/20: RFA9559/9560 strength-specific treatment durations and capsule-only policy.
        reviewed_orilissa_orladeyo = {
            'uhc-oct-complete-e4cc9976aa1b8bb4': ('orilissa', 'preferred', 'GL-140726', [0,1,2], 'Orilissa named 150 mg initial/renewal and 200 mg stage-unspecified policy', 'Orilissa (Elagolix) Oral Tablet', 'oral tablet', 'FDA label: 150 mg once daily for up to 24 months in normal or mild hepatic impairment; 200 mg twice daily for up to 6 months. Moderate hepatic impairment: 150 mg once daily, maximum 6 months; 200 mg twice daily not recommended. Contraindicated in pregnancy, known osteoporosis and severe hepatic impairment; dose- and duration-dependent bone loss. UHC GL-140726: 150 mg initial and renewal each authorize 6 months up to a total of 24 months; 200 mg branch has a 6-month maximum with stage unspecified. Initial 150 mg and 200 mg criteria require premenopausal endometriosis pain, specified three-month trials of two analgesics and one hormonal contraceptive or progestin (or contraindication/intolerance), and OB/GYN or reproductive endocrinologist. The 150 mg renewal requires response, BMD impact considered and total duration within 24 months; do not assign to 200 mg. Exact payer strength eligibility and numeric dispensing QL unverified.', 'a86757b3-09c5-fd3b-1223-244e94f50a66'),
            'uhc-oct-complete-d5f0d9099efaea18': ('orladeyo oral capsule', 'non_preferred', 'GL-546227', [0], 'Orladeyo capsule HAE prophylaxis policy (stage unspecified; not pellets)', 'Orladeyo (Berotralstat) Oral Capsule', 'oral capsule', 'FDA label: 110 mg and 150 mg capsules for age 12 or older, distinct from oral pellet packets for pediatric weight-based dosing and labeled pellet use. Prophylaxis only, not acute attacks; higher than recommended doses increase QTc risk. UHC GL-546227 HAE prophylaxis requires documented diagnostic pathway, age at least 12 for capsules (at least 2 for pellets), allergist/immunologist, and documented failure, contraindication or intolerance to Cinryze or Haegarda OR current therapy with a named agent. Authorizes 12 months, stage unspecified. Do not infer pellet benefit from this capsule row. Exact strength/package and numeric dispensing QL unverified.', '3527ece1-e7e0-40b1-b0c5-6baeb0deabeb'),
        }
        if record['id'] in reviewed_orilissa_orladeyo:
            name, pref, code, indexes, scope, label, form, note, setid = reviewed_orilissa_orladeyo[record['id']]
            assert october_name == name, (record['id'], october_name)
            assert record['pa'] == 'required' and record['preferred'] == pref and ql
            assert matched.get(code) == set(indexes), (record['id'], matched)
            matched.pop(code)
            add(code, indexes, 'product')
            bindings[-1]['productLabel'] = scope
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': label, 'dosageForm': form, 'note': note,
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=' + setid,
            }
        # DEC-05/06/12/13/14/19/20: exact stage-unspecified named policy; preserve brand-only prerequisites and raw flags.
        reviewed_stage_options = {
            'uhc-oct-complete-3db650dbb78aa872': ("icatibant acetate (generic for firazyr)", "preferred", "GL-546227", 1, "Generic icatibant acute HAE policy (stage unspecified)", "Icatibant (Generic Firazyr) Subcutaneous Prefilled Syringe", "subcutaneous prefilled syringe", "FDA label: single-dose 30 mg/3 mL (10 mg/mL) prefilled syringe. UHC GL-546227 acute HAE branch: age 18 or older for generic icatibant, confirmed HAE diagnosis, allergist/immunologist and no concurrent approved acute HAE treatment; 12 months, stage unspecified. Preferred-agent failure or current therapy prerequisite applies to named nonpreferred agents, not generic icatibant. Exact carton eligibility and numeric dispensing QL unverified.", "ccbb5e50-ce56-4898-aa1a-f1c1f3d312f6"),
            'uhc-oct-complete-62e4bb1c3d06bdc7': ("gleevec oral tablet 100 mg (brand for imatinib mesylate)", "non_preferred", "GL-741203", 0, "Brand Gleevec cancer policy (stage unspecified)", "Gleevec (Imatinib Mesylate) 100 mg Oral Tablet", "oral tablet", "FDA label: 100 mg oral tablet; the 400 mg tablet is separate. UHC GL-741203 cancer branch requires NCCN category 1, 2A or 2B use and trial/failure of preferred generic imatinib for nonpreferred Brand Gleevec or Imkeldi; 12 months, stage unspecified. Imkeldi is an oral solution, not this tablet. Numeric dispensing QL unverified.", "211ef2da-2868-4a77-8055-1cb2cd78e24b"),
            'uhc-oct-complete-8f9b8e5073a65ff3': ("imatinib mesylate oral (generic for gleevec)", "preferred", "GL-741203", 0, "Generic imatinib cancer policy (stage unspecified)", "Imatinib Mesylate (Generic Gleevec) Oral Tablets", "oral tablet", "FDA label: 100 mg and 400 mg film-coated oral tablets; payer listing does not specify strengths. UHC GL-741203 cancer branch requires NCCN category 1, 2A or 2B use; 12 months, stage unspecified. Brand-only generic trial/failure requirement does not apply to generic imatinib. Imkeldi oral solution is separate. Exact strength eligibility and numeric dispensing QL unverified.", "07764bf9-21b4-4e32-9d7e-e348f8e4291f"),
        }
        if record['id'] in reviewed_stage_options:
            name, pref, code, index, scope, label, form, note, setid = reviewed_stage_options[record['id']]
            assert october_name == name, (record['id'], october_name)
            assert record['pa'] == 'required' and record['preferred'] == pref and ql
            assert matched.get(code) == {index}, (record['id'], matched)
            matched.pop(code)
            add(code, [index], 'product')
            bindings[-1]['productLabel'] = scope
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': label, 'dosageForm': form, 'note': note,
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=' + setid,
            }
        # DEC-05/06/12/13/14/19/20: exact stage and non-solid scope; no QL extrapolation.
        reviewed_stage_options_jivi_lacosamide = {
            'uhc-oct-complete-69ac4f11b2cd9e7e': ("jivi intravenous solution reconstituted 1000 unit, 2000 unit, 3000 unit, 500 unit", "non_preferred", "GL-716187", 8, "Jivi named hemophilia A policy (stage unspecified)", "Jivi (Damoctocog Alfa Pegol) Powder for Intravenous Injection — 500, 1000, 2000, 3000 IU", "powder for intravenous injection", "FDA label: recombinant PEGylated factor VIII, IV only after reconstitution, for previously treated patients age 7 or older; not indicated for von Willebrand disease. FDA also labels a 4000 IU vial, not included in this PDL row. UHC GL-716187 requires physician attestation that shorter half-life factor VIII is unsuitable and routine infusion no more than twice weekly; 12 months, stage unspecified. Frequency is a policy criterion, not a numeric dispensing limit. No QL printed.", "f04e5bd5-d7e2-453b-a407-2616d81a695d", False),
            'uhc-oct-complete-e73b15b47b711f87': ("vimpat oral (brand for lacosamide)", "non_preferred", "GL-572198", 0, "Brand Vimpat oral policy (payer form unspecified)", "Vimpat (Lacosamide) Oral Tablet or Solution (Payer Form Unverified)", "oral tablet or solution; payer form unverified", "FDA label: oral film-coated tablets and 10 mg/mL oral solution are distinct from IV injection. UHC GL-572198 covers a diagnosis pathway for partial-onset or primary generalized tonic-clonic seizures or continuation of prior seizure therapy. For the diagnosis pathway, nonpreferred requests require the specified two-agent trials and response or intolerance evidence; Brand Vimpat additionally requires generic lacosamide failure, contraindication or intolerance. No separate initial/renewal stage printed; 12 months. Exact oral form, age-limit flag details and numeric QL unverified.", "9e79b42c-38a3-4b2c-a196-a5a1948250e2", True),
            'uhc-oct-complete-d8e1730a52588b48': ("lacosamide oral solution 10 mg/ml, 100 mg/10ml, 50 mg/5ml (generic for vimpat)", "preferred", "GL-572198", 0, "Generic lacosamide oral solution policy (stage unspecified)", "Lacosamide (Generic Vimpat) Oral Solution 10 mg/mL", "oral solution", "FDA label: 10 mg/mL oral solution; 100 mg/10 mL and 50 mg/5 mL are the same concentration, not distinct strengths. UHC GL-572198 diagnosis or continuation pathway, 12 months; brand-only and nonpreferred prerequisites do not apply to this preferred generic. Separate GL-545275 non-solid administrative review retains inability to swallow, feeding tube or applicable solid-alternative criteria. Do not transfer to oral tablets. Age-limit flag details and numeric QL unverified.", "024bca92-cac5-4832-a1ff-c1b3d5994ba0", True),
            'uhc-oct-complete-699ad8210001a43d': ("lacosamide oral tablet (generic for vimpat)", "preferred", "GL-572198", 0, "Generic lacosamide oral tablet policy (stage unspecified)", "Lacosamide (Generic Vimpat) Oral Tablet", "oral tablet", "FDA label: 50, 100, 150 and 200 mg film-coated oral tablets, distinct from solution and IV injection. UHC GL-572198 diagnosis or continuation pathway, 12 months; brand-only and nonpreferred prerequisites do not apply to this preferred generic. Non-solid administrative review is not a tablet requirement. Exact strength eligibility, age-limit flag details and numeric QL unverified.", "df1d2e6a-6129-49c9-b2c1-0fdf73f38b9c", True),
        }
        if record['id'] in reviewed_stage_options_jivi_lacosamide:
            name, pref, code, index, scope, label, form, note, setid, has_ql = reviewed_stage_options_jivi_lacosamide[record['id']]
            assert october_name == name, (record['id'], october_name)
            assert record['pa'] == 'required' and record['preferred'] == pref and bool(ql) == has_ql
            assert matched.get(code) == {index}, (record['id'], matched)
            matched.pop(code)
            add(code, [index], 'product')
            bindings[-1]['productLabel'] = scope
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': label, 'dosageForm': form, 'note': note,
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=' + setid,
            }
        # DEC-05/06/12/13/14/19/20: Lupron formulation and named indication/stage scope.
        reviewed_lupron_stage = {
            'uhc-oct-complete-9e43afbe428c7e21': ("lupron depot (1-month)", "preferred", [2,3,4,5,6,7,8,9,10], "Lupron Depot (Leuprolide) 1-Month IM Depot Suspension Kit", "FDA labels distinguish adult 3.75 mg gynecologic and 7.5 mg prostate monthly kits; exact payer strength unverified. Endometriosis initial/renewal and fibroids branches name 3.75 mg, prostate branch names 7.5 mg, not interchangeable. UHC GL-752232: under-19 gender dysphoria is a use-specific exclusion, with six-month grandfathering for therapy begun on or before Oct 13, 2026; not a blanket exclusion. Adult adjunct and fertility preservation each have distinct initial and renewal pathways (12 months); exact indication eligibility is unverified. Numeric dispensing QL unverified.", "00c486b0-bd7b-4898-834d-8c656e5e73cb", True),
            'uhc-oct-complete-574bd69073276e99': ("lupron depot (3-month) intramuscular kit 22.5 mg", "non_preferred", [5,6,7,8,9,10], "Lupron Depot (Leuprolide) 22.5 mg 3-Month IM Depot Suspension Kit", "FDA label: advanced prostate cancer, 12-week kit, distinct from gynecologic 11.25 mg and pediatric 3-month kits. UHC GL-752232: under-19 gender dysphoria is a use-specific exclusion, with six-month grandfathering for therapy begun on or before Oct 13, 2026; not a blanket exclusion. Adult adjunct and fertility preservation each have distinct initial and renewal pathways (12 months); exact indication eligibility is unverified. Prostate and nonpreferred adult adjunct/fertility branches retain their named alternative requirements; continuation exception is not for this kit. Numeric dispensing QL unverified.", "cbc8f94e-7330-4465-05ad-16d64493a5dd", True),
            'uhc-oct-complete-603070689561b9d7': ("lupron depot (4-month) intramuscular kit 30mg", "non_preferred", [5,6,7,8,9,10], "Lupron Depot (Leuprolide) 30 mg 4-Month IM Depot Suspension Kit", "FDA label: advanced prostate cancer, 16-week kit, not pediatric 30 mg 3-month kit. UHC GL-752232: under-19 gender dysphoria is a use-specific exclusion, with six-month grandfathering for therapy begun on or before Oct 13, 2026; not a blanket exclusion. Adult adjunct and fertility preservation each have distinct initial and renewal pathways (12 months); exact indication eligibility is unverified. Prostate and nonpreferred adult adjunct/fertility branches retain named alternative requirements; continuation exception is not for this kit. Numeric dispensing QL unverified.", "cbc8f94e-7330-4465-05ad-16d64493a5dd", True),
            'uhc-oct-complete-f1461e4b8f46fcb2': ("lupron depot (6-month) intramuscular kit 45mg", "non_preferred", [5,6,7,8,9,10], "Lupron Depot (Leuprolide) 45 mg 6-Month IM Depot Suspension Kit", "FDA label: advanced prostate cancer, 24-week kit; distinct from pediatric 45 mg. Different release formulations are not additive. UHC GL-752232: under-19 gender dysphoria is a use-specific exclusion, with six-month grandfathering for therapy begun on or before Oct 13, 2026; not a blanket exclusion. Adult adjunct and fertility preservation each have distinct initial and renewal pathways (12 months); exact indication eligibility is unverified. Continuation of prior therapy is a nonpreferred alternative for prostate and adult adjunct/fertility renewal, not initial. Numeric dispensing QL unverified.", "cbc8f94e-7330-4465-05ad-16d64493a5dd", True),
            'uhc-oct-complete-7d034ab551399d27': ("lupron depot-ped (1-month)", "preferred", [0,1,5,6,7,8,9], "Lupron Depot-Ped (Leuprolide) 1-Month IM Depot Suspension Kit", "FDA label: central precocious puberty (CPP); 7.5, 11.25 or 15 mg monthly, distinct from adult and longer-release kits. Exact payer strength eligibility unverified. CPP initial requires onset and diagnostic evidence; renewal requires response and age criteria. UHC GL-752232: under-19 gender dysphoria is a use-specific exclusion, with six-month grandfathering for therapy begun on or before Oct 13, 2026; not a blanket exclusion. Adult adjunct and fertility preservation each have distinct initial and renewal pathways (12 months); exact indication eligibility is unverified. Numeric dispensing QL unverified.", "e99f47d2-da10-3127-ecb3-e5d942ae6e81", True),
            'uhc-oct-complete-df7e2017cb699106': ("lupron depot-ped (3-month)", "non_preferred", [0,1,5,6,7,8,9], "Lupron Depot-Ped (Leuprolide) 3-Month IM Depot Suspension Kit", "FDA label: CPP; 11.25 or 30 mg every 12 weeks, distinct from monthly pediatric 11.25 mg and adult 30 mg 4-month kit. Exact payer strength eligibility unverified. UHC GL-752232: under-19 gender dysphoria is a use-specific exclusion, with six-month grandfathering for therapy begun on or before Oct 13, 2026; not a blanket exclusion. Adult adjunct and fertility preservation each have distinct initial and renewal pathways (12 months); exact indication eligibility is unverified. Continuation of prior therapy is an alternative for nonpreferred CPP and adult adjunct/fertility renewal, not initial. No QL printed.", "e99f47d2-da10-3127-ecb3-e5d942ae6e81", False),
        }
        if record['id'] in reviewed_lupron_stage:
            name, pref, indexes, label, note, setid, has_ql = reviewed_lupron_stage[record['id']]
            assert october_name == name, (record['id'], october_name)
            assert record['pa'] == 'required' and record['preferred'] == pref and bool(ql) == has_ql
            code = 'GL-752232'
            assert matched.get(code) == set(indexes), (record['id'], matched)
            matched.pop(code)
            add(code, indexes, 'product')
            bindings[-1]['productLabel'] = 'Named Lupron indication and stage criteria; formulation-specific limits apply'
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': label, 'dosageForm': 'intramuscular depot suspension kit', 'note': note,
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=' + setid,
            }
        # DEC-05/06/12/13/14/19/20: 300 mg hyperglycemia presentation is not the reproductive-health product.
        if record['id'] == 'uhc-oct-complete-bfb63d261b16bc39':
            assert october_name == 'mifepristone oral tablet 300 mg (generic for korlym)' and record['pa'] == 'required' and record['preferred'] == 'preferred' and ql
            assert matched.get('GL-140849') == {0, 1} and matched.get('GL-434343') == {0}, (record['id'], matched)
            matched.pop('GL-140849')
            matched.pop('GL-434343')
            record['excludedPolicyCode'] = 'GL-434343'
            record['unverifiedPolicyCode'] = 'GL-140849'
            add('GL-140849', [0, 1], 'korlym_reference')
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Mifepristone 300 mg Oral Tablet (Korlym reference)', 'dosageForm': 'oral tablet',
                'note': 'FDA label: adult hyperglycemia secondary to endogenous Cushing syndrome in patients with type 2 diabetes or glucose intolerance who have failed surgery or are not candidates for surgery. Pregnancy contraindicated. Not equivalent to Mifeprex 200 mg. Korlym brand initial/renewal policy is a reference; generic applicability and numeric quantity limit are unverified.',
                'labelUrl': 'https://www.dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=542f3fae-8bc8-4f00-9228-e4b66c9ad6a9',
            }
            sources = record.get('policySources', [])
            excluded = [p for p in sources if p.get('policyCode') == 'GL-434343' or p.get('policyId', '').endswith('gl-434343')]
            if excluded:
                record['excludedPolicySources'] = excluded
                record['policySources'] = [p for p in sources if p not in excluded]
        # DEC-05/06/12/13/14/19/20: Lybalvi product/stage and policy-supported limit, preserve raw PDL flags.
        if record['id'] == 'uhc-oct-complete-6a6a03b0a0dddc28':
            code = 'GL-722200'
            assert october_name == 'lybalvi' and record['pa'] == 'required' and record['preferred'] == 'non_preferred' and ql
            assert matched.get(code) == {1, 4, 10}, (record['id'], matched)
            assert policies[code]['policyEffective'] == '2026-10-18'
            matched.pop(code)
            add(code, [1, 4], 'product')
            bindings[-1]['productLabel'] = 'Lybalvi adult schizophrenia and bipolar I policy (stage unspecified)'
            add(code, [10], 'quantity')
            record['policyQuantityLimit'] = {'text': '1 tablet/day; see product-specific quantity exception criteria.', 'sourcePolicyId': policies[code]['id']}
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': "Lybalvi (Olanzapine/Samidorphan) Oral Tablet", 'dosageForm': 'oral tablet',
                'note': "FDA label: adult schizophrenia and bipolar I disorder; olanzapine/samidorphan 5/10, 10/10, 15/10 and 20/10 mg tablets. Contraindicated in patients using opioids or in acute opioid withdrawal; not equivalent to olanzapine alone. UHC GL-722200 schizophrenia and bipolar I branches (12 months each; stage unspecified) require age 18 or older and different alternative-drug criteria, plus one Lybalvi-specific BMI, weight-gain or documented samidorphan rationale pathway. Separate quantity exception policy explicitly identifies 1 tablet/day; exact strength eligibility and PDL age-limit details unverified.",
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=32ffddd1-4e2b-45d9-9b36-bb730167ec80',
            }
        # DEC-05/06/12/13/14/19/20: device-specific labeling only; preserve existing general named criteria.
        device_label_holds = {
            'uhc-oct-complete-49d179ce14de8e08': (
                'xolair subcutaneous solution auto-injector', 'Xolair (Omalizumab) Subcutaneous Autoinjector', 'subcutaneous autoinjector',
                'FDA label: 75 mg/0.5 mL, 150 mg/mL, or 300 mg/2 mL single-dose autoinjector; device only for age 12 or older, even when the indication permits younger children. Anaphylaxis boxed warning; initiate in a healthcare setting and assess suitability before self-administration.',
                '7f6a2191-adfb-48b9-9bfa-0d9920479f0d', 'GL-713364', set(range(8)), 'preferred', True),
            'uhc-oct-complete-2ba862a9dacbc59b': (
                'xolair subcutaneous solution prefilled syringe', 'Xolair (Omalizumab) Subcutaneous Prefilled Syringe', 'subcutaneous prefilled syringe',
                'FDA label: 75 mg/0.5 mL, 150 mg/mL, or 300 mg/2 mL single-dose prefilled syringe; distinct from autoinjector. For eligible pediatric patients age 1 to 11, administration is by caregiver after appropriate selection; indication-specific ages still apply. Anaphylaxis boxed warning; initiate in a healthcare setting.',
                '7f6a2191-adfb-48b9-9bfa-0d9920479f0d', 'GL-713364', set(range(8)), 'preferred', True),
            'uhc-oct-complete-396902bfb6ebf8b7': (
                'xolair subcutaneous solution reconstituted', 'Xolair (Omalizumab) Powder for Subcutaneous Injection', 'powder for subcutaneous injection',
                'FDA label: 150 mg single-dose lyophilized vial yields 150 mg/1.2 mL after reconstitution; preparation and administration by a healthcare provider only. Distinct from ready-to-use syringe and autoinjector. Anaphylaxis boxed warning.',
                '7f6a2191-adfb-48b9-9bfa-0d9920479f0d', 'GL-713364', set(range(8)), 'preferred', True),
            'uhc-oct-complete-caf5904f63f299c4': (
                'yorvipath subcutaneous solution pen-injector 294 mcg/0.98ml', 'Yorvipath (Palopegteriparatide) 294 mcg/0.98 mL Subcutaneous Pen', 'subcutaneous pen injector',
                'FDA label: this single-patient-use pen delivers only 15, 18 or 21 mcg doses; 294 mcg is total pen content, not a daily dose. Distinct from 168 mcg/0.56 mL and 420 mcg/1.4 mL pens and from teriparatide osteoporosis products.',
                'a1fa23fd-c434-443e-9a17-5750578c8602', 'GL-163670', {0, 1}, 'non_preferred', False),
        }
        if record['id'] in device_label_holds:
            name, label, form, note, setid, code, indexes, preference, has_ql = device_label_holds[record['id']]
            assert october_name == name, (record['id'], october_name)
            assert record['pa'] == 'required' and record['preferred'] == preference and bool(ql) == has_ql
            assert matched.get(code) == indexes, (record['id'], matched)
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': label, 'dosageForm': form,
                'note': note + ' UHC general product criteria remain linked; exact device/package applicability is unverified.' + (' Numeric quantity limit unverified.' if has_ql else ' No quantity limit printed for this listing.'),
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=' + setid,
            }
        # DEC-05/06/12/13/14/19/20: label-backed identities, no extrapolated payer criteria.
        label_holds = {
            'uhc-oct-complete-d6b49b27961f969c': (
                "vascepa (brand for icosapent ethyl)", "Vascepa (Icosapent Ethyl) Oral Capsule", "oral capsule",
                "FDA label: 0.5 and 1 g capsules, distinct from mixed EPA/DHA omega-3 products. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "9c1a2828-1583-4414-ab22-a60480e8e508", True),
            'uhc-oct-complete-9e388ff3dae2c7a5': (
                "viokace", "Viokace (Pancrelipase) Oral Tablet", "oral tablet",
                "FDA label: 10,440 and 20,880 lipase-unit tablets; indicated with a proton pump inhibitor in adults with exocrine pancreatic insufficiency due to chronic pancreatitis or pancreatectomy. Do not substitute other pancreatic enzyme products. Exact UHC product-specific initial/renewal criteria are unverified. No quantity limit printed for this listing.",
                "58bdb8de-582d-44e6-9b72-8d5a42fdf501", False),
            'uhc-oct-complete-0c501f7a157fe744': (
                "vyzulta", "Vyzulta (Latanoprostene Bunod) Ophthalmic Solution", "ophthalmic solution",
                "FDA label: 0.024% (0.24 mg/mL), distinct from latanoprost. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "60ce7900-a677-4fc2-88d0-1603baa9dbd4", True),
            'uhc-oct-complete-7654658c09b78f85': (
                "winlevi", "Winlevi (Clascoterone) Topical Cream", "topical cream",
                "FDA label: 1% cream for acne in patients aged 12 years and older; not for oral, ophthalmic or vaginal use. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "1673a84b-7f5c-47ab-a99c-1e3db21a6a09", True),
            'uhc-oct-complete-275ef9d310381264': (
                "winrevair subcutaneous kit 2 x 45 mg", "Winrevair (Sotatercept-csrk) 2 x 45 mg Subcutaneous Injection Kit", "subcutaneous injection kit",
                "FDA label: two 45 mg single-dose vials with diluent for reconstitution, distinct from 1-vial and 60 mg kits. GL-715293 describes Winrevair for PAH generally, not this exact kit. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "21693ee2-cd23-4137-ac67-066bb3a4a9b7", True),
            'uhc-oct-complete-e3adddae581cbcfd': (
                "xaciato", "Xaciato (Clindamycin) Vaginal Gel", "vaginal gel",
                "FDA label: 2% single-dose vaginal gel (100 mg/5 g), distinct from multidose cream. Avoid polyurethane condoms during treatment and for 7 days afterward; use latex or polyisoprene instead. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "0423007f-28fa-4159-bf58-9174626d2347", True),
            'uhc-oct-complete-00da649844317125': (
                "zeposia 7-day starter pack", "Zeposia (Ozanimod) 7-Day Oral Capsule Titration Pack", "oral capsule titration pack",
                "FDA label: four 0.23 mg and three 0.46 mg capsules; no 0.92 mg maintenance capsules in this seven-day pack. Distinct from 28- and 37-day starter kits. UHC GL-720197 effective October 18, 2026 describes Zeposia for MS and UC generally, not this exact pack. Exact UHC product-specific initial/renewal criteria for the pack and numeric quantity limit are unverified.",
                "93ce2fab-edfb-4804-8074-963071de51e4", True),
            'uhc-oct-complete-d4c999ec3fe83160': (
                "zioptan (brand for tafluprost (pf))", "Zioptan (Tafluprost) Preservative-Free Ophthalmic Solution", "ophthalmic solution",
                "FDA label: 0.0015% (15 mcg/mL), 0.3 mL single-use containers; discard after opening and use. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "db529b54-2ac7-4020-9791-7333bbe6c90f", True),
            'uhc-oct-complete-dc190cbfa1a36c65': (
                "zonegran (brand for zonisamide)", "Zonegran (Zonisamide) Oral Capsule", "oral capsule",
                "FDA label: 25 and 100 mg capsules, distinct from zonisamide oral suspension. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "d12de43e-3ac3-4335-bc85-70d7366a91eb", True),
            'uhc-oct-complete-4001483fb5296830': (
                "zypitamag", "Zypitamag (Pitavastatin Magnesium) Oral Tablet", "oral tablet",
                "FDA label: 2 and 4 mg pitavastatin equivalents as the magnesium salt, distinct from pitavastatin calcium. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "e9f0fe3a-0462-4c24-8f22-3c89afe8fcea", True),
            'uhc-oct-complete-8e34212b5a29106f': (
                'topamax (brand for topiramate)', 'Topamax (Topiramate) Oral Tablet', 'oral tablet',
                'FDA label: 25, 50, 100 and 200 mg immediate-release tablets, distinct from sprinkle capsules and ER formulations. GL-572198 mentions generic IR tablets as trial alternatives, not as a named brand Topamax PA branch. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.',
                '21628112-0c47-11df-95b3-498d55d89593', True),
            'uhc-oct-complete-0b3a19b761869f8f': (
                "tiglutik", "Tiglutik (Riluzole) Oral Suspension", "oral suspension",
                "FDA label: riluzole 5 mg/mL (50 mg/10 mL) oral suspension for oral or PEG-tube administration, distinct from riluzole tablets and oral film. Shake gently before administration; liver enzyme monitoring is required. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "75d68f19-4208-109e-e053-2991aa0ac857", True),
            'uhc-oct-complete-3be2fce160eb4e1a': (
                "betimol (brand for timolol hemihydrate)", "Betimol (Timolol Hemihydrate) Ophthalmic Solution", "ophthalmic solution",
                "FDA label: 0.25% and 0.5% timolol ophthalmic solution as hemihydrate, distinct from timolol maleate and gel-forming products. Systemic beta-blocker effects may occur, including bronchospasm and bradycardia. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "3ae775f4-340c-4bf4-aa49-8a31daba0f8b", True),
            'uhc-oct-complete-ce85f87b9d08019d': (
                "thiola (brand for tiopronin)", "Thiola (Tiopronin) Oral Tablet", "oral tablet",
                "FDA label: 100 mg sugar-coated oral tablet, not delayed-release; take on an empty stomach at least one hour before or two hours after meals. Distinct from Thiola EC. Monitor for proteinuria. Exact UHC product-specific initial/renewal criteria are unverified; no quantity limit printed for this listing.",
                "494a714e-923c-cd57-df6c-12886afb265a", False),
            'uhc-oct-complete-fe1aa6c1fd02f3ed': (
                "thiola ec (brand for tiopronin)", "Thiola EC (Tiopronin) Delayed-Release Oral Tablet", "delayed-release oral tablet",
                "FDA label: 100 and 300 mg delayed-release tablets, with or without food on a consistent meal schedule. Avoid alcohol two hours before and three hours after administration. Distinct from conventional Thiola; monitor for proteinuria. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "20298a52-a194-a161-8632-d84b6f26e23c", True),
            'uhc-oct-complete-9d8ad92e4e67aa1f': (
                'tazorac (brand for tazarotene)', 'Tazorac (Tazarotene) Topical Cream or Gel (Payer Form Unspecified)', 'topical form unspecified',
                'FDA labels: cream and gel are distinct topical formulations; the UHC listing does not specify which form is covered. Do not assume both are covered. Contraindicated during pregnancy. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.',
                '4e4e4b81-420e-4492-8a74-80b692a80057', True),
            'uhc-oct-complete-26eaf8d3998418d6': (
                'tezspire subcutaneous solution prefilled syringe', 'Tezspire (Tezepelumab-ekko) Subcutaneous Prefilled Syringe', 'subcutaneous prefilled syringe',
                'FDA label: 210 mg/1.91 mL single-dose prefilled syringe for healthcare provider administration; distinct from the prefilled pen. Exact UHC product-specific initial/renewal criteria are unverified; no quantity limit printed for this listing.',
                '60f0aa03-ad25-4d48-80ce-7fcfa76f325f', False),
            'uhc-oct-complete-e9644f76806d0c78': (
                'sutab', 'Sutab (Sodium Sulfate / Magnesium Sulfate / Potassium Chloride) Oral Tablet Kit', 'oral tablet',
                'FDA label: 1.479 g sodium sulfate / 0.225 g magnesium sulfate / 0.188 g potassium chloride per tablet; 24 tablets per bowel preparation kit. Distinct from Suprep oral solution. Follow label hydration instructions. Exact UHC product-specific initial/renewal criteria are unverified; no quantity limit printed for this listing.',
                'dddd2701-4d46-44de-a9f8-303d4dcceef7', False),
            'uhc-oct-complete-b452a2e1e260634a': (
                'synarel', 'Synarel (Nafarelin) Metered Nasal Spray', 'metered nasal spray',
                'FDA label: 200 mcg per actuation intranasal spray for central precocious puberty or endometriosis; distinct from injectable GnRH agonists. Exact UHC product-specific initial/renewal criteria are unverified; no quantity limit printed for this listing.',
                'd0aa57cb-d2f4-46d7-af43-7c8b06aa81a6', False),
            'uhc-oct-complete-ebc77e55ddd6f0c7': (
                'striverdi respimat', 'Striverdi Respimat (Olodaterol) Metered Inhalation Spray', 'metered inhalation spray',
                'FDA label: 2.5 mcg per actuation, 60-actuation cartridge for Respimat oral inhalation; COPD maintenance, not rescue treatment or asthma treatment. Not the olodaterol/tiotropium combination. GL-735259 is therapeutic duplication review, not named product initial/renewal criteria. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.',
                '5d9a5433-857e-44ea-b3d6-2a400ca0cef5', True),
            'uhc-oct-complete-22171578e784f52d': (
                'solosec', 'Solosec (Secnidazole) Oral Granules Packet', 'oral granules packet',
                'FDA label: 2 g secnidazole in one unit-dose packet for oral use only; do not dissolve in liquid. Contraindicated in Cockayne syndrome. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.',
                '056485b6-8bba-4a21-ae00-cdb4e7ae4bfa', True),
            'uhc-oct-complete-097bbd79f985a20c': (
                "siklos", "Siklos (Hydroxyurea) Scored Oral Tablet", "scored oral tablet",
                "FDA label: 100 mg tablets scored into halves and 1000 mg tablets scored into quarters; distinct from hydroxyurea capsules. Boxed warnings for myelosuppression and malignancies. Hydroxyurea can interfere with certain continuous glucose monitors. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "76957c0d-0f98-4376-bb06-eee651adc09d", True),
            'uhc-oct-complete-ecf070f7d966f3c0': (
                "simbrinza", "Simbrinza (Brinzolamide / Brimonidine Tartrate) Ophthalmic Suspension", "ophthalmic suspension",
                "FDA label: brinzolamide 1% / brimonidine tartrate 0.2% ophthalmic suspension, distinct from either single ingredient. Shake well before use; contraindicated in children under 2 years. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "a49c157e-6310-0011-7b7f-e26fc1820d59", True),
            'uhc-oct-complete-45bccbf7d28f0d2d': (
                "rasuvo", "Rasuvo (Methotrexate) Subcutaneous Autoinjector", "subcutaneous autoinjector",
                "FDA label: single-use 50 mg/mL subcutaneous autoinjectors, 7.5–30 mg in 2.5 mg increments. Once weekly, never daily; not for other routes. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "d0075461-0e7e-4967-9c9b-d6440e912c0e", True),
            'uhc-oct-complete-787fc9bd1b5d7710': (
                "rayaldee", "Rayaldee (Calcifediol) Extended-Release Oral Capsule", "extended-release oral capsule",
                "FDA label: 30 mcg extended-release capsule, distinct from calcitriol and cholecalciferol. Labeled for secondary hyperparathyroidism in adults with stage 3 or 4 CKD and serum 25-hydroxyvitamin D below 30 ng/mL; not indicated for stage 5 CKD or dialysis. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "6a95effd-32a5-46b6-a30e-7f4f9bf8cc77", True),
            'uhc-oct-complete-0d8138a620761a85': (
                "rezvoglar kwikpen", "Rezvoglar KwikPen (Insulin Glargine-aglr) Subcutaneous Prefilled Pen", "subcutaneous prefilled pen",
                "FDA label: 100 units/mL, 3 mL prefilled pen. Do not withdraw insulin from the pen into a syringe or use intravenously or in an insulin pump. Separate product identity; no payer substitution inference. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "f6af8706-2058-4fe1-99c8-43684c20bfa2", True),
            'uhc-oct-complete-92305bb0ac20fce9': (
                "edurant (brand for rilpivirine hcl)", "Edurant (Rilpivirine) Oral Tablet", "oral tablet",
                "FDA label: 25 mg film-coated tablet, taken with a meal; distinct from Edurant PED 2.5 mg tablets for oral suspension. These presentations are not substitutable mg-for-mg. No payer benefit extension to Edurant PED. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "03880372-2c68-45c6-a53a-f420c49541d6", True),
            'uhc-oct-complete-8bbcf6cc69fead95': (
                "rocklatan", "Rocklatan (Netarsudil / Latanoprost) Ophthalmic Solution", "ophthalmic solution",
                "FDA label: netarsudil 0.02% and latanoprost 0.005% ophthalmic solution, distinct from either single ingredient. Epithelial corneal edema has been reported. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "b1d71f41-be06-4a08-94d4-e352198f09c2", True),
            'uhc-oct-complete-94c48abf89211479': (
                "rhopressa", "Rhopressa (Netarsudil) Ophthalmic Solution", "ophthalmic solution",
                "FDA label: netarsudil 0.02% ophthalmic solution, distinct from netarsudil/latanoprost combination. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "7d4f0e3a-5b86-4c43-982a-813b22ae7e22", True),
            'uhc-oct-complete-e09ab8c74dc567df': (
                "qnasl", "QNASL (Beclomethasone Dipropionate) Metered Nasal Aerosol (Strength Unspecified)", "metered nasal aerosol",
                "FDA label: intranasal use only; 80 mcg/actuation for age 12 years and older, 40 mcg/actuation for age 4–11 years. The unqualified UHC listing does not print a strength; the separate Children's QNASL listing corresponds to the pediatric presentation. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "4b8d8e84-b5d2-4e56-97ec-4f72971465c5", True),
            'uhc-oct-complete-34c3d53b54b42268': (
                "qnasl childrens", "Children's QNASL (Beclomethasone Dipropionate) 40 mcg/Actuation Metered Nasal Aerosol", "metered nasal aerosol",
                "FDA label: pediatric 40 mcg/actuation nasal aerosol for ages 4–11 years; 60-actuation retail canister, distinct from the 80 mcg/actuation presentation. Intranasal use only; labeled age and package are not payer criteria. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "4b8d8e84-b5d2-4e56-97ec-4f72971465c5", True),
            'uhc-oct-complete-9e19c60da2981b4c': (
                "radicava ors starter kit", "Radicava ORS Starter Kit (Edaravone) Oral Suspension", "oral suspension starter kit",
                "FDA label: 105 mg/5 mL oral suspension, initial 14-day treatment kit with two 35 mL bottles (70 mL total), distinct from the 10-day continuation kit and IV infusion. The UHC Radicava ORS guideline GL-140940 (effective 12/01/2022, pp. 1402–1404) names Radicava ORS but does not specifically name the starter kit. Exact UHC product-specific initial/renewal criteria for the kit and numeric quantity limit are unverified.",
                "0ce2c1c4-2a40-485c-b7cb-96a9b85d9d11", True),
            'uhc-oct-complete-20d43250059212cb': (
                "plegridy starter pack subcutaneous solution prefilled syringe", "Plegridy Starter Pack (Peginterferon Beta-1a) Subcutaneous Prefilled Syringe Pack", "subcutaneous injection prefilled syringe pack",
                "FDA label: two SC prefilled syringes, 63 and 94 mcg per 0.5 mL, for titration; distinct from the SC pen starter pack, SC maintenance syringe and IM syringe with separate titration clips. UHC MS Agents guideline GL-722207 (effective 10/18/2026, pp. 1152–1154) names Plegridy, not the exact starter pack. Exact UHC product-specific initial/renewal criteria for the pack and numeric quantity limit are unverified.",
                "08f0ea03-4e6d-195d-aef4-886e32befa95", True),
            'uhc-oct-complete-73bdfcbd8ed83459': (
                "pred forte (brand for prednisolone acetate)", "Pred Forte (Prednisolone Acetate) Ophthalmic Suspension", "ophthalmic suspension",
                "FDA label: prednisolone acetate 1% suspension, not a phosphate solution or systemic preparation; shake before use. Monitor intraocular pressure with use for 10 days or longer; this is a label safety precaution, not a payer duration limit. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "00a5aa88-e361-4ea7-8922-530c738b726e", True),
            'uhc-oct-complete-4763deab6556b498': (
                "moviprep (brand for peg-3350/electrolytes/ascorbat)", "MoviPrep (PEG 3350 / Electrolytes / Ascorbate) Powder for Oral Solution", "powder for oral solution",
                "FDA label: mix pouch A and pouch B together with water to make each liter; kit supplies two liters of bowel preparation, not ready-to-drink solution. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "8ff46193-2a3b-4de0-9572-775dda8cd8b2", True),
            'uhc-oct-complete-0d5d9de3ba6af1f0': (
                "perforomist (brand for formoterol fumarate)", "Perforomist (Formoterol Fumarate) Nebulizer Solution", "inhalation solution",
                "FDA label: 20 mcg/2 mL unit-dose vial for jet nebulization, for COPD maintenance; not rescue treatment or an asthma indication. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "fb2fe258-fe2e-47f6-8adf-ca75bf6f90af", True),
            'uhc-oct-complete-7f3a07339d47bc24': (
                "pertzye oral capsule delayed release particles 16000- 57500 unit, 24000-86250 unit, 8000-28750 unit", "Pertzye (Pancrelipase) 8,000 / 16,000 / 24,000 Lipase Unit Delayed-Release Capsules", "delayed-release oral capsule",
                "FDA label: respective lipase/protease/amylase USP units 8000/28750/30250, 16000/57500/60500, 24000/86250/90750. Not the 4,000-unit capsule specified for gastrostomy tube administration. Do not substitute other pancreatic enzyme products without clinical reassessment. Exact UHC product-specific initial/renewal criteria are unverified; no QL printed on this listing.",
                "481eec00-9abf-11dd-b71c-0002a5d5c51b", False),
            'uhc-oct-complete-7fbd2d78a81af2c4': (
                "pertzye oral capsule delayed release particles 4000- 14375 unit", "Pertzye (Pancrelipase) 4,000 Lipase Unit Delayed-Release Capsule", "delayed-release oral capsule",
                "FDA label: 4000 lipase / 14375 protease / 15125 amylase USP units. Only the 4,000-unit capsule contents are labeled for gastrostomy tube administration (14 French or larger). Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "481eec00-9abf-11dd-b71c-0002a5d5c51b", True),
            'uhc-oct-complete-34f80389bb5991b1': (
                "omnaris", "Omnaris (Ciclesonide) Metered Nasal Spray", "nasal spray",
                "FDA label: 50 mcg per actuation aqueous nasal spray, distinct from orally inhaled ciclesonide. Labeled seasonal allergic rhinitis age 6 years or older and perennial age 12 years or older; these are not payer PA age criteria. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "15fefd46-ac7e-40d0-b635-e6c3d653c666", True),
            'uhc-oct-complete-414fa24b98ae95bf': (
                "ongentys", "Ongentys (Opicapone) Oral Capsule", "oral capsule",
                "FDA label: 25 and 50 mg capsules, adjunct to carbidopa/levodopa for OFF episodes. Use 25 mg in moderate hepatic impairment; avoid severe hepatic impairment. Nonselective MAO inhibitors are contraindicated. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "a511a531-112e-43f8-a43f-5334b0efe979", True),
            'uhc-oct-complete-27dba7fd41442c41': (
                "onpattro", "Onpattro (Patisiran) Lipid Complex Intravenous Infusion", "lipid complex injection",
                "FDA label: 10 mg/5 mL single-dose vial for IV infusion only after dilution; premedicate for infusion reactions. Labeled for adult hereditary transthyretin amyloidosis with polyneuropathy. Confirm pharmacy versus medical benefit routing; exact payer package is unverified. Exact UHC product-specific initial/renewal criteria are unverified.",
                "e87ec36f-b4b4-49d4-aea4-d4ffb09b0970", False),
            'uhc-oct-complete-91e168afff6eb5db': (
                "nuvessa", "Nuvessa (Metronidazole) 1.3% Vaginal Gel", "vaginal gel",
                "FDA label: single 5 g prefilled applicator containing 65 mg metronidazole; for intravaginal use only, distinct from 0.75% multidose vaginal gel and topical skin gel. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "3b6ff39d-f84b-43b3-9b07-c0521c6d7968", True),
            'uhc-oct-complete-f40ecc70e4799494': (
                "neupro", "Neupro (Rotigotine) Extended-Release Transdermal Patch", "extended-release transdermal patch",
                "FDA label: 1, 2, 3, 4, 6 and 8 mg/24 hours delivery strengths. Remove patch before MRI or cardioversion because of burn risk. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "939e28c5-f3a9-42c0-9a2d-8d471d82a6e0", True),
            'uhc-oct-complete-8ea52132ca0e6e33': (
                "nevanac", "Nevanac (Nepafenac) Ophthalmic Suspension", "ophthalmic suspension",
                "FDA label: 0.1% (1 mg/mL) ophthalmic suspension; shake well. Distinct from Ilevro 0.3% suspension. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "11b9a0cf-2a70-17ef-e063-6394a90a5d9e", True),
            'uhc-oct-complete-b3fc8d5441814c1f': (
                "nextstellis", "Nextstellis (Drospirenone / Estetrol) Oral Tablet Pack", "oral tablet pack",
                "FDA label: 24 active tablets containing 3 mg drospirenone and 14.2 mg estetrol (anhydrous basis), followed by 4 inert tablets; not drospirenone/ethinyl estradiol. Boxed warning for cigarette smoking and serious cardiovascular events. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "c5270073-d083-4109-ae4b-156986175e0a", True),
            'uhc-oct-complete-e8f1bcbf0e4fa7a5': (
                "vigamox (brand for moxifloxacin hcl)", "Vigamox (Moxifloxacin) Ophthalmic Solution", "ophthalmic solution",
                "FDA label: 0.5% (5 mg/mL) topical ophthalmic solution; not for systemic use or intraocular injection. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "12053b08-7e66-c6f3-e063-6394a90a9cd9", True),
            'uhc-oct-complete-9d0f4cda9a3a81e0': (
                "suprep bowel prep kit (brand for na sulfate-k sulfate-mg sulf)", "Suprep Bowel Prep Kit (Sodium / Potassium / Magnesium Sulfates) Oral Solution Concentrate", "oral solution concentrate",
                "FDA label: requires dilution; adult kit has two 6 oz bottles (17.5 g / 3.13 g / 1.6 g per bottle), and pediatric kit for age 12 years or older has two 4.5 oz bottles (13.13 g / 2.35 g / 1.2 g per bottle). UHC listing does not distinguish the kits. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "50f23abd-6a66-44cb-960e-d43c16a5ae5f", True),
            'uhc-oct-complete-140a0740fb8177a5': (
                "natazia", "Natazia (Estradiol Valerate / Dienogest) Multiphasic Oral Tablet Pack", "multiphasic oral tablet pack",
                "FDA label: 28-tablet sequence of differing active ingredients and strengths, followed by two inert tablets; not a single fixed-dose combination tablet. Boxed warning for smoking-related serious cardiovascular events in women over 35. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "02c91fba-9c47-43ef-ac78-e82369798834", True),
            'uhc-oct-complete-5084711389d55a87': (
                "mayzent starter pack", "Mayzent Starter Pack (Siponimod) Oral Tablet Titration Pack", "oral tablet titration pack",
                "FDA label: 0.25 mg tablets in separate 7-tablet (1 mg maintenance) and 12-tablet (2 mg maintenance) starter packs. CYP2C9 genotype determines the titration and maintenance regimen; CYP2C9*3/*3 is contraindicated. UHC listing does not distinguish the two starter packs. The UHC MS Agents guideline GL-722207 (effective 10/18/2026, pp. 1152–1154) names Mayzent, but does not explicitly identify either starter pack. Exact UHC product-specific initial/renewal criteria for the starter pack and numeric quantity limit are unverified.",
                "44492772-5aed-4627-bd85-e8e89f308bb3", True),
            'uhc-oct-complete-7ae59a9be90894fb': (
                "lialda (brand for mesalamine)", "Lialda (Mesalamine) Delayed-Release Oral Tablet", "delayed-release oral tablet",
                "FDA label: 1.2 g delayed-release oral tablet, not a mesalamine capsule, enema or suppository. Swallow whole; assess renal function before and during treatment. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "3098a080-be86-4265-9818-7fc4beab77b7", True),
            'uhc-oct-complete-3e5ea0bc90a6979f': (
                "lyumjev", "Lyumjev (Insulin Lispro-aabc) Injectable Solution (Device Unspecified)", "injectable solution",
                "FDA label: U-100 vial, KwikPen, Junior KwikPen, Tempo Pen and cartridge; U-200 KwikPen. This UHC listing does not identify a device or concentration. U-200 is subcutaneous only; never administer U-200 by pump or IV, or withdraw it from a pen into a syringe. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "c5a056e2-b568-4ca6-9ed8-79c010942d00", True),
            'uhc-oct-complete-686742f153d68e01': (
                "lyumjev kwikpen", "Lyumjev KwikPen (Insulin Lispro-aabc) Prefilled Pen (Concentration Unspecified)", "prefilled pen",
                "FDA label: separate U-100 and U-200 3 mL single-patient-use pens for subcutaneous injection. The UHC listing does not establish which concentration is covered. Never withdraw U-200 from the pen into a syringe; no U-200 pump or IV use. Junior KwikPen is a distinct U-100 half-unit device. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "c5a056e2-b568-4ca6-9ed8-79c010942d00", True),
            'uhc-oct-complete-6520d7a7c776b0eb': (
                "livalo (brand for pitavastatin calcium)", "Livalo (Pitavastatin Calcium) Oral Tablet", "oral tablet",
                "FDA label: 1, 2 and 4 mg pitavastatin equivalents; calcium salt, distinct from pitavastatin magnesium. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "44dcbf97-99ec-427c-ba50-207e0069d6d2", True),
            'uhc-oct-complete-b72a09032c056ced': (
                "lotemax sm", "Lotemax SM (Loteprednol Etabonate) Ophthalmic Gel", "ophthalmic gel",
                "FDA label: 0.38% (3.8 mg/g), distinct from Lotemax 0.5% formulations. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "6f9477b5-699f-4d3b-b9a6-0cc238266237", True),
            'uhc-oct-complete-5f08db26327b4d8e': (
                "lotemax (brand for loteprednol etabonate)", "Lotemax (Loteprednol Etabonate) Ophthalmic Form Unspecified", "ophthalmic form unspecified",
                "FDA labels identify 0.5% gel, suspension and ointment as separate presentations. The UHC listing does not specify the form; do not infer coverage for each presentation or for Lotemax SM. Linked label is the gel example. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "9a666065-d467-42b8-8ecd-0ec1de9986d5", True),
            'uhc-oct-complete-8b9d3977c36fecd2': (
                "zylet (brand for loteprednol-tobramycin)", "Zylet (Loteprednol Etabonate / Tobramycin) Ophthalmic Suspension", "ophthalmic suspension",
                "FDA label: loteprednol 0.5% / tobramycin 0.3%, combined steroid and antibacterial, not single-agent loteprednol. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "3dd9b060-5355-404d-bdf1-09ee8b52a9f5", True),
            'uhc-oct-complete-ddac5d138221ee70': (
                "istalol ophthalmic solution 0.5 % (brand for timolol maleate (once-daily))", "Istalol (Timolol Maleate) Once-Daily Ophthalmic Solution", "ophthalmic solution",
                "FDA label: 0.5%, once daily in the morning; distinguish other timolol presentations. Contraindicated in asthma, severe COPD, sinus bradycardia, second- or third-degree AV block, overt cardiac failure and cardiogenic shock. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "258bbc8d-00ee-45b0-ac35-6f16c4e8d45f", True),
            'uhc-oct-complete-d63c3b1ab823b361': (
                "lo loestrin fe", "Lo Loestrin Fe (Norethindrone Acetate / Ethinyl Estradiol / Ferrous Fumarate) Oral Tablet Pack", "oral tablet pack",
                "FDA label: 28-day pack with 24 combined tablets (1 mg norethindrone acetate / 10 mcg ethinyl estradiol), 2 ethinyl estradiol 10 mcg tablets and 2 nonhormonal ferrous fumarate tablets; not equivalent to Loestrin 24 Fe. Boxed warning: contraindicated in women over 35 who smoke. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "c33072cf-625d-4b4a-981e-ec049c5d78aa", True),
            'uhc-oct-complete-76eeafb86c6f7dd9': (
                "inveltys", "Inveltys (Loteprednol Etabonate) Ophthalmic Suspension", "ophthalmic suspension",
                "FDA label: 1% (10 mg/mL), for inflammation and pain after ocular surgery; distinct from lower-strength suspensions and gels. Shake before use; monitor intraocular pressure if used for 10 days or longer. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "2ec16df8-2e5c-4e06-8d28-21df76f27d72", True),
            'uhc-oct-complete-e9587576b936cf5e': (
                "eysuvis", "Eysuvis (Loteprednol Etabonate) Ophthalmic Suspension", "ophthalmic suspension",
                "FDA label: 0.25% (2.5 mg/mL), short-term dry eye treatment for up to 2 weeks; distinct from other loteprednol forms and concentrations. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "a2169d82-4275-4ab6-a1c3-c274080b815c", True),
            'uhc-oct-complete-1de36cc0a4b8fcd4': (
                "fiasp", "Fiasp (Insulin Aspart) Injectable Solution (Device Unspecified)", "injectable solution",
                "FDA label: 100 units/mL; vial, FlexTouch, PenFill and PumpCart are distinct presentations. The plain UHC listing does not establish a particular device; do not infer vial coverage. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "834e7efc-393f-4c55-9125-628562a8a5cf", True),
            'uhc-oct-complete-100bab6065fcfca3': (
                "fiasp flextouch", "Fiasp FlexTouch (Insulin Aspart) Prefilled Pen", "prefilled pen",
                "FDA label: 100 units/mL, 3 mL single-patient-use prefilled pen for subcutaneous injection; distinct from vial or cartridge. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "834e7efc-393f-4c55-9125-628562a8a5cf", True),
            'uhc-oct-complete-47e7ac4802b75ef8': (
                "fiasp penfill", "Fiasp PenFill (Insulin Aspart) Cartridge", "cartridge",
                "FDA label: 100 units/mL, 3 mL PenFill cartridge for compatible insulin delivery device, subcutaneous injection; distinct from 1.6 mL PumpCart and FlexTouch pen. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "834e7efc-393f-4c55-9125-628562a8a5cf", True),
            'uhc-oct-complete-e6a8af6fb0e528d0': (
                "finacea external foam", "Finacea (Azelaic Acid) Topical Foam", "topical foam",
                "FDA label: 15% aerosol foam for inflammatory papules and pustules of rosacea; distinct from gel. Flammable; topical use only. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "9fabd24e-4c3b-49a0-aa5f-c8d75ae67572", True),
            'uhc-oct-complete-04c2175bcaa7ee29': (
                "flarex", "Flarex (Fluorometholone Acetate) Ophthalmic Suspension", "ophthalmic suspension",
                "FDA label: 0.1% fluorometholone acetate; distinct from fluorometholone alcohol. Shake well; topical ophthalmic use only. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "f060dec4-09dc-4266-ab4c-a6ed49cd8126", True),
            'uhc-oct-complete-44ba8a15828b42b8': (
                "symfi (brand for efavirenz-lamivudine-tenofovir)", "Symfi (Efavirenz / Lamivudine / Tenofovir Disoproxil Fumarate) Oral Tablet", "oral tablet",
                "FDA label: 600/300/300 mg; distinct from Symfi Lo 400/300/300 mg. Fixed-dose combination not recommended for CrCl below 50 mL/min. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "81a55dd9-78a8-49c3-88ab-8f5bffafa359", True),
            'uhc-oct-complete-e48614a8896d1c42': (
                "elyxyb", "Elyxyb (Celecoxib) Oral Solution", "oral solution",
                "FDA label: 25 mg/mL (120 mg/4.8 mL) for acute migraine in adults, not prevention. Boxed cardiovascular and gastrointestinal warnings. UHC therapeutic duplication review is administrative. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "c8a5de07-9f27-4a54-a885-8089f0307bd7", True),
            'uhc-oct-complete-3c48b4c2b5592695': (
                "emend oral", "Emend (Aprepitant) Oral Capsule / Powder for Oral Suspension (Form Unspecified)", "oral capsule or powder for oral suspension",
                "FDA label: Capsules (40/80/125 mg) and powder for oral suspension (125 mg) are distinct. CINV labeled ages differ: capsules 12 years and older, suspension 6 months and older. The UHC listing does not identify the oral formulation; do not transfer benefits to a specific child or to IV. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "696f9e80-9cae-403b-de9e-078343ce4713", True),
            'uhc-oct-complete-42d6b65788f7e18f': (
                "truvada (brand for emtricitabine-tenofovir df)", "Truvada (Emtricitabine / Tenofovir Disoproxil Fumarate) Oral Tablet", "oral tablet",
                "FDA label: Four labeled strengths (100/150, 133/200, 167/250, 200/300 mg); distinct from tenofovir alafenamide combinations. PrEP requires confirmed HIV-negative status; boxed HBV discontinuation warning. PDL does not identify a strength-level benefit. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "46e06df0-654d-43cc-e054-00144ff8d46c", True),
            'uhc-oct-complete-91cfa1e69148c0ca': (
                "emverm", "Emverm (Mebendazole) Chewable Tablet", "chewable tablet",
                "FDA label: 100 mg chewable tablet for indicated helminth infections in patients 2 years and older. Avoid concomitant metronidazole due to serious skin reaction risk (SJS/TEN). Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "a8c46363-f739-4f6e-bca8-1ce5e8d3f78d", True),
            'uhc-oct-complete-93cb1d792516d6af': (
                "enstilar", "Enstilar (Calcipotriene / Betamethasone Dipropionate) Topical Foam", "topical foam",
                "FDA label: 0.005%/0.064% aerosol foam, distinct from ointment or suspension; flammable. Labeled maximum 60 g every 4 days is a clinical limit, not a payer quantity limit. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "d1193df2-d53f-4342-bd9d-d9cba7c89709", True),
            'uhc-oct-complete-8f02f89ad4d636c6': (
                "beyaz (brand for drospiren-eth estrad-levomefol)", "Beyaz (Drospirenone / Ethinyl Estradiol / Levomefolate) Oral Tablet Pack", "oral tablet pack",
                "FDA label: 24 hormone-containing tablets (3/0.02/0.451 mg) and 4 folate-only tablets (0.451 mg). Distinct from Safyral 21/7 pack. Contraindicated with renal impairment, adrenal insufficiency and specified thrombotic risks. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "8132454a-6135-4bac-b206-83a55eb8dbc6", True),
            'uhc-oct-complete-f142ec3c46691c32': (
                "safyral (brand for drospiren-eth estrad-levomefol)", "Safyral (Drospirenone / Ethinyl Estradiol / Levomefolate) Oral Tablet Pack", "oral tablet pack",
                "FDA label: 21 hormone-containing tablets (3/0.03/0.451 mg) and 7 folate-only tablets (0.451 mg). Distinct from Beyaz 24/4 pack. Contraindicated with renal impairment, adrenal insufficiency and specified thrombotic risks. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "97563516-306a-4e17-9690-edbda49ecd83", True),
            'uhc-oct-complete-4174a6295393bf8f': (
                "duaklir pressair", "Duaklir Pressair (Aclidinium / Formoterol) Dry Powder Inhaler", "dry powder inhaler",
                "FDA label: 400/12 mcg per metered actuation; COPD maintenance, not rescue or asthma. Do not combine with another LABA. UHC therapeutic duplication review is administrative; exact package eligibility is unverified. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "2eba3089-28b4-4190-9fba-2511246cfd16", True),
            'uhc-oct-complete-36fd5377645d6fba': (
                "edarbyclor", "Edarbyclor (Azilsartan Medoxomil / Chlorthalidone) Oral Tablet", "oral tablet",
                "FDA label: 40/12.5 mg or 40/25 mg combination tablets, distinct from single-agent Edarbi. Boxed fetal toxicity warning; contraindicated in anuria. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "e60f795b-fce3-4361-aa03-f143451689d1", True),
            'uhc-oct-complete-1d35bfcfe764c083': (
                "cycloset", "Cycloset (Bromocriptine) Oral Tablet", "oral tablet",
                "FDA label: 0.8 mg tablet for glycemic control in type 2 diabetes; taken within 2 hours of waking with food. Distinct from other bromocriptine products. Exact UHC product-specific initial/renewal criteria are unverified.",
                "e42ba916-16b9-4d1c-8d09-9d2fbb1b6c20", False),
            'uhc-oct-complete-8eaaa9a428e51bfe': (
                "diazepam rectal gel 2.5 mg", "Diazepam 2.5 mg Rectal Gel", "rectal gel",
                "FDA label: fixed 2.5 mg dose in 0.5 mL; distinct from the 10 mg and 20 mg adjustable syringes. Oral diazepam anxiolytic criteria are not verified for this rectal product. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "b5b17a28-2cab-4c0d-8f9d-7b224e4d0989", True),
            'uhc-oct-complete-92cd6d282b2fdba2': (
                "dipentum", "Dipentum (Olsalazine Sodium) Oral Capsule", "oral capsule",
                "FDA label: 250 mg capsule, distinct from other aminosalicylates. Renal monitoring; contraindicated with salicylate or aminosalicylate hypersensitivity. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "8512d0c6-db4e-4673-b3b4-28975c18413f", True),
            'uhc-oct-complete-d6a9c6a4da764191': (
                "norpace (brand for disopyramide phosphate)", "Norpace (Disopyramide Phosphate) Immediate-Release Oral Capsule", "oral capsule",
                "FDA label: 100 mg or 150 mg immediate-release capsule, distinct from 12-hour Norpace CR. Proarrhythmic risk; hospital initiation. Brand listing does not establish coverage of authorized generic or CR. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "e2aa1642-d262-4520-bc6a-9fd3ad795677", True),
            'uhc-oct-complete-f99f6e23bf651e34': (
                "cosopt (brand for dorzolamide hcl-timolol mal)", "Cosopt (Dorzolamide / Timolol) Ophthalmic Solution", "ophthalmic solution",
                "FDA label: 2% / 0.5% preserved multidose ophthalmic solution, distinct from single-dose Cosopt PF. Contraindicated with asthma or severe COPD and specified cardiac conditions. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.",
                "23bdf1c1-3134-4ad1-8e7c-bc655156bdc6", True),
            'uhc-oct-complete-4ffe1eab1f90ef46': (
                "cosopt pf (brand for dorzolamide hcl-timolol mal pf)", "Cosopt PF (Dorzolamide / Timolol) Preservative-Free Ophthalmic Solution", "ophthalmic solution",
                "FDA label: 2% / 0.5% preservative-free single-dose 0.2 mL container; discard after use. Distinct from preserved multidose Cosopt. Do not transfer the other listing's QL. Exact UHC product-specific initial/renewal criteria are unverified.",
                "535fc801-8c3f-4974-a120-3eff1d5a5062", False),
            'uhc-oct-complete-013b59b93699a5c4': (
                'onexton (brand for clindamycin phos-benzoyl perox)', 'Onexton (Clindamycin Phosphate / Benzoyl Peroxide) Topical Gel', 'topical gel',
                'FDA label: 1.2% clindamycin phosphate / 3.75% benzoyl peroxide gel for topical use, not oral, ophthalmic or intravaginal. Contraindicated with history of regional enteritis, ulcerative colitis or antibiotic-associated colitis. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.',
                '697e760a-c206-4565-8f4e-a8085e215827', True),
            'uhc-oct-complete-add6e7e9261e4c8f': (
                'clindesse', 'Clindesse (Clindamycin Phosphate) Vaginal Cream', 'vaginal cream',
                'FDA label: 2% cream, single 5 g prefilled vaginal applicator; not a multidose regimen or topical skin product. Avoid latex or rubber barrier contraceptives during treatment and for 5 days afterward. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.',
                'fe8bb204-f173-44fe-803b-b08f2ec5aa31', True),
            'uhc-oct-complete-8e1f189a8596a674': (
                'combipatch', 'CombiPatch (Estradiol / Norethindrone Acetate) Twice-Weekly Transdermal Patch', 'transdermal patch',
                'FDA label: estradiol 0.05 mg/day with norethindrone acetate 0.14 or 0.25 mg/day; twice-weekly system, not weekly Climara Pro. Payer listing does not distinguish strengths. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.',
                '83198ef1-11c4-11e4-9191-0800200c9a66', True),
            'uhc-oct-complete-b9ec5dd97103ff2a': (
                'nascobal (brand for cyanocobalamin)', 'Nascobal (Cyanocobalamin) Nasal Spray', 'nasal spray',
                'FDA label: 500 mcg single-use nasal spray, not oral or injectable cyanocobalamin. Defer during nasal congestion, allergic rhinitis or upper respiratory infection until symptoms subside. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.',
                '697e0e52-c01b-4b53-9994-f79c46eb6b4f', True),
            'uhc-oct-complete-8b9ddaaef849c561': (
                'crysvita subcutaneous solution 20 mg/ml', 'Crysvita (Burosumab-twza) 20 mg/mL Subcutaneous Solution', 'subcutaneous injection solution',
                'FDA label: single-dose 1 mL vial, healthcare provider administration only. Contraindicated with oral phosphate or active vitamin D analogs, normal/high age-adjusted phosphorus, or severe renal impairment/ESRD. Medical-benefit policy applicability to this pharmacy listing is unverified. Exact UHC product-specific initial/renewal criteria are unverified.',
                '102f96a0-6e3a-4fc1-b204-34d604683af6', False),
            'uhc-oct-complete-8ac95e39cc071af9': (
                'cimduo', 'Cimduo (Lamivudine / Tenofovir Disoproxil Fumarate) Oral Tablet', 'oral tablet',
                'FDA label: fixed 300 mg/300 mg tablet; not tenofovir alafenamide. Not recommended with CrCl below 50 mL/min or ESRD requiring hemodialysis. Boxed warning for HBV exacerbation after discontinuation. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.',
                'a300f04d-118f-4136-aaf3-ddfd00197f86', True),
            'uhc-oct-complete-3ce934e09340ac9a': (
                'clenpiq', 'Clenpiq (Sodium Picosulfate / Magnesium Oxide / Citric Acid) Oral Solution', 'oral solution',
                'FDA label: ready-to-drink 175 mL solution, not a powder for reconstitution. Contraindicated with CrCl below 30 mL/min or bowel obstruction, ileus, perforation, toxic colitis/megacolon or gastric retention. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.',
                'e95fff66-4ec0-4001-a727-33e66a5ec7d5', True),
            'uhc-oct-complete-65b8740769a16e55': (
                'climara pro', 'Climara Pro (Estradiol / Levonorgestrel) Weekly Transdermal Patch', 'transdermal patch',
                'FDA label: 0.045 mg estradiol and 0.015 mg levonorgestrel per day; weekly system, not estradiol-only Climara or twice-weekly CombiPatch. Exact UHC product-specific initial/renewal criteria are unverified.',
                '184d3092-7fc6-4375-816b-1ab06bb99cfd', False),
            'uhc-oct-complete-ea99523e63092e14': (
                'sorilux (brand for calcipotriene)', 'Sorilux (Calcipotriene) Topical Foam', 'topical foam',
                'FDA label: 0.005% foam for skin/scalp; avoid flame during and immediately after use. Contraindicated in known hypercalcemia. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.',
                '51f208d0-7b3f-44cc-8bed-92fa3d2e7bbe', True),
            'uhc-oct-complete-2e1dfaa167d25964': (
                'taclonex (brand for calcipotriene-betameth diprop)', 'Taclonex (Calcipotriene / Betamethasone Dipropionate) Topical Form Unspecified', 'topical form unspecified',
                'UHC does not identify ointment versus topical suspension. These are distinct formulations; do not transfer formulation-specific treatment duration or payer benefits between them. FDA suspension label linked. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.',
                '757c914f-dd8d-43cc-a973-212d591af4af', True),
            'uhc-oct-complete-604fed6ff3bba12e': (
                'dhivy (brand for carbidopa-levodopa)', 'Dhivy (Carbidopa / Levodopa) Functionally Scored Oral Tablet', 'oral tablet',
                'FDA label: 25 mg/100 mg tablet with three functional scores; each quarter contains 6.25 mg/25 mg. Do not assume other tablets support equivalent quarter dosing. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.',
                '39d79ade-8ee0-40ba-9fdd-13045b8ddbdf', True),
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
            allowed_administrative = {'GL-735259'} if record['id'] in {'uhc-oct-complete-4174a6295393bf8f', 'uhc-oct-complete-e48614a8896d1c42', 'uhc-oct-complete-0d5d9de3ba6af1f0', 'uhc-oct-complete-0d8138a620761a85', 'uhc-oct-complete-ebc77e55ddd6f0c7'} else set()
            if record['id'] == 'uhc-oct-complete-26eaf8d3998418d6':
                allowed_administrative.add('GL-733328')
            assert not (set(matched) - allowed_administrative), ('Review newly available named criteria before use', record['id'], matched)
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': label, 'dosageForm': form, 'note': note,
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=' + label_id,
            }
        # DEC-05/12/13/14/19/20: preferred listing identity only; preserve original PA trigger.
        preferred_label_holds = {
            'uhc-oct-complete-8ea2e18a291f48b7': ("vancomycin hcl oral solution reconstituted 25 mg/ml (generic for firvanq)", "Vancomycin Hydrochloride 25 mg/mL Powder for Oral Solution (Generic for Firvanq)", "powder for oral solution", "FDA label: 25 mg/mL after reconstitution, for oral use only, distinct from IV vancomycin. GL-545275 is general nonsolid review, not named product criteria. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.", "4c3d2e99-5351-4442-916a-d2001b0a5f5a", "required"),
            'uhc-oct-complete-45d4feeaedf3552e': ("voriconazole oral tablet", "Voriconazole Oral Tablet", "oral tablet", "FDA label: 50 and 200 mg tablets, distinct from IV and oral suspension; review drug interactions. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.", "796cad15-2aef-4823-917d-17b822a6916e", "required"),
            'uhc-oct-complete-90702ce4eec9617a': ('topiramate oral capsule sprinkle 15 mg, 25 mg (generic for topamax sprinkle)', 'Topiramate 15 or 25 mg Oral Sprinkle Capsule', 'oral sprinkle capsule', 'FDA label: 15 and 25 mg immediate-release sprinkle capsules, distinct from the 50 mg sprinkle and extended-release products. UHC conditional PA applies at age 8 or older, not a labeled indication age. GL-572198 names 50 mg sprinkle and ER products, not this option. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.', '872927eb-0b61-44bb-9892-3c700b6f2181', 'conditional'),
            'uhc-oct-complete-0f013ce4207021c3': ("reyataz oral packet", "Reyataz (Atazanavir) Oral Powder Packet", "oral powder packet", "FDA label: 50 mg oral powder packet, not a capsule; take with food and ritonavir. Switching formulations may require dose adjustment. UHC PDL conditional PA applies at age 8 or older; this is a payer trigger, not a labeled indication age. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.", "165cff62-b284-4a27-a65d-9ec8a5bfcdd8", "conditional"),
            'uhc-oct-complete-c52599e942ff4716': ("lamotrigine oral tablet chewable (generic for lamictal)", "Lamotrigine Chewable / Dispersible Tablet for Oral Suspension", "tablet for oral suspension", "FDA label: 5 and 25 mg chewable/dispersible tablets, distinct from ODT and ER. Boxed warning for serious rash. UHC PDL conditional PA applies at age 8 or older; this is a payer trigger, not a labeled indication age. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.", "ae6522d4-d824-44aa-afe0-70cdcbd845af", "conditional"),
            'uhc-oct-complete-2350c3053e5d6856': ("lidocaine external ointment 5 %", "Lidocaine 5% Topical Ointment", "topical ointment", "FDA label: 50 mg/g topical ointment, not a patch or injection. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.", "071b2cfd-07ad-46a3-8808-87080d545fd3", "required"),
            'uhc-oct-complete-877751e558a7560e': ("lokelma", "Lokelma (Sodium Zirconium Cyclosilicate) Powder for Oral Suspension", "powder for oral suspension", "FDA label: 5 and 10 g packets; generally separate other oral medications by 2 hours. Exact UHC product-specific initial/renewal criteria and numeric quantity limit are unverified.", "90bf8e28-748d-4e4b-a19f-9cf483370eff", "required"),
        }
        if record['id'] in preferred_label_holds:
            expected, label, form, note, label_id, pa = preferred_label_holds[record['id']]
            assert october_name == expected and record['pa'] == pa
            assert record['preferred'] == 'preferred' and ql
            assert not matched, ('Review newly available named criteria before use', record['id'], matched)
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': label, 'dosageForm': form, 'note': note,
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=' + label_id,
            }
        # DEC-05/06/12/13/14/19/20: preserve distinct octreotide concentrations and depot route.
        # GL-140960 names generic octreotide, but not individual concentration or depot packages.
        # Preserve existing policy bindings; do not extend them or medical-benefit eligibility.
        octreotide_presentations = {
            'uhc-oct-complete-f02ebb3ed15163c2': (
                'octreotide acetate injection solution 1000 mcg/ml',
                'Octreotide Acetate 1000 mcg/mL Non-Depot Injection Solution',
                'injection solution', 'FDA label example: 1000 mcg/mL in a 5 mL multidose vial for subcutaneous or intravenous use; distinct from depot IM suspension. Exact payer package and numeric quantity limit are unverified.',
                'ffaf9462-cdd8-433b-8b03-464a35577fe9', True),
            'uhc-oct-complete-2365e48035c832b5': (
                'octreotide acetate injection solution 200 mcg/ml',
                'Octreotide Acetate 200 mcg/mL Non-Depot Injection Solution',
                'injection solution', 'FDA label example: 200 mcg/mL in a 5 mL multidose vial for subcutaneous or intravenous use; distinct from 1000 mcg/mL and depot IM suspension. Exact payer package is unverified; QL not specified.',
                'ffaf9462-cdd8-433b-8b03-464a35577fe9', False),
            'uhc-oct-complete-f655e03418b3c0dd': (
                'octreotide acetate injection solution 500 mcg/ml (generic for sandostatin)',
                'Octreotide Acetate 500 mcg/mL Non-Depot Injection Solution',
                'injection solution', 'FDA label example: 500 mcg/mL single-dose 1 mL vial; distinct from the 200/1000 mcg/mL multidose presentations and depot IM suspension. Exact payer package and numeric quantity limit are unverified.',
                'f278f0d8-4062-420a-97c3-3a8b88253a08', True),
            'uhc-oct-complete-8b2ff71efd223fc7': (
                'octreotide acetate intramuscular (generic for sandostatin lar depot)',
                'Octreotide Acetate Depot Intramuscular Injectable Suspension',
                'powder for injectable suspension', 'FDA label example: 10, 20 and 30 mg kits for gluteal intramuscular administration, not non-depot subcutaneous or intravenous solution. Exact payer kit and medical benefit applicability are unverified; QL not specified.',
                'd9739ea6-74de-4a41-a806-6e827a23cedb', False),
            'uhc-oct-complete-cd9f5afab9cb36c4': (
                'octreotide acetate subcutaneous solution prefilled syringe 100 mcg/ml, 50 mcg/ml',
                'Octreotide Acetate 50 or 100 mcg/mL Subcutaneous Prefilled Syringe',
                'subcutaneous solution prefilled syringe', 'FDA label example: 50 or 100 mcg/mL in separate 1 mL single-dose prefilled syringes; not a vial, pen or depot suspension. Exact payer package is unverified; QL not specified.',
                '2d78d5d1-77b2-4da1-98d4-d9c36e743ce2', False),
            'uhc-oct-complete-1e81e13b95303948': (
                'octreotide acetate subcutaneous solution prefilled syringe 500 mcg/ml',
                'Octreotide Acetate 500 mcg/mL Subcutaneous Prefilled Syringe',
                'subcutaneous solution prefilled syringe', 'FDA label example: 500 mcg/mL in a 1 mL single-dose prefilled syringe; not a vial, pen or depot suspension. Exact payer package and numeric quantity limit are unverified.',
                '2d78d5d1-77b2-4da1-98d4-d9c36e743ce2', True),
        }
        if record['id'] in octreotide_presentations:
            expected, label, form, note, label_id, has_ql = octreotide_presentations[record['id']]
            assert october_name == expected and record['pa'] == 'required'
            assert record['preferred'] == 'preferred' and ql == has_ql
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': label, 'dosageForm': form,
                'note': note + ' UHC GL-140960 names generic octreotide but does not specify this concentration, device or depot package. Exact prescribing-option criteria remain unverified. Mycapssa-specific initiation criteria are separate.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=' + label_id,
            }
        # DEC-05/12/13/14/19/20: distinguish the packet from other raltegravir forms.
        if record['id'] == 'uhc-oct-complete-9fcb07846f5d9ec6':
            assert october_name == 'isentress oral packet'
            assert record['pa'] == 'conditional' and record['preferred'] == 'preferred' and ql
            assert not matched, ('Review new named policy', record['id'], matched)
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Isentress (Raltegravir) Granules for Oral Suspension',
                'dosageForm': 'granules for oral suspension',
                'note': 'FDA label: 100 mg single-use packet for oral suspension. Do not substitute the packet for the film-coated tablet on a milligram-for-milligram basis; the formulations are not bioequivalent. UHC PDL requires PA for members aged 2 years or older for the oral packet; exact product-specific criteria and numeric quantity limit are unverified.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=89a5ec53-d956-4329-8004-0f40f51c88a3',
            }
        # DEC-05/12/13/14/19/20: exact preferred sprinkle capsule; retain conditional age rule.
        if record['id'] == 'uhc-oct-complete-f24f86de993ce49c':
            assert october_name == 'divalproex sodium oral capsule delayed release sprinkle (generic for depakote sprinkles)'
            assert record['pa'] == 'conditional' and record['preferred'] == 'preferred' and ql
            assert not matched, ('Review new named policy', record['id'], matched)
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Divalproex Sodium Delayed-Release Sprinkle Oral Capsule',
                'dosageForm': 'delayed-release sprinkle capsule',
                'note': 'FDA label: 125 mg delayed-release sprinkle capsule; swallow whole or sprinkle contents on soft food without chewing. Not delayed-release tablets or extended-release tablets. Boxed warnings include hepatotoxicity, fetal risk and pancreatitis. UHC PDL requires PA for members aged 8 years or older; exact product-specific criteria and numeric quantity limit are unverified.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=699a9722-27bd-4e90-819b-d4ecb99466c8',
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
        # DEC-05/12/13/14/19/20: exact preferred oral suspension; preserve conditional PA and administrative references.
        if record['id'] == 'uhc-oct-complete-25343462b850be92':
            assert october_name == 'felbamate oral suspension'
            assert record['pa'] == 'conditional' and record['preferred'] == 'preferred' and ql
            assert not matched, ('Review new named policy', record['id'], matched)
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Felbamate Oral Suspension',
                'dosageForm': 'oral suspension',
                'note': 'FDA label: 600 mg/5 mL oral suspension; boxed warnings for aplastic anemia and hepatic failure. UHC PDL requires PA for members aged 8 years or older; general nonsolid criteria are not named product-specific criteria. Exact product-specific criteria and numeric quantity limit remain unverified.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=0afffb17-e6ac-4bea-a90e-7ef3c8150290',
            }
        # DEC-05/12/13/14/19/20: preserve age-conditioned PDL rule and general nonsolid criteria.
        if record['id'] == 'uhc-oct-complete-e29a433265e8ba09':
            assert october_name == 'calcitriol oral solution'
            assert record['pa'] == 'conditional' and record['preferred'] == 'preferred' and not ql
            assert not matched, ('Review new named policy', record['id'], matched)
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Calcitriol Oral Solution',
                'dosageForm': 'oral solution',
                'note': 'FDA label: 1 mcg/mL oral solution, not injectable calcitriol or topical calcitriol. UHC PDL requires PA for members aged 8 years or older; general nonsolid criteria are not named product-specific initial/renewal criteria. Exact product-specific criteria remain unverified.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=bdb9c0d4-bdb3-4174-a4d9-55c423f38476',
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
        # DEC-05/12/13/14/19/20: fixed 300 mg SC UnoReady, not every Cosentyx SC dose.
        # Preserve original source branches and label mixed populations explicitly.
        if record['id'] == 'uhc-oct-complete-9449c2ad49f55210':
            assert october_name == 'cosentyx unoready'
            assert record['pa'] == 'required' and record['preferred'] == 'non_preferred' and ql
            code = 'GL-628292'
            assert policies[code]['policyEffective'] == '2026-07-01'
            branches = structured[code]['branches']
            assert len(branches) == 9
            for i, (dx, stage) in enumerate([
                ('Plaque Psoriasis (PsO)', 'Initial Authorization'),
                ('Hidradenitis Suppurativa (HS)', 'Initial Authorization'),
                ('Plaque Psoriasis (PsO), Hidradenitis Suppurativa (HS)', 'Reauthorization'),
                ('Enthesitis-Related Arthritis (ERA)', 'Initial Authorization'),
                ('Enthesitis-Related Arthritis (ERA)', 'Reauthorization'),
                ('Psoriatic Arthritis (PsA)', 'Initial Authorization'),
                ('Psoriatic Arthritis (PsA)', 'Reauthorization'),
                ('Ankylosing Spondylitis (AS), Non-Radiographic Axial Spondyloarthritis (nr-axSpA)', 'Initial Authorization'),
                ('Ankylosing Spondylitis (AS), Non-Radiographic Axial Spondyloarthritis (nr-axSpA)', 'Reauthorization'),
            ]):
                fields = branches[i]['fields']
                assert fields['Product Name']['text'] == 'Cosentyx SC'
                assert ' '.join(fields['Diagnosis']['text'].split()) == dx
                # Page 412 running header interrupts the AS initial stage; use
                # the already furniture-cleaned display span, not raw source text.
                stage_field = fields['Therapy Stage']
                assert stage_field.get('displayText', stage_field['text']) == stage
                assert fields['Guideline Type']['text'] == 'Prior Authorization'
            assert set(matched).issubset({code}), ('Review other named policy', matched)
            matched.pop(code, None)
            add(code, [0, 1, 2, 5, 6, 7, 8], 'product')
            bindings[-1]['branchLabels'] = {
                '0': 'UnoReady 300 mg only: adult plaque psoriasis; pediatric doses are lower',
                '1': 'UnoReady 300 mg only: adult HS or pediatric HS weighing at least 90 kg',
                '2': 'UnoReady 300 mg only: adult plaque psoriasis or eligible 300 mg HS regimen',
                '5': 'UnoReady 300 mg only: adult PsA with a labeled 300 mg regimen',
                '6': 'UnoReady 300 mg only: adult PsA with a labeled 300 mg regimen',
                '7': 'UnoReady 300 mg only: adult AS escalation; NOT the nr-axSpA or pediatric AS regimen',
                '8': 'UnoReady 300 mg only: adult AS escalation; NOT the nr-axSpA or pediatric AS regimen',
            }
            record['reviewedPresentation'] = {
                **record.get('reviewedPresentation', {}), 'separate': True,
                'label': 'Cosentyx UnoReady (Secukinumab) 300 mg/2 mL Subcutaneous Pen',
                'dosageForm': 'subcutaneous autoinjector',
                'note': 'FDA label: fixed single-dose 300 mg pen; not for 75 mg or 150 mg doses or IV infusion. The UHC Cosentyx SC guideline is not pen-specific. Apply criteria only to a labeled 300 mg regimen: adult plaque psoriasis, qualifying adult PsA or AS, adult HS or pediatric HS weighing at least 90 kg. Do not apply the nr-axSpA, ERA or lower-dose pediatric branches to this pen. Exact payer device-specific approval criteria and numeric quantity limit are unverified.',
                'labelUrl': 'https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=77c4b13e-7df3-42d4-81db-3d0cddb7f67a',
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

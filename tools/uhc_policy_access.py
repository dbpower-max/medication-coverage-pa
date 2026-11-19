"""Expose existing exact UHC policy branches; never infer PA/coverage status."""
import hashlib
import json
import re
from collections import defaultdict
from structured_statewide_criteria import structure_policy, validate_structure

PLAN = 'uhc-community-az'
# Reviewed October PDL names mapped to the November 2026 named-product branches.
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
        'Generic pantoprazole packets', 'generic pantoprazole suspension packets',
    ),
    'protonix oral packet (brand for pantoprazole sodium)': (
        'Brand Protonix packets', 'Brand Protonix suspension packets',
    ),
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
            validate_structure(result,source)
        else:result = structure_policy(policy, source)
        # Repeated PDF running headers are furniture, never a clinical requirement.
        for b in result['branches']:
            for f in list(b['fields'].values()) + b['criteria'] + b['notes']:
                display = re.sub(r'UnitedHealthcare Community Plan of Arizona [–-] Clinical Pharmacy Guidelines\s*', '', f.get('displayText',f['text']))
                if display != f['text']: f['displayText'] = display.strip()
        if code == 'GL-735259':
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
        for code,indexes in sorted(matched.items()):
            if code == 'GL-735259':
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

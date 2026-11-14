"""Banner GLP-1 pilot: versioned common criteria and explicit product branches."""
from copy import deepcopy

POLICY_ID = 'banner-glp1-GL-715192'
GUIDES = ['banner-guide-glp-preferred', 'banner-guide-glp-nonpreferred-injection', 'banner-guide-glp-oral']

def attach_shared_policy(data):
    policies = {p['id']: p for p in data['policies']}
    guides = [policies[k] for k in GUIDES]
    common = guides[0]['guide']['requirements'][:3]
    assert all(g['guide']['requirements'][:3] == common for g in guides)
    shared = {
        'id': POLICY_ID, 'planId': 'banner-ufc', 'policyCode': 'GL-715192',
        'version': '2026-10-01', 'effective': '2026-10-01',
        'sourceSnapshot': '2026-11-01', 'indication': 'Type 2 diabetes',
        'guide': dict(requirements=deepcopy(common)),
        'branches': {},
    }
    for g in guides:
        branch = deepcopy(g['guide'])
        branch['requirements'] = branch['requirements'][3:]
        shared['branches'][g['id']] = branch
        g['sharedPolicyRef'] = dict(policyId=POLICY_ID, version=shared['version'], branchId=g['id'])
        g['policyEffective'] = shared['effective']
        del g['guide']
    data['sharedPolicies'] = [shared]
    for med in data['medications']:
        refs = [policies[k]['sharedPolicyRef'] for k in med.get('approvalGuideIds', []) if k in GUIDES]
        if refs:
            assert med['planId'] == shared['planId']
            med['paPolicyAssignments'] = deepcopy(refs)
    validate_shared_policy(data)

def resolve(data, med):
    result = []
    for ref in med.get('paPolicyAssignments', []):
        policy = next(p for p in data['sharedPolicies'] if p['id'] == ref['policyId'])
        assert med['planId'] == policy['planId'], 'Wrong-plan policy assignment'
        assert ref['version'] == policy['version'], 'Policy version mismatch'
        branch = deepcopy(policy['branches'][ref['branchId']])
        branch['requirements'] = policy['guide']['requirements'] + branch['requirements']
        result.append(branch)
    return result

def validate_shared_policy(data):
    for med in data['medications']:
        resolve(data, med)

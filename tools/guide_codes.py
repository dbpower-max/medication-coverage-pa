"""Read explicit guide flags without treating prose inside AI(...) as flags."""
import re
CODES={'PA','ST','QL','AL','AG','SP','H-PA','E'}
def guide_codes(plan_id,raw):
 if plan_id=='uhc-commercial-reference':return set(re.split(r'[,\s]+',raw)) & CODES
 result=set(re.findall(r'(?:^|;\s*)(PA|ST|QL|AL|AG|SP|H-PA|E)(?=\s|;|$|\()',raw))
 if re.search(r'(?:^|;\s*)Smart PA(?=;|$)',raw):result.add('PA')
 return result

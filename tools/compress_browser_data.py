"""Keep full source JSON in the repository; deploy gzip datasets with identical bytes."""
import json,gzip,shutil,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];d=json.loads((ROOT/'dist/data.json').read_text());archive=ROOT/'data/browser-json';archive.mkdir(exist_ok=True)
for pid,path in list(d['planDataFiles'].items()):
 if path.endswith('.gz'):continue
 src=ROOT/'dist'/path.removeprefix('./');saved=archive/src.name;shutil.copy2(src,saved)
 dest=Path(str(src)+'.gz')
 with src.open('rb') as f,gzip.open(dest,'wb',compresslevel=9) as g:shutil.copyfileobj(f,g)
 assert gzip.decompress(dest.read_bytes())==src.read_bytes();src.unlink();d['planDataFiles'][pid]=path+'.gz'
(ROOT/'dist/data.json').write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')))
print('Compressed',len(d['planDataFiles']),'datasets. Expanded static bytes:',sum(p.stat().st_size for p in (ROOT/'dist').rglob('*') if p.is_file()))

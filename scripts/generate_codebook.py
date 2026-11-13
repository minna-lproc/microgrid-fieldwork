"""Regenerate the public codebook after editing static/survey.json."""
import csv,io,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
book_path=ROOT/'static/codebook.json'
schema=json.loads(
    (ROOT/'static/survey.json').read_text(encoding='utf-8-sig')
)
book=json.loads(
    book_path.read_text(encoding='utf-8-sig')
)
book.update(version=schema['version'],sections=schema['sections'])
output=io.StringIO();writer=csv.writer(output);writer.writerow(['version','instrument','part','id','question','type','options','fields_or_columns','notes'])
for key,label in book['metadata'].items():writer.writerow([schema['version'],'all','metadata',key,label,'metadata','','',''])
for section in schema['sections']:
 for q in section['questions']:writer.writerow([schema['version'],section['instrument'],section['id'],q['id'],q['label'],q['type'],json.dumps(q.get('options',[]),ensure_ascii=False),json.dumps(q.get('fields',q.get('columns',[])),ensure_ascii=False),q.get('help','')])
expected={book_path:json.dumps(book,ensure_ascii=False,indent=2),ROOT/'static/codebook.csv':'\ufeff'+output.getvalue()}
if '--check' in sys.argv:
 mismatch=[str(p.relative_to(ROOT)) for p,value in expected.items() if p.read_bytes()!=value.encode('utf-8')]
 if mismatch:raise SystemExit('Codebook is stale: '+', '.join(mismatch)+'. Run python scripts/generate_codebook.py.')
 print('Codebook matches questionnaire.')
else:
 for p,value in expected.items():p.write_bytes(value.encode('utf-8'))
 print('Codebook regenerated.')

from pathlib import Path
from pypdf import PdfReader
from lxml import etree as E
from zipfile import ZipFile
import json,re,sys
R=Path(__file__).resolve().parents[2];doc=R/'informe/entrega/Informe_Hito1_Cofrial_SpA.docx'
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
with ZipFile(doc) as z:root=E.fromstring(z.read('word/document.xml'))
# match heading and caption first text occurrences; exclude prior index content by page context
expected={'contenido':[],'tablas':[],'figuras':[]}
for p in root.xpath('//w:body/w:p',namespaces=ns):
 t=''.join(p.xpath('.//w:t/text()',namespaces=ns)).strip();style=p.xpath('./w:pPr/w:pStyle/@w:val',namespaces=ns)
 if style==['Heading1'] and t not in ('Índice de tablas','Índice de figuras'):expected['contenido'].append(t)
 if style==['Caption']:
  # first line contains label; full caption includes title; line break not present in xpath concat
  m=re.match(r'(Tabla|Figura) (\d+)(.*)',t)
  if m:expected['tablas' if m[1]=='Tabla' else 'figuras'].append(f'{m[1]} {m[2]} {m[3]}'.strip())
pdf=Path(sys.argv[1]);pages=PdfReader(pdf).pages
texts=[re.sub(r'\s+',' ',p.extract_text() or '') for p in pages]
# actual captions may have font ligature extraction anomalies, use label and number boundary first.
start=next((i for i,t in enumerate(texts) if 'Resumen ejecutivo' in t and 'Cofrial SpA presenta' in t),5)
result={k:[] for k in expected}
for kind,entries in expected.items():
 for t in entries:
  if kind=='contenido':needle=re.sub(r'\s+',' ',t);candidates=[i for i,txt in enumerate(texts) if i>=start and needle in txt]
  else:
   m=re.match(r'(Tabla|Figura) (\d+) (.*)',t);pat=rf'\b{m[1]} {m[2]}\b';candidates=[i for i,txt in enumerate(texts) if i>=start and re.search(pat,txt)]
  # titles may be mentioned before caption; choose page with title snippet where possible
  if kind!='contenido':
   title=m[3][:35];precise=[i for i in candidates if title in texts[i]]
   if precise:candidates=precise
  if not candidates:print('NO MATCH',kind,t[:65]);continue
  result[kind].append({'titulo':t,'pagina':min(candidates)+1})
(R/'informe/exportar/indices.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print({k:len(v) for k,v in result.items()},'páginas',len(pages))

"""Aplica la plantilla adjunta sin adoptar su pauta de Proyecto de Título."""
import sys,zipfile,re,copy
from lxml import etree as E
from pathlib import Path
G,P,O,*args=sys.argv[1:]
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main';R='http://schemas.openxmlformats.org/officeDocument/2006/relationships';PK='http://schemas.openxmlformats.org/package/2006/relationships'
ns={'w':W,'r':R};q=lambda n:'{'+W+'}'+n
with zipfile.ZipFile(P) as z:T={n:z.read(n) for n in z.namelist()}
with zipfile.ZipFile(G) as z:D={n:z.read(n) for n in z.namelist()}
root=E.fromstring(T['word/document.xml']);body=root.find(q('body'));cover=[copy.deepcopy(e) for e in list(body)[:6]];sect=copy.deepcopy(body.find(q('sectPr')))
# Fill textboxes in both DrawingML and VML fallback; no examples retained.
for el in cover:
 for p in el.xpath('.//w:p',namespaces=ns):
  ts=p.xpath('.//w:t',namespaces=ns);t=''.join(x.text or '' for x in ts)
  val=None
  if t=='TÍTULO':val='Informe de ingeniería'
  elif t=='Nombre o título del proyecto':val='Cofrial SpA'
  elif t.startswith('Asignatura:'):val='Asignatura: Transformación Digital TIEL15'
  elif t.startswith('Sección:'):val='Evaluación EVA2_3 Unidad 02 Hito 1'
  elif t.startswith('Académico guía'):val='Docente: Felipe Andrés Henríquez Vilugrón'
  elif t.startswith('Integrantes del'):val='Equipo consultor: Sergio Vásquez Marimán y Eric Aguayo Quintriqueo'
  elif t=='Fecha de entrega':val='Jueves 5 de noviembre de 2026'
  if val is not None and ts:
   ts[0].text=val
   for x in ts[1:]:x.text=''
   for sz in p.xpath('.//w:sz|.//w:szCs',namespaces=ns):
    if val.startswith(('Asignatura','Evaluación','Docente','Equipo','Jueves')):sz.set(q('val'),'20')
rels=E.fromstring(T['word/_rels/document.xml.rels']);grels=E.fromstring(D['word/_rels/document.xml.rels']);groot=E.fromstring(D['word/document.xml']);gb=groot.find(q('body'));ridmap={}
for rel in grels:
 typ=rel.get('Type');target=rel.get('Target');old=rel.get('Id')
 if typ.endswith('/image'):
  name='media/cofrial_'+Path(target).name;T['word/'+name]=D['word/'+target];new='rIdCofrial'+old;ridmap[old]=new
  rels.append(E.Element('{'+PK+'}Relationship',Id=new,Type=typ,Target=name))
 elif typ.endswith('/numbering'):
  # use generated numbering for body; cover has no lists
  for oldrel in list(rels):
   if oldrel.get('Type').endswith('/numbering'):rels.remove(oldrel)
  rels.append(E.Element('{'+PK+'}Relationship',Id='rIdCofrialNum',Type=typ,Target='numbering.xml'));T['word/numbering.xml']=D['word/'+target]
for el in gb:
 for node in el.iter():
  for attr in ('{'+R+'}embed','{'+R+'}id'):
   if node.get(attr) in ridmap:node.set(attr,ridmap[node.get(attr)])
# Merge generated styles by ID; retain template furniture styles.
st=E.fromstring(T['word/styles.xml']);gs=E.fromstring(D['word/styles.xml'])
for el in gs:
 sid=el.get(q('styleId'))
 if sid:
  for old in list(st):
   if old.get(q('styleId'))==sid:st.remove(old)
  st.append(copy.deepcopy(el))
# Remove inherited numbering on generated headings and use clear black styles.
for sid in ['Heading1','Heading2','Heading3']:
 for style in st.xpath('w:style[@w:styleId="'+sid+'"]',namespaces=ns):
  for num in style.xpath('.//w:numPr',namespaces=ns):num.getparent().remove(num)
# Derivar muebles horizontales sin modificar las partes originales de la plantilla.
land_ids={};land_parts=[]
for ref in sect:
 if ref.tag not in (q('headerReference'),q('footerReference')) or ref.get(q('type'))=='first':continue
 old_id=ref.get('{'+R+'}id')
 rel=next((r for r in rels if r.get('Id')==old_id),None)
 if rel is None:continue
 target=rel.get('Target');name='cofrial_land_'+Path(target).name;part='word/'+target
 tree=E.fromstring(T[part])
 wp='http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'
 a='http://schemas.openxmlformats.org/drawingml/2006/main'
 if ref.tag==q('headerReference'):
  for x in tree.findall('.//{'+wp+'}positionH/{'+wp+'}posOffset'):
   x.text=str(int(x.text)+2286000)
 else:
  for x in tree.iter():
   if x.tag in ('{'+wp+'}extent','{'+a+'}ext') and int(x.get('cx','0'))>7000000 and int(x.get('cy','9999999'))<500000:
    x.set('cx',str(int(x.get('cx'))+2286000))
 T['word/'+name]=E.tostring(tree,xml_declaration=True,encoding='UTF-8',standalone=True)
 relpart='word/_rels/'+Path(target).name+'.rels'
 if relpart in T:T['word/_rels/'+name+'.rels']=T[relpart]
 new_id='rIdLand'+old_id;land_ids[old_id]=new_id
 rels.append(E.Element('{'+PK+'}Relationship',Id=new_id,Type=rel.get('Type'),Target=name))
 land_parts.append((name,'application/vnd.openxmlformats-officedocument.wordprocessingml.'+('header' if ref.tag==q('headerReference') else 'footer')+'+xml'))
# Body sections inherit institutional headers/footer. Generated margins sized to attached reference.
def config(s,first=False):
 for x in list(s):
  if x.tag in (q('headerReference'),q('footerReference'),q('titlePg')):s.remove(x)
 size=s.find(q('pgSz'));land=size is not None and size.get(q('orient'))=='landscape'
 for x in sect:
  if x.tag in (q('headerReference'),q('footerReference')) and (first or x.get(q('type'))!='first'):
   newref=copy.deepcopy(x)
   if land and newref.get('{'+R+'}id') in land_ids:newref.set('{'+R+'}id',land_ids[newref.get('{'+R+'}id')])
   s.insert(0,newref)
 if first:s.append(E.Element(q('titlePg')))
 mar=s.find(q('pgMar'))
 if mar is None:mar=E.SubElement(s,q('pgMar'))
 for k,v in {'top':1418,'bottom':1418,'left':1418,'right':1418,'header':448,'footer':544}.items():mar.set(q(k),str(v))
 return s
for el in list(body):body.remove(el)
for el in cover:
 for br in list(el.xpath('.//w:br[@w:type="page"]',namespaces=ns)):br.getparent().remove(br)
 body.append(el)
# original cover ends with page break, preserve it; no extra blank section page
sp=copy.deepcopy(sect);config(sp,True);typ=sp.find(q('type'))
if typ is not None:sp.remove(typ)
p=E.Element(q('p'));pp=E.SubElement(p,q('pPr'));pp.append(sp);body.append(p)
for el in list(gb):
 if el.tag==q('sectPr'):continue
 for x in el.xpath('.//w:sectPr',namespaces=ns):config(x)
 body.append(copy.deepcopy(el))
last=gb.find(q('sectPr'));body.append(config(copy.deepcopy(last)))
# Footer text slot changes only.
for n in list(T):
 if re.match(r'word/(?:cofrial_land_)?footer\d+\.xml$',n): 
  ft=E.fromstring(T[n])
  for p in ft.xpath('//w:p',namespaces=ns):
   ts=p.xpath('.//w:t',namespaces=ns)
   if 'Formulación' in ''.join(x.text or '' for x in ts):
    if ts:
     ts[0].text='Ingeniería en Informática · Cofrial SpA · TIEL15'
     for x in ts[1:]:x.text=''
  T[n]=E.tostring(ft,xml_declaration=True,encoding='UTF-8',standalone=True)
settings=E.fromstring(T['word/settings.xml']);up=settings.find(q('updateFields'))
if up is None:up=E.SubElement(settings,q('updateFields'))
up.set(q('val'),'true')
ct=E.fromstring(T['[Content_Types].xml']);gct=E.fromstring(D['[Content_Types].xml']);exts={e.get('Extension') for e in ct}
for el in gct:
 if el.get('Extension') and el.get('Extension') not in exts:ct.append(copy.deepcopy(el));exts.add(el.get('Extension'))
for name,kind in land_parts:
 E.SubElement(ct,'{http://schemas.openxmlformats.org/package/2006/content-types}Override',PartName='/word/'+name,ContentType=kind)
for n,e in [('word/document.xml',root),('word/styles.xml',st),('word/settings.xml',settings),('word/_rels/document.xml.rels',rels),('[Content_Types].xml',ct)]:T[n]=E.tostring(e,xml_declaration=True,encoding='UTF-8',standalone=True)
with zipfile.ZipFile(O,'w',zipfile.ZIP_DEFLATED) as z:
 for n,b in T.items():z.writestr(n,b)
print('Formato de plantilla adjunta aplicado:',O)

"""Figuras documentales del sistema vigente. Requiere Pillow; no consulta servicios externos.

La topología usa la misma lista de elementos para PNG y draw.io. El Gantt lee el MD.
"""
from pathlib import Path
from datetime import date, timedelta
from xml.etree import ElementTree as E
import math, re
from PIL import Image, ImageDraw, ImageFont

IMG=Path(__file__).resolve().parent
FONTS=[Path('/System/Library/Fonts/Supplemental/Arial.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
FONT=next((p for p in FONTS if p.exists()),None)
def font(size):return ImageFont.truetype(str(FONT),size) if FONT else ImageFont.load_default()
INK='#172B42'; LINE='#6D7F92'; BLUE='#EEF4FB'; GREEN='#EFF6EE'
def canvas(w,h):
 im=Image.new('RGB',(w,h),'white');return im,ImageDraw.Draw(im)
def text(d,xy,s,size=28,fill=INK):d.text(xy,s,font=font(size),fill=fill)
def wrap(d,s,width,size):
 out=[]
 for raw in s.split('\n'):
  line=''
  for word in raw.split():
   test=(line+' '+word).strip()
   if line and d.textlength(test,font=font(size))>width:out.append(line);line=word
   else:line=test
  out.append(line)
 return out
def box(d,rect,title,body='',fill=BLUE,size=28):
 x,y,w,h=rect;d.rounded_rectangle((x,y,x+w,y+h),radius=10,fill=fill,outline=LINE,width=2)
 lines=wrap(d,title,w-32,size+2)+([''] if body else [])+wrap(d,body,w-32,size)
 step=size+9; yy=y+16
 for line in lines:
  text(d,(x+16,yy),line,size+2 if yy==y+16 else size);yy+=step if line else step//3
 if yy>y+h+5:raise ValueError('Caja insuficiente: '+title)
def arrow(d,pts,color=LINE,width=4):
 d.line(pts,fill=color,width=width)
 a,b=pts[-2:];ang=math.atan2(b[1]-a[1],b[0]-a[0]);r=13
 d.polygon([b,(b[0]-r*math.cos(ang-.5),b[1]-r*math.sin(ang-.5)),(b[0]-r*math.cos(ang+.5),b[1]-r*math.sin(ang+.5))],fill=color)

def arquitectura():
 im,d=canvas(2200,1050)
 text(d,(35,25),'Cofrial SpA   Topología implementada del prototipo',42)
 text(d,(35,84),'AWS Academy · us-east-1 por defecto · configuración al 25-oct-2026',29)
 groups=[('vpc',(385,145,1400,750),'VPC 10.0.0.0/16','#7C6099'),
         ('publica',(425,235,820,470),'Pública 10.0.1.0/24 · zona A','#52845D'),
         ('privadas',(1280,235,465,620),'DB subnet group privado','#537CA1')]
 for _,(x,y,w,h),t,c in groups:
  d.rectangle((x,y,x+w,y+h),outline=c,width=3);text(d,(x+18,y+16),t,29)
 nodes=[('usuarios',(25,320,300,245),'Usuarios','Clientes B2B/B2C\nVendedor, gerencia\ny despachador',BLUE),
        ('web',(455,330,355,260),'EC2 web','t3.small\nDjango + Gunicorn\nWhiteNoise\nGrafana en Docker',BLUE),
        ('iot',(850,330,355,260),'EC2 IoT','t3.micro\n5 grupos × 10 camiones\n50 camiones, cada 5 s',GREEN),
        ('pa',(1310,330,405,120),'10.0.2.0/24','Privada · zona A',BLUE),
        ('pb',(1310,480,405,120),'10.0.3.0/24','Privada · zona B',BLUE),
        ('rds',(1310,650,405,175),'RDS PostgreSQL 16','db.t3.micro · 20 GB\nSingle-AZ, sin réplica',BLUE),
        ('igw',(455,750,750,110),'Internet Gateway','Pública: ruta 0.0.0.0/0; privadas: ruta local',BLUE),
        ('externos',(1830,320,340,440),'Fuera de AWS','IA: Gemini y Groq\n\nMapas y rutas:\nOpenStreetMap\nNominatim y OSRM\n\nLlamadas salientes',BLUE)]
 for _,rc,t,body,f in nodes:box(d,rc,t,body,f,size=27)
 arrow(d,[(325,440),(455,440)])
 arrow(d,[(810,415),(830,415),(830,620),(1260,620),(1260,730),(1310,730)])
 arrow(d,[(1205,490),(1240,490),(1240,710),(1310,710)])
 arrow(d,[(1205,805),(1260,805),(1260,875),(1805,875),(1805,500),(1830,500)])
 arrow(d,[(630,750),(630,590)])
 text(d,(35,930),'sg-web: 80 y 3000 públicos; SSH desde IP del equipo. sg-iot: SSH desde esa IP.',30)
 text(d,(35,980),'sg-rds: 5432 solo desde web/IoT, con SSL. RDS sin acceso público; respaldos: 1 día.',30)
 im.save(IMG/'arquitectura-cloud.drawio.png')
 root=E.Element('mxfile');dg=E.SubElement(root,'diagram',name='Topología vigente');m=E.SubElement(dg,'mxGraphModel',pageWidth='2200',pageHeight='1050');rr=E.SubElement(m,'root');E.SubElement(rr,'mxCell',id='0');E.SubElement(rr,'mxCell',id='1',parent='0')
 for id,(x,y,w,h),t,c in groups:
  v=E.SubElement(rr,'mxCell',id=id,value=t,vertex='1',parent='1',style=f'fillColor=none;strokeColor={c};verticalAlign=top;align=left;fontSize=28;');E.SubElement(v,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),attrib={'as':'geometry'})
 for id,(x,y,w,h),t,body,f in nodes:
  v=E.SubElement(rr,'mxCell',id=id,value=t+'\n'+body,vertex='1',parent='1',style=f'rounded=1;whiteSpace=wrap;fillColor={f};strokeColor=#6D7F92;fontSize=26;');E.SubElement(v,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),attrib={'as':'geometry'})
 for i,(src,dst,label) in enumerate([('usuarios','web','HTTP 80 / Grafana 3000'),('web','rds','SQL SSL 5432'),('iot','rds','INSERT SSL 5432'),('web','externos','API saliente'),('igw','web','Ruta pública')]):
  v=E.SubElement(rr,'mxCell',id='e'+str(i),source=src,target=dst,value=label,edge='1',parent='1',style='edgeStyle=orthogonalEdgeStyle;endArrow=block;fontSize=22;');E.SubElement(v,'mxGeometry',relative='1',attrib={'as':'geometry'})
 E.indent(root);E.ElementTree(root).write(IMG/'arquitectura-cloud.drawio',encoding='utf-8',xml_declaration=True)


def pipeline():
 im,d=canvas(2050,900);text(d,(40,28),'Pipeline implementado del CRM',40)
 xs=[40,445,850,1255]; titles=['Prospecto','Contactado','Propuesta enviada','Negociación'];body=['Ingreso manual\nen el CRM','Interacción previa\ny cambio explícito','Cambio explícito\ndesde Contactado','Cambio explícito\ndesde Propuesta']
 for x,t,b in zip(xs,titles,body):box(d,(x,150,345,210),t,b,size=28)
 for a,b in zip(xs,xs[1:]):arrow(d,[(a+345,255),(b,255)])
 box(d,(1685,150,325,250),'Cliente ganado','RUT informado\nCorreo presente\nRUT no duplicado',GREEN,26)
 arrow(d,[(1600,255),(1685,255)])
 box(d,(830,540,400,170),'Perdido','Motivo obligatorio\nFecha de cierre','#FBEFEC',28)
 for x in xs:arrow(d,[(x+170,360),(x+170,470),(1030,470),(1030,540)])
 text(d,(40,775),'Desde cada etapa abierta: siguiente etapa o Perdido. Sin saltos ni retrocesos.',29)
 text(d,(40,825),'Registrar una interacción no mueve automáticamente la tarjeta.',29)
 im.save(IMG/'crm-pipeline.png')

def normalizacion():
 im,d=canvas(2000,1170);text(d,(40,25),'Requerimientos   Diseño lógico y representación física',40)
 text(d,(40,105),'DESCOMPOSICIÓN LÓGICA EN 3FN · tipos disjuntos por origen',29)
 box(d,(40,175,925,280),'requerimiento_general','PK requerimiento_id\nFK cliente_id\nAsunto, descripción, categoría, confianza, estado y fechas\nSin referencia a una orden',size=29)
 box(d,(1030,175,925,280),'requerimiento_pedido','PK requerimiento_id\nFK orden_id\nAsunto, descripción, categoría, confianza, estado y fechas\nCliente derivado: orden → dirección → cliente',size=29)
 text(d,(100,955),'Identificador → atributos de atención; no se repite el cliente de una orden.',29)
 arrow(d,[(500,455),(500,575),(1000,575),(1000,650)])
 arrow(d,[(1490,455),(1490,575),(1000,575)])
 box(d,(290,650,1420,280),'TABLA FÍSICA VIGENTE: requerimiento','requerimiento_id · cliente_id opcional · orden_id opcional · datos de atención\nConsulta general: orden_id nulo. Reclamo: orden propia vinculada.\nEl portal controla propiedad; no hay garantía SQL completa de coincidencia.\nLa redundancia física condicional se declara; no se ha ejecutado la descomposición.',size=29)
 text(d,(40,1010),'Reconstrucción lógica: unión de ambos tipos; en el segundo se deriva el cliente.',29)
 text(d,(40,1065),'Se conserva la función reclamo–pedido y se evita afirmar BCNF universal.',29)
 im.save(IMG/'mer-requerimientos-normalizacion.png')

def gantt():
 s=(IMG.parent/'07-metodologia-cronograma.md').read_text();s=s[s.index('## Cronograma'):s.index('## Equipo')]
 rows=[];mes={'oct':10,'nov':11}
 for line in s.splitlines():
  c=[x.strip() for x in line.strip('|').split('|')]
  if len(c)==5 and re.fullmatch(r'\d+-(oct|nov)',c[2]):
   parse=lambda v:date(2026,mes[v.split('-')[1]],int(v.split('-')[0]));rows.append((c[0],c[1],parse(c[2]),parse(c[3]),c[4]))
 start,end=date(2026,10,13),date(2026,11,12);days=(end-start).days+1
 im,d=canvas(2200,1020);text(d,(40,25),'Carta Gantt   Avance documentado y planificación restante',40)
 text(d,(40,85),'Corte: 25-oct-2026 · Hito 1: jueves 5-nov · Hito 2: jueves 12-nov',30)
 left,top,step,rowh=710,200,44,48
 for n in range(days):
  x=left+n*step;day=start+timedelta(days=n)
  if day.weekday()>4:d.rectangle((x,top,x+step,top+len(rows)*rowh),fill='#F3F4F6')
  text(d,(x+5,top-45),str(day.day),23);d.line((x,top,x,top+len(rows)*rowh),fill='#DDE2E7',width=1)
 text(d,(left,130),'OCTUBRE',25);text(d,(left+19*step,130),'NOVIEMBRE',25)
 colors={'Eric':'#426F9D','Sergio':'#3E8060','Ambos':'#8C713A'}
 for i,(act,resp,a,b,state) in enumerate(rows):
  y=top+i*rowh;text(d,(35,y+5),act,26);text(d,(550,y+8),resp,24)
  x=left+(a-start).days*step;w=((b-a).days+1)*step
  d.rectangle((x,y+7,x+w-3,y+39),fill=colors[resp]);d.line((20,y+rowh-4,2140,y+rowh-4),fill='#E5E9ED')
 for day,label,c in [(date(2026,10,25),'Corte','#45505D'),(date(2026,11,5),'H1','#B3483F'),(date(2026,11,12),'H2','#B3483F')]:
  x=left+(day-start).days*step+step//2;d.line((x,top-15,x,top+len(rows)*rowh+15),fill=c,width=4);text(d,(x-20,top+len(rows)*rowh+25),label,25,c)
 text(d,(40,top+len(rows)*rowh+100),'Barras previas: ventanas de trabajo documentadas. Barras posteriores: actividades planificadas.',27)
 im.save(IMG/'gantt.png')

def proceso_crm():
 """BPMN simplificado: alta manual y cambios explícitos, sin creación por la IA."""
 im,d=canvas(2100,1100);text(d,(40,25),'Proceso comercial TO-BE   Alta manual y control de etapas',38)
 lanes=['Vendedor','CRM','Cliente o prospecto','Gerencia'];w=510
 for i,t in enumerate(lanes):
  x=25+i*w;d.rectangle((x,110,x+w,1030),fill='#F7F9FC' if i%2==0 else 'white',outline=LINE,width=2);text(d,(x+20,130),t,30)
 tasks=[('alta',(65,230,430,150),'Ingreso manual','Datos y responsable del prospecto'),
        ('registro',(575,230,430,150),'Registrar prospecto','Etapa inicial y cartera asignada'),
        ('contacto',(65,500,430,170),'Registrar interacción','Luego mover explícitamente a Contactado'),
        ('etapas',(575,500,430,170),'Validar transición','Propuesta → Negociación; sin saltos ni retrocesos'),
        ('respuesta',(1085,500,430,170),'Aceptar o rechazar','El vendedor registra el resultado'),
        ('cierre',(575,800,430,180),'Cerrar oportunidad','Ganado: correo y RUT no duplicado. Perdido: motivo'),
        ('medir',(1595,800,430,180),'Consultar indicadores','Conversión y valor del embudo en el CRM')]
 for _,rc,t,b in tasks:box(d,rc,t,b,size=27)
 edges=[('alta','registro'),('registro','contacto'),('contacto','etapas'),('etapas','respuesta'),('respuesta','cierre'),('cierre','medir')]
 arrow(d,[(495,305),(575,305)])
 arrow(d,[(790,380),(790,430),(280,430),(280,500)])
 arrow(d,[(495,585),(575,585)]);arrow(d,[(1005,585),(1085,585)])
 arrow(d,[(1300,670),(1300,730),(790,730),(790,800)])
 arrow(d,[(1005,890),(1595,890)])
 im.save(IMG/'bpmn-p3-tobe.drawio.png')
 root=E.Element('mxfile');dg=E.SubElement(root,'diagram',name='Proceso CRM vigente');m=E.SubElement(dg,'mxGraphModel',pageWidth='2100',pageHeight='1100');rr=E.SubElement(m,'root');E.SubElement(rr,'mxCell',id='0');E.SubElement(rr,'mxCell',id='1',parent='0')
 for i,t in enumerate(lanes):
  c=E.SubElement(rr,'mxCell',id='lane'+str(i),value=t,vertex='1',parent='1',style='swimlane;horizontal=1;startSize=60;fillColor=#F7F9FC;fontSize=28;');E.SubElement(c,'mxGeometry',x=str(25+i*w),y='110',width=str(w),height='920',attrib={'as':'geometry'})
 for id,(x,y,ww,h),t,b in tasks:
  c=E.SubElement(rr,'mxCell',id=id,value=t+'\n'+b,vertex='1',parent='1',style='rounded=1;whiteSpace=wrap;fillColor=#EEF4FB;strokeColor=#6D7F92;fontSize=26;');E.SubElement(c,'mxGeometry',x=str(x),y=str(y),width=str(ww),height=str(h),attrib={'as':'geometry'})
 for i,(src,dst) in enumerate(edges):
  c=E.SubElement(rr,'mxCell',id='e'+str(i),source=src,target=dst,edge='1',parent='1',style='edgeStyle=orthogonalEdgeStyle;endArrow=block;');E.SubElement(c,'mxGeometry',relative='1',attrib={'as':'geometry'})
 E.indent(root);E.ElementTree(root).write(IMG/'bpmn-p3-tobe.drawio',encoding='utf-8',xml_declaration=True)

if __name__=='__main__':
 arquitectura();pipeline();normalizacion();gantt();proceso_crm();print('Topología, pipeline, normalización, proceso CRM y Gantt regenerados')

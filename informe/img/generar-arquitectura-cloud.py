import xml.etree.ElementTree as ET
from xml.sax.saxutils import quoteattr
OUT="informe/img/arquitectura-cloud.drawio"
PTS="points=[[0,0,0],[0.25,0,0],[0.5,0,0],[0.75,0,0],[1,0,0],[0,1,0],[0.25,1,0],[0.5,1,0],[0.75,1,0],[1,1,0],[0,0.25,0],[0,0.5,0],[0,0.75,0],[1,0.25,0],[1,0.5,0],[1,0.75,0]];"
GPTS="points=[[0,0],[0.25,0],[0.5,0],[0.75,0],[1,0],[1,0.25],[1,0.5],[1,0.75],[1,1],[0.75,1],[0.5,1],[0.25,1],[0,1],[0,0.75],[0,0.5],[0,0.25]];"
cells=[]; origin={"1":(0,0)}
def add(id,value,style,x,y,w,h,parent="1",vertex=True):
    ox,oy=origin[parent]
    origin[id]=(x,y)
    cells.append(f'<mxCell id="{id}" value={quoteattr(value)} style={quoteattr(style)} vertex="1" parent="{parent}"><mxGeometry x="{x-ox}" y="{y-oy}" width="{w}" height="{h}" as="geometry" /></mxCell>')
def group(id,value,icon,stroke,font,x,y,w,h,parent="1",dashed=0):
    st=f"{GPTS}outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;fontSize=12;fontStyle=0;container=1;dropTarget=1;pointerEvents=0;collapsible=0;recursiveResize=0;shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.{icon};strokeColor={stroke};fillColor=none;verticalAlign=top;align=left;spacingLeft=30;fontColor={font};dashed={dashed};"
    add(id,value,st,x,y,w,h,parent)
def svc(id,value,res,fill,x,y,parent="1",label="right"):
    lab="verticalLabelPosition=middle;verticalAlign=middle;labelPosition=right;align=left;spacingLeft=8;" if label=="right" else "verticalLabelPosition=bottom;verticalAlign=top;align=center;"
    st=f"sketch=0;{PTS}outlineConnect=0;fontColor=#232F3E;fillColor={fill};strokeColor=#ffffff;dashed=0;{lab}html=1;fontSize=12;fontStyle=0;aspect=fixed;shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{res};"
    add(id,value,st,x,y,78,78,parent)
def shape(id,value,shp,fill,x,y,parent="1",label="bottom"):
    lab="verticalLabelPosition=bottom;verticalAlign=top;align=center;"
    st=f"sketch=0;{PTS}outlineConnect=0;fontColor=#232F3E;fillColor={fill};strokeColor=none;dashed=0;{lab}html=1;fontSize=12;fontStyle=0;aspect=fixed;shape=mxgraph.aws4.{shp};"
    add(id,value,st,x,y,78,78,parent)
def edge(id,src,tgt,value="",ex=None,en=None,dashed=False,color=None,straight=False):
    st=("edgeStyle=none;" if straight else "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;")+"html=1;strokeWidth=2;"
    if ex: st+=f"exitX={ex[0]};exitY={ex[1]};exitDx=0;exitDy=0;"
    if en: st+=f"entryX={en[0]};entryY={en[1]};entryDx=0;entryDy=0;"
    if dashed: st+="dashed=1;"
    if color: st+=f"strokeColor={color};"
    if value: st+="labelBackgroundColor=#F5F5F5;fontSize=11;"
    cells.append(f'<mxCell id="{id}" value={quoteattr(value)} style={quoteattr(st)} edge="1" parent="1" source="{src}" target="{tgt}"><mxGeometry relative="1" as="geometry" /></mxCell>')

add("bg","","rounded=0;whiteSpace=wrap;html=1;fillColor=#F5F5F5;strokeColor=none;",0,0,2400,1400)
add("title","<b>Cofrial SpA - Arquitectura cloud del prototipo</b><br>Consultora TD-TIEL15 | 2026-10-12 | v0.1 borrador",
    "text;html=1;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontSize=14;spacing=8;",40,30,620,60)
# actores
actors=[("a_b2c","Cliente B2C<br>(portal web)"),("a_b2b","Cliente B2B<br>(lista institucional)"),("a_ven","Vendedor<br>(CRM)"),("a_des","Despachador<br>(torre de control)"),("a_ger","Gerencia<br>(dashboard BI)")]
for i,(id,v) in enumerate(actors):
    svc_y=210+i*150
    st=f"sketch=0;{PTS}outlineConnect=0;fontColor=#232F3E;fillColor=#232F3D;strokeColor=none;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=12;fontStyle=0;aspect=fixed;shape=mxgraph.aws4.users;"
    add(id,v,st,60,svc_y,78,78)
# nube
group("cloud","AWS Cloud (AWS Academy Learner Lab)","group_aws_cloud_alt","#232F3E","#232F3E",300,120,1800,1220)
group("region","Region us-east-1","group_region","#147EBA","#147EBA",330,170,1740,1130,"cloud")
group("vpc","VPC cofrial-vpc | 10.0.0.0/16","group_vpc2","#8C4FFF","#8C4FFF",370,230,1660,1040,"region")
group("az1","Zona de disponibilidad us-east-1a (prototipo Single-AZ)","group_availability_zone","#007FAA","#007FAA",470,290,1100,940,"vpc",dashed=1)
group("sn_web","Subred publica web | 10.0.1.0/24 | tabla de ruteo publica","group_security_group","#7AA116","#248814",500,350,1040,270,"az1")
group("sn_iot","Subred publica IoT | 10.0.2.0/24 | tabla de ruteo publica","group_security_group","#7AA116","#248814",500,660,1040,230,"az1")
group("sn_db1","Subred privada datos | 10.0.11.0/24 | tabla de ruteo privada","group_security_group","#147EBA","#147EBA",500,930,1040,270,"az1")
group("az2","Zona de disponibilidad us-east-1b","group_availability_zone","#007FAA","#007FAA",1610,880,380,350,"vpc",dashed=1)
group("sn_db2","Subred privada reserva | 10.0.12.0/24","group_security_group","#147EBA","#147EBA",1630,930,340,270,"az2")
add("note_db2","Sin instancia: el DB subnet group de RDS exige subredes en 2 zonas. En produccion aloja la replica Multi-AZ.",
    "text;html=1;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontSize=12;fontColor=#232F3E;",1650,1000,300,80,"sn_db2")
# servicios
shape("igw","Internet Gateway","internet_gateway","#8C4FFF",331,450)
svc("ec2web","<b>EC2 web + backend</b><br>e-commerce, CRM y API (Django)<br>Grafana en Docker (BI)<br>IP elastica, t3.small","ec2","#ED7100",900,450,"sn_web")
svc("ec2iot","<b>EC2 nodo IoT</b><br>Docker Compose: un contenedor<br>por camion (50 simulados)<br>t3.small","ec2","#ED7100",1100,720,"sn_iot")
svc("rds","<b>RDS PostgreSQL</b><br>db.t3.micro, Single-AZ<br>respaldos automaticos","rds","#C925D1",900,1010,"sn_db1",label="bottom")
# externo
add("ext","Google Gemini API<br>(free tier; Groq de respaldo)",f"sketch=0;{PTS}outlineConnect=0;fontColor=#232F3E;fillColor=#232F3D;strokeColor=none;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=12;fontStyle=0;aspect=fixed;shape=mxgraph.aws4.traditional_server;",2200,371,78,78)
add("ext_t","<b>Internet (fuera de AWS)</b>","text;html=1;align=center;verticalAlign=top;whiteSpace=wrap;rounded=0;fontSize=12;",2140,330,200,30)
# leyenda
leg=("<b>Security Groups (conexion encadenada)</b><br>"
"<b>sg-web:</b> 80 desde 0.0.0.0/0 (443 solo si hay dominio y certificado); 22 y 3000 (Grafana) solo desde la IP del equipo.<br>"
"<b>sg-iot:</b> sin entradas publicas; 22 solo desde la IP del equipo.<br>"
"<b>sg-rds:</b> 5432 solo desde sg-web y sg-iot. Sin acceso a internet.<br><br>"
"<b>Tablas de ruteo</b><br>"
"<b>Publica:</b> 10.0.0.0/16 local; 0.0.0.0/0 hacia el Internet Gateway.<br>"
"<b>Privada:</b> 10.0.0.0/16 local; sin ruta a internet.")
add("legend",leg,"text;html=1;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontSize=12;fontColor=#232F3E;fillColor=#FFFFFF;strokeColor=#232F3E;spacing=10;",1610,470,380,250,"vpc")
# aristas
for i,(id,_) in enumerate(actors):
    edge("e_"+id,id,"igw","",ex=(1,0.5),en=(0,round(0.1+i*0.2,1)),straight=True)
edge("e_igw_web","igw","ec2web","HTTP",ex=(1,0.5),en=(0,0.5))
edge("e_web_ia","ec2web","ext","API de IA",ex=(0.5,0),en=(0,0.5),dashed=True)
edge("e_web_rds","ec2web","rds","SQL 5432",ex=(0.5,1),en=(0.5,0))
edge("e_iot_rds","ec2iot","rds","INSERT telemetria",ex=(0.5,1),en=(1,0.5))
root="".join(cells)
xml=f'<mxfile><diagram id="arq-cloud" name="Arquitectura cloud"><mxGraphModel dx="2800" dy="1600" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="2400" pageHeight="1400" math="0" shadow="0"><root><mxCell id="0" /><mxCell id="1" parent="0" />{root}</root></mxGraphModel></diagram></mxfile>'
ET.fromstring(xml)
ids=[c.get("id") for c in ET.fromstring(xml).iter("mxCell")]; assert len(ids)==len(set(ids))
open(OUT,"w").write(xml); print("ok",len(ids))

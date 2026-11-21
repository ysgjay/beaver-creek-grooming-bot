"""Build the 0xSnow guide. Original reference art remains clipped raster.
The selected Balanced alternate is drawn from frozen native vector paths.
Requires reportlab, Pillow and pypdf. Fonts and artwork are packaged beside this file.
"""
from pathlib import Path
import math, json, re
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader, simpleSplit
from PIL import Image
from pypdf import PdfReader, PdfWriter

OUT=Path(__file__).resolve().parents[1]
A=OUT/'assets'
W,H=960,600
PAPER='#F5F9FC'; NAVY='#071B2E'; INK='#0C2A4A'; BLUE='#376F9B'; CYAN='#29C3FE'; GLACIER='#8DC4EB'; ICE='#DCEBFA'; BURG='#7B1E2E'; MUTED='#465C70'; LINE='#C3D3E0'
for name,file in [('Outfit','Outfit-400.ttf'),('Outfit600','Outfit-600.ttf'),('Outfit700','Outfit-700.ttf'),('Plex','IBMPlexSans-400.ttf'),('Plex600','IBMPlexSans-600.ttf'),('Mono','IBMPlexMono-Regular.ttf')]:
 pdfmetrics.registerFont(TTFont(name,str(A/'fonts'/file)))
T=json.loads((OUT/'tokens.json').read_text())
G=json.loads((OUT/'source/geometry.json').read_text())
BALANCED=json.loads((OUT/'selection.json').read_text())['selected_alternate']['spec']
c=canvas.Canvas(str(OUT/'0xSnow-Brand-Guide.pdf'),pagesize=(W,H),pageCompression=1)
c.setTitle('0xSnow | Brand & Product Guide | 1.1')
c.setAuthor('0xSnow')
c.setSubject('04S-C-A identity, Glacial Precision candidate slogan, color, typography, material, interface, and applications')
page=0; dark=False; issues=[]; allcopy=[]
def col(v):return HexColor(v) if isinstance(v,str) else v
def box(x,y,w,h,fill,r=0,stroke=None,lw=1):
 c.setFillColor(col(fill));c.setLineWidth(lw)
 if stroke:c.setStrokeColor(col(stroke))
 if r:c.roundRect(x,H-y-h,w,h,r,stroke=bool(stroke),fill=1)
 else:c.rect(x,H-y-h,w,h,stroke=bool(stroke),fill=1)
def line(x1,y1,x2,y2,color=LINE,lw=1,dash=None):
 c.saveState();c.setStrokeColor(col(color));c.setLineWidth(lw)
 if dash:c.setDash(*dash)
 c.line(x1,H-y1,x2,H-y2);c.restoreState()
def txt(s,x,y,size=14,font='Plex',color=None,align='left'):
 color=color or ('#E7F2FC' if dark else INK)
 c.setFillColor(col(color));c.setFont(font,size)
 wid=pdfmetrics.stringWidth(s,font,size)
 left=x if align=='left' else x-wid/2 if align=='center' else x-wid
 if left < -1 or left+wid>W+1 or y+size>H+1:issues.append((page,'text outside page',s,left,y,wid))
 f={'left':c.drawString,'center':c.drawCentredString,'right':c.drawRightString}[align]
 f(x,H-y-size*.80,s)
 allcopy.append(s)
def para(s,x,y,w,size=13,font='Plex',color=None,leading=None):
 leading=leading or size*1.45
 lines=[]
 for p in s.split('\n'):
  lines+=simpleSplit(p,font,size,w) if p else ['']
 for i,l in enumerate(lines):txt(l,x,y+i*leading,size,font,color)
 return y+len(lines)*leading
def label(s,x,y,color=None):txt(s.upper().replace('0XSNOW','0xSnow'),x,y,9,'Mono',color or ('#8DC4EB' if dark else BLUE))
def block(title,body,x,y,w=260):
 txt(title,x,y,20,'Outfit600');para(body,x,y+32,w,13,color=('#BDCEDC' if dark else MUTED))
def new(kicker,title=None,sub=None,d=False):
 global page,dark
 if page:c.showPage()
 page+=1;dark=d
 bg=NAVY if d else PAPER
 box(0,0,W,H,bg)
 c.bookmarkPage(f'page{page}');c.addOutlineEntry(f'{page:02d} {kicker.title()}',f'page{page}',0)
 label('0xSnow / '+kicker,48,25)
 txt('BRAND & PRODUCT GUIDE / 1.1',912,25,9,'Mono',GLACIER if d else MUTED,'right')
 if title:txt(title,48,65,34,'Outfit600')
 if sub:para(sub,48,113,860,12.5,color='#BDCEDC' if d else MUTED)
 line(48,562,912,562,'#32516A' if d else LINE,.6)
 txt('0xSnow  /  GLACIAL PRECISION - WORKING SLOGAN',48,575,8,'Mono',GLACIER if d else MUTED)
 txt(f'21 NOV 2026   /   {page:02d}',912,575,8,'Mono',GLACIER if d else MUTED,'right')
def ref(path,rect,x,y,w,h=None,rounding=0):
 # Clip a source-image viewport as layout, with no edits to original bitmap.
 sx,sy,sw,sh=rect
 h=h or w*sh/sw
 im=ImageReader(str(path));iw,ih=im.getSize();scale=min(w/sw,h/sh)
 ox=x+(w-sw*scale)/2;oy=y+(h-sh*scale)/2
 c.saveState();p=c.beginPath()
 if rounding:
  # Rectangular source viewports live inside a rounded panel when desired.
  p.roundRect(ox,H-oy-sh*scale,sw*scale,sh*scale,rounding)
 else:p.rect(ox,H-oy-sh*scale,sw*scale,sh*scale)
 c.clipPath(p,stroke=0,fill=0)
 c.drawImage(im,ox-sx*scale,H-oy-(ih-sy)*scale,width=iw*scale,height=ih*scale,mask='auto')
 c.restoreState()
def logo(x,y,w,kind='light'):
 rect={'light':(490,280,800,176),'symbol':(1425,274,137,202),'inverse':(1700,302,440,111)}[kind]
 ref(A/'logo-approved-reference.png',rect,x,y,w)
def vector_path(data):
 tokens=re.findall(r'[MLCZ]|-?\d+(?:\.\d+)?',data);p=c.beginPath();i=0
 while i<len(tokens):
  op=tokens[i];i+=1
  if op=='Z':p.close();continue
  n=6 if op=='C' else 2;v=[float(k) for k in tokens[i:i+n]];i+=n
  {'M':p.moveTo,'L':p.lineTo,'C':p.curveTo}[op](*v)
 return p
def balanced(x,y,w,theme='light',detail=False,guides=False):
 ink=NAVY if theme=='light' else '#E7F2FC'
 scale=w/(306 if detail else 726.22)
 c.saveState();c.translate(x,H-y);c.scale(scale,-scale)
 if guides:
  c.setStrokeColor(col('#83ACC7'));c.setLineWidth(.6);c.setDash(3,3)
  for yy in [.82,153.96]:c.line(-10,yy,316,yy)
  c.setDash()
 c.setFillColor(col(ink));c.drawPath(vector_path(G['gauge_ink']),fill=1,stroke=0)
 c.saveState();c.clipPath(vector_path(G['gauge_outer']),fill=0,stroke=0);c.setFillColor(col(CYAN));c.drawPath(vector_path(G['snow_plane']),fill=1,stroke=0);c.restoreState()
 xb=G['glyphs']['x'][0]['bounds'];s=BALANCED
 c.saveState();c.translate(s['x']-xb[0]*s['scale'],s['y']-xb[1]*s['scale']);c.scale(s['scale'],s['scale']);c.setFillColor(col(ink))
 c.drawPath(vector_path(' '.join(p['d'] for p in G['glyphs']['x'])),fill=1,stroke=0,fillMode=0);c.restoreState()
 c.translate(s['snowX'],0);c.setFillColor(col(ink))
 for n in ('S' if detail else 'Snow'):c.drawPath(vector_path(' '.join(p['d'] for p in G['glyphs'][n])),fill=1,stroke=0,fillMode=0)
 c.restoreState()
def texture(x,y,w,h,opacity=.16):
 c.saveState();p=c.beginPath();p.rect(x,H-y-h,w,h);c.clipPath(p,stroke=0,fill=0);c.setFillAlpha(opacity)
 im=ImageReader(str(A/'material/ice-etch-v4.webp'))
 for xx in range(int(x),int(x+w),480):
  for yy in range(int(y),int(y+h),480):c.drawImage(im,xx,H-yy-480,480,480)
 c.restoreState()
def frost(x,y,w,h,d=False,r=20,amount=None):
 fill='#102A40' if d else '#EDF7FE'
 box(x,y,w,h,fill,r, '#63839B' if d else '#C1D8E8',.7)
 c.saveState();p=c.beginPath();p.roundRect(x,H-y-h,w,h,r);c.clipPath(p,stroke=0,fill=0)
 texture(x,y,w,h,amount if amount is not None else (.22 if d else .055))
 c.restoreState()
 line(x+r,y+1,x+w-r,y+1,'#A6D6F2' if d else '#FFFFFF',.8)
def chip(s,x,y,w=None,d=False):
 w=w or pdfmetrics.stringWidth(s,'Plex600',10)+24
 box(x,y,w,26,'#24475E' if d else '#DCE8F2',8)
 txt(s,x+w/2,y+8,10,'Plex600','#E7F2FC' if d else INK,'center')
def nav_icon(name,x,y,size=28,color=INK,selected=False):
 c.saveState();c.translate(x,H-y-size);c.scale(size/28,size/28)
 # draw in a top-left SVG-like coordinate system
 c.translate(0,28);c.scale(1,-1);c.setStrokeColor(col(color));c.setLineWidth(1.75);c.setLineCap(1);c.setLineJoin(1)
 fill=GLACIER if selected else PAPER
 def path(points,closed=False,paint=False):
  p=c.beginPath();p.moveTo(*points[0])
  for a in points[1:]:p.lineTo(*a)
  if closed:p.close()
  c.setFillColor(col(fill));c.drawPath(p,stroke=1,fill=paint)
 if name=='today':
  c.setFillColor(col(fill));c.circle(21,7,2.75,stroke=1,fill=selected)
  path([(3,23),(11,8),(17,18),(20,13),(25,23)],True,selected);path([(8,13.5),(11,15),(13.5,12.2)])
 elif name=='calendar':
  c.roundRect(4,6,20,18,3,stroke=1,fill=0);c.line(4,11,24,11);c.line(9,3.5,9,8.5);c.line(19,3.5,19,8.5)
  c.setFillColor(col(fill));c.roundRect(8,15,5,5,1,stroke=1,fill=selected);c.line(17,16,20,16);c.line(17,20,20,20)
 elif name=='help':
  p=c.beginPath();p.moveTo(14,3);p.lineTo(23,6.5);p.lineTo(23,12.5);p.curveTo(23,17.9,19.2,21.9,14,24.5);p.curveTo(8.8,21.9,5,17.9,5,12.5);p.lineTo(5,6.5);p.close()
  c.setFillColor(col(fill));c.drawPath(p,fill=selected,stroke=1);c.line(14,9,14,18);c.line(9.5,13.5,18.5,13.5)
 else:
  c.saveState();p=c.beginPath();p.roundRect(16.5,2.5,8,23,2.5);c.clipPath(p,stroke=0)
  for i in range(32):
   c.setFillColor(HexColor('#A9CCE6'));c.setFillAlpha(i/31*.65);c.rect(16.5+i*.25,2.5,.26,23,stroke=0,fill=1)
  c.restoreState();c.setLineWidth(1.1)
  for yy in [7,12,17,22]:c.line(21 if yy in [7,17] else 21.5,yy,23.5,yy)
  c.setLineWidth(1.25)
  for i in range(6):
   an=-math.pi/2+i*math.pi/3;ux,uy=math.cos(an),math.sin(an);vx,vy=-uy,ux
   c.line(11.5,16,11.5+8.4*ux,16+8.4*uy)
   bx,by=11.5+5.3*ux,16+5.3*uy
   c.line(bx+1.6*ux+1.6*vx,by+1.6*uy+1.6*vy,bx,by);c.line(bx,by,bx+1.6*ux-1.6*vx,by+1.6*uy-1.6*vy)
 c.restoreState()
def stake(x,y,w,h,value,maxv=10,d=False,low=None,high=None):
 st=GLACIER if d else BLUE;bg='#173B55' if d else '#E5F1FA';fl='#376B92' if d else '#C5DFF2'
 box(x,y,w,h,bg,10,st,.8)
 c.saveState();p=c.beginPath();p.roundRect(x,H-y-h,w,h,10);c.clipPath(p,stroke=0)
 sy=y+h-value/maxv*h
 if high:
  hy=y+h-high/maxv*h
  c.setStrokeColor(col(st));c.setLineWidth(.5)
  for xx in range(int(x-h),int(x+w+h),7):c.line(xx,H-sy,xx+sy-hy,H-hy)
 p=c.beginPath();p.moveTo(x,H-y-h);p.lineTo(x,H-sy);p.curveTo(x+w*.3,H-sy-5,x+w*.55,H-sy+6,x+w,H-sy);p.lineTo(x+w,H-y-h);p.close()
 c.setFillColor(col(fl));c.drawPath(p,fill=1,stroke=0)
 c.restoreState()
 for i in range(1,5):line(x+2,y+h*i/5,x+7,y+h*i/5,st,.65)
 if low is not None:line(x+w-9,y+h-low/maxv*h,x+w-2,y+h-low/maxv*h,st,1.6)
 txt(str(value)+'"',x+w/2,y+h-23,14,'Outfit600','#E7F2FC' if d else INK,'center')
def heatstrip(x,y,w,d=False):
 vals=[1,.1,0,2,.6,0,.5,1,.3,4];names=['Tue','Wed','Thu','Fri','Sat','Sun','Mon','Tue','Wed','Thu']
 a,b=('#173B55','#315D7B') if d else ('#E5F1FA','#88B2D5')
 ca,cb=col(a),col(b);cw=(w-9*4)/10
 for i,v in enumerate(vals):
  r=v/4;cl=Color(ca.red*(1-r)+cb.red*r,ca.green*(1-r)+cb.green*r,ca.blue*(1-r)+cb.blue*r)
  xx=x+i*(cw+4);box(xx,y,cw,33,cl,6);txt(str(v) if v else '0',xx+cw/2,y+11,10,'Mono','#E7F2FC' if d else INK,'center');txt(names[i],xx+cw/2,y+40,9,'Plex','#BDCEDC' if d else MUTED,'center')
def legend_item(s,x,y,color=BLUE):
 box(x,y+3,8,8,color,2);txt(s,x+15,y,10,'Plex', '#BDCEDC' if dark else MUTED)
def schematic_map(x,y,w,h,d=False):
 box(x,y,w,h,'#E4EEF0',12)
 c.saveState();p=c.beginPath();p.roundRect(x,H-y-h,w,h,12);c.clipPath(p,stroke=0)
 for i in range(7):
  p=c.beginPath();p.moveTo(x-20,H-y-h+15+i*17);p.curveTo(x+w*.25,H-y-h+60+i*16,x+w*.35,H-y-h+10+i*25,x+w+30,H-y+10+i*8)
  c.setStrokeColor(HexColor('#B7D0D7'));c.setLineWidth(1);c.drawPath(p)
 for j in range(3):
  p=c.beginPath();p.moveTo(x+w*.66+j*12,H-y+3);p.curveTo(x+w*.2+j*15,H-y-h*.3,x+w*.85,H-y-h*.55,x+w*.27+j*22,H-y-h+15)
  c.setStrokeColor(HexColor('#376F9B'));c.setLineWidth(2);c.drawPath(p)
 c.restoreState();chip('ILLUSTRATIVE MAP',x+12,y+12,130)
def desktop(x,y,w,h,d=False):
 # Illustrative layout, intentionally not a live screenshot.
 sc=w/864; body='#071B2E' if d else '#DCEBFA';text='#E7F2FC' if d else INK;sub='#BDCEDC' if d else MUTED
 c.saveState();c.translate(x,H-y);c.scale(sc,sc);c.translate(0,-H)
 # helpers now use original 600 high coordinate system with x/y relative.
 box(0,0,864,h/sc,body,14)
 frost(10,10,844,54,d,12)
 logo(24,24,104,'inverse' if d else 'light');txt('Beaver Creek',149,26,15,'Outfit600',text)
 for i,n in enumerate(['Today','Calendar','Forecast','Help']):
  xx=320+i*83
  if i==0:chip(n,xx,22,72,d)
  else:txt(n,xx+12,29,11,'Plex',text)
 chip('Morning report',720,22,120,d)
 frost(10,76,492,302,d,16);txt('Grooming',26,91,19,'Outfit600',text);txt('Map from Nov 21 / 6:15 AM MT',26,119,10,'Plex',sub)
 schematic_map(26,143,460,188,d);txt('Groomed overnight',26,345,10,'Plex600',sub);txt('Little Brave Lower   /   Flint   /   Maverick',162,345,10,'Plex',text)
 frost(514,76,340,98,d,16)
 for i,(v,l) in enumerate([('4"','NEW 24H'),('28"','BASE'),('24°','TEMP'),('8 mph','WIND')]):
  xx=530+i*80;label(l,xx,93,sub);txt(v,xx,114,25,'Outfit600',text)
 txt('Resort snow / 5:30 AM MT',530,150,9,'Plex',sub)
 frost(514,186,340,110,d,16);txt('Snow forecast',530,201,18,'Outfit600',text);txt('Next 5 days 3.7" / likely 2-6"',530,228,10,'Plex',sub);heatstrip(530,246,308,d)
 frost(514,308,340,70,d,16);txt('Source clarity comes first.',530,324,15,'Outfit600',text);txt('Times, units and uncertainty stay beside the number.',530,348,10,'Plex',sub)
 c.restoreState()
def phone(x,y,w,d=False):
 # Illustrated at 0.72x a 320px handset, with readable page annotations nearby.
 sc=w/320;c.saveState();c.translate(x,H-y);c.scale(sc,sc);c.translate(0,-H)
 bg='#071B2E' if d else '#DCEBFA';text='#E7F2FC' if d else INK;sub='#BDCEDC' if d else MUTED
 box(0,0,320,510,bg,28,'#32516A' if d else '#B6CBDC',1)
 frost(8,8,304,71,d,21);txt('9:41',22,18,9,'Plex600',text);logo(22,41,100,'inverse' if d else 'light');txt('Beaver Creek',144,46,17,'Outfit600',text)
 txt('Today',20,98,26,'Outfit600',text);txt('Sat, Nov 21 / saved 7 AM MT',20,132,11,'Plex',sub)
 frost(12,158,296,79,d,16)
 for i,(v,l) in enumerate([('4"','NEW 24H'),('28"','BASE DEPTH'),('24°','NOW')]):
  xx=26+94*i;label(l,xx,172,sub);txt(v,xx,191,30,'Outfit600',text)
 frost(12,249,296,124,d,16);txt('Next 5 days',26,264,17,'Outfit600',text);txt('3.7" expected / likely 2-6"',26,291,11,'Plex',sub);heatstrip(26,314,268,d)
 frost(12,385,296,47,d,14);txt('Grooming report',26,400,15,'Outfit600',text);txt('Updated 6:15 AM',178,402,10,'Plex',sub)
 frost(8,443,304,59,d,18)
 for i,name in enumerate(['today','calendar','forecast','help']):
  xx=20+i*74
  if i==0:box(xx-3,448,68,48,'#24475E' if d else '#DCE8F2',10)
  nav_icon(name,xx+17,452,24,text,i==0);txt(name.title(),xx+30,482,9,'Plex600' if i==0 else 'Plex',text,'center')
 c.restoreState()

# 01 / COVER
new('Identity system',d=False)
label('SELECTED DIRECTION / 04S-C-A',48,101)
logo(65,175,830)
txt('Glacial Precision',48,400,46,'Outfit600')
txt('Working slogan',49,457,11,'Mono',BLUE)
para('A measured identity for snow forecasts, grooming reports and mountain days.',580,407,312,18,'Plex',MUTED,26)
line(48,515,912,515,LINE)
txt('BRAND STRATEGY  /  LOGO  /  PRODUCT  /  APPLICATIONS',48,531,10,'Mono',MUTED)

# 02 / FOUNDATION
new('The idea','A clear read on the mountain.','Simple enough to recognize. Precise enough to help people make a plan.')
block('Measured', 'Show the number, its time, its source and what remains uncertain. Earn trust through visible context.',48,177,252)
block('Frosty', 'Borrow the clarity, color and etched detail of ice. Keep the information at the center calm and legible.',354,177,252)
block('Useful', 'Help a skier answer three questions: what fell, what is groomed, and what comes next?',660,177,252)
box(48,335,864,185,ICE,18)
label('BRAND PROMISE',72,357)
txt('Mountain information, made clear.',72,388,30,'Outfit600')
para('0xSnow brings snow forecasts, resort reports and practical mountain information into a readable daily view. The zero behaves like a snow gauge: a compact idea that connects the name to the product.',72,438,770,14)

# 03 / LOGO IDEA
new('The primary mark','Snow becomes the zero.','04S-C-A / Glacial Precision lettering / baseline-aligned refinement')
logo(78,178,165,'symbol')
label('THE CORE IDEA',340,183)
block('A gauge, a zero, a snowline.', 'Two inward ticks suggest measurement. The blue drift completes the lower contour of the zero itself. Its open center keeps the symbol simple at a glance.',340,210,515)
line(340,340,877,340,LINE)
para('Keep the outer bottom edge of the zero aligned with the wordmark baseline. Match the top to the capital S; preserve the selected width and the two left-hand ticks.',340,361,510,15)
para('The blue base is part of the silhouette. Do not add a dark rim beneath it.',340,452,510,13,'Plex600',BLUE)

# 04 / LOCKUPS
new('Logo family','One identity. Three practical forms.','Primary reference specimens. Use the matching production vectors in assets/primary for exports.')
box(48,165,555,167,'#EDF7FE',18);logo(75,186,500)
label('01 / PRIMARY WORDMARK',68,311)
box(623,165,289,167,ICE,18);logo(739,187,66,'symbol');label('02 / COMPACT SYMBOL',642,302)
box(48,350,555,170,NAVY,18);logo(96,368,450,'inverse');label('03 / INVERSE COLOR STUDY',68,501,GLACIER)
para('Wordmark: website, email masthead, documents and signage.\n\nSymbol: compact navigation, app tile and small identifiers.',643,362,244,13)
para('Production SVG/PDF masters are included. The next sheet records Balanced A-01, the selected raised-x alternate.',643,459,244,11,color=MUTED)

# SELECTED ALTERNATE / added in 1.1
new('Selected alternate','Balanced. The selected raised x.','04S-C-A-alt-A-01 / selected 21 November 2026 / exact study geometry retained')
balanced_page=page
for xx,theme in [(48,'light'),(492,'dark')]:
 box(xx,155,420,153,'#EDF7FE' if theme=='light' else NAVY,18)
 label(theme+' / standard treatment',xx+22,173,BLUE if theme=='light' else GLACIER)
 balanced(xx+28,211,364,theme)
label('PRESERVE THE SELECTED RELATIONSHIP',48,333)
txt('48% x scale. Tighter spacing.',48,357,23,'Outfit600')
para('The x sits between 0 and Snow. The original gauge,\nSnow letterforms and baseline remain unchanged.',48,393,480,13)
para('Use this alternate for brand signatures and mastheads.\nLeave 1/4 cap-height clear space; proof at 160 px / 35 mm.',48,442,480,12,color=MUTED)
balanced(630,342,245,'light',detail=True,guides=True)
txt('Cap line + baseline / original optical overshoot',760,484,9,'Mono',BLUE,'center')
for xx,hx,name in [(48,NAVY,'MIDNIGHT'),(235,'#E7F2FC','LIGHT INK'),(422,CYAN,'SNOW BLUE')]:
 box(xx,513,24,24,hx,6,LINE if hx=='#E7F2FC' else None,.5)
 txt(name,xx+34,514,9,'Mono',MUTED);txt(hx,xx+34,527,9,'Mono',BLUE)
txt('Custom outlined lettering',912,514,11,'Plex600',INK,'right')
txt('Glacial Precision remains a working slogan.',912,531,10,'Plex',MUTED,'right')

# 05 / PROPORTIONS
new('Proportions & spacing','Let the mark breathe.','Primary-logo spacing guidance. Use supplied paths and proof actual size for the intended application.')
logo(120,193,620)
line(120,198,740,198,BLUE,.6,[3,3]);line(120,322,740,322,BLUE,.6,[3,3])
line(93,198,93,322,BLUE,1);line(86,198,100,198,BLUE,1);line(86,322,100,322,BLUE,1);txt('H',74,254,13,'Mono',BLUE)
line(89,167,772,167,GLACIER,.7,[3,3]);line(89,353,772,353,GLACIER,.7,[3,3]);line(89,167,89,353,GLACIER,.7,[3,3]);line(772,167,772,353,GLACIER,.7,[3,3]);label('X = 1/4 H',791,250)
block('Clear space', 'Keep at least X around every side. Measure from the visible artwork, including the blue base.',48,390,250)
block('Proportion', 'Wordmark approximately 5:1; gauge approximately 0.68H wide inside the lockup. Scale as one object.',354,390,250)
block('Starting minimums', 'Wordmark: 160 px / 35 mm wide. Symbol: 32 px / 8 mm tall. Proof at actual size before production.',660,390,250)

# 06 / USE RULES
new('Logo discipline','The details that make it ours.','Treat the selected geometry as a fixed design, not a font setting.')
for i,(title,body) in enumerate([
 ('Keep the baseline','The snow base sits with xSnow, not below it. Do not stretch the zero vertically.'),
 ('Keep the snow contour','The blue snowbank forms the bottom edge. No dark lower rim and no separate bowl.'),
 ('Keep the two ticks','Maintain their left-hand position, thickness and spacing. Avoid extra gauge markings.'),
 ('Keep the name','Write 0xSnow: numeral zero, lowercase x, capital S. Preserve the lowercase n, o and w.'),
 ('Keep the lettering','Do not retype the logo in Outfit. Outfit is the product typeface, not a logo substitute.'),
 ('Keep effects secondary','No enclosing icy zero, fake bevel on small marks, drop shadow on letters or stretched lockup.')]):
  x=48+(i%3)*306;y=171+(i//3)*184
  label(f'0{i+1}',x,y);block(title,body,x,y+28,250)

# 07 / SLOGAN
new('Brand language','Glacial Precision','A candidate slogan, now shown in context. The logo ID stays 04S-C-A.')
box(48,169,864,217,'#EDF7FE',20);logo(180,185,600);txt('Glacial Precision',480,344,22,'Plex',INK,'center')
block('What it communicates', 'A cold, deliberate and technically considered identity. It connects the glacier palette with the measuring zero.',48,421,250)
block('How to set it', 'Use IBM Plex Sans 400 in sentence case. Keep it separate from the logo and at least 1/4 H below it.',354,421,250)
block('Where it belongs', 'Brand covers, campaigns, packaging and larger signs. Omit it in dense product headers and small app icons.',660,421,250)

# 08 / PALETTE
new('Core palette','Cold color. Warm restraint.','sRGB specification targets. The approved raster remains unchanged and includes tonal variation.')
swatches=[('Midnight',NAVY,'Primary brand anchor'),('Snow Blue',CYAN,'Snowbank / brand highlight'),('Glacier',GLACIER,'Dark-mode snow strokes'),('Ice',ICE,'Light background'),('Frost Paper',PAPER,'Readable surfaces'),('Burgundy',BURG,'Small brand accents')]
for i,(n,hx,role) in enumerate(swatches):
 x=48+(i%3)*294;y=166+(i//3)*173
 box(x,y,276,95,hx,14,LINE if hx==PAPER else None)
 txt(n,x,y+108,17,'Outfit600');txt(hx,x+276,y+112,11,'Mono',MUTED,'right');txt(role,x,y+137,11,'Plex',MUTED)
txt('Use Snow Blue as a fill or highlight, not small text on white. All snow data stays in the blue / ice family.',48,526,12,'Plex600',BLUE)

# 09 / THEMES
new('Light & dark','Two appearances, one hierarchy.','Theme values are grounded in the existing app. The brand snowbank blue is separate from chart colors.')
for i,mode in enumerate(['light','dark']):
 d=mode=='dark';x=48+i*444;v=T[mode]
 box(x,166,420,346,v['background'],20)
 txt('Frosted Snow' if not d else 'Midnight Ice',x+24,187,22,'Outfit600',v['text'])
 for j,(key,nm) in enumerate([('surface','Surface'),('text','Text'),('textSecondary','Secondary'),('selected','Selected tab'),('snowStroke','Snow stroke'),('snowFill','Expected fill'),('snowRange','Uncertainty')]):
  yy=232+j*36;box(x+24,yy,24,24,v[key],6,v['line'],.5);txt(nm,x+60,yy+5,12,'Plex',v['text']);txt(v[key],x+396,yy+6,11,'Mono',v['textSecondary'],'right')
txt('System appearance is the default. Keep the same information order, chart meanings and navigation in both modes.',48,531,12,'Plex',MUTED)

# 10 / CONTRAST
new('Readable color','Color with a job to do.','Contrast ratios below are calculated for the opaque tokens, not a certification of every translucent state.')
def lum(h):
 a=[int(h[i:i+2],16)/255 for i in (1,3,5)];a=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in a];return sum(v*k for v,k in zip(a,[.2126,.7152,.0722]))
def contrast(a,b):
 l=sorted([lum(a),lum(b)]);return (l[1]+.05)/(l[0]+.05)
pairs=[('Light body',T['light']['text'],PAPER),('Light secondary',MUTED,PAPER),('Dark body','#E7F2FC','#102A40'),('Dark secondary','#BDCEDC','#102A40'),('Light snow line',BLUE,PAPER),('Dark snow line',GLACIER,'#102A40')]
ratios=[]
for i,(name,fg,bg) in enumerate(pairs):
 x=48+(i%3)*294;y=166+(i//3)*128;r=contrast(fg,bg);ratios.append({'pair':name,'foreground':fg,'background':bg,'ratio':r})
 box(x,y,276,107,bg,14,LINE if bg==PAPER else None);txt(name,x+18,y+17,12,'Plex600',fg);txt(f'{r:.2f}:1',x+18,y+46,32,'Outfit600',fg)
para('Target 4.5:1 for normal text and 3:1 for essential graphical boundaries. Pale fills are supported by darker outlines, values and labels. Test actual composited surfaces over maps, images and scrolling content.',48,446,550,13)
para('Use at least 44 x 44 px touch targets as the product standard. Focus must be visible, distinct from selection and never clipped.',653,446,259,13)
txt('Reference: W3C WCAG 2.2 / Contrast (Minimum) and Non-text Contrast. Linked in Sources.',48,532,10,'Plex',MUTED)
(OUT/'contrast-checks.json').write_text(json.dumps(ratios,indent=2)+'\n')

# 11 / TYPOGRAPHY
new('Typography','Precision without stiffness.','Retain the three licensed, self-hosted type families already used by the app.')
label('OUTFIT / HEADINGS & KEY NUMBERS',48,172);txt('Your next snow day.',48,204,48,'Outfit600');txt('4"  28"  24°',48,269,46,'Outfit600',BLUE)
label('IBM PLEX SANS / INTERFACE & BODY',48,355);para('Snowfall, grooming and resort information.\nA clear forecast includes its likely range.',48,386,480,21,'Plex',INK,29)
label('IBM PLEX MONO / DATA & TIMESTAMPS',48,475);txt('07:00 MT   /   3.7 in   /   24 h',48,504,18,'Mono',BLUE)
box(620,168,292,363,ICE,18)
label('PRODUCT TYPE SCALE',644,190)
for j,(role,spec) in enumerate([('Page title','Outfit 600 / 28-32'),('Section title','Outfit 600 / 22'),('Primary metric','Outfit 600 / 34-40'),('Body / control','Plex Sans 400-600 / 15-16'),('Metadata','Plex Sans 400 / 12-13'),('Dense data','Plex Mono 400 / 11-13')]):
 txt(role,644,226+j*43,12,'Plex600');txt(spec,644,243+j*43,10,'Mono',MUTED)
txt('Sizes in CSS px. Use 1.45-1.6 body leading.',644,504,10,'Plex',MUTED)

# 12 / MATERIAL
new('Material language','Ice with depth. Information with clarity.','Carry the app\'s etched ice forward as a supporting material, with the logo kept crisp.',d=True)
frost(48,164,508,351,True,24,.40)
label('ETCHED ICE / MATERIAL CLOSE-UP',72,187,GLACIER)
txt('Fine texture.',72,247,38,'Outfit600');txt('Soft optical edges.',72,295,38,'Outfit600')
para('Small curled etches, scattered bubble contours and directional light give the pane substance.',72,363,416,17,color='#E7F2FC')
txt('Magnified material study; stronger than normal UI.',72,480,10,'Mono',GLACIER)
block('01 / Texture', 'Use the existing ice-etch-v4 tile at a constant scale. Avoid large crystals, fern branches and a noisy rim.',604,172,280)
block('02 / Depth', 'A gentle upper-left reflection and a narrow inner highlight suggest thickness. Avoid raised button lips.',604,289,280)
block('03 / Restraint', 'Header, navigation and card shells carry the material. Keep images, chart fills and dense labels clear.',604,406,280)

# 13 / MATERIAL RECIPE
new('Material in product','The same ice, in both appearances.','These are design specimens; the packaged source records the existing app material settings.')
for i,d in enumerate([False,True]):
 x=48+i*444;bg=NAVY if d else ICE;fg='#E7F2FC' if d else INK
 box(x,168,420,221,bg,20);frost(x+18,187,384,55,d,12);txt('Beaver Creek',x+35,204,20,'Outfit600',fg)
 frost(x+18,255,384,116,d,16);txt('Next 5 days',x+35,272,16,'Outfit600',fg);txt('3.7"',x+35,302,34,'Outfit600',fg);txt('Likely 2-6"',x+128,317,13,'Plex',fg)
block('A stable surface', 'Cards: 74% pale tint / 76% navy tint. Header and bottom navigation: 94% tint. Keep opaque fallback surfaces.',48,421,260)
block('A fixed texture scale', '480 x 480 CSS px tile. Start at 10% opacity in light and 20% in dark. Never stretch the texture to fit a card.',354,421,260)
block('A readable fallback', 'Remove texture, blur and decorative shadows for reduced transparency, forced colors and print.',660,421,250)

# 14 / CHARTS
new('Data language','Snow is always blue.','Keep the app\'s distinctive snow stakes and daily heat strip. Meaning comes before material.')
box(48,166,534,292,'#FFFFFF',20,LINE,.6)
label('EXPECTED SNOWFALL / INCHES',70,185)
for i,(v,l,h) in enumerate([(2,1,4),(4,2,6),(1,.5,3),(6,4,9),(3,1,5)]):
 xx=82+i*99;stake(xx,222,59,170,v,10,False,l,h);txt(['Tue','Wed','Thu','Fri','Sat'][i],xx+29.5,406,11,'Plex',MUTED,'center')
legend_item('Expected fill',70,437,'#C5DFF2');legend_item('Likely range: hatch + low mark',215,437,BLUE)
block('The snow stake', 'Preserve ruler ticks, the drift top, the low-end mark and hatched upper estimate. Keep values and units visible.',626,177,276)
block('The daily strip', 'Use a consistent blue scale and explicit values. Zero is 0; unavailable data is a dash with a clear label.',626,316,276)
heatstrip(48,481,534,False)
para('All values shown here and in UI specimens are illustrative. No forecast or resort report is being published.',626,467,274,12,color=MUTED)

# 15 / DESKTOP LIGHT
new('Product / light','A calm daily overview.','Proposed 0xSnow identity applied to the existing map-led information structure. Illustrative data.')
desktop(48,158,864,390,False)

# 16 / DESKTOP DARK
new('Product / dark','The same clarity, after dark.','Keep maps and camera images in their original colors. Adapt surfaces and chart tokens, not the source imagery.',d=True)
desktop(48,158,864,390,True)

# 17 / MOBILE
new('Product / mobile','The next useful fact comes first.','A compact brand header, clear conditions and familiar bottom navigation. Illustrative data.')
phone(48,158,235,False);phone(311,158,235,True)
block('A quick scan', 'Lead with new snow, base depth and current conditions, then the short outlook and grooming report.',591,174,293)
block('An easy next step', 'Give Forecast a snowfall-first view and enough horizontal space for the original stakes. Keep day details close.',591,303,293)
block('A stable navigation', 'Use four labeled destinations. Selected tabs are flat ice tints, with no underline or raised bottom edge.',591,433,293)

# 18 / COMPONENTS
new('Navigation & controls','Useful shapes. Quiet states.','Retain the existing custom alpine icon family; it complements the new gauge symbol.')
for i,n in enumerate(['today','calendar','forecast','help']):
 x=48+i*216;box(x,166,196,112,ICE,16);nav_icon(n,x+74,185,48,INK,True);txt(n.title(),x+98,247,14,'Plex600',INK,'center')
frost(48,310,420,91,False,16)
for i,n in enumerate(['today','calendar','forecast','help']):
 x=64+i*100
 if i==2:box(x,321,88,66,'#DCE8F2',12)
 nav_icon(n,x+30,329,28,INK,i==2);txt(n.title(),x+44,367,10,'Plex600' if i==2 else 'Plex',INK,'center')
para('28-unit icon grid; rounded caps and joins. Render 26 px on mobile and 20 px in desktop tabs. Forecast uses a fine snowflake and a softly fading ruler edge.',48,426,408,13)
chip('View forecast',518,321,138)
box(678,321,150,44,BURG,12);txt('Get the report',753,336,12,'Plex600','#FFFFFF','center')
para('Use blue for routine actions and focus. Reserve burgundy for an occasional brand action; keep it out of weather graphics. A visible focus ring is separate from the selected state.',518,392,370,13)
txt('SVG originals are included in assets/navigation/.',518,502,10,'Mono',BLUE)

# 19 / VOICE
new('Voice & data integrity','Say what we know. Show what we don\'t.','A calm, specific voice builds the credibility behind “Glacial Precision.”')
examples=[('Forecast','3.7" expected over the next 5 days. Likely range 2-6".','Lead with the useful number. Keep uncertainty beside it.'),('Grooming','Map from Fri, Nov 20. Awaiting a newer report.','Use the actual printed date; distinguish stale from missing.'),('Unavailable','Snow report unavailable. Last checked 7:05 AM MT.','Missing data is not zero snowfall.'),('Source timing','Resort snow: 5:30 AM MT. Forecast valid: 7 AM MT.','Keep saved-report, observation and forecast times separate.')]
for i,(name,example,why) in enumerate(examples):
 y=170+i*85;label(name,48,y+3);txt(example,220,y,16,'Plex600');txt(why,220,y+32,12,'Plex',MUTED);line(220,y+65,912,y+65,LINE,.6)
txt('Avoid guaranteed conditions, “perfect accuracy,” unexplained precision and hype that outruns the data.',48,532,12,'Plex600',BLUE)

# 20 / COMPANIONS
new('Supporting marks','A family with clear roles.','Companions support a section or a story; the gauge zero remains the primary identity.')
items=[('21A / Core Groomer','Grooming reports','Selected companion direction. Prepare its own vector master before small UI or print use.',A/'companions/21-groomer-reference.png',(35,172,258,176)),('48 / Resort Fold','Trail maps & grooming','Family shortlisted. 48B shown as a corduroy direction; no final family variant is frozen.',A/'companions/48-resort-fold-reference.png',(985,350,184,117)),('55B / Powder Boots','Friendly brand moments','Selected character direction. Keep it for onboarding, editorial and merchandise, not critical status.',A/'companions/55-stake-scout-reference.png',(980,335,198,145))]
for i,(id,role,desc,p,r) in enumerate(items):
 x=48+i*294;box(x,166,276,190,'#EDF7FE',18);ref(p,r,x+35,194,206,135)
 label(id,x,378);txt(role,x,405,20,'Outfit600');para(desc,x,443,255,13,color=MUTED)

# 21 / BRAND GRAPHICS
new('Supporting graphics','The snowline and the corduroy.','Use the product\'s own visual ideas to create a recognizable graphic language.')
box(48,166,414,245,NAVY,20)
c.saveState();p=c.beginPath();p.roundRect(48,H-411,414,245,20);c.clipPath(p,stroke=0)
p=c.beginPath();p.moveTo(48,H-411);p.lineTo(48,H-330);p.curveTo(176,H-359,258,H-230,462,H-295);p.lineTo(462,H-411);p.close();c.setFillColor(col(GLACIER));c.drawPath(p,stroke=0,fill=1);c.restoreState()
label('SNOWLINE',72,191,GLACIER);txt('A quiet change in level.',72,222,26,'Outfit600','#E7F2FC')
box(490,166,422,245,ICE,20)
c.saveState();p=c.beginPath();p.roundRect(490,H-411,422,245,20);c.clipPath(p,stroke=0)
for i in range(15):
 p=c.beginPath();p.moveTo(475,H-(246+i*13));p.curveTo(633,H-(193+i*13),723,H-(344+i*13),935,H-(254+i*13));c.setStrokeColor(col('#8DC4EB'));c.setLineWidth(2);c.drawPath(p)
c.restoreState();label('CORDUROY',514,191)
block('Snowline', 'A single continuous curve can divide a campaign, report cover or package. Keep it separate from quantitative chart axes.',48,440,388)
block('Corduroy', 'Parallel cuts suggest a freshly groomed run. Use them on supporting graphics, not through body text or the approved logo.',490,440,395)

# 22 / APPLICATIONS
new('Print & merchandise','Make the mark work in the world.','Flat layout studies for print and production discussion, not press-ready artwork or physical mockups.')
# Report cover / hang tag / signage
box(48,167,250,316,ICE,8);logo(68,192,210);txt('Glacial',68,297,29,'Outfit600');txt('Precision',68,332,29,'Outfit600');label('MOUNTAIN FIELD NOTES',68,407);txt('Forecasts / Grooming / Resort guides',68,448,9,'Plex',MUTED)
box(335,167,201,316,'#FFFFFF',12,LINE,.6);logo(400,207,70,'symbol');txt('0xSnow',435,342,23,'Outfit600',INK,'center');txt('Glacial Precision',435,380,12,'Plex',MUTED,'center');line(355,414,516,414,LINE);label('MERCHANDISE TAG',355,447)
box(573,167,339,142,NAVY,14);logo(602,194,280,'inverse');txt('Glacial Precision',742,273,15,'Plex','#E7F2FC','center')
box(573,331,339,152,ICE,14);txt('A small signature.',596,355,24,'Outfit600');para('Embroidery: simplify only after approval. Preserve the counter and ticks. Screen print: two-color flat art. Signage: use vector paths.',596,398,289,13)
txt('Proof minimum stroke widths, actual-size legibility and spot-color matches with the producer. CMYK is substrate/profile dependent.',48,521,12,'Plex',MUTED)

# 23 / DIGITAL
new('Digital applications','A compact identity with room to grow.','App tile, report masthead and social card directions. These specimens are not exported install icons.')
box(48,168,211,211,ICE,42);logo(113,199,78,'symbol')
label('APP TILE / FLAT DIRECTION',48,400);para('Use the compact symbol. Keep the artwork inside a central circle with radius 40% of the tile width. Proof masks before export.',48,428,211,12)
box(297,168,615,130,'#FFFFFF',16,LINE,.6);logo(319,190,225);txt('Your morning report',319,253,20,'Outfit600');txt('Beaver Creek / Sat, Nov 21',889,261,12,'Plex',MUTED,'right')
box(297,319,615,193,NAVY,18);texture(298,320,613,191,.25);logo(321,341,260,'inverse');txt('Glacial Precision',321,429,30,'Outfit600','#E7F2FC');txt('Snow forecasts. Grooming reports. Resort guides.',321,476,13,'Plex','#BDCEDC')
txt('Use a calm, opaque email surface. Keep social headlines outside the logo clear space. No slogan in the app tile.',297,531,11,'Plex',MUTED)

# 24 / TRANSITION
new('Adoption & handoff','A new identity, with a careful handover.','This guide proposes the 0xSnow system. The website and installed app have not been changed by this work.')
cols=[48,351,654]
block('Preserve', 'The selected 04S-C-A light wordmark; its aligned baseline, open counter, two ticks and snow base. Keep the blue chart language, source labels and app navigation.',cols[0],173,253)
block('Use the masters', 'Primary vectors and selected Balanced A-01 are supplied. Preserve their exact paths and IDs. Proof small sizes, app masks, print and embroidery for the actual use.',cols[1],173,253)
block('Apply', 'Swap brand assets only after vector proof approval. Update headers, email, manifest icons, social previews and documentation together; preserve data behavior.',cols[2],173,253)
box(48,365,864,166,ICE,18)
label('ASSET STATUS',72,387)
txt('Selected identities',72,421,16,'Plex600');txt('04S-C-A primary / Balanced A-01 alternate',335,422,13,'Plex')
txt('Working slogan',72,454,16,'Plex600');txt('Glacial Precision - candidate, not permanently locked',335,455,13,'Plex')
txt('Ready to reuse',72,487,16,'Plex600');txt('Logo vectors, guide, tokens, fonts and navigation SVGs',335,488,13,'Plex')

# 25 / SOURCE OF TRUTH
new('Sources & package','A practical source of truth.','Use the packaged specification and asset manifest to keep future changes intentional.')
block('Design evidence', 'Primary: frozen 04S-C-A vectors and original reference. Selected alternate: Balanced A-01, with exact study paths. Companions: 21A, 48 family and 55B raster boards.',48,170,400)
block('Product evidence', 'Local app snapshot: ysgjay/beaver-creek-grooming-bot, commit 95662ad, dated Nov 17, 2026. Reviewed BRAND.md, frost.css, dark.css, frost-surfaces.css and navigation SVGs. No claim of a fresh live-site audit.',510,170,402)
line(48,318,912,318,LINE)
label('IN THE KIT',48,339)
para('Brand-Specification.md / Agent-Handoff.md\ntokens.css / tokens.json / contrast-checks.json\nasset-manifest.json / assets/ / source/',48,370,412,14,'Mono',INK,25)
label('REFERENCE LINKS',510,339)
links=[('W3C / text contrast','https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html'),('W3C / non-text contrast','https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html'),('web.dev / maskable app icons','https://web.dev/articles/maskable-icon')]
for i,(s,url) in enumerate(links):
 yy=373+i*29;txt(s,510,yy,13,'Plex',BLUE);c.linkURL(url,(510,H-yy-17,900,H-yy+2),relative=0)
para('Font licenses are included with Outfit, IBM Plex Sans and IBM Plex Mono. The logo lettering is custom exploratory artwork, not one of these fonts.',510,477,390,11,color=MUTED)
txt('Edition 1.1 / 21 November 2026 / Balanced A-01 selected. Primary and alternate SVG/PDF paths supplied.',48,532,10,'Plex600',BLUE)

c.save()
sheet=PdfWriter();sheet.add_page(PdfReader(OUT/'0xSnow-Brand-Guide.pdf').pages[balanced_page-1])
sheet.add_metadata({'/Title':'0xSnow / Balanced A-01 / Selected alternate brand sheet','/Author':'0xSnow'})
sheet.write(OUT/'0xSnow-Balanced-Brand-Sheet.pdf')
(OUT/'source/layout-check.json').write_text(json.dumps({'pages':page,'balancedPage':balanced_page,'issues':issues},indent=2))
(OUT/'source/guide-text.txt').write_text('\n'.join(allcopy)+'\n')
print('Built',page,'pages; page-boundary text issues:',len(issues))
if issues:print(issues)

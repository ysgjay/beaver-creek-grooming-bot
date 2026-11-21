"""Export the selected Balanced alternate directly from frozen paths."""
from pathlib import Path
import json,re
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
O=Path(__file__).resolve().parents[1]
G=json.loads((O/'source/geometry.json').read_text())
S=json.loads((O/'selection.json').read_text())['selected_alternate']['spec']
def path(c,d):
 t=re.findall(r'[MLCZ]|-?\d+(?:\.\d+)?',d);p=c.beginPath();i=0
 while i<len(t):
  op=t[i];i+=1
  if op=='Z':p.close();continue
  n=6 if op=='C' else 2;v=[float(k) for k in t[i:i+n]];i+=n
  {'M':p.moveTo,'L':p.lineTo,'C':p.curveTo}[op](*v)
 return p
def gd(n):return ' '.join(p['d'] for p in G['glyphs'][n])
for theme,ink in [('light','#071B2E'),('dark','#E7F2FC')]:
 c=canvas.Canvas(str(O/'assets/alternate'/f'04S-C-A-alt-A-01-{theme}.pdf'),pagesize=(810,216))
 c.setTitle('0xSnow / Balanced A-01 / selected raised-x alternate / '+theme);c.setAuthor('0xSnow')
 c.translate(14,186);c.scale(1,-1);c.setFillColor(HexColor(ink));c.drawPath(path(c,G['gauge_ink']),fill=1,stroke=0)
 c.saveState();c.clipPath(path(c,G['gauge_outer']),fill=0,stroke=0);c.setFillColor(HexColor('#29C3FE'));c.drawPath(path(c,G['snow_plane']),fill=1,stroke=0);c.restoreState()
 b=G['glyphs']['x'][0]['bounds'];c.saveState();c.translate(S['x']-b[0]*S['scale'],S['y']-b[1]*S['scale']);c.scale(S['scale'],S['scale']);c.setFillColor(HexColor(ink));c.drawPath(path(c,gd('x')),fill=1,stroke=0,fillMode=0);c.restoreState()
 c.translate(S['snowX'],0);c.setFillColor(HexColor(ink))
 for n in 'Snow':c.drawPath(path(c,gd(n)),fill=1,stroke=0,fillMode=0)
 c.showPage();c.save()
print('Exported exact selected Balanced light/dark PDFs.')

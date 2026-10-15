"""Render matching vector and small raster favicons from one guitar drawing."""
from pathlib import Path
from PIL import Image,ImageDraw

BODY=[('M',27,28),('C',20,26,17,30,18,35),('C',19,39,23,39,22,42),
      ('C',21,45,15,46,15,52),('C',15,59,22,62,32,62),
      ('C',42,62,49,59,49,52),('C',49,46,43,45,42,42),
      ('C',41,39,45,39,46,35),('C',47,30,44,26,37,28),('Z',)]
WOOD='#c3a882';IVORY='#eee9df';DARK='#181916';NECK='#493b2b'

def artwork():
 path=' '.join(command[0]+' '.join(str(n) for n in command[1:]) for command in BODY)
 layers=[f'<path d="{path}" fill="{WOOD}" stroke="{IVORY}" stroke-width="1.2"/>',
         f'<rect x="28.5" y="12" width="7" height="21" rx=".7" fill="{NECK}" stroke="{IVORY}" stroke-width="1"/>',
         f'<path d="M26 3Q32 1 38 3L37 15H27Z" fill="{WOOD}" stroke="{IVORY}" stroke-width="1"/>']
 for y in (5.5,9,12.5):
  for x in (25.5,38.5):layers.append(f'<circle cx="{x}" cy="{y}" r="1.2" fill="{IVORY}"/>')
 for x in (28,34):layers.append(f'<rect x="{x}" y="4.5" width="2" height="7" rx="1" fill="{DARK}"/>')
 for y in (18,22,26,30):layers.append(f'<path d="M29 {y}h6" stroke="{WOOD}" stroke-width=".65"/>')
 layers.extend([f'<circle cx="32" cy="36" r="6" fill="none" stroke="{NECK}" stroke-width="1.2"/>',
                f'<circle cx="32" cy="36" r="4.5" fill="{DARK}" stroke="{IVORY}" stroke-width=".8"/>',
                f'<rect x="25.5" y="51" width="13" height="3" rx=".7" fill="{NECK}"/>'])
 for x in (30.3,31,31.65,32.35,33,33.7):
  layers.append(f'<path d="M{x} 14V53" stroke="{IVORY}" stroke-width=".4" opacity=".65"/>')
 return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><title>Guitare classique — Guitarreria.eu</title><g transform="rotate(25 32 32)">'+''.join(layers)+'</g></svg>\n'

def render(size=256):
 scale=12
 image=Image.new('RGBA',(64*scale,64*scale))
 draw=ImageDraw.Draw(image)
 def box(values):return tuple(round(v*scale) for v in values)
 def rounded(values,radius,fill,outline=None,width=1):
  draw.rounded_rectangle(box(values),radius=round(radius*scale),fill=fill,outline=outline,width=round(width*scale))
 points=[];current=None;start=None
 for command in BODY:
  if command[0]=='M':current=start=command[1:];points.append(current)
  elif command[0]=='C':
   a,b,c=command[1:3],command[3:5],command[5:7]
   for step in range(1,33):
    t=step/32;u=1-t
    points.append(tuple(u**3*current[i]+3*u*u*t*a[i]+3*u*t*t*b[i]+t**3*c[i] for i in (0,1)))
   current=c
  else:points.append(start)
 points=[box(p) for p in points]
 draw.polygon(points,fill=WOOD);draw.line(points,fill=IVORY,width=round(1.2*scale),joint='curve')
 rounded((28.5,12,35.5,33),.7,NECK,IVORY)
 head=[box(p) for p in ((26,3),(32,2),(38,3),(37,15),(27,15),(26,3))]
 draw.polygon(head,fill=WOOD);draw.line(head,fill=IVORY,width=scale,joint='curve')
 for y in (5.5,9,12.5):
  for x in (25.5,38.5):draw.ellipse(box((x-1.2,y-1.2,x+1.2,y+1.2)),fill=IVORY)
 for x in (28,34):rounded((x,4.5,x+2,11.5),1,DARK)
 for y in (18,22,26,30):draw.line((box((29,y)),box((35,y))),fill=WOOD,width=round(.65*scale))
 draw.ellipse(box((26,30,38,42)),outline=NECK,width=round(1.2*scale))
 draw.ellipse(box((27.5,31.5,36.5,40.5)),fill=DARK,outline=IVORY,width=round(.8*scale))
 rounded((25.5,51,38.5,54),.7,NECK)
 for x in (30.3,31,31.65,32.35,33,33.7):
  draw.line((box((x,14)),box((x,53))),fill='#dfd2b9',width=round(.4*scale))
 return image.rotate(-25,resample=Image.Resampling.BICUBIC).resize((size,size),Image.Resampling.LANCZOS)

def main():
 root=Path(__file__).resolve().parents[1]
 target=root/'tools/branding' if (root/'audit').exists() else root/'source/branding'
 target.mkdir(parents=True,exist_ok=True)
 (target/'favicon.svg').write_text(artwork(),encoding='utf-8')
 render(32).save(target/'favicon-32.png')
 render(256).save(target/'favicon.ico',format='ICO',sizes=[(16,16),(32,32),(48,48)])
 print(target)

if __name__=='__main__':main()

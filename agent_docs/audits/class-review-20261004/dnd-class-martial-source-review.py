import hashlib,json,math
from pathlib import Path
import numpy as np
from PIL import Image
from game.weapon_trail_media import source_trail_pixels
root=Path.cwd();receipt=json.loads((root/'game/data/class_media/weapon-trails-source.json').read_text())
source=Path(receipt['source']);assert hashlib.sha256(source.read_bytes()).hexdigest()==receipt['source_sha256']
rows=json.loads((root/'game/data/class_media/weapon-trails.json').read_text())['presentation']['poses']
by={(row['category'],row['clip']):row for row in rows}
original=json.loads((source.parent/'project/StrikePaths.json').read_text())['paths']
headings=('E','SE','S','SW','W','NW','N','NE');count=0
for record in receipt['source_sheets']:
    path=root/record['file'];assert hashlib.sha256(path.read_bytes()).hexdigest()==record['sha256']
    image=np.array(Image.open(path).convert('RGBA'));pose=by[(record['category'],record['clip'])]
    for heading,direction in enumerate(headings):
        for frame,point in enumerate(pose['pointsByFacing'][direction]):
            cell=image[heading*128:(heading+1)*128,frame*128:(frame+1)*128]
            y,x=np.where(cell[:,:,3]>120)
            if len(x):
                distances=(x-64)**2+(y-66)**2;selected=distances>=np.quantile(distances,.84)
                expected={'x':round(float(x[selected].mean()),3),'y':round(float(y[selected].mean()),3)}
            else:expected=None
            assert point==expected,(record['category'],record['clip'],direction,frame,point,expected)
            if record['category']=='Melee1' and record['clip']=='Attack1':assert [point['x'],point['y']]==original[heading][frame]
            count+=1
# Literal source shader/pack equations, independent scalar group accumulation.
rng=np.random.default_rng(4);uv=rng.random((12,10,2));owned=rng.random((12,10))>.15
palette=(0x642b2b,0xbf5745,0xe4ccb1);levels=(26,49,78,109,143,177,211,239)
cases=0
for age in (.18,.5,.73,.92):
    for step in (1.,1.5,2.,4.):
        origin=(3.25,-5.75);groups={};values={};actual=source_trail_pixels(uv,owned,age,palette,sample_pixels=step,origin=origin)
        for x in range(12):
            for y in range(10):
                u,v=uv[x,y];edge=math.sin(v*math.pi);ridge=edge**6
                t=max(0.,min(1.,(age-.67)/.27));fade=1-t*t*(3-2*t)
                alpha=max(0.,min(1.,edge*u*(.65+.35*math.sin(u*48+v*14))*fade*.92))*owned[x,y]
                energy=(1.055*(.25+.6*ridge)**(1/2.4)-.055)*255
                group=(math.floor((x+origin[0])/step),math.floor((y+origin[1])/step))
                groups.setdefault(group,[]).append((alpha,energy));values[x,y]=(alpha,group)
        for (x,y),(alpha,group) in values.items():
            weight=sum(a for a,e in groups[group]);value=sum(a*e for a,e in groups[group])/weight if weight else 0
            selected=min(levels,key=lambda n:abs(value-n));position=selected/239*2;index=min(1,math.floor(position));mix=position-index
            left,right=palette[index:index+2];rgb=[math.floor(((left>>shift)&255)*(1-mix)+((right>>shift)&255)*mix+.5) for shift in (16,8,0)]
            a=round(alpha*255);expected=rgb+[a] if a>=3 else [0,0,0,0]
            assert list(actual[x,y])==expected,(age,step,x,y,list(actual[x,y]),expected)
        cases+=1
print(f'{len(rows)} source sheets / {count} measured cells exact; original 120 points exact; {cases} scalar shader/palette registration cases exact')

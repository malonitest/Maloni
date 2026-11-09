"""Original smooth illustrative SUV meshes. No manufacturer CAD or third-party assets."""
import math
import xml.etree.ElementTree as E


def add_vehicle(asset, world, directory, key, center, length, color, variant):
    x,y=center
    def geom(name,pos,size,material,kind='box',**kw):
        return E.SubElement(world,'geom',name=key+'_'+name,type=kind,pos=' '.join(map(str,(x+pos[0],y+pos[1],pos[2]))),size=' '.join(map(str,size)),material=material,contype='0',conaffinity='0',**kw)
    def rod(name,a,b,radius,material):
        E.SubElement(world,'geom',name=key+'_'+name,type='capsule',fromto=' '.join(map(str,(x+a[0],y+a[1],a[2],x+b[0],y+b[1],b[2]))),size=str(radius),material=material,contype='0',conaffinity='0')
    def mesh(name,rings,material):
        verts=[v for ring in rings for v in ring];n=len(rings[0]);faces=[]
        for k in range(1,n-1):faces.append((0,k+1,k))
        for j in range(len(rings)-1):
            for k in range(n):
                a=j*n+k;b=j*n+(k+1)%n;faces.extend([(a,b,b+n),(a,b+n,a+n)])
        last=(len(rings)-1)*n
        for k in range(1,n-1):faces.append((last,last+k,last+k+1))
        path=directory/(key+'_'+name+'.obj')
        path.write_text('\n'.join(['v '+' '.join(f'{a:.6f}' for a in v) for v in verts]+['f '+' '.join(str(a+1) for a in f) for f in faces]))
        E.SubElement(asset,'mesh',name=key+'_'+name,file=str(path),smoothnormal='true')
        E.SubElement(world,'geom',name=key+'_'+name,type='mesh',mesh=key+'_'+name,pos=f'{x} {y} 0',material=material,contype='0',conaffinity='0')
    # Smoothly rounded lower body; the glasshouse is a separate, narrower loft.
    rings=[]
    for j in range(57):
        t=j/56;xx=(t-.5)*length
        width=.93-.16*(abs(2*t-1)**6)
        top=1.025+.085*math.sin(math.pi*t)
        ring=[]
        for k in range(24):
            theta=2*math.pi*k/24
            yy=width*math.copysign(abs(math.cos(theta))**.45,math.cos(theta))
            zz=.765+(top-.765)*math.copysign(abs(math.sin(theta))**.5,math.sin(theta))
            ring.append((xx,yy,zz))
        rings.append(ring)
    mesh('coachwork',rings,color)
    front=-length*.32;rear=length*(.45+variant*.005);roof=1.64+variant*.025
    cabin=[];roof_rings=[]
    for j in range(25):
        t=j/24;xx=front+t*(rear-front)
        rise=min(1,t/.24,(1-t)/.17)
        z=1.08+(roof-1.08)*max(0,rise)
        width=.83-.15*max(0,rise)
        cabin.append([(xx,-.855,1.065),(xx,.855,1.065),(xx,width,z),(xx,-width,z)])
        if .24<=t<=.83:
            roof_rings.append([(xx,-width-.015,z+.012),(xx,width+.015,z+.012),(xx,width-.01,z+.035),(xx,-width+.01,z+.035)])
    mesh('glazing',cabin,'autoglass');mesh('roof',roof_rings,color)
    # Window frames, B/C pillars, shut lines, handles and side accents.
    for side in (-1,1):
        rod('belt'+str(side),(front,side*.86,1.07),(rear,side*.86,1.07),.013,'chrome')
        for p in (.38,.72):
            xx=front+(rear-front)*p
            rod(f'pillar{side}_{p}',(xx,side*.86,1.07),(xx,side*.695,roof),.043,'dark')
        for p in (.38,.86):
            xx=front+(rear-front)*p
            rod(f'door{side}_{p}',(xx,side*.936,.61),(xx,side*.936,1.025),.006,'dark')
            geom(f'handle{side}_{p}',(xx-.14,side*.946,1.015),(.105,.018,.016),'chrome')
        rod('sill'+str(side),(-length*.34,side*.9,.48),(length*.35,side*.9,.48),.036,'dark')
        rod('rail'+str(side),(front+.48,side*.61,roof+.07),(rear-.28,side*.61,roof+.07),.021,'chrome')
        geom('mirror'+str(side),(front+.18,side*1.015,1.20),(.14,.13,.065),color,kind='ellipsoid')
        # Wheel and machined five twin-spoke alloy. Tire shoulders are rounded.
        for axle in (-length*.30,length*.30):
            label=f'{side}_{axle}'
            geom('tire'+label,(axle,side*.94,.4),(.39,.14),'rubber','cylinder',quat='.7071068 .7071068 0 0')
            geom('shoulder'+label,(axle,side*.98,.4),(.385,.17,.385),'rubber','ellipsoid')
            geom('rimwell'+label,(axle,side*1.135,.4),(.285,.012),'dark','cylinder',quat='.7071068 .7071068 0 0')
            geom('hub'+label,(axle,side*1.16,.4),(.075,.023),'chrome','cylinder',quat='.7071068 .7071068 0 0')
            for k in range(10):
                a=2*math.pi*k/10
                rod('spoke'+label+str(k),(axle+.075*math.sin(a),side*1.16,.4+.075*math.cos(a)),(axle+.26*math.sin(a+.12),side*1.16,.4+.26*math.cos(a+.12)),.017,'chrome')
            for k in range(32):
                a=2*math.pi*k/32;b=2*math.pi*(k+1)/32
                rod('rimedge'+label+str(k),(axle+.277*math.sin(a),side*1.155,.4+.277*math.cos(a)),(axle+.277*math.sin(b),side*1.155,.4+.277*math.cos(b)),.012,'chrome')
    nose=-length/2
    geom('grille',(nose-.012,0,.74),(.025,.54,.17),'dark')
    for k in range(-8,9):
        rod('grille'+str(k),(nose-.043,k*.057,.60),(nose-.043,k*.057+.02,.88),.008,'chrome')
    for side in (-1,1):
        geom('headlight'+str(side),(nose-.032,side*.66,.99),(.027,.19,.024),'led')
        geom('daylight'+str(side),(nose-.035,side*.8,.9),(.025,.022,.08),'led')
        geom('tail'+str(side),(length/2+.015,side*.61,1.0),(.022,.22,.026),'taillight')
    geom('frontplate',(nose-.065,0,.48),(.018,.23,.055),'ivory')
    geom('lowerbumper',(nose+.01,0,.44),(.06,.70,.035),'chrome')
    geom('rearbumper',(length/2-.02,0,.47),(.04,.72,.035),'chrome')

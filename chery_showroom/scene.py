"""Portable MALONI Robotics showroom using licensed reference models."""
from pathlib import Path
import os
import math
import xml.etree.ElementTree as E
from PIL import Image, ImageDraw, ImageFont
from .library_models import add_reference_vehicle,MODELS
from .architecture import add_architecture
from .furnishings import add_furnishings
from .layout import CARS, STOPS, WAYPOINTS, QUALITY
from .asset_io import save_image,write_xml
from .customer_actor import add_actor
ROOT=Path(__file__).resolve().parents[1]
ASSETS=Path(__file__).with_name('assets')
SCENE=ASSETS/'showroom.xml'

def build(quality="interactive"):
    if quality not in QUALITY:raise ValueError("Unknown quality profile")
    ASSETS.mkdir(exist_ok=True)
    model=E.Element('mujoco',model='MALONI Robotics Automotive Showroom')
    robot=E.parse(ROOT/'unitree_mujoco/unitree_robots/g1/g1_29dof.xml')
    robot.find('compiler').attrib.pop('meshdir',None)
    for mesh in robot.findall('./asset/mesh'):
        mesh.set('file',os.path.relpath(ROOT/'unitree_mujoco/unitree_robots/g1/meshes'/mesh.get('file'),ASSETS))
    for geom in robot.findall('.//geom'):
        if geom.get('contype')!='0':geom.set('group','5')
    write_xml(robot.getroot(),ASSETS/'robot.xml')
    E.SubElement(model,'include',file=str(ASSETS/'robot.xml'))
    E.SubElement(model,'statistic',center='0 1 1',extent='12')
    visual=E.SubElement(model,'visual')
    E.SubElement(visual,'global',offwidth='1280',offheight='800',azimuth='90',elevation='-28')
    E.SubElement(visual,'quality',**{key:str(value) for key,value in QUALITY[quality].items()})
    E.SubElement(visual,'map',znear='.03',zfar='120',shadowscale='.7')
    E.SubElement(visual,'headlight',ambient='.23 .25 .28',diffuse='.08 .08 .08',specular='.1 .1 .1')
    custom=E.SubElement(model,'custom')
    E.SubElement(custom,'numeric',name='filament.fallback.environment_light_intensity',data='10000')
    E.SubElement(custom,'numeric',name='filament.fallback.scene_light_intensity',data='100000')
    E.SubElement(custom,'numeric',name='filament.fallback.head_light_intensity',data='25000')
    asset=E.SubElement(model,'asset');world=E.SubElement(model,'worldbody')
    E.SubElement(custom,'text',name='filament.shadows.type',data='pcss')
    E.SubElement(asset,'texture',name='studio_environment',type='cube',builtin='gradient',rgb1='.86 .87 .88',rgb2='.62 .64 .67',width='256',height='1536')
    E.SubElement(asset,'texture',name='daylight',type='skybox',builtin='gradient',rgb1='.48 .61 .72',rgb2='.91 .94 .96',width='512',height='3072')
    colors={'ivory':'.85 .85 .81 1','dark':'.045 .055 .065 1','metal':'.5 .55 .58 1','glass':'.55 .7 .76 .12','rubber':'.025 .025 .028 1','wood':'.43 .28 .16 1','red':'.6 .025 .04 1','white':'.86 .9 .92 1','blue':'.06 .2 .34 1','leaf':'.08 .24 .12 1','lamp':'1 .94 .82 1','autoglass':'.018 .038 .05 1','chrome':'.7 .76 .8 1','led':'.86 .95 1 1','taillight':'.9 .025 .035 1','display':'.22 .25 .26 1','wallpanel':'.075 .09 .105 1','diffuser':'.70 .72 .73 1'}
    for name,c in colors.items():E.SubElement(asset,'material',name=name,rgba=c,specular='.35' if name in ('ivory','dark','rubber','wood','leaf','wallpanel') else '.75',shininess='.25' if name in ('ivory','dark','rubber','wood','leaf','wallpanel') else '.85',**({'emission':'.6'} if name in ('lamp','led','taillight','diffuser') else {}))
    def geom(name,pos,size,mat='ivory',kind='box',collision=False,**kw):
        node=E.SubElement(world,'geom',name=name,type=kind,pos=' '.join(map(str,pos)),size=' '.join(map(str,size)),material=mat,group=kw.pop('group','5' if collision else '2'),contype='1' if collision else '0',conaffinity='1' if collision else '0',**kw)
        if collision and float(node.get('rgba','0 0 0 1').split()[-1])>0:
            visual=dict(node.attrib);visual.update(name=name+'_visual',group='2',contype='0',conaffinity='0');E.SubElement(world,'geom',visual)
        return node
    def sign(name,text,pos,size):
        im=Image.new('RGB',(1200,300),'#172127');d=ImageDraw.Draw(im);f=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',66)
        for i,line in enumerate(text.split('\n')):d.text((45,25+i*95),line,font=f,fill='#f4f1e7')
        save_image(im,ASSETS/(name+'.png'))
        E.SubElement(asset,'texture',name=name,type='2d',file=str(ASSETS/(name+'.png')))
        E.SubElement(asset,'material',name=name,texture=name,texuniform='false',specular='.08',emission='.12')
        geom(name,pos,size,name)
    geom('floor',(0,0,-.08),(10,8,.08),collision=True,rgba='0 0 0 0')
    geom('floor_finish',(0,0,.0001),(9,6.1,.01),'stone','plane')
    for x in range(-10,11):geom('tilex'+str(x),(x,0,.001),(.003,8,.001),'metal')
    for y in range(-8,9):geom('tiley'+str(y),(0,y,.001),(10,.003,.001),'metal')
    geom('back',(0,7,2.4),(10,.12,2.4),collision=True)
    geom('featurewall',(0,6.85,2.45),(8.5,.025,2.2),'wallpanel')
    for slat in range(-32,33):geom('slat'+str(slat),(slat*.255,6.80,2.45),(.015,.025,2.15),'wood')
    geom('brandpanel',(0,6.72,3.1),(4.3,.045,.85),'dark')
    for x in (-9,9):
        geom('side'+str(x),(x,0,2.4),(.08,7,2.4),'glass',collision=True)
        for y in range(-6,8,2):geom(f'pillar{x}_{y}',(x,y,2.4),(.09,.06,2.4),'metal')
    for x in (-6,-3,3,6):geom('front'+str(x),(x,-6,2.3),(1.48,.05,2.3),'glass',collision=True)
    sign('brand','MALONI ROBOTICS\nAUTOMOTIVE DEMONSTRATION',(0,6.64,3.25),(4,.04,.7))
    for x in (-5,0,5):
        E.SubElement(world,'light',pos=f'{x} 3.5 4.6',dir='0 0 -1',diffuse='.38 .41 .46',specular='.5 .55 .6',attenuation='1 .04 .015',castshadow='false')
        geom('ceilingframe'+str(x),(x,3.5,4.6),(2.15,1.35,.035),'dark')
        geom('ceilingdiffuser'+str(x),(x,3.5,4.555),(2.02,1.19,.008),'diffuser')
        for dx in (-1.75,1.75):geom(f'suspension{x}_{dx}',(x+dx,3.5,4.8),(.012,.012,.2),'metal')
        for dy in (-1.2,1.2):geom(f'ceilingled{x}_{dy}',(x,3.5+dy,4.55),(2.05,.035,.018),'led')
    for x in (-6,0,6):
        E.SubElement(world,'light',pos=f'{x} -2 4.8',dir='0 0 -1',diffuse='.5 .48 .43',specular='.7 .65 .58',attenuation='1 .04 .015',cutoff='70',exponent='2',bulbradius='.6',castshadow='true')
        geom('light'+str(x),(x,-2,4.8),(2.2,.07,.025),'lamp')
    E.SubElement(world,'light',name='window_daylight',pos='-7 -5 4',dir='.35 .7 -.5',directional='true',diffuse='.65 .68 .72',specular='.65 .7 .75',castshadow='true')
    geom('reception',(-5,-3.7,.55),(1.5,.5,.55),'wood',collision=True)
    sign('welcome','MALONI ROBOTICS\nWELCOME / RECEPTION',(-5,-4.22,.64),(1.20,.02,.32))
    geom('reception_screen',(-5,-3.7,1.43),(.4,.035,.23),'dark')
    geom('reception_stem',(-5,-3.7,1.23),(.035,.06,.12),'metal')
    geom('counter',(-5,-3.7,1.13),(1.6,.58,.05),'dark')
    for x in (5.7,7.5):
        geom('sofa'+str(x),(x,-3.7,.4),(.65,1,.32),'dark',collision=True)
        geom('backrest'+str(x),(x+.5,-3.7,.85),(.15,1,.35),'dark')
    geom('coffee',(6.5,-3.7,.4),(.25,.5,.04),'wood',collision=True)
    for x in (-7,7):
        for side in (-1,1):
            geom(f'chair{x}_{side}',(x,5.8+side*.9,.44),(.33,.32,.08),'dark')
            geom(f'chairback{x}_{side}',(x,5.8+side*1.15,.75),(.33,.06,.32),'dark')
            for dx in (-.24,.24):geom(f'chairleg{x}_{side}_{dx}',(x+dx,5.8+side*.9,.2),(.025,.025,.2),'metal')
        geom('table'+str(x),(x,5.8,.75),(.65,.5,.05),'wood',collision=True)
        geom('leg'+str(x),(x,5.8,.36),(.08,.08,.36),'metal',collision=True)
        geom('pot'+str(x),(x,-5,.25),(.28,.25),'dark','cylinder',True)
        geom('plant'+str(x),(x,-5,.95),(.4,.4,.65),'leaf','ellipsoid')
    add_architecture(asset,world,ASSETS,geom)
    add_furnishings(asset,world,geom)
    for i,(key,(x,y,length)) in enumerate(CARS.items()):
        col=['red','white','blue'][i]
        title,halfwidth=add_reference_vehicle(asset,world,key,x,y)
        geom(key+'_collision',(x,y,.85),(length/2+.03,halfwidth+.03,1.0),'glass',collision=True,rgba='0 0 0 0')
        geom(key+'_display',(x,y,.006),(length/2+.22,1.28,.006),'display')
        geom(key+'_stand',(x+1.9,1.65,.58),(.4,.22,.58),'dark',collision=True,rgba='0 0 0 0')
        geom(key+'_standfoot',(x+1.9,1.65,.035),(.4,.25,.035),'metal')
        geom(key+'_standpost',(x+1.9,1.65,.48),(.045,.055,.45),'metal')
        sign(key+'_label',title.upper()+'\nVEHICLE '+str(i+1)+' / DEMONSTRATION\nINDEPENDENT SIMULATION',(x+1.9,1.40,1.0),(.49,.025,.19))
    for name,pos,xy in [('overview','0 -11 8','1 0 0 0 .65 .76'),('customer','-1 -5.1 1.65','1 0 0 0 0 1')]:
        E.SubElement(world,'camera',name=name,pos=pos,xyaxes=xy,fovy='62' if name=='overview' else '66')
    E.SubElement(world,'camera',name='entrance',pos='1.5 .5 1.65',xyaxes='-1 0 0 0 0 1',fovy='70')
    for key,(x,y,length) in CARS.items():
        E.SubElement(world,'camera',name='hero_'+key,pos=f'{x-2.6} {y-3.2} 1.55',xyaxes='.776 -.631 0 .070 .086 .994',fovy='57')
    E.SubElement(world,'camera',name='cinematic',pos='0 -4 1.5',xyaxes='1 0 0 0 0 1',fovy='48')
    # A world camera is updated from the pelvis each rendered frame by the runtime.
    E.SubElement(world,'camera',name='robot',pos='0 0 1.25',xyaxes='0 -1 0 0 0 1')
    # Physical light units are consumed by installed Filament; classic OpenGL keeps its legacy colours.
    for light in world.findall('light'):
        light.set('intensity','25000' if light.get('directional')=='true' else '7000')
    E.SubElement(world,'light',name='environment_fill',type='image',texture='studio_environment',intensity='10000')
    for name,xy in WAYPOINTS.items():
        E.SubElement(world,'site',name=name,pos=f'{xy[0]} {xy[1]} .025',size='.025',rgba='.12 .7 .65 0',group='5')
    def camera(name,pos,target,fovy):
        import numpy as np
        p=np.array(pos);forward=np.array(target)-p;forward=forward/np.linalg.norm(forward)
        right=np.cross(forward,[0,0,1]);right/=np.linalg.norm(right);up=np.cross(right,forward)
        E.SubElement(world,'camera',name=name,pos=' '.join(map(str,pos)),xyaxes=' '.join(map(str,[*right,*up])),fovy=str(fovy))
    camera('showroom_overview',(0,-10,7),(0,1.4,1),64)
    camera('entrance_view',(0,-5.15,1.65),(0,3.3,1.1),72)
    camera('reception_view',(-.1,-5.1,1.7),(-4,-2.9,.9),64)
    camera('vehicle_demo_view',(3,-3.6,1.8),(5.8,2.3,1.1),58)
    camera('furniture_detail',(6,-2,1.2),(5.5,-3.7,.55),50)
    camera('detail_view',(3.35,1.45,.72),(4.6,3.1,.65),42)
    add_actor(world)
    for node in model.iter():
        if node.get('file') and Path(node.get('file')).is_absolute():
            node.set('file',os.path.relpath(node.get('file'),ASSETS))
    E.indent(model)
    destination=SCENE if quality=='interactive' else SCENE.with_name('showroom_presentation.xml')
    write_xml(model,destination)
    return destination
if __name__=='__main__':print(build())

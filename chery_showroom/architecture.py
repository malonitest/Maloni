"""Original architectural finishes and real-scale dealership furnishings."""
import math
import xml.etree.ElementTree as E
import numpy as np
from PIL import Image
from .asset_io import save_image


def add_architecture(asset,world,directory,geom):
    rng=np.random.default_rng(902)
    def finish(name,base,noise,repeat='1 1',wood=False):
        h,w=384,384
        texture=rng.normal(0,noise,(h,w))
        if wood:
            yy,xx=np.mgrid[:h,:w];texture+=7*np.sin(xx*.22+2*np.sin(yy*.012))
        pixels=np.clip(np.asarray(base)[None,None,:]+texture[:,:,None],0,255).astype('uint8')
        path=directory/(name+'_finish.png');save_image(Image.fromarray(pixels),path)
        E.SubElement(asset,'texture',name=name+'_texture',type='2d',file=str(path))
        material=asset.find(f"material[@name='{name}']")
        if material is None:material=E.SubElement(asset,'material',name=name,rgba='1 1 1 1')
        material.set('texture',name+'_texture');material.set('rgba','1 1 1 1');material.set('texrepeat',repeat);material.set('texuniform','true')
    finish('stone',(184,183,176),1.8,repeat='.5 .5')
    finish('wood',(133,103,76),1.5,wood=True)
    finish('upholstery',(66,76,81),2.0,repeat='3 3')
    finish('asphalt',(58,61,63),4,repeat='1 1')
    E.SubElement(asset,'material',name='paper',rgba='.91 .9 .86 1',specular='.05')
    E.SubElement(asset,'material',name='grass',rgba='.25 .34 .20 1',specular='.03')
    E.SubElement(asset,'material',name='concrete',rgba='.55 .56 .54 1',specular='.1')
    asset.find("material[@name='stone']").set('reflectance','0')
    asset.find("material[@name='stone']").set('roughness','.55')
    asset.find("material[@name='stone']").set('metallic','0')
    asset.find("material[@name='stone']").set('specular','.14')
    # A ceiling and finished façade give eye-level shots an enclosed building.
    geom('ceiling',(0,.5,5.05),(9,6.6,.10),'ivory',group='4')
    for x in (-6,-3,0,3,6):
        geom('ceiling_seam'+str(x),(x,.5,4.94),(.008,6.4,.007),'metal',group='4')
    for x in (-9,9):
        geom('fascia'+str(x),(x,.4,4.75),(.16,6.6,.2),'ivory',group='4')
        geom('skirting'+str(x),(x,.4,.12),(.12,6.6,.12),'metal')
    geom('front_header',(0,-6.05,4.45),(9,.14,.5),'ivory',group='4')
    for x in (-7.5,-4.5,-1.5,1.5,4.5,7.5):
        geom('entrance_mullion'+str(x),(x,-6.04,2.1),(.035,.07,2.1),'metal',collision=True)
    for side in (-1,1):
        geom('entrance_door'+str(side),(side*.75,-6.05,1.4),(.72,.025,1.4),'glass',collision=True)
        geom('door_rail'+str(side),(side*.75,-6.09,2.8),(.75,.035,.025),'metal')
        geom('door_handle'+str(side),(side*.16,-5.98,1.2),(.018,.045,.25),'metal')
        for x in (.1,.5,.9):geom(f'door_safety{side}_{x}',(side*x,-5.998,1.45),(.09,.002,.025),'white')
    # Customer arrival: paving, marked parking, greenery and street beyond the glass.
    geom('forecourt',(0,-8,-.055),(14,2,.05),'concrete')
    geom('road',(0,-16,-.065),(24,6,.06),'asphalt')
    geom('curb',(0,-10,.065),(14,.10,.065),'ivory')
    for x in range(-12,14,3):
        geom('parking_mark'+str(x),(x,-12.7,.002),(.035,1.9,.002),'white')
    for x in (-3,3,-7,7):
        geom('bollard'+str(x),(x,-7,.4),(.065,.4),'metal','cylinder')
    for x in (-12,12):
        geom('landscaping'+str(x),(x,-5,.08),(1.2,4,.08),'grass')


    for x in (-15,0,15):
        geom('neighbour'+str(x),(x,-27,3.0),(5,3,3),'concrete')
        for row in range(2):
            for k in range(6):geom(f'neighbour_window{x}_{row}_{k}',(x-4+k*1.55,-23.98,1.5+row*2),(.5,.025,.6),'autoglass')
    for x in (-6.48,-3.52):
        geom('reception_edge'+str(x),(x,-4.19,.56),(.025,.53),'wood','capsule')
    geom('reception_toekick',(-5,-4.205,.08),(1.44,.025,.08),'dark')
    geom('reception_counter_edge',(-5,-4.25,1.12),(1.55,.025,.025),'metal')
    # Actual working surfaces, paperwork and upholstered seating.
    geom('reception_keyboard',(-5,-3.92,1.20),(.25,.095,.012),'dark')
    geom('reception_papers',(-4.15,-3.85,1.20),(.16,.22,.009),'paper')
    geom('reception_chair',(-5,-2.9,.43),(.35,.32,.07),'upholstery')
    geom('operator_chair_collision',(-5,-2.9,.5),(.4,.4,.5),'dark',collision=True,rgba='0 0 0 0')
    geom('reception_chair_back',(-5,-2.65,.77),(.35,.06,.32),'upholstery')
    for x in (5.7,7.5):
        geom('sofa_cushion'+str(x),(x,-3.7,.74),(.56,.89,.09),'upholstery')
        for dy in (-.9,.9):geom(f'sofa_arm{x}_{dy}',(x,-3.7+dy,.76),(.58,.11,.20),'upholstery')
        geom('sofa_back_cushion'+str(x),(x+.35,-3.7,.94),(.13,.82,.22),'upholstery')
    for x in (-7,7):
        geom('desk_laptop_base'+str(x),(x,5.8,.82),(.23,.16,.014),'metal')
        geom('desk_laptop_screen'+str(x),(x,5.95,1.0),(.23,.018,.17),'dark')
        geom('desk_brochure'+str(x),(x+.4,5.65,.82),(.12,.17,.006),'paper')
    geom('coffee_pedestal',(6.5,-3.7,.18),(.08,.18),'metal','cylinder',collision=True)
    geom('coffee_base',(6.5,-3.7,.02),(.20,.02),'metal','cylinder')
    geom('lounge_magazine',(6.5,-3.7,.45),(.14,.20,.006),'paper')
    # Multiple branches/leaves replace the previous solid oval topiary.
    for x in (-7,7):
        old=world.find(f"geom[@name='plant{x}']")
        if old is not None:world.remove(old)
        for j in range(14):
            a=j*2.399;z=.55+j*.065
            xx=x+math.cos(a)*.19;yy=-5+math.sin(a)*.19
            E.SubElement(world,'geom',name=f'plant_branch{x}_{j}',type='capsule',fromto=f'{x} -5 .5 {xx} {yy} {z}',size='.012',material='wood',contype='0',conaffinity='0')
            geom(f'plant_leaf{x}_{j}',(xx,yy,z),(.14,.065,.045),'leaf','ellipsoid',euler=f'0 .5 {a}')

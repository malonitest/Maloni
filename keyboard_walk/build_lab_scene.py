#!/usr/bin/env python3
"""Build a self-contained lab scene from native MuJoCo geometry and local signage."""
from pathlib import Path
import math
import numpy as np
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / 'unitree_mujoco/unitree_robots/g1'
ASSETS = DEST / 'lab_assets'
ASSETS.mkdir(exist_ok=True)

# Original graphics, generated locally; no external assets or downloads.
im = Image.new('RGB', (1536, 512), '#152936')
draw = ImageDraw.Draw(im)
font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
font = lambda size: ImageFont.truetype(font_path, size)
draw.rectangle((64, 66, 76, 424), fill='#56e0cf')
draw.text((112, 64), 'MALONI', font=font(96), fill='#eff8f7')
draw.text((116, 190), 'ROBOTICS LAB', font=font(57), fill='#56e0cf')
draw.line((116, 288, 1400, 288), fill='#395c6a', width=2)
draw.text((116, 336), 'G1  /  LOCOMOTION & EMBODIED INTELLIGENCE', font=font(30), fill='#b4c8cd')
im.save(ASSETS / 'lab_sign.png')

im = Image.new('RGB', (1024, 640), '#091c27')
draw = ImageDraw.Draw(im)
for x in range(40, 1000, 64): draw.line((x, 120, x, 580), fill='#163844', width=1)
for y in range(120, 600, 64): draw.line((40, y, 980, y), fill='#163844', width=1)
draw.text((45, 28), 'G1 / MOTION ANALYSIS', font=font(38), fill='#bcefe7')
for k,color in enumerate(['#51d7c5', '#6b9cec', '#e9b762']):
    points = [(x, 250+k*90+int(45*math.sin(x/80+k))) for x in range(45, 980, 3)]
    draw.line(points, fill=color, width=4)
draw.text((50, 566), 'POLICY READY    /    LOCAL SIMULATION', font=font(26), fill='#bcefe7')
im.save(ASSETS / 'monitor.png')

rng = np.random.default_rng(17)
noise = rng.normal(0, 1.6, (512, 512, 1))
concrete = np.clip(np.array([167, 177, 182]) + noise, 0, 255).astype(np.uint8)
Image.fromarray(concrete).save(ASSETS / 'concrete.png')
x = np.arange(1024)[None, :]
y = np.arange(256)[:, None]
grain = 7*np.sin(y*.25 + 2*np.sin(x*.017)) + rng.normal(0, 1.5, (256, 1024))
wood = np.clip(np.array([149, 110, 76]) + grain[..., None], 0, 255).astype(np.uint8)
Image.fromarray(wood).save(ASSETS / 'oak.png')

scene = ET.Element('mujoco', model='MALONI Robotics Laboratory')
ET.SubElement(scene, 'include', file='g1_29dof.xml')
ET.SubElement(scene, 'statistic', center='0 0 1', extent='9')
visual = ET.SubElement(scene, 'visual')
ET.SubElement(visual, 'global', azimuth='55', elevation='-12', offwidth='1600', offheight='1000')
ET.SubElement(visual, 'quality', shadowsize='4096', offsamples='4')
ET.SubElement(visual, 'headlight', ambient='.20 .22 .24', diffuse='.20 .21 .22', specular='.15 .15 .15')
ET.SubElement(visual, 'rgba', haze='.8 .86 .9 1')
ET.SubElement(visual, 'map', znear='.01', zfar='80', fogstart='20', fogend='60')
assets = ET.SubElement(scene, 'asset')
ET.SubElement(assets, 'texture', name='lab_sky', type='skybox', builtin='gradient', rgb1='.48 .65 .82', rgb2='.9 .95 .99', width='512', height='3072')
materials = {
    'floor': ('.54 .60 .63 1', '.18', '.24'),
    'wall': ('.80 .84 .86 1', '.08', '.12'),
    'metal': ('.19 .25 .30 1', '.5', '.65'),
    'white': ('.87 .91 .93 1', '.25', '.4'),
    'dark': ('.055 .085 .11 1', '.3', '.35'),
    'wood': ('.55 .37 .22 1', '.1', '.2'),
    'glass': ('.46 .73 .82 .18', '.65', '.8'),
    'teal': ('.07 .59 .56 1', '.22', '.45'),
    'amber': ('.94 .55 .14 1', '.2', '.3'),
    'leaf': ('.12 .32 .23 1', '.12', '.2'),
    'seam': ('.35 .41 .44 1', '.05', '.1'),
}
for name,(rgba,specular,shininess) in materials.items():
    ET.SubElement(assets, 'material', name='lab_'+name, rgba=rgba, specular=specular, shininess=shininess)
for name,file,repeat in [('floor','concrete.png','1 1'),('wood','oak.png','1 1')]:
    ET.SubElement(assets, 'texture', name='lab_'+name+'_finish', type='2d', file='lab_assets/'+file)
    mat = assets.find(f"material[@name='lab_{name}']")
    mat.set('texture','lab_'+name+'_finish')
    mat.set('rgba','1 1 1 1')
    mat.set('texrepeat',repeat)
    mat.set('texuniform','true' if name == 'floor' else 'false')

for name,color in [('strip', '.35 .94 .85 1'), ('light', '.98 .97 .90 1')]:
    ET.SubElement(assets, 'material', name='lab_'+name, rgba=color, emission='.8', specular='.2')
for name,file in [('sign','lab_sign.png'),('screen','monitor.png')]:
    ET.SubElement(assets, 'texture', name='lab_'+name+'_tex', type='2d', file='lab_assets/'+file)
    ET.SubElement(assets, 'material', name='lab_'+name, texture='lab_'+name+'_tex', texrepeat='1 1', texuniform='false', emission='.2', specular='.1')
world = ET.SubElement(scene, 'worldbody')

def geom(name, pos, size, material='white', kind='box', collision=False, **attrs):
    a = dict(name='lab_'+name, type=kind, pos=' '.join(map(str,pos)), size=' '.join(map(str,size)), material='lab_'+material)
    if not collision: a.update(contype='0', conaffinity='0', group='2')
    a.update({k:str(v) for k,v in attrs.items()})
    return ET.SubElement(world, 'geom', a)

def light(name,pos,direction,diffuse,**kw):
    ET.SubElement(world, 'light', name=name, pos=pos, dir=direction, diffuse=diffuse, specular='.3 .3 .3', **kw)

light('daylight','-5 -4 8','1 .7 -1.6','.58 .59 .56', directional='true', castshadow='true')
light('ceiling_fill','1 3 4.2','0 0 -1','.32 .36 .40', directional='true', castshadow='false')
light('bench_fill','-6 3 3','1 -1 -1','.10 .14 .17', directional='true', castshadow='false')
light('interior_key','0 -2 4.3','0 .3 -1','.62 .61 .57', directional='false', castshadow='true', cutoff='100', exponent='1', attenuation='1 0 0')
# Match the original floor's collision properties so the policy retains its footing.
ET.SubElement(world, 'geom', name='floor', type='plane', size='0 0 .05', material='lab_floor')
for i in range(-8, 9): geom(f'floor_x_{i}', (i,0,.0004), (.006,6,.0003), 'seam')
for i in range(-6, 7): geom(f'floor_y_{i}', (0,i,.0004), (8,.006,.0003), 'seam')
# Thin painted perimeter around the clear 9 x 7 m walking area.
for x in [-4.5,4.5]: geom(f'arena_x_{x}',(x,0,.001),(.025,3.5,.0005),'teal')
for y in [-3.5,3.5]: geom(f'arena_y_{y}',(0,y,.001),(4.5,.025,.0005),'teal')
for x in [-4.5,4.5]:
    for y in [-3.5,3.5]: geom(f'corner_{x}_{y}',(x,y,.003),(.16,.16,.001),'amber')
# Two solid sides, with an open viewing side and a glass facade on the right.
geom('rear_wall',(0,6,2.4),(8,.13,2.4),'wall',collision=True)
geom('west_wall',(-8,0,2.4),(.13,6,2.4),'wall',collision=True)
for y in [-5.9,5.85]: geom(f'skirting_y_{y}',(0,y,.12),(8,.04,.12),'metal')
geom('skirting_west',(-7.84,0,.12),(.04,6,.12),'metal')
for x in range(-7,8,2):
    geom(f'wall_panel_{x}',(x,5.86,1.55),(.92,.02,1.25),'white')
    geom(f'wall_reveal_{x}',(x+1,5.83,2.2),(.012,.015,2),'metal')
geom('rear_light',(0,5.77,4.25),(7.6,.035,.025),'strip')
geom('west_light',(-7.75,0,4.25),(.035,5.6,.025),'strip')
# Rear sign in front of the architectural panels, facing into the room.
geom('brand_sign',(0,5.77,3.25),(2.3,.77,.001),'sign',kind='plane',quat='.70710678 .70710678 0 0')
# Glass mullions and a calm landscaped background beyond the facade.
for y in [-5,-2,1,4]:
    geom(f'glass_{y}',(7.9,y,2.3),(.035,1.43,2.2),'glass')
    geom(f'mullion_{y}',(7.82,y-1.5,2.3),(.065,.055,2.3),'metal')
for z in [.2,4.6]: geom(f'glass_beam_{z}',(7.82,0,z),(.065,6,.055),'metal')
geom('outside_lawn',(14,0,-.04),(5,15,.03),'leaf')
for i in range(6):
    x,y=12+(i%2)*3,-9+i*3.6
    geom(f'tree_trunk_{i}',(x,y,1.2),(.14,1.2),'wood',kind='cylinder')
    geom(f'tree_crown_{i}',(x,y,2.8),(.95,.95,1.3),'leaf',kind='ellipsoid')
# A skylight roof with perimeter panels and exposed beams.
for y in [-4.75,4.75]: geom(f'ceiling_y_{y}',(0,y,4.85),(8,1.25,.08),'white')
for x in [-6.5,6.5]: geom(f'ceiling_x_{x}',(x,0,4.85),(1.5,3.5,.08),'white')
for x in [-4.9,0,4.9]: geom(f'skylight_beam_{x}',(x,0,4.82),(.045,3.5,.07),'metal')
for y in [-3.5,0,3.5]: geom(f'skylight_frame_{y}',(0,y,4.82),(5,.045,.07),'metal')
geom('skylight',(0,0,4.91),(4.9,3.45,.018),'glass')

# Workstations, situated behind the walking zone.
for index,x in enumerate([-5.7,5.7]):
    y=4.65
    geom(f'bench_top_{index}',(x,y,.98),(1.45,.6,.06),'wood',collision=True)
    for dx in [-1.18,1.18]:
        geom(f'bench_leg_{index}_{dx}',(x+dx,y,.46),(.065,.43,.46),'metal',collision=True)
    geom(f'bench_drawer_{index}',(x-.7,y,.66),(.45,.49,.25),'white',collision=True)
    for z in [.53,.70,.85]: geom(f'drawer_handle_{index}_{z}',(x-.7,y-.51,z),(.24,.025,.012),'metal')
    geom(f'monitor_base_{index}',(x+.3,y,1.075),(.28,.2,.025),'metal')
    geom(f'monitor_stem_{index}',(x+.3,y+.12,1.32),(.035,.035,.23),'metal')
    geom(f'monitor_case_{index}',(x+.3,y+.14,1.63),(.55,.055,.34),'dark')
    geom(f'monitor_display_{index}',(x+.3,y+.079,1.63),(.515,.30,.001),'screen',kind='plane',quat='.70710678 .70710678 0 0')
    geom(f'keyboard_{index}',(x+.3,y-.05,1.055),(.38,.115,.018),'dark')
    geom(f'instrument_{index}',(x-1,y+.05,1.24),(.27,.3,.20),'white')
    geom(f'instrument_face_{index}',(x-1,y-.255,1.24),(.22,.01,.13),'dark')
    for k in range(3): geom(f'instrument_dial_{index}_{k}',(x-1.14+k*.13,y-.275,1.21),(.023,.012),'teal',kind='cylinder',quat='.70710678 .70710678 0 0')
# A dark server cabinet and a storage wall.
geom('rack',(-7.1,1.4,1.15),(.42,.58,1.15),'dark',collision=True)
for j in range(9):
    geom(f'rack_unit_{j}',(-6.66,1.4,.25+j*.22),(.014,.49,.085),'metal')
    for k in range(3): geom(f'rack_led_{j}_{k}',(-6.635,1.07+k*.09,.25+j*.22),(.006,.015,.012),'strip')
geom('storage',(-7.35,-2,1.15),(.45,1.25,1.15),'white',collision=True)
for y in [-2.65,-1.35]:
    geom(f'cabinet_door_{y}',(-6.89,y,1.2),(.012,.59,1.03),'wall')
    geom(f'cabinet_handle_{y}',(-6.86,y-.36,1.2),(.02,.025,.17),'metal')
# Planters and ceiling pendants, leaving the whole central floor clear.
for i,(x,y) in enumerate([(-6.9,-4.9),(6.7,5.1)]):
    geom(f'pot_{i}',(x,y,.30),(.27,.3),'white',kind='cylinder',collision=True)
    geom(f'soil_{i}',(x,y,.606),(.235,.007),'dark',kind='cylinder')
    for k in range(7):
        a=k*math.tau/7
        geom(f'plant_{i}_{k}',(x+.16*math.cos(a),y+.16*math.sin(a),.95+.06*(k%3)),(.12,.09,.4),'leaf',kind='ellipsoid',euler=f'{.25*math.sin(a)} {.25*math.cos(a)} {a}')
for x in [-4,0,4]:
    geom(f'pendant_{x}',(x,1,4.5),(1.3,.16,.065),'metal')
    geom(f'pendant_diffuser_{x}',(x,1,4.427),(1.24,.13,.012),'light')
    for dx in [-.9,.9]: geom(f'pendant_wire_{x}_{dx}',(x+dx,1,5),(.008,.008,.44),'dark')
ET.indent(scene, space='  ')
ET.ElementTree(scene).write(DEST / 'scene_lab.xml', encoding='unicode')

# Small free-standing Buddha: root is at the bottom of the flat base.
buddha = ET.SubElement(world, 'body', name='buddha', pos='1 0 .001')
ET.SubElement(buddha, 'freejoint', name='buddha_free')
ET.SubElement(buddha, 'inertial', pos='0 0 .065', mass='.15', diaginertia='.0003 .0003 .0002')
def statue(name, kind, pos, size, **attrs):
    ET.SubElement(buddha, 'geom', name='buddha_'+name, type=kind,
                  pos=pos, size=size, rgba='.78 .018 .025 1',
                  friction='1 .01 .001', condim='3', contype='2', conaffinity='2', **attrs)
statue('base', 'cylinder', '0 0 .012', '.068 .012')
statue('legs', 'ellipsoid', '0 0 .035', '.07 .052 .025')
statue('body', 'ellipsoid', '0 0 .078', '.039 .03 .049')
statue('head', 'sphere', '0 0 .142', '.027')
statue('topknot', 'sphere', '0 0 .174', '.008')
for side in [-1, 1]:
    statue('ear_'+str(side), 'ellipsoid', f'0 {side*.028} .137', '.009 .007 .018')
    statue('arm_'+str(side), 'capsule', f'.018 {side*.04} .078', '.012 .031',
           euler=f'{side*.45} .4 0')
statue('hands', 'ellipsoid', '.035 0 .058', '.016 .023 .011')
# Statue interacts with the room; rigid robot hands use the explicit grasp
# constraint rather than pushing the tiny object during assisted acquisition.
for room_geom in world.findall('geom'):
    if room_geom.get('contype', '1') != '0':
        room_geom.set('conaffinity', str(int(room_geom.get('conaffinity', '1')) | 2))
# Palm markers and a disabled point constraint. Both local anchor positions
# are set at acquisition, preserving the statue's current world pose.
robot_xml = ET.parse(DEST / 'g1_29dof.xml').getroot()
# Sites must live inside the included robot, so add them with an XML attachment
# in the generated scene through a generated copy of the robot description.
for side in ['left', 'right']:
    hand = robot_xml.find(f".//body[@name='{side}_wrist_yaw_link']")
    ET.SubElement(hand, 'site', name=side+'_palm', pos='.055 0 0', size='.008', rgba='0 0 0 0')
ET.ElementTree(robot_xml).write(DEST / 'g1_29dof_task.xml', encoding='unicode')
scene.find('include').set('file', 'g1_29dof_task.xml')
support = ET.SubElement(world, 'body', name='task_support', mocap='true', pos='0 0 .793')
equality = ET.SubElement(scene, 'equality')
ET.SubElement(equality, 'weld', name='task_base_support', body1='task_support', body2='pelvis',
              relpose='0 0 0 1 0 0 0', active='false', solref='.01 1', solimp='.99 .99 .001')
ET.SubElement(equality, 'connect', name='buddha_grasp', body1='left_wrist_yaw_link',
              body2='buddha', anchor='0 0 0', active='false', solref='.015 1')
ET.SubElement(world, 'site', name='buddha_drop', pos='5.7 4.22 1.04',
              type='cylinder', size='.16 .001', rgba='.1 .9 .55 .35')
ET.indent(scene, space='  ')
ET.ElementTree(scene).write(DEST / 'scene_lab_task.xml', encoding='unicode')
print(DEST / 'scene_lab.xml')
print(DEST / 'scene_lab_task.xml')

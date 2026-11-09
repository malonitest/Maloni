"""Attach preconverted CC-BY reference vehicles without runtime conversion dependencies."""
import json,os
from pathlib import Path
import xml.etree.ElementTree as E
LIBRARY=Path(__file__).with_name('assets')/'library'
MODELS={'tiggo4':('bmw-x1','BMW X1 2013'),'tiggo7':('volvo-xc60','Volvo XC60 2023'),'tiggo8':('chery-tiggo','CHERY Tiggo 8 Pro 2023')}

def add_reference_vehicle(asset,world,key,x,y):
    name,title=MODELS[key];manifest=json.loads((LIBRARY/(name+'.json')).read_text())
    for i,part in enumerate(manifest['parts']):
        label=key+'_reference_'+str(i);props=part['material']
        if props.get('texture'):
            E.SubElement(asset,'texture',name=label,type='2d',file=os.path.relpath(LIBRARY/props['texture'],LIBRARY.parent))
        E.SubElement(asset,'material',name=label,rgba=' '.join(map(str,props['rgba'])),specular=str(props['specular']),shininess=str(props['shininess']),metallic=str(props.get('metallic',0)),roughness=str(props.get('roughness',.5)),**({'texture':label} if props.get('texture') else {}))
        E.SubElement(asset,'mesh',name=label,file=os.path.relpath(LIBRARY/part['file'],LIBRARY.parent))
        E.SubElement(world,'geom',name=label,type='mesh',mesh=label,material=label,pos=f'{x} {y} .005',contype='0',conaffinity='0',group='2')
    bounds=manifest['bounds'];return title,max(abs(v[1]) for v in bounds)
